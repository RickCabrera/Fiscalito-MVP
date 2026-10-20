"""
XSD del CFDI 4.0 de ingreso, egreso y pago (complemento de recepción de pagos 2.0), offline.

FUENTE
------
- `cfdv40.xsd`, `catCFDI.xsd`, `tdCFDI.xsd` y `TimbreFiscalDigitalv11.xsd`: los MISMOS de
  `app/nomina_cfdi/xsd/` (byte-idénticos a `tests/xsd/`, descargados del SAT el 2026-09-01,
  hashes en `tests/xsd/README.md`). No se copian otra vez: se resuelven desde allá.
- `xsd/Pagos20.xsd` (http://www.sat.gob.mx/sitio_internet/cfd/Pagos/Pagos20.xsd) y
  `xsd/catPagos.xsd` (…/cfd/catalogos/Pagos/catPagos.xsd): tomados del paquete PyPI `satcfdi`
  26.10.1 (MIT), carpeta `satcfdi/transform/schemas/www.sat.gob.mx/sitio_internet/cfd/`, el
  2026-10-19, porque www.sat.gob.mx no resuelve desde este entorno — mismo origen y misma
  salvedad que `retenciones_cfdi/esquemas.py` (satcfdi los guarda minificados: mismo contenido,
  no los mismos bytes que publica el SAT). SHA-256 en `HASHES` y verificados por
  `tests/plan_p/test_facturacion.py`.
- La cadena original: el XSLT oficial del CFDI 4.0 de `app/nomina_cfdi/sat/` (que incluye
  `Pagos/Pagos20.xslt`), por `app.nomina_cfdi.esquemas.cadena_original`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

from app.nomina_cfdi import esquemas as base

AQUI = Path(__file__).parent / "xsd"
NS_CFDI = base.NS_CFDI
NS_TFD = base.NS_TFD
NS_PAGOS = "http://www.sat.gob.mx/Pagos20"
XSD_PAGOS = "http://www.sat.gob.mx/sitio_internet/cfd/Pagos/Pagos20.xsd"
HASHES = {
    "Pagos20.xsd": "c95f8a4653f29aebbb862de6a4280f96d630c6b429cd515911be1b2a88a47b93",
    "catPagos.xsd": "293b0ce1ba6d70419bc056cd344ae350052b97c262af0a7aa4a04ae4d73ecbc3",
}
_DIRECTORIOS = (AQUI, base.XSD)


class _Resolver(etree.Resolver):
    """Cualquier `schemaLocation` (URL del SAT o ruta relativa) → archivo local por nombre."""

    def resolve(self, url, public_id, context):  # noqa: D102
        nombre = (url or "").rsplit("/", 1)[-1]
        if nombre.endswith(".xsd"):
            for d in _DIRECTORIOS:
                if (d / nombre).exists():
                    return self.resolve_filename(str(d / nombre), context)
        return None


@lru_cache(maxsize=1)
def esquema() -> etree.XMLSchema:
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_Resolver())
    return etree.XMLSchema(etree.parse(str(AQUI / "envoltorio_facturacion.xsd"), parser))


def validar(doc: etree._Element) -> list[str]:
    """Errores contra CFDI 4.0 + Pagos 2.0 + TFD 1.1 (vacío = válido)."""
    s = esquema()
    if s.validate(doc):
        return []
    return [f"línea {e.line}: {e.message}" for e in s.error_log][:50]


cadena_original = base.cadena_original
cadena_original_tfd = base.cadena_original_tfd
parsear = base.parsear
