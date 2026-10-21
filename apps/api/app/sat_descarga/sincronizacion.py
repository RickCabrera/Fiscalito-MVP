"""
Sincronización diaria, descarga por rango y bitácora por día (P1-02).

QUÉ SE PIDE POR CADA RANGO
--------------------------
Según la configuración del cliente (`ConfigDescargaSat`; sin configuración, todo encendido):

| Interruptor | Solicitud al SAT |
|---|---|
| emitidos   | XML emitidos (vigentes; también cancelados si `cancelados`) |
| recibidos  | XML recibidos, SÓLO vigentes (el SAT 1.5 no entrega XML recibidos cancelados) |
| metadata   | Metadata de emitidos y/o recibidos, vigentes y cancelados |
| cancelados | Metadata aunque `metadata` esté apagado: es la única forma de ver cancelados |

Un rango largo se parte por MES (una solicitud por mes y tipo): el SAT entrega hasta 200,000
XML por solicitud y un mes rara vez los rebasa; si los rebasa (5003) la solicitud se parte
sola (`servicio._dividir`).

DIARIA
------
Cada 15 minutos el worker revisa qué clientes activos ya pasaron su hora (default 02:00 en la
Ciudad de México) y encola `sat.descarga.rango` del DÍA ANTERIOR con clave única
`sat.diaria:<cliente>:<día>`. Sin e.firma vigente la configuración se pausa
(`pausada_por="efirma"`) y queda una alerta `sin_efirma`; al volver a tener e.firma se
reanuda sola.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.credenciales.certificados import NOMBRE_TIPO
from app.modelos.cfdi import Comprobante
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import (
    ESTADOS_VIVOS_SOLICITUD,
    AlertaDescargaSat,
    ConfigDescargaSat,
    MetadataCfdiSat,
    SolicitudDescargaSat,
)
from app.sat_descarga.servicio import (
    Pedido,
    alertar,
    crear_o_reusar,
    fin_dia,
    inicio_dia,
    reloj,
    ventanas_por_mes,
)
from app.trabajos import encolar

ZONA = ZoneInfo("America/Mexico_City")
HORA_DEFAULT = "02:00"


# ── configuración ──


def config_de(db: Session, cliente: Cliente) -> ConfigDescargaSat:
    """La configuración del cliente (sin guardarla si no existe: defaults en memoria)."""
    cfg = db.scalar(select(ConfigDescargaSat).where(ConfigDescargaSat.cliente_id == cliente.id))
    if cfg is None:
        cfg = ConfigDescargaSat(
            cliente_id=cliente.id, activa=False, emitidos=True, recibidos=True,
            metadata_=True, cancelados=True, desde=None, hora=HORA_DEFAULT, pausada_por="",
        )
    return cfg


def guardar_config(db: Session, cliente: Cliente, cambios: dict[str, Any]) -> ConfigDescargaSat:
    cfg = config_de(db, cliente)
    if cfg.id is None:
        db.add(cfg)
    for campo in ("activa", "emitidos", "recibidos", "cancelados", "desde", "hora"):
        if campo in cambios and cambios[campo] is not None:
            setattr(cfg, campo, cambios[campo])
    if cambios.get("metadata") is not None:
        cfg.metadata_ = cambios["metadata"]
    if cfg.activa:
        revisar_efirma(db, cliente, cfg)
    db.flush()
    return cfg


def _a_utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def estado_efirma(db: Session, cliente: Cliente, momento: datetime | None = None) -> dict:
    """Si el cliente tiene e.firma vigente (sin descifrarla)."""
    ahora = momento or datetime.now(UTC)
    cred = db.scalar(select(CredencialCliente).where(
        CredencialCliente.cliente_id == cliente.id, CredencialCliente.tipo == "efirma",
        CredencialCliente.activo.is_(True),
    ).order_by(CredencialCliente.id.desc()))
    if cred is None:
        return {"vigente": False, "valido_hasta": None,
                "mensaje": f"El cliente no tiene {NOMBRE_TIPO['efirma']} cargada. Súbela en "
                           "su ficha para descargar del SAT."}
    hasta = _a_utc(cred.valido_hasta)
    if hasta <= ahora:
        return {"vigente": False, "valido_hasta": hasta.isoformat(),
                "mensaje": f"La e.firma del cliente venció el {hasta.date().isoformat()}. "
                           "Sube la nueva en su ficha."}
    return {"vigente": True, "valido_hasta": hasta.isoformat(), "mensaje": ""}


def revisar_efirma(db: Session, cliente: Cliente, cfg: ConfigDescargaSat) -> bool:
    """Pausa (y alerta) sin e.firma vigente; reanuda si ya la hay. True si puede correr."""
    estado = estado_efirma(db, cliente)
    if not estado["vigente"]:
        if cfg.pausada_por != "efirma":
            cfg.pausada_por = "efirma"
        alertar(db, cliente.id, "sin_efirma", estado["mensaje"])
        return False
    if cfg.pausada_por == "efirma":
        cfg.pausada_por = ""
    for a in db.scalars(select(AlertaDescargaSat).where(
        AlertaDescargaSat.cliente_id == cliente.id, AlertaDescargaSat.tipo == "sin_efirma",
        AlertaDescargaSat.resuelta.is_(False),
    )):
        a.resuelta = True
    return True


# ── qué se pide ──


class Seleccion:
    """Qué tipos de solicitud se crean para un rango."""

    def __init__(self, emitidos: bool = True, recibidos: bool = True, metadata: bool = True,
                 cancelados: bool = True) -> None:
        self.emitidos, self.recibidos = emitidos, recibidos
        self.metadata, self.cancelados = metadata, cancelados

    @classmethod
    def de_config(cls, cfg: ConfigDescargaSat) -> Seleccion:
        return cls(cfg.emitidos, cfg.recibidos, cfg.metadata_, cfg.cancelados)

    def como_dict(self) -> dict[str, bool]:
        return {"emitidos": self.emitidos, "recibidos": self.recibidos,
                "metadata": self.metadata, "cancelados": self.cancelados}

    def pedidos(self, inicio: datetime, fin: datetime) -> list[Pedido]:
        p: list[Pedido] = []
        if self.emitidos:
            p.append(Pedido("emitidos", "cfdi", inicio, fin,
                            "todos" if self.cancelados else "vigentes"))
        if self.recibidos:
            p.append(Pedido("recibidos", "cfdi", inicio, fin, "vigentes"))
        if self.metadata or self.cancelados:
            if self.emitidos or not self.recibidos:
                p.append(Pedido("emitidos", "metadata", inicio, fin, "todos"))
            if self.recibidos or not self.emitidos:
                p.append(Pedido("recibidos", "metadata", inicio, fin, "todos"))
        return p


def crear_rango(
    db: Session, cliente: Cliente, inicio: datetime, fin: datetime, sel: Seleccion,
    origen: str,
) -> list[SolicitudDescargaSat]:
    """Crea (o reusa) las solicitudes del rango y encola su avance. Idempotente."""
    salida = []
    for pedido in sel.pedidos(inicio, fin):
        s, _nueva = crear_o_reusar(db, cliente, pedido, origen=origen)
        salida.append(s)
        encolar_avance(db, cliente, s)
    return salida


def encolar_avance(db: Session, cliente: Cliente, s: SolicitudDescargaSat,
                   cuando: datetime | None = None) -> None:
    if s.estado not in ESTADOS_VIVOS_SOLICITUD:
        return
    encolar(db, "sat.descarga.avanzar", {"solicitud_id": s.id},
            despacho_id=cliente.despacho_id, cliente_id=cliente.id,
            ejecutar_en=cuando or s.proxima_verificacion or reloj(),
            clave_unica=f"sat.solicitud:{s.id}", max_intentos=3)


def encolar_meses(
    db: Session, cliente: Cliente, desde: date, hasta: date, sel: Seleccion, origen: str,
) -> list[dict[str, Any]]:
    """Un trabajo `sat.descarga.rango` por mes del rango. Devuelve qué se encoló."""
    salida = []
    for ini, fin in ventanas_por_mes(desde, hasta):
        clave = f"sat.rango:{cliente.id}:{origen}:{ini.date()}:{fin.date()}"
        t = encolar(db, "sat.descarga.rango",
                    {"inicio": ini.isoformat(), "fin": fin.isoformat(), "origen": origen,
                     "seleccion": sel.como_dict()},
                    despacho_id=cliente.despacho_id, cliente_id=cliente.id,
                    clave_unica=clave, max_intentos=3)
        salida.append({"trabajo_id": t.id, "inicio": ini.date().isoformat(),
                       "fin": fin.date().isoformat()})
    return salida


# ── diaria ──


def _hora(texto: str) -> time:
    try:
        h, m = texto.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return time(2, 0)


def encolar_diarias(db: Session, momento: datetime) -> list[int]:
    """
    Clientes activos que ya pasaron su hora y no tienen encolado el día anterior.
    Devuelve los ids de cliente encolados.
    """
    local = momento.astimezone(ZONA)
    ayer = local.date() - timedelta(days=1)
    encolados = []
    for cfg in db.scalars(select(ConfigDescargaSat).where(ConfigDescargaSat.activa.is_(True))):
        if local.time() < _hora(cfg.hora):
            continue
        if cfg.ultimo_dia_encolado is not None and cfg.ultimo_dia_encolado >= ayer:
            continue
        cliente = db.get(Cliente, cfg.cliente_id)
        if cliente is None:
            continue
        if not revisar_efirma(db, cliente, cfg):
            continue
        if cfg.desde is not None and ayer < cfg.desde:
            cfg.ultimo_dia_encolado = ayer
            continue
        encolar(db, "sat.descarga.rango",
                {"inicio": inicio_dia(ayer).isoformat(), "fin": fin_dia(ayer).isoformat(),
                 "origen": "diaria", "seleccion": Seleccion.de_config(cfg).como_dict()},
                despacho_id=cliente.despacho_id, cliente_id=cliente.id, ejecutar_en=momento,
                clave_unica=f"sat.diaria:{cliente.id}:{ayer.isoformat()}", max_intentos=3)
        cfg.ultimo_dia_encolado = ayer
        encolados.append(cliente.id)
    db.flush()
    return encolados


# ── bitácora ──

ORDEN = {"fallido": 4, "en_proceso": 3, "completo": 2, "sin_movimientos": 1}


def _estado_de(s: SolicitudDescargaSat) -> str:
    if s.estado == "fallida":
        return "fallido"
    if s.estado in ESTADOS_VIVOS_SOLICITUD:
        return "en_proceso"
    if s.estado == "sin_datos":
        return "sin_movimientos"
    return "completo"


def bitacora(db: Session, cliente: Cliente, anio: int, mes: int) -> list[dict[str, Any]]:
    """
    Un renglón por día del mes: `estado` (completo | en_proceso | sin_movimientos | fallido |
    no_solicitado) y conteos de la bóveda y de la metadata de ese día.

    Un día lo cubren todas las solicitudes cuyo rango lo toca (las `dividida` no cuentan:
    las cubren sus hijas). Manda el peor estado; un día es "sin movimientos" sólo si TODAS
    las que lo cubren respondieron que no había información.
    """
    dias = calendar.monthrange(anio, mes)[1]
    primero, ultimo = date(anio, mes, 1), date(anio, mes, dias)
    sols = list(db.scalars(select(SolicitudDescargaSat).where(
        SolicitudDescargaSat.cliente_id == cliente.id,
        SolicitudDescargaSat.estado != "dividida",
        SolicitudDescargaSat.fecha_inicial <= fin_dia(ultimo),
        SolicitudDescargaSat.fecha_final >= inicio_dia(primero),
    )))
    por_dia: dict[date, list[SolicitudDescargaSat]] = defaultdict(list)
    for s in sols:
        d = max(s.fecha_inicial.date(), primero)
        while d <= min(s.fecha_final.date(), ultimo):
            por_dia[d].append(s)
            d += timedelta(days=1)

    dia_cfdi = func.date(Comprobante.fecha)
    conteos: dict[tuple[str, str], int] = {}
    for d, direccion, n in db.execute(
        select(dia_cfdi, Comprobante.direccion, func.count(Comprobante.id))
        .where(Comprobante.cliente_id == cliente.id,
               Comprobante.fecha >= inicio_dia(primero),
               Comprobante.fecha <= fin_dia(ultimo))
        .group_by(dia_cfdi, Comprobante.direccion)
    ):
        conteos[(str(d)[:10], direccion)] = int(n)
    dia_meta = func.date(MetadataCfdiSat.fecha_emision)
    meta: dict[tuple[str, str], int] = {}
    for d, est, n in db.execute(
        select(dia_meta, MetadataCfdiSat.estatus, func.count(MetadataCfdiSat.id))
        .where(MetadataCfdiSat.cliente_id == cliente.id,
               MetadataCfdiSat.fecha_emision >= inicio_dia(primero),
               MetadataCfdiSat.fecha_emision <= fin_dia(ultimo))
        .group_by(dia_meta, MetadataCfdiSat.estatus)
    ):
        meta[(str(d)[:10], est)] = int(n)

    salida = []
    for n in range(1, dias + 1):
        d = date(anio, mes, n)
        clave = d.isoformat()
        cubren = por_dia.get(d, [])
        if not cubren:
            estado = "no_solicitado"
        else:
            estado = max((_estado_de(s) for s in cubren), key=lambda e: ORDEN[e])
        mensaje = next((s.mensaje for s in cubren if s.estado == "fallida"), "")
        salida.append({
            "fecha": clave, "estado": estado, "solicitudes": len(cubren),
            "emitidos": conteos.get((clave, "emitido"), 0),
            "recibidos": conteos.get((clave, "recibido"), 0),
            "metadata": meta.get((clave, "vigente"), 0) + meta.get((clave, "cancelado"), 0),
            "cancelados": meta.get((clave, "cancelado"), 0),
            "mensaje": mensaje,
        })
    return salida


def alertas_abiertas(db: Session, cliente: Cliente) -> list[dict[str, Any]]:
    return [
        {"id": a.id, "tipo": a.tipo, "mensaje": a.mensaje, "solicitud_id": a.solicitud_id,
         "creado_en": a.creado_en.isoformat() if a.creado_en else None}
        for a in db.scalars(select(AlertaDescargaSat).where(
            AlertaDescargaSat.cliente_id == cliente.id, AlertaDescargaSat.resuelta.is_(False),
        ).order_by(AlertaDescargaSat.id.desc()))
    ]
