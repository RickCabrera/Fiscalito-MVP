"""
Lectura de los paquetes de METADATA del SAT y su guardado (P1-01).

FORMATO
-------
El paquete es un ZIP con uno o varios `.txt` separados por `~`, con encabezado:

    Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~
    FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion

`Estatus` es 1 (vigente) o 0 (cancelado). Fuente del formato: phpcfdi/sat-ws-descarga-masiva
(`MetadataPackageReader`), que lo documenta a partir de paquetes reales; el documento del SAT
1.5 no describe las columnas. Desde 2025 algunos paquetes agregan columnas (p. ej.
`RfcACuentaTerceros`): se leen por NOMBRE de encabezado, nunca por posición, y lo que sobra
se guarda en `datos`.

Un defecto conocido de esos archivos (también documentado por phpcfdi): si el fin de línea es
CRLF, un salto LF suelto DENTRO de un nombre parte el renglón. Se reconstruye uniendo hasta
encontrar el CRLF.

STREAMING
---------
Un paquete de metadata trae hasta 1,000,000 renglones: se lee un miembro y un renglón a la vez
y se guarda en lotes de `LOTE`.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import IO, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import MetadataCfdiSat

LOTE = 500
COLUMNAS = {
    "uuid": "uuid", "rfcemisor": "rfc_emisor", "nombreemisor": "nombre_emisor",
    "rfcreceptor": "rfc_receptor", "nombrereceptor": "nombre_receptor", "rfcpac": "rfc_pac",
    "fechaemision": "fecha_emision", "fechacertificacionsat": "fecha_certificacion",
    "monto": "monto", "efectocomprobante": "efecto", "estatus": "estatus",
    "fechacancelacion": "fecha_cancelacion",
}


def _renglones(texto: IO[str]) -> Iterator[str]:
    """Renglones del .txt, reparando los LF sueltos de un archivo CRLF."""
    crlf: bool | None = None
    pendiente = ""
    for linea in texto:
        if crlf is None:
            crlf = linea.endswith("\r\n")
        if crlf and not linea.endswith("\r\n"):
            pendiente += linea.rstrip("\n")
            continue
        completo = (pendiente + linea).rstrip("\r\n")
        pendiente = ""
        if completo.strip():
            yield completo
    if pendiente.strip():
        yield pendiente.rstrip("\r\n")


def leer_paquete(archivo: IO[bytes]) -> Iterator[dict[str, str]]:
    """Cada renglón de cada .txt del ZIP como dict {columna_en_minúsculas: valor}."""
    with zipfile.ZipFile(archivo) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".txt"):
                continue
            if info.filename.startswith("__MACOSX/"):
                continue
            with zf.open(info) as crudo:
                texto = io.TextIOWrapper(crudo, encoding="utf-8-sig", errors="replace",
                                         newline="")
                encabezado: list[str] | None = None
                for renglon in _renglones(texto):
                    campos = renglon.split("~")
                    if encabezado is None:
                        encabezado = [c.strip().lower() for c in campos]
                        continue
                    yield {
                        encabezado[i]: campos[i].strip() if i < len(campos) else ""
                        for i in range(len(encabezado))
                    }


def _fecha(valor: str) -> datetime | None:
    valor = (valor or "").strip()
    if not valor:
        return None
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor[:19], formato)
        except ValueError:
            continue
    return None


def _monto(valor: str) -> Decimal:
    try:
        return Decimal((valor or "0").strip() or "0").quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def _normalizar(fila: dict[str, str], rfc_cliente: str) -> dict[str, Any] | None:
    uuid = fila.get("uuid", "").strip().upper()
    if len(uuid) != 36:
        return None
    rfc_emisor = fila.get("rfcemisor", "").strip().upper()
    estatus = fila.get("estatus", "").strip()
    extra = {k: v for k, v in fila.items() if k not in COLUMNAS}
    return {
        "uuid": uuid,
        "rfc_emisor": rfc_emisor,
        "nombre_emisor": fila.get("nombreemisor", "")[:300],
        "rfc_receptor": fila.get("rfcreceptor", "").strip().upper(),
        "nombre_receptor": fila.get("nombrereceptor", "")[:300],
        "rfc_pac": fila.get("rfcpac", "").strip().upper(),
        "fecha_emision": _fecha(fila.get("fechaemision", "")),
        "fecha_certificacion": _fecha(fila.get("fechacertificacionsat", "")),
        "monto": _monto(fila.get("monto", "")),
        "efecto": fila.get("efectocomprobante", "").strip().upper()[:1],
        "estatus": "cancelado" if estatus == "0" else "vigente",
        "fecha_cancelacion": _fecha(fila.get("fechacancelacion", "")),
        "direccion": "emitido" if rfc_emisor == rfc_cliente else "recibido",
        "datos": extra,
    }


def guardar(db: Session, cliente: Cliente, archivo: IO[bytes], rfc_cliente: str) -> int:
    """
    Guarda (o actualiza) la metadata del paquete. Devuelve cuántos renglones leyó.

    Si el UUID ya está en la bóveda, le actualiza `estatus_sat` y `fecha_estatus`: la
    metadata es la fuente del SAT sobre si el CFDI sigue vigente.
    """
    total = 0
    lote: list[dict[str, Any]] = []
    for fila in leer_paquete(archivo):
        normal = _normalizar(fila, rfc_cliente)
        if normal is None:
            continue
        lote.append(normal)
        total += 1
        if len(lote) >= LOTE:
            _guardar_lote(db, cliente, lote)
            lote = []
    if lote:
        _guardar_lote(db, cliente, lote)
    return total


def _guardar_lote(db: Session, cliente: Cliente, lote: list[dict[str, Any]]) -> None:
    # Un UUID repetido en el mismo lote: gana el último (el más reciente del SAT).
    por_uuid = {f["uuid"]: f for f in lote}
    uuids = list(por_uuid)
    existentes = {
        m.uuid: m for m in db.scalars(select(MetadataCfdiSat).where(
            MetadataCfdiSat.cliente_id == cliente.id, MetadataCfdiSat.uuid.in_(uuids)
        ))
    }
    for uuid, f in por_uuid.items():
        fila = existentes.get(uuid)
        if fila is None:
            db.add(MetadataCfdiSat(cliente_id=cliente.id, **f))
        else:
            for k, v in f.items():
                setattr(fila, k, v)
    ahora = datetime.now(UTC)
    for comp in db.scalars(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.uuid.in_(uuids)
    )):
        estatus = por_uuid[comp.uuid]["estatus"]
        if comp.estatus_sat != estatus:
            comp.estatus_sat = estatus
        comp.fecha_estatus = ahora
    db.flush()
