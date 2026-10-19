"""
Motor de personas morales: régimen general (601) y RESICO de personas morales (P3-01). Puro.

No lee la base: recibe importes ya sumados (los arma `app/impuestos/personas_morales.py` desde
la bóveda, la contabilidad P2 y los datos capturados) y devuelve cada paso del cálculo para
que el contador lo pueda rehacer a mano y los papeles de trabajo (P3-06) lo copien tal cual.

FUENTES (LISR vigente, texto de la Cámara de Diputados; ver `knowledge_base/16_personas_morales.md`)
---------------------------------------------------------------------------------------------
- **Art. 9** — tasa del 30 % sobre el resultado fiscal. Fr. I: utilidad fiscal = ingresos
  acumulables − deducciones autorizadas − PTU pagada en el ejercicio. Fr. II: a la utilidad
  fiscal se le restan las pérdidas pendientes de ejercicios anteriores. Cuarto párrafo: la
  renta gravable para la PTU no disminuye la PTU pagada ni las pérdidas pendientes, y SÍ
  disminuye de los ingresos acumulables las cantidades no deducibles por el Art. 28 fr. XXX
  (`EntradaAnual.no_deducibles_art28_xxx`, ver `pm_anual.py`). Último párrafo: la anual se
  presenta dentro de los tres meses siguientes al cierre (marzo).
- **Art. 14** — pagos provisionales mensuales (día 17 del mes siguiente):
  - fr. I: coeficiente de utilidad = utilidad fiscal del último ejercicio de doce meses (más los
    anticipos y rendimientos del Art. 94 fr. II, cooperativas) entre sus ingresos nominales. Si
    ese ejercicio no dio coeficiente (pérdida), se usa el del último que lo tenga, sin que sea
    anterior en más de cinco años. El artículo NO actualiza el coeficiente.
  - fr. II: utilidad estimada = coeficiente × ingresos nominales del inicio del ejercicio al
    último día del mes; se disminuye la PTU pagada en el ejercicio **en partes iguales en los
    pagos de mayo a diciembre** (acumulativa, sin exceder la utilidad) y las pérdidas
    pendientes. Ingresos nominales = ingresos acumulables sin el ajuste anual por inflación
    acumulable.
  - fr. III: tasa del Art. 9 y se acreditan los pagos provisionales anteriores del ejercicio y
    las retenciones del Art. 54 (intereses pagados por el sistema financiero).
- **Arts. 44-46** — ajuste anual por inflación: saldo promedio anual de créditos y de deudas
  (suma de saldos al último día de cada mes ÷ meses del ejercicio); si deudas > créditos el
  ajuste es acumulable y si créditos > deudas es deducible; factor de ajuste anual = INPC del
  último mes del ejercicio ÷ INPC del último mes del ejercicio anterior − 1.
- **Art. 57** — pérdidas: se disminuyen en los diez ejercicios siguientes; primera
  actualización de julio a diciembre del ejercicio en que ocurrió; las siguientes desde el
  mes de la última actualización hasta el último mes de la primera mitad (junio) del ejercicio
  en que se aplican. Pérdida = deducciones − ingresos, aumentada con la PTU pagada.
- **Arts. 206-215 (Título VII, Cap. XII, RESICO PM)** — 207 ingresos efectivamente
  percibidos; 208 deducciones; 209 inversiones; 210 requisitos (efectivamente erogadas);
  **211 pagos provisionales**: ingresos percibidos − deducciones erogadas − PTU pagada en el
  ejercicio − pérdidas, por la tasa del Art. 9, menos pagos anteriores y retenciones del 54;
  **212 anual** conforme al Art. 9 con esos mismos flujos.
- **Art. 17-A CFF último párrafo** — factores y proporciones "hasta el diezmilésimo": se usa
  para el coeficiente de utilidad, los factores de actualización y el factor de ajuste anual,
  con el criterio de corte del cliente (`ModoFactor`, DP-3; default truncar, FUENTE POR
  CONFIRMAR, ver `actualizacion.py`).

CRITERIOS QUE NO DICE LA LEY (DECISIONES, todas señaladas en `notas`)
---------------------------------------------------------------------
- Pérdidas en pagos provisionales: en enero-junio se aplican con su última actualización y
  desde julio actualizadas a junio (el INPC de junio aún no existe en la primera mitad).
  DECISIÓN PROVISIONAL (la más conservadora: no se adelanta una actualización).
  FUENTE POR CONFIRMAR.
- PTU pagada después de mayo: la fracción acumulada de mayo a diciembre se empieza a disminuir
  en el pago del mes en que se pagó (no antes de pagarla). DECISIÓN PROVISIONAL.
- RESICO PM: los Arts. 206-215 no remiten al Art. 44; no se calcula ajuste anual por inflación
  salvo que el despacho lo pida (`aai_en_resico`). FUENTE POR CONFIRMAR.
- PTU a repartir: 10 % de la renta gravable — `FUNDAMENTO_PTU` (Resolución de la Sexta
  Comisión Nacional para la PTU, DOF 18-sep-2020; ver `pm_anual.py`).

FUENTES POR CONFIRMAR EN LA RESPUESTA (O12)
-------------------------------------------
Todo factor INPC (pérdidas, ajuste anual por inflación) lleva `fuentes_por_confirmar` con los
índices que no se cotejaron contra el boletín del INEGI; los resultados los juntan y la
serialización los expone como `por_confirmar`.

MÓDULOS (O11)
-------------
`pm_perdidas.py` (factores, coeficiente, pérdidas), `pm_provisionales.py` (Arts. 14 y 211),
`pm_anual.py` (Arts. 44-46, 9 y 212, PTU). Este módulo los reexporta (la API pública no
cambió) y serializa para la API.
"""

from __future__ import annotations

from decimal import Decimal

from app.fiscal_engine.pm_anual import (
    FUNDAMENTO_PTU,
    PORCENTAJE_PTU,
    EntradaAnual,
    Renglon,
    ResultadoAAI,
    ResultadoAnualPM,
    ajuste_anual_inflacion,
    ajuste_por_promedios,
    anual_pm,
)
from app.fiscal_engine.pm_perdidas import (
    ANIOS_COEFICIENTE,
    ANIOS_PERDIDA,
    CERO,
    UNO,
    FactorINPC,
    Mes,
    PerdidaAplicada,
    PerdidaPendiente,
    actualizar_perdida,
    aplicar_perdidas,
    coeficiente_utilidad,
    factor_inpc,
)
from app.fiscal_engine.pm_provisionales import (
    MESES_PTU,
    PRIMER_MES_PTU,
    TASA_ISR_PM,
    EntradaProvisionales,
    Estimulo,
    PagoProvisionalPM,
    pagos_provisionales_pm,
    pagos_provisionales_resico_pm,
    ptu_disminuible_provisional,
)

__all__ = [
    "ANIOS_COEFICIENTE", "ANIOS_PERDIDA", "CERO", "FUNDAMENTO_PTU", "MESES_PTU",
    "PORCENTAJE_PTU", "PRIMER_MES_PTU", "TASA_ISR_PM", "UNO", "EntradaAnual",
    "EntradaProvisionales", "Estimulo", "FactorINPC", "Mes", "PagoProvisionalPM",
    "PerdidaAplicada", "PerdidaPendiente", "Renglon", "ResultadoAAI", "ResultadoAnualPM",
    "aai_dict", "actualizar_perdida", "ajuste_anual_inflacion", "ajuste_por_promedios",
    "anual_pm", "aplicar_perdidas", "coeficiente_utilidad", "factor_dict", "factor_inpc",
    "pago_dict", "pagos_provisionales_pm", "pagos_provisionales_resico_pm", "perdida_dict",
    "ptu_disminuible_provisional", "renglon_dict",
]


# ── serialización ──


def _t(v: Decimal) -> str:
    return f"{v:.2f}"


def factor_dict(f: FactorINPC) -> dict[str, object]:
    return {"factor": f"{f.factor:.4f}", "inpc_reciente": str(f.inpc_reciente),
            "mes_reciente": f.mes_reciente, "inpc_antiguo": str(f.inpc_antiguo),
            "mes_antiguo": f.mes_antiguo, "uso_ultimo_publicado": f.uso_ultimo_publicado,
            "por_confirmar": bool(f.fuentes_por_confirmar),
            "fuentes_por_confirmar": list(f.fuentes_por_confirmar)}


def pago_dict(p: PagoProvisionalPM) -> dict[str, object]:
    return {
        "mes": p.mes, "ingresos_mes": _t(p.ingresos_mes),
        "ingresos_acumulados": _t(p.ingresos_acumulados),
        "deducciones_acumuladas": _t(p.deducciones_acumuladas),
        "coeficiente": f"{p.coeficiente:.4f}", "utilidad_estimada": _t(p.utilidad_estimada),
        "ptu_disminuida": _t(p.ptu_disminuida), "estimulos": _t(p.estimulos),
        "perdidas": _t(p.perdidas), "base": _t(p.base), "isr_causado": _t(p.isr_causado),
        "pagos_anteriores": _t(p.pagos_anteriores), "retenciones": _t(p.retenciones),
        "pago_determinado": _t(p.pago_determinado), "pago_efectuado": _t(p.pago_efectuado),
        "pago_capturado": p.pago_capturado, "a_pagar_pesos": _t(p.a_pagar_pesos),
        "por_confirmar": bool(p.fuentes_por_confirmar),
    }


def perdida_dict(p: PerdidaAplicada) -> dict[str, object]:
    return {"ejercicio": p.ejercicio, "remanente_inicial": _t(p.remanente_inicial),
            "factores": [factor_dict(f) for f in p.factores], "actualizada": _t(p.actualizada),
            "actualizada_a": p.actualizada_a, "aplicada": _t(p.aplicada),
            "remanente_final": _t(p.remanente_final), "vigente": p.vigente, "nota": p.nota}


def aai_dict(a: ResultadoAAI) -> dict[str, object]:
    return {
        "saldos_creditos": [_t(x) for x in a.saldos_creditos],
        "saldos_deudas": [_t(x) for x in a.saldos_deudas],
        "promedio_creditos": _t(a.promedio_creditos), "promedio_deudas": _t(a.promedio_deudas),
        "factor": factor_dict(a.factor) if a.factor else None,
        "factor_ajuste": f"{a.factor_ajuste:.4f}", "acumulable": _t(a.acumulable),
        "deducible": _t(a.deducible), "notas": a.notas,
    }


def renglon_dict(r: Renglon) -> dict[str, str]:
    return {"clave": r.clave, "concepto": r.concepto, "importe": _t(r.importe),
            "fundamento": r.fundamento}
