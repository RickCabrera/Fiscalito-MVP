"""
Fecha de los complementos de pago (revisión P2, §D-C1 de `docs/decisiones-contables.md`).

Un CFDI tipo P se timbra después de cobrar (hasta el día 5 del mes siguiente, o más tarde).
Para flujo de efectivo (arts. 1-B LIVA y 102 LISR: el ingreso y el IVA se causan al cobrar)
lo que cuenta es la `FechaPago` de CADA pago del complemento, no la fecha de emisión. Un
complemento puede traer pagos de fechas distintas: se agrupan por día.

`VENTANA_ANTES` / `VENTANA_DESPUES`: para encontrar los P cuyos pagos caen en un periodo se
buscan los emitidos desde un mes antes del inicio (FechaPago posterior a la emisión es raro
pero el SAT no lo impide del todo) hasta 400 días después del fin (el complemento puede
emitirse tarde; la regla general es a más tardar el día 5 del mes siguiente, regla 2.7.1.35
RMF, pero en la práctica llegan atrasados).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.modelos.cfdi import Comprobante

VENTANA_ANTES = timedelta(days=31)
VENTANA_DESPUES = timedelta(days=400)


def fecha_de_pago(pago: dict[str, Any], defecto: date) -> date:
    """El día de `FechaPago` (AAAA-MM-DDThh:mm:ss); si falta o no se lee, `defecto`."""
    texto = str(pago.get("FechaPago") or "").strip()[:10]
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return defecto


def pagos_por_fecha(comp: Comprobante) -> dict[date, list[dict[str, Any]]]:
    """Los pagos del complemento agrupados por su día de pago (en el orden del XML)."""
    defecto = comp.fecha.date()
    grupos: dict[date, list[dict[str, Any]]] = {}
    for p in ((comp.datos or {}).get("pagos") or {}).get("pagos") or []:
        grupos.setdefault(fecha_de_pago(p, defecto), []).append(p)
    return grupos
