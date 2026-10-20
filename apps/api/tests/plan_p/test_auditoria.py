"""P0-07: bitácora de auditoría — registro explícito, red del middleware, consulta y tenencia."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.auditoria import registrar
from app.modelos.auditoria import EventoAuditoria
from app.modelos.nucleo import Cliente, Despacho, Usuario
from app.modelos.trabajos import Trabajo
from app.tenancy import Contexto, asegurar_usuario


def _eventos(sesionador, despacho: str | None = None) -> list[EventoAuditoria]:
    with sesionador() as db:
        consulta = select(EventoAuditoria).order_by(EventoAuditoria.id)
        if despacho:
            consulta = consulta.where(EventoAuditoria.despacho_id == despacho)
        return list(db.scalars(consulta))


def _cliente(sesionador, despacho: str, clave: str) -> int:
    with sesionador() as db:
        if db.get(Despacho, despacho) is None:
            db.add(Despacho(id=despacho))
            db.flush()
        c = Cliente(despacho_id=despacho, clave=clave, nombre=clave)
        db.add(c)
        db.commit()
        return c.id


def test_registrar_directo(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller")
    db_sesion.add(c)
    db_sesion.flush()
    ctx = Contexto(uid="uid-a", despacho_id="uid-a", rol="dueno", db=db_sesion)
    e = registrar(ctx, "cliente.alta", "cliente", c.id, {"rfc": "XAXX010101000"}, cliente=c)
    assert (e.uid, e.despacho_id, e.cliente_id) == ("uid-a", "uid-a", c.id)
    assert e.cliente_clave == "taller"
    assert e.fecha.tzinfo is not None and e.detalle == {"rfc": "XAXX010101000"}


def test_escritura_con_registro_explicito_deja_un_solo_renglon(api, sesionador):
    a = api("uid-a")
    a.get("/api/v1/trabajos")
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        t = Trabajo(tipo="x", estado="fallido", despacho_id="uid-a", cliente_id=cid,
                    ejecutar_en=datetime(2026, 1, 1, tzinfo=UTC))
        db.add(t)
        db.commit()
    assert a.post(f"/api/v1/trabajos/{t.id}/reintentar").status_code == 200
    eventos = _eventos(sesionador)
    assert len(eventos) == 1
    e = eventos[0]
    assert e.accion == "trabajo.reintentar" and e.entidad_id == str(t.id)
    assert e.uid == "uid-a" and e.cliente_clave == "taller" and e.fecha is not None


def test_escritura_fallida_la_deja_el_middleware_con_su_status(api, sesionador):
    a = api("uid-a")
    a.get("/api/v1/trabajos")
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        t = Trabajo(tipo="x", estado="hecho", despacho_id="uid-a", cliente_id=cid,
                    ejecutar_en=datetime(2026, 1, 1, tzinfo=UTC))
        db.add(t)
        db.commit()
    assert a.post(f"/api/v1/trabajos/{t.id}/reintentar").status_code == 409
    [e] = _eventos(sesionador)
    assert e.accion == "http.POST" and e.detalle["status"] == 409
    assert e.detalle["ruta"] == f"/api/v1/trabajos/{t.id}/reintentar"


def test_escritura_con_cliente_lleva_el_cliente_aunque_la_ruta_no_audite(api, sesionador):
    """`cliente_o_404` anota el cliente: el renglón de la red lo lleva."""
    a = api("uid-a")
    a.get("/api/v1/trabajos")
    _cliente(sesionador, "uid-a", "taller")
    a.post("/api/v1/trabajos/clientes/taller/diagnostico", params={"ejecutar_en": "2026-01-01"})
    [e] = _eventos(sesionador)
    assert e.accion == "http.POST" and e.detalle["status"] == 422
    assert e.cliente_clave == "taller"


def test_lecturas_y_anonimos_no_dejan_renglon(api, sesionador):
    a = api("uid-a")
    a.get("/api/v1/trabajos")
    a.get("/api/v1/auditoria")
    # Escritura sin autenticar: no hay a quién atribuirla.
    from fastapi.testclient import TestClient

    from app.main import app

    TestClient(app).post("/api/v1/trabajos/1/cancelar")
    assert _eventos(sesionador) == []


def test_consulta_filtros_y_paginado(api, sesionador):
    a = api("uid-a")
    a.get("/api/v1/auditoria")
    _cliente(sesionador, "uid-a", "uno")
    with sesionador() as db:
        for i in range(5):
            db.add(EventoAuditoria(
                despacho_id="uid-a", uid="uid-a" if i % 2 == 0 else "otro",
                cliente_clave="uno" if i < 3 else None,
                accion="cliente.alta" if i < 2 else "trabajo.cancelar",
                fecha=datetime(2026, 10, 10 + i, 18, 0, tzinfo=UTC),
            ))
        db.commit()
    todo = a.get("/api/v1/auditoria").json()
    assert todo["total"] == 5 and todo["eventos"][0]["fecha"].startswith("2026-10-14")

    assert a.get("/api/v1/auditoria", params={"usuario": "otro"}).json()["total"] == 2
    assert a.get("/api/v1/auditoria", params={"cliente": "uno"}).json()["total"] == 3
    assert a.get("/api/v1/auditoria", params={"accion": "trabajo.*"}).json()["total"] == 3
    assert a.get("/api/v1/auditoria", params={"accion": "cliente.alta"}).json()["total"] == 2
    rango = a.get("/api/v1/auditoria", params={"desde": "2026-10-11", "hasta": "2026-10-12"})
    assert rango.json()["total"] == 2
    al_reves = {"desde": "2026-10-12", "hasta": "2026-10-11"}
    assert a.get("/api/v1/auditoria", params=al_reves).status_code == 422

    pag = a.get("/api/v1/auditoria", params={"por_pagina": 2, "pagina": 3}).json()
    assert pag["total"] == 5 and len(pag["eventos"]) == 1 and pag["pagina"] == 3


def test_fechas_del_filtro_en_hora_de_cdmx(api, sesionador):
    """Las 23:30 del día 10 en CDMX son el 11 en UTC: cuenta como del día 10."""
    a = api("uid-a")
    a.get("/api/v1/auditoria")
    with sesionador() as db:
        db.add(EventoAuditoria(despacho_id="uid-a", uid="uid-a", accion="x",
                               fecha=datetime(2026, 10, 11, 5, 30, tzinfo=UTC)))
        db.commit()
    dia_10 = {"desde": "2026-10-10", "hasta": "2026-10-10"}
    assert a.get("/api/v1/auditoria", params=dia_10).json()["total"] == 1
    assert a.get("/api/v1/auditoria", params={"desde": "2026-10-11"}).json()["total"] == 0


def test_multi_tenant(api, sesionador):
    a, b = api("uid-a"), api("uid-b")
    a.get("/api/v1/auditoria")
    b.get("/api/v1/auditoria")
    with sesionador() as db:
        db.add(EventoAuditoria(despacho_id="uid-a", uid="uid-a", accion="secreto"))
        db.commit()
    assert b.get("/api/v1/auditoria").json()["total"] == 0
    assert b.get("/api/v1/auditoria", params={"usuario": "uid-a"}).json()["total"] == 0
    assert a.get("/api/v1/auditoria").json()["total"] == 1
    # La escritura fallida de B contra un trabajo de A queda en la bitácora de B, no de A.
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        t = Trabajo(tipo="x", estado="fallido", despacho_id="uid-a", cliente_id=cid,
                    ejecutar_en=datetime(2026, 1, 1, tzinfo=UTC))
        db.add(t)
        db.commit()
    assert b.post(f"/api/v1/trabajos/{t.id}/reintentar").status_code == 404
    assert [e.accion for e in _eventos(sesionador, "uid-a")] == ["secreto"]
    [de_b] = _eventos(sesionador, "uid-b")
    assert de_b.uid == "uid-b" and de_b.detalle["status"] == 404 and de_b.cliente_id is None


def test_solo_dueno_y_contador(api, sesionador):
    api("uid-a").get("/api/v1/auditoria")
    with sesionador() as db:
        db.add_all([
            Usuario(uid="cont", despacho_id="uid-a", rol="contador"),
            Usuario(uid="aux", despacho_id="uid-a", rol="auxiliar"),
        ])
        db.commit()
    assert api("cont").get("/api/v1/auditoria").status_code == 200
    assert api("aux").get("/api/v1/auditoria").status_code == 403


def test_borrar_el_cliente_no_borra_su_rastro(sesionador):
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        db.add(EventoAuditoria(despacho_id="uid-a", uid="uid-a", accion="x",
                               cliente_id=cid, cliente_clave="taller"))
        db.commit()
        db.delete(db.get(Cliente, cid))
        db.commit()
    [e] = _eventos(sesionador)
    assert e.cliente_id is None and e.cliente_clave == "taller"
