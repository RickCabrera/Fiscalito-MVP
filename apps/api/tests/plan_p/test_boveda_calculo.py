"""
P1-06: los módulos leen la bóveda.

"Listo cuando": con la bóveda cargada, la pre-declaración del mes sale sin subir un archivo;
los cancelados y la nómina no cuentan. Aquí se prueba la forma exacta del CFDI de cálculo,
las exclusiones, los pagos PPD con su complemento (también cuando el original es de otro
mes) y el multi-tenant. CFDI sintéticos (`cfdi_sintetico.py`).
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.boveda_cfdi import calculo
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.schemas.fiscal import CFDI
from app.tenancy import asegurar_usuario
from tests.plan_p.cfdi_sintetico import (
    RFC_CLIENTE,
    RFC_COMPRADOR,
    RFC_PROVEEDOR,
    cfdi,
    pago,
    uuid_n,
)

BASE = "/api/v1/boveda/clientes"
CALC = "/api/v1/clientes"

# Marzo 2026 del cliente (RFC_CLIENTE):
U_VENTA = uuid_n(1)        # emitida PUE, marzo
U_GASTO = uuid_n(2)        # recibida PUE, marzo, con retenciones
U_CANCELADA = uuid_n(3)    # emitida PUE, marzo, cancelada ante el SAT
U_NOMINA = uuid_n(4)       # nómina que el cliente emitió a un trabajador, marzo
U_PPD_FEB = uuid_n(5)      # emitida PPD en FEBRERO
U_PAGO = uuid_n(6)         # complemento de pago en marzo que liquida U_PPD_FEB
U_PPD_MAR = uuid_n(7)      # emitida PPD en marzo, sin pago: no debe sumar
U_ABRIL = uuid_n(8)        # emitida en abril: fuera del periodo


def _ppd(xml: bytes) -> bytes:
    return xml.replace(b'MetodoPago="PUE"', b'MetodoPago="PPD"')


def _con_retenciones(xml: bytes) -> bytes:
    """Agrega retenciones de ISR (10 %) e IVA (2/3) al nodo global de impuestos."""
    return xml.replace(
        b'<cfdi:Impuestos TotalImpuestosTrasladados="160.00">',
        b'<cfdi:Impuestos TotalImpuestosTrasladados="160.00" TotalImpuestosRetenidos="206.67">'
        b'<cfdi:Retenciones><cfdi:Retencion Impuesto="001" Importe="100.00"/>'
        b'<cfdi:Retencion Impuesto="002" Importe="106.67"/></cfdi:Retenciones>',
    ).replace(b'Total="1160.00"', b'Total="953.33"')


def _lote() -> list[tuple[str, bytes]]:
    return [
        ("venta.xml", cfdi(U_VENTA, fecha="2026-03-05T10:00:00")),
        ("gasto.xml", _con_retenciones(cfdi(U_GASTO, emisor=RFC_PROVEEDOR,
                                            receptor=RFC_CLIENTE, fecha="2026-03-06T10:00:00"))),
        ("cancelada.xml", cfdi(U_CANCELADA, fecha="2026-03-07T10:00:00")),
        ("nomina.xml", cfdi(U_NOMINA, tipo="N", receptor="TRAB010101AA1",
                            fecha="2026-03-15T10:00:00", subtotal="5000.00", total="5000.00")),
        ("ppd-feb.xml", _ppd(cfdi(U_PPD_FEB, fecha="2026-02-20T10:00:00"))),
        ("pago.xml", pago(U_PAGO, [U_PPD_FEB])),
        ("ppd-mar.xml", _ppd(cfdi(U_PPD_MAR, fecha="2026-03-25T10:00:00",
                                  subtotal="9000.00", total="10440.00", iva="1440.00"))),
        ("abril.xml", cfdi(U_ABRIL, fecha="2026-04-01T00:00:00")),
    ]


@pytest.fixture
def almacen_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    return tmp_path / "almacen"


@pytest.fixture
def boveda_cargada(api, sesionador, almacen_dir):
    """Despacho A con `taller` (612) y su marzo cargado; despacho B con `otro` (mismo RFC)."""
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([
        Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE,
                datos={"rfc": RFC_CLIENTE, "regimen": "612"}),
        Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE,
                datos={"rfc": RFC_CLIENTE, "regimen": "612"}),
    ])
    db.commit()
    db.close()

    a = api("uid-a")
    archivos = [("archivos", (n, x, "text/xml")) for n, x in _lote()]
    r = a.post(f"{BASE}/taller/cfdi", files=archivos)
    assert r.json()["importados"] == 8, r.text

    # P1-03 marcó una como cancelada.
    db = sesionador()
    comp = db.scalar(select(Comprobante).where(Comprobante.uuid == U_CANCELADA))
    comp.estatus_sat = "cancelado"
    db.commit()
    db.close()
    return a


def _marzo(a, **params):
    return a.get(f"{BASE}/taller/facturas-calculo",
                 params={"desde": "2026-03-01", "hasta": "2026-03-31", **params})


# ── forma exacta y exclusiones ──


def test_forma_exacta_del_cfdi_de_calculo(boveda_cargada):
    r = _marzo(boveda_cargada)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    por_uuid = {f["uuid"]: f for f in cuerpo["facturas"]}

    # Cada factura valida contra el esquema de cálculo y trae exactamente sus campos.
    for f in cuerpo["facturas"] + cuerpo["relacionados"]:
        assert set(f) == set(CFDI.model_fields)
        CFDI.model_validate(f)

    assert por_uuid[U_VENTA] == {
        "uuid": U_VENTA, "fecha": "2026-03-05", "tipo": "I",
        "rfc_emisor": RFC_CLIENTE, "rfc_receptor": RFC_COMPRADOR,
        "subtotal": 1000.0, "total": 1160.0, "iva_trasladado": 160.0,
        "iva_retenido": 0.0, "isr_retenido": 0.0, "descuento": 0.0, "uso_cfdi": "G03",
        "descripcion": "Servicio", "clave_prod_serv": "84111506", "metodo_pago": "PUE",
        "uuid_relacionado": None, "monto_pago": None,
    }
    gasto = por_uuid[U_GASTO]
    assert (gasto["isr_retenido"], gasto["iva_retenido"], gasto["total"]) == (100.0, 106.67, 953.33)
    assert gasto["rfc_emisor"] == RFC_PROVEEDOR


def test_cancelados_y_nomina_no_cuentan(boveda_cargada):
    cuerpo = _marzo(boveda_cargada).json()
    uuids = {f["uuid"] for f in cuerpo["facturas"]}
    assert U_CANCELADA not in uuids
    assert U_NOMINA not in uuids
    assert U_ABRIL not in uuids
    assert all(f["tipo"] in {"I", "E", "P", "T"} for f in cuerpo["facturas"])
    assert uuids == {U_VENTA, U_GASTO, U_PAGO, U_PPD_MAR}
    assert cuerpo["resumen"] == {
        "comprobantes": 4, "emitidos": 3, "recibidos": 1,
        "por_tipo": {"I": 3, "P": 1},
        "cancelados_excluidos": 1, "nomina_excluidos": 1,
        "relacionados_fuera_del_periodo": 1,
    }


def test_pago_ppd_con_complemento_y_original_de_otro_mes(boveda_cargada):
    cuerpo = _marzo(boveda_cargada).json()
    pago_ = next(f for f in cuerpo["facturas"] if f["tipo"] == "P")
    assert pago_["uuid"] == U_PAGO
    assert pago_["uuid_relacionado"] == U_PPD_FEB
    assert pago_["monto_pago"] == 1160.0
    assert (pago_["rfc_emisor"], pago_["rfc_receptor"]) == (RFC_CLIENTE, RFC_COMPRADOR)
    # El original PPD de febrero viaja aparte para que el motor pueda cruzarlo.
    assert [f["uuid"] for f in cuerpo["relacionados"]] == [U_PPD_FEB]
    assert cuerpo["relacionados"][0]["metodo_pago"] == "PPD"


def test_filtro_por_tipos_y_validaciones(boveda_cargada):
    a = boveda_cargada
    solo_p = _marzo(a, tipos="P").json()
    assert [f["tipo"] for f in solo_p["facturas"]] == ["P"]
    assert _marzo(a, tipos="N").status_code == 422  # la nómina no se pide para cálculos
    assert _marzo(a, tipos="I,Z").status_code == 422
    assert a.get(f"{BASE}/taller/facturas-calculo",
                 params={"desde": "2026-04-01", "hasta": "2026-03-01"}).status_code == 422
    assert a.get(f"{BASE}/taller/facturas-calculo").status_code == 422  # faltan fechas


def test_pago_que_liquida_varias_facturas_sale_uno_por_documento(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    cliente = Cliente(despacho_id="uid-a", clave="t", nombre="T", rfc=RFC_CLIENTE)
    db_sesion.add(cliente)
    db_sesion.flush()
    from app.boveda_cfdi import servicio
    from app.integraciones.almacenamiento import AlmacenamientoMemoria

    almacen = AlmacenamientoMemoria()
    import io
    lote = [
        ("a.xml", io.BytesIO(_ppd(cfdi(uuid_n(10), fecha="2026-03-01T10:00:00")))),
        ("b.xml", io.BytesIO(_ppd(cfdi(uuid_n(11), fecha="2026-03-02T10:00:00")))),
        ("p.xml", io.BytesIO(pago(uuid_n(12), [uuid_n(10), uuid_n(11)], version_pagos="1.0",
                                  version="3.3"))),
    ]
    assert servicio.importar(db_sesion, cliente, lote, almacen).importados == 3
    r = calculo.facturas_para_calculo(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31))
    pagos = [f for f in r.facturas if f.tipo == "P"]
    assert [(f.uuid, f.uuid_relacionado, f.monto_pago) for f in pagos] == [
        (f"{uuid_n(12)}#1", uuid_n(10), 1160.0),
        (f"{uuid_n(12)}#2", uuid_n(11), 1160.0),
    ]
    assert r.relacionados == []


def test_rango_del_periodo():
    assert calculo.rango_del_periodo(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert calculo.rango_del_periodo(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))
    assert calculo.rango_del_periodo(2026, bimestre=6) == (date(2026, 11, 1), date(2026, 12, 31))
    assert calculo.rango_del_periodo(2026) == (date(2026, 1, 1), date(2026, 12, 31))


# ── cálculos por cliente: el mes sale sin subir un archivo ──


def test_pre_declaracion_del_mes_sale_de_la_boveda_sin_subir_archivo(boveda_cargada):
    a = boveda_cargada
    r = a.post(f"{CALC}/taller/calculos/pre-declaracion",
               json={"periodo_year": 2026, "periodo_month": 3, "incluir_explicacion": False})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    d = cuerpo["desglose"]
    # Ingresos: la venta PUE (1000) + el pago del PPD de febrero (1000). La cancelada, la
    # nómina y el PPD de marzo sin pago no suman.
    assert d["total_ingresos_facturados"] == 2000.0
    assert d["cantidad_facturas_ingreso"] == 2
    assert d["iva_trasladado_cobrado"] == 320.0
    # Gasto recibido con sus retenciones.
    assert d["cantidad_facturas_egreso"] == 1
    assert cuerpo["periodo"] == "Marzo 2026"
    assert cuerpo["boveda"]["cancelados_excluidos"] == 1
    assert cuerpo["boveda"]["nomina_excluidos"] == 1

    # Es el MISMO cálculo que el endpoint con facturas en el body.
    fact = _marzo(a).json()
    original = a.post("/api/v1/pre-declaracion", json={
        "contribuyente": {"rfc": RFC_CLIENTE, "regimen": "612"},
        "facturas": fact["facturas"] + fact["relacionados"],
        "periodo_year": 2026, "periodo_month": 3, "incluir_explicacion": False,
    }).json()
    assert original["desglose"] == d


def test_los_demas_calculos_por_cliente(boveda_cargada):
    a = boveda_cargada
    base = f"{CALC}/taller/calculos"
    sin = {"incluir_explicacion": False}

    anual = a.post(f"{base}/pre-declaracion-anual", json={"periodo_year": 2026, **sin})
    assert anual.status_code == 200, anual.text
    assert anual.json()["tipo_declaracion"] == "anual"
    # Abril ya cuenta en el ejercicio.
    assert anual.json()["desglose"]["cantidad_facturas_ingreso"] == 3

    d = a.post(f"{base}/diot", json={"periodo_year": 2026, "periodo_month": 3, **sin}).json()
    assert [p["rfc"] for p in d["proveedores"]] == [RFC_PROVEEDOR]

    ret = a.post(f"{base}/retenciones-terceros",
                 json={"periodo_year": 2026, "periodo_month": 3, **sin}).json()
    assert (ret["total_isr_retenido"], ret["total_iva_retenido"]) == (100.0, 106.67)

    mp = a.post(f"{base}/multi-periodo",
                json={"periodo_year": 2026, "periodos": [2, 3, 4], **sin})
    assert mp.status_code == 200, mp.text
    assert len(mp.json()["resultados"]) == 3

    ec = a.post(f"{base}/estado-cuenta", json={"periodo_year": 2026, **sin})
    assert ec.status_code == 200, ec.text
    assert ec.json()["ingresos_acumulados"] == 3000.0


def test_periodo_vacio_y_ficha_incompleta(boveda_cargada, sesionador):
    a = boveda_cargada
    r = a.post(f"{CALC}/taller/calculos/pre-declaracion",
               json={"periodo_year": 2026, "periodo_month": 1})
    assert r.status_code == 400 and "Bóveda" in r.json()["error"]
    assert a.post(f"{CALC}/taller/calculos/pre-declaracion",
                  json={"periodo_year": 2026}).status_code == 422

    db = sesionador()
    c = db.scalar(select(Cliente).where(Cliente.clave == "taller"))
    c.datos = {"rfc": RFC_CLIENTE}
    db.commit()
    db.close()
    r = a.post(f"{CALC}/taller/calculos/pre-declaracion",
               json={"periodo_year": 2026, "periodo_month": 3})
    assert r.status_code == 422 and r.json()["error"] == "Captura el régimen de este cliente."


def test_persona_moral_se_rechaza_como_en_el_endpoint_original(boveda_cargada, sesionador):
    db = sesionador()
    c = db.scalar(select(Cliente).where(Cliente.clave == "taller"))
    c.datos = {"rfc": RFC_CLIENTE, "regimen": "601"}
    db.commit()
    db.close()
    r = boveda_cargada.post(f"{CALC}/taller/calculos/pre-declaracion",
                            json={"periodo_year": 2026, "periodo_month": 3})
    assert r.status_code == 400


# ── multi-tenant ──


def test_multi_tenant_b_no_lee_ni_calcula_con_la_boveda_de_a(boveda_cargada, api):
    b = api("uid-b")
    assert b.get(f"{BASE}/taller/facturas-calculo",
                 params={"desde": "2026-03-01", "hasta": "2026-03-31"}).status_code == 404
    assert b.post(f"{CALC}/taller/calculos/pre-declaracion",
                  json={"periodo_year": 2026, "periodo_month": 3}).status_code == 404
    # Su cliente con el MISMO RFC tiene la bóveda vacía: nada de A se cuela.
    propio = b.get(f"{BASE}/otro/facturas-calculo",
                   params={"desde": "2026-03-01", "hasta": "2026-03-31"}).json()
    assert propio["facturas"] == [] and propio["resumen"]["comprobantes"] == 0
    assert b.post(f"{CALC}/otro/calculos/pre-declaracion",
                  json={"periodo_year": 2026, "periodo_month": 3}).status_code == 400
    # Y A no ve el de B.
    assert boveda_cargada.get(f"{BASE}/otro/facturas-calculo",
                              params={"desde": "2026-03-01",
                                      "hasta": "2026-03-31"}).status_code == 404
