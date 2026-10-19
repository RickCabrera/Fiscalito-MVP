"""
Resumen y actualización de impuestos de un cliente en un periodo (P3-02). Motor puro.

Es la tabla de la pantalla "Resumen y actualización de impuestos" (como la de Contadigital):
un renglón por impuesto, con columnas

    importe sistema | importe a pagar | actualización | recargos | subsidio | compensaciones | total

- **importe sistema**: lo que calculan los motores (`calculadora.py`, `iva.py`, la nómina en
  la bóveda). Lo arma `app/impuestos/servicio.py` y llega aquí ya calculado.
- **importe a pagar**: por default el del sistema; el contador lo puede capturar (p. ej. si
  ya pagó una parte o la declaración real difiere).
- **subsidio** (sólo retenciones de salarios) y **compensaciones**: capturables.
- **actualización y recargos**: Arts. 17-A y 21 CFF (`actualizacion.py`) sobre el NETO
  (`a pagar - subsidio - compensaciones`), desde la fecha límite hasta la fecha de pago.

DECISIÓN PROVISIONAL (P3-02): la actualización y los recargos se calculan sobre el neto
después de subsidio y compensaciones. Es la lectura del Art. 23 CFF (la compensación extingue
la contribución hasta por ese monto) y la del Art. 21 (recargos sobre "las contribuciones
omitidas" actualizadas). Si la contadora aplica la compensación después de actualizar, se
ajusta aquí (DP-3).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.actualizacion import (
    MODO_FACTOR_DEFAULT,
    TOPE_MESES_RECARGOS_DEFAULT,
    ModoFactor,
    TipoRecargo,
    ajustar_a_pesos,
    calcular_actualizacion_recargos,
)
from app.redondeo import redondear

CERO = Decimal("0.00")

# (clave, grupo, nombre) en el orden de la pantalla.
CONCEPTOS: tuple[tuple[str, str, str], ...] = (
    ("isr_pm", "ISR propio", "ISR personas morales"),
    ("isr_pf_empresarial", "ISR propio", "ISR PF actividad empresarial y profesional"),
    ("isr_arrendamiento", "ISR propio", "ISR PF arrendamiento"),
    ("isr_plataformas", "ISR propio", "ISR PF plataformas tecnológicas"),
    ("isr_resico_pf", "ISR propio", "ISR RESICO personas físicas"),
    ("isr_resico_pm", "ISR propio", "ISR RESICO personas morales"),
    ("ret_isr_salarios", "Retenciones de ISR", "ISR retenido por salarios"),
    ("ret_isr_asimilados", "Retenciones de ISR", "ISR retenido por asimilados a salarios"),
    ("ret_isr_honorarios", "Retenciones de ISR", "ISR retenido por servicios profesionales"),
    ("ret_isr_arrendamiento", "Retenciones de ISR", "ISR retenido por arrendamiento"),
    ("ret_isr_resico", "Retenciones de ISR", "ISR retenido a RESICO (1.25 %)"),
    ("iva_a_cargo", "IVA", "IVA a cargo"),
    ("iva_retenido", "IVA", "IVA retenido a terceros"),
)
CLAVES = {c[0] for c in CONCEPTOS}


@dataclass(frozen=True)
class ImporteSistema:
    """Lo que un motor calculó para un concepto, con su nota (o por qué está en cero)."""

    clave: str
    importe: Decimal
    nota: str = ""
    aplica: bool = True


@dataclass(frozen=True)
class Captura:
    """Lo que el contador captura en un renglón."""

    importe_a_pagar: Decimal | None = None
    subsidio: Decimal = CERO
    compensaciones: Decimal = CERO


@dataclass(frozen=True)
class OpcionesResumen:
    """Criterios del despacho para el cálculo de accesorios (DP-3)."""

    modo_factor: ModoFactor = MODO_FACTOR_DEFAULT
    tipo_recargo: TipoRecargo = "mora"
    tope_meses: int = TOPE_MESES_RECARGOS_DEFAULT


@dataclass
class RenglonResumen:
    """Un renglón de la tabla."""

    clave: str
    grupo: str
    concepto: str
    aplica: bool
    importe_sistema: Decimal
    importe_a_pagar: Decimal
    capturado: bool
    actualizacion: Decimal
    recargos: Decimal
    subsidio: Decimal
    compensaciones: Decimal
    total: Decimal
    nota: str = ""
    factor: str = ""
    meses_recargo: int = 0
    fuentes_por_confirmar: tuple[str, ...] = ()


@dataclass
class ResumenImpuestos:
    """La tabla completa y sus totales."""

    anio: int
    mes: int
    fecha_limite: date
    fecha_pago: date
    renglones: list[RenglonResumen]
    totales: dict[str, Decimal] = field(default_factory=dict)
    total_a_pagar_ajustado: Decimal = CERO
    notas: list[str] = field(default_factory=list)
    fuentes_por_confirmar: list[str] = field(default_factory=list)


def armar_resumen(
    anio: int,
    mes: int,
    fecha_limite: date,
    fecha_pago: date,
    importes: Iterable[ImporteSistema],
    capturas: dict[str, Captura] | None = None,
    opciones: OpcionesResumen | None = None,
) -> ResumenImpuestos:
    """Arma la tabla. Redondeo por renglón a centavos (ROUND_HALF_UP); total ajustado a pesos."""
    capturas = capturas or {}
    opciones = opciones or OpcionesResumen()
    desconocidas = set(capturas) - CLAVES
    if desconocidas:
        raise FiscalValidationError(f"Conceptos desconocidos en capturas: {sorted(desconocidas)}")
    por_clave = {i.clave: i for i in importes}
    renglones: list[RenglonResumen] = []
    for clave, grupo, nombre in CONCEPTOS:
        sistema = por_clave.get(clave, ImporteSistema(clave, CERO, "", aplica=False))
        cap = capturas.get(clave, Captura())
        if min(cap.subsidio, cap.compensaciones) < 0 or (
            cap.importe_a_pagar is not None and cap.importe_a_pagar < 0
        ):
            raise FiscalValidationError(f"Importes capturados negativos en {clave}.")
        if cap.subsidio and clave != "ret_isr_salarios":
            raise FiscalValidationError("El subsidio para el empleo sólo se acredita contra "
                                        "el ISR retenido por salarios.")
        a_pagar = redondear(cap.importe_a_pagar if cap.importe_a_pagar is not None
                            else max(sistema.importe, CERO))
        subsidio, comp = redondear(cap.subsidio), redondear(cap.compensaciones)
        neto = max(a_pagar - subsidio - comp, CERO)
        acc = calcular_actualizacion_recargos(
            neto, fecha_limite, fecha_pago, tipo_recargo=opciones.tipo_recargo,
            modo_factor=opciones.modo_factor, tope_meses=opciones.tope_meses,
        )
        renglones.append(RenglonResumen(
            clave=clave, grupo=grupo, concepto=nombre, aplica=sistema.aplica,
            importe_sistema=redondear(sistema.importe), importe_a_pagar=a_pagar,
            capturado=cap.importe_a_pagar is not None, actualizacion=acc.actualizacion,
            recargos=acc.recargos, subsidio=subsidio, compensaciones=comp,
            total=acc.total, nota=sistema.nota,
            factor=str(acc.factor.factor) if acc.factor else "",
            meses_recargo=acc.meses, fuentes_por_confirmar=acc.fuentes_por_confirmar,
        ))
    totales = {
        k: sum((getattr(r, k) for r in renglones), CERO)
        for k in ("importe_sistema", "importe_a_pagar", "actualizacion", "recargos",
                  "subsidio", "compensaciones", "total")
    }
    notas = []
    if fecha_pago > fecha_limite:
        notas.append(f"Pago posterior a la fecha límite ({fecha_limite.isoformat()}): se "
                     f"calculan actualización (Art. 17-A CFF) y recargos (Art. 21 CFF).")
    # O12: el INPC o la tasa de recargos de fuente secundaria se dice en la respuesta.
    fuentes = list(dict.fromkeys(f for r in renglones for f in r.fuentes_por_confirmar))
    if fuentes:
        notas.append("La actualización o los recargos usan índices o tasas de fuente "
                     "secundaria (FUENTE POR CONFIRMAR): " + "; ".join(fuentes) + ".")
    return ResumenImpuestos(
        anio=anio, mes=mes, fecha_limite=fecha_limite, fecha_pago=fecha_pago,
        renglones=renglones, totales=totales,
        total_a_pagar_ajustado=ajustar_a_pesos(totales["total"]), notas=notas,
        fuentes_por_confirmar=fuentes,
    )


def resumen_dict(r: ResumenImpuestos) -> dict[str, object]:
    """Serialización para la API."""
    def fila(x: RenglonResumen) -> dict[str, object]:
        return {
            "clave": x.clave, "grupo": x.grupo, "concepto": x.concepto, "aplica": x.aplica,
            **{k: f"{getattr(x, k):.2f}" for k in (
                "importe_sistema", "importe_a_pagar", "actualizacion", "recargos",
                "subsidio", "compensaciones", "total")},
            "capturado": x.capturado, "nota": x.nota, "factor": x.factor,
            "meses_recargo": x.meses_recargo,
            "por_confirmar": bool(x.fuentes_por_confirmar),
        }
    return {
        "anio": r.anio, "mes": r.mes, "fecha_limite": r.fecha_limite.isoformat(),
        "fecha_pago": r.fecha_pago.isoformat(),
        "renglones": [fila(x) for x in r.renglones],
        "totales": {k: f"{v:.2f}" for k, v in r.totales.items()},
        "total_a_pagar_ajustado": f"{r.total_a_pagar_ajustado:.2f}",
        "notas": r.notas,
        "por_confirmar": bool(r.fuentes_por_confirmar),
        "fuentes_por_confirmar": r.fuentes_por_confirmar,
    }
