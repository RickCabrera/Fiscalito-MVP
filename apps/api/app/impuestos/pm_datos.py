"""
Personas morales: tipo (601 / RESICO PM) y datos anuales capturados por el despacho
(pérdidas, estímulos). Salió de `impuestos/personas_morales.py` en P6-05 (tope de 300 líneas)
sin cambiar nada; ese módulo lo reexporta.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.fiscal_engine import personas_morales as motor
from app.impuestos.servicio import regimen_de
from app.modelos.impuestos import DatosAnualesPM
from app.modelos.nucleo import Cliente
from app.schemas.personas_morales import DatosAnualesPMSchema

# ── tipo y datos capturados ──


def tipo_pm(cliente: Cliente) -> str | None:
    """`general` (601), `resico` (626 con RFC de 12) o None si no es persona moral."""
    regimen = regimen_de(cliente)
    if regimen == "601":
        return "general"
    if regimen == "626" and len(cliente.rfc or "") == 12:
        return "resico"
    return None


def datos_de(db: Session, cliente: Cliente, anio: int) -> DatosAnualesPMSchema:
    fila = db.get(DatosAnualesPM, (cliente.id, anio))
    return DatosAnualesPMSchema.model_validate(fila.datos if fila else {})


def guardar_datos(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema) -> None:
    fila = db.get(DatosAnualesPM, (cliente.id, anio))
    datos = d.model_dump(mode="json")
    if fila is None:
        db.add(DatosAnualesPM(cliente_id=cliente.id, anio=anio, datos=datos))
    else:
        fila.datos = datos
    db.flush()


def perdidas_de(d: DatosAnualesPMSchema) -> list[motor.PerdidaPendiente]:
    salida = []
    for p in d.perdidas:
        act = None
        if p.actualizada_a:
            a, m = p.actualizada_a.split("-")
            act = (int(a), int(m))
        salida.append(motor.PerdidaPendiente(p.ejercicio, p.remanente, act))
    return salida


def estimulos_de(d: DatosAnualesPMSchema) -> list[motor.Estimulo]:
    return [motor.Estimulo(e.concepto, e.importe, e.fundamento, e.desde_mes, e.en_provisionales)
            for e in d.estimulos]
