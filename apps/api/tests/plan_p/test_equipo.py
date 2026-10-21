"""
P5-01: varios usuarios por despacho — invitaciones de un solo uso con vencimiento, aceptación
(mover un despacho autocreado vacío), roles, desactivar, asignaciones, límite del plan y
auditoría. "Listo cuando": un auxiliar sólo ve los clientes que le asignaron.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import almacen_cartera
from app.equipo import servicio
from app.integraciones import registro
from app.modelos.auditoria import EventoAuditoria
from app.modelos.equipo import Invitacion
from app.modelos.nucleo import Despacho, Usuario
from app.planes import PLANES
from app.tenancy import asegurar_usuario
from tests.cartera.test_cartera_crud import CLIENTE

NUEVO = {**CLIENTE, "id": "nuevo"}

DUENO = "uid-dueno"


@pytest.fixture
def correo():
    registro.limpiar_cache()
    return registro.obtener("correo")


def _despacho(sesionador, uid: str = DUENO, plan: str = "despacho", clientes=("a", "b", "c")):
    with sesionador() as db:
        asegurar_usuario(db, uid)
        db.get(Despacho, uid).plan = plan
        for clave in clientes:
            almacen_cartera.crear_cliente(db, uid, clave, {"nombre": f"Cliente {clave}"},
                                          con_tope=False)
        db.commit()


def _invitar(api, correo, mail: str, rol: str = "auxiliar", uid: str = DUENO) -> str:
    r = api(uid).post("/api/v1/equipo/invitaciones", json={"correo": mail, "rol": rol})
    assert r.status_code == 200, r.text
    enviado = correo.enviados[-1]
    assert enviado.destinatarios == [mail]
    return re.search(r"aceptar-invitacion\?token=([\w-]+)", enviado.html).group(1)


def _aceptar(api, uid: str, token: str):
    return api(uid).post("/api/v1/equipo/invitaciones/aceptar", json={"token": token})


def _claves(api, uid: str) -> list[str]:
    r = api(uid).get("/api/v1/cartera/clientes")
    assert r.status_code == 200, r.text
    return sorted(c["id"] for c in r.json()["clientes"])


def test_auxiliar_solo_ve_lo_asignado_tras_aceptar_y_asignar(api, sesionador, correo):
    _despacho(sesionador)
    token = _invitar(api, correo, "aux@ejemplo.mx")
    r = _aceptar(api, "uid-aux", token)
    assert r.status_code == 200, r.text
    assert r.json() == {"exito": True, "despacho_id": DUENO, "rol": "auxiliar"}
    assert _claves(api, "uid-aux") == []
    assert api(DUENO).post("/api/v1/equipo/usuarios/uid-aux/clientes/b").status_code == 200
    assert _claves(api, "uid-aux") == ["b"]
    assert api("uid-aux").get("/api/v1/cartera/clientes/a/empleados").status_code == 404
    assert api(DUENO).delete("/api/v1/equipo/usuarios/uid-aux/clientes/b").status_code == 200
    assert _claves(api, "uid-aux") == []
    # El dueño sigue viendo todo.
    assert _claves(api, DUENO) == ["a", "b", "c"]


def test_la_invitacion_es_de_un_solo_uso(api, sesionador, correo):
    _despacho(sesionador)
    token = _invitar(api, correo, "x@ejemplo.mx", "contador")
    assert _aceptar(api, "uid-x", token).status_code == 200
    r = _aceptar(api, "uid-y", token)
    assert r.status_code == 409 and "ya se usó" in r.json()["error"]
    # El token no se guarda en claro.
    with sesionador() as db:
        inv = db.scalar(select(Invitacion))
        assert inv.token_hash != token and inv.token_hash == servicio.hash_token(token)


def test_invitacion_expirada_y_token_invalido(api, sesionador, correo):
    _despacho(sesionador)
    token = _invitar(api, correo, "x@ejemplo.mx")
    with sesionador() as db:
        inv = db.scalar(select(Invitacion))
        inv.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert _aceptar(api, "uid-x", token).status_code == 410
    assert _aceptar(api, "uid-x", "token-que-no-existe-1234").status_code == 404


def test_la_invitacion_vence_a_los_7_dias(api, sesionador, correo):
    _despacho(sesionador)
    _invitar(api, correo, "x@ejemplo.mx")
    with sesionador() as db:
        inv = db.scalar(select(Invitacion))
        creado = inv.creado_en.replace(tzinfo=inv.creado_en.tzinfo or UTC)
        dias = (inv.expira_en - creado).total_seconds() / 86400
    assert 6.99 < dias < 7.01


def test_limite_de_usuarios_del_plan(api, sesionador, correo):
    _despacho(sesionador, plan="contador")  # 1 usuario: el dueño ya lo ocupa
    r = api(DUENO).post("/api/v1/equipo/invitaciones", json={"correo": "x@e.mx", "rol": "auxiliar"})
    assert r.status_code == 409 and "Contador" in r.json()["error"]
    assert correo.enviados == []
    # En el plan despacho caben 10: el dueño + 9 invitaciones; la décima ya no.
    assert api(DUENO).put("/api/v1/equipo/plan", json={"plan": "despacho"}).status_code == 200
    for i in range(PLANES["despacho"].max_usuarios - 1):
        _invitar(api, correo, f"u{i}@e.mx")
    r = api(DUENO).post("/api/v1/equipo/invitaciones", json={"correo": "z@e.mx", "rol": "auxiliar"})
    assert r.status_code == 409
    # Reinvitar al mismo correo no gasta otro lugar: revoca la anterior.
    _invitar(api, correo, "u0@e.mx")
    # Revocar libera el lugar.
    inv_id = api(DUENO).get("/api/v1/equipo").json()["invitaciones"][0]["id"]
    assert api(DUENO).delete(f"/api/v1/equipo/invitaciones/{inv_id}").status_code == 200
    _invitar(api, correo, "z@e.mx")


def test_al_aceptar_tambien_se_revisa_el_limite(api, sesionador, correo):
    _despacho(sesionador)
    token = _invitar(api, correo, "x@e.mx")
    with sesionador() as db:  # el despacho baja de plan "a mano" con la invitación viva
        db.get(Despacho, DUENO).plan = "contador"
        db.commit()
    r = _aceptar(api, "uid-x", token)
    assert r.status_code == 409 and "tope" in r.json()["error"]


def test_el_limite_de_clientes_sale_de_planes(api, sesionador):
    _despacho(sesionador, plan="contador", clientes=[f"c{i}" for i in range(25)])
    r = api(DUENO).put("/api/v1/cartera/clientes/nuevo", json=NUEVO)
    assert r.status_code == 409 and "25" in r.json()["error"]
    assert api(DUENO).put("/api/v1/equipo/plan", json={"plan": "despacho"}).status_code == 200
    r = api(DUENO).put("/api/v1/cartera/clientes/nuevo", json=NUEVO)
    assert r.status_code == 200, r.text
    # Bajar a un plan que ya no alcanza se permite (T8): se conserva todo, pero no entra más.
    assert api(DUENO).put("/api/v1/equipo/plan", json={"plan": "contador"}).status_code == 200
    assert api(DUENO).put("/api/v1/cartera/clientes/otro",
                          json={**NUEVO, "id": "otro"}).status_code == 409
    assert api(DUENO).put("/api/v1/cartera/clientes/nuevo", json=NUEVO).status_code == 200


def test_planes_del_front_y_del_back_coinciden():
    ts = (Path(__file__).resolve().parents[4] / "apps/store/src/services/planes.ts").read_text()
    for p in PLANES.values():
        bloque = ts.split(f"id: '{p.id}'", 1)[1].split("incluye", 1)[0]
        assert f"maxUsuarios: {p.max_usuarios}," in bloque, p.id
        assert f"maxClientes: {p.max_clientes}," in bloque, p.id


def test_solo_el_dueno_gestiona(api, sesionador, correo):
    _despacho(sesionador)
    _aceptar(api, "uid-cont", _invitar(api, correo, "c@e.mx", "contador"))
    _aceptar(api, "uid-aux", _invitar(api, correo, "a@e.mx", "auxiliar"))
    for uid in ("uid-cont", "uid-aux"):
        c = api(uid)
        assert c.post("/api/v1/equipo/invitaciones",
                      json={"correo": "q@e.mx", "rol": "auxiliar"}).status_code == 403
        assert c.put("/api/v1/equipo/usuarios/uid-aux/rol",
                     json={"rol": "dueno"}).status_code == 403
        assert c.post("/api/v1/equipo/usuarios/uid-aux/clientes/a").status_code == 403
        assert c.post("/api/v1/equipo/usuarios/uid-aux/desactivar").status_code == 403
        assert c.put("/api/v1/equipo/plan", json={"plan": "contador"}).status_code == 403
        cuerpo = c.get("/api/v1/equipo").json()
        assert cuerpo["puede_gestionar"] is False and cuerpo["invitaciones"] == []
    cuerpo = api(DUENO).get("/api/v1/equipo").json()
    assert cuerpo["puede_gestionar"] is True
    assert {u["uid"]: u["rol"] for u in cuerpo["usuarios"]} == {
        DUENO: "dueno", "uid-cont": "contador", "uid-aux": "auxiliar"}


def test_cambio_de_rol_desactivar_y_ultimo_dueno(api, sesionador, correo):
    _despacho(sesionador)
    _aceptar(api, "uid-x", _invitar(api, correo, "x@e.mx", "contador"))
    d = api(DUENO)
    assert d.put("/api/v1/equipo/usuarios/uid-x/rol", json={"rol": "auxiliar"}).status_code == 200
    assert _claves(api, "uid-x") == []  # ya es auxiliar sin asignaciones
    # El último dueño no se degrada ni se desactiva a sí mismo.
    r = d.put(f"/api/v1/equipo/usuarios/{DUENO}/rol", json={"rol": "contador"})
    assert r.status_code == 409
    assert d.post(f"/api/v1/equipo/usuarios/{DUENO}/desactivar").status_code == 422
    # Desactivado: ya no entra.
    assert d.post("/api/v1/equipo/usuarios/uid-x/desactivar").status_code == 200
    assert api("uid-x").get("/api/v1/cartera/clientes").status_code == 403
    assert d.post("/api/v1/equipo/usuarios/uid-x/reactivar").status_code == 200
    assert api("uid-x").get("/api/v1/cartera/clientes").status_code == 200


def test_cada_cambio_queda_en_la_auditoria(api, sesionador, correo):
    _despacho(sesionador)
    _aceptar(api, "uid-x", _invitar(api, correo, "x@e.mx"))
    d = api(DUENO)
    d.post("/api/v1/equipo/usuarios/uid-x/clientes/a")
    d.delete("/api/v1/equipo/usuarios/uid-x/clientes/a")
    d.put("/api/v1/equipo/usuarios/uid-x/rol", json={"rol": "contador"})
    d.post("/api/v1/equipo/usuarios/uid-x/desactivar")
    d.post("/api/v1/equipo/usuarios/uid-x/reactivar")
    d.put("/api/v1/equipo/plan", json={"plan": "despacho"})
    with sesionador() as db:
        acciones = [e.accion for e in db.scalars(select(EventoAuditoria).where(
            EventoAuditoria.despacho_id == DUENO).order_by(EventoAuditoria.id))
            if e.accion.startswith("equipo.")]
    assert acciones == ["equipo.invitar", "equipo.aceptar_invitacion", "equipo.asignar_cliente",
                        "equipo.desasignar_cliente", "equipo.cambiar_rol", "equipo.desactivar",
                        "equipo.reactivar", "equipo.cambiar_plan"]


def test_mueve_el_despacho_autocreado_vacio_y_rechaza_si_tiene_datos(api, sesionador, correo):
    _despacho(sesionador)
    # uid-v entró antes y se le autocreó su despacho (vacío): se mueve.
    assert api("uid-v").get("/api/v1/cartera/clientes").json()["total"] == 0
    assert _aceptar(api, "uid-v", _invitar(api, correo, "v@e.mx")).status_code == 200
    with sesionador() as db:
        assert db.get(Usuario, "uid-v").despacho_id == DUENO
    # uid-d tiene su propio despacho con un cliente: error claro, nada se mueve.
    _despacho(sesionador, uid="uid-d", clientes=["propio"])
    r = _aceptar(api, "uid-d", _invitar(api, correo, "d@e.mx"))
    assert r.status_code == 409 and "propio despacho con datos" in r.json()["error"]
    with sesionador() as db:
        assert db.get(Usuario, "uid-d").despacho_id == "uid-d"
        assert db.scalar(select(Invitacion).where(Invitacion.correo == "d@e.mx")).aceptada_en \
            is None


def test_multi_tenant(api, sesionador, correo):
    _despacho(sesionador)
    _despacho(sesionador, uid="uid-otro", clientes=["ajeno"])
    _aceptar(api, "uid-x", _invitar(api, correo, "x@e.mx"))
    d = api(DUENO)
    # No se asigna un cliente de otro despacho, ni se toca a un usuario de otro despacho.
    assert d.post("/api/v1/equipo/usuarios/uid-x/clientes/ajeno").status_code == 404
    assert d.put("/api/v1/equipo/usuarios/uid-otro/rol", json={"rol": "auxiliar"}).status_code \
        == 404
    assert d.post("/api/v1/equipo/usuarios/uid-otro/desactivar").status_code == 404
    # El otro despacho no ve mi equipo ni revoca mis invitaciones.
    _invitar(api, correo, "y@e.mx")
    inv_id = d.get("/api/v1/equipo").json()["invitaciones"][0]["id"]
    assert api("uid-otro").delete(f"/api/v1/equipo/invitaciones/{inv_id}").status_code == 404
    assert {u["uid"] for u in api("uid-otro").get("/api/v1/equipo").json()["usuarios"]} == {
        "uid-otro"}
