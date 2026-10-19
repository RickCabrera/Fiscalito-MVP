"""
Importación y consulta de la bóveda de CFDI (plan P, P0-03).

IMPORTAR
--------
`importar(db, cliente, archivos)` recibe pares `(nombre, archivo binario)` —XML sueltos o
ZIP— y por cada XML:
1. lo parsea (`parser.parsear_cfdi`); si no es un CFDI timbrado, va a `rechazados`;
2. si su UUID ya está en la bóveda del cliente (o salió antes en el mismo lote), va a
   `duplicados` con la razón "ya existía" y no se toca nada;
3. lo clasifica `emitido`/`recibido` comparando con el RFC del cliente; si el cliente no es
   ni emisor ni receptor, se rechaza (no es suyo);
4. guarda el XML **byte por byte** en el almacenamiento y crea el renglón.

ZIP EN STREAMING
----------------
Del ZIP se lee un miembro a la vez (`ZipFile.open`), nunca el archivo completo en memoria
ni todos los XML juntos. Un ZIP dentro de otro no se abre (se rechaza con su razón) y cada
miembro tiene un tope de tamaño, para que un ZIP-bomba no tumbe el proceso.

CLIENTE SIN RFC
---------------
Si el cliente no tiene RFC capturado se hace una pasada previa que sólo cuenta RFCs: el
que aparece en más comprobantes (como emisor o receptor) se toma como el del cliente y se
reporta en `rfc_deducido`. **No se guarda en la ficha del cliente**: corregir un dato
fiscal de la cartera es decisión del contador, no un efecto lateral de subir XML.
"""

from __future__ import annotations

import hashlib
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import IO, Any

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.parser import CfdiInvalido, CfdiLeido, parsear_cfdi
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente

# Un CFDI real rara vez pasa de 1 MB; los de nómina con cientos de conceptos, de 5.
MAX_BYTES_XML = 10 * 1024 * 1024
FIRMA_ZIP = b"PK\x03\x04"
LOTE_FLUSH = 100


@dataclass
class Reporte:
    """Resultado de una importación."""

    rfc_cliente: str = ""
    rfc_deducido: bool = False
    importados: int = 0
    duplicados: int = 0
    importados_detalle: list[dict[str, str]] = field(default_factory=list)
    duplicados_detalle: list[dict[str, str]] = field(default_factory=list)
    rechazados: list[dict[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {
            "rfc_cliente": self.rfc_cliente,
            "rfc_deducido": self.rfc_deducido,
            "importados": self.importados,
            "duplicados": self.duplicados,
            "rechazados": self.rechazados,
            "importados_detalle": self.importados_detalle,
            "duplicados_detalle": self.duplicados_detalle,
        }


# ── lectura de archivos ──


def _es_xml(nombre: str) -> bool:
    return nombre.lower().endswith(".xml")


def _es_zip(nombre: str, cabeza: bytes) -> bool:
    return nombre.lower().endswith(".zip") or cabeza.startswith(FIRMA_ZIP)


def _iterar_xml(
    archivos: Iterable[tuple[str, IO[bytes]]],
) -> Iterator[tuple[str, bytes | None, str]]:
    """
    Recorre los archivos y produce `(nombre, bytes, "")` por cada XML, o
    `(nombre, None, razon)` por cada cosa que no se puede leer. Uno a la vez.
    """
    for nombre, archivo in archivos:
        archivo.seek(0)
        cabeza = archivo.read(4)
        archivo.seek(0)
        if _es_zip(nombre, cabeza):
            yield from _iterar_zip(nombre, archivo)
        elif _es_xml(nombre):
            datos = archivo.read(MAX_BYTES_XML + 1)
            if len(datos) > MAX_BYTES_XML:
                yield nombre, None, "El XML pasa de 10 MB."
            else:
                yield nombre, datos, ""
        else:
            yield nombre, None, "No es XML ni ZIP."


def _iterar_zip(nombre_zip: str, archivo: IO[bytes]) -> Iterator[tuple[str, bytes | None, str]]:
    try:
        zf = zipfile.ZipFile(archivo)
    except zipfile.BadZipFile:
        yield nombre_zip, None, "El ZIP está dañado o no es un ZIP."
        return
    with zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX/"):
                continue
            nombre = f"{nombre_zip}/{info.filename}"
            if info.filename.lower().endswith(".zip"):
                yield nombre, None, "ZIP dentro de otro ZIP: súbelo por separado."
                continue
            if not _es_xml(info.filename):
                yield nombre, None, "No es XML."
                continue
            if info.file_size > MAX_BYTES_XML:
                yield nombre, None, "El XML pasa de 10 MB."
                continue
            try:
                with zf.open(info) as miembro:
                    # Se lee con tope aunque `file_size` diga otra cosa: el encabezado
                    # del ZIP lo escribe quien armó el ZIP.
                    datos = miembro.read(MAX_BYTES_XML + 1)
            except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as e:
                yield nombre, None, f"No se pudo extraer del ZIP: {e}"
                continue
            if len(datos) > MAX_BYTES_XML:
                yield nombre, None, "El XML pasa de 10 MB."
            else:
                yield nombre, datos, ""


# ── importación ──


def rfc_del_cliente(cliente: Cliente) -> str:
    """El RFC capturado del cliente (columna o, si no, el de su ficha)."""
    rfc = cliente.rfc or str((cliente.datos or {}).get("rfc") or "")
    return rfc.strip().upper()


def deducir_rfc(archivos: list[tuple[str, IO[bytes]]]) -> str:
    """El RFC que más comprobantes comparten (como emisor o receptor). "" si no hay."""
    cuenta: Counter[str] = Counter()
    for _nombre, datos, _razon in _iterar_xml(archivos):
        if datos is None:
            continue
        try:
            cfdi = parsear_cfdi(datos)
        except CfdiInvalido:
            continue
        cuenta.update({cfdi.rfc_emisor, cfdi.rfc_receptor})
    if not cuenta:
        return ""
    # Desempate determinístico: mayor cuenta y luego orden alfabético.
    return sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def ruta_del_xml(cliente: Cliente, uuid: str) -> str:
    """Dónde vive el XML original en el almacenamiento."""
    return f"cfdi/{cliente.despacho_id}/{cliente.id}/{uuid}.xml"


def _direccion(cfdi: CfdiLeido, rfc: str) -> str | None:
    if cfdi.rfc_emisor == rfc:
        return "emitido"
    if cfdi.rfc_receptor == rfc:
        return "recibido"
    return None


def importar(
    db: Session,
    cliente: Cliente,
    archivos: Iterable[tuple[str, IO[bytes]]],
    almacen: Almacenamiento | None = None,
    origen: str = "manual",
) -> Reporte:
    """Importa XML y ZIP a la bóveda del cliente. Ver el docstring del módulo."""
    almacen = almacen or obtener_almacenamiento()
    archivos = list(archivos)
    reporte = Reporte(rfc_cliente=rfc_del_cliente(cliente))
    if not reporte.rfc_cliente:
        reporte.rfc_cliente = deducir_rfc(archivos)
        reporte.rfc_deducido = bool(reporte.rfc_cliente)

    vistos: set[str] = set()
    pendientes = 0
    for nombre, datos, razon in _iterar_xml(archivos):
        if datos is None:
            reporte.rechazados.append({"archivo": nombre, "razon": razon})
            continue
        try:
            cfdi = parsear_cfdi(datos)
        except CfdiInvalido as e:
            reporte.rechazados.append({"archivo": nombre, "razon": str(e)})
            continue

        if cfdi.uuid in vistos or _existe(db, cliente.id, cfdi.uuid):
            reporte.duplicados += 1
            reporte.duplicados_detalle.append(
                {"archivo": nombre, "uuid": cfdi.uuid, "razon": "ya existía"}
            )
            continue

        direccion = _direccion(cfdi, reporte.rfc_cliente) if reporte.rfc_cliente else None
        if direccion is None:
            reporte.rechazados.append({
                "archivo": nombre,
                "razon": f"El RFC del cliente ({reporte.rfc_cliente or 'sin RFC'}) no es "
                f"emisor ni receptor ({cfdi.rfc_emisor} → {cfdi.rfc_receptor}).",
            })
            continue

        ruta = almacen.guardar(datos, ruta_del_xml(cliente, cfdi.uuid))
        db.add(_comprobante(cliente, cfdi, direccion, origen, ruta, datos))
        vistos.add(cfdi.uuid)
        reporte.importados += 1
        reporte.importados_detalle.append(
            {"archivo": nombre, "uuid": cfdi.uuid, "direccion": direccion, "tipo": cfdi.tipo}
        )
        pendientes += 1
        if pendientes >= LOTE_FLUSH:
            db.flush()
            pendientes = 0
    db.flush()
    return reporte


def _existe(db: Session, cliente_id: int, uuid: str) -> bool:
    return db.scalar(
        select(Comprobante.id).where(
            Comprobante.cliente_id == cliente_id, Comprobante.uuid == uuid
        )
    ) is not None


def _comprobante(
    cliente: Cliente, cfdi: CfdiLeido, direccion: str, origen: str, ruta: str, datos: bytes
) -> Comprobante:
    return Comprobante(
        cliente_id=cliente.id, uuid=cfdi.uuid, version=cfdi.version, tipo=cfdi.tipo,
        fecha=cfdi.fecha, fecha_timbrado=cfdi.fecha_timbrado, serie=cfdi.serie,
        folio=cfdi.folio, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        rfc_receptor=cfdi.rfc_receptor, nombre_receptor=cfdi.nombre_receptor,
        direccion=direccion, subtotal=cfdi.subtotal, descuento=cfdi.descuento,
        total=cfdi.total, moneda=cfdi.moneda, tipo_cambio=cfdi.tipo_cambio,
        metodo_pago=cfdi.metodo_pago, forma_pago=cfdi.forma_pago, uso_cfdi=cfdi.uso_cfdi,
        iva_trasladado=cfdi.iva_trasladado, iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido, ieps=cfdi.ieps, estatus_sat="desconocido",
        origen=origen, ruta_xml=ruta, sha256=hashlib.sha256(datos).hexdigest(),
        datos=cfdi.datos,
    )


# ── consulta ──


def comprobantes_vigentes(consulta: Any) -> Any:
    """
    La consulta sin los CFDI cancelados ante el SAT (P1-03).

    Es el filtro que usan los cálculos (Fiscalito, Contabilito, la anual, P1-06): un CFDI
    cancelado sigue en la bóveda —se ve, se descarga— pero deja de contar. Los que todavía no
    se verifican (`desconocido`) SÍ cuentan: no verificar no es motivo para excluir.

        servicio.comprobantes_vigentes(select(Comprobante).where(...))
    """
    return consulta.where(Comprobante.estatus_sat != "cancelado")



@dataclass
class Filtros:
    """Filtros de la lista de la bóveda. Todo opcional."""

    desde: date | None = None
    hasta: date | None = None
    tipo: str | None = None
    direccion: str | None = None
    rfc: str | None = None
    estatus: str | None = None


def _condiciones(cliente: Cliente, f: Filtros) -> list[Any]:
    cond: list[Any] = [Comprobante.cliente_id == cliente.id]
    if f.desde:
        cond.append(Comprobante.fecha >= datetime.combine(f.desde, time.min))
    if f.hasta:
        # Inclusivo: todo el día `hasta`.
        cond.append(Comprobante.fecha < datetime.combine(f.hasta + timedelta(days=1), time.min))
    if f.tipo:
        cond.append(Comprobante.tipo == f.tipo.upper())
    if f.direccion:
        cond.append(Comprobante.direccion == f.direccion)
    if f.estatus:
        cond.append(Comprobante.estatus_sat == f.estatus)
    if f.rfc:
        rfc = f.rfc.strip().upper()
        # La contraparte: el receptor de lo emitido, el emisor de lo recibido.
        cond.append(or_(
            and_(Comprobante.direccion == "emitido", Comprobante.rfc_receptor == rfc),
            and_(Comprobante.direccion == "recibido", Comprobante.rfc_emisor == rfc),
        ))
    return cond


def listar(
    db: Session, cliente: Cliente, filtros: Filtros, pagina: int = 1, por_pagina: int = 50
) -> tuple[list[Comprobante], int]:
    """Una página de comprobantes (más recientes primero) y el total que cumple el filtro."""
    cond = _condiciones(cliente, filtros)
    total = db.scalar(select(func.count(Comprobante.id)).where(*cond)) or 0
    filas = db.scalars(
        select(Comprobante).where(*cond)
        .order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        .offset((pagina - 1) * por_pagina).limit(por_pagina)
    )
    return list(filas), int(total)


def obtener(db: Session, cliente: Cliente, uuid: str) -> Comprobante:
    """El comprobante `uuid` del cliente, o 404."""
    comp = db.scalar(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.uuid == uuid.strip().upper()
    ))
    if comp is None:
        raise FiscalAgentError(f"No existe el CFDI {uuid} en la bóveda de este cliente.", 404)
    return comp


def leer_xml_original(comp: Comprobante, almacen: Almacenamiento | None = None) -> bytes:
    """Los bytes tal como se subieron. 500 si el almacén devolvió otra cosa."""
    datos = (almacen or obtener_almacenamiento()).leer(comp.ruta_xml)
    if hashlib.sha256(datos).hexdigest() != comp.sha256:
        raise FiscalAgentError(
            f"El XML guardado de {comp.uuid} no coincide con su huella; no se entrega.", 500
        )
    return datos


def borrar(
    db: Session, cliente: Cliente, uuid: str, almacen: Almacenamiento | None = None
) -> None:
    """Quita el comprobante de la bóveda y su XML del almacén."""
    comp = obtener(db, cliente, uuid)
    db.delete(comp)
    db.flush()
    (almacen or obtener_almacenamiento()).borrar(comp.ruta_xml)


def resumen(db: Session, cliente: Cliente, filtros: Filtros) -> list[dict[str, Any]]:
    """Conteos y totales por mes, tipo y dirección."""
    anio = extract("year", Comprobante.fecha)
    mes = extract("month", Comprobante.fecha)
    filas = db.execute(
        select(anio, mes, Comprobante.tipo, Comprobante.direccion,
               func.count(Comprobante.id), func.sum(Comprobante.total))
        .where(*_condiciones(cliente, filtros))
        .group_by(anio, mes, Comprobante.tipo, Comprobante.direccion)
        .order_by(anio, mes, Comprobante.tipo, Comprobante.direccion)
    )
    return [
        {"periodo": f"{int(a):04d}-{int(m):02d}", "tipo": t, "direccion": d,
         "cantidad": int(c), "total": f"{(s or 0):.2f}"}
        for a, m, t, d, c, s in filas
    ]
