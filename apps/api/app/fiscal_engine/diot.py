"""Motor de generacion de DIOT (Declaracion Informativa de Operaciones con Terceros)."""

from __future__ import annotations
from app.schemas.fiscal import CFDI, TipoFactura
from app.schemas.diot import ProveedorDIOT


def generar_diot(
    rfc_contribuyente: str,
    facturas: list[CFDI],
) -> list[ProveedorDIOT]:
    """
    Genera el desglose DIOT agrupando egresos por proveedor.

    Filtra facturas donde el contribuyente es receptor (el pago),
    agrupa por rfc_emisor y suma subtotal e IVA pagado.
    """
    rfc = rfc_contribuyente.upper()

    # Filtrar egresos: facturas de ingreso donde el contribuyente es receptor
    egresos = [
        f for f in facturas
        if f.tipo == TipoFactura.INGRESO and f.rfc_receptor.upper() == rfc
    ]

    # Agrupar por proveedor (rfc_emisor)
    proveedores: dict[str, dict] = {}
    for f in egresos:
        rfc_prov = f.rfc_emisor.upper()
        if rfc_prov not in proveedores:
            proveedores[rfc_prov] = {
                "rfc": rfc_prov,
                "nombre": f.rfc_emisor,
                "total_operaciones": 0.0,
                "iva_pagado": 0.0,
                "cantidad_facturas": 0,
            }
        proveedores[rfc_prov]["total_operaciones"] += f.subtotal
        proveedores[rfc_prov]["iva_pagado"] += f.iva_trasladado
        proveedores[rfc_prov]["cantidad_facturas"] += 1

    return [
        ProveedorDIOT(
            rfc=p["rfc"],
            nombre=p["nombre"],
            total_operaciones=round(p["total_operaciones"], 2),
            iva_pagado=round(p["iva_pagado"], 2),
            cantidad_facturas=p["cantidad_facturas"],
        )
        for p in proveedores.values()
    ]
