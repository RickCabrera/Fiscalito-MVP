"""
Bot de WhatsApp del despacho (P5-06).

EL CAMINO DE UN MENSAJE
-----------------------
1. **Webhook** (`recibir`): la ruta ya verificó la firma del proveedor. Por cada mensaje: si
   su id ya está en la bitácora, se ignora (Meta reintenta); si el número rebasó su límite por
   minuto, se anota `limitado` y no se contesta; si no, se anota `recibido` y se encola
   `whatsapp.responder`. El webhook contesta 200 rápido: Meta reintenta si tarda.
2. **Trabajo** (`responder`): identifica el número entre los contactos ACTIVOS y CON
   CONSENTIMIENTO. Número desconocido → un aviso de rechazo (a lo más uno por día) y nada
   más: ni LLM, ni datos. Número de varias empresas → pide el RFC (sin LLM). Identificado →
   cobra el tope diario del despacho y le pide al LLM que INTERPRETE la intención.
3. **Respuesta**: la intención se resuelve con la base y los motores: el PDF de la opinión o
   de la constancia (el último guardado), el ZIP de XML del mes, o el resumen de impuestos
   del motor. El texto con cifras lo arma este módulo, nunca el modelo; si el modelo contesta
   texto libre y trae dígitos, se manda el menú en su lugar (una cifra inventada no sale).

Las respuestas van dentro de la ventana de 24 h que abre el mensaje del cliente, así que van
como texto y documento libres, no como plantilla aprobada.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.acceso.dependencias import aplicar_limite
from app.acceso.limitador import entero_de_entorno
from app.acceso.llm import ZONA, cobrar_dia, tope_diario
from app.asistente import consultas
from app.boveda_cfdi import servicio as boveda
from app.exceptions import FiscalAgentError, LimiteExcedido
from app.integraciones import registro
from app.integraciones.whatsapp import MensajeEntrante
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.whatsapp import ContactoWhatsApp, MensajeWhatsApp
from app.sat_verificacion import cumplimiento
from app.schemas.empleado_pago import normalizar_celular
from app.trabajos.cola import encolar
from app.whatsapp_bot import enlaces

TIPO_TRABAJO = "whatsapp.responder"
DEFAULT_POR_MINUTO = 6
MAX_TEXTO = 2000
MAX_XML_ZIP = 500
_RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

RECHAZO = ("Este número no está registrado con ningún despacho en Fiscalito. Pide a tu "
           "contador que lo dé de alta para poder atenderte.")
MENU = ("Puedo mandarte: tu opinión de cumplimiento, tu constancia de situación fiscal, tus "
        "facturas del mes o decirte cuánto pagas de impuestos este mes. ¿Qué necesitas?")
VARIAS = ("Tu número está registrado en varias empresas. Escríbeme tu pedido junto con el "
          "RFC de la empresa (por ejemplo: «opinión ABC010101AB1»).")
TOPE = ("Por hoy ya no puedo atender más consultas automáticas. Tu despacho sigue "
        "disponible; vuelve a escribir mañana.")


def limite_por_minuto() -> int:
    """Mensajes por minuto por número (`FISCALITO_WHATSAPP_BOT_POR_MINUTO`, default 6)."""
    return entero_de_entorno("FISCALITO_WHATSAPP_BOT_POR_MINUTO", DEFAULT_POR_MINUTO)


def normalizar_entrante(telefono: str) -> str:
    """Meta manda `5215512345678`, Twilio `+52…`: todo a E.164 (`+52` y 10 dígitos)."""
    crudo = "+" + re.sub(r"\D", "", telefono or "")
    try:
        return normalizar_celular(crudo)
    except ValueError:
        return crudo  # extranjero o basura: no coincidirá con ningún contacto


# ── Contactos (lado del despacho) ──


def registrar_contacto(db: Session, cliente: Cliente, telefono: str, nombre: str,
                       uid: str) -> ContactoWhatsApp:
    """Alta (o reactivación) de un número con consentimiento para este cliente."""
    try:
        tel = normalizar_celular(telefono)
    except ValueError as exc:
        raise FiscalAgentError(str(exc), 422) from exc
    if not tel:
        raise FiscalAgentError("Falta el número de WhatsApp.", 422)
    c = db.scalar(select(ContactoWhatsApp).where(ContactoWhatsApp.cliente_id == cliente.id,
                                                 ContactoWhatsApp.telefono == tel))
    if c is None:
        c = ContactoWhatsApp(despacho_id=cliente.despacho_id, cliente_id=cliente.id,
                             telefono=tel)
        db.add(c)
    c.nombre, c.activo, c.consentimiento = nombre.strip()[:200], True, True
    c.consentimiento_en, c.registrado_por = datetime.now(UTC), uid
    db.flush()
    return c


def contactos(db: Session, cliente: Cliente) -> list[ContactoWhatsApp]:
    return list(db.scalars(select(ContactoWhatsApp).where(
        ContactoWhatsApp.cliente_id == cliente.id, ContactoWhatsApp.activo.is_(True))
        .order_by(ContactoWhatsApp.id)))


def desactivar_contacto(db: Session, cliente: Cliente, contacto_id: int) -> ContactoWhatsApp:
    c = db.get(ContactoWhatsApp, contacto_id)
    if c is None or c.cliente_id != cliente.id or not c.activo:
        raise FiscalAgentError("No existe ese contacto para este cliente.", 404)
    c.activo = False
    db.flush()
    return c


def contacto_json(c: ContactoWhatsApp) -> dict[str, Any]:
    return {"id": c.id, "telefono": c.telefono, "nombre": c.nombre,
            "consentimiento": c.consentimiento,
            "consentimiento_en": c.consentimiento_en.isoformat() if c.consentimiento_en
            else None}


def conversacion(db: Session, cliente: Cliente, limite: int = 200) -> list[dict[str, Any]]:
    filas = db.scalars(select(MensajeWhatsApp).where(MensajeWhatsApp.cliente_id == cliente.id)
                       .order_by(MensajeWhatsApp.id.desc()).limit(limite))
    return [{"id": m.id, "fecha": m.creado_en.isoformat(), "direccion": m.direccion,
             "telefono": m.telefono, "texto": m.texto, "intencion": m.intencion,
             "estado": m.estado, "documento": (m.detalle or {}).get("archivo")}
            for m in reversed(list(filas))]


# ── Webhook ──


def recibir(db: Session, mensajes: list[MensajeEntrante]) -> dict[str, int]:
    """Anota cada mensaje (idempotente por id del proveedor) y encola su respuesta."""
    cuenta = {"encolados": 0, "repetidos": 0, "limitados": 0}
    for m in mensajes:
        if not m.id_mensaje:
            continue
        if db.scalar(select(MensajeWhatsApp.id).where(
                MensajeWhatsApp.direccion == "entrante",
                MensajeWhatsApp.id_externo == m.id_mensaje)) is not None:
            cuenta["repetidos"] += 1
            continue
        tel = normalizar_entrante(m.telefono)
        try:
            aplicar_limite(f"whatsapp:{tel}", limite_por_minuto(), "mensajes")
            estado = "recibido"
        except LimiteExcedido:
            estado = "limitado"
        # El texto espera en `texto_pendiente` a que el trabajo identifique el número: pasa a
        # `texto` si está registrado y se BORRA si no (ver `responder`).
        detalle: dict[str, Any] = {"tipo": m.tipo}
        if estado == "recibido":
            detalle["texto_pendiente"] = (m.texto or "")[:MAX_TEXTO]
        fila = MensajeWhatsApp(telefono=tel, direccion="entrante", id_externo=m.id_mensaje,
                               estado=estado, detalle=detalle)
        try:
            with db.begin_nested():
                db.add(fila)
        except IntegrityError:  # el mismo id llegó por dos webhooks a la vez
            cuenta["repetidos"] += 1
            continue
        if estado == "limitado":
            cuenta["limitados"] += 1
            continue
        encolar(db, TIPO_TRABAJO, {"mensaje_id": fila.id},
                clave_unica=f"{TIPO_TRABAJO}:{m.id_mensaje}", max_intentos=3)
        cuenta["encolados"] += 1
    db.flush()
    return cuenta


# ── Trabajo: responder ──

INTENCIONES: list[dict[str, Any]] = [
    {"nombre": "enviar_opinion_cumplimiento",
     "descripcion": "El cliente pide su opinión de cumplimiento (32-D) del SAT.",
     "parametros": {"type": "object", "properties": {}}},
    {"nombre": "enviar_constancia",
     "descripcion": "El cliente pide su constancia de situación fiscal (CSF / cédula).",
     "parametros": {"type": "object", "properties": {}}},
    {"nombre": "enviar_facturas_del_mes",
     "descripcion": "El cliente pide sus facturas (CFDI) de un mes; sin mes = el actual.",
     "parametros": {"type": "object", "properties": {
         "anio": {"type": "integer", "minimum": 2000, "maximum": 2100},
         "mes": {"type": "integer", "minimum": 1, "maximum": 12}}}},
    {"nombre": "consultar_pago_del_mes",
     "descripcion": "El cliente pregunta cuánto paga de impuestos este mes.",
     "parametros": {"type": "object", "properties": {}}},
]
_NOMBRES_INTENCION = {i["nombre"] for i in INTENCIONES}


def _prompt(cliente: Cliente) -> str:
    return (f"Atiendes por WhatsApp a {cliente.nombre or cliente.clave}, cliente de un despacho "
            "contable mexicano. Tu ÚNICO trabajo es entender qué pide y llamar la herramienta "
            "que corresponda. Si no pide ninguna de ellas, contesta en una o dos oraciones "
            "amables ofreciendo lo que puedes mandar. NUNCA escribas cifras, importes, fechas "
            "ni datos fiscales: esos los manda el sistema.")


def _enviar(db: Session, base: MensajeWhatsApp, texto: str, *, intencion: str,
            archivo: str = "", documento: dict[str, Any] | None = None) -> MensajeWhatsApp:
    """Manda texto o documento y lo anota en la bitácora."""
    wa = registro.obtener("whatsapp")
    salida = MensajeWhatsApp(
        despacho_id=base.despacho_id, cliente_id=base.cliente_id, contacto_id=base.contacto_id,
        telefono=base.telefono, direccion="saliente", texto=texto[:MAX_TEXTO],
        intencion=intencion, estado="enviado",
        detalle={"archivo": archivo, **({"documento": documento} if documento else {})})
    db.add(salida)
    db.flush()
    if archivo:
        url = enlaces.url_firmada(salida.id, archivo)
        salida.id_externo = wa.enviar_documento(base.telefono, url, archivo, texto)
    else:
        salida.id_externo = wa.enviar_texto(base.telefono, texto)
    db.flush()
    return salida


def _ya_rechazado_hoy(db: Session, tel: str) -> bool:
    desde = datetime.now(UTC) - timedelta(days=1)
    return db.scalar(select(MensajeWhatsApp.id).where(
        MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "saliente",
        MensajeWhatsApp.intencion == "rechazo", MensajeWhatsApp.creado_en >= desde)) is not None


def _identificar(db: Session, tel: str, texto: str) -> tuple[list[ContactoWhatsApp],
                                                             ContactoWhatsApp | None]:
    candidatos = list(db.scalars(select(ContactoWhatsApp).where(
        ContactoWhatsApp.telefono == tel, ContactoWhatsApp.activo.is_(True),
        ContactoWhatsApp.consentimiento.is_(True)).order_by(ContactoWhatsApp.id)))
    if len(candidatos) <= 1:
        return candidatos, (candidatos[0] if candidatos else None)
    rfcs = set(_RFC.findall((texto or "").upper()))
    elegidos = [c for c in candidatos
                if boveda.rfc_del_cliente(db.get(Cliente, c.cliente_id)) in rfcs]
    return candidatos, (elegidos[0] if len(elegidos) == 1 else None)


def responder(db: Session, mensaje_id: int, hoy: date | None = None) -> dict[str, Any]:
    """El manejador de `whatsapp.responder`. Idempotente: sólo atiende los `recibido`."""
    m = db.get(MensajeWhatsApp, mensaje_id)
    if m is None or m.estado != "recibido":
        return {"omitido": True}
    hoy = hoy or datetime.now(ZONA).date()
    texto = str((m.detalle or {}).get("texto_pendiente", ""))
    candidatos, contacto = _identificar(db, m.telefono, texto)
    m.detalle = {k: v for k, v in (m.detalle or {}).items() if k != "texto_pendiente"}
    if not candidatos:
        m.estado = "rechazado"
        if not _ya_rechazado_hoy(db, m.telefono):
            _enviar(db, m, RECHAZO, intencion="rechazo")
        return {"estado": "rechazado"}
    m.texto = texto
    if contacto is None:
        m.estado = "respondido"
        _enviar(db, m, VARIAS, intencion="pedir_rfc")
        return {"estado": "pedir_rfc"}
    cliente = db.get(Cliente, contacto.cliente_id)
    assert cliente is not None
    m.despacho_id, m.cliente_id, m.contacto_id = cliente.despacho_id, cliente.id, contacto.id
    try:
        cobrar_dia(db, cliente.despacho_id, tope_diario())  # hace commit (ver acceso/llm.py)
    except LimiteExcedido:
        m.estado = "limitado"
        _enviar(db, m, TOPE, intencion="tope")
        return {"estado": "tope"}
    r = registro.obtener("llm").completar(
        [{"role": "system", "content": _prompt(cliente)}, {"role": "user", "content": texto}],
        INTENCIONES)
    llamada = next((ll for ll in r.llamadas if ll.nombre in _NOMBRES_INTENCION), None)
    m.estado = "respondido"
    if llamada is None:
        libre = (r.texto or "").strip()
        # El modelo no da cifras: si su texto trae dígitos, se manda el menú en su lugar.
        _enviar(db, m, MENU if not libre or re.search(r"\d", libre) else libre[:MAX_TEXTO],
                intencion="conversacion")
        m.intencion = "conversacion"
        return {"estado": "conversacion"}
    m.intencion = llamada.nombre
    _resolver(db, m, cliente, llamada.nombre, llamada.argumentos, hoy)
    return {"estado": "respondido", "intencion": llamada.nombre}


def _pesos(valor: str) -> str:
    return f"${Decimal(str(valor)).quantize(Decimal('0.01')):,}"


def _resolver(db: Session, m: MensajeWhatsApp, cliente: Cliente, intencion: str,
              args: dict[str, Any], hoy: date) -> None:
    nombre = cliente.nombre or cliente.clave
    if intencion in ("enviar_opinion_cumplimiento", "enviar_constancia"):
        tipo = "opinion" if intencion == "enviar_opinion_cumplimiento" else "constancia"
        etiqueta = "opinión de cumplimiento" if tipo == "opinion" \
            else "constancia de situación fiscal"
        docs = cumplimiento.historial(db, cliente, tipo, limite=1)
        if not docs:
            _enviar(db, m, f"Aún no tenemos tu {etiqueta} en el sistema. Tu despacho la "
                           "puede obtener; vuelve a pedirla más tarde.", intencion=intencion)
            return
        d = docs[0]
        leyenda = f"Tu {etiqueta} ({nombre}), del {d.fecha.strftime('%d/%m/%Y')}"
        if tipo == "opinion" and d.resultado != "desconocido":
            leyenda += f": {d.resultado}"
        _enviar(db, m, leyenda + ".", intencion=intencion, archivo=f"{tipo}.pdf",
                documento={"tipo": tipo, "doc_id": d.id})
        return
    if intencion == "enviar_facturas_del_mes":
        try:
            anio, mes = int(args.get("anio") or hoy.year), int(args.get("mes") or hoy.month)
            datos = consultas.boveda_mes(db, cliente, anio, mes)
        except (TypeError, ValueError, FiscalAgentError):
            anio, mes = hoy.year, hoy.month
            datos = consultas.boveda_mes(db, cliente, anio, mes)
        etiqueta = f"{_MESES[mes - 1]} de {anio}"
        if not datos["no_cancelados"]:
            _enviar(db, m, f"No hay facturas de {nombre} en {etiqueta}.",
                    intencion=intencion)
            return
        partes = [f"{r['cantidad']} {'emitidas' if r['direccion'] == 'emitido' else 'recibidas'}"
                  f" tipo {r['tipo']} por {_pesos(r['total'])}" for r in datos["no_cancelados"]]
        _enviar(db, m, f"Facturas de {nombre} en {etiqueta} (sin canceladas): " + "; ".join(partes)
                + ". Te mando los XML en un ZIP.", intencion=intencion, archivo="facturas.zip",
                documento={"tipo": "facturas", "anio": anio, "mes": mes})
        return
    # consultar_pago_del_mes
    anio, mes = consultas.periodo_que_vence(hoy)
    r = consultas.impuestos_mes(db, cliente, anio, mes, hoy)
    lineas = [f"- {c['concepto']}: {_pesos(c['total'])}" for c in r["conceptos"]]
    texto = (f"{nombre}: la declaración de {_MESES[mes - 1]} de {anio} (vence el "
             f"{date.fromisoformat(r['fecha_limite']).strftime('%d/%m/%Y')}) suma "
             f"{_pesos(r['total_a_pagar'])}" + (":\n" + "\n".join(lineas) if lineas else ".")
             + f"\n{r['aviso']}")
    _enviar(db, m, texto, intencion=intencion, documento={"tipo": "impuestos",
                                                          "periodo": r["periodo"]})


# ── Descarga pública del documento entregado ──


def documento_entregado(db: Session, mensaje_id: int, archivo: str) -> tuple[bytes, str]:
    """El archivo que el bot mandó en el mensaje `mensaje_id`: (contenido, tipo MIME)."""
    no_existe = FiscalAgentError("No existe el documento.", 404)
    m = db.get(MensajeWhatsApp, mensaje_id)
    if m is None or m.direccion != "saliente" or m.cliente_id is None:
        raise no_existe
    doc = (m.detalle or {}).get("documento") or {}
    if (m.detalle or {}).get("archivo") != archivo:
        raise no_existe
    cliente = db.get(Cliente, m.cliente_id)
    if cliente is None:
        raise no_existe
    if doc.get("tipo") in ("opinion", "constancia"):
        d = cumplimiento.documento(db, cliente, int(doc["doc_id"]))
        return cumplimiento.leer_pdf(d), "application/pdf"
    if doc.get("tipo") == "facturas":
        return _zip_del_mes(db, cliente, int(doc["anio"]), int(doc["mes"])), "application/zip"
    raise no_existe


def _zip_del_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> bytes:
    desde, hasta = consultas.rango_mes(anio, mes)
    filas = db.scalars(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.estatus_sat != "cancelado",
        Comprobante.fecha >= datetime.combine(desde, time.min),
        Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), time.min),
    ).order_by(Comprobante.fecha, Comprobante.id).limit(MAX_XML_ZIP))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for c in filas:
            z.writestr(f"{c.uuid}.xml", boveda.leer_xml_original(c))
    return buf.getvalue()
