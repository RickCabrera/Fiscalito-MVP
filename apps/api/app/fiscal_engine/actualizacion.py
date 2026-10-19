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
"""

from __future__ import annotations

import csv
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.inpc import inpc_para_actualizar, mes_anterior
from app.redondeo import redondear

ModoFactor = Literal["truncar", "redondear", "sin_redondeo"]
TipoRecargo = Literal[
    "mora", "prorroga", "parcialidades_12", "parcialidades_24", "parcialidades_mas_24"
]

# FUENTE POR CONFIRMAR: truncar vs redondear el factor al diezmilésimo (DP-3). Ver docstring.
MODO_FACTOR_DEFAULT: ModoFactor = "truncar"
# Art. 21 CFF: "Los recargos se causarán hasta por cinco años". Diez en los casos del Art. 67.
TOPE_MESES_RECARGOS_DEFAULT = 60
INCREMENTO_MORA = Decimal("1.5")  # Art. 21 CFF: la de prórroga incrementada en 50 %.
DIEZMILESIMO = Decimal("0.0001")

ARCHIVO_RECARGOS = Path(__file__).parent / "datos" / "recargos.csv"


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
    )


# ── recargos ──


@dataclass(frozen=True)
class TasasRecargoAnio:
    """Tasas mensuales de un año de la LIF (fracciones, no porcentajes)."""

    anio: int
    prorroga: Decimal
    parcialidades_12: Decimal | None
    parcialidades_24: Decimal | None
    parcialidades_mas_24: Decimal | None
    verificacion: str
    fuente: str


def _dec(v: str) -> Decimal | None:
    return Decimal(v) if v.strip() else None


@lru_cache(maxsize=1)
def tasas_recargos() -> dict[int, TasasRecargoAnio]:
    """Tasas de la LIF por año, leídas de `datos/recargos.csv`."""
    salida: dict[int, TasasRecargoAnio] = {}
    with ARCHIVO_RECARGOS.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            anio = int(fila["anio"])
            salida[anio] = TasasRecargoAnio(
                anio=anio,
                prorroga=Decimal(fila["prorroga"]),
                parcialidades_12=_dec(fila["parcialidades_12"]),
                parcialidades_24=_dec(fila["parcialidades_24"]),
                parcialidades_mas_24=_dec(fila["parcialidades_mas_24"]),
                verificacion=fila["verificacion"],
                fuente=fila["fuente"],
            )
    return salida


def tasa_mensual(anio: int, tipo: TipoRecargo) -> Decimal:
    """Tasa mensual de recargos de un año. Mora = prórroga × 1.5 (Art. 21 CFF)."""
    tasas = tasas_recargos().get(anio)
    if tasas is None:
        disponibles = ", ".join(str(a) for a in sorted(tasas_recargos()))
        raise FiscalValidationError(
            f"No hay tasa de recargos cargada para {anio}. Años: {disponibles}. Para agregar uno "
            f"hay que citar la Ley de Ingresos de la Federación de ese año."
        )
    if tipo == "mora":
        return tasas.prorroga * INCREMENTO_MORA
    if tipo == "prorroga":
        return tasas.prorroga
    valor = getattr(tasas, tipo)
    if valor is None:
        raise FiscalValidationError(
            f"No hay tasa de {tipo.replace('_', ' ')} cargada para {anio} (FUENTE POR CONFIRMAR)."
        )
    return valor


def sumar_meses(fecha: date, meses: int) -> date:
    """La misma fecha `meses` después; el día se recorta al último del mes si no existe."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, monthrange(anio, mes)[1]))


def meses_de_mora(fecha_debio_pagarse: date, fecha_pago: date) -> int:
    """
    Meses o fracción transcurridos desde el día en que debió pagarse (Art. 21 CFF).

    Pagar el mismo día del vencimiento = 0. Un día después = 1. Exactamente un mes después
    (17-feb → 17-mar) = 1; un día más = 2.
    """
    if fecha_pago <= fecha_debio_pagarse:
        return 0
    completos = 0
    while sumar_meses(fecha_debio_pagarse, completos + 1) <= fecha_pago:
        completos += 1
    return completos + (1 if sumar_meses(fecha_debio_pagarse, completos) < fecha_pago else 0)


@dataclass(frozen=True)
class MesDeRecargo:
    """Un mes de mora con la tasa que le tocó."""

    numero: int
    inicia: date
    tasa: Decimal


def calcular_recargos(
    monto_actualizado: Decimal, fecha_debio_pagarse: date, meses: int, tipo: TipoRecargo
) -> tuple[tuple[MesDeRecargo, ...], Decimal, Decimal]:
    """
    Recargos de `meses` meses sobre el monto ya actualizado (Art. 21 CFF).

    Cada mes de mora toma la tasa de la LIF del año en que ese mes empieza a correr, así un
    adeudo que cruza el 1 de enero paga cada tramo con su tasa. La tasa acumulada es la suma
    exacta de las mensuales; los recargos se redondean a centavos (ROUND_HALF_UP).
    """
    detalle = []
    for n in range(1, meses + 1):
        inicia = sumar_meses(fecha_debio_pagarse, n - 1) + timedelta(days=1)
        detalle.append(MesDeRecargo(n, inicia, tasa_mensual(inicia.year, tipo)))
    tasa_acumulada = sum((m.tasa for m in detalle), Decimal("0"))
    return tuple(detalle), tasa_acumulada, redondear(monto_actualizado * tasa_acumulada)


# ── fecha límite del pago mensual ──


def _n_esimo_lunes(anio: int, mes: int, n: int) -> date:
    primero = date(anio, mes, 1)
    return primero + timedelta(days=(-primero.weekday()) % 7 + 7 * (n - 1))


def dias_inhabiles_cff(anio: int) -> frozenset[date]:
    """
    Días inhábiles del Art. 12 CFF (primer párrafo), además de sábados y domingos.

    1o. de enero; primer lunes de febrero; tercer lunes de marzo; 1o. y 5 de mayo; 16 de
    septiembre; tercer lunes de noviembre; 25 de diciembre. El 1o. de diciembre "de cada 6
    años, cuando corresponda a la transmisión del Poder Ejecutivo" no se incluye: la próxima
    ocurrencia es 2030 y la fecha de transmisión cambió por reforma constitucional (FUENTE
    POR CONFIRMAR). Los periodos vacacionales que el SAT declara inhábiles por regla de la RMF
    tampoco se incluyen: dependen de cada año.
    """
    return frozenset({
        date(anio, 1, 1), _n_esimo_lunes(anio, 2, 1), _n_esimo_lunes(anio, 3, 3),
        date(anio, 5, 1), date(anio, 5, 5), date(anio, 9, 16), _n_esimo_lunes(anio, 11, 3),
        date(anio, 12, 25),
    })


def siguiente_dia_habil(dia: date) -> date:
    """El mismo día si es hábil; si no, el siguiente hábil (Art. 12 CFF, cuarto párrafo)."""
    while dia.weekday() >= 5 or dia in dias_inhabiles_cff(dia.year):
        dia += timedelta(days=1)
    return dia


def fecha_limite_mensual(anio: int, mes: int) -> date:
    """
    Día en que debió pagarse una contribución mensual del periodo (anio, mes).

    El día 17 del mes inmediato posterior (Arts. 96 y 106 LISR, 5-D LIVA), corrido al
    siguiente día hábil si es inhábil (Art. 12 CFF). La prórroga por el sexto dígito del RFC
    NO se aplica aquí: es un beneficio de decreto que P3-10 incorpora al calendario; hasta
    entonces la fecha límite se puede capturar a mano en el resumen.
    """
    siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return siguiente_dia_habil(date(siguiente[0], siguiente[1], 17))


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
    return ResultadoActualizacion(
        monto=monto, fecha_debio_pagarse=fecha_debio_pagarse, fecha_pago=fecha_pago,
        factor=factor, monto_actualizado=actualizado, actualizacion=actualizado - monto,
        meses=meses, meses_topados=topados, tasa_acumulada=tasa_acumulada,
        recargos=recargos, total=total, total_a_pagar_ajustado=ajustar_a_pesos(total),
        tipo_recargo=tipo_recargo, modo_factor=modo_factor, detalle_meses=tuple(detalle),
        notas=tuple(notas),
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
        "fundamento": "Arts. 17-A, 20 y 21 CFF; Art. 44 RCFF; LIF del año de cada mes de mora.",
    }
