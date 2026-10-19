"""
Opinión de cumplimiento 32-D y constancia de situación fiscal por cliente (P1-05).

- `obtener_y_guardar`: llama al adaptador configurado (falso, portal_sat, proveedor; manual
  responde 409), guarda el PDF en el almacenamiento y crea el `DocumentoCumplimiento`.
- `guardar_pdf`: el PDF subido a mano por el despacho (disponible con cualquier adaptador).
- El resultado sale, por orden: lo que diga el adaptador (un proveedor lo trae en JSON) → lo
  que diga el texto del PDF → `desconocido`. Nunca se inventa.

SEMÁFORO
--------
`verde` = última opinión positiva o sin obligaciones y con menos de `DIAS_VIGENCIA` días;
`rojo` = última opinión negativa; `amarillo` = la última tiene más de `DIAS_VIGENCIA` días o
su sentido es desconocido; `gris` = no hay opinión.

`DIAS_VIGENCIA` = 30 (configurable con `FISCALITO_OPINION_DIAS_VIGENCIA`). # FUENTE POR
CONFIRMAR: la regla 2.1.37 de la RMF dice que la opinión positiva tiene vigencia de 30 días
naturales a partir de su emisión; no se verificó contra el texto de la RMF 2026 vigente.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credenciales import obtener_firmante
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.integraciones.opinion_cumplimiento import (
    RESULTADOS,
    TIPOS,
    DocumentoObtenido,
    OpinionCumplimiento,
    SolicitudCumplimiento,
)
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import ConfigCumplimiento, DocumentoCumplimiento
from app.sat_verificacion import pdf as lector


def dias_vigencia() -> int:
    try:
        return max(1, int(os.environ.get("FISCALITO_OPINION_DIAS_VIGENCIA", "") or 30))
    except ValueError:
        return 30


def rfc_de(cliente: Cliente) -> str:
    return (cliente.rfc or str((cliente.datos or {}).get("rfc") or "")).strip().upper()


def _validar_tipo(tipo: str) -> None:
    if tipo not in TIPOS:
        raise FiscalAgentError("El tipo debe ser 'opinion' o 'constancia'.", status_code=422)


def ruta_pdf(cliente: Cliente, tipo: str, huella: str) -> str:
    return f"cumplimiento/{cliente.despacho_id}/{cliente.id}/{tipo}-{huella[:16]}.pdf"


def _guardar(
    db: Session, cliente: Cliente, tipo: str, obtenido: DocumentoObtenido, origen: str,
    usuario: str, almacen: Almacenamiento | None,
) -> DocumentoCumplimiento:
    lector.validar_pdf(obtenido.pdf)
    huella = hashlib.sha256(obtenido.pdf).hexdigest()
    previo = db.scalar(select(DocumentoCumplimiento).where(
        DocumentoCumplimiento.cliente_id == cliente.id, DocumentoCumplimiento.tipo == tipo,
        DocumentoCumplimiento.sha256 == huella))
    if previo is not None:
        return previo  # mismo PDF dos veces = un solo renglón (idempotente)
    leido = lector.leer_opinion(obtenido.pdf) if tipo == "opinion" \
        else lector.leer_constancia(obtenido.pdf)
    if obtenido.resultado in RESULTADOS:
        resultado, lectura = obtenido.resultado, "adaptador"
    elif tipo == "opinion" and leido.resultado != "desconocido":
        resultado, lectura = leido.resultado, "pdf"
    else:
        resultado, lectura = "desconocido", "pdf" if leido.texto_leido else "sin_lectura"
    rfc = rfc_de(cliente)
    datos: dict[str, Any] = dict(obtenido.datos)
    if leido.rfc and rfc and leido.rfc != rfc:
        datos["aviso"] = f"El PDF es del RFC {leido.rfc}, no del cliente ({rfc})."
    ruta = (almacen or obtener_almacenamiento()).guardar(
        obtenido.pdf, ruta_pdf(cliente, tipo, huella))
    doc = DocumentoCumplimiento(
        cliente_id=cliente.id, tipo=tipo,
        fecha=obtenido.fecha or leido.fecha or datetime.now(UTC).date(),
        resultado=resultado if tipo == "opinion" else "desconocido",
        folio=(obtenido.folio or leido.folio)[:80], origen=origen, ruta_pdf=ruta,
        sha256=huella, tamano=len(obtenido.pdf), lectura=lectura, creado_por=usuario,
        datos=datos,
    )
    db.add(doc)
    db.flush()
    return doc


def obtener_y_guardar(
    db: Session, cliente: Cliente, tipo: str, adaptador: OpinionCumplimiento, usuario: str,
    almacen: Almacenamiento | None = None,
) -> DocumentoCumplimiento:
    """Pide el documento al adaptador y lo guarda."""
    _validar_tipo(tipo)
    rfc = rfc_de(cliente)
    if not rfc:
        raise FiscalAgentError("Captura el RFC del cliente antes de pedir su opinión.", 422)
    solicitud = SolicitudCumplimiento(
        rfc=rfc, tipo=tipo, firmante=lambda: obtener_firmante(db, cliente, "efirma"))
    obtenido = adaptador.obtener(solicitud)
    return _guardar(db, cliente, tipo, obtenido, getattr(adaptador, "nombre", "falso"),
                    usuario, almacen)


def guardar_pdf(
    db: Session, cliente: Cliente, tipo: str, pdf: bytes, usuario: str,
    resultado: str | None = None, almacen: Almacenamiento | None = None,
) -> DocumentoCumplimiento:
    """El PDF subido a mano. `resultado` lo puede indicar el despacho si el PDF no se lee."""
    _validar_tipo(tipo)
    if resultado is not None and resultado not in RESULTADOS:
        raise FiscalAgentError(f"Resultado inválido: {resultado}.", status_code=422)
    obtenido = DocumentoObtenido(pdf=pdf, resultado=resultado if resultado != "desconocido"
                                 else None)
    doc = _guardar(db, cliente, tipo, obtenido, "manual", usuario, almacen)
    if obtenido.resultado:
        doc.lectura = "manual"
    return doc


def historial(db: Session, cliente: Cliente, tipo: str, limite: int = 50
              ) -> list[DocumentoCumplimiento]:
    _validar_tipo(tipo)
    return list(db.scalars(
        select(DocumentoCumplimiento)
        .where(DocumentoCumplimiento.cliente_id == cliente.id,
               DocumentoCumplimiento.tipo == tipo)
        .order_by(DocumentoCumplimiento.fecha.desc(), DocumentoCumplimiento.id.desc())
        .limit(limite)))


def documento(db: Session, cliente: Cliente, doc_id: int) -> DocumentoCumplimiento:
    doc = db.get(DocumentoCumplimiento, doc_id)
    if doc is None or doc.cliente_id != cliente.id:
        raise FiscalAgentError("No existe ese documento para este cliente.", status_code=404)
    return doc


def leer_pdf(doc: DocumentoCumplimiento, almacen: Almacenamiento | None = None) -> bytes:
    datos = (almacen or obtener_almacenamiento()).leer(doc.ruta_pdf)
    if hashlib.sha256(datos).hexdigest() != doc.sha256:
        raise FiscalAgentError("El PDF guardado no coincide con su huella; no se entrega.", 500)
    return datos


def semaforo(doc: DocumentoCumplimiento | None, hoy: date | None = None) -> str:
    if doc is None:
        return "gris"
    if doc.resultado == "negativa":
        return "rojo"
    edad = ((hoy or datetime.now(UTC).date()) - doc.fecha).days
    if doc.resultado in ("positiva", "sin_obligaciones") and edad <= dias_vigencia():
        return "verde"
    return "amarillo"


def fila(doc: DocumentoCumplimiento) -> dict[str, Any]:
    return {
        "id": doc.id, "tipo": doc.tipo, "fecha": doc.fecha.isoformat(),
        "resultado": doc.resultado, "folio": doc.folio, "origen": doc.origen,
        "lectura": doc.lectura, "tamano": doc.tamano,
        "creado_en": doc.creado_en.isoformat() if doc.creado_en else None,
        "aviso": (doc.datos or {}).get("aviso"),
    }


def ultimas(db: Session, cliente_ids: list[int], tipo: str
            ) -> dict[int, DocumentoCumplimiento]:
    """
    El documento más reciente (por `fecha`, luego `id`) de cada cliente, en una consulta.

    Se ordena en Python y no con max(id): un PDF viejo subido tarde tiene id mayor pero no
    es el vigente. El historial por cliente es corto (uno al mes), así que cabe.
    """
    if not cliente_ids:
        return {}
    docs = list(db.scalars(select(DocumentoCumplimiento).where(
        DocumentoCumplimiento.cliente_id.in_(cliente_ids),
        DocumentoCumplimiento.tipo == tipo)))
    salida: dict[int, DocumentoCumplimiento] = {}
    for d in docs:
        actual = salida.get(d.cliente_id)
        if actual is None or (d.fecha, d.id) > (actual.fecha, actual.id):
            salida[d.cliente_id] = d
    return salida


# ── configuración y programación ──


def config_de(db: Session, cliente: Cliente) -> ConfigCumplimiento:
    return db.get(ConfigCumplimiento, cliente.id) or ConfigCumplimiento(
        cliente_id=cliente.id, automatico=True, dia_del_mes=1, constancia=True)


def toca_hoy(config: ConfigCumplimiento, ultima: DocumentoCumplimiento | None,
             hoy: date) -> bool:
    """¿Se pide la opinión mensual hoy? Ya llegó el día del mes y no hay una de este mes."""
    if not config.automatico:
        return False
    if hoy.day < min(config.dia_del_mes or 1, 28):
        return False
    return ultima is None or (ultima.fecha.year, ultima.fecha.month) < (hoy.year, hoy.month)
