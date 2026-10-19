"""
Reparto de utilidades (PTU). (P4-07) — funciones puras.

FUENTES
-------
- **LFT Art. 117 y 120**: el porcentaje lo fija la Comisión Nacional. Vigente: **10 %**
  de la renta gravable, ratificado por la Resolución del Consejo de Representantes de
  la Sexta Comisión Nacional para la PTU (DOF 18-09-2020); antecedente, la de la
  Quinta Comisión (DOF 03-02-2009). Fuente única: `PORCENTAJE_PTU` de este módulo.
  La renta gravable es **dato capturado**: el motor no la determina.
- **LFT Art. 123**: la utilidad repartible se divide en dos partes iguales; la
  primera por igual según los **días trabajados**, independientemente del salario;
  la segunda en proporción a los **salarios devengados** en el año.
- **LFT Art. 124**: salario = cuota diaria (sin gratificaciones, horas extra ni
  otras prestaciones). Es dato capturado por trabajador.
- **LFT Art. 127**: fr. I directores, administradores y gerentes generales no
  participan; fr. II el salario de los de confianza se topa al del **sindicalizado** de
  más alto salario —a falta de éste, al de **planta**, nunca a un eventual— + 20 %; los
  eventuales participan si trabajaron 60 días en el año por lo menos; y el **tope de la
  reforma DOF 23-04-2021**:
  la PTU individual no puede exceder **3 meses de salario o el promedio de lo
  recibido en los últimos 3 años, lo que sea mayor**.
- **LISR Art. 93 fr. XIV**: exención de 15 UMA (desindexada, DOF 27-01-2016).
- **LSS Art. 27 fr. IV**: la PTU no integra al SBC.

# FUENTE POR CONFIRMAR: "tres meses de salario" se toma como 90 días de cuota
# diaria (Guía de la STPS para el reparto: "90 días (tres meses) del salario").
# FUENTE POR CONFIRMAR: el remanente que deja el tope no se redistribuye por
# default (la LFT no lo ordena); `ptu_remanente="redistribuir"` lo reparte entre
# quienes no topan, y `"sumar_siguiente_ejercicio"` lo reporta para sumarlo a la
# utilidad repartible del año siguiente (criterio IDC, por analogía con el Art. 122 LFT).
# FUENTE POR CONFIRMAR: la numeración de las fracciones del Art. 127 tras la reforma de
# 2021 (tope y eventuales) no se pudo cotejar contra el DOF; se citan por su contenido.
# NO MODELADO (se avisa en cada reparto): fr. III (patrones cuyos ingresos derivan sólo
# de su trabajo o del cuidado de bienes que producen rentas: máximo un mes de salario),
# fr. VII (trabajadores del hogar) y fr. X.
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
PORCENTAJE_PTU = Decimal("0.10")  # Sexta Comisión Nacional para la PTU, DOF 18-09-2020
DIAS_TOPE = Decimal("90")  # 3 meses de salario — ver FUENTE POR CONFIRMAR arriba
UMAS_EXENCION_PTU = 15  # Art. 93 fr. XIV LISR
DIAS_MINIMOS_EVENTUAL = 60  # Art. 127 fr. VIII LFT
SOBRE_SINDICALIZADO = Decimal("1.20")  # Art. 127 fr. II LFT
NOTAS_REMANENTE = {
    "no_se_reparte": "Remanente de {} que deja el tope del Art. 127: no se reparte (la LFT no "
    "ordena redistribuirlo). Decisión abierta para la contadora (§D33).",
    "redistribuir": "Remanente de {} que no cupo ni redistribuyendo: todos llegaron a su tope.",
    "sumar_siguiente_ejercicio": "Remanente de {}: se suma a la utilidad repartible del "
    "ejercicio siguiente (criterio IDC, por analogía con el Art. 122 LFT).",
}


@dataclass(frozen=True)
class TrabajadorPTU:
    """Lo que el reparto necesita de cada trabajador."""

    empleado_no: str
    dias_trabajados: int
    salario_diario: Decimal  # cuota diaria, Art. 124 LFT
    salarios_devengados: Decimal  # en el año
    tipo: str = "planta"  # planta | sindicalizado | eventual | confianza | director
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
    avisos: tuple[str, ...] = ()


def utilidad_repartible(renta_gravable: Decimal) -> Decimal:
    """10 % de la renta gravable (Art. 120 LFT; Sexta Comisión, DOF 18-09-2020)."""
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
    """
    Salario diario máximo del trabajador de confianza (Art. 127 fr. II): el del
    sindicalizado de más alto salario × 1.2 o, a falta de sindicalizados, el del de
    planta. Los eventuales no cuentan.
    """
    sindicalizados = [t.salario_diario for t in trabajadores if t.tipo == "sindicalizado"]
    referencia = sindicalizados or [t.salario_diario for t in trabajadores if t.tipo == "planta"]
    return redondear(max(referencia) * SOBRE_SINDICALIZADO) if referencia else None


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
    sobra = repartible - repartido
    avisos = [
        "No modelado del Art. 127 LFT: fr. III (patrones cuyos ingresos derivan sólo de su "
        "trabajo o del cuidado de bienes que producen rentas), fr. VII (trabajadores del "
        "hogar) y fr. X. Revísalos a mano si aplican."
    ]
    if sobra > 0:
        avisos.append(
            NOTAS_REMANENTE.get(remanente, NOTAS_REMANENTE["no_se_reparte"]).format(sobra)
        )
    return ResultadoPTU(
        renta_gravable=renta_gravable,
        utilidad_repartible=repartible,
        repartido=repartido,
        remanente=sobra,
        trabajadores=tuple(filas),
        fundamento="Arts. 117, 120, 123, 124 y 127 LFT; Art. 93 fr. XIV LISR (15 UMA)",
        avisos=tuple(avisos),
    )


def ptu_individual(
    utilidad_repartible: Decimal,
    dias_trabajador: int,
    salarios_trabajador: Decimal,
    total_dias: int,
    total_salarios: Decimal,
    salario_diario: Decimal,
    promedio_3_anios: Decimal,
    fecha_pago: date,
    ingreso_ordinario_mensual: Decimal,
    metodo_isr: str = "art_96",
) -> RepartoTrabajador:
    """
    La PTU de UN trabajador cuando ya se conocen los totales de la empresa.

    Es la calculadora suelta (`/calculadoras/ptu`): misma regla que `repartir_ptu`
    —50 % días, 50 % salarios (Art. 123), tope del Art. 127 y 15 UMA exentas— para quien
    sólo tiene los totales. No aplica exclusiones (directores, eventuales): quien captura
    los totales ya los dejó fuera.
    """
    if total_dias <= 0 or total_salarios <= 0:
        raise FiscalValidationError("Los totales de días y salarios deben ser positivos.")
    mitad = utilidad_repartible / 2
    por_dias = redondear(mitad * dias_trabajador / total_dias)
    por_salarios = redondear(mitad * salarios_trabajador / total_salarios)
    tope = max(redondear(salario_diario * DIAS_TOPE), promedio_3_anios)
    ptu = min(por_dias + por_salarios, tope)
    exento = min(ptu, redondear(uma_vigente(fecha_pago) * UMAS_EXENCION_PTU))
    isr = isr_extraordinario(ptu - exento, ingreso_ordinario_mensual, fecha_pago, metodo_isr)
    return RepartoTrabajador(
        "",
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
