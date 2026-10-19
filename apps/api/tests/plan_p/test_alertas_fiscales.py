"""
P3-09: alertas fiscales. Cada regla dispara, no se duplica al correr otra vez, se resuelve
sola cuando la situación pasa, y las rutas respetan la tenencia.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.alertas import reglas
from app.config import settings
from app.modelos.agenda import EstadoObligacion
from app.modelos.alertas import AlertaFiscal
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import Poliza
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import AlertaDescargaSat
from app.modelos.sat_verificacion import AlertaRiesgo, DocumentoCumplimiento
from app.modelos.trabajos import Trabajo
from app.tenancy import asegurar_usuario
from app.trabajos.cola import encolar, procesar_siguiente
from tests.plan_p.cfdi_sintetico import uuid_n

HOY = date(2026, 10, 19)
RFC_PF = "PERJ800109AB1"  # RESICO PF, sexto dígito 9


def _comp(cliente_id: int, n: int, fecha: datetime, total: str, **kw) -> Comprobante:
    base = dict(cliente_id=cliente_id, uuid=uuid_n(n), version="4.0", tipo="I", fecha=fecha,
                rfc_emisor=RFC_PF, rfc_receptor="COM010101BB2", direccion="emitido",
                subtotal=Decimal(total), total=Decimal(total), metodo_pago="PUE",
                ruta_xml=f"x/{n}.xml", sha256="0" * 64, datos={})
    base.update(kw)
    return Comprobante(**base)


@pytest.fixture
def escenario(sesionador, monkeypatch):
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    c = Cliente(despacho_id="uid-a", clave="resico", nombre="Resico PF", rfc=RFC_PF,
                datos={"regimen": "626"})
    otro = Cliente(despacho_id="uid-b", clave="ajeno", nombre="Ajeno", rfc=RFC_PF,
                   datos={"regimen": "626"})
    db.add_all([c, otro])
    db.flush()
    # ingresos cobrados 2026: 2.9 millones (83 % del tope de 3.5)
    db.add(_comp(c.id, 1, datetime(2026, 2, 10), "2900000.00"))
    # febrero tiene póliza; marzo tiene CFDI y ninguna póliza
    db.add(Poliza(cliente_id=c.id, tipo="ingreso", anio=2026, mes=2, numero=1,
                  fecha=date(2026, 2, 10), clave_origen=f"cfdi:{uuid_n(1)}",
                  uuid_cfdi=uuid_n(1)))
    db.add(_comp(c.id, 2, datetime(2026, 3, 5), "100.00"))
    # CFDI cancelado ante el SAT con póliza activa sin reversa
    db.add(_comp(c.id, 3, datetime(2026, 4, 5), "50.00", estatus_sat="cancelado"))
    db.add(Poliza(cliente_id=c.id, tipo="ingreso", anio=2026, mes=4, numero=1,
                  fecha=date(2026, 4, 5), clave_origen=f"cfdi:{uuid_n(3)}",
                  uuid_cfdi=uuid_n(3)))
    db.add(AlertaRiesgo(despacho_id="uid-a", cliente_id=c.id, tipo="art69b", clave="69b:EFO",
                        rfc="EFO010101AA1", nombre="FACTURERA", lista="69b",
                        situacion="definitivo", relacion="proveedor", nivel="alto"))
    db.add(DocumentoCumplimiento(cliente_id=c.id, tipo="opinion", fecha=date(2026, 10, 1),
                                 resultado="negativa", origen="manual", ruta_pdf="x.pdf",
                                 sha256="0" * 64))
    db.add(AlertaDescargaSat(cliente_id=c.id, tipo="atorada", mensaje="Lleva 3 días."))
    # septiembre declarado con ingresos que no cuadran con la bóveda (cobrado 0)
    db.add(EstadoObligacion(cliente_id=c.id, clave="mensual:2026-09", estado="presentada",
                            origen="declaracion", fecha_presentacion=date(2026, 10, 15),
                            ingresos_declarados=Decimal("50000")))
    # e.firma que vence 5 días después de HOY. La regla sólo lee la vigencia: el renglón se
    # inserta directo para no depender de la fecha real en que corra la suite.
    db.add(CredencialCliente(
        cliente_id=c.id, tipo="efirma", rfc=RFC_PF, numero_certificado="0" * 20,
        valido_desde=datetime(2024, 1, 1, tzinfo=UTC),
        valido_hasta=datetime.combine(HOY + timedelta(days=5), datetime.min.time(), UTC),
        cer_der=b"", key_cifrada=b"", password_cifrada=b""))
    db.commit()
    db.close()


def _alertas(db) -> dict[str, AlertaFiscal]:
    return {a.clave: a for a in db.scalars(select(AlertaFiscal))}


def test_cada_regla_dispara_y_no_duplica(escenario, sesionador):
    db = sesionador()
    c = db.scalar(select(Cliente).where(Cliente.clave == "resico"))
    r = reglas.evaluar_cliente(db, c, HOY)
    db.commit()
    tipos = {a.tipo for a in _alertas(db).values()}
    assert tipos == set(reglas.REGLAS), set(reglas.REGLAS) - tipos
    claves = _alertas(db)
    assert "tope_resico:2026:80" in claves and claves["tope_resico:2026:80"].severidad == "media"
    assert f"cfdi_cancelado:{uuid_n(3)}" in claves
    assert "sin_polizas:2026-03" in claves and "sin_polizas:2026-02" not in claves
    assert "diferencia:2026-09" in claves
    # vencimiento: la declaración de septiembre de la PF (dígito 9) vence el 23 de octubre
    assert "vencimiento:mensual:2026-09" not in claves  # ya presentada
    assert any(k.startswith("vencimiento:") for k in claves)
    assert any(k.startswith("credencial:") and k.endswith(":7") for k in claves)
    total = r["creadas"]

    otra = reglas.evaluar_cliente(db, c, HOY)
    db.commit()
    assert otra["creadas"] == 0 and otra["resueltas"] == 0
    assert db.scalar(select(func.count()).select_from(AlertaFiscal)) == total


def test_se_resuelve_sola_y_lo_resuelto_a_mano_no_se_reabre(escenario, sesionador):
    db = sesionador()
    c = db.scalar(select(Cliente).where(Cliente.clave == "resico"))
    reglas.evaluar_cliente(db, c, HOY)
    claves = _alertas(db)
    claves["opinion:1"].resuelta, claves["opinion:1"].resuelta_por = True, "uid-a"
    db.scalar(select(AlertaRiesgo)).atendida = True
    db.commit()
    reglas.evaluar_cliente(db, c, HOY)
    db.commit()
    claves = _alertas(db)
    efos = [a for a in claves.values() if a.tipo == "efos"][0]
    assert efos.resuelta and efos.resuelta_por == "sistema"
    assert claves["opinion:1"].resuelta and claves["opinion:1"].resuelta_por == "uid-a"


def test_rutas_listar_conteo_resolver_y_tenencia(api, escenario):
    a, b = api("uid-a"), api("uid-b")
    r = a.post("/api/v1/alertas/evaluar", params={"cliente": "resico"})
    assert r.status_code == 200, r.text
    lista = a.get("/api/v1/alertas").json()["alertas"]
    assert lista and lista[0]["severidad"] == "alta"
    conteo = a.get("/api/v1/alertas/conteo").json()
    assert conteo["total"] == len(lista) and conteo["por_cliente"]["resico"]["total"] == \
        len(lista)
    altas = a.get("/api/v1/alertas", params={"severidad": "alta"}).json()["alertas"]
    assert {x["severidad"] for x in altas} == {"alta"}
    # B no ve ni resuelve las alertas de A
    assert b.get("/api/v1/alertas").json()["alertas"] == []
    assert b.get("/api/v1/alertas", params={"cliente": "resico"}).status_code == 404
    assert b.post(f"/api/v1/alertas/{lista[0]['id']}/resolver").status_code == 404
    r = a.post(f"/api/v1/alertas/{lista[0]['id']}/resolver")
    assert r.status_code == 200 and r.json()["alerta"]["resuelta"] is True
    assert a.get("/api/v1/alertas/conteo").json()["total"] == len(lista) - 1
    resueltas = a.get("/api/v1/alertas", params={"resuelta": True}).json()["alertas"]
    assert [x["id"] for x in resueltas] == [lista[0]["id"]]


def test_trabajo_diario_encola_un_trabajo_por_cliente(escenario, sesionador):
    db = sesionador()
    encolar(db, "alertas.programado", {"hoy": HOY.isoformat()})
    db.commit()
    db.close()
    import app.alertas.trabajos  # noqa: F401 — registra los manejadores

    hechos = []
    for _ in range(5):
        t = procesar_siguiente(sesionador, ahora=datetime.now(UTC) + timedelta(minutes=1))
        if t is None:
            break
        hechos.append((t.tipo, t.estado))
    assert ("alertas.programado", "hecho") in hechos
    assert sum(1 for tipo, estado in hechos if tipo == "alertas.evaluar" and
               estado == "hecho") == 2
    db = sesionador()
    assert db.scalar(select(func.count()).select_from(AlertaFiscal)) > 0
    assert db.scalar(select(func.count()).select_from(Trabajo)) == 3
