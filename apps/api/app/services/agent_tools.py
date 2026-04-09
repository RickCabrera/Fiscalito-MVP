"""
Definicion y ejecucion de las tools del agente de pre-declaraciones.

Tres tools:
  1. leer_perfil_contribuyente  — RFC, regimen, tipo, obligaciones
  2. obtener_predeclaraciones   — historial de declaraciones existentes
  3. crear_predeclaracion       — calcula una nueva pre-declaracion con el motor fiscal

Cada tool recibe el input del LLM + el contexto del request original (stateless).
"""

from __future__ import annotations
import json
import logging

from app.schemas.fiscal import PerfilContribuyente, CFDI
from app.schemas.agente import DeclaracionHistorialItem
from app.fiscal_engine.calculadora import calcular_declaracion
from app.constants import NOMBRES_MESES, NOMBRES_BIMESTRES, NOMBRES_REGIMEN

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Definiciones de tools (formato Anthropic)
# ─────────────────────────────────────────────────────────────

TOOLS_ANTHROPIC = [
    {
        "name": "leer_perfil_contribuyente",
        "description": (
            "Lee y resume el perfil fiscal del contribuyente: RFC, regimen, "
            "tipo de contribuyente, periodicidad de declaracion y obligaciones fiscales clave. "
            "Usa esta tool primero para entender quien es el contribuyente y qué reglas aplican."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "obtener_predeclaraciones",
        "description": (
            "Obtiene el historial de pre-declaraciones ya calculadas del contribuyente. "
            "Puedes filtrar por año y/o mes para encontrar declaraciones especificas. "
            "Usa esta tool para saber si ya existe una declaracion del periodo solicitado "
            "o para mostrar el historial reciente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo_year": {
                    "type": "integer",
                    "description": "Filtrar por año (ej: 2026). Opcional.",
                },
                "periodo_month": {
                    "type": "integer",
                    "description": "Filtrar por mes (1-12). Opcional.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "crear_predeclaracion",
        "description": (
            "Calcula una nueva pre-declaracion ISR/IVA usando el motor fiscal determinístico. "
            "Usa las facturas CFDI del request para el periodo indicado. "
            "Llama a esta tool cuando el usuario quiera saber cuánto tiene que pagar "
            "o necesite un calculo nuevo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo_year": {
                    "type": "integer",
                    "description": "Año del periodo a declarar (ej: 2026)",
                },
                "periodo_month": {
                    "type": "integer",
                    "description": "Mes del periodo (1-12). Obligatorio para declaracion mensual.",
                },
                "periodo_bimestre": {
                    "type": "integer",
                    "description": "Bimestre (1-6). Solo si el contribuyente declara bimestralmente.",
                },
                "pagos_provisionales_anteriores": {
                    "type": "number",
                    "description": "ISR ya pagado en meses anteriores del mismo ejercicio. Solo para regimenes 612 y 606.",
                    "default": 0,
                },
            },
            "required": ["periodo_year"],
        },
    },
]

# Conversion a formato OpenAI
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS_ANTHROPIC
]


# ─────────────────────────────────────────────────────────────
# Contexto del request (pasado a cada handler)
# ─────────────────────────────────────────────────────────────

class RequestContext:
    """Contenedor del contexto stateless del request original."""

    def __init__(
        self,
        contribuyente: PerfilContribuyente,
        facturas: list[CFDI],
        historial: list[DeclaracionHistorialItem],
        periodo_year: int,
        periodo_month: int | None,
    ) -> None:
        self.contribuyente = contribuyente
        self.facturas = facturas
        self.historial = historial
        self.periodo_year = periodo_year
        self.periodo_month = periodo_month


# ─────────────────────────────────────────────────────────────
# Handlers de cada tool
# ─────────────────────────────────────────────────────────────

def _handle_leer_perfil(ctx: RequestContext, _tool_input: dict) -> str:
    """Devuelve un resumen del perfil fiscal del contribuyente."""
    c = ctx.contribuyente
    regimen_nombre = NOMBRES_REGIMEN.get(c.regimen, c.regimen)
    contributor_type = c.contributor_type.value if c.contributor_type else "no especificado"

    obligaciones = _describir_obligaciones(contributor_type, c.regimen)

    resultado = {
        "rfc": c.rfc,
        "nombre": c.nombre or "No especificado",
        "regimen_codigo": c.regimen,
        "regimen_nombre": regimen_nombre,
        "tipo_contribuyente": contributor_type,
        "tipo_persona": c.tipo_persona,
        "periodicidad_declaracion": c.periodicidad.value,
        "tiene_empleados": c.tiene_empleados,
        "retenedor_iva": c.retenedor_iva,
        "actividad_economica": c.actividad_economica or "No especificada",
        "obligaciones_clave": obligaciones,
    }
    return json.dumps(resultado, ensure_ascii=False, indent=2)


def _describir_obligaciones(contributor_type: str, regimen: str) -> list[str]:
    """Retorna las obligaciones clave segun el perfil."""
    base = []
    if regimen == "626":
        base = [
            "Declaracion mensual ISR (RESICO, tasa fija 1%-2.5%)",
            "Declaracion mensual IVA (16%)",
            "Declaracion anual en abril",
        ]
    elif regimen == "612":
        base = [
            "Pago provisional mensual ISR (tabla progresiva Art. 96)",
            "Declaracion mensual IVA",
            "Declaracion anual en abril",
        ]
    elif regimen == "606":
        base = [
            "Pago provisional mensual ISR (arrendamiento, tabla acumulativa Art. 116/106)",
            "Declaracion mensual IVA",
            "Declaracion anual en abril",
            "Opcion: deduccion ciega 35% o gastos reales",
        ]
    elif regimen == "605":
        base = [
            "Sin declaraciones mensuales (patron retiene ISR)",
            "Declaracion anual en abril para recuperar saldo a favor",
            "Posibles deducciones personales: medicos, colegiaturas, hipoteca, etc.",
        ]
    elif regimen == "625":
        base = [
            "Retenciones de ISR/IVA por plataforma (Uber, Rappi, etc.)",
            "Si ingresos < $300k anuales: retenciones como pago definitivo",
            "Si ingresos > $300k: declaracion mensual normal",
        ]

    if contributor_type == "pyme":
        base += ["DIOT mensual (proveedores)", "Retenciones de nomina a empleados"]

    return base


def _handle_obtener_predeclaraciones(ctx: RequestContext, tool_input: dict) -> str:
    """Filtra y retorna el historial de declaraciones existentes."""
    historial = ctx.historial

    filtro_year = tool_input.get("periodo_year")
    filtro_month = tool_input.get("periodo_month")

    if filtro_year:
        historial = [d for d in historial if str(filtro_year) in d.periodo]

    if filtro_month and filtro_year:
        mes_nombre = NOMBRES_MESES.get(filtro_month, "").lower()
        historial = [d for d in historial if mes_nombre in d.periodo.lower()]

    if not historial:
        return json.dumps(
            {"encontradas": 0, "declaraciones": [], "mensaje": "No hay declaraciones registradas para ese periodo."},
            ensure_ascii=False
        )

    declaraciones = [
        {
            "periodo": d.periodo,
            "tipo": d.tipo,
            "fecha_calculo": d.fecha_calculo,
            "total_a_pagar": d.total_a_pagar,
            "isr_a_pagar": d.isr_a_pagar,
            "iva_a_pagar": d.iva_a_pagar,
            "regimen": d.regimen,
        }
        for d in historial
    ]

    return json.dumps(
        {"encontradas": len(declaraciones), "declaraciones": declaraciones},
        ensure_ascii=False,
        indent=2
    )


def _handle_crear_predeclaracion(ctx: RequestContext, tool_input: dict) -> tuple[str, dict | None]:
    """
    Calcula una nueva pre-declaracion usando el motor fiscal.
    Retorna (texto_resultado, desglose_dict) para que el route pueda incluirlo en la respuesta.
    """
    periodo_year = tool_input.get("periodo_year", ctx.periodo_year)
    periodo_month = tool_input.get("periodo_month", ctx.periodo_month)
    periodo_bimestre = tool_input.get("periodo_bimestre")
    pagos_provisionales = float(tool_input.get("pagos_provisionales_anteriores", 0))

    if not ctx.facturas:
        return json.dumps(
            {"error": "No hay facturas disponibles en el request para calcular la declaracion."},
            ensure_ascii=False
        ), None

    # Determinar string del periodo
    if periodo_bimestre:
        periodo_str = f"{NOMBRES_BIMESTRES.get(periodo_bimestre, str(periodo_bimestre))} {periodo_year}"
    elif periodo_month:
        periodo_str = f"{NOMBRES_MESES.get(periodo_month, str(periodo_month))} {periodo_year}"
    else:
        periodo_str = f"Ejercicio fiscal {periodo_year}"

    desglose = calcular_declaracion(
        contribuyente=ctx.contribuyente,
        facturas=ctx.facturas,
        es_anual=(periodo_month is None and periodo_bimestre is None),
        periodo_month=periodo_month if not periodo_bimestre else None,
        pagos_provisionales_anteriores=pagos_provisionales,
    )

    regimen_nombre = NOMBRES_REGIMEN.get(ctx.contribuyente.regimen, ctx.contribuyente.regimen)

    resultado = {
        "periodo": periodo_str,
        "regimen": regimen_nombre,
        "facturas_ingreso": desglose.cantidad_facturas_ingreso,
        "facturas_egreso": desglose.cantidad_facturas_egreso,
        "total_ingresos_gravados": round(desglose.total_ingresos_gravados, 2),
        "total_deducciones": round(desglose.total_deducciones_autorizadas, 2),
        "base_isr": round(desglose.base_isr, 2),
        "tasa_isr": f"{desglose.tasa_isr:.2%}",
        "isr_causado": round(desglose.isr_causado, 2),
        "isr_retenido": round(desglose.isr_retenido, 2),
        "isr_a_pagar": round(desglose.isr_a_pagar, 2),
        "iva_cobrado": round(desglose.iva_trasladado_cobrado, 2),
        "iva_acreditable": round(desglose.iva_trasladado_pagado, 2),
        "iva_retenido": round(desglose.iva_retenido, 2),
        "iva_a_pagar": round(desglose.iva_a_pagar, 2),
        "total_a_pagar": round(desglose.total_a_pagar, 2),
    }

    if desglose.deduccion_ciega_aplicada:
        resultado["nota_arrendamiento"] = desglose.comparacion_deduccion

    if desglose.retenciones_definitivas:
        resultado["nota_plataformas"] = "Retenciones aplicadas como pago definitivo (ingresos < $300k anuales)"

    desglose_dict = desglose.model_dump()
    desglose_dict["periodo"] = periodo_str
    desglose_dict["regimen"] = regimen_nombre

    return json.dumps(resultado, ensure_ascii=False, indent=2), desglose_dict


# ─────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────

def ejecutar_tool(
    tool_name: str,
    tool_input: dict,
    ctx: RequestContext,
) -> tuple[str, dict | None]:
    """
    Ejecuta la tool indicada y retorna (resultado_str, desglose_dict_o_None).
    El desglose_dict se usa solo cuando la tool es crear_predeclaracion.
    """
    logger.info("Ejecutando tool: %s con input: %s", tool_name, tool_input)

    if tool_name == "leer_perfil_contribuyente":
        return _handle_leer_perfil(ctx, tool_input), None

    if tool_name == "obtener_predeclaraciones":
        return _handle_obtener_predeclaraciones(ctx, tool_input), None

    if tool_name == "crear_predeclaracion":
        return _handle_crear_predeclaracion(ctx, tool_input)

    return json.dumps({"error": f"Tool desconocida: {tool_name}"}), None
