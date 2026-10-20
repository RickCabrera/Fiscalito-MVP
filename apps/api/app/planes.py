"""
Planes del despacho: FUENTE ÚNICA de los límites de clientes y usuarios (P5-01).

El front (`apps/store/src/services/planes.ts`) pinta los mismos números, pero quien los
HACE CUMPLIR es el backend: el alta de clientes (`almacen_cartera.crear_cliente`) y las
invitaciones y reactivaciones de usuarios (`app/equipo/servicio.py`) preguntan aquí.
`tests/plan_p/test_equipo.py` fija que los dos lados digan lo mismo.

El plan elegido vive en `despachos.plan`. Un despacho sin plan válido cae en el más chico
(`PLAN_POR_DEFECTO`): un default generoso regalaría capacidad que nadie contrató.
No hay cobro: es el encuadre comercial con límites que sí muerden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """Límites de un plan."""

    id: str
    nombre: str
    max_usuarios: int
    max_clientes: int


PLANES: dict[str, Plan] = {
    "contador": Plan("contador", "Contador", max_usuarios=1, max_clientes=25),
    "despacho": Plan("despacho", "Despacho", max_usuarios=10, max_clientes=200),
}

PLAN_POR_DEFECTO = "contador"


def plan(id_plan: str | None) -> Plan:
    """El plan `id_plan`, o el de por defecto si no existe."""
    return PLANES.get((id_plan or "").strip(), PLANES[PLAN_POR_DEFECTO])
