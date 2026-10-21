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

import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import IO, Any

from sqlalchemy.orm import Session

# La consulta vive en `consulta.py` (P6-05); se reexporta para no cambiar a quien importa.
from app.boveda_cfdi.consulta import (  # noqa: F401
    Filtros,
    _comprobante,
    _condiciones,
    _existe,
    borrar,
    comprobantes_vigentes,
    leer_xml_original,
    listar,
    obtener,
    resumen,
)
from app.boveda_cfdi.parser import CfdiInvalido, CfdiLeido, parsear_cfdi
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.modelos.nucleo import Cliente

# Un CFDI real rara vez pasa de 1 MB; los de nómina con cientos de conceptos, de 5.
MAX_BYTES_XML = 10 * 1024 * 1024
# Topes globales por ZIP (revisor P0): sin ellos, un ZIP con millones de miembros pequeños
# o un total descomprimido enorme agota memoria y CPU aunque cada XML sea chico.
MAX_MIEMBROS_ZIP = 250_000
MAX_BYTES_ZIP = 4 * 1024 * 1024 * 1024
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
        miembros = zf.infolist()
        if len(miembros) > MAX_MIEMBROS_ZIP:
            yield nombre_zip, None, (
                f"El ZIP trae {len(miembros):,} archivos; el máximo por carga es "
                f"{MAX_MIEMBROS_ZIP:,}. Pártelo en varios."
            )
            return
        leidos = 0
        for info in miembros:
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
            leidos += len(datos)
            if leidos > MAX_BYTES_ZIP:
                yield nombre, None, "El ZIP pasa del tope total descomprimido; pártelo en varios."
                return
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
    rfc: str | None = None,
    detalle: bool = True,
) -> Reporte:
    """
    Importa XML y ZIP a la bóveda del cliente. Ver el docstring del módulo.

    `rfc` fuerza el RFC con el que se clasifica (la descarga del SAT usa el de la e.firma,
    que es el que el SAT respondió). `detalle=False` no guarda un renglón por XML en el
    reporte: un paquete del SAT trae hasta 200,000 y sólo interesan los conteos.
    """
    almacen = almacen or obtener_almacenamiento()
    archivos = list(archivos)
    reporte = Reporte(rfc_cliente=(rfc or rfc_del_cliente(cliente)).strip().upper())
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
            if detalle:
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
        if detalle:
            reporte.importados_detalle.append(
                {"archivo": nombre, "uuid": cfdi.uuid, "direccion": direccion, "tipo": cfdi.tipo}
            )
        pendientes += 1
        if pendientes >= LOTE_FLUSH:
            db.flush()
            pendientes = 0
    db.flush()
    return reporte
