"""
Redondeo monetario del sistema.

Una sola definicion, a proposito. El modo de redondeo es la decision **D2** de
`docs/decisiones-nomina.md` (por concepto y por empleado, 2 decimales, al
estilo SUA) y de el depende que el motor cuadre contra el caso real. Tres
copias privadas del mismo helper pueden separarse sin que ningun test falle,
asi que vive aqui y lo importan `app/constants.py` y `app/nomina_engine/`.

`ROUND_HALF_UP` NO es el redondeo por defecto de Python: `Decimal.quantize()`
sin `rounding` usa `ROUND_HALF_EVEN` (banker's rounding), que en los empates
redondea al par mas cercano — 0.125 daria 0.12 en vez de 0.13. La diferencia
solo aparece en empates exactos, que es justo lo que hace que el bug sobreviva
a una suite que no los prueba.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DOS_DECIMALES = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_UP (D2)."""
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


CUATRO_DECIMALES = Decimal("0.0001")


def redondear_factor(valor: Decimal) -> Decimal:
    """
    Redondea a 4 decimales con ROUND_HALF_UP.

    Es la precision con la que se declara el factor de integracion y con la
    que lo publican las tablas de prestaciones minimas de ley. Ver la decision
    D12 de `docs/decisiones-nomina.md`: el SBC se calcula con ESTE factor ya
    redondeado, no con el cociente completo, para que el numero que el patron
    declara al IMSS sea reproducible a mano.
    """
    return valor.quantize(CUATRO_DECIMALES, rounding=ROUND_HALF_UP)
