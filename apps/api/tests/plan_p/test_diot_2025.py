"""
P3-05: DIOT con el layout de carga masiva 2025 (54 campos) y cortes por tasa reales.

El caso de marzo de 2026 mezcla 16 %, 0 %, exento, no objeto, 8 % (región sur por
configuración), una nota de crédito, honorarios con IVA retenido y una factura PPD de febrero
pagada en marzo con complemento. El `.txt` se valida contra el instructivo (campo por campo).
"""

from __future__ import annotations

import pytest

from app.diot import layout
from app.modelos.nucleo import Cliente
from app.tenancy import asegurar_usuario
from tests.plan_p.cfdi_p3 import cfdi_tasas
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, pago, uuid_n

RFC_PF = "PERJ800101AB1"
RFC_FRONTERA = "FRO010101CC3"
RFC_PPD = "PPD010101DD4"


def _vacios(n: int) -> list[str]:
    return [""] * n


def test_el_layout_son_54_campos_en_el_orden_del_instructivo():
    assert len(layout.CAMPOS) == 54
    assert layout.CAMPOS[0].clave == "tipo_tercero" and layout.CAMPOS[53].clave == \
        "efectos_fiscales"
    assert layout.POR_CLAVE["valor_tasa_16"].numero == 12
    assert layout.POR_CLAVE["acreditable_gravadas_tasa_16"].numero == 22
    assert layout.POR_CLAVE["no_acreditable_no_objeto_importacion_intangibles"].numero == 47
    assert layout.POR_CLAVE["iva_retenido"].numero == 48


def test_validador_rechaza_lo_que_el_sat_rechaza():
    viejo = "|".join(["04", "85", RFC_PROVEEDOR] + _vacios(22))
    assert layout.validar_linea(viejo)[0].endswith("se esperan 54 campos y hay 25.")
    base = {"tipo_tercero": "04", "tipo_operacion": "85", "rfc": RFC_PROVEEDOR,
            "efectos_fiscales": "01"}
    assert layout.validar_linea(layout.linea(base)) == []
    errores = layout.validar_linea(layout.linea({**base, "tipo_operacion": "07"}))
    assert any("campo 2" in e for e in errores)
    errores = layout.validar_linea(layout.linea({**base, "valor_tasa_16": "100.50"}))
    assert any("campo 12" in e and "entero" in e for e in errores)
    errores = layout.validar_linea(layout.linea({**base, "valor_tasa_16": 10,
                                                 "devoluciones_tasa_16": 20}))
    assert any("campo 13" in e and "campo 12" in e for e in errores)
    errores = layout.validar_linea(layout.linea({**base, "tipo_tercero": "05",
                                                 "tipo_operacion": "07"}))
    assert any("campo 4" in e for e in errores) and any("campo 6" in e for e in errores)
    errores = layout.validar_linea(layout.linea({**base, "efectos_fiscales": ""}))
    assert any("campo 54" in e for e in errores)
    assert layout.validar_archivo("x".encode("latin-1") + b"\xe9") == \
        ["El archivo no está en UTF-8."]


@pytest.fixture
def con_cliente(sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([
        Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE,
                datos={"regimen": "601"}),
        Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE),
    ])
    db.commit()
    db.close()


def _subir(a, archivos):
    r = a.post("/api/v1/boveda/clientes/taller/cfdi",
               files=[("archivos", (f"{i}.xml", x, "text/xml")) for i, x in enumerate(archivos)])
    assert r.status_code == 200 and not r.json()["rechazados"], r.text


CASO = [
    # A: servicios a 16 %, 0 %, exento y no objeto; nota de crédito de 1,000 a 16 %.
    cfdi_tasas(uuid_n(1), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
               fecha="2026-03-05T10:00:00",
               conceptos=[("10000.00", "0.160000"), ("2000.00", "0.000000"),
                          ("1500.00", "Exento"), ("300.00", "")]),
    cfdi_tasas(uuid_n(2), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
               fecha="2026-03-20T10:00:00", conceptos=[("1000.00", "0.160000")], tipo="E"),
    # B: honorarios de persona física con ISR y 2/3 de IVA retenidos.
    cfdi_tasas(uuid_n(3), emisor=RFC_PF, receptor=RFC_CLIENTE, fecha="2026-03-12T10:00:00",
               conceptos=[("5000.00", "0.160000")], isr_ret="500.00", iva_ret="533.33",
               regimen_emisor="612"),
    # C: bienes a 8 % (región fronteriza); el despacho lo marca región SUR.
    cfdi_tasas(uuid_n(4), emisor=RFC_FRONTERA, receptor=RFC_CLIENTE,
               fecha="2026-03-15T10:00:00", conceptos=[("3000.00", "0.080000")],
               clave_prod="43211503"),
    # D: PPD de febrero pagado en marzo con complemento (cuenta en marzo, no en febrero).
    cfdi_tasas(uuid_n(5), emisor=RFC_PPD, receptor=RFC_CLIENTE, fecha="2026-02-20T10:00:00",
               conceptos=[("1000.00", "0.160000")], metodo="PPD"),
    pago(uuid_n(6), [uuid_n(5)], emisor=RFC_PPD, receptor=RFC_CLIENTE),
]


def _linea(**campos: object) -> str:
    return layout.linea({k: v for k, v in campos.items()})


def test_diot_del_caso_contra_el_layout_oficial(api, con_cliente):
    a = api("uid-a")
    _subir(a, CASO)
    r = a.put(f"/api/v1/clientes/taller/diot/proveedores/{RFC_FRONTERA}",
              json={"region_8": "sur"})
    assert r.status_code == 200, r.text

    r = a.get("/api/v1/clientes/taller/diot/2026/3")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["errores_layout"] == []
    por_rfc = {p["rfc"]: p for p in datos["proveedores"]}
    assert set(por_rfc) == {RFC_PROVEEDOR, RFC_PF, RFC_FRONTERA, RFC_PPD}
    assert por_rfc[RFC_PF]["tipo_operacion"] == "03"
    assert por_rfc[RFC_FRONTERA]["tipo_operacion"] == "02"
    assert por_rfc[RFC_FRONTERA]["clasificacion_capturada"] is True

    txt = a.get("/api/v1/clientes/taller/diot/2026/3/txt")
    assert txt.status_code == 200, txt.text
    assert layout.validar_archivo(txt.content) == []
    renglones = txt.content.decode("utf-8").splitlines()
    assert renglones == [
        _linea(tipo_tercero="04", tipo_operacion="02", rfc=RFC_FRONTERA, valor_region_sur=3000,
               acreditable_gravadas_region_sur=240, efectos_fiscales="01"),
        _linea(tipo_tercero="04", tipo_operacion="03", rfc=RFC_PF, valor_tasa_16=5000,
               acreditable_gravadas_tasa_16=800, iva_retenido=533, efectos_fiscales="01"),
        _linea(tipo_tercero="04", tipo_operacion="85", rfc=RFC_PPD, valor_tasa_16=1000,
               acreditable_gravadas_tasa_16=160, efectos_fiscales="01"),
        _linea(tipo_tercero="04", tipo_operacion="85", rfc=RFC_PROVEEDOR, valor_tasa_16=10000,
               devoluciones_tasa_16=1000, acreditable_gravadas_tasa_16=1440, exentos=1500,
               tasa_0=2000, no_objeto_nacional=300, efectos_fiscales="01"),
    ]
    # Campo por campo, el renglón del proveedor A según el instructivo:
    a_campos = renglones[3].split("|")
    assert len(a_campos) == 54
    assert (a_campos[0], a_campos[1], a_campos[2]) == ("04", "85", RFC_PROVEEDOR)
    assert (a_campos[11], a_campos[12], a_campos[21]) == ("10000", "1000", "1440")
    assert (a_campos[49], a_campos[50], a_campos[51], a_campos[53]) == \
        ("1500", "2000", "300", "01")

    # Febrero no lleva la factura PPD: todavía no estaba pagada.
    feb = a.get("/api/v1/clientes/taller/diot/2026/2").json()
    assert feb["proveedores"] == []


def test_iva_no_acreditable_y_proveedor_extranjero_configurables(api, con_cliente):
    a = api("uid-a")
    _subir(a, [
        cfdi_tasas(uuid_n(1), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                   fecha="2026-03-05T10:00:00", conceptos=[("1000.00", "0.160000")]),
        # uso "sin efectos fiscales": su IVA no se acredita (no cumple requisitos)
        cfdi_tasas(uuid_n(2), emisor=RFC_PF, receptor=RFC_CLIENTE, fecha="2026-03-06T10:00:00",
                   conceptos=[("500.00", "0.160000")], uso="S01"),
    ])
    a.put(f"/api/v1/clientes/taller/diot/proveedores/{RFC_PROVEEDOR}",
          json={"iva_no_acreditable": "exentas", "tipo_operacion": "06"})
    datos = a.get("/api/v1/clientes/taller/diot/2026/3").json()
    por_rfc = {p["rfc"]: p for p in datos["proveedores"]}
    assert por_rfc[RFC_PROVEEDOR]["campos"] == {"no_acreditable_exentas_tasa_16": 160,
                                                "valor_tasa_16": 1000}
    assert por_rfc[RFC_PROVEEDOR]["tipo_operacion"] == "06"
    assert por_rfc[RFC_PF]["campos"]["no_acreditable_requisitos_tasa_16"] == 80

    # Extranjero sin sus datos: el archivo NO se entrega (422 con el campo que falta).
    a.put(f"/api/v1/clientes/taller/diot/proveedores/{RFC_PROVEEDOR}",
          json={"tipo_tercero": "05", "tipo_operacion": "07"})
    r = a.get("/api/v1/clientes/taller/diot/2026/3/txt")
    assert r.status_code == 422 and "campo 4" in r.json()["error"]
    a.put(f"/api/v1/clientes/taller/diot/proveedores/{RFC_PROVEEDOR}", json={
        "tipo_tercero": "05", "tipo_operacion": "07", "id_fiscal": "TAX-123",
        "nombre_extranjero": "FOREIGN SUPPLIER INC", "pais": "US",
        "importacion": "intangibles"})
    r = a.get("/api/v1/clientes/taller/diot/2026/3/txt")
    assert r.status_code == 200, r.text
    renglon = [x for x in r.content.decode().splitlines() if "TAX-123" in x][0].split("|")
    assert renglon[:7] == ["05", "07", RFC_PROVEEDOR, "TAX-123", "FOREIGN SUPPLIER INC", "US",
                           ""]
    assert renglon[15] == "1000" and renglon[25] == "160"


def test_diot_multitenant_y_endpoint_viejo_compatible(api, con_cliente):
    a = api("uid-a")
    _subir(a, CASO[:1])
    assert api("uid-b").get("/api/v1/clientes/taller/diot/2026/3").status_code == 404
    assert api("uid-b").put(f"/api/v1/clientes/taller/diot/proveedores/{RFC_PROVEEDOR}",
                            json={}).status_code == 404
    viejo = a.post("/api/v1/clientes/taller/calculos/diot",
                   json={"periodo_year": 2026, "periodo_month": 3,
                         "incluir_explicacion": False})
    assert viejo.status_code == 200 and viejo.json()["total_proveedores"] == 1
