"""
Trabajo en segundo plano de la contabilidad (P2-03).

`contabilidad.generar_polizas` (cliente): genera las pólizas automáticas de un rango. Es
idempotente por construcción (una póliza por UUID), así que un reintento o una segunda
corrida no duplica. Carga `{desde, hasta, uid}`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.contabilidad import generador
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import encolar, manejador

TIPO_GENERAR = "contabilidad.generar_polizas"


def encolar_generacion(db: Session, cliente: Cliente, desde: date, hasta: date,
                       uid: str) -> Trabajo:
    """Encola la generación del rango; la misma petición viva no se duplica."""
    return encolar(
        db, TIPO_GENERAR, {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "uid": uid},
        despacho_id=cliente.despacho_id, cliente_id=cliente.id,
        clave_unica=f"{TIPO_GENERAR}:{cliente.id}:{desde.isoformat()}:{hasta.isoformat()}",
        max_intentos=3,
    )


@manejador(TIPO_GENERAR)
def generar_polizas(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    cliente = db.get(Cliente, trabajo.cliente_id) if trabajo.cliente_id else None
    if cliente is None:
        raise FiscalAgentError("El trabajo no tiene un cliente válido.", status_code=404)
    c = trabajo.carga
    r = generador.generar(db, cliente, date.fromisoformat(c["desde"]),
                          date.fromisoformat(c["hasta"]), str(c.get("uid") or ""))
    return r.como_dict()
