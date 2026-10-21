"""
Catálogo de herramientas del asistente del despacho (P5-07). EL SERVIDOR ES SU DUEÑO.

Dos familias, las dos declaradas aquí y nunca recibidas del navegador:

- **De servidor** (`HERRAMIENTAS_SERVIDOR`): consultan al cliente ACTIVO —el que la ruta ya
  resolvió con `cliente_o_404`, así que un auxiliar sólo consulta lo asignado y un despacho
  nunca toca a otro— y devuelven lo que dicen la base y los motores (`consultas.py`).
- **De navegador** (`HERRAMIENTAS_NAVEGADOR`): operan la app de React (navegar, cargar los
  XML de demostración, pre-declaración con lo cargado). El servidor sólo las anuncia al LLM;
  quien las ejecuta es `apps/store/src/agent/tools.ts`, que vuelve a validar sus argumentos.

Las rutas de `navegar` son espejo de `RUTAS_BASE` en `apps/store/src/agent/tools.ts`. Si
divergen, lo peor que pasa es que el navegador rechace una ruta (la revalida); se mantienen
juntas a mano.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.asistente import consultas
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente

_ANIO = {"type": "integer", "minimum": 2000, "maximum": 2100, "description": "Año (AAAA)"}
_MES = {"type": "integer", "minimum": 1, "maximum": 12, "description": "Mes (1-12)"}


def _obj(propiedades: dict[str, Any], requeridas: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": propiedades, "required": requeridas}


HERRAMIENTAS_SERVIDOR: list[dict[str, Any]] = [
    {"nombre": "consultar_boveda",
     "descripcion": "CFDI del cliente activo en un mes: cuántos y por cuánto, por tipo "
                    "(ingreso, egreso, pago, nómina) y si son emitidos o recibidos, vigentes y "
                    "cancelados. Úsala para preguntas de facturas.",
     "parametros": _obj({"anio": _ANIO, "mes": _MES}, ["anio", "mes"])},
    {"nombre": "consultar_balanza",
     "descripcion": "Balanza de comprobación del cliente activo en un mes (saldos iniciales, "
                    "cargos, abonos, saldos finales) y si cuadra. nivel 1 = cuentas de mayor.",
     "parametros": _obj({"anio": _ANIO, "mes": _MES,
                         "nivel": {"type": "integer", "minimum": 1, "maximum": 3}},
                        ["anio", "mes"])},
    {"nombre": "consultar_nomina",
     "descripcion": "Nóminas guardadas del cliente activo: periodos con totales y neto. Con "
                    "periodo_id, los netos por trabajador de ese periodo.",
     "parametros": _obj({"periodo_id": {"type": "integer", "minimum": 1}}, [])},
    {"nombre": "consultar_vencimientos",
     "descripcion": "Obligaciones del calendario del cliente activo: vencidas sin presentar y "
                    "las que vencen en los próximos `dias` (fiscales, patronales, e.firma/CSD).",
     "parametros": _obj({"dias": {"type": "integer", "minimum": 1, "maximum": 120}}, [])},
    {"nombre": "consultar_alertas",
     "descripcion": "Alertas fiscales abiertas del cliente activo, las más graves primero.",
     "parametros": _obj({}, [])},
    {"nombre": "consultar_impuestos_mes",
     "descripcion": "Resumen de impuestos del mes (ISR, IVA, retenciones) que calcula el "
                    "motor con la bóveda, con actualización y recargos si ya venció. Úsala "
                    "para '¿cuánto paga?'.",
     "parametros": _obj({"anio": _ANIO, "mes": _MES}, ["anio", "mes"])},
]

RUTAS_NAVEGAR = (
    "/app/clientes", "/app/empleados", "/app/dispositivos", "/app/calendario", "/app/nomina",
    "/app/store", "/app/store/fiscalito/use", "/app/store/contabilito/use", "/app/profile",
    *(f"/app/store/fiscalito/use?tab={t}" for t in (
        "declaracion", "anual", "calendario", "comparar", "diot", "retenciones",
        "multiperiodo", "estado-cuenta", "deducciones", "pagospm")),
)

HERRAMIENTAS_NAVEGADOR: list[dict[str, Any]] = [
    {"nombre": "navegar",
     "descripcion": "Navega a una sección de la aplicación. Úsala cuando el usuario pida ver, "
                    "ir, entrar o mostrar una sección o tab.",
     "parametros": _obj({"ruta": {"type": "string", "enum": list(RUTAS_NAVEGAR)}}, ["ruta"])},
    {"nombre": "cargar_xmls_demo",
     "descripcion": "Carga facturas CFDI de demostración de un periodo para poder calcular "
                    "una pre-declaración de prueba.",
     "parametros": _obj({"anio": _ANIO, "mes": _MES}, ["anio", "mes"])},
    {"nombre": "calcular_predeclaracion",
     "descripcion": "Calcula en pantalla una pre-declaración mensual de ISR e IVA con las "
                    "facturas cargadas en el agente (si no hay, primero cargar_xmls_demo).",
     "parametros": _obj({"anio": _ANIO, "mes": _MES}, ["anio", "mes"])},
]

NOMBRES_SERVIDOR = frozenset(h["nombre"] for h in HERRAMIENTAS_SERVIDOR)
NOMBRES_NAVEGADOR = frozenset(h["nombre"] for h in HERRAMIENTAS_NAVEGADOR)
CATALOGO = HERRAMIENTAS_SERVIDOR + HERRAMIENTAS_NAVEGADOR


def _entero(args: dict[str, Any], nombre: str, default: int | None = None) -> int:
    valor = args.get(nombre, default)
    if valor is None:
        raise FiscalAgentError(f"Falta el argumento '{nombre}'.", 422)
    try:
        return int(valor)
    except (TypeError, ValueError) as exc:
        raise FiscalAgentError(f"El argumento '{nombre}' debe ser entero.", 422) from exc


Ejecutor = Callable[[Session, Cliente, dict[str, Any], date], dict[str, Any]]

_EJECUTORES: dict[str, Ejecutor] = {
    "consultar_boveda": lambda db, c, a, hoy: consultas.boveda_mes(
        db, c, _entero(a, "anio"), _entero(a, "mes")),
    "consultar_balanza": lambda db, c, a, hoy: consultas.balanza_mes(
        db, c, _entero(a, "anio"), _entero(a, "mes"), _entero(a, "nivel", 1)),
    "consultar_nomina": lambda db, c, a, hoy: consultas.nomina(
        db, c, _entero(a, "periodo_id") if a.get("periodo_id") is not None else None),
    "consultar_vencimientos": lambda db, c, a, hoy: consultas.vencimientos(
        db, c, hoy, _entero(a, "dias", 30)),
    "consultar_alertas": lambda db, c, a, hoy: consultas.alertas(db, c),
    "consultar_impuestos_mes": lambda db, c, a, hoy: consultas.impuestos_mes(
        db, c, _entero(a, "anio"), _entero(a, "mes"), hoy),
}


def ejecutar(db: Session, cliente: Cliente | None, nombre: str, argumentos: dict[str, Any],
             hoy: date) -> dict[str, Any]:
    """
    Corre una herramienta de servidor y devuelve `{ok, datos}` o `{ok: False, error}`.

    Nunca lanza: un error de dominio (periodo inválido, periodo de nómina de otro cliente →
    404) vuelve al LLM como resultado de la herramienta, para que lo explique.
    """
    if cliente is None:
        return {"ok": False, "error": "No hay cliente activo: pide al contador que elija uno "
                                      "en Clientes."}
    ejecutor = _EJECUTORES.get(nombre)
    if ejecutor is None:
        return {"ok": False, "error": f"Herramienta desconocida: {nombre}."}
    try:
        with db.begin_nested():  # una consulta que falla no envenena la transacción
            return {"ok": True, "datos": ejecutor(db, cliente, dict(argumentos or {}), hoy)}
    except FiscalAgentError as exc:
        return {"ok": False, "error": exc.message}


def como_contenido(resultado: dict[str, Any]) -> str:
    """El resultado como texto para el mensaje `herramienta` del LLM."""
    return json.dumps(resultado, ensure_ascii=False, default=str)
