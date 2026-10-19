"""
Manejadores de la cola y tareas recurrentes de la descarga del SAT (P1-01, P1-02).

- `sat.descarga.rango` {inicio, fin, origen, seleccion}: crea (o reusa) las solicitudes del
  rango y encola su avance. Idempotente: la huella de cada solicitud no se repite.
- `sat.descarga.avanzar` {solicitud_id}: da los pasos que tocan y, si la solicitud sigue viva,
  se vuelve a encolar para su `proxima_verificacion`. Una solicitud que el SAT tarda días no
  ocupa al worker: sólo hay un trabajo pendiente con fecha futura.
- Recurrentes: `sat_diaria` (cada 15 min revisa qué clientes ya pasaron su hora) y
  `sat_pendientes` (cada 30 min recoge solicitudes vivas cuyo trabajo se perdió).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credenciales import obtener_firmante
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import SolicitudDescargaSat
from app.modelos.trabajos import ESTADOS_VIVOS, Trabajo
from app.sat_descarga import servicio, sincronizacion
from app.trabajos.cola import encolar, manejador
from app.trabajos.programacion import TareaRecurrente


@manejador("sat.descarga.rango")
def descargar_rango(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    cliente = db.get(Cliente, trabajo.cliente_id)
    if cliente is None:
        return {"omitido": "cliente borrado"}
    c = trabajo.carga
    sel = sincronizacion.Seleccion(**c.get("seleccion", {}))
    sols = sincronizacion.crear_rango(
        db, cliente, datetime.fromisoformat(c["inicio"]), datetime.fromisoformat(c["fin"]),
        sel, c.get("origen", "manual"),
    )
    return {"solicitudes": [s.id for s in sols]}


@manejador("sat.descarga.avanzar")
def avanzar_solicitud(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    s = db.get(SolicitudDescargaSat, int(trabajo.carga["solicitud_id"]))
    if s is None:
        return {"omitido": "solicitud borrada"}
    cliente = db.get(Cliente, s.cliente_id)
    assert cliente is not None
    momento = servicio.reloj()
    if s.estado in servicio.TERMINALES:
        return {"estado": s.estado, "omitido": "ya terminó"}
    if s.proxima_verificacion is not None and s.proxima_verificacion > momento:
        # Trabajo duplicado o adelantado: el que toca ya está en la cola con su fecha.
        return {"estado": s.estado, "omitido": "todavía no toca"}
    try:
        firmante = obtener_firmante(db, cliente, "efirma")
    except FiscalAgentError as e:
        if e.status_code == 503:
            raise  # llave maestra: problema del servidor; la cola reintenta
        servicio.alertar(db, cliente.id, "sin_efirma", e.message, s.id)
        s.mensaje = f"En pausa: {e.message}"
        s.proxima_verificacion = momento + timedelta(hours=6)
        _reencolar(db, cliente, s, trabajo)
        return {"estado": s.estado, "pausa": "efirma"}
    servicio.correr_hasta_esperar(db, s, servicio.contexto_por_default(firmante), momento)
    _reencolar(db, cliente, s, trabajo)
    return {"estado": s.estado, "codigo": s.codigo, "xml_importados": s.xml_importados,
            "duplicados": s.duplicados}


def _reencolar(db: Session, cliente: Cliente, s: SolicitudDescargaSat, actual: Trabajo) -> None:
    """El trabajo actual sigue `corriendo` (su clave está viva): el siguiente lleva otra."""
    if s.estado not in servicio.TERMINALES and s.proxima_verificacion is not None:
        encolar(db, "sat.descarga.avanzar", {"solicitud_id": s.id},
                despacho_id=cliente.despacho_id, cliente_id=cliente.id,
                ejecutar_en=s.proxima_verificacion,
                clave_unica=f"sat.solicitud:{s.id}:{s.proxima_verificacion.isoformat()}",
                max_intentos=3)


def _encolar_revision_diaria(db: Session, ranura: datetime) -> object:
    return sincronizacion.encolar_diarias(db, ranura)


def _recoger_pendientes(db: Session, ranura: datetime) -> object:
    """Red de seguridad: solicitudes vivas y vencidas sin trabajo en la cola."""
    ids = servicio.vivas_vencidas(db, ranura)
    for sid in ids:
        s = db.get(SolicitudDescargaSat, sid)
        cliente = db.get(Cliente, s.cliente_id) if s else None
        if s is None or cliente is None:
            continue
        ya_hay = db.scalar(select(Trabajo.id).where(
            Trabajo.tipo == "sat.descarga.avanzar",
            Trabajo.estado.in_(ESTADOS_VIVOS),
            Trabajo.clave_unica.like(f"sat.solicitud:{s.id}%"),
        ).limit(1))
        if ya_hay is not None:
            continue
        encolar(db, "sat.descarga.avanzar", {"solicitud_id": s.id},
                despacho_id=cliente.despacho_id, cliente_id=cliente.id,
                clave_unica=f"sat.solicitud:{s.id}:recoger:{ranura.isoformat()}",
                max_intentos=3)
    return ids


TAREAS = [
    TareaRecurrente("sat_diaria", _encolar_revision_diaria, cada=timedelta(minutes=15)),
    TareaRecurrente("sat_pendientes", _recoger_pendientes, cada=timedelta(minutes=30)),
]


def _registrar_tareas() -> None:
    """Agrega las tareas del SAT a la lista del programador (una sola vez)."""
    from app.trabajos import programacion

    nombres = {t.nombre for t in programacion.TAREAS}
    programacion.TAREAS.extend(t for t in TAREAS if t.nombre not in nombres)


_registrar_tareas()
