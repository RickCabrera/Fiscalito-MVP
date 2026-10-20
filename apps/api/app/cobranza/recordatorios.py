"""
Recordatorios de cobro por correo o WhatsApp (P5-03), con los adaptadores `correo` y
`whatsapp` (`app/integraciones/`). Sin red en tests: el adaptador `falso` guarda lo enviado.

- Manual: el despacho manda uno ahora o lo programa para una fecha (trabajo
  `cobranza.recordatorio` con `ejecutar_en`).
- Automático: el trabajo diario `cobranza.recordatorios_automaticos` manda uno a cada cliente
  con `recordatorio_automatico`, saldo VENCIDO y sin recordatorio en los últimos
  `dias_entre_recordatorios` días.

Idempotente: un recordatorio sólo se envía si sigue `programado`; el trabajo diario usa la
fecha como clave y revisa el último enviado antes de mandar otro.
WhatsApp manda texto libre (`enviar_texto`). # POR CONFIRMAR: fuera de la ventana de 24 h la
API de Meta exige plantilla aprobada; cuando exista, se cambia aquí por `enviar_plantilla`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cobranza.servicio import CERO, Saldo, calcular_saldo, dinero
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.modelos.cobranza import (
    CANALES,
    CargoCobranza,
    HonorarioCliente,
    PagoCobranza,
    RecordatorioCobro,
)
from app.modelos.nucleo import Cliente, Despacho
from app.trabajos.cola import encolar

TIPO_RECORDATORIO = "cobranza.recordatorio"


def saldo_cliente(db: Session, cliente: Cliente, hoy: date) -> Saldo:
    cargos = list(db.scalars(select(CargoCobranza).where(CargoCobranza.cliente_id == cliente.id)))
    pagos = list(db.scalars(select(PagoCobranza).where(PagoCobranza.cliente_id == cliente.id)))
    return calcular_saldo(cargos, pagos, hoy)


def texto(cliente: Cliente, despacho: str, s: Saldo) -> str:
    partes = [f"Hola, {cliente.nombre or cliente.clave}. Te recordamos que tu saldo con "
              f"{despacho} es de ${s.saldo:,.2f} MXN."]
    if s.vencido > 0 and s.vencido_desde:
        partes.append(f"De ese saldo, ${dinero(s.vencido):,.2f} está vencido desde el "
                      f"{s.vencido_desde.strftime('%d/%m/%Y')}.")
    partes.append("Si ya pagaste, ignora este mensaje. ¡Gracias!")
    return " ".join(partes)


def destino_de(h: HonorarioCliente | None, canal: str) -> str:
    if h is None:
        return ""
    return (h.correo if canal == "correo" else h.telefono).strip()


def enviar(db: Session, rec: RecordatorioCobro, hoy: date | None = None, *,
           relanzar: bool = False) -> RecordatorioCobro:
    """
    Manda un recordatorio `programado` con el adaptador del canal. Idempotente.

    Si el proveedor falla queda `fallido` con el error; con `relanzar` (el trabajo de la cola)
    además se relanza la excepción para que la cola lo reintente con backoff.
    """
    if rec.estado != "programado":
        return rec
    cliente = db.get(Cliente, rec.cliente_id)
    if cliente is None:
        rec.estado, rec.error = "omitido", "El cliente ya no existe."
        return rec
    s = saldo_cliente(db, cliente, hoy or date.today())
    rec.saldo = s.saldo
    if s.saldo <= CERO:
        rec.estado, rec.error = "omitido", "El cliente no tiene saldo pendiente."
        db.flush()
        return rec
    despacho = db.get(Despacho, cliente.despacho_id)
    nombre = (despacho.nombre if despacho else "") or "tu despacho contable"
    mensaje = texto(cliente, nombre, s)
    try:
        if rec.canal == "correo":
            rec.mensaje_id = registro.obtener("correo").enviar(
                [rec.destino], f"Recordatorio de pago — {nombre}",
                f"<p>{escape(mensaje)}</p>")
        else:
            rec.mensaje_id = registro.obtener("whatsapp").enviar_texto(rec.destino, mensaje)
    except Exception as exc:  # noqa: BLE001 — se guarda el fallo; el trabajo lo reintenta
        rec.estado, rec.error = "fallido", f"{type(exc).__name__}: {exc}"[:2000]
        db.flush()
        if relanzar:
            raise
        return rec
    rec.estado, rec.enviado_en, rec.error = "enviado", datetime.now(UTC), ""
    db.flush()
    return rec


def crear(db: Session, cliente: Cliente, canal: str, destino: str, *, usuario: str,
          origen: str = "manual", programado_para: datetime | None = None
          ) -> RecordatorioCobro:
    if canal not in CANALES:
        raise FiscalAgentError("Canal inválido: correo o whatsapp.", 422)
    if not destino:
        raise FiscalAgentError(
            f"El cliente no tiene {'correo' if canal == 'correo' else 'teléfono'} de cobranza "
            "capturado en su configuración de honorarios.", 422)
    rec = RecordatorioCobro(despacho_id=cliente.despacho_id, cliente_id=cliente.id,
                            canal=canal, destino=destino, origen=origen, creado_por=usuario,
                            programado_para=programado_para or datetime.now(UTC))
    db.add(rec)
    db.flush()
    return rec


def programar(db: Session, rec: RecordatorioCobro) -> None:
    """Encola el envío para `programado_para`."""
    encolar(db, TIPO_RECORDATORIO, {"recordatorio_id": rec.id}, despacho_id=rec.despacho_id,
            cliente_id=rec.cliente_id, ejecutar_en=rec.programado_para,
            clave_unica=f"{TIPO_RECORDATORIO}:{rec.id}", max_intentos=3)


def automaticos(db: Session, hoy: date) -> dict[str, Any]:
    """Recordatorio a cada cliente con saldo vencido que lo tenga configurado."""
    enviados = omitidos = 0
    for h in db.scalars(select(HonorarioCliente).where(
            HonorarioCliente.recordatorio_automatico.is_(True))
            .order_by(HonorarioCliente.cliente_id)):
        cliente = db.get(Cliente, h.cliente_id)
        if cliente is None:
            continue
        s = saldo_cliente(db, cliente, hoy)
        if s.vencido <= 0:
            continue
        limite = datetime.combine(hoy - timedelta(days=max(h.dias_entre_recordatorios, 1) - 1),
                                  datetime.min.time(), tzinfo=UTC)
        reciente = db.scalar(select(RecordatorioCobro.id).where(
            RecordatorioCobro.cliente_id == h.cliente_id,
            RecordatorioCobro.estado == "enviado",
            RecordatorioCobro.enviado_en >= limite))
        destino = destino_de(h, h.canal_recordatorio)
        if reciente is not None or not destino:
            omitidos += 1
            continue
        rec = crear(db, cliente, h.canal_recordatorio, destino, usuario="sistema",
                    origen="automatico")
        if enviar(db, rec, hoy).estado == "enviado":
            enviados += 1
    return {"enviados": enviados, "omitidos": omitidos}


def recordatorio_json(r: RecordatorioCobro) -> dict[str, Any]:
    return {"id": r.id, "canal": r.canal, "destino": r.destino, "estado": r.estado,
            "origen": r.origen, "programado_para": r.programado_para.isoformat(),
            "enviado_en": r.enviado_en.isoformat() if r.enviado_en else None,
            "saldo": str(dinero(r.saldo)), "error": r.error}
