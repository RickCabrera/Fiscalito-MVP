"""
Reparto de utilidades (PTU). (P4-07) — funciones puras.

FUENTES
-------
- **LFT Art. 117 y 120**: el porcentaje lo fija la Comisión Nacional (vigente:
  **10 %**, Sexta Resolución, DOF 28-02-2009) sobre la renta gravable del
  patrón conforme a la LISR. La renta gravable es **dato capturado**: el motor no
  la determina.
- **LFT Art. 123**: la utilidad repartible se divide en dos partes iguales; la
  primera por igual según los **días trabajados**, independientemente del salario;
  la segunda en proporción a los **salarios devengados** en el año.
- **LFT Art. 124**: salario = cuota diaria (sin gratificaciones, horas extra ni
  otras prestaciones). Es dato capturado por trabajador.
- **LFT Art. 127**: fr. I directores, administradores y gerentes generales no
  participan; fr. II el salario de los de confianza se topa al del sindicalizado
  de más alto salario + 20 %; fr. VIII los eventuales participan si trabajaron
  60 días en el año por lo menos; y el **tope de la reforma DOF 23-04-2021**:
  la PTU individual no puede exceder **3 meses de salario o el promedio de lo
  recibido en los últimos 3 años, lo que sea mayor**.
- **LISR Art. 93 fr. XIV**: exención de 15 UMA (desindexada, DOF 27-01-2016).
- **LSS Art. 27 fr. IV**: la PTU no integra al SBC.

# FUENTE POR CONFIRMAR: "tres meses de salario" se toma como 90 días de cuota
# diaria (Guía de la STPS para el reparto: "90 días (tres meses) del salario").
# FUENTE POR CONFIRMAR: el remanente que deja el tope no se redistribuye por
# default (la LFT no lo ordena); `ptu_remanente="redistribuir"` lo reparte entre
# quienes no topan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.isr_extraordinario import ISRExtraordinario, isr_extraordinario
from app.redondeo import redondear

CERO = Decimal("0.00")
PORCENTAJE_PTU = Decimal("0.10")  # Sexta Resolución CNPTU, DOF 28-02-2009
DIAS_TOPE = Decimal("90")  # 3 meses de salario — ver FUENTE POR CONFIRMAR arriba
UMAS_EXENCION_PTU = 15  # Art. 93 fr. XIV LISR
DIAS_MINIMOS_EVENTUAL = 60  # Art. 127 fr. VIII LFT
SOBRE_SINDICALIZADO = Decimal("1.20")  # Art. 127 fr. II LFT


@dataclass(frozen=True)
class TrabajadorPTU:
    """Lo que el reparto necesita de cada trabajador."""

    empleado_no: str
    dias_trabajados: int
    salario_diario: Decimal  # cuota diaria, Art. 124 LFT
    salarios_devengados: Decimal  # en el año
    tipo: str = "planta"  # planta | eventual | confianza | director
    promedio_ptu_3_anios: Decimal = CERO


@dataclass(frozen=True)
class RepartoTrabajador:
    """La PTU de un trabajador, con el tope y su ISR."""

    empleado_no: str
    participa: bool
    motivo: str
    por_dias: Decimal
    por_salarios: Decimal
    antes_de_tope: Decimal
    tope: Decimal
    ptu: Decimal
    exento: Decimal
    gravado: Decimal
    isr: ISRExtraordinario | None


@dataclass(frozen=True)
class ResultadoPTU:
    """El reparto completo."""

    renta_gravable: Decimal
    utilidad_repartible: Decimal
    repartido: Decimal
    remanente: Decimal
    trabajadores: tuple[RepartoTrabajador, ...]
    fundamento: str


def utilidad_repartible(renta_gravable: Decimal) -> Decimal:
    """10 % de la renta gravable (Art. 120 LFT, Sexta Resolución)."""
    if renta_gravable < 0:
        raise FiscalValidationError("La renta gravable no puede ser negativa.")
    return redondear(renta_gravable * PORCENTAJE_PTU)


def _motivo_excluido(t: TrabajadorPTU) -> str | None:
    if t.tipo == "director":
        return "Director, administrador o gerente general: no participa (Art. 127 fr. I LFT)."
    if t.tipo == "eventual" and t.dias_trabajados < DIAS_MINIMOS_EVENTUAL:
        return f"Eventual con menos de {DIAS_MINIMOS_EVENTUAL} días (Art. 127 fr. VIII LFT)."
    if t.dias_trabajados <= 0:
        return "Sin días trabajados en el ejercicio."
    return None


def _salario_tope_confianza(trabajadores: tuple[TrabajadorPTU, ...]) -> Decimal | None:
    """Salario diario del sindicalizado/planta mejor pagado × 1.2 (Art. 127 fr. II)."""
    planta = [t.salario_diario for t in trabajadores if t.tipo in ("planta", "eventual")]
    return redondear(max(planta) * SOBRE_SINDICALIZADO) if planta else None


def repartir_ptu(
    renta_gravable: Decimal,
    trabajadores: tuple[TrabajadorPTU, ...],
    fecha_pago: date,
    ingreso_ordinario_mensual: dict[str, Decimal] | None = None,
    metodo_isr: str = "art_96",
    remanente: str = "no_se_reparte",
) -> ResultadoPTU:
    """Reparte la PTU: 50 % por días, 50 % por salarios, con tope y exención."""
    repartible = utilidad_repartible(renta_gravable)
    participan = [t for t in trabajadores if _motivo_excluido(t) is None]
    tope_confianza = _salario_tope_confianza(tuple(participan))

    def salarios_de(t: TrabajadorPTU) -> Decimal:
        if t.tipo == "confianza" and tope_confianza and t.salario_diario > tope_confianza:
            return redondear(t.salarios_devengados * tope_confianza / t.salario_diario)
        return t.salarios_devengados

    total_dias = sum(t.dias_trabajados for t in participan)
    total_salarios = sum((salarios_de(t) for t in participan), start=CERO)
    mitad = repartible / 2
    factor_dias = mitad / total_dias if total_dias else CERO
    factor_salarios = mitad / total_salarios if total_salarios else CERO

    base: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
    for t in participan:
        por_dias = redondear(factor_dias * t.dias_trabajados)
        por_salarios = redondear(factor_salarios * salarios_de(t))
        tope = max(redondear(t.salario_diario * DIAS_TOPE), t.promedio_ptu_3_anios)
        base[t.empleado_no] = (por_dias, por_salarios, tope)

    # DECISIÓN PROVISIONAL (nocturno): redondear cada mitad por trabajador puede
    # sumar un centavo de más o de menos que la utilidad repartible. La diferencia
    # se ajusta en la parte por salarios del de mayor salario, para que lo repartido
    # nunca exceda el 10 % (Art. 120 LFT).
    if base:
        ajuste = repartible - sum((d + s for d, s, _ in base.values()), start=CERO)
        mayor = max(base, key=lambda k: base[k][1])
        d, s, tope = base[mayor]
        base[mayor] = (d, s + ajuste, tope)
    asignado = {k: min(d + s, tope) for k, (d, s, tope) in base.items()}
    sobrante = repartible - sum(asignado.values(), start=CERO)
    if remanente == "redistribuir":
        for _ in range(len(base) + 1):  # cada vuelta topa a alguien o agota el sobrante
            libres = {k: base[k][0] + base[k][1] for k in base if asignado[k] < base[k][2]}
            peso = sum(libres.values(), start=CERO)
            if sobrante <= Decimal("0.01") or not peso:
                break
            reparto = sobrante
            for k, w in libres.items():
                extra = min(redondear(reparto * w / peso), base[k][2] - asignado[k])
                asignado[k] += extra
                sobrante -= extra

    ordinario = ingreso_ordinario_mensual or {}
    tope_exento = redondear(uma_vigente(fecha_pago) * UMAS_EXENCION_PTU)
    filas: list[RepartoTrabajador] = []
    for t in trabajadores:
        motivo = _motivo_excluido(t)
        if motivo:
            filas.append(
                RepartoTrabajador(
                    t.empleado_no, False, motivo, CERO, CERO, CERO, CERO, CERO, CERO, CERO, None
                )
            )
            continue
        por_dias, por_salarios, tope = base[t.empleado_no]
        ptu = asignado[t.empleado_no]
        exento = min(ptu, tope_exento)
        isr = isr_extraordinario(
            ptu - exento, ordinario.get(t.empleado_no, CERO), fecha_pago, metodo_isr
        )
        filas.append(
            RepartoTrabajador(
                t.empleado_no,
                True,
                "Participa.",
                por_dias,
                por_salarios,
                por_dias + por_salarios,
                tope,
                ptu,
                exento,
                ptu - exento,
                isr,
            )
        )
    repartido = sum((f.ptu for f in filas), start=CERO)
    return ResultadoPTU(
        renta_gravable=renta_gravable,
        utilidad_repartible=repartible,
        repartido=repartido,
        remanente=repartible - repartido,
        trabajadores=tuple(filas),
        fundamento="Arts. 117, 120, 123, 124 y 127 LFT; Art. 93 fr. XIV LISR (15 UMA)",
    )
