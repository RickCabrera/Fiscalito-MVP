"""
P5-08: suscripciones y cobro de planes con el adaptador de pagos falso.

"Listo cuando": un despacho se suscribe, cambia de plan y se le bloquea lo que rebasa su plan
(clientes, usuarios, módulos, solo lectura al vencer), sin borrar nada; webhook firmado e
idempotente con historial de pagos; multi-tenant.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app import almacen_cartera
from app.exceptions import FiscalAgentError
from app.integraciones import pagos, registro
from app.modelos.auditoria import EventoAuditoria
from app.modelos.nucleo import Cliente, Despacho
from app.modelos.suscripciones import Suscripcion
from app.planes import PLANES, modulos_del_plan
from app.suscripciones.vigencia import asegurar, vigencia
from app.tenancy import asegurar_usuario
from tests.cartera.test_cartera_crud import CLIENTE
from tests.plan_p.test_integraciones import Grabadora, grabada

FIX = Path(__file__).resolve().parents[1] / "fixtures"
A, B = "uid-desp-a", "uid-desp-b"
WEBHOOK = "/api/v1/pagos/webhook"


def _clientes(sesionador, uid: str, n: int) -> None:
    with sesionador() as db:
        asegurar_usuario(db, uid)
        for i in range(n):
            almacen_cartera.crear_cliente(db, uid, f"c{i}", {"nombre": f"C{i}"}, con_tope=False)
        db.commit()


def _alta(api, uid: str, clave: str):
    return api(uid).put(f"/api/v1/cartera/clientes/{clave}", json={**CLIENTE, "id": clave})


def _evento(api, cuerpo: dict):
    """Manda un evento firmado por el adaptador falso, como lo haría el proveedor."""
    crudo = json.dumps(cuerpo).encode()
    falso = registro.obtener("pagos")
    return api("sin-sesion").post(WEBHOOK, content=crudo, headers={
        **falso.firmar(crudo), "Authorization": ""})


def _estado(api, uid: str = A) -> dict:
    r = api(uid).get("/api/v1/suscripcion")
    assert r.status_code == 200, r.text
    return r.json()


def _mover_fin(sesionador, uid: str, dias: float) -> None:
    with sesionador() as db:
        s = db.get(Suscripcion, uid)
        s.fin_periodo = datetime.now(UTC) + timedelta(days=dias)
        db.commit()


# ── el flujo de "Listo cuando" ──


def test_suscribirse_cambiar_y_bloquear_lo_que_rebasa(api, sesionador, monkeypatch):
    monkeypatch.setenv("FISCALITO_PLAN_CONTADOR_PRECIO", "100.00")  # placeholder de prueba
    _clientes(sesionador, A, 25)
    j = _estado(api)
    assert j["suscripcion"]["estado"] == "prueba" and j["suscripcion"]["vigente"]
    assert j["suscripcion"]["plan"] == "contador" and j["puede_gestionar"]
    precios = {p["id"]: p["precio_mensual"] for p in j["planes"]}
    assert precios == {"contador": "100.00", "despacho": None}  # sin variable: sin cifra
    assert {b["tipo"] for b in j["bloqueos"]} == {
        "clientes", "usuarios", "modulo:dispersion", "modulo:imss_archivos"}

    # Alta del cobro al plan Contador.
    r = api(A).post("/api/v1/suscripcion", json={"plan": "contador"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "activa"
    falso = registro.obtener("pagos")
    [(sid, sub)] = falso.suscripciones.items()
    assert sub["plan"] == "contador" and sub["estado"] == "active"
    assert api(A).post("/api/v1/suscripcion", json={"plan": "despacho"}).status_code == 409

    # Al tope de clientes: el alta se bloquea con el motivo.
    r = _alta(api, A, "nuevo")
    assert r.status_code == 409 and "25 clientes" in r.json()["error"]

    # Cambio a Despacho: se cambia en el proveedor y se desbloquea.
    assert api(A).put("/api/v1/suscripcion/plan", json={"plan": "despacho"}).status_code == 200
    assert falso.suscripciones[sid]["plan"] == "despacho"
    assert _alta(api, A, "nuevo").status_code == 200
    assert _estado(api)["bloqueos"] == []

    # Bajar a Contador con 26 clientes: no se borra nada, sólo se bloquean altas.
    assert api(A).put("/api/v1/suscripcion/plan", json={"plan": "contador"}).status_code == 200
    with sesionador() as db:
        assert db.scalar(select(func.count()).select_from(Cliente).where(
            Cliente.despacho_id == A)) == 26
    assert _alta(api, A, "otro").status_code == 409
    assert _alta(api, A, "nuevo").status_code == 200  # editar uno existente sí
    motivo = {b["tipo"]: b["motivo"] for b in _estado(api)["bloqueos"]}["clientes"]
    assert "Llevas 26" in motivo and "conservas todos" in motivo


def test_modulos_por_plan(api, sesionador, monkeypatch):
    from tests.plan_p.nomina_cerrada import nomina_cerrada

    n = nomina_cerrada(api, sesionador, uid=A)  # deja el plan en Despacho
    url = f"/api/v1/nomina/clientes/{n['clave']}/periodos/{n['pid']}/dispersion"
    assert n["http"].post(url, json={"layout": "generico"}).status_code == 200
    assert api(A).put("/api/v1/suscripcion/plan", json={"plan": "contador"}).status_code == 200
    r = n["http"].post(url, json={"layout": "generico"})
    assert r.status_code == 403
    assert "no incluye Dispersión bancaria" in r.json()["error"] and "Despacho" in r.json()[
        "error"]
    # Configurable en un solo lugar: la variable abre el módulo al plan Contador.
    monkeypatch.setenv("FISCALITO_PLANES_MODULOS", json.dumps({"contador": ["dispersion"]}))
    assert modulos_del_plan(PLANES["contador"]) == {"dispersion"}
    assert n["http"].post(url, json={"layout": "generico"}).status_code == 200
    # Un JSON roto no abre nada.
    monkeypatch.setenv("FISCALITO_PLANES_MODULOS", "{roto")
    assert modulos_del_plan(PLANES["contador"]) == frozenset()


def test_limite_de_usuarios_tras_bajar_de_plan(api, sesionador):
    _clientes(sesionador, A, 0)
    api(A).post("/api/v1/suscripcion", json={"plan": "despacho"})
    r = api(A).post("/api/v1/equipo/invitaciones", json={"correo": "x@e.mx", "rol": "auxiliar"})
    assert r.status_code == 200, r.text
    api(A).put("/api/v1/suscripcion/plan", json={"plan": "contador"})
    r = api(A).post("/api/v1/equipo/invitaciones", json={"correo": "y@e.mx", "rol": "auxiliar"})
    assert r.status_code == 409 and "Contador" in r.json()["error"]
    # La invitación ya mandada se conserva.
    assert len(api(A).get("/api/v1/equipo").json()["invitaciones"]) == 1


# ── webhook ──


def test_webhook_firmado_idempotente_y_con_historial(api, sesionador):
    _clientes(sesionador, A, 1)
    api(A).post("/api/v1/suscripcion", json={"plan": "contador"})
    sid = next(iter(registro.obtener("pagos").suscripciones))
    fin = (datetime.now(UTC) + timedelta(days=60)).replace(microsecond=0)
    evento = {"id_evento": "ev-1", "tipo": "pago_exitoso", "id": sid,
              "datos": {"monto": "499.00", "moneda": "mxn", "fin_periodo": fin.isoformat()}}

    # Sin firma o con firma ajena: 400 y nada cambia. Es ruta pública: no pide sesión.
    crudo = json.dumps(evento).encode()
    r = api("x").post(WEBHOOK, content=crudo, headers={"X-Fiscalito-Firma": "00",
                                                       "Authorization": ""})
    assert r.status_code == 400

    r = _evento(api, evento)
    assert r.status_code == 200 and r.json() == {
        "exito": True, "duplicado": False, "resultado": "aplicado"}
    r = _evento(api, evento)
    assert r.json()["duplicado"] is True
    j = _estado(api)
    assert j["suscripcion"]["fin_periodo"] == fin.isoformat()
    assert [(p["estado"], p["monto"], p["moneda"]) for p in j["pagos"]] == [
        ("pagado", "499.00", "MXN")]

    # Pago fallido: morosa, sigue vigente pero con aviso.
    _evento(api, {"id_evento": "ev-2", "tipo": "pago_fallido", "id": sid,
                  "datos": {"monto": "499.00", "moneda": "MXN"}})
    j = _estado(api)
    assert j["suscripcion"]["estado"] == "morosa" and j["suscripcion"]["vigente"]
    assert "No hemos recibido el pago" in j["suscripcion"]["aviso"]
    assert [p["estado"] for p in j["pagos"]] == ["fallido", "pagado"]

    # Evento de una suscripción que no conocemos: 200, se registra y no toca a nadie.
    r = _evento(api, {"id_evento": "ev-3", "tipo": "pago_exitoso", "id": "sub_ajena"})
    assert r.json()["resultado"] == "sin_suscripcion"

    # Cancelación desde el proveedor.
    _evento(api, {"id_evento": "ev-4", "tipo": "suscripcion_cancelada", "id": sid})
    assert _estado(api)["suscripcion"]["estado"] == "cancelada"


def test_alta_pendiente_se_aplica_con_el_primer_pago(api, sesionador, monkeypatch):
    _clientes(sesionador, A, 0)
    falso = registro.obtener("pagos")
    monkeypatch.setattr(falso, "crear_suscripcion", lambda c, p: pagos.Suscripcion(
        "sub_pend", "incomplete", "https://pago.ejemplo/checkout"))
    r = api(A).post("/api/v1/suscripcion", json={"plan": "despacho"})
    assert r.json()["url_pago"] == "https://pago.ejemplo/checkout"
    assert r.json()["plan"] == "contador" and r.json()["plan_pendiente"] == "despacho"
    _evento(api, {"id_evento": "e1", "tipo": "pago_exitoso", "id": "sub_pend"})
    j = _estado(api)
    assert j["suscripcion"]["plan"] == "despacho" and j["suscripcion"]["estado"] == "activa"
    assert j["suscripcion"]["plan_pendiente"] is None


# ── solo lectura ──


def test_vencida_es_solo_lectura_sin_borrar_y_se_reactiva(api, sesionador):
    _clientes(sesionador, A, 2)
    asegurar_prueba = _estado(api)  # crea la suscripción en prueba
    assert asegurar_prueba["suscripcion"]["estado"] == "prueba"
    _mover_fin(sesionador, A, -1)  # la prueba terminó ayer
    j = _estado(api)
    assert j["suscripcion"]["estado"] == "vencida" and j["suscripcion"]["solo_lectura"]
    assert j["bloqueos"][0]["tipo"] == "solo_lectura"
    r = _alta(api, A, "nuevo")
    assert r.status_code == 402 and "solo lectura" in r.json()["error"]
    assert api(A).put("/api/v1/cartera/clientes/c0", json={**CLIENTE, "id": "c0"}
                      ).status_code == 402
    # Leer sigue: los datos están completos.
    assert api(A).get("/api/v1/cartera/clientes").json()["total"] == 2
    # Las rutas de suscripción no se bloquean: suscribirse saca del bloqueo.
    assert api(A).post("/api/v1/suscripcion", json={"plan": "contador"}).status_code == 200
    assert _alta(api, A, "nuevo").status_code == 200


def test_cancelar_conserva_acceso_hasta_fin_de_periodo(api, sesionador):
    _clientes(sesionador, A, 1)
    api(A).post("/api/v1/suscripcion", json={"plan": "contador"})
    r = api(A).post("/api/v1/suscripcion/cancelar")
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    assert next(iter(registro.obtener("pagos").suscripciones.values()))["estado"] == "canceled"
    assert api(A).post("/api/v1/suscripcion/cancelar").status_code == 409
    j = _estado(api)
    assert j["suscripcion"]["vigente"] and "conservas el acceso" in j["suscripcion"]["aviso"]
    assert _alta(api, A, "dentro").status_code == 200
    _mover_fin(sesionador, A, -0.01)
    assert _alta(api, A, "fuera").status_code == 402
    assert api(A).get("/api/v1/cartera/clientes").json()["total"] == 2


def test_tabla_de_vigencia(db_sesion):
    db_sesion.add(Despacho(id="d"))
    db_sesion.flush()
    s = asegurar(db_sesion, "d")
    t = s.fin_periodo
    assert vigencia(s, t - timedelta(seconds=1)).estado == "prueba"
    assert not vigencia(s, t).vigente
    s.estado = "activa"
    assert vigencia(s, t - timedelta(seconds=1)).estado == "activa"
    v = vigencia(s, t + timedelta(days=1))  # sin renovación, dentro de la gracia
    assert v.estado == "morosa" and v.vigente
    assert not vigencia(s, t + timedelta(days=4)).vigente  # gracia default: 3 días
    s.estado = "cancelada"
    assert vigencia(s, t - timedelta(seconds=1)).vigente
    assert vigencia(s, t).estado == "cancelada" and not vigencia(s, t).vigente


# ── permisos y multi-tenant ──


def test_solo_el_dueno_y_multi_tenant(api, sesionador):
    _clientes(sesionador, A, 1)
    _clientes(sesionador, B, 1)
    api(A).post("/api/v1/suscripcion", json={"plan": "despacho"})
    sid_a = next(iter(registro.obtener("pagos").suscripciones))
    _evento(api, {"id_evento": "pa", "tipo": "pago_exitoso", "id": sid_a,
                  "datos": {"monto": "1.00", "moneda": "MXN"}})
    jb = _estado(api, B)
    assert jb["suscripcion"]["plan"] == "contador" and jb["suscripcion"]["estado"] == "prueba"
    assert jb["pagos"] == [] and not jb["suscripcion"]["con_cobro"]
    # A vence: B sigue escribiendo.
    _mover_fin(sesionador, A, -30)
    with sesionador() as db:
        db.get(Suscripcion, A).estado = "vencida"
        db.commit()
    assert _alta(api, A, "x").status_code == 402
    assert _alta(api, B, "x").status_code == 200
    # Un contador del despacho ve el estado pero no lo cambia.
    with sesionador() as db:
        from app.modelos.nucleo import Usuario

        db.add(Usuario(uid="uid-cont-b", despacho_id=B, rol="contador"))
        db.commit()
    c = api("uid-cont-b")
    assert c.get("/api/v1/suscripcion").json()["puede_gestionar"] is False
    assert c.put("/api/v1/suscripcion/plan", json={"plan": "despacho"}).status_code == 403
    assert c.post("/api/v1/suscripcion/cancelar").status_code == 403
    assert c.post("/api/v1/suscripcion", json={"plan": "despacho"}).status_code == 403


def test_cada_movimiento_queda_en_la_auditoria(api, sesionador):
    _clientes(sesionador, A, 0)
    api(A).post("/api/v1/suscripcion", json={"plan": "contador"})
    api(A).put("/api/v1/suscripcion/plan", json={"plan": "despacho"})
    sid = next(iter(registro.obtener("pagos").suscripciones))
    _evento(api, {"id_evento": "x1", "tipo": "pago_exitoso", "id": sid})
    api(A).post("/api/v1/suscripcion/cancelar")
    with sesionador() as db:
        acciones = [e.accion for e in db.scalars(select(EventoAuditoria).where(
            EventoAuditoria.despacho_id == A).order_by(EventoAuditoria.id))
            if e.accion.startswith("suscripcion.")]
    assert acciones == ["suscripcion.alta", "suscripcion.cambiar_plan",
                        "suscripcion.webhook.pago_exitoso", "suscripcion.cancelar"]


# ── adaptador real (Stripe) con respuestas grabadas ──


def test_stripe_normaliza_factura_pagada_y_cambia_plan():
    g = Grabadora({
        "/subscriptions/sub_PRUEBA456": httpx.Response(
            200, json=grabada("pagos/stripe_subscription_items.json")),
    })
    s = pagos.PagosStripe("sk_test_x", "whsec_x", http=g.cliente())
    r = s.cambiar_plan("sub_PRUEBA456", "price_despacho")
    assert r.estado == "active"
    assert g.peticiones[0].method == "GET" and g.peticiones[1].method == "POST"
    from urllib.parse import parse_qsl

    enviado = dict(parse_qsl(g.peticiones[1].content.decode()))
    assert enviado["items[0][id]"] == "si_RENGLON1"
    assert enviado["items[0][price]"] == "price_despacho"

    cuerpo = (FIX / "pagos/stripe_invoice_paid.json").read_bytes()
    t = str(int(time.time()))
    v1 = hmac.new(b"whsec_x", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    ev = s.parsear_webhook(cuerpo, {"Stripe-Signature": f"t={t},v1={v1}"})
    assert (ev.clase, ev.id_evento, ev.suscripcion_externa) == (
        "pago_exitoso", "evt_FACTURA_PAGADA", "sub_PRUEBA456")
    assert str(ev.monto) == "499.00" and ev.moneda == "MXN"
    assert ev.fin_periodo == datetime.fromtimestamp(1794355200, UTC)


def test_mercadopago_no_cambia_plan_en_sitio():
    m = pagos.PagosMercadoPago("APP_USR-x", "secreto", http=httpx.Client())
    with pytest.raises(FiscalAgentError) as e:
        m.cambiar_plan("x", "plan-2")
    assert e.value.status_code == 409
