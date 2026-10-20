"""
Planes del despacho: FUENTE ÚNICA de lo que incluye cada plan (P5-01, P5-08).

Aquí, y en ningún otro lado, vive:
- los límites de clientes y usuarios (`Plan.max_clientes`, `Plan.max_usuarios`);
- los módulos de paga que incluye cada plan (`MODULOS`, `modulos_del_plan`);
- el precio que se muestra (`precio_del_plan`) y el id del precio en el proveedor de pagos
  (`precio_externo`), los dos por variable de entorno;
- los días de prueba y de gracia de la suscripción.

Quien HACE CUMPLIR es el backend: el alta de clientes (`almacen_cartera.crear_cliente`), las
invitaciones y reactivaciones (`app/equipo/servicio.py`), los módulos
(`app/suscripciones/vigencia.exigir_modulo`) y el modo solo lectura
(`app/suscripciones/vigencia.exigir_escritura`, desde `tenancy.contexto_actual`). El front
(`apps/store/src/services/planes.ts`) pinta los mismos límites;
`tests/plan_p/test_equipo.py` fija que los dos lados digan lo mismo.

El plan vigente vive en `despachos.plan` y el estado del cobro en `suscripciones`
(`app/modelos/suscripciones.py`). Un despacho sin plan válido cae en el más chico
(`PLAN_POR_DEFECTO`): un default generoso regalaría capacidad que nadie contrató.

PRECIOS: NO HAY CIFRAS EN EL CÓDIGO
-----------------------------------
`FISCALITO_PLAN_<ID>_PRECIO` (p. ej. `FISCALITO_PLAN_CONTADOR_PRECIO=499.00`) es lo que se
muestra; sin la variable el precio es `None` y la pantalla dice "Precio por definir". Lo que
de verdad se cobra lo decide el proveedor con su propio precio (`FISCALITO_PAGOS_PRECIO_<ID>`:
el `price_...` de Stripe o el `preapproval_plan_id` de Mercado Pago). Ver
`docs/servicios-externos.md` § Pagos de suscripción.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


# Funciones que NO vienen en todos los planes. Todo lo que no esté aquí lo incluyen todos.
# Agregar un módulo = una clave aquí + `vigencia.exigir_modulo(ctx, "<clave>")` en su ruta.
MODULOS: dict[str, str] = {
    "dispersion": "Dispersión bancaria de la nómina",
    "imss_archivos": "Archivos IDSE y SUA para el IMSS",
}


@dataclass(frozen=True)
class Plan:
    """Límites y módulos de un plan."""

    id: str
    nombre: str
    max_usuarios: int
    max_clientes: int
    modulos: frozenset[str] = frozenset()


PLANES: dict[str, Plan] = {
    "contador": Plan("contador", "Contador", max_usuarios=1, max_clientes=25),
    "despacho": Plan("despacho", "Despacho", max_usuarios=10, max_clientes=200,
                     modulos=frozenset(MODULOS)),
}

PLAN_POR_DEFECTO = "contador"

# DECISIÓN PROVISIONAL (P5-08): política comercial, no norma. Se cambian por variable.
DIAS_PRUEBA_DEFAULT = 14
DIAS_GRACIA_DEFAULT = 3
MONEDA_DEFAULT = "MXN"


def plan(id_plan: str | None) -> Plan:
    """El plan `id_plan`, o el de por defecto si no existe."""
    return PLANES.get((id_plan or "").strip(), PLANES[PLAN_POR_DEFECTO])


def modulos_del_plan(p: Plan) -> frozenset[str]:
    """
    Los módulos del plan. `FISCALITO_PLANES_MODULOS` (JSON `{"contador": ["dispersion"]}`)
    reemplaza la lista de los planes que nombre; claves desconocidas se ignoran. Un JSON
    roto NO abre nada: se usa lo de este archivo y se avisa en el log.
    """
    crudo = os.environ.get("FISCALITO_PLANES_MODULOS", "").strip()
    if not crudo:
        return p.modulos
    try:
        config = json.loads(crudo)
        lista = config.get(p.id) if isinstance(config, dict) else None
    except ValueError:
        logger.warning("FISCALITO_PLANES_MODULOS no es JSON válido; se ignora.")
        return p.modulos
    if not isinstance(lista, list):
        return p.modulos
    return frozenset(m for m in lista if m in MODULOS)


def precio_del_plan(p: Plan) -> Decimal | None:
    """Precio mensual que se MUESTRA (`FISCALITO_PLAN_<ID>_PRECIO`), o None si no hay."""
    crudo = os.environ.get(f"FISCALITO_PLAN_{p.id.upper()}_PRECIO", "").strip()
    if not crudo:
        return None
    try:
        valor = Decimal(crudo).quantize(Decimal("0.01"))
    except InvalidOperation:
        logger.warning("FISCALITO_PLAN_%s_PRECIO no es un número; se ignora.", p.id.upper())
        return None
    return valor if valor >= 0 else None


def moneda() -> str:
    return (os.environ.get("FISCALITO_PLAN_MONEDA", "").strip() or MONEDA_DEFAULT).upper()


def precio_externo(p: Plan) -> str:
    """Id del precio en el proveedor (`FISCALITO_PAGOS_PRECIO_<ID>`); el falso usa el id."""
    return os.environ.get(f"FISCALITO_PAGOS_PRECIO_{p.id.upper()}", "").strip()


def _entero(variable: str, default: int) -> int:
    try:
        valor = int(os.environ.get(variable, "").strip() or default)
    except ValueError:
        return default
    return max(valor, 0)


def dias_prueba() -> int:
    return _entero("FISCALITO_SUSCRIPCION_DIAS_PRUEBA", DIAS_PRUEBA_DEFAULT)


def dias_gracia() -> int:
    return _entero("FISCALITO_SUSCRIPCION_DIAS_GRACIA", DIAS_GRACIA_DEFAULT)
