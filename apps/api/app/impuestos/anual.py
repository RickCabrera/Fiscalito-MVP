"""
Cálculo anual del cliente (P3-06): personas físicas (612, 606, 625, 626) y morales (601 y
RESICO PM), con el detalle mes a mes. Devuelve UN diccionario que pinta la pantalla y que
`papeles.py` copia al Excel: el archivo y la pantalla salen del mismo cálculo, así que cuadran
por construcción (y un test lo verifica).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import FiscalValidationError
from app.fiscal_engine import personas_morales as motor
from app.fiscal_engine.anual_pf import REGIMENES_PF, anual_pf, mes_pf_dict
from app.impuestos import personas_morales as pm
from app.impuestos.flujo import flujo_del_mes
from app.impuestos.servicio import _como_cfdi, config_de, regimen_de
from app.modelos.nucleo import Cliente
from app.schemas.fiscal import PerfilContribuyente

CERO = Decimal("0.00")


def _t(v: Decimal) -> str:
    return f"{v:.2f}"


def anual_persona_fisica(db: Session, cliente: Cliente, anio: int,
                         pagos: dict[int, Decimal]) -> dict[str, Any]:
    regimen = regimen_de(cliente)
    perfil = PerfilContribuyente(rfc=cliente.rfc or "XAXX010101000", regimen=regimen,
                                 nombre=cliente.nombre)
    facturas = [_como_cfdi(e) for m in range(1, 13) for e in flujo_del_mes(db, cliente, anio, m)]
    r = anual_pf(perfil, anio, facturas, pagos)
    return {
        "tipo": "pf", "anio": anio, "regimen": regimen, "fuente": "boveda",
        "renglones": [motor.renglon_dict(x) for x in r.renglones],
        "meses": [mes_pf_dict(m) for m in r.meses],
        "notas": ["Ingresos y deducciones de la bóveda por flujo de efectivo."] + r.notas,
    }


def anual_persona_moral(db: Session, cliente: Cliente, anio: int, tipo: str) -> dict[str, Any]:
    d = pm.datos_de(db, cliente, anio)
    modo = config_de(db, cliente).modo_factor
    pagos, coef, origen, b = pm.pagos_provisionales(db, cliente, anio, 12, tipo)
    pagado = sum((p.pago_efectuado for p in pagos), CERO)
    retenciones = pagos[-1].retenciones
    r = motor.anual_pm(pm.entrada_anual(b, d, anio, modo, pagado, retenciones),
                       resico=tipo == "resico")
    ret_mes = d.retenciones_bancarias
    meses = [{
        "mes": m, "ingresos": _t(b.ingresos_mes[m]), "deducciones": _t(b.deducciones_mes[m]),
        "no_deducibles": _t(b.no_deducibles_mes[m]),
        "retenciones": _t(ret_mes.get(m, CERO)),
        "pago_provisional": _t(pagos[m - 1].pago_efectuado),
    } for m in range(1, 13)]
    notas = b.notas + r.notas + pm.notas_provisionales(tipo, coef, origen, 12)
    # O12: INPC de fuente secundaria en el ajuste por inflación, las pérdidas o los pagos.
    fuentes = list(dict.fromkeys(
        [*r.fuentes_por_confirmar, *(x for p in pagos for x in p.fuentes_por_confirmar)]))
    if fuentes:
        notas.append("Hay INPC de fuente secundaria sin cotejar con el boletín del INEGI "
                     "(FUENTE POR CONFIRMAR): " + "; ".join(fuentes) + ".")
    if b.origen_saldos == "contabilidad":
        notas.append("La cuenta 213 puede incluir ISR propio por pagar, que no es deuda para "
                     "el ajuste (Art. 46): revísalo o captura las cuentas de deudas.")
    return {
        "tipo": "pm" if tipo == "general" else "resico_pm", "anio": anio,
        "regimen": regimen_de(cliente), "fuente": b.fuente,
        "renglones": [motor.renglon_dict(x) for x in r.renglones],
        "meses": meses,
        "ajustes": {
            "ingresos_adicionales": _t(d.ingresos_adicionales),
            "deduccion_inversiones": _t(d.deduccion_inversiones),
            "deducciones_adicionales": _t(d.deducciones_adicionales),
            "no_deducibles_adicionales": _t(d.no_deducibles_adicionales),
        },
        "cuentas": [{"numero": c.numero, "nombre": c.nombre, "codigo": c.codigo,
                     "clase": c.clase, "total": _t(c.total),
                     "meses": [_t(c.meses[m]) for m in range(1, 13)]} for c in b.cuentas],
        "pagos_provisionales": [motor.pago_dict(p) for p in pagos],
        "coeficiente": {
            "aplicado": f"{coef:.4f}", "origen": origen,
            "siguiente": f"{r.coeficiente_siguiente:.4f}",
            "utilidad_fiscal": _t(r.utilidad_fiscal),
            "ingresos_nominales": _t(r.ingresos_nominales),
            "anticipos_miembros": _t(d.anticipos_miembros_base),
        },
        "aai": motor.aai_dict(b.aai) if b.aai else None,
        "origen_saldos": b.origen_saldos,
        "ptu": {"utilidad_antes_ptu": _t(r.importe("utilidad_antes_ptu")),
                "no_deducibles_art28_xxx": _t(r.no_deducibles_art28_xxx),
                "origen_art28_xxx": b.origen_art28_xxx,
                "renta_gravable": _t(r.renta_gravable_ptu),
                "porcentaje": f"{motor.PORCENTAJE_PTU:.2f}",
                "fundamento": motor.FUNDAMENTO_PTU,
                "a_repartir": _t(r.ptu_a_repartir), "pagada_en_el_ejercicio": _t(d.ptu_pagada)},
        "perdidas": [motor.perdida_dict(p) for p in r.perdidas],
        "notas": notas,
        "por_confirmar": bool(fuentes),
        "fuentes_por_confirmar": fuentes,
    }


def anual_cliente(db: Session, cliente: Cliente, anio: int,
                  pagos_pf: dict[int, Decimal]) -> dict[str, Any]:
    """La anual que le toca al cliente según su régimen."""
    tipo = pm.tipo_pm(cliente)
    if tipo is not None:
        return anual_persona_moral(db, cliente, anio, tipo)
    regimen = regimen_de(cliente)
    if regimen in REGIMENES_PF:
        return anual_persona_fisica(db, cliente, anio, pagos_pf)
    if not regimen:
        raise FiscalValidationError("Captura el régimen de este cliente.")
    raise FiscalValidationError(
        f"El régimen {regimen} no tiene cálculo anual en el sistema (601, RESICO PM, 612, "
        "606, 625 y 626).")
