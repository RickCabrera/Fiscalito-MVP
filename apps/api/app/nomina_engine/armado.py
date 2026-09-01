"""
Arma un recibo **calculando** sus deducciones con el motor.

Es la otra mitad de `recibo.py`, y esta separada a proposito. `recibo.py` es
aritmetica pura sobre partidas dadas y por eso reproduce los totales de los 70
recibos del caso real, 70 de 70. Este modulo, en cambio, **calcula** el ISR y
la cuota obrera, asi que se mide contra lo que ya establecieron F1-03 y F1-04:

- la cuota obrera del caso real solo se reproduce en **5 de 70** (§D14);
- el ISR, en los **28 recibos de abril** (§D15).

F1-05 no re-litiga esos numeros ni intenta mejorarlos. Y en particular:
**cerrar el neto metiendo la diferencia en una deduccion clave 004 "Otros"
esta prohibido** — haria cuadrar los 70 sin probar nada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.cuotas import DiasDelPeriodo, cuotas_empleado
from app.nomina_engine.integracion import SBCAcotado
from app.nomina_engine.isr_nomina import (
    ContextoExencion,
    Percepcion,
    base_gravable,
    isr_retenido,
)
from app.nomina_engine.recibo import (
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)

# Claves internas por defecto. NO son claves de catalogo: son el codigo del
# patron, y por eso se pueden sobreescribir.
CLAVE_INTERNA_ISR = "D001"
CLAVE_INTERNA_IMSS = "D002"
CLAVE_INTERNA_SUBSIDIO = "D100"

TIPO_DEDUCCION_ISR = "002"
TIPO_DEDUCCION_SEGURIDAD_SOCIAL = "001"
TIPO_OTRO_PAGO_SUBSIDIO = "002"


def armar_recibo(
    percepciones: tuple[tuple[Percepcion, str], ...],
    sbc: SBCAcotado,
    dias: DiasDelPeriodo,
    fecha: date,
    zona: ZonaSalarioMinimo,
    prima_riesgo: Decimal,
    ingreso_gravado_mensual: Decimal,
    clave_periodicidad: str,
    es_trabajador_de_salario_minimo: bool = False,
) -> Recibo:
    """
    Calcula ISR y cuota obrera, y arma el recibo.

    Args:
        percepciones: pares `(percepcion, clave_interna)`. La clave interna es
            el codigo del patron y **no se deriva** del tipo de catalogo: en el
            caso real conviven `Clave="P019"` con `TipoPercepcion="020"`.
        ingreso_gravado_mensual: base mensual para el tope del subsidio. La
            decision de como se obtiene sigue abierta (§D11); este modulo no la
            toma, igual que `isr_retenido`.

    El subsidio se emite como `OtroPago` clave 002 con `Importe` = lo
    efectivamente entregado (cero desde 2024) y `SubsidioCausado` con el monto.
    Es lo que hacen las 70 fixtures del caso real, y sigue a §D16: al
    trabajador de salario minimo queda causado, sin acreditar y sin entregar.
    """
    contexto = ContextoExencion(
        fecha=fecha, es_trabajador_de_salario_minimo=es_trabajador_de_salario_minimo
    )
    desglose, base = base_gravable(tuple(p for p, _ in percepciones), contexto)
    claves_internas = [clave for _, clave in percepciones]

    partidas = tuple(
        PartidaPercepcion(
            tipo=gravada.clave,
            clave=clave_interna,
            concepto=gravada.descripcion,
            gravado=gravada.gravado,
            exento=gravada.exento,
        )
        for gravada, clave_interna in zip(desglose, claves_internas)
    )

    isr = isr_retenido(
        base,
        clave_periodicidad,
        fecha,
        ingreso_gravado_mensual,
        dias.dias_periodo,
        es_trabajador_de_salario_minimo,
    )
    obrera = cuotas_empleado(sbc, dias, fecha, zona, prima_riesgo).total_obrero

    deducciones: list[PartidaDeduccion] = []
    if isr.retenido > 0:
        deducciones.append(
            PartidaDeduccion(TIPO_DEDUCCION_ISR, CLAVE_INTERNA_ISR, "ISR", isr.retenido)
        )
    if obrera > 0:
        deducciones.append(
            PartidaDeduccion(
                TIPO_DEDUCCION_SEGURIDAD_SOCIAL, CLAVE_INTERNA_IMSS, "IMSS", obrera
            )
        )

    otros_pagos = (
        PartidaOtroPago(
            tipo=TIPO_OTRO_PAGO_SUBSIDIO,
            clave=CLAVE_INTERNA_SUBSIDIO,
            concepto="SUBSIDIO PARA EL EMPLEO",
            # Desde 2024 el subsidio no se entrega en efectivo: lo que se
            # acredito redujo el ISR y ya esta reflejado en `isr.retenido`.
            importe=Decimal("0.00"),
            subsidio_causado=isr.subsidio,
        ),
    ) if isr.subsidio > 0 else ()

    return Recibo(
        percepciones=partidas,
        deducciones=tuple(deducciones),
        otros_pagos=otros_pagos,
    )
