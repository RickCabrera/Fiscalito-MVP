"""
Actualización y recargos de contribuciones pagadas fuera de plazo (P3-02).

FUENTES
-------
- **Art. 17-A CFF** — actualización. "Dicho factor se obtendrá dividiendo el Índice Nacional
  de Precios al Consumidor del mes anterior al más reciente del periodo entre el citado índice
  correspondiente al mes anterior al más antiguo de dicho periodo." Si el resultado es menor a
  1, el factor es 1. Si el INPC del mes no se ha publicado, se aplica el último publicado.
  Último párrafo: las operaciones "con el fin de determinar factores o proporciones ... deberán
  calcularse hasta el diezmilésimo".
- **Art. 21 CFF** — "su monto se actualizará desde el mes en que debió hacerse el pago y hasta
  que el mismo se efectúe"; los recargos "se causarán por cada mes o fracción que transcurra a
  partir del día en que debió hacerse el pago", sobre "el monto de las contribuciones ...
  actualizados", "hasta por cinco años" (salvo Art. 67), y "la tasa de recargos para cada uno
  de los meses de mora será la que resulte de incrementar en 50%" la que fije la Ley de
  Ingresos de la Federación para la prórroga.
- **Ley de Ingresos de la Federación** — tasa mensual de prórroga y de pago a plazos, por año,
  en `datos/recargos.csv` (2026: LIF 2026 art. 11 → prórroga 1.38%, mora 2.07%).
- **Art. 44 RCFF** — "El monto de las contribuciones actualizadas deberá expresarse hasta
  centavos."
- **Art. 20 CFF** — para el pago, los centavos de 1 a 50 bajan al peso y de 51 a 99 suben.

LA REGLA DE REDONDEO DEL FACTOR ES CRITERIO DEL DESPACHO (DP-3)
----------------------------------------------------------------
"Hasta el diezmilésimo" no dice si se trunca o se redondea, y en la práctica conviven las dos
lecturas: hay calculadoras públicas que ni siquiera cortan el factor (sdv.com.mx publica
$25,275.27 para $25,000 con 145.169/143.588, que sólo sale con el cociente completo; con
1.0110 truncado da $25,275.00). Por eso `ModoFactor` es configurable por cliente y el default
es `truncar` — la lectura más extendida del último párrafo del Art. 17-A —, marcado
`# FUENTE POR CONFIRMAR` hasta que la contadora lo confirme (DP-3).

FUENTES POR CONFIRMAR EN LA RESPUESTA (O12)
-------------------------------------------
Si el factor usa un INPC que no se cotejó contra el boletín del INEGI, o un mes de mora cae en
un año cuya tasa de la LIF viene de fuente secundaria, el resultado lo dice:
`fuentes_por_confirmar` (una línea por índice o tasa) y `por_confirmar` = True. La marca sale
de la columna `verificacion` de `datos/inpc.csv` y `datos/recargos.csv`.

MÓDULOS (O11): los recargos viven en `recargos.py` y la fecha límite en `fecha_limite.py`;
aquí se reexportan para no romper a quien los importaba de este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Literal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.fecha_limite import (
    dias_inhabiles_cff,
    fecha_limite_mensual,
    siguiente_dia_habil,
)
from app.fiscal_engine.inpc import inpc_para_actualizar, mes_anterior
from app.fiscal_engine.recargos import (
    INCREMENTO_MORA,
    TOPE_MESES_RECARGOS_DEFAULT,
    MesDeRecargo,
    TasasRecargoAnio,
    TipoRecargo,
    avisos_tasas,
    calcular_recargos,
    meses_de_mora,
    sumar_meses,
    tasa_mensual,
    tasas_recargos,
)
from app.redondeo import redondear

# Reexportados: la API pública de este módulo antes de partirlo (O11).
__all__ = [
    "DIEZMILESIMO", "INCREMENTO_MORA", "MODO_FACTOR_DEFAULT", "TOPE_MESES_RECARGOS_DEFAULT",
    "FactorActualizacion", "MesDeRecargo", "ModoFactor", "ResultadoActualizacion",
    "TasasRecargoAnio", "TipoRecargo", "ajustar_a_pesos", "calcular_actualizacion_recargos",
    "calcular_recargos", "cortar_diezmilesimo", "dias_inhabiles_cff", "factor_actualizacion",
    "fecha_limite_mensual", "meses_de_mora", "resultado_como_dict", "siguiente_dia_habil",
    "sumar_meses", "tasa_mensual", "tasas_recargos",
]

ModoFactor = Literal["truncar", "redondear", "sin_redondeo"]

# FUENTE POR CONFIRMAR: truncar vs redondear el factor al diezmilésimo (DP-3). Ver docstring.
MODO_FACTOR_DEFAULT: ModoFactor = "truncar"
DIEZMILESIMO = Decimal("0.0001")


# ── factor ──


def cortar_diezmilesimo(valor: Decimal, modo: ModoFactor) -> Decimal:
    """Factor o proporción al diezmilésimo (Art. 17-A CFF, último párrafo) según el criterio."""
    if modo == "sin_redondeo":
        return valor
    redondeo = ROUND_DOWN if modo == "truncar" else ROUND_HALF_UP
    return valor.quantize(DIEZMILESIMO, rounding=redondeo)


@dataclass(frozen=True)
class FactorActualizacion:
    """El factor y de dónde salió, para que el contador lo pueda rehacer a mano."""

    factor: Decimal
    factor_sin_cortar: Decimal
    inpc_reciente: Decimal
    mes_inpc_reciente: str
    inpc_antiguo: Decimal
    mes_inpc_antiguo: str
    se_uso_ultimo_publicado: bool
    factor_menor_a_uno: bool
    fuentes_por_confirmar: tuple[str, ...] = ()


def factor_actualizacion(
    fecha_debio_pagarse: date, fecha_pago: date, modo: ModoFactor = MODO_FACTOR_DEFAULT
) -> FactorActualizacion:
    """
    Factor de actualización del Art. 17-A CFF para un pago extemporáneo.

    El periodo va del mes en que debió hacerse el pago al mes en que se efectúa (Art. 21):
    numerador = INPC del mes anterior al del pago; denominador = INPC del mes anterior al del
    vencimiento.
    """
    if fecha_pago < fecha_debio_pagarse:
        raise FiscalValidationError("La fecha de pago es anterior a la fecha límite.")
    reciente_am = mes_anterior(fecha_pago.year, fecha_pago.month)
    antiguo_am = mes_anterior(fecha_debio_pagarse.year, fecha_debio_pagarse.month)
    reciente, uso_ultimo_r = inpc_para_actualizar(*reciente_am)
    antiguo, uso_ultimo_a = inpc_para_actualizar(*antiguo_am)
    cociente = reciente.valor / antiguo.valor
    cortado = cortar_diezmilesimo(cociente, modo)
    menor = cortado < 1
    return FactorActualizacion(
        factor=Decimal("1") if menor else cortado,
        factor_sin_cortar=cociente,
        inpc_reciente=reciente.valor,
        mes_inpc_reciente=f"{reciente.anio}-{reciente.mes:02d}",
        inpc_antiguo=antiguo.valor,
        mes_inpc_antiguo=f"{antiguo.anio}-{antiguo.mes:02d}",
        se_uso_ultimo_publicado=uso_ultimo_r or uso_ultimo_a,
        factor_menor_a_uno=menor,
        fuentes_por_confirmar=tuple(
            a for a in (reciente.aviso_por_confirmar, antiguo.aviso_por_confirmar) if a
        ),
    )


@dataclass(frozen=True)
class ResultadoActualizacion:
    """Actualización y recargos de un adeudo, con el detalle para revisarlo."""

    monto: Decimal
    fecha_debio_pagarse: date
    fecha_pago: date
    factor: FactorActualizacion | None
    monto_actualizado: Decimal
    actualizacion: Decimal
    meses: int
    meses_topados: bool
    tasa_acumulada: Decimal
    recargos: Decimal
    total: Decimal
    total_a_pagar_ajustado: Decimal
    tipo_recargo: TipoRecargo
    modo_factor: ModoFactor
    detalle_meses: tuple[MesDeRecargo, ...] = field(default_factory=tuple)
    notas: tuple[str, ...] = field(default_factory=tuple)
    fuentes_por_confirmar: tuple[str, ...] = field(default_factory=tuple)

    @property
    def por_confirmar(self) -> bool:
        """True si algún INPC o tasa de recargos usado viene de fuente secundaria."""
        return bool(self.fuentes_por_confirmar)


def ajustar_a_pesos(monto: Decimal) -> Decimal:
    """Art. 20 CFF: 1 a 50 centavos bajan al peso; 51 a 99 suben."""
    pesos = monto.quantize(Decimal("1"), rounding=ROUND_DOWN)
    centavos = monto - pesos
    return pesos + (1 if centavos >= Decimal("0.51") else 0)


def calcular_actualizacion_recargos(
    monto: Decimal,
    fecha_debio_pagarse: date,
    fecha_pago: date,
    *,
    tipo_recargo: TipoRecargo = "mora",
    modo_factor: ModoFactor = MODO_FACTOR_DEFAULT,
    tope_meses: int = TOPE_MESES_RECARGOS_DEFAULT,
) -> ResultadoActualizacion:
    """
    Actualización (Art. 17-A) y recargos (Art. 21) de `monto`, pagado en `fecha_pago`.

    Redondeo: el monto actualizado y los recargos a centavos con ROUND_HALF_UP (Art. 44
    RCFF: "hasta centavos"); la tasa acumulada es la suma exacta de las tasas mensuales; el
    total a pagar además se ajusta a pesos (Art. 20 CFF).
    """
    if monto < 0:
        raise FiscalValidationError("El monto no puede ser negativo.")
    if tope_meses <= 0:
        raise FiscalValidationError("El tope de meses de recargos debe ser positivo.")
    notas: list[str] = []
    monto = redondear(monto)
    if fecha_pago <= fecha_debio_pagarse or monto == 0:
        return ResultadoActualizacion(
            monto=monto, fecha_debio_pagarse=fecha_debio_pagarse, fecha_pago=fecha_pago,
            factor=None, monto_actualizado=monto, actualizacion=Decimal("0.00"), meses=0,
            meses_topados=False, tasa_acumulada=Decimal("0"), recargos=Decimal("0.00"),
            total=monto, total_a_pagar_ajustado=ajustar_a_pesos(monto),
            tipo_recargo=tipo_recargo, modo_factor=modo_factor,
            notas=("Pagado en plazo: sin actualización ni recargos.",) if monto else (),
        )

    factor = factor_actualizacion(fecha_debio_pagarse, fecha_pago, modo_factor)
    if factor.se_uso_ultimo_publicado:
        notas.append("Aún no se publica el INPC del mes: se usó el último publicado "
                     "(Art. 17-A CFF).")
    if factor.factor_menor_a_uno:
        notas.append("El factor resultó menor a 1: se toma 1 (Art. 17-A CFF).")
    actualizado = redondear(monto * factor.factor)

    meses = meses_de_mora(fecha_debio_pagarse, fecha_pago)
    topados = meses > tope_meses
    if topados:
        notas.append(f"Recargos topados a {tope_meses} meses (Art. 21 CFF).")
        meses = tope_meses
    detalle, tasa_acumulada, recargos = calcular_recargos(
        actualizado, fecha_debio_pagarse, meses, tipo_recargo
    )
    if tipo_recargo.startswith("parcialidades"):
        notas.append(
            "Estimación simple: tasa de pago a plazos por mes sobre el monto actualizado, sin "
            "tabla de amortización del Art. 66-A CFF (FUENTE POR CONFIRMAR)."
        )
    total = actualizado + recargos
    fuentes = factor.fuentes_por_confirmar + avisos_tasas(detalle)
    if fuentes:
        notas.append("Hay índices o tasas de fuente secundaria (FUENTE POR CONFIRMAR): ver "
                     "fuentes_por_confirmar.")
    return ResultadoActualizacion(
        monto=monto, fecha_debio_pagarse=fecha_debio_pagarse, fecha_pago=fecha_pago,
        factor=factor, monto_actualizado=actualizado, actualizacion=actualizado - monto,
        meses=meses, meses_topados=topados, tasa_acumulada=tasa_acumulada,
        recargos=recargos, total=total, total_a_pagar_ajustado=ajustar_a_pesos(total),
        tipo_recargo=tipo_recargo, modo_factor=modo_factor, detalle_meses=tuple(detalle),
        notas=tuple(notas), fuentes_por_confirmar=fuentes,
    )


def resultado_como_dict(r: ResultadoActualizacion) -> dict[str, object]:
    """Serialización para la API (importes como texto con 2 decimales)."""
    f = r.factor
    return {
        "monto": f"{r.monto:.2f}",
        "fecha_debio_pagarse": r.fecha_debio_pagarse.isoformat(),
        "fecha_pago": r.fecha_pago.isoformat(),
        "factor": None if f is None else {
            "factor": str(f.factor),
            "factor_sin_cortar": f"{f.factor_sin_cortar:.10f}",
            "inpc_reciente": str(f.inpc_reciente), "mes_inpc_reciente": f.mes_inpc_reciente,
            "inpc_antiguo": str(f.inpc_antiguo), "mes_inpc_antiguo": f.mes_inpc_antiguo,
            "se_uso_ultimo_publicado": f.se_uso_ultimo_publicado,
            "factor_menor_a_uno": f.factor_menor_a_uno,
            "fuentes_por_confirmar": list(f.fuentes_por_confirmar),
        },
        "monto_actualizado": f"{r.monto_actualizado:.2f}",
        "actualizacion": f"{r.actualizacion:.2f}",
        "meses": r.meses,
        "meses_topados": r.meses_topados,
        "tasa_acumulada": str(r.tasa_acumulada),
        "recargos": f"{r.recargos:.2f}",
        "total": f"{r.total:.2f}",
        "total_a_pagar_ajustado": f"{r.total_a_pagar_ajustado:.2f}",
        "tipo_recargo": r.tipo_recargo,
        "modo_factor": r.modo_factor,
        "detalle_meses": [
            {"numero": m.numero, "inicia": m.inicia.isoformat(), "tasa": str(m.tasa)}
            for m in r.detalle_meses
        ],
        "notas": list(r.notas),
        "por_confirmar": r.por_confirmar,
        "fuentes_por_confirmar": list(r.fuentes_por_confirmar),
        "fundamento": "Arts. 17-A, 20 y 21 CFF; Art. 44 RCFF; LIF del año de cada mes de mora.",
    }
