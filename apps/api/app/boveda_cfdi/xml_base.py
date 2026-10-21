"""
Utilidades de lectura de XML compartidas por el parser de la bóveda (P0-03).

Salieron de `parser.py` en P6-05 sólo para respetar el tope de 300 líneas; el parser
las reexporta, así que quien importe de `app.boveda_cfdi.parser` no cambia.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

NS_CFDI = {"3.3": "http://www.sat.gob.mx/cfd/3", "4.0": "http://www.sat.gob.mx/cfd/4"}
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"
NS_PAGOS = {"1.0": "http://www.sat.gob.mx/Pagos", "2.0": "http://www.sat.gob.mx/Pagos20"}
NS_NOMINA12 = "http://www.sat.gob.mx/nomina12"

TIPOS = {"I", "E", "P", "N", "T"}
# Catálogo c_Impuesto del SAT.
ISR, IVA, IEPS = "001", "002", "003"

CENTAVO = Decimal("0.01")


class CfdiInvalido(ValueError):
    """El archivo no es un CFDI timbrado que la bóveda pueda guardar."""



def _dec(valor: str | None) -> Decimal:
    if valor is None or str(valor).strip() == "":
        return Decimal("0")
    try:
        return Decimal(str(valor).strip())
    except InvalidOperation as e:
        raise CfdiInvalido(f"Importe inválido: {valor!r}") from e


def _centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _fecha(valor: str | None, campo: str) -> datetime:
    if not valor:
        raise CfdiInvalido(f"Falta {campo}.")
    try:
        # Sin zona: el CFDI expresa la hora local del lugar de expedición.
        return datetime.fromisoformat(valor.strip()[:19])
    except ValueError as e:
        raise CfdiInvalido(f"{campo} inválida: {valor!r}") from e


def _hijo(nodo: Any, ns: str, nombre: str) -> Any:
    return nodo.find(f"{{{ns}}}{nombre}") if nodo is not None else None


def _hijos(nodo: Any, ns: str, ruta: str) -> list[Any]:
    if nodo is None:
        return []
    partes = "/".join(f"{{{ns}}}{p}" for p in ruta.split("/"))
    return list(nodo.findall(partes))


def _attrs(nodo: Any, *nombres: str) -> dict[str, str]:
    """Los atributos pedidos que traiga el nodo, como texto."""
    if nodo is None:
        return {}
    return {n: nodo.get(n) for n in nombres if nodo.get(n) is not None}

