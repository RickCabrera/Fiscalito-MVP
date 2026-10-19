"""
XSD y XSLT oficiales de contabilidad electrónica 1.3 (Anexo 24 RMF), versionados offline.

FUENTE
------
`app/contabilidad/anexo24/sat/esquemas/` es copia byte por byte de lo que publica el SAT en
`http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/...` (y `.../esquemas/utilerias.xslt`),
tomada del paquete PyPI `satcfdi` 26.10.0 (MIT), carpeta
`satcfdi/transform/schemas/www.sat.gob.mx/esquemas/`, el 2026-10-19 (el sitio del SAT no es
alcanzable desde este entorno). La misma copia está en `tests/xsd/contabilidad/` con sus
SHA-256 en el README; `tests/plan_p/test_anexo24.py` exige que las dos sean idénticas.

Se respeta la estructura de carpetas del SAT porque cada XSD importa
`../CatalogosParaEsqContE/CatalogosParaEsqContE.xsd` y cada XSLT incluye
`../../../utilerias.xslt` por ruta relativa: así resuelven sin red y sin editar los archivos.

Los XSLT se llaman `*_1_2.xslt` pero dentro apuntan al namespace 1_3: así los publica el SAT
para la versión 1.3 (la cadena original no cambió de la 1.2 a la 1.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).parent / "sat" / "esquemas" / "ContabilidadE" / "1_3"
NS_BASE = "http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/"


@dataclass(frozen=True)
class TipoDocumento:
    clave: str  # catalogo | balanza | polizas | auxiliar_cuentas | auxiliar_folios
    raiz: str  # elemento raíz
    carpeta: str
    xsd: str
    xslt: str
    prefijo: str
    sufijo: str  # del nombre de archivo (Anexo 24: CT, B<N|C>, PL, XC, XF)
    nombre: str

    @property
    def ns(self) -> str:
        return NS_BASE + self.carpeta

    @property
    def schema_location(self) -> str:
        return f"{self.ns} {self.ns}/{self.xsd}"


TIPOS: dict[str, TipoDocumento] = {t.clave: t for t in (
    TipoDocumento("catalogo", "Catalogo", "CatalogoCuentas", "CatalogoCuentas_1_3.xsd",
                  "CatalogoCuentas_1_2.xslt", "catalogocuentas", "CT", "Catálogo de cuentas"),
    TipoDocumento("balanza", "Balanza", "BalanzaComprobacion", "BalanzaComprobacion_1_3.xsd",
                  "BalanzaComprobacion_1_2.xslt", "BCE", "B", "Balanza de comprobación"),
    TipoDocumento("polizas", "Polizas", "PolizasPeriodo", "PolizasPeriodo_1_3.xsd",
                  "PolizasPeriodo_1_2.xslt", "PLZ", "PL", "Pólizas del periodo"),
    TipoDocumento("auxiliar_cuentas", "AuxiliarCtas", "AuxiliarCtas", "AuxiliarCtas_1_3.xsd",
                  "AuxiliarCtas_1_2.xslt", "AuxiliarCtas", "XC", "Auxiliar de cuentas"),
    TipoDocumento("auxiliar_folios", "RepAuxFol", "AuxiliarFolios", "AuxiliarFolios_1_3.xsd",
                  "AuxiliarFolios_1_2.xslt", "RepAux", "XF", "Auxiliar de folios"),
)}


@lru_cache(maxsize=8)
def esquema(clave: str) -> etree.XMLSchema:
    t = TIPOS[clave]
    return etree.XMLSchema(etree.parse(str(RAIZ / t.carpeta / t.xsd)))


@lru_cache(maxsize=8)
def transformacion(clave: str) -> etree.XSLT:
    t = TIPOS[clave]
    return etree.XSLT(etree.parse(str(RAIZ / t.carpeta / t.xslt)))


def validar(clave: str, doc: etree._Element) -> list[str]:
    """Errores del XSD (vacío = válido), legibles: línea + mensaje."""
    s = esquema(clave)
    if s.validate(doc):
        return []
    return [f"línea {e.line}: {e.message}" for e in s.error_log][:200]


def cadena_original(clave: str, doc: etree._Element) -> str:
    """Cadena original con el XSLT oficial del SAT (`||...||`)."""
    return str(transformacion(clave)(doc))
