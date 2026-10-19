"""
Impuesto sobre nóminas (ISN) por entidad federativa (P3-07).

QUÉ ES
------
Impuesto ESTATAL sobre las erogaciones por remuneraciones al trabajo personal subordinado
que se presta en el territorio del estado. Cada estado fija su objeto, base, tasa y
exenciones en su propia ley; no hay una ley federal. Se paga mensual, casi siempre a más
tardar el día 17 del mes siguiente (Veracruz: Código Financiero art. 102).

LA TABLA
--------
`datos/isn.csv`: una fila por entidad (clave `c_Estado` del SAT) y vigencia, con
`verificacion`:

- `ley_citada`: tasa y artículo de la ley estatal identificados (texto de la ley consultado o
  tabla que cita el artículo con su ley de ingresos 2026).
- `secundaria`: la tasa coincide en dos tablas secundarias 2025-2026, pero el artículo de la
  ley estatal NO se consultó. Columna `fundamento` = "FUENTE POR CONFIRMAR: ...".

VERACRUZ (verificado — "Listo cuando" de P3-07)
------------------------------------------------
Código Financiero para el Estado de Veracruz de Ignacio de la Llave:
- Art. 98: objeto — erogaciones en efectivo o en especie por remuneraciones al trabajo
  personal subordinado prestado en el Estado (sueldos, gratificaciones, primas, comisiones,
  prestaciones en especie, honorarios a administradores, etc.).
- Art. 100: base — el monto total de las erogaciones del art. 98.
- Art. 101: "Este impuesto se causará, liquidará y pagará aplicando la tasa del 3% sobre la
  base que señala el artículo anterior." (Congreso de Veracruz: se mantiene en 3 % para 2026.)
- Art. 103: exenciones (despensa, indemnizaciones por separación, PTU, horas extra dentro de
  límites, aportaciones de seguridad social, premios de asistencia y puntualidad ANUALES
  —inciso n)—, etc.). Los premios por periodo (lo usual) gravan.
- Arts. 134-135: impuesto adicional para el fomento de la educación, "a razón del 15% sobre
  su base", que es "el importe de los pagos por concepto de impuestos y derechos estatales";
  se liquida junto con el impuesto sobre el que recae. Por eso el ISN de Veracruz se presenta
  como "3% (+) 15% sobre tasa". Es **configurable por cliente** (`aplicar_adicional`, default
  sí): si el despacho lo entera aparte, lo apaga.

BASE GRAVABLE (configurable por cliente, DP-3)
----------------------------------------------
Default conservador: TODAS las percepciones gravan (ISN de más es multa evitada; de menos es
crédito fiscal). Se excluyen sólo las claves `c_TipoPercepcion` que la ley local exenta Y que
están documentadas aquí con su fundamento (`EXCLUSIONES_DOCUMENTADAS`). El despacho puede
añadir o quitar claves por cliente (`claves_excluidas_extra`, `claves_incluidas_forzadas`).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from app.exceptions import FiscalValidationError
from app.redondeo import redondear

ARCHIVO_ISN = Path(__file__).parent / "datos" / "isn.csv"

# Claves c_TipoPercepcion (catálogo del complemento de nómina 1.2, tests/xsd/catNomina.xsd)
# que la ley del estado exenta, con su fundamento. Sólo las verificadas contra el texto.
EXCLUSIONES_DOCUMENTADAS: dict[str, dict[str, str]] = {
    "VER": {
        "003": "PTU — Código Financiero de Veracruz art. 103 fr. I inciso g)",
        "022": "Prima por antigüedad (separación) — art. 103 fr. I inciso b)",
        "023": "Pagos por separación — art. 103 fr. I inciso b)",
        "025": "Indemnizaciones — art. 103 fr. I inciso b)",
        "039": "Jubilaciones, pensiones o haberes de retiro — art. 103 fr. I inciso d)",
        "044": "Jubilaciones en parcialidades — art. 103 fr. I inciso d)",
        "029": "Vales de despensa — art. 103 fr. I incisos a) y m)",
        "026": "Reembolso por funeral — art. 103 fr. I inciso k)",
        "037": "Ayuda para gastos de funeral — art. 103 fr. I inciso k)",
    },
}
# Fuera A PROPÓSITO (exenciones condicionales que el CFDI no deja comprobar; excluirlas sin
# comprobar baja el impuesto): fondo de ahorro (inciso l, con requisitos), alimentación y
# habitación (inciso j, sólo si son gratuitas), cuotas de seguridad social (inciso h, sólo
# las aportaciones patronales). El despacho las excluye por cliente si le constan.
# Premios de puntualidad (010) y asistencia (049) en Veracruz: el art. 103 fr. I inciso n)
# sólo exenta los premios de asistencia y puntualidad que se paguen en forma ANUAL. El CFDI de
# nómina no dice si el premio es anual (casi siempre se paga por periodo) → se GRAVAN. Si al
# despacho le consta que el cliente los paga una vez al año, los excluye por cliente con
# `claves_excluidas_extra` = {"010", "049"} (`isn_claves_excluidas` en la configuración).
# Horas extra (019) en Veracruz: exentas sólo dentro de 3 horas diarias y 3 veces por semana
# (art. 103 fr. I inciso i). El CFDI no trae las horas → se GRAVAN (conservador) salvo que
# el despacho las excluya por cliente.


@dataclass(frozen=True)
class TasaISN:
    """La tasa vigente de una entidad, con su fuente."""

    entidad: str
    nombre: str
    vigencia_desde: date
    tasa: Decimal
    adicional_sobre_impuesto: Decimal
    verificacion: str
    fundamento: str
    fuente: str
    notas: str

    @property
    def por_confirmar(self) -> bool:
        """True si el artículo de la ley estatal no se consultó."""
        return self.verificacion != "ley_citada"


@lru_cache(maxsize=1)
def tabla_isn() -> dict[str, tuple[TasaISN, ...]]:
    """Tasas por entidad (puede haber varias vigencias), leídas de `datos/isn.csv`."""
    salida: dict[str, list[TasaISN]] = {}
    with ARCHIVO_ISN.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            t = TasaISN(
                entidad=fila["entidad"], nombre=fila["nombre"],
                vigencia_desde=date.fromisoformat(fila["vigencia_desde"]),
                tasa=Decimal(fila["tasa"]),
                adicional_sobre_impuesto=Decimal(fila["adicional_sobre_impuesto"] or "0"),
                verificacion=fila["verificacion"], fundamento=fila["fundamento"],
                fuente=fila["fuente"], notas=fila["notas"],
            )
            salida.setdefault(t.entidad, []).append(t)
    return {k: tuple(sorted(v, key=lambda x: x.vigencia_desde)) for k, v in salida.items()}


def _normalizar(entidad: str) -> str:
    e = entidad.strip().upper()
    return "CMX" if e == "DIF" else e


def tasa_vigente(entidad: str, fecha: date) -> TasaISN:
    """La tasa de `entidad` vigente en `fecha`. 422 si no hay."""
    clave = _normalizar(entidad)
    vigencias = tabla_isn().get(clave)
    if not vigencias:
        raise FiscalValidationError(
            f"No hay tasa de ISN cargada para la entidad {entidad!r}. Captura la entidad del "
            f"cliente (catálogo c_Estado) en su ficha."
        )
    aplicables = [v for v in vigencias if v.vigencia_desde <= fecha]
    if not aplicables:
        raise FiscalValidationError(
            f"No hay tasa de ISN de {clave} vigente al {fecha.isoformat()}; la primera "
            f"cargada rige desde {vigencias[0].vigencia_desde.isoformat()}."
        )
    return aplicables[-1]


@dataclass(frozen=True)
class ConfigISN:
    """Criterio del despacho por cliente (DP-3). Defaults documentados en el docstring."""

    aplicar_adicional: bool = True
    claves_excluidas_extra: frozenset[str] = frozenset()
    claves_incluidas_forzadas: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PercepcionISN:
    """Una percepción pagada en el periodo (clave c_TipoPercepcion e importe total)."""

    clave: str
    importe: Decimal
    descripcion: str = ""


@dataclass(frozen=True)
class ResultadoISN:
    """ISN del periodo con el desglose."""

    entidad: str
    tasa: TasaISN
    total_erogaciones: Decimal
    excluido: Decimal
    base: Decimal
    impuesto: Decimal
    adicional: Decimal
    total: Decimal
    detalle_exclusiones: tuple[dict[str, str], ...] = field(default_factory=tuple)
    notas: tuple[str, ...] = field(default_factory=tuple)


def calcular_isn(
    entidad: str,
    fecha: date,
    percepciones: Iterable[PercepcionISN],
    config: ConfigISN | None = None,
) -> ResultadoISN:
    """
    ISN del periodo: base = erogaciones - exclusiones; impuesto = base × tasa; adicional =
    impuesto × adicional (si aplica). Redondeo a centavos ROUND_HALF_UP en impuesto y
    adicional por separado (cada uno es un concepto que se declara).
    """
    config = config or ConfigISN()
    tasa = tasa_vigente(entidad, fecha)
    documentadas = EXCLUSIONES_DOCUMENTADAS.get(tasa.entidad, {})
    total = Decimal("0")
    excluido = Decimal("0")
    detalle: list[dict[str, str]] = []
    for p in percepciones:
        if p.importe < 0:
            raise FiscalValidationError(f"Importe negativo en la percepción {p.clave}.")
        total += p.importe
        if p.clave in config.claves_incluidas_forzadas:
            continue
        motivo = documentadas.get(p.clave)
        if motivo is None and p.clave in config.claves_excluidas_extra:
            motivo = "Excluida por criterio del despacho (configuración del cliente)"
        if motivo:
            excluido += p.importe
            detalle.append({"clave": p.clave, "importe": f"{p.importe:.2f}", "motivo": motivo})
    base = redondear(total - excluido)
    impuesto = redondear(base * tasa.tasa)
    adicional = (
        redondear(impuesto * tasa.adicional_sobre_impuesto) if config.aplicar_adicional
        else Decimal("0.00")
    )
    notas = []
    if tasa.por_confirmar:
        notas.append(f"Tasa de {tasa.nombre} con FUENTE POR CONFIRMAR: {tasa.fundamento}")
    if tasa.adicional_sobre_impuesto and not config.aplicar_adicional:
        notas.append("El adicional estatal se omitió por configuración del cliente.")
    if not documentadas:
        notas.append(
            f"No hay exenciones documentadas para {tasa.nombre}: todas las percepciones "
            f"integran la base (criterio conservador)."
        )
    return ResultadoISN(
        entidad=tasa.entidad, tasa=tasa, total_erogaciones=redondear(total),
        excluido=redondear(excluido), base=base, impuesto=impuesto, adicional=adicional,
        total=impuesto + adicional, detalle_exclusiones=tuple(detalle), notas=tuple(notas),
    )


def resultado_isn_dict(r: ResultadoISN) -> dict[str, object]:
    """Serialización para la API."""
    t = r.tasa
    return {
        "entidad": r.entidad, "nombre_entidad": t.nombre,
        "tasa": str(t.tasa), "adicional_sobre_impuesto": str(t.adicional_sobre_impuesto),
        "vigencia_desde": t.vigencia_desde.isoformat(),
        "verificacion": t.verificacion, "por_confirmar": t.por_confirmar,
        "fundamento": t.fundamento, "fuente": t.fuente,
        "total_erogaciones": f"{r.total_erogaciones:.2f}", "excluido": f"{r.excluido:.2f}",
        "base": f"{r.base:.2f}", "impuesto": f"{r.impuesto:.2f}",
        "adicional": f"{r.adicional:.2f}", "total": f"{r.total:.2f}",
        "detalle_exclusiones": list(r.detalle_exclusiones), "notas": list(r.notas),
    }


def catalogo_isn(fecha: date) -> list[dict[str, object]]:
    """Las 32 entidades con su tasa vigente en `fecha`, para la pantalla."""
    salida = []
    for clave in sorted(tabla_isn()):
        try:
            t = tasa_vigente(clave, fecha)
        except FiscalValidationError:
            continue
        salida.append({
            "entidad": t.entidad, "nombre": t.nombre, "tasa": str(t.tasa),
            "adicional_sobre_impuesto": str(t.adicional_sobre_impuesto),
            "por_confirmar": t.por_confirmar, "fundamento": t.fundamento,
        })
    return salida
