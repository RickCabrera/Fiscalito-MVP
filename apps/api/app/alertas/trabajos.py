"""
Trabajo diario de alertas fiscales (P3-09).

`alertas.programado` (una vez al día, `programacion.TAREAS`) encola un `alertas.evaluar` por
cliente; cada uno corre las reglas de ese cliente. Idempotentes: correr dos veces el mismo día
no duplica alertas (la clave de cada una es estable, ver `reglas.sincronizar`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas import reglas
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import encolar, manejador

TIPO_EVALUAR = "alertas.evaluar"


@manejador(TIPO_EVALUAR)
def evaluar(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    cliente = db.get(Cliente, trabajo.cliente_id)
    if cliente is None:
        return {"omitido": "el cliente ya no existe"}
    hoy = date.fromisoformat(str(trabajo.carga.get("hoy") or date.today().isoformat()))
    return reglas.evaluar_cliente(db, cliente, hoy)


@manejador("alertas.programado")
def programado(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    hoy = str(trabajo.carga.get("hoy") or date.today().isoformat())
    total = 0
    for cliente in db.scalars(select(Cliente).order_by(Cliente.id)):
        encolar(db, TIPO_EVALUAR, {"hoy": hoy}, despacho_id=cliente.despacho_id,
                cliente_id=cliente.id, clave_unica=f"{TIPO_EVALUAR}:{cliente.id}:{hoy}",
                max_intentos=3)
        total += 1
    return {"clientes": total}


def encolar_diario(db: Session, ranura: datetime) -> object:
    hoy = ranura.date().isoformat()
    return encolar(db, "alertas.programado", {"hoy": hoy}, ejecutar_en=ranura,
                   clave_unica=f"prog:alertas:{ranura.isoformat()}", max_intentos=3)
