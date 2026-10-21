"""
P3-10: calendario de vencimientos de la cartera (prórroga por sexto dígito, día 17 inhábil
corregido, fiscales + patronales + credenciales) y agenda semanal multi-tenant.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.credenciales import servicio as cred_servicio
from app.fiscal_engine import vencimientos as v
from app.fiscal_engine.calendario import generar_calendario
from app.modelos.nucleo import Cliente, Empleado
from app.tenancy import asegurar_usuario
from tests.plan_p import certs_sat

PF_1 = "PERJ800101AB1"  # sexto dígito 1 → +1 día hábil
PF_9 = "PERJ800109AB1"  # 9 → +5
PF_3 = "PERJ800103AB1"  # 3 → +2
PF_5 = "PERJ800105AB1"  # 5 → +3
PM = "EMP010101AB1"


def _fecha(rfc: str, regimen: str, anio: int, clave: str, **kw) -> date:
    return {x.clave: x for x in v.vencimientos_fiscales(rfc, regimen, anio, **kw)}[clave] \
        .fecha_limite


def test_prorroga_por_sexto_digito_solo_personas_fisicas():
    assert v.sexto_digito(PF_9) == 9 and v.sexto_digito(PM) == 1
    # febrero 2026 vence el martes 17 de marzo; dígito 5 → +3 hábiles = viernes 20
    assert _fecha(PF_5, "612", 2026, "mensual:2026-02") == date(2026, 3, 20)
    # la persona moral no tiene prórroga del decreto
    assert _fecha(PM, "601", 2026, "mensual:2026-02") == date(2026, 3, 17)
    # dictaminada: tampoco
    assert _fecha(PF_5, "612", 2026, "mensual:2026-02", dictamina=True) == date(2026, 3, 17)


def test_dia_17_inhabil_corregido():
    # septiembre 2026: el 17 de octubre es sábado → persona moral, lunes 19
    assert _fecha(PM, "601", 2026, "mensual:2026-09") == date(2026, 10, 19)
    # abril 2026: 17 de mayo domingo; dígito 1 → el primer hábil después del 17 (lunes 18)
    assert _fecha(PF_1, "626", 2026, "mensual:2026-04") == date(2026, 5, 18)
    # dígito 9 → cinco hábiles después del 17: 19, 20, 21, 22, 23 de octubre
    assert _fecha(PF_9, "612", 2026, "mensual:2026-09") == date(2026, 10, 23)
    # diciembre 2026 vence en enero 2027 (17 domingo → lunes 18 para la moral)
    assert _fecha(PM, "601", 2026, "mensual:2026-12") == date(2027, 1, 18)


def test_dias_inhabiles_del_cff_dentro_de_la_prorroga():
    # 2028: el tercer lunes de marzo es el 20 (inhábil, Art. 12 CFF). Febrero 2028 vence el
    # viernes 17; dígito 3 → +2 hábiles saltando el 20: martes 21 y miércoles 22.
    assert _fecha(PF_3, "612", 2028, "mensual:2028-02") == date(2028, 3, 22)
    # 2029: el 17 de noviembre es sábado y el lunes 19 es el tercer lunes → martes 20.
    assert _fecha(PM, "601", 2029, "mensual:2029-10") == date(2029, 11, 20)


def test_diot_balanza_y_anual():
    pm = {x.clave: x for x in v.vencimientos_fiscales(PM, "601", 2026)}
    assert pm["diot:2026-03"].fecha_limite == date(2026, 4, 30)
    assert pm["balanza:2026-03"].fecha_limite == date(2026, 5, 4)  # 3 de mayo es domingo
    assert pm["anual:2026"].fecha_limite == date(2027, 3, 31)
    resico = {x.clave: x for x in v.vencimientos_fiscales(PF_1, "626", 2026)}
    assert not any(k.startswith(("diot:", "balanza:")) for k in resico)
    assert resico["anual:2026"].fecha_limite == date(2027, 4, 30)


def test_el_calendario_viejo_ya_no_cae_en_fin_de_semana():
    obligaciones = generar_calendario("independiente", "612", "XAXX010101000", 2026)
    for o in obligaciones:
        if o.periodicidad == "mensual":
            assert date.fromisoformat(o.fecha_limite).weekday() < 5, o


# ── por la API ──


@pytest.fixture
def cartera(sesionador, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    pf = Cliente(despacho_id="uid-a", clave="pf", nombre="Persona Fisica", rfc=PF_9,
                 datos={"regimen": "612"})
    pm = Cliente(despacho_id="uid-a", clave="pm", nombre="Moral Patron", rfc=PM,
                 datos={"regimen": "601"})
    db.add_all([pf, pm, Cliente(despacho_id="uid-b", clave="ajeno", nombre="Ajeno", rfc=PM,
                                datos={"regimen": "601"})])
    db.flush()
    db.add(Empleado(cliente_id=pm.id, empleado_no="1", datos={}))
    par = certs_sat.generar(rfc=PF_9, tipo="efirma", dias_hasta=20)
    cred_servicio.guardar(db, pf, "efirma", par.cer, par.key, par.password, "uid-a")
    db.commit()
    db.close()


def test_semana_con_cada_vencimiento_de_cada_cliente(api, cartera):
    a = api("uid-a")
    r = a.get("/api/v1/calendario/cartera",
              params={"desde": "2026-10-19", "hasta": "2026-10-25"})
    assert r.status_code == 200, r.text
    obl = {(o["cliente"], o["clave"]): o for o in r.json()["obligaciones"]}
    # septiembre 2026: la moral el lunes 19 (17 sábado), la física con dígito 9 el viernes 23
    assert obl[("pm", "mensual:2026-09")]["fecha_limite"] == "2026-10-19"
    assert obl[("pf", "mensual:2026-09")]["fecha_limite"] == "2026-10-23"
    assert "sexto dígito" in obl[("pf", "mensual:2026-09")]["nota"]
    # patronales sólo del cliente con empleados, y sin duplicar el ISR retenido
    patronales = [k for k in obl if k[1].startswith("patronal:")]
    assert patronales and all(k[0] == "pm" for k in patronales)
    assert not any("isr_retenido" in k[1] for k in patronales)
    assert not any(k[0] == "ajeno" for k in obl)

    # credencial de la persona física
    hoy = date.today()
    r = a.get("/api/v1/calendario/cartera", params={
        "desde": hoy.isoformat(), "hasta": (hoy + timedelta(days=30)).isoformat(),
        "tipo": "credencial"})
    assert [o["cliente"] for o in r.json()["obligaciones"]] == ["pf"]


def test_presentada_a_mano_y_por_declaracion(api, cartera):
    a = api("uid-a")
    params = {"desde": "2026-10-19", "hasta": "2026-10-25", "cliente": "pf", "tipo": "fiscal"}
    r = a.post("/api/v1/clientes/pf/declaraciones", json={
        "tipo": "mensual", "periodo": "2026-09", "fecha_presentacion": "2026-10-20",
        "ingresos_declarados": "15000.00"})
    assert r.status_code == 200 and r.json()["origen"] == "declaracion"
    (o,) = [x for x in a.get("/api/v1/calendario/cartera", params=params).json()
            ["obligaciones"] if x["clave"] == "mensual:2026-09"]
    assert o["estado"] == "presentada" and o["origen_estado"] == "declaracion"
    r = a.put("/api/v1/clientes/pf/obligaciones/estado",
              json={"clave": "mensual:2026-09", "estado": "pendiente"})
    assert r.status_code == 200
    (o,) = [x for x in a.get("/api/v1/calendario/cartera", params=params).json()
            ["obligaciones"] if x["clave"] == "mensual:2026-09"]
    assert o["estado"] in ("pendiente", "vencida")
    # B no puede marcar obligaciones de un cliente de A
    assert api("uid-b").put("/api/v1/clientes/pf/obligaciones/estado", json={
        "clave": "mensual:2026-09", "estado": "presentada"}).status_code == 404


def test_tareas_multitenant_y_generadas_desde_obligaciones(api, cartera):
    a, b = api("uid-a"), api("uid-b")
    r = a.post("/api/v1/agenda/tareas", json={
        "titulo": "Pedir estados de cuenta", "fecha": "2026-10-20", "cliente": "pm",
        "responsable_uid": "uid-a"})
    assert r.status_code == 200, r.text
    tarea = r.json()["tarea"]
    assert tarea["cliente"] == "pm" and tarea["responsable_uid"] == "uid-a"
    # responsable de otro despacho: no
    assert a.post("/api/v1/agenda/tareas", json={
        "titulo": "x", "fecha": "2026-10-20", "responsable_uid": "uid-b"}).status_code == 422
    # B no ve, no edita, no borra y no crea tareas en clientes de A
    semana = {"desde": "2026-10-19", "hasta": "2026-10-25"}
    assert b.get("/api/v1/agenda/tareas", params=semana).json()["tareas"] == []
    assert b.put(f"/api/v1/agenda/tareas/{tarea['id']}", json={"estado": "hecha"}) \
        .status_code == 404
    assert b.delete(f"/api/v1/agenda/tareas/{tarea['id']}").status_code == 404
    assert b.post("/api/v1/agenda/tareas", json={
        "titulo": "x", "fecha": "2026-10-20", "cliente": "pm"}).status_code == 404

    r = a.post("/api/v1/agenda/tareas/desde-obligaciones", json={**semana, "cliente": "pf"})
    assert r.status_code == 200 and r.json()["creadas"] >= 1
    assert a.post("/api/v1/agenda/tareas/desde-obligaciones",
                  json={**semana, "cliente": "pf"}).json()["creadas"] == 0
    tareas = a.get("/api/v1/agenda/tareas", params=semana).json()["tareas"]
    assert {t["origen"] for t in tareas} == {"manual", "obligacion"}
    r = a.put(f"/api/v1/agenda/tareas/{tarea['id']}", json={"estado": "hecha"})
    assert r.json()["tarea"]["estado"] == "hecha"
    assert a.get("/api/v1/agenda/usuarios").json()["usuarios"][0]["uid"] == "uid-a"
    assert a.delete(f"/api/v1/agenda/tareas/{tarea['id']}").status_code == 200
