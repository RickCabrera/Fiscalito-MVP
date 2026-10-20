"""
XSD y XSLT oficiales del CFDI 4.0 con complemento de nómina 1.2, sin red (P4-11).

FUENTE
------
- `xsd/`: copia BYTE-IDÉNTICA de `tests/xsd/` (cfdv40, nomina12, catCFDI, catNomina, tdCFDI,
  TimbreFiscalDigitalv11, descargados del SAT el 2026-09-01 con sus SHA-256 en
  `tests/xsd/README.md`) más el envoltorio que los compila juntos.
  `tests/nomina/test_p4_11_cfdi.py` exige que ambas copias sean idénticas.
- `sat/www.sat.gob.mx/sitio_internet/cfd/`: el XSLT de la cadena original del CFDI 4.0
  (`4/cadenaoriginal_4_0/cadenaoriginal_4_0.xslt`) con TODOS los complementos que incluye por
  ruta relativa (entre ellos `nomina/nomina12.xslt`), `2/cadenaoriginal_2_0/utilerias.xslt` y la
  cadena del TFD 1.1. Tomados del paquete PyPI `satcfdi` 26.10.1 (MIT), carpeta
  `satcfdi/transform/schemas/www.sat.gob.mx/`, el 2026-10-19, porque www.sat.gob.mx no
  resuelve desde este entorno — mismo origen y misma salvedad que `retenciones_cfdi/esquemas.py`
  (satcfdi los guarda minificados: mismo contenido, no los mismos bytes que publica el SAT).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

AQUI = Path(__file__).parent
XSD = AQUI / "xsd"
CFD = AQUI / "sat" / "www.sat.gob.mx" / "sitio_internet" / "cfd"
NS_CFDI = "http://www.sat.gob.mx/cfd/4"
NS_NOMINA = "http://www.sat.gob.mx/nomina12"
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"
_PREFIJO_SAT = "http://www.sat.gob.mx/"


class _ResolverSat(etree.Resolver):
    """Las URLs del SAT de los `schemaLocation` → archivos locales de `xsd/`."""

    def resolve(self, url, public_id, context):  # noqa: D102
        if url and url.startswith(_PREFIJO_SAT):
            local = XSD / url.rsplit("/", 1)[-1]
            if local.exists():
                return self.resolve_filename(str(local), context)
        return None


@lru_cache(maxsize=1)
def esquema() -> etree.XMLSchema:
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_ResolverSat())
    return etree.XMLSchema(etree.parse(str(XSD / "envoltorio_validacion.xsd"), parser))


@lru_cache(maxsize=1)
def _xslt_cadena() -> etree.XSLT:
    return etree.XSLT(etree.parse(
        str(CFD / "4" / "cadenaoriginal_4_0" / "cadenaoriginal_4_0.xslt")))


@lru_cache(maxsize=1)
def _xslt_tfd() -> etree.XSLT:
    return etree.XSLT(etree.parse(
        str(CFD / "TimbreFiscalDigital" / "cadenaoriginal_TFD_1_1.xslt")))


def validar(doc: etree._Element) -> list[str]:
    """Errores contra CFDI 4.0 + nómina 1.2 + TFD 1.1 (vacío = válido)."""
    s = esquema()
    if s.validate(doc):
        return []
    return [f"línea {e.line}: {e.message}" for e in s.error_log][:50]


def cadena_original(doc: etree._Element) -> str:
    """Cadena original del comprobante con el XSLT oficial (`||4.0|...||`)."""
    return str(_xslt_cadena()(doc))


def cadena_original_tfd(tfd: etree._Element) -> str:
    return str(_xslt_tfd()(etree.ElementTree(tfd)))


def parsear(xml: bytes | str) -> etree._Element:
    datos = xml.encode("utf-8") if isinstance(xml, str) else xml
    return etree.fromstring(datos, etree.XMLParser(resolve_entities=False, no_network=True))
