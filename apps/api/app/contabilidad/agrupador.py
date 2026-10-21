"""
Código agrupador de cuentas del SAT (Anexo 24 de la RMF, contabilidad electrónica). P2-01.

FUENTE
------
`datos/codigo_agrupador.csv`, versionado en el repo. Su encabezado cita las fuentes:
- **Códigos**: la enumeración `c_CodAgrup` del XSD oficial del SAT
  `http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogosParaEsqContE/CatalogosParaEsqContE.xsd`
  (1080 códigos), tomada de la copia que distribuye el paquete `satcfdi` 26.10.0.
- **Nombres**: el catálogo `c_CodAgrup` de `satcfdi` (transcrito de los catálogos del SAT),
  cotejado contra la transcripción del Anexo 24 del DOF del 04-oct-2016 en elconta.mx; los
  nombres que venían cortados se completaron de ahí. 401.39–401.41 (zona fronteriza norte)
  vienen de contadormx.com. **402.05 queda `FUENTE POR CONFIRMAR`**: está en el XSD
  vigente, pero no se encontró su nombre en una fuente verificable.

NIVEL, NATURALEZA Y TIPO
------------------------
El Anexo 24 da código y nombre; el nivel (1 cuenta, 2 subcuenta, 0 encabezado de rubro)
sale del propio código. La naturaleza y el tipo NO vienen en el Anexo: se derivan del rubro
(1xx activo deudora, 2xx pasivo acreedora, 3xx capital acreedora, 4xx ingreso acreedora,
5xx costo deudora, 6xx gasto deudora, 7xx RIF, 8xx orden) con las cuentas complementarias
de naturaleza contraria que el propio catálogo nombra (estimaciones, depreciaciones y
amortizaciones acumuladas; devoluciones sobre ventas y sobre compras; productos
financieros y otros productos; contra cuentas de orden).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RUTA_CSV = Path(__file__).parent / "datos" / "codigo_agrupador.csv"
FUENTE = (
    "Anexo 24 RMF — XSD oficial del SAT c_CodAgrup (ContabilidadE 1.3, CatalogosParaEsqContE); "
    "nombres de satcfdi 26.10.0 cotejados contra el DOF 04-oct-2016"
)
POR_CONFIRMAR = "FUENTE POR CONFIRMAR"


@dataclass(frozen=True)
class CodigoAgrupador:
    """Un renglón del código agrupador."""

    codigo: str
    nivel: int
    nombre: str
    naturaleza: str
    tipo: str
    nota: str

    @property
    def asignable(self) -> bool:
        """Se puede asignar a una cuenta (no es encabezado de rubro)."""
        return self.nivel in (1, 2)


@lru_cache(maxsize=1)
def catalogo() -> dict[str, CodigoAgrupador]:
    """Todo el código agrupador, por código, en el orden del Anexo."""
    with RUTA_CSV.open(encoding="utf-8") as f:
        lineas = [linea for linea in f if not linea.startswith("#")]
    salida: dict[str, CodigoAgrupador] = {}
    for fila in csv.DictReader(lineas):
        salida[fila["codigo"]] = CodigoAgrupador(
            codigo=fila["codigo"], nivel=int(fila["nivel"]), nombre=fila["nombre"],
            naturaleza=fila["naturaleza"], tipo=fila["tipo"], nota=fila["nota"],
        )
    return salida


def obtener(codigo: str) -> CodigoAgrupador | None:
    """El código, o None si no existe en el Anexo."""
    return catalogo().get(codigo.strip())


def como_lista() -> list[dict[str, object]]:
    """El catálogo serializable (para la pantalla)."""
    return [
        {"codigo": c.codigo, "nivel": c.nivel, "nombre": c.nombre,
         "naturaleza": c.naturaleza, "tipo": c.tipo, "nota": c.nota}
        for c in catalogo().values()
    ]
