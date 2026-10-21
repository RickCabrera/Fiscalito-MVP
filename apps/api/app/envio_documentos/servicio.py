"""
Envío de documentos al cliente (P5-05): contactos, expediente subido, envíos y el trabajo.

REUSO DE P4-13
--------------
Mismos adaptadores (`registro.obtener("correo" | "whatsapp")`), mismo enlace firmado para que
WhatsApp baje el archivo (`nomina_envio.enlaces`, ámbito `documentos`) y el mismo ciclo de
estados con reintentos: `preparar` deja un renglón `pendiente` por (documento, contacto, canal),
el trabajo `documentos.enviar` (uno vivo por cliente) manda pendientes y fallidos con intentos,
y ASIENTA CADA ENVÍO CON COMMIT: si el worker muere a la mitad, lo enviado no se repite. Si
quedan fallidos con intentos (o pendientes que llegaron mientras corría), el trabajo levanta al
final y la cola lo reintenta con backoff.

WHATSAPP
--------
Fuera de la ventana de 24 h sólo sale una PLANTILLA APROBADA por Meta. Su nombre es
`FISCALITO_WHATSAPP_PLANTILLA_DOCUMENTOS` (default `documento_cliente`, idioma es_MX), con dos
parámetros {{1}} nombre del contacto y {{2}} descripción del documento, y el documento como
encabezado (PDF si hay, si no el XML). Sin consentimiento registrado del contacto no sale nada.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.db.base import ahora
from app.envio_documentos import documentos
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.almacenamiento import obtener_almacenamiento
from app.integraciones.correo import Adjunto
from app.integraciones.whatsapp import DocumentoPlantilla
from app.modelos.auditoria import EventoAuditoria
from app.modelos.envio_documentos import (
    TIPOS_SUBIDOS,
    ContactoCliente,
    DocumentoCliente,
    EnvioDocumento,
)
from app.modelos.nucleo import Cliente, Despacho
from app.modelos.trabajos import Trabajo
from app.nomina_envio import enlaces
from app.tenancy import Contexto
from app.trabajos.cola import encolar

TIPO_TRABAJO = "documentos.enviar"
MAX_INTENTOS = 3
CANALES = ("correo", "whatsapp")
TAMANO_MAXIMO = 10 * 1024 * 1024
TELEFONO = re.compile(r"^[0-9]{10,15}$")
MIMES = {"application/pdf": ".pdf", "application/xml": ".xml", "text/xml": ".xml"}


def plantilla_whatsapp() -> str:
    return os.environ.get("FISCALITO_WHATSAPP_PLANTILLA_DOCUMENTOS", "").strip() or \
        "documento_cliente"


# ── contactos ──


def contactos(db: Session, cliente: Cliente, solo_activos: bool = False) -> list[ContactoCliente]:
    q = select(ContactoCliente).where(ContactoCliente.cliente_id == cliente.id)
    if solo_activos:
        q = q.where(ContactoCliente.activo.is_(True))
    return list(db.scalars(q.order_by(ContactoCliente.nombre, ContactoCliente.id)))


def contacto_de(db: Session, cliente: Cliente, contacto_id: int) -> ContactoCliente:
    c = db.get(ContactoCliente, contacto_id)
    if c is None or c.cliente_id != cliente.id:
        raise FiscalAgentError("No existe ese contacto en este cliente.", 404)
    return c


def guardar_contacto(ctx: Contexto, cliente: Cliente, datos: dict[str, Any],
                     contacto_id: int | None = None) -> ContactoCliente:
    tel = re.sub(r"\D", "", str(datos.get("telefono") or ""))
    if tel and not TELEFONO.match(tel):
        raise FiscalAgentError("El celular va con lada internacional, de 10 a 15 dígitos.", 422)
    if not datos.get("correo") and not tel:
        raise FiscalAgentError("Captura al menos un correo o un celular.", 422)
    if datos.get("consentimiento_whatsapp") and not tel:
        raise FiscalAgentError("El consentimiento de WhatsApp necesita un celular.", 422)
    if contacto_id is None:
        c = ContactoCliente(despacho_id=ctx.despacho_id, cliente_id=cliente.id)
        ctx.db.add(c)
    else:
        c = contacto_de(ctx.db, cliente, contacto_id)
    antes = c.consentimiento_whatsapp
    c.nombre, c.puesto = str(datos["nombre"]).strip(), str(datos.get("puesto") or "").strip()
    c.correo, c.telefono = str(datos.get("correo") or "").strip().lower(), tel
    c.activo = bool(datos.get("activo", True))
    c.consentimiento_whatsapp = bool(datos.get("consentimiento_whatsapp"))
    if c.consentimiento_whatsapp and not antes:
        c.consentimiento_en, c.consentimiento_por = ahora(), ctx.uid
    elif not c.consentimiento_whatsapp:
        c.consentimiento_en, c.consentimiento_por = None, ""
    ctx.db.flush()
    registrar(ctx, "documentos.contacto", "contacto_cliente", c.id,
              {"nombre": c.nombre, "consentimiento_whatsapp": c.consentimiento_whatsapp},
              cliente)
    return c


def borrar_contacto(ctx: Contexto, cliente: Cliente, contacto_id: int) -> None:
    c = contacto_de(ctx.db, cliente, contacto_id)
    ctx.db.delete(c)
    ctx.db.flush()
    registrar(ctx, "documentos.contacto_borrado", "contacto_cliente", contacto_id, {}, cliente)


def contacto_json(c: ContactoCliente) -> dict[str, Any]:
    return {"id": c.id, "nombre": c.nombre, "puesto": c.puesto, "correo": c.correo,
            "telefono": c.telefono, "consentimiento_whatsapp": c.consentimiento_whatsapp,
            "consentimiento_en": c.consentimiento_en.isoformat() if c.consentimiento_en
            else None, "activo": c.activo}


# ── expediente subido (declaraciones, acuses, otros) ──


def subir(ctx: Contexto, cliente: Cliente, tipo: str, descripcion: str, periodo: str,
          nombre: str, mime: str, contenido: bytes) -> DocumentoCliente:
    if tipo not in TIPOS_SUBIDOS:
        raise FiscalAgentError("Tipo: declaracion, acuse u otro.", 422)
    if not contenido or len(contenido) > TAMANO_MAXIMO:
        raise FiscalAgentError("El archivo está vacío o pesa más de 10 MB.", 422)
    if contenido[:4] == b"%PDF":
        mime = "application/pdf"
    elif contenido.lstrip()[:1] == b"<":
        mime = "application/xml"
    else:
        raise FiscalAgentError("Sólo se suben PDF o XML.", 422)
    if periodo and not re.match(r"^[0-9]{4}-(0[1-9]|1[0-2])$", periodo):
        raise FiscalAgentError("El periodo va como AAAA-MM.", 422)
    huella = hashlib.sha256(contenido).hexdigest()
    limpio = re.sub(r"[^A-Za-z0-9._-]", "_", nombre or "documento")[:120]
    if not limpio.lower().endswith(MIMES[mime]):
        limpio += MIMES[mime]
    ruta = obtener_almacenamiento().guardar(
        contenido, f"expediente/{cliente.despacho_id}/{cliente.id}/{huella[:16]}-{limpio}")
    d = DocumentoCliente(despacho_id=ctx.despacho_id, cliente_id=cliente.id, tipo=tipo,
                         descripcion=descripcion.strip()[:300], periodo=periodo,
                         nombre_archivo=limpio, mime=mime, ruta=ruta, sha256=huella,
                         tamano=len(contenido), creado_por=ctx.uid)
    ctx.db.add(d)
    ctx.db.flush()
    registrar(ctx, "documentos.subir", "documento_cliente", d.id,
              {"tipo": tipo, "archivo": limpio, "sha256": huella}, cliente)
    return d


# ── envíos ──


@dataclass(frozen=True)
class Omitido:
    contacto: str
    canal: str
    motivo: str


def destino(c: ContactoCliente, canal: str) -> tuple[str, str]:
    """(destino, motivo). Con motivo, ese contacto no recibe por ese canal."""
    if not c.activo:
        return "", "Contacto inactivo."
    if canal == "correo":
        return (c.correo, "") if c.correo else ("", "Sin correo capturado.")
    if not c.telefono:
        return "", "Sin celular capturado."
    if not c.consentimiento_whatsapp:
        return "", "No ha dado su consentimiento para recibir documentos por WhatsApp."
    return c.telefono, ""


def clave_trabajo(cliente_id: int) -> str:
    return f"{TIPO_TRABAJO}:{cliente_id}"


def preparar(ctx: Contexto, cliente: Cliente, docs: list[tuple[str, str]], canales: list[str],
             contacto_ids: list[int], mensaje: str) -> tuple[list[EnvioDocumento],
                                                             list[Omitido], Trabajo | None]:
    """Valida los documentos (que sean del cliente), crea los envíos y encola el trabajo."""
    if not docs or not canales or not contacto_ids:
        raise FiscalAgentError("Elige al menos un documento, un canal y un contacto.", 422)
    if any(c not in CANALES for c in canales):
        raise FiscalAgentError("Canal: correo o whatsapp.", 422)
    descripciones = {}
    for tipo, ref in docs:
        descripciones[(tipo, ref)] = documentos.paquete(ctx.db, cliente, tipo, ref).descripcion
    nuevos: list[EnvioDocumento] = []
    omitidos: list[Omitido] = []
    for cid in dict.fromkeys(contacto_ids):
        c = contacto_de(ctx.db, cliente, cid)
        for canal in dict.fromkeys(canales):
            a, motivo = destino(c, canal)
            if motivo:
                omitidos.append(Omitido(c.nombre, canal, motivo))
                continue
            for (tipo, ref), desc in descripciones.items():
                e = EnvioDocumento(despacho_id=ctx.despacho_id, cliente_id=cliente.id,
                                   contacto_id=c.id, canal=canal, destino=a, tipo_documento=tipo,
                                   ref=ref, descripcion=desc[:300], mensaje=mensaje[:2000],
                                   estado="pendiente", creado_por=ctx.uid)
                ctx.db.add(e)
                nuevos.append(e)
    ctx.db.flush()
    trabajo = None
    if nuevos:
        trabajo = encolar(ctx.db, TIPO_TRABAJO, {"cliente_id": cliente.id},
                          despacho_id=ctx.despacho_id, cliente_id=cliente.id,
                          clave_unica=clave_trabajo(cliente.id))
    registrar(ctx, "documentos.enviar", "cliente", cliente.id,
              {"documentos": [f"{t}:{r}" for t, r in docs], "canales": canales,
               "contactos": contacto_ids, "envios": [e.id for e in nuevos],
               "omitidos": len(omitidos)}, cliente)
    return nuevos, omitidos, trabajo


def reenviar(ctx: Contexto, cliente: Cliente, envio_id: int) -> EnvioDocumento:
    e = envio_de(ctx.db, cliente, envio_id)
    e.estado, e.intentos, e.error = "pendiente", 0, ""
    ctx.db.flush()
    encolar(ctx.db, TIPO_TRABAJO, {"cliente_id": cliente.id}, despacho_id=ctx.despacho_id,
            cliente_id=cliente.id, clave_unica=clave_trabajo(cliente.id))
    registrar(ctx, "documentos.reenviar", "envio_documento", e.id,
              {"canal": e.canal, "documento": f"{e.tipo_documento}:{e.ref}"}, cliente)
    return e


def envio_de(db: Session, cliente: Cliente, envio_id: int) -> EnvioDocumento:
    e = db.get(EnvioDocumento, envio_id)
    if e is None or e.cliente_id != cliente.id:
        raise FiscalAgentError("No existe ese envío en este cliente.", 404)
    return e


def envios(db: Session, cliente: Cliente, limite: int = 100) -> list[EnvioDocumento]:
    return list(db.scalars(select(EnvioDocumento).where(EnvioDocumento.cliente_id == cliente.id)
                           .order_by(EnvioDocumento.id.desc()).limit(limite)))


def ultimo_trabajo(db: Session, cliente: Cliente) -> Trabajo | None:
    return db.scalar(select(Trabajo).where(Trabajo.clave_unica == clave_trabajo(cliente.id))
                     .order_by(Trabajo.id.desc()).limit(1))


def envio_json(e: EnvioDocumento) -> dict[str, Any]:
    return {"id": e.id, "contacto_id": e.contacto_id, "canal": e.canal, "destino": e.destino,
            "tipo_documento": e.tipo_documento, "ref": e.ref, "descripcion": e.descripcion,
            "estado": e.estado, "intentos": e.intentos, "error": e.error,
            "enviado_en": e.enviado_en.isoformat() if e.enviado_en else None,
            "creado_en": e.creado_en.isoformat() if e.creado_en else None}


def _nombre_contacto(db: Session, e: EnvioDocumento) -> str:
    c = db.get(ContactoCliente, e.contacto_id) if e.contacto_id else None
    return c.nombre if c is not None else ""


def enviar_uno(db: Session, cliente: Cliente, despacho: str, e: EnvioDocumento) -> str:
    """Manda un envío por su canal y devuelve el id del mensaje del proveedor."""
    p = documentos.paquete(db, cliente, e.tipo_documento, e.ref)
    nombre = _nombre_contacto(db, e) or cliente.nombre
    if e.canal == "correo":
        cuerpo = (f"<p>Hola {html.escape(nombre)}:</p><p>{html.escape(despacho)} te comparte: "
                  f"<strong>{html.escape(p.descripcion)}</strong>.</p>")
        if e.mensaje:
            cuerpo += f"<p>{html.escape(e.mensaje)}</p>"
        return registro.obtener("correo").enviar(
            [e.destino], f"{p.descripcion} · {cliente.nombre}", cuerpo,
            [Adjunto(a.nombre, a.contenido, a.mime) for a in p.archivos])
    archivo = p.de_tipo(documentos.PDF) or p.archivos[0]
    publico = "documento.pdf" if archivo.mime == documentos.PDF else "documento.xml"
    return registro.obtener("whatsapp").enviar_plantilla(
        e.destino, plantilla_whatsapp(), "es_MX", [nombre, p.descripcion],
        documento=DocumentoPlantilla(enlaces.url_firmada(e.id, publico, ambito="documentos"),
                                     archivo.nombre))


def enviar_lote(db: Session, despacho_id: str, cliente_id: int) -> dict[str, Any]:
    """El cuerpo del trabajo. Commit por envío: lo enviado no se repite."""
    cliente = db.get(Cliente, cliente_id)
    if cliente is None or cliente.despacho_id != despacho_id:
        return {"enviados": 0, "fallidos": 0, "nota": "El cliente ya no existe."}
    despacho = db.get(Despacho, despacho_id)
    nombre_despacho = (despacho.nombre if despacho else "") or "Tu despacho contable"
    por_mandar = list(db.scalars(select(EnvioDocumento).where(
        EnvioDocumento.cliente_id == cliente.id,
        (EnvioDocumento.estado == "pendiente") | (
            (EnvioDocumento.estado == "fallido") & (EnvioDocumento.intentos < MAX_INTENTOS)))
        .order_by(EnvioDocumento.id)))
    enviados = fallidos = 0
    for e in por_mandar:
        try:
            e.id_mensaje = str(enviar_uno(db, cliente, nombre_despacho, e))[:200]
            e.estado, e.error, e.enviado_en = "enviado", "", ahora()
            enviados += 1
        except Exception as exc:  # noqa: BLE001 — se guarda por envío y se reintenta
            e.estado, e.error = "fallido", f"{type(exc).__name__}: {exc}"[:500]
            fallidos += 1
        e.intentos += 1
        db.commit()
    db.add(EventoAuditoria(
        despacho_id=despacho_id, uid="worker", cliente_id=cliente.id, cliente_clave=cliente.clave,
        accion="documentos.enviados", entidad="cliente", entidad_id=str(cliente.id),
        detalle={"enviados": enviados, "fallidos": fallidos,
                 "envios": [e.id for e in por_mandar]}))
    db.commit()
    quedan = db.scalar(select(func.count()).select_from(EnvioDocumento).where(
        EnvioDocumento.cliente_id == cliente.id,
        (EnvioDocumento.estado == "pendiente") | (
            (EnvioDocumento.estado == "fallido") & (EnvioDocumento.intentos < MAX_INTENTOS))))
    if quedan:
        raise RuntimeError(f"{quedan} envíos por reintentar; se reprograman con backoff.")
    return {"enviados": enviados, "fallidos": fallidos}
