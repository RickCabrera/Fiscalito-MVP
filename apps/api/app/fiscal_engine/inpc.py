"""
Índice Nacional de Precios al Consumidor (INPC), serie mensual versionada (P3-02).

FUENTE
------
INEGI, INPC mensual, base segunda quincena de julio de 2018 = 100. El Art. 20 CFF manda que
el INPC lo calcule el INEGI y se publique en el DOF dentro de los primeros diez días del mes
siguiente. La serie vive en `datos/inpc.csv`, una fila por mes, con dos columnas de
trazabilidad:

- `verificacion = boletin_inegi`: el valor se cotejó contra el boletín de prensa del INEGI
  que se cita en `fuente` ("En <mes> de <año>, el INPC presentó un nivel de X puntos").
- `verificacion = secundaria_coincidente`: el valor se tomó de dos tablas secundarias que
  coinciden entre sí al milésimo (elcontribuyente.mx e idconline.mx). FUENTE POR CONFIRMAR
  contra el DOF o el BIE del INEGI; las filas cotejadas contra boletín coinciden al milésimo
  con esas mismas tablas, lo que da confianza en la serie, pero no sustituye el cotejo.

Todo cálculo que use un índice no verificado lo dice en su respuesta (`por_confirmar` y
`fuentes_por_confirmar`, ver `ValorINPC.aviso_por_confirmar`).

AGREGAR UN MES
--------------
Se agrega una fila al CSV con su boletín. Nunca se extrapola: si el mes que el cálculo pide
no está publicado, manda el Art. 17-A CFF ("se aplicará el último índice mensual publicado"),
y eso lo resuelve `inpc_para_actualizar`, no un valor inventado.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from app.exceptions import FiscalValidationError

ARCHIVO_INPC = Path(__file__).parent / "datos" / "inpc.csv"
# Única marca de la columna `verificacion` que cuenta como verificada (O12: el resto se
# propaga a la respuesta como `por_confirmar`).
VERIFICADO = "boletin_inegi"


@dataclass(frozen=True)
class ValorINPC:
    """Un mes de la serie, con su trazabilidad."""

    anio: int
    mes: int
    valor: Decimal
    verificacion: str
    fuente: str

    @property
    def verificado(self) -> bool:
        """True sólo si el valor se cotejó contra el boletín del INEGI (`boletin_inegi`)."""
        return self.verificacion == VERIFICADO

    @property
    def aviso_por_confirmar(self) -> str | None:
        """Texto para la respuesta cuando el índice viene de fuente secundaria; None si no."""
        if self.verificado:
            return None
        return (f"INPC {self.anio}-{self.mes:02d} ({self.valor}): tablas secundarias, sin "
                f"cotejar con el boletín del INEGI")


@lru_cache(maxsize=1)
def serie_inpc() -> dict[tuple[int, int], ValorINPC]:
    """La serie completa indexada por (año, mes). Se lee una vez."""
    serie: dict[tuple[int, int], ValorINPC] = {}
    with ARCHIVO_INPC.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            anio, mes = int(fila["anio"]), int(fila["mes"])
            serie[(anio, mes)] = ValorINPC(
                anio, mes, Decimal(fila["inpc"]), fila["verificacion"], fila["fuente"]
            )
    return serie


def ultimo_publicado() -> ValorINPC:
    """El mes más reciente cargado en la serie."""
    serie = serie_inpc()
    return serie[max(serie)]


def inpc(anio: int, mes: int) -> ValorINPC:
    """El INPC de un mes. 422 si no está en la serie (no se extrapola)."""
    valor = serie_inpc().get((anio, mes))
    if valor is None:
        primero = min(serie_inpc())
        ultimo = ultimo_publicado()
        raise FiscalValidationError(
            f"No hay INPC cargado para {mes:02d}/{anio}. La serie va de "
            f"{primero[1]:02d}/{primero[0]} a {ultimo.mes:02d}/{ultimo.anio}; para agregar un "
            f"mes hay que citar el boletín del INEGI en datos/inpc.csv."
        )
    return valor


def mes_anterior(anio: int, mes: int) -> tuple[int, int]:
    """(año, mes) del mes calendario anterior."""
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def inpc_para_actualizar(anio: int, mes: int) -> tuple[ValorINPC, bool]:
    """
    El INPC de (año, mes) o, si aún no se publica, el último publicado.

    Art. 17-A CFF: "Cuando no se publiquen oportunamente los índices, la actualización de que
    se trate se realizará aplicando el último índice mensual publicado." Devuelve también si
    se usó esa regla, para que la respuesta lo diga.
    """
    ultimo = ultimo_publicado()
    if (anio, mes) > (ultimo.anio, ultimo.mes):
        return ultimo, True
    return inpc(anio, mes), False
