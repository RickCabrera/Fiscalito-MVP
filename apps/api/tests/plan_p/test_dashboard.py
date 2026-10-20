"""
P5-02: dashboard del despacho — una llamada con datos de varias fuentes (calendario, alertas,
descarga SAT, opinión, credenciales, nómina, agenda, cobranza), visibilidad del auxiliar,
multi-tenant y sin N+1 (las consultas no crecen con los clientes).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import event, select

from app import almacen_cartera
from app.modelos.agenda import TareaAgenda
from app.modelos.alertas import AlertaFiscal
from app.modelos.cobranza import CargoCobranza
from app.modelos.credenciales import CredencialCliente
from app.modelos.nomina import NominaPeriodo
from app.modelos.nucleo import AsignacionCliente, Cliente, Despacho, Usuario
from app.modelos.sat_descarga import AlertaDescargaSat, ConfigDescargaSat
from app.modelos.sat_verificacion import DocumentoCumplimiento
from app.tenancy import asegurar_usuario

A = "uid-a"
HOY = date(2026, 10, 19)
RFC_PM = "EMP010101AB1"


def _sembrar(sesionador, uid: str = A, n: int = 2) -> dict[str, int]:
    """`n` clientes persona moral 601; al primero le pone una fuente de cada tarjeta."""
    with sesionador() as db:
        asegurar_usuario(db, uid)
        db.get(Despacho, uid).plan = "despacho"
        ids = {}
        for i in range(n):
            c = almacen_cartera.crear_cliente(db, uid, f"c{i}", {
                "nombre": f"Cliente {i}", "rfc": RFC_PM, "regimen": "601"}, con_tope=False)
            ids[c.clave] = c.id
        cid = ids["c0"]
        db.add_all([
            AlertaFiscal(despacho_id=uid, cliente_id=cid, tipo="efos", severidad="alta",
                         titulo="EFOS", fecha=HOY, clave="a1"),
            AlertaFiscal(despacho_id=uid, cliente_id=cid, tipo="opinion", severidad="media",
                         titulo="Opinión", fecha=HOY, clave="a2"),
            AlertaFiscal(despacho_id=uid, cliente_id=cid, tipo="x", severidad="baja",
                         titulo="Resuelta", fecha=HOY, clave="a3", resuelta=True),
            ConfigDescargaSat(cliente_id=cid, activa=True),
            AlertaDescargaSat(cliente_id=cid, tipo="sin_efirma", mensaje="Sin e.firma"),
            DocumentoCumplimiento(cliente_id=cid, tipo="opinion", fecha=HOY - timedelta(days=3),
                                  resultado="negativa", origen="portal_sat", ruta_pdf="x",
                                  sha256="0" * 64),
            CredencialCliente(cliente_id=cid, tipo="efirma", rfc=RFC_PM, numero_certificado="1",
                              valido_desde=datetime(2022, 1, 1, tzinfo=UTC),
                              valido_hasta=datetime(2026, 11, 1, tzinfo=UTC),
                              cer_der=b"", key_cifrada=b"", password_cifrada=b""),
            NominaPeriodo(cliente_id=cid, despacho_id=uid, inicio=date(2026, 10, 1),
                          fin=date(2026, 10, 15), fecha_pago=date(2026, 10, 15),
                          estado="calculada"),
            NominaPeriodo(cliente_id=cid, despacho_id=uid, inicio=date(2026, 9, 16),
                          fin=date(2026, 9, 30), fecha_pago=date(2026, 9, 30), estado="cerrada"),
            NominaPeriodo(cliente_id=cid, despacho_id=uid, inicio=date(2026, 9, 1),
                          fin=date(2026, 9, 15), fecha_pago=date(2026, 9, 15), estado="timbrada"),
            TareaAgenda(despacho_id=uid, cliente_id=cid, titulo="Mía", fecha=HOY,
                        responsable_uid=uid),
            TareaAgenda(despacho_id=uid, cliente_id=cid, titulo="De otro", fecha=HOY,
                        responsable_uid="otro"),
            CargoCobranza(despacho_id=uid, cliente_id=cid, tipo="iguala", concepto="Iguala",
                          clave="iguala:2026-09", periodo="2026-09", fecha=date(2026, 9, 5),
                          vencimiento=date(2026, 9, 15), importe=Decimal("5000")),
        ])
        db.commit()
        return ids


def _tablero(api, uid: str = A) -> dict:
    r = api(uid).get("/api/v1/dashboard", params={"hoy": HOY.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def test_dashboard_con_datos_de_varias_fuentes(api, sesionador):
    _sembrar(sesionador)
    d = _tablero(api)
    assert d["clientes"] == 2
    # Calendario: la mensual de septiembre de una PM vence el lunes 19 de octubre (hoy).
    claves = {(r["cliente"], r["clave"]) for r in d["vencimientos"]["renglones"]}
    assert ("c0", "mensual:2026-09") in claves and ("c1", "mensual:2026-09") in claves
    assert all(r["enlace"].startswith("/app/calendario") for r in d["vencimientos"]["renglones"])
    assert {k: d["alertas"][k] for k in ("total", "alta", "media", "baja")} == {
        "total": 2, "alta": 1, "media": 1, "baja": 0}
    sat = {r["cliente"]: r["estado"] for r in d["descarga_sat"]["renglones"]}
    assert sat == {"c0": "con_error", "c1": "sin_configurar"}
    op = {r["cliente"]: r["semaforo"] for r in d["opinion"]["renglones"]}
    assert op == {"c0": "rojo", "c1": "gris"} and d["opinion"]["rojo"] == 1
    assert d["credenciales"]["renglones"][0]["dias"] == 13
    assert d["credenciales"]["renglones"][0]["enlace"] == "/app/clientes/c0"
    assert (d["nominas"]["por_cerrar"], d["nominas"]["por_timbrar"]) == (1, 1)
    assert d["nominas"]["renglones"][0]["enlace"] == "/app/clientes/c0/nomina"
    assert [t["titulo"] for t in d["agenda"]["renglones"]] == ["Mía"]
    assert d["cobranza"]["vencido"] == "5000.00"
    assert d["cobranza"]["renglones"][0]["enlace"] == "/app/cobranza?cliente=c0"
    # Toda tarjeta lleva a su detalle.
    for tarjeta in ("vencimientos", "credenciales", "alertas", "descarga_sat", "opinion",
                    "agenda", "cobranza"):
        assert d[tarjeta]["enlace"].startswith("/app/"), tarjeta


def test_auxiliar_solo_ve_sus_asignados(api, sesionador):
    ids = _sembrar(sesionador)
    with sesionador() as db:
        db.add(Usuario(uid="uid-aux", despacho_id=A, rol="auxiliar"))
        db.flush()
        db.add(AsignacionCliente(usuario_uid="uid-aux", cliente_id=ids["c1"]))
        db.commit()
    d = _tablero(api, "uid-aux")
    assert d["clientes"] == 1
    assert d["alertas"]["total"] == 0
    assert {r["cliente"] for r in d["vencimientos"]["renglones"]} == {"c1"}
    assert [r["cliente"] for r in d["opinion"]["renglones"]] == ["c1"]
    assert d["credenciales"]["total"] == 0 and d["nominas"]["por_cerrar"] == 0
    assert d["cobranza"] is None  # los honorarios no son del auxiliar


def test_multi_tenant(api, sesionador):
    _sembrar(sesionador)
    d = _tablero(api, "uid-b")  # despacho nuevo y vacío
    assert d["clientes"] == 0 and d["alertas"]["total"] == 0
    assert d["vencimientos"]["renglones"] == [] and d["cobranza"]["vencido"] == "0.00"


def test_sin_n_mas_1(api, sesionador):
    _sembrar(sesionador, n=2)
    motor = sesionador.kw["bind"]
    cuenta = {"n": 0}

    def contar(*_a, **_k):
        cuenta["n"] += 1

    event.listen(motor, "before_cursor_execute", contar)
    try:
        _tablero(api)
        con_dos = cuenta["n"]
        with sesionador() as db:
            for i in range(2, 12):
                almacen_cartera.crear_cliente(db, A, f"c{i}", {
                    "nombre": f"Cliente {i}", "rfc": RFC_PM, "regimen": "601"}, con_tope=False)
            db.commit()
        cuenta["n"] = 0
        _tablero(api)
        con_doce = cuenta["n"]
    finally:
        event.remove(motor, "before_cursor_execute", contar)
    assert con_doce == con_dos, (con_dos, con_doce)
    with sesionador() as db:
        assert len(list(db.scalars(select(Cliente)))) == 12
