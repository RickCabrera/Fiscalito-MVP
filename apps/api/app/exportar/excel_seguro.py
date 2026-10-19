"""
Excel sin inyección de fórmulas (revisión P1/P2).

Un texto que viene de fuera (concepto de un CFDI, referencia de un estado de cuenta, nombre
de un cliente) y empieza con `=`, `+`, `-`, `@`, tabulador o retorno de carro, Excel lo
puede tomar por fórmula: `=HYPERLINK("http://malo", "clic")` se volvería un vínculo vivo en
la hoja del contador (CSV/formula injection, OWASP).

- `texto_seguro(v)`: el valor listo para escribirse donde no hay tipo de celda (CSV):
  antepone `'` a los textos peligrosos. Lo demás pasa igual.
- `asegurar_celda(celda)`: para openpyxl. Fuerza `data_type = "s"` y `quotePrefix` (el
  apóstrofo invisible de Excel): la celda muestra el texto tal cual, no se evalúa y, si
  alguien la edita, Excel la sigue tratando como texto.
- `libro_a_bytes(wb)`: guarda el libro después de pasar `asegurar_celda` por TODAS sus
  celdas. Es la red de seguridad: ningún exportador escribe fórmulas a propósito (los
  totales se escriben con el valor calculado), así que toda celda con tipo fórmula o texto
  peligroso es dato y se fuerza a texto. Todo `.xlsx` del repo se guarda con esta función.
"""

from __future__ import annotations

import io
from typing import Any

PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def es_peligroso(valor: Any) -> bool:
    return isinstance(valor, str) and valor.startswith(PELIGROSOS)


def texto_seguro(valor: Any) -> Any:
    """`'` antepuesto a un texto que Excel tomaría por fórmula (para CSV y similares)."""
    return f"'{valor}" if es_peligroso(valor) else valor


def asegurar_celda(celda: Any) -> None:
    """Una celda openpyxl con texto peligroso (o tipo fórmula) queda como texto literal."""
    if celda.data_type == "f" or es_peligroso(celda.value):
        celda.data_type = "s"
        celda.quotePrefix = True


def asegurar_libro(wb: Any) -> None:
    for hoja in wb.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                if celda.value is not None:
                    asegurar_celda(celda)


def libro_a_bytes(wb: Any) -> bytes:
    """El .xlsx con todas sus celdas aseguradas."""
    asegurar_libro(wb)
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()
