"""
XSD y XSLT oficiales del CFDI de Retenciones e información de pagos 2.0, offline.

FUENTE
------
`app/retenciones_cfdi/sat/www.sat.gob.mx/` replica las rutas que publica el SAT:

- `esquemas/retencionpago/2/retencionpagov2.xsd` y `retenciones.xslt` (cadena original),
- `esquemas/retencionpago/1/catalogos/catRetenciones.xsd` (c_CveRetenc, c_TipoPagoRet...),
- los XSLT de los complementos que `retenciones.xslt` incluye por ruta relativa,
- `sitio_internet/cfd/catalogos/catCFDI.xsd`, `tipoDatos/tdCFDI/tdCFDI.xsd`,
  `cfd/2/cadenaoriginal_2_0/utilerias.xslt` y el `TimbreFiscalDigitalv11.xsd` con su XSLT.

Tomados del paquete PyPI `satcfdi` 26.10.1 (MIT), carpeta
`satcfdi/transform/schemas/www.sat.gob.mx/`, el 2026-10-19, porque www.sat.gob.mx no resuelve
desde este entorno. OJO: `satcfdi` guarda los archivos **minificados** (sin espacios entre
nodos), así que NO son byte-idénticos a los del SAT aunque el contenido sí lo sea. Los hashes
están en `tests/xsd/retenciones/README.md` y `tests/plan_p/test_retenciones_cfdi.py` exige que
la copia de `tests/xsd/retenciones/` y ésta sean idénticas.

Se respeta la estructura de carpetas del SAT para que los `import`/`include` relativos
resuelvan sin red y sin editar los archivos.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).parent / "sat" / "www.sat.gob.mx"
NS = "http://www.sat.gob.mx/esquemas/retencionpago/2"
XSD_URL = "http://www.sat.gob.mx/esquemas/retencionpago/2/retencionpagov2.xsd"
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"

_XSD = RAIZ / "esquemas/retencionpago/2/retencionpagov2.xsd"
_XSLT = RAIZ / "esquemas/retencionpago/2/retenciones.xslt"
_XSD_TFD = RAIZ / "sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"
_XSLT_TFD = RAIZ / "sitio_internet/cfd/TimbreFiscalDigital/cadenaoriginal_TFD_1_1.xslt"


@lru_cache(maxsize=1)
def esquema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(_XSD)))


@lru_cache(maxsize=1)
def esquema_tfd() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(_XSD_TFD)))


@lru_cache(maxsize=1)
def _transformacion() -> etree.XSLT:
    return etree.XSLT(etree.parse(str(_XSLT)))


@lru_cache(maxsize=1)
def _transformacion_tfd() -> etree.XSLT:
    return etree.XSLT(etree.parse(str(_XSLT_TFD)))


def _errores(s: etree.XMLSchema, doc: etree._Element) -> list[str]:
    if s.validate(doc):
        return []
    return [f"línea {e.line}: {e.message}" for e in s.error_log][:200]


def validar(doc: etree._Element) -> list[str]:
    """
    Errores del XSD de retenciones 2.0 (vacío = válido).

    El `Complemento` es un `xs:any` estricto: si trae el TimbreFiscalDigital, éste se valida
    aparte contra su propio XSD y se quita de la copia que va al de retenciones.
    """
    copia = etree.fromstring(etree.tostring(doc))
    errores: list[str] = []
    complemento = copia.find(f"{{{NS}}}Complemento")
    if complemento is not None:
        for tfd in complemento.findall(f"{{{NS_TFD}}}TimbreFiscalDigital"):
            errores += [f"TFD {e}" for e in _errores(esquema_tfd(), tfd)]
            complemento.remove(tfd)
        if len(complemento) == 0:
            copia.remove(complemento)
    return errores + _errores(esquema(), copia)


def cadena_original(doc: etree._Element) -> str:
    """Cadena original con el XSLT oficial del SAT (`||...||`)."""
    return str(_transformacion()(doc))


def cadena_original_tfd(tfd: etree._Element) -> str:
    """Cadena original del complemento de certificación (TFD 1.1), para la representación."""
    return str(_transformacion_tfd()(etree.ElementTree(tfd)))
