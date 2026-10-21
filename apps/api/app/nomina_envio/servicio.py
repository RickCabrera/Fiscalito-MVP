"""
Envío de recibos de una nómina cerrada (P4-13): a quién, por dónde, y el trabajo que envía.

IDEMPOTENCIA (el trabajo puede correr dos veces)
------------------------------------------------
- `preparar` crea UN renglón por (recibo, canal) y nunca toca los `enviado` ni `rebotado`.
- `enviar_lote` sólo manda `pendiente` y `fallido` con intentos disponibles, y **asienta cada
  recibo con commit** apenas sale: si el worker muere a la mitad, lo ya enviado no se repite.
  Queda una ventana mínima —entre que el proveedor acepta y el commit— en la que un caído
  podría reenviar ése uno; es la garantía que permite un proveedor sin llave de idempotencia.
- Si quedan fallidos con intentos, el trabajo levanta al final y la cola lo reprograma con
  backoff; en ese reintento los ya enviados no se vuelven a mandar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import nomina_servicio as srv
from app.db.base import ahora
from app.dispersion.servicio import exigir_cerrada
from app.integraciones import registro
from app.integraciones.correo import Adjunto
from app.integraciones.whatsapp import DocumentoPlantilla
from app.modelos.auditoria import EventoAuditoria
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nomina_envio import EnvioRecibo
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.nomina_envio import enlaces, plantillas
from app.nomina_envio.documentos import Documentos, documentos_del_recibo
from app.schemas.empleado import EmpleadoCarteraSchema
from app.trabajos.cola import encolar

TIPO_TRABAJO = "nomina.enviar_recibos"
MAX_INTENTOS_RECIBO = 3


@dataclass(frozen=True)
class Omitido:
    empleado_no: str
    nombre: str
    motivo: str


def destino(ficha: EmpleadoCarteraSchema | None, canal: str) -> tuple[str, str]:
    """(destino, motivo). Con motivo no vacío, ese recibo no se manda por ese canal."""
    if ficha is None:
        return "", "El empleado ya no está (o no es legible) en la cartera."
    if canal == "correo":
        return (ficha.correo, "") if ficha.correo else ("", "Sin correo capturado en su ficha.")
    if not ficha.celular:
        return "", "Sin celular capturado en su ficha."
    if not ficha.consentimiento_whatsapp:
        return "", "No ha dado su consentimiento para recibir sus recibos por WhatsApp."
    return ficha.celular, ""


def clave_trabajo(periodo_id: int, canal: str) -> str:
    return f"{TIPO_TRABAJO}:{periodo_id}:{canal}"


def envios_de(db: Session, periodo: NominaPeriodo, canal: str) -> list[EnvioRecibo]:
    return list(db.scalars(select(EnvioRecibo).where(
        EnvioRecibo.periodo_id == periodo.id, EnvioRecibo.canal == canal
    ).order_by(EnvioRecibo.empleado_no)))


def preparar(db: Session, despacho_id: str, cliente: Cliente, periodo: NominaPeriodo,
             canal: str) -> tuple[list[EnvioRecibo], list[Omitido]]:
    """Crea (o reactiva) los envíos del periodo por el canal. No manda nada."""
    exigir_cerrada(periodo)
    fichas = {f.empleado_no: f for f in srv.fichas_del_cliente(db, cliente)[0]}
    existentes = {e.recibo_id: e for e in envios_de(db, periodo, canal)}
    omitidos: list[Omitido] = []
    for r in srv.recibos_de(db, periodo):
        a, motivo = destino(fichas.get(r.empleado_no), canal)
        if motivo:
            omitidos.append(Omitido(r.empleado_no, r.nombre, motivo))
            continue
        e = existentes.get(r.id)
        if e is None:
            db.add(EnvioRecibo(despacho_id=despacho_id, cliente_id=cliente.id,
                               periodo_id=periodo.id, recibo_id=r.id,
                               empleado_no=r.empleado_no, canal=canal, destino=a,
                               estado="pendiente", intentos=0))
        elif e.estado == "fallido":  # pedirlo otra vez es pedir que se reintente
            e.estado, e.intentos, e.destino, e.error = "pendiente", 0, a, ""
        elif e.estado == "pendiente":
            e.destino = a
    db.flush()
    return envios_de(db, periodo, canal), omitidos


def omitidos_de(db: Session, cliente: Cliente, periodo: NominaPeriodo, canal: str,
                ) -> list[Omitido]:
    fichas = {f.empleado_no: f for f in srv.fichas_del_cliente(db, cliente)[0]}
    con_envio = {e.recibo_id for e in envios_de(db, periodo, canal)}
    salida = []
    for r in srv.recibos_de(db, periodo):
        _, motivo = destino(fichas.get(r.empleado_no), canal)
        if motivo and r.id not in con_envio:
            salida.append(Omitido(r.empleado_no, r.nombre, motivo))
    return salida


def encolar_envio(db: Session, despacho_id: str, cliente: Cliente, periodo: NominaPeriodo,
                  canal: str) -> Trabajo:
    return encolar(db, TIPO_TRABAJO, {"periodo_id": periodo.id, "canal": canal},
                   despacho_id=despacho_id, cliente_id=cliente.id,
                   clave_unica=clave_trabajo(periodo.id, canal))


def ultimo_trabajo(db: Session, periodo_id: int, canal: str) -> Trabajo | None:
    return db.scalar(select(Trabajo).where(Trabajo.clave_unica == clave_trabajo(periodo_id, canal))
                     .order_by(Trabajo.id.desc()).limit(1))


def valores(periodo: NominaPeriodo, recibo: ReciboNomina) -> dict[str, str]:
    return {"nombre": recibo.nombre or recibo.empleado_no,
            "periodo": f"{periodo.inicio:%d/%m/%Y} al {periodo.fin:%d/%m/%Y}",
            "neto": f"${Decimal(recibo.neto):,.2f}"}


def enviar_uno(e: EnvioRecibo, docs: Documentos, plantilla: dict[str, str],
               vals: dict[str, str]) -> str:
    """Manda un recibo por su canal y devuelve el id del mensaje del proveedor."""
    if e.canal == "correo":
        adjuntos = []
        if docs.pdf is not None:
            adjuntos.append(Adjunto(f"{docs.nombre_base}.pdf", docs.pdf, "application/pdf"))
        if docs.xml is not None:
            adjuntos.append(Adjunto(f"{docs.nombre_base}.xml", docs.xml, "application/xml"))
        return registro.obtener("correo").enviar(
            [e.destino], plantillas.renderizar(plantilla["asunto"], vals),
            plantillas.renderizar(plantilla["cuerpo"], vals, escapar=True), adjuntos)
    if not plantilla.get("plantilla_whatsapp"):
        raise ValueError("Falta el nombre de la plantilla de WhatsApp aprobada por Meta.")
    archivo, ext = ("recibo.pdf", "pdf") if docs.pdf is not None else ("recibo.xml", "xml")
    return registro.obtener("whatsapp").enviar_plantilla(
        e.destino, plantilla["plantilla_whatsapp"], plantilla.get("idioma") or "es_MX",
        [vals["nombre"], vals["periodo"], vals["neto"]],
        documento=DocumentoPlantilla(enlaces.url_firmada(e.id, archivo),
                                     f"{docs.nombre_base}.{ext}"))


def enviar_lote(db: Session, despacho_id: str, periodo_id: int, canal: str) -> dict[str, Any]:
    """El cuerpo del trabajo. Ver encabezado: commit por recibo, sin duplicar."""
    periodo = db.get(NominaPeriodo, periodo_id)
    if periodo is None or periodo.despacho_id != despacho_id:
        return {"enviados": 0, "fallidos": 0, "nota": "El periodo ya no existe."}
    cliente = db.get(Cliente, periodo.cliente_id)
    assert cliente is not None
    plantilla = plantillas.de_despacho(db, despacho_id, canal)
    por_mandar = [e for e in envios_de(db, periodo, canal)
                  if e.estado == "pendiente"
                  or (e.estado == "fallido" and e.intentos < MAX_INTENTOS_RECIBO)]
    enviados = fallidos = 0
    for e in por_mandar:
        recibo = db.get(ReciboNomina, e.recibo_id)
        assert recibo is not None
        try:
            docs = documentos_del_recibo(db, cliente, periodo, recibo)
            e.id_mensaje = str(enviar_uno(e, docs, plantilla, valores(periodo, recibo)))[:200]
            e.estado, e.error, e.enviado_en, e.timbrado = "enviado", "", ahora(), docs.timbrado
            enviados += 1
        except Exception as exc:  # noqa: BLE001 — se guarda por recibo y se reintenta
            e.estado, e.error = "fallido", f"{type(exc).__name__}: {exc}"[:500]
            fallidos += 1
        e.intentos += 1
        db.commit()
    db.add(EventoAuditoria(
        despacho_id=despacho_id, uid="worker", cliente_id=cliente.id, cliente_clave=cliente.clave,
        accion="nomina.recibos.enviados", entidad="nomina_periodo", entidad_id=str(periodo.id),
        detalle={"canal": canal, "enviados": enviados, "fallidos": fallidos}))
    db.commit()
    reintentables = db.scalar(select(func.count()).select_from(EnvioRecibo).where(
        EnvioRecibo.periodo_id == periodo.id, EnvioRecibo.canal == canal,
        EnvioRecibo.estado == "fallido", EnvioRecibo.intentos < MAX_INTENTOS_RECIBO))
    if reintentables:
        raise RuntimeError(f"{reintentables} recibos fallaron; se reintentan con backoff.")
    return {"enviados": enviados, "fallidos": fallidos}
