"""Motor de resumen de retenciones a terceros."""

from __future__ import annotations
from app.schemas.fiscal import CFDI, TipoFactura
from app.schemas.retenciones import TerceroRetencion


def generar_resumen_retenciones(
    rfc_contribuyente: str,
    facturas: list[CFDI],
) -> list[TerceroRetencion]:
    """
    Genera resumen de retenciones agrupado por tercero.

    Filtra facturas donde el contribuyente es receptor y hay retenciones,
    agrupa por rfc_emisor.
    """
    rfc = rfc_contribuyente.upper()

    # Facturas donde el contribuyente es receptor con retenciones
    con_retenciones = [
        f for f in facturas
        if f.tipo == TipoFactura.INGRESO
        and f.rfc_receptor.upper() == rfc
        and (f.isr_retenido > 0 or f.iva_retenido > 0)
    ]

    # Agrupar por tercero (rfc_emisor)
    terceros: dict[str, dict] = {}
    for f in con_retenciones:
        rfc_tercero = f.rfc_emisor.upper()
        if rfc_tercero not in terceros:
            terceros[rfc_tercero] = {
                "rfc": rfc_tercero,
                "nombre": f.rfc_emisor,
                "total_pagado": 0.0,
                "isr_retenido": 0.0,
                "iva_retenido": 0.0,
                "cantidad_facturas": 0,
            }
        terceros[rfc_tercero]["total_pagado"] += f.subtotal
        terceros[rfc_tercero]["isr_retenido"] += f.isr_retenido
        terceros[rfc_tercero]["iva_retenido"] += f.iva_retenido
        terceros[rfc_tercero]["cantidad_facturas"] += 1

    return [
        TerceroRetencion(
            rfc=t["rfc"],
            nombre=t["nombre"],
            total_pagado=round(t["total_pagado"], 2),
            isr_retenido=round(t["isr_retenido"], 2),
            iva_retenido=round(t["iva_retenido"], 2),
            cantidad_facturas=t["cantidad_facturas"],
        )
        for t in terceros.values()
    ]
