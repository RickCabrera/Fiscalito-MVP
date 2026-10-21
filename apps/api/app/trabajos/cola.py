"""
La cola: encolar, tomar, correr y reprogramar trabajos (P0-04).

CÓMO SE TOMA UN TRABAJO SIN QUE DOS WORKERS TOMEN EL MISMO
-----------------------------------------------------------
1. Se elige el pendiente vencido más viejo. En Postgres con `FOR UPDATE SKIP LOCKED`: dos
   workers simultáneos eligen renglones distintos sin esperarse.
2. Se marca `corriendo` con una actualización CONDICIONAL (`WHERE estado = 'pendiente'`).
   En SQLite, que no tiene `SKIP LOCKED`, ésa es la garantía: si otro lo tomó primero, la
   actualización toca cero renglones y se prueba con el siguiente.
3. El manejador corre en una sesión NUEVA. Si falla, su transacción se descarta entera y
   el error se guarda en otra, así un manejador a medio escribir no deja basura.

TODO MANEJADOR DEBE SER IDEMPOTENTE
-----------------------------------
Un worker que muere a media ejecución deja el trabajo `corriendo` para siempre; pasados
`MINUTOS_HUERFANO` minutos vuelve a `pendiente` y corre otra vez. Además, el reintento
tras un error repite el trabajo desde el principio. Correr dos veces no puede duplicar nada.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import ahora as _ahora
from app.exceptions import FiscalAgentError
from app.modelos.trabajos import ESTADOS_VIVOS, Trabajo

logger = logging.getLogger(__name__)

Manejador = Callable[[Session, Trabajo], dict[str, Any] | None]

# Backoff exponencial: 30 s, 60 s, 2 min, 4 min… con techo de una hora.
BACKOFF_BASE_SEGUNDOS = 30
BACKOFF_MAX_SEGUNDOS = 3600
# Un `corriendo` sin terminar después de esto se da por huérfano (worker caído).
MINUTOS_HUERFANO = 15
# Tope del texto de error guardado: una traza enorme no debe inflar la tabla.
MAX_ERROR = 2000

_MANEJADORES: dict[str, Manejador] = {}


def manejador(tipo: str) -> Callable[[Manejador], Manejador]:
    """Decorador: registra la función que corre los trabajos de `tipo`."""

    def registrar(funcion: Manejador) -> Manejador:
        if tipo in _MANEJADORES and _MANEJADORES[tipo] is not funcion:
            raise ValueError(f"Ya hay un manejador registrado para '{tipo}'.")
        _MANEJADORES[tipo] = funcion
        return funcion

    return registrar


def manejadores() -> dict[str, Manejador]:
    """Copia del registro (para diagnóstico y tests)."""
    return dict(_MANEJADORES)


def olvidar_manejador(tipo: str) -> None:
    """Para tests: quita un manejador registrado."""
    _MANEJADORES.pop(tipo, None)


def backoff(intentos: int) -> timedelta:
    """Espera antes del siguiente intento, tras `intentos` fallidos."""
    segundos = BACKOFF_BASE_SEGUNDOS * (2 ** max(intentos - 1, 0))
    return timedelta(seconds=min(segundos, BACKOFF_MAX_SEGUNDOS))


def _vivo_con_clave(db: Session, clave_unica: str) -> Trabajo | None:
    return db.scalar(
        select(Trabajo).where(
            Trabajo.clave_unica == clave_unica, Trabajo.estado.in_(ESTADOS_VIVOS)
        )
    )


def encolar(
    db: Session,
    tipo: str,
    carga: dict[str, Any] | None = None,
    *,
    despacho_id: str | None = None,
    cliente_id: int | None = None,
    ejecutar_en: datetime | None = None,
    clave_unica: str | None = None,
    max_intentos: int = 5,
) -> Trabajo:
    """
    Agrega un trabajo a la cola (dentro de la transacción de `db`, sin commit).

    Con `clave_unica`, si ya hay uno pendiente o corriendo con esa clave se devuelve ése y
    no se crea otro. Uno terminado (hecho, fallido, cancelado) no estorba.
    """
    if max_intentos < 1:
        raise ValueError("max_intentos debe ser al menos 1.")
    if clave_unica:
        existente = _vivo_con_clave(db, clave_unica)
        if existente is not None:
            return existente
    trabajo = Trabajo(
        tipo=tipo,
        carga=dict(carga or {}),
        despacho_id=despacho_id,
        cliente_id=cliente_id,
        ejecutar_en=ejecutar_en or _ahora(),
        clave_unica=clave_unica,
        max_intentos=max_intentos,
        estado="pendiente",
        intentos=0,
    )
    if not clave_unica:
        db.add(trabajo)
        db.flush()
        return trabajo
    # Carrera: otro proceso pudo insertar la misma clave entre la consulta y el insert. El
    # índice único parcial lo rechaza; el savepoint deja viva la transacción de afuera.
    try:
        with db.begin_nested():
            db.add(trabajo)
            db.flush()
    except IntegrityError:
        existente = _vivo_con_clave(db, clave_unica)
        if existente is None:
            raise
        return existente
    return trabajo


def recuperar_huerfanos(
    sesionador: sessionmaker, *, ahora: datetime | None = None, minutos: int = MINUTOS_HUERFANO
) -> int:
    """`corriendo` de hace más de `minutos` → `pendiente` (o `fallido` si ya no le quedan
    intentos). Devuelve cuántos se recuperaron."""
    momento = ahora or _ahora()
    limite = momento - timedelta(minutes=minutos)
    with sesionador() as db:
        huerfanos = list(
            db.scalars(
                select(Trabajo).where(
                    Trabajo.estado == "corriendo", Trabajo.iniciado_en < limite
                )
            )
        )
        for t in huerfanos:
            nota = f"Huérfano: el worker no terminó en {minutos} minutos."
            if t.intentos >= t.max_intentos:
                t.estado, t.terminado_en, t.error = "fallido", momento, nota
            else:
                t.estado, t.ejecutar_en, t.error = "pendiente", momento, nota
            logger.warning("Trabajo %s huérfano → %s", t.id, t.estado)
        db.commit()
        return len(huerfanos)


def _tomar(sesionador: sessionmaker, momento: datetime) -> int | None:
    """Reclama el siguiente pendiente vencido y lo marca `corriendo`. Devuelve su id."""
    for _ in range(10):  # Si otro worker gana la carrera, se prueba con el siguiente.
        with sesionador() as db:
            consulta = (
                select(Trabajo.id)
                .where(Trabajo.estado == "pendiente", Trabajo.ejecutar_en <= momento)
                .order_by(Trabajo.ejecutar_en, Trabajo.id)
                .limit(1)
            )
            if db.get_bind().dialect.name == "postgresql":
                consulta = consulta.with_for_update(skip_locked=True)
            trabajo_id = db.scalar(consulta)
            if trabajo_id is None:
                return None
            tomado = db.execute(
                update(Trabajo)
                .where(Trabajo.id == trabajo_id, Trabajo.estado == "pendiente")
                .values(
                    estado="corriendo",
                    iniciado_en=momento,
                    terminado_en=None,
                    intentos=Trabajo.intentos + 1,
                )
            )
            db.commit()
            if tomado.rowcount == 1:
                return trabajo_id
    return None


def _cerrar(
    sesionador: sessionmaker, trabajo_id: int, valores: dict[str, Any]
) -> Trabajo | None:
    """Escribe el desenlace sólo si el trabajo sigue `corriendo` (nadie lo canceló ni lo
    recuperó como huérfano mientras tanto)."""
    with sesionador() as db:
        db.execute(
            update(Trabajo)
            .where(Trabajo.id == trabajo_id, Trabajo.estado == "corriendo")
            .values(**valores)
        )
        db.commit()
        return db.get(Trabajo, trabajo_id)


def procesar_siguiente(
    sesionador: sessionmaker, *, ahora: datetime | None = None
) -> Trabajo | None:
    """
    Corre UN trabajo vencido, si hay. Devuelve cómo quedó (o None si la cola está vacía).

    El éxito guarda `resultado`; el error se guarda en `error` y el trabajo vuelve a
    `pendiente` con backoff exponencial, hasta `max_intentos`, donde queda `fallido`.
    """
    momento = ahora or _ahora()
    recuperar_huerfanos(sesionador, ahora=momento)
    trabajo_id = _tomar(sesionador, momento)
    if trabajo_id is None:
        return None

    with sesionador() as db:
        trabajo = db.get(Trabajo, trabajo_id)
        assert trabajo is not None
        funcion = _MANEJADORES.get(trabajo.tipo)
        intentos, max_intentos = trabajo.intentos, trabajo.max_intentos
        if funcion is None:
            # Sin manejador no hay reintento que valga: falla de una vez y lo dice.
            error: str | None = f"No hay manejador registrado para el tipo '{trabajo.tipo}'."
            resultado = None
            intentos = max_intentos
        else:
            try:
                resultado = funcion(db, trabajo) or {}
                db.commit()
                error = None
            except Exception as exc:  # noqa: BLE001 — cualquier fallo se guarda y se reintenta
                db.rollback()
                if isinstance(exc, FiscalAgentError):
                    error = exc.message
                else:
                    error = f"{type(exc).__name__}: {exc}"
                resultado = None
                logger.exception("Trabajo %s (%s) falló", trabajo_id, trabajo.tipo)

    fin = _ahora() if ahora is None else momento
    if error is None:
        return _cerrar(
            sesionador,
            trabajo_id,
            {"estado": "hecho", "resultado": resultado, "error": None, "terminado_en": fin},
        )
    error = error[:MAX_ERROR]
    if intentos >= max_intentos:
        return _cerrar(
            sesionador, trabajo_id, {"estado": "fallido", "error": error, "terminado_en": fin}
        )
    return _cerrar(
        sesionador,
        trabajo_id,
        {"estado": "pendiente", "error": error, "ejecutar_en": momento + backoff(intentos)},
    )


def reintentar(db: Session, trabajo: Trabajo, *, ahora: datetime | None = None) -> Trabajo:
    """Un trabajo `fallido` o `cancelado` vuelve a la cola con sus intentos en cero."""
    if trabajo.estado not in ("fallido", "cancelado"):
        raise FiscalAgentError(
            f"Sólo se reintenta un trabajo fallido o cancelado; éste está '{trabajo.estado}'.",
            status_code=409,
        )
    if trabajo.clave_unica:
        otro = _vivo_con_clave(db, trabajo.clave_unica)
        if otro is not None and otro.id != trabajo.id:
            raise FiscalAgentError(
                "Ya hay otro trabajo igual en la cola; no se duplica.", status_code=409
            )
    trabajo.estado = "pendiente"
    trabajo.intentos = 0
    trabajo.ejecutar_en = ahora or _ahora()
    trabajo.iniciado_en = None
    trabajo.terminado_en = None
    db.flush()
    return trabajo


def cancelar(db: Session, trabajo: Trabajo, *, ahora: datetime | None = None) -> Trabajo:
    """
    Cancela un trabajo `pendiente`.

    Uno `corriendo` no se cancela: el manejador ya está escribiendo y cortarlo a media
    transacción no es algo que esta cola pueda garantizar.
    """
    # Condicional, como `_tomar`: si un worker lo reclamó entre la lectura y este UPDATE,
    # toca cero renglones y se responde 409 en vez de pisar un `corriendo`.
    cambio = db.execute(
        update(Trabajo)
        .where(Trabajo.id == trabajo.id, Trabajo.estado == "pendiente")
        .values(estado="cancelado", terminado_en=ahora or _ahora())
    )
    db.refresh(trabajo)
    if cambio.rowcount != 1:
        raise FiscalAgentError(
            f"Sólo se cancela un trabajo pendiente; éste está '{trabajo.estado}'.",
            status_code=409,
        )
    return trabajo
