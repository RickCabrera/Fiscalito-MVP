"""
Estatus de los CFDI de la bóveda ante el SAT (P1-03).

QUÉ SE CONSULTA
---------------
Los comprobantes del cliente en un rango de fechas que **no** están ya cancelados (un CFDI
cancelado no revive) y que no se han consultado desde `corte` (el momento en que se pidió la
verificación). Eso hace al trabajo idempotente y reanudable: si corre dos veces, la segunda
no encuentra nada; si se corta a la mitad, la continuación toma lo que faltó.

QUÉ SE ESCRIBE
--------------
- `Comprobante.estatus_sat` = `vigente` | `cancelado`, y `fecha_estatus`.
- `VerificacionCfdi` con los textos del SAT tal cual (incluye "En proceso" de cancelación y
  la ValidacionEFOS).
- "No encontrado" NO cambia el estatus: un CFDI recién timbrado tarda en aparecer en el SAT y
  "no encontrado" no es "cancelado". Queda el detalle en `VerificacionCfdi`.

CANCELADO = DEJA DE CONTAR
--------------------------
`app.boveda_cfdi.servicio.comprobantes_vigentes(consulta)` es el filtro que deben usar los
cálculos (Fiscalito, Contabilito, la anual). Desde P2-03, al detectar una cancelación nueva
se cancela su póliza automática (o se genera la reversa si su mes está cerrado), con
`app.contabilidad.polizas.cancelar_por_cfdi`.

RITMO
-----
El SAT no publica un límite, pero bloquea ráfagas. `FISCALITO_SAT_ESTATUS_CONCURRENCIA`
(default 4 consultas simultáneas) y `FISCALITO_SAT_ESTATUS_POR_SEGUNDO` (default 5) lo
controlan; `FISCALITO_SAT_ESTATUS_LOTE` (default 1000) es cuántos CFDI hace un trabajo antes
de encolar su continuación.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.contabilidad.polizas import cancelar_por_cfdi_o_alertar
from app.integraciones.sat_estatus import EstatusCfdi, ExpresionCfdi, SatEstatus
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import VerificacionCfdi


def _entero(variable: str, default: int, minimo: int = 1) -> int:
    try:
        return max(minimo, int(os.environ.get(variable, "") or default))
    except ValueError:
        return default


def concurrencia() -> int:
    return _entero("FISCALITO_SAT_ESTATUS_CONCURRENCIA", 4)


def por_segundo() -> float:
    try:
        valor = float(os.environ.get("FISCALITO_SAT_ESTATUS_POR_SEGUNDO", "") or 5)
    except ValueError:
        valor = 5.0
    return max(valor, 0.1)


def tamano_lote() -> int:
    return _entero("FISCALITO_SAT_ESTATUS_LOTE", 1000)


class Ritmo:
    """Espacia las llamadas a `por_segundo` por segundo, entre todos los hilos."""

    def __init__(
        self,
        por_segundo: float,
        reloj: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.intervalo = 1.0 / por_segundo
        self.reloj = reloj
        self.dormir = dormir
        self._siguiente = 0.0
        self._candado = threading.Lock()

    def esperar(self) -> None:
        with self._candado:
            ahora = self.reloj()
            turno = max(ahora, self._siguiente)
            self._siguiente = turno + self.intervalo
        if turno > ahora:
            self.dormir(turno - ahora)


@dataclass
class ResultadoVerificacion:
    consultados: int = 0
    vigentes: int = 0
    cancelados: int = 0
    nuevos_cancelados: int = 0
    no_encontrados: int = 0
    en_proceso: int = 0
    errores: int = 0
    pendientes: int = 0
    reversas_fallidas: int = 0
    detalle_errores: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "detalle_errores"}
        if self.detalle_errores:
            d["errores_muestra"] = self.detalle_errores[:3]
        return d


def expresion_de(c: Comprobante) -> ExpresionCfdi:
    return ExpresionCfdi(uuid=c.uuid, rfc_emisor=c.rfc_emisor, rfc_receptor=c.rfc_receptor,
                         total=c.total)


def _condiciones(cliente: Cliente, desde: date, hasta: date, corte: datetime) -> list[Any]:
    # Con zona: Postgres compara timestamptz bien; el DateTime de SQLite guarda y compara el
    # texto sin offset, y como todo `fecha_estatus` se escribe en UTC, cuadra igual.
    corte_utc = corte.astimezone(UTC)
    return [
        Comprobante.cliente_id == cliente.id,
        Comprobante.fecha >= datetime.combine(desde, dtime.min),
        Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), dtime.min),
        Comprobante.estatus_sat != "cancelado",
        or_(Comprobante.fecha_estatus.is_(None), Comprobante.fecha_estatus < corte_utc),
    ]


def por_verificar(
    db: Session, cliente: Cliente, desde: date, hasta: date, corte: datetime,
    limite: int | None = None,
) -> tuple[list[Comprobante], int]:
    """Los comprobantes que faltan (hasta `limite`) y cuántos faltan en total."""
    cond = _condiciones(cliente, desde, hasta, corte)
    total = db.scalar(select(func.count(Comprobante.id)).where(*cond)) or 0
    consulta = select(Comprobante).where(*cond).order_by(Comprobante.fecha.desc(),
                                                         Comprobante.id)
    if limite:
        consulta = consulta.limit(limite)
    return list(db.scalars(consulta)), int(total)


def _aplicar(db: Session, c: Comprobante, est: EstatusCfdi, momento: datetime,
             r: ResultadoVerificacion) -> None:
    previo = c.estatus_sat
    if est.encontrado and est.resumen in ("vigente", "cancelado"):
        c.estatus_sat = est.resumen
    else:
        r.no_encontrados += 1
    c.fecha_estatus = momento
    if c.estatus_sat == "cancelado":
        r.cancelados += 1
        if previo != "cancelado":
            r.nuevos_cancelados += 1
            # P2-03: la póliza del CFDI deja de contar (o se revierte si su mes se cerró).
            # Si no se puede (periodo de la reversa cerrado u otro error), queda una alerta
            # consultable; el estatus se guarda igual y el generador lo reintenta.
            if cancelar_por_cfdi_o_alertar(db, c) == "alerta":
                r.reversas_fallidas += 1
    elif c.estatus_sat == "vigente":
        r.vigentes += 1
    if est.en_proceso_de_cancelacion:
        r.en_proceso += 1
    v = db.get(VerificacionCfdi, c.id)
    if v is None:
        v = VerificacionCfdi(comprobante_id=c.id)
        db.add(v)
    v.codigo_estatus = est.codigo_estatus[:200]
    v.estado = est.estado[:40]
    v.es_cancelable = est.es_cancelable[:60]
    v.estatus_cancelacion = est.estatus_cancelacion[:60]
    v.validacion_efos = est.validacion_efos[:20]
    v.consultado_en = momento


def verificar(
    db: Session,
    comprobantes: list[Comprobante],
    adaptador: SatEstatus,
    *,
    hilos: int | None = None,
    ritmo: Ritmo | None = None,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ResultadoVerificacion:
    """
    Consulta cada comprobante y actualiza la bóveda. Las llamadas al SAT van en paralelo
    (sólo red); las escrituras a la base, en este hilo.
    """
    r = ResultadoVerificacion()
    if not comprobantes:
        return r
    ritmo = ritmo or Ritmo(por_segundo())

    def consultar(expr: ExpresionCfdi) -> EstatusCfdi | Exception:
        ritmo.esperar()
        try:
            return adaptador.consultar(expr)
        except Exception as e:  # noqa: BLE001 — se cuenta por CFDI, no tumba el lote
            return e

    expresiones = [expresion_de(c) for c in comprobantes]
    with ThreadPoolExecutor(max_workers=hilos or concurrencia()) as ejecutor:
        respuestas = list(ejecutor.map(consultar, expresiones))

    for c, resp in zip(comprobantes, respuestas, strict=True):
        if isinstance(resp, Exception):
            r.errores += 1
            r.detalle_errores.append(f"{c.uuid}: {getattr(resp, 'message', resp)}")
            continue
        r.consultados += 1
        _aplicar(db, c, resp, ahora(), r)
    db.flush()
    return r


def verificar_cliente(
    db: Session,
    cliente: Cliente,
    desde: date,
    hasta: date,
    corte: datetime,
    adaptador: SatEstatus,
    *,
    limite: int | None = None,
    hilos: int | None = None,
    ritmo: Ritmo | None = None,
) -> ResultadoVerificacion:
    """Un lote de los comprobantes que faltan del cliente; `pendientes` = lo que queda."""
    lote, total = por_verificar(db, cliente, desde, hasta, corte, limite or tamano_lote())
    r = verificar(db, lote, adaptador, hilos=hilos, ritmo=ritmo)
    r.pendientes = max(total - len(lote), 0)
    return r


def detalle(db: Session, comprobante_ids: list[int]) -> dict[int, VerificacionCfdi]:
    """Las verificaciones de una página de la bóveda, por id de comprobante."""
    if not comprobante_ids:
        return {}
    filas = db.scalars(select(VerificacionCfdi).where(
        VerificacionCfdi.comprobante_id.in_(comprobante_ids)))
    return {v.comprobante_id: v for v in filas}
