"""P0-03: parser de CFDI de la bóveda contra los XML que ya hay en el repo y sintéticos."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.boveda_cfdi.parser import CfdiInvalido, parsear_cfdi
from tests.plan_p.cfdi_sintetico import cfdi, pago, uuid_n

RAIZ = Path(__file__).resolve().parents[4]
DEMO = RAIZ / "apps" / "store" / "public" / "demo-xmls" / "2026" / "01"
NOMINA = Path(__file__).resolve().parents[1] / "fixtures" / "nomina"


def _rfc_del_xml(nombre: str, nodo: str) -> str:
    """RFC de `nodo` leído con una búsqueda de texto independiente del parser."""
    import re

    texto = (DEMO / nombre).read_text(encoding="utf-8")
    return re.search(rf"<cfdi:{nodo}[^>]*\sRfc=\"([^\"]+)\"", texto).group(1)


def test_demo_ingreso_40():
    c = parsear_cfdi((DEMO / "ingreso-001.xml").read_bytes())
    assert (c.version, c.tipo) == ("4.0", "I")
    assert c.uuid == "11111111-1111-1111-1111-111111110001"
    # El RFC del emisor se lee del propio XML: no se escribe un RFC real en el repo.
    assert c.rfc_emisor == _rfc_del_xml("ingreso-001.xml", "Emisor")
    assert c.rfc_receptor == "XAXX010101000"
    assert c.total == Decimal("17400.00") and c.subtotal == Decimal("15000.00")
    assert c.iva_trasladado == Decimal("2400.00")
    assert c.fecha_timbrado is not None
    assert c.datos["conceptos"][0]["ClaveProdServ"] == "80101500"


def test_demo_egreso_40():
    c = parsear_cfdi((DEMO / "egreso-001.xml").read_bytes())
    assert c.tipo == "I" and c.rfc_receptor == _rfc_del_xml("egreso-001.xml", "Receptor")
    assert c.iva_trasladado == Decimal("512.00") and c.total == Decimal("3712.00")
    assert c.uso_cfdi == "G03" and c.forma_pago == "04"


def test_los_70_cfdi_de_nomina_de_las_fixtures():
    archivos = sorted(NOMINA.glob("semana-*/*.xml"))
    assert len(archivos) == 70
    uuids = set()
    for ruta in archivos:
        c = parsear_cfdi(ruta.read_bytes())
        assert c.tipo == "N", ruta
        n = c.datos["nomina"]
        assert n["version"] == "1.2"
        # Totales de nómina = los del comprobante: percepciones + otros pagos = subtotal.
        assert Decimal(n["TotalPercepciones"]) + Decimal(n.get("TotalOtrosPagos", "0")) \
            == c.subtotal, ruta
        assert Decimal(n.get("TotalDeducciones", "0")) == c.descuento, ruta
        # El ISR retenido de la nómina es la deducción 002.
        assert c.isr_retenido == Decimal(n["isr_retenido"]).quantize(Decimal("0.01"))
        uuids.add(c.uuid)
    assert len(uuids) == 70


def test_una_nomina_concreta():
    c = parsear_cfdi((NOMINA / "semana-01" / "E-01.xml").read_bytes())
    assert c.uuid == "B6B08751-4E2D-419D-A5D7-D7975E9EE713"
    assert c.isr_retenido == Decimal("34.68")
    assert c.datos["nomina"]["subsidio_causado"] == "123.47"
    assert c.datos["nomina"]["receptor"]["NumEmpleado"] == "E-01"


def test_cfdi_33_con_retenciones():
    xml = cfdi(uuid_n(1), version="3.3").replace(
        b"</cfdi:Traslados></cfdi:Impuestos>",
        b'</cfdi:Traslados><cfdi:Retenciones><cfdi:Retencion Impuesto="001" Importe="100.00"/>'
        b'<cfdi:Retencion Impuesto="002" Importe="106.67"/></cfdi:Retenciones>'
        b"</cfdi:Impuestos>",
    )
    c = parsear_cfdi(xml)
    assert c.version == "3.3"
    assert c.isr_retenido == Decimal("100.00") and c.iva_retenido == Decimal("106.67")


@pytest.mark.parametrize("tipo", ["I", "E", "T"])
def test_tipos(tipo):
    assert parsear_cfdi(cfdi(uuid_n(2), tipo=tipo)).tipo == tipo


def test_pagos_20():
    rel = [uuid_n(10), uuid_n(11)]
    c = parsear_cfdi(pago(uuid_n(3), rel))
    assert c.tipo == "P"
    p = c.datos["pagos"]
    assert p["version"] == "2.0" and p["uuids_relacionados"] == sorted(rel)
    assert p["pagos"][0]["documentos"][0]["ImpPagado"] == "1160.00"
    assert p["totales"]["MontoTotalPagos"] == "1160.00"


def test_pagos_10_con_cfdi_33():
    c = parsear_cfdi(pago(uuid_n(4), [uuid_n(12).lower()], version_pagos="1.0", version="3.3"))
    assert c.datos["pagos"]["version"] == "1.0"
    assert c.datos["pagos"]["uuids_relacionados"] == [uuid_n(12).upper()]


def test_uuid_en_mayusculas():
    assert parsear_cfdi(cfdi(uuid_n(5).lower())).uuid == uuid_n(5).upper()


@pytest.mark.parametrize("contenido,razon", [
    (b"", "vacío"),
    (b"no soy xml", "XML válido"),
    (b"<?xml version='1.0'?><Factura/>", "no es un CFDI"),
    (cfdi(uuid_n(6)).replace(b'Version="4.0"', b'Version="3.2"'), "no soportada"),
    (cfdi(uuid_n(6), sin_timbre=True), "timbrado"),
    (cfdi(uuid_n(6)).replace(b'TipoDeComprobante="I"', b'TipoDeComprobante="X"'),
     "TipoDeComprobante"),
])
def test_rechazos_con_razon(contenido, razon):
    with pytest.raises(CfdiInvalido, match=razon):
        parsear_cfdi(contenido)


def test_rechaza_dtd_y_entidades():
    bomba = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
             b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><l>&b;</l>')
    with pytest.raises(CfdiInvalido):
        parsear_cfdi(bomba)
    xxe = (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
           b'<x>&e;</x>')
    with pytest.raises(CfdiInvalido):
        parsear_cfdi(xxe)
