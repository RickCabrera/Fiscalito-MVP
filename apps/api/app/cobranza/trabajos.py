"""
Trabajos de cobranza (P5-03). Todos idempotentes.

- `cobranza.cargos_mensuales` (diario): genera la iguala del mes de cada cliente cuyo día de
  cargo ya llegó. Correr dos veces no duplica: la iguala es única por `iguala:YYYY-MM`.
- `cobranza.recordatorios_automaticos` (diario): recordatorio a clientes con saldo vencido.
- `cobranza.recordatorio`: manda un recordatorio programado a mano.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cobranza import recordatorios
from app.cobranza.servicio import generar_igualas
from app.modelos.cobranza import RecordatorioCobro
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import encolar, manejador


def _hoy(trabajo: Trabajo) -> date:
    return date.fromisoformat(str(trabajo.carga.get("hoy") or date.today().isoformat()))


@manejador("cobranza.cargos_mensuales")
def cargos_mensuales(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    nuevos = generar_igualas(db, _hoy(trabajo))
    return {"cargos": len(nuevos)}


@manejador("cobranza.recordatorios_automaticos")
def recordatorios_automaticos(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    return recordatorios.automaticos(db, _hoy(trabajo))


@manejador(recordatorios.TIPO_RECORDATORIO)
def recordatorio(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    rec = db.get(RecordatorioCobro, int(trabajo.carga.get("recordatorio_id", 0)))
    if rec is None:
        return {"omitido": "el recordatorio ya no existe"}
    recordatorios.enviar(db, rec, relanzar=True)
    return {"estado": rec.estado}


def encolar_cargos(db: Session, ranura: datetime) -> object:
    hoy = ranura.date().isoformat()
    return encolar(db, "cobranza.cargos_mensuales", {"hoy": hoy}, ejecutar_en=ranura,
                   clave_unica=f"prog:cobranza_cargos:{ranura.isoformat()}", max_intentos=3)


def encolar_recordatorios(db: Session, ranura: datetime) -> object:
    hoy = ranura.date().isoformat()
    return encolar(db, "cobranza.recordatorios_automaticos", {"hoy": hoy}, ejecutar_en=ranura,
                   clave_unica=f"prog:cobranza_recordatorios:{ranura.isoformat()}",
                   max_intentos=3)
