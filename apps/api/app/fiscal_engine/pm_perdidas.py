"""
Personas morales: factores INPC, coeficiente de utilidad y pérdidas (Arts. 14 fr. I y 57
LISR). Parte de `personas_morales.py` (O11); las fuentes y decisiones están en su docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.fiscal_engine.actualizacion import (
    MODO_FACTOR_DEFAULT,
    ModoFactor,
    cortar_diezmilesimo,
)
from app.fiscal_engine.inpc import inpc_para_actualizar
from app.redondeo import redondear

CERO = Decimal("0.00")
UNO = Decimal("1")
ANIOS_PERDIDA = 10  # Art. 57 LISR.
ANIOS_COEFICIENTE = 5  # Art. 14 fr. I.

Mes = tuple[int, int]


def mes_txt(m: Mes) -> str:
    """'AAAA-MM'."""
    return f"{m[0]}-{m[1]:02d}"


def ceros(v: Decimal) -> Decimal:
    """El importe si es positivo; si no, cero."""
    return v if v > 0 else CERO


def unicas(fuentes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Las fuentes por confirmar sin repetir, en el orden en que aparecen."""
    return tuple(dict.fromkeys(fuentes))


# ── factores ──


@dataclass(frozen=True)
class FactorINPC:
    """Un factor INPC reciente ÷ antiguo, con sus índices para rehacerlo a mano."""

    factor: Decimal
    inpc_reciente: Decimal
    mes_reciente: str
    inpc_antiguo: Decimal
    mes_antiguo: str
    uso_ultimo_publicado: bool
    # O12: índices de fuente secundaria (sin cotejar con el boletín del INEGI).
    fuentes_por_confirmar: tuple[str, ...] = ()


def factor_inpc(reciente: Mes, antiguo: Mes, modo: ModoFactor = MODO_FACTOR_DEFAULT) -> FactorINPC:
    """INPC del mes más reciente ÷ INPC del más antiguo del periodo; nunca menor que 1."""
    r, ur = inpc_para_actualizar(*reciente)
    a, ua = inpc_para_actualizar(*antiguo)
    f = cortar_diezmilesimo(r.valor / a.valor, modo)
    avisos = tuple(x for x in (r.aviso_por_confirmar, a.aviso_por_confirmar) if x)
    return FactorINPC(max(f, UNO), r.valor, mes_txt((r.anio, r.mes)), a.valor,
                      mes_txt((a.anio, a.mes)), ur or ua, avisos)


def coeficiente_utilidad(
    utilidad_fiscal: Decimal, ingresos_nominales: Decimal, anticipos: Decimal = CERO,
    modo: ModoFactor = MODO_FACTOR_DEFAULT,
) -> Decimal:
    """Art. 14 fr. I: (utilidad fiscal + anticipos Art. 94 fr. II) ÷ ingresos nominales."""
    numerador = utilidad_fiscal + anticipos
    if ingresos_nominales <= 0 or numerador <= 0:
        return Decimal("0.0000")
    return cortar_diezmilesimo(numerador / ingresos_nominales, modo)


# ── pérdidas (Art. 57) ──


@dataclass(frozen=True)
class PerdidaPendiente:
    """Pérdida por amortizar. `actualizada_a` None = monto histórico, nunca actualizado."""

    ejercicio: int
    remanente: Decimal
    actualizada_a: Mes | None = None


@dataclass
class PerdidaAplicada:
    ejercicio: int
    remanente_inicial: Decimal
    factores: list[FactorINPC]
    actualizada: Decimal
    actualizada_a: str
    aplicada: Decimal = CERO
    remanente_final: Decimal = CERO
    vigente: bool = True
    nota: str = ""

    @property
    def fuentes_por_confirmar(self) -> tuple[str, ...]:
        return unicas([x for f in self.factores for x in f.fuentes_por_confirmar])


def actualizar_perdida(
    p: PerdidaPendiente, anio: int, hasta: Mes | None, modo: ModoFactor
) -> PerdidaAplicada:
    """Actualiza la pérdida (Art. 57) hasta `hasta`; None = sólo la primera actualización."""
    if anio - p.ejercicio > ANIOS_PERDIDA or p.ejercicio >= anio:
        motivo = ("más de diez ejercicios: ya no se puede disminuir (Art. 57)"
                  if p.ejercicio < anio else "no es de un ejercicio anterior")
        return PerdidaAplicada(p.ejercicio, p.remanente, [], CERO, "", vigente=False,
                               nota=f"Pérdida de {p.ejercicio}: {motivo}.")
    monto, factores = p.remanente, []
    ultimo = p.actualizada_a
    if ultimo is None:
        f = factor_inpc((p.ejercicio, 12), (p.ejercicio, 7), modo)
        factores.append(f)
        monto, ultimo = redondear(monto * f.factor), (p.ejercicio, 12)
    if hasta is not None and hasta > ultimo:
        f = factor_inpc(hasta, ultimo, modo)
        factores.append(f)
        monto, ultimo = redondear(monto * f.factor), hasta
    return PerdidaAplicada(p.ejercicio, p.remanente, factores, monto, mes_txt(ultimo))


def aplicar_perdidas(
    perdidas: list[PerdidaPendiente], anio: int, hasta: Mes | None, base: Decimal,
    modo: ModoFactor,
) -> tuple[Decimal, list[PerdidaAplicada]]:
    """Actualiza y disminuye las pérdidas de la más antigua a la más reciente, hasta la base."""
    disponible, total, detalle = ceros(base), CERO, []
    for p in sorted(perdidas, key=lambda x: x.ejercicio):
        a = actualizar_perdida(p, anio, hasta, modo)
        if a.vigente:
            a.aplicada = min(a.actualizada, disponible)
            a.remanente_final = a.actualizada - a.aplicada
            disponible -= a.aplicada
            total += a.aplicada
        detalle.append(a)
    return total, detalle
