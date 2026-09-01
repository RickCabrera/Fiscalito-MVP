"""
Tool de nómina del agente (D-06). **Demo-only.**

Vive aparte de `agent_tools.py` porque ese archivo ya está en 348 líneas y el
límite de la casa son 300: meterle esto profundiza una violación existente.
`agent_tools.py` sólo lo engancha.

POR QUE LEE EL ALMACEN DE ASISTENCIA
------------------------------------
El chat de texto no puede mandar nueve sueldos ni el cierre del periodo. Para
que "¿cuánto pago de IMSS este mes?" funcione, la tool arma el cálculo con lo
que hay en memoria: `PLANTILLA_DEMO` más las incidencias que salen de
`cerrar_periodo`. Es el mismo `almacen` que `apps/api/CLAUDE.md` declara como
ruptura consciente y acotada del stateless.

SIN EVENTOS SE RESPONDE ERROR, NO UNA NOMINA
--------------------------------------------
Con el almacén vacío `cerrar_periodo` marca **todos** los días laborables como
falta y el motor devuelve una nómina perfectamente válida y completamente
falsa, que el agente afirmaría en el chat como un hecho. Por eso el caso de
cero eventos se corta antes de calcular.
"""

from __future__ import annotations

import json
from datetime import date

from app.asistencia.almacen import almacen
from app.asistencia.incidencias import cerrar_periodo
from app.constants import CLIENTE_DEMO
from app.demo_nomina import CLAVE_PERIODICIDAD_DEMO, PLANTILLA_DEMO, PRIMA_RIESGO_DEMO
from app.exceptions import FiscalAgentError
from app.nomina_engine.periodo import IncidenciasPeriodo, calcular_periodo
from app.schemas.asistencia import Periodo

TOOL_NOMINA_PERIODO = {
    "name": "calcular_nomina_periodo",
    "description": (
        "Calcula la nomina de un periodo del cliente de demostracion a partir de las "
        "checadas del reloj biometrico que hay en memoria: recibos por empleado (sueldo, "
        "ISR, subsidio, cuota obrera, neto) y cuotas patronales del IMSS por ramo. "
        "Usala cuando pregunten cuanto se paga de nomina, de IMSS o de Infonavit en un "
        "periodo. IMPORTANTE: los importes que devuelve ya estan calculados por el motor "
        "fiscal; reportalos tal cual y NO sumes, promedies ni derives numeros nuevos. "
        "Las cuotas son lo DEVENGADO en el periodo pedido, no el entero mensual."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "periodo_inicio": {
                "type": "string",
                "description": "Primer día del periodo, ISO (2026-08-16).",
            },
            "periodo_fin": {
                "type": "string",
                "description": "Último día del periodo, ISO (2026-08-31).",
            },
            "cliente": {
                "type": "string",
                "description": f"Id del cliente. Default {CLIENTE_DEMO!r}.",
            },
        },
        "required": ["periodo_inicio", "periodo_fin"],
    },
}


def _fecha(valor: object, campo: str) -> date:
    if not isinstance(valor, str):
        raise FiscalAgentError(f"Falta `{campo}` en formato ISO (2026-08-16).")
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise FiscalAgentError(f"`{campo}` no es una fecha ISO válida: {valor!r}.") from exc


def _error(mensaje: str) -> str:
    return json.dumps({"error": mensaje}, ensure_ascii=False)


def calcular_nomina_periodo(tool_input: dict) -> str:
    """
    Ejecuta la tool. Devuelve JSON para el LLM, nunca levanta.

    El agente convierte cualquier excepción en un turno roto, así que los
    errores de dominio se devuelven como `{"error": ...}` y el modelo puede
    explicárselos al usuario.
    """
    try:
        inicio = _fecha(tool_input.get("periodo_inicio"), "periodo_inicio")
        fin = _fecha(tool_input.get("periodo_fin"), "periodo_fin")
    except FiscalAgentError as exc:
        return _error(str(exc))
    cliente = tool_input.get("cliente") or CLIENTE_DEMO

    eventos = almacen.eventos(cliente)
    del_periodo = [e for e in eventos if inicio <= e.timestamp.date() <= fin]
    if not del_periodo:
        return _error(
            f"No hay ninguna checada registrada para el cliente {cliente!r} entre "
            f"{inicio} y {fin}, así que no se puede calcular la nómina: sin checadas "
            f"todos los días saldrían como falta y el resultado sería una nómina "
            f"inventada. Corre el simulador del checador o conecta el dispositivo."
        )

    incidencias, desconocidos = cerrar_periodo(
        eventos,
        [e.empleado_no for e in PLANTILLA_DEMO],
        Periodo(inicio=inicio, fin=fin),
    )
    try:
        resultado = calcular_periodo(
            empleados=PLANTILLA_DEMO,
            incidencias=tuple(
                IncidenciasPeriodo(
                    empleado_no=i.empleado_no,
                    dias_periodo=i.dias_periodo,
                    faltas=i.faltas,
                    dias_ausentismo=i.dias_ausentismo,
                )
                for i in incidencias
            ),
            fecha_pago=fin,
            prima_riesgo=PRIMA_RIESGO_DEMO,
            clave_periodicidad=CLAVE_PERIODICIDAD_DEMO,
        )
    except FiscalAgentError as exc:
        return _error(str(exc))

    advertencias = list(resultado.advertencias)
    if desconocidos:
        advertencias.append(
            f"Hay checadas de empleados que no están en la plantilla: "
            f"{', '.join(desconocidos)}. Suele ser un alta con el número equivocado "
            f"en el checador, y esas checadas NO entraron al cálculo."
        )
    return json.dumps(
        {
            "cliente": cliente,
            "periodo": {"inicio": str(inicio), "fin": str(fin)},
            "empleados": len(resultado.recibos),
            "total_neto": float(resultado.total_neto),
            "total_isr": float(resultado.total_isr),
            "cuota_obrera": float(resultado.total_obrero),
            "cuota_patronal": float(resultado.total_patron),
            "ramos_mensuales": {
                k: float(v) for k, v in resultado.porcion_mensual.por_ramo.items()
            },
            "ramos_bimestrales": {
                k: float(v) for k, v in resultado.porcion_bimestral.por_ramo.items()
            },
            "recibos": [
                {
                    "empleado_no": r.empleado_no,
                    "nombre": r.nombre,
                    "dias_pagados": r.dias_pagados,
                    "dias_ausentismo": r.dias.dias_ausentismo,
                    "neto": float(r.recibo.total),
                }
                for r in resultado.recibos
            ],
            "advertencias": advertencias,
        },
        ensure_ascii=False,
    )
