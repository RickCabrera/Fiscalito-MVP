"""
Trabajos en segundo plano de las verificaciones SAT (P1-03/04/05).

Tipos (todos idempotentes):
- `sat.verificar_estatus` (cliente): un lote de CFDI del rango; si quedan, encola su
  continuación. Carga `{desde, hasta, corte}`.
- `sat.estatus_programado` (sistema): encola `sat.verificar_estatus` para cada cliente con
  CFDI no cancelados en el alcance (`mes` diario, `anio` semanal).
- `sat.listas_actualizar` (sistema): descarga las listas activas y encola el cruce de cada
  cliente con una contraparte listada.
- `sat.listas_cruce` (cliente): crea las alertas nuevas del cliente.
- `sat.cumplimiento_programado` (sistema): encola la opinión (y constancia) mensual de los
  clientes a los que les toca hoy.
- `sat.cumplimiento_obtener` (cliente): obtiene y guarda la opinión o constancia.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.integraciones.comun import ErrorServicioExterno
from app.integraciones.opinion_cumplimiento import obtener_opinion_cumplimiento
from app.integraciones.sat_estatus import obtener_sat_estatus
from app.integraciones.sat_listas import listas_activas, obtener_sat_listas
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.sat_verificacion import cumplimiento, estatus, listas
from app.trabajos.cola import encolar, manejador

ZONA = ZoneInfo("America/Mexico_City")
TIPO_ESTATUS = "sat.verificar_estatus"
TIPO_CUMPLIMIENTO = "sat.cumplimiento_obtener"


def _cliente(db: Session, trabajo: Trabajo) -> Cliente:
    cliente = db.get(Cliente, trabajo.cliente_id) if trabajo.cliente_id else None
    if cliente is None:
        raise FiscalAgentError("El trabajo no tiene un cliente válido.", status_code=404)
    return cliente


def encolar_verificacion(
    db: Session, cliente: Cliente, desde: date, hasta: date, *,
    corte: datetime | None = None, parte: int = 1, origen: str = "manual",
    ejecutar_en: datetime | None = None,
) -> Trabajo:
    """Encola la verificación de estatus del rango. La misma petición viva no se duplica."""
    momento = (corte or datetime.now(UTC)).astimezone(UTC)
    clave = f"{TIPO_ESTATUS}:{cliente.id}:{desde.isoformat()}:{hasta.isoformat()}"
    return encolar(
        db, TIPO_ESTATUS,
        {"desde": desde.isoformat(), "hasta": hasta.isoformat(),
         "corte": momento.isoformat(), "parte": parte, "origen": origen},
        despacho_id=cliente.despacho_id, cliente_id=cliente.id, ejecutar_en=ejecutar_en,
        # La continuación (parte > 1) corre mientras la parte anterior sigue `corriendo`:
        # lleva su número en la clave para no chocar con ella.
        clave_unica=clave if parte == 1 else f"{clave}:p{parte}:{momento.isoformat()}",
        max_intentos=4,
    )


@manejador(TIPO_ESTATUS)
def verificar_estatus(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    cliente = _cliente(db, trabajo)
    c = trabajo.carga
    desde, hasta = date.fromisoformat(c["desde"]), date.fromisoformat(c["hasta"])
    corte = datetime.fromisoformat(c["corte"])
    r = estatus.verificar_cliente(db, cliente, desde, hasta, corte, obtener_sat_estatus())
    if r.errores and not r.consultados:
        # El SAT no contestó a nada: se reintenta el trabajo completo con backoff.
        raise ErrorServicioExterno(
            f"El SAT no respondió ninguna consulta ({r.errores} errores): "
            + "; ".join(r.detalle_errores[:2]))
    if r.pendientes:
        encolar_verificacion(db, cliente, desde, hasta, corte=corte,
                             parte=int(c.get("parte", 1)) + 1, origen=c.get("origen", ""))
    return r.como_dict()


def _alcance(alcance: str, hoy: date) -> tuple[date, date]:
    if alcance == "mes":
        return hoy.replace(day=1), hoy
    return hoy - timedelta(days=365), hoy


@manejador("sat.estatus_programado")
def estatus_programado(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    alcance = trabajo.carga.get("alcance", "mes")
    hoy = datetime.now(ZONA).date()
    desde, hasta = _alcance(alcance, hoy)
    ids = list(db.scalars(select(Comprobante.cliente_id).distinct().where(
        Comprobante.estatus_sat != "cancelado",
        Comprobante.fecha >= datetime.combine(desde, datetime.min.time()),
    )))
    for cliente in db.scalars(select(Cliente).where(Cliente.id.in_(ids))):
        encolar_verificacion(db, cliente, desde, hasta, origen=f"programado:{alcance}")
    return {"alcance": alcance, "clientes": len(ids)}


def encolar_estatus_mes(db: Session, ranura: datetime) -> object:
    return encolar(db, "sat.estatus_programado", {"alcance": "mes"}, ejecutar_en=ranura,
                   clave_unica=f"prog:sat_estatus_mes:{ranura.isoformat()}", max_intentos=3)


def encolar_estatus_anio(db: Session, ranura: datetime) -> object:
    return encolar(db, "sat.estatus_programado", {"alcance": "anio"}, ejecutar_en=ranura,
                   clave_unica=f"prog:sat_estatus_anio:{ranura.isoformat()}", max_intentos=3)


# ── listas 69-B / 69 ──


@manejador("sat.listas_actualizar")
def listas_actualizar(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    adaptador = obtener_sat_listas()
    resultados, errores = [], []
    for lista in trabajo.carga.get("listas") or listas_activas():
        try:
            with db.begin_nested():
                resultados.append(listas.cargar_lista(db, lista, adaptador).como_dict())
        except Exception as e:  # noqa: BLE001 — una lista rota no detiene a las demás
            mensaje = getattr(e, "message", None) or f"{type(e).__name__}: {e}"
            errores.append({"lista": lista, "error": mensaje})
            listas.registrar_error(db, lista, mensaje)
    if errores and not resultados:
        db.commit()  # que quede el error registrado aunque el trabajo se reintente
        raise ErrorServicioExterno(f"No se pudo cargar ninguna lista: {errores}")
    clientes = listas.clientes_con_contraparte_listada(db)
    for cliente in clientes:
        encolar(db, "sat.listas_cruce", {}, despacho_id=cliente.despacho_id,
                cliente_id=cliente.id, clave_unica=f"sat.listas_cruce:{cliente.id}",
                max_intentos=3)
    return {"listas": resultados, "errores": errores, "clientes_a_cruzar": len(clientes)}


@manejador("sat.listas_cruce")
def listas_cruce(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    nuevas = listas.cruzar_cliente(db, _cliente(db, trabajo))
    return {"alertas_nuevas": len(nuevas)}


def encolar_listas(db: Session, ranura: datetime) -> object:
    return encolar(db, "sat.listas_actualizar", {}, ejecutar_en=ranura,
                   clave_unica=f"prog:sat_listas:{ranura.isoformat()}", max_intentos=4)


# ── opinión de cumplimiento ──


def encolar_cumplimiento(db: Session, cliente: Cliente, tipo: str, usuario: str = "sistema",
                         origen: str = "manual") -> Trabajo:
    return encolar(
        db, TIPO_CUMPLIMIENTO, {"tipo": tipo, "usuario": usuario, "origen": origen},
        despacho_id=cliente.despacho_id, cliente_id=cliente.id,
        clave_unica=f"{TIPO_CUMPLIMIENTO}:{cliente.id}:{tipo}", max_intentos=3,
    )


@manejador(TIPO_CUMPLIMIENTO)
def cumplimiento_obtener(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    cliente = _cliente(db, trabajo)
    doc = cumplimiento.obtener_y_guardar(
        db, cliente, trabajo.carga.get("tipo", "opinion"), obtener_opinion_cumplimiento(),
        str(trabajo.carga.get("usuario") or "sistema"))
    return {"documento": doc.id, "resultado": doc.resultado, "fecha": doc.fecha.isoformat()}


@manejador("sat.cumplimiento_programado")
def cumplimiento_programado(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    hoy = datetime.now(ZONA).date()
    clientes = [c for c in db.scalars(select(Cliente).order_by(Cliente.id))
                if cumplimiento.rfc_de(c)]
    ultimas = cumplimiento.ultimas(db, [c.id for c in clientes], "opinion")
    ultimas_cons = cumplimiento.ultimas(db, [c.id for c in clientes], "constancia")
    encolados = 0
    for c in clientes:
        config = cumplimiento.config_de(db, c)
        if cumplimiento.toca_hoy(config, ultimas.get(c.id), hoy):
            encolar_cumplimiento(db, c, "opinion", origen="programado")
            encolados += 1
        if config.constancia and cumplimiento.toca_hoy(config, ultimas_cons.get(c.id), hoy):
            encolar_cumplimiento(db, c, "constancia", origen="programado")
            encolados += 1
    return {"encolados": encolados}


def encolar_cumplimiento_diario(db: Session, ranura: datetime) -> object:
    return encolar(db, "sat.cumplimiento_programado", {}, ejecutar_en=ranura,
                   clave_unica=f"prog:sat_cumplimiento:{ranura.isoformat()}", max_intentos=3)
