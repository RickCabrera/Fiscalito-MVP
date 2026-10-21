"""
Listados del SAT (art. 69-B y 69 del CFF): carga del CSV y cruce con la bóveda (P1-04).

PARSEO ROBUSTO
--------------
El CSV del SAT viene en latin-1 (a veces cp1252, a veces UTF-8 con BOM), con uno o más
renglones de título antes del encabezado, encabezados con acentos y mayúsculas variables, y
fechas `dd/mm/aaaa`. Por eso:
1. se decodifica UTF-8 (con BOM) y, si falla, cp1252 → latin-1;
2. el encabezado es el primer renglón que tiene una columna "RFC";
3. las columnas se reconocen por palabras clave sin acentos, no por posición;
4. un renglón sin RFC válido se descarta (el SAT agrega notas al pie).

REEMPLAZO, NO ACUMULACIÓN
-------------------------
Cada carga reemplaza la lista completa: un contribuyente que el SAT quitó (desvirtuado y luego
retirado) deja de estar. Si el archivo no cambió (mismo SHA-256) no se toca nada y sólo se
anota la revisión. Si el archivo viene vacío o con menos del 50 % de los renglones de la
carga anterior, NO se reemplaza: es más probable un archivo truncado que una amnistía.

CRUCE (EFOS / EDOS)
-------------------
- Proveedores: emisores de los CFDI **recibidos** del cliente que están en la lista → riesgo
  de que el SAT desconozca la deducción (el cliente sería EDOS si no se autocorrige).
- Clientes: receptores de los CFDI **emitidos** → informativo (el cliente le facturó a un EFOS).
- El propio RFC del cliente en la lista → alerta propia.
Situación 69-B → nivel: `definitivo` alto, `presunto` medio, `desvirtuado` y
`sentencia_favorable` informativo (no se marca en rojo). Listas del 69 → medio.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integraciones.sat_listas import LISTAS, SatListas
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import AlertaRiesgo, CargaListaSat, ContribuyenteListaSat

RFC_VALIDO = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
UMBRAL_TRUNCADO = 0.5

# Situación 69-B → (normalizada, nivel, se marca en rojo)
SITUACIONES_69B: dict[str, tuple[str, str, bool]] = {
    "definitivo": ("definitivo", "alto", True),
    "presunto": ("presunto", "medio", True),
    "desvirtuado": ("desvirtuado", "info", False),
    "sentencia favorable": ("sentencia_favorable", "info", False),
}


def _plano(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                  if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin).strip().lower()


def decodificar(datos: bytes) -> str:
    """UTF-8 (con o sin BOM) y si no, cp1252/latin-1 (lo normal en el SAT)."""
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return datos.decode("cp1252")
    except UnicodeDecodeError:
        return datos.decode("latin-1")


def _fecha(texto: str) -> date | None:
    texto = (texto or "").strip()
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", texto)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


@dataclass
class RenglonLista:
    rfc: str
    nombre: str
    situacion: str
    situacion_texto: str
    fecha_publicacion_sat: date | None
    fecha_publicacion_dof: date | None
    datos: dict[str, str] = field(default_factory=dict)


def _columna(encabezados: list[str], *claves: str, excluir: tuple[str, ...] = ()) -> int | None:
    """Índice de la PRIMERA columna cuyo encabezado contiene todas las `claves`."""
    for i, e in enumerate(encabezados):
        p = _plano(e)
        if all(c in p for c in claves) and not any(x in p for x in excluir):
            return i
    return None


def _columnas_fecha(encabezados: list[str], medio: str) -> list[int]:
    """Columnas 'Publicación ... <medio>' en orden (presuntos, definitivos, desvirtuados...)."""
    return [i for i, e in enumerate(encabezados)
            if "publicacion" in _plano(e) and medio in _plano(e)]


def _situacion(lista: str, texto: str) -> str:
    p = _plano(texto)
    if lista == "69b":
        for clave, (norm, _n, _r) in SITUACIONES_69B.items():
            if clave in p:
                return norm
        return p.replace(" ", "_")[:60] or "desconocida"
    return lista.removeprefix("69_")


def parsear_csv(datos: bytes, lista: str) -> list[RenglonLista]:
    """Renglones con RFC válido. `ValueError` si no hay encabezado con RFC."""
    texto = decodificar(datos)
    # El delimitador se deduce del ENCABEZADO (el primer renglón con una celda "RFC"), no
    # de una muestra: los renglones de título y los nombres con comas engañan al Sniffer.
    delimitador = None
    for linea in texto.splitlines()[:50]:
        for d in (",", ";", "|", "\t"):
            if any(_plano(c).strip('"') == "rfc" for c in linea.split(d)):
                delimitador = d
                break
        if delimitador:
            break
    if delimitador is None:
        raise ValueError(f"El CSV de la lista {lista} no trae una columna RFC.")
    filas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    inicio = next((i for i, f in enumerate(filas)
                   if any(_plano(c) == "rfc" for c in f)), None)
    if inicio is None:
        raise ValueError(f"El CSV de la lista {lista} no trae una columna RFC.")
    enc = [c.strip() for c in filas[inicio]]
    i_rfc = next(i for i, c in enumerate(enc) if _plano(c) == "rfc")
    i_nombre = _columna(enc, "nombre") or _columna(enc, "razon social")
    i_sit = _columna(enc, "situacion") or _columna(enc, "supuesto")
    cols_sat = _columnas_fecha(enc, "sat")
    cols_dof = _columnas_fecha(enc, "dof")

    def ultima_fecha(fila: list[str], cols: list[int]) -> date | None:
        fechas = [_fecha(fila[i]) for i in cols if i < len(fila)]
        validas = [f for f in fechas if f]
        return max(validas) if validas else None

    salida: dict[str, RenglonLista] = {}
    for fila in filas[inicio + 1:]:
        if i_rfc >= len(fila):
            continue
        rfc = fila[i_rfc].strip().upper().replace(" ", "")
        if not RFC_VALIDO.match(rfc):
            continue
        sit_texto = fila[i_sit].strip() if i_sit is not None and i_sit < len(fila) else ""
        salida[rfc] = RenglonLista(
            rfc=rfc,
            nombre=(fila[i_nombre].strip() if i_nombre is not None and i_nombre < len(fila)
                    else "")[:400],
            situacion=_situacion(lista, sit_texto),
            situacion_texto=sit_texto[:200],
            fecha_publicacion_sat=ultima_fecha(fila, cols_sat),
            fecha_publicacion_dof=ultima_fecha(fila, cols_dof),
            datos={enc[i] if i < len(enc) else f"col{i}": v.strip()
                   for i, v in enumerate(fila) if v.strip()},
        )
    return list(salida.values())


@dataclass
class ResultadoCarga:
    lista: str
    registros: int = 0
    sin_cambios: bool = False
    rechazada: str | None = None
    url: str = ""

    def como_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def cargar_lista(db: Session, lista: str, adaptador: SatListas,
                 ahora: datetime | None = None) -> ResultadoCarga:
    """Descarga, parsea y reemplaza la lista. Idempotente (mismo archivo = sin cambios)."""
    momento = ahora or datetime.now(UTC)
    datos, url = adaptador.descargar(lista)
    huella = hashlib.sha256(datos).hexdigest()
    carga = db.get(CargaListaSat, lista) or CargaListaSat(lista=lista)
    db.add(carga)
    carga.revisada_en, carga.url = momento, url[:500]
    r = ResultadoCarga(lista=lista, url=url)
    if carga.sha256 == huella and carga.cargada_en is not None:
        carga.error = None
        r.sin_cambios, r.registros = True, carga.registros
        db.flush()
        return r
    renglones = parsear_csv(datos, lista)
    anteriores = carga.registros or 0
    if not renglones or (anteriores and len(renglones) < anteriores * UMBRAL_TRUNCADO):
        r.rechazada = (f"El archivo trae {len(renglones)} renglones contra {anteriores} de la "
                       "carga anterior; parece truncado y no se reemplazó.")
        carga.error = r.rechazada
        db.flush()
        return r
    db.execute(delete(ContribuyenteListaSat).where(ContribuyenteListaSat.lista == lista))
    db.add_all(ContribuyenteListaSat(
        lista=lista, rfc=x.rfc, nombre=x.nombre, situacion=x.situacion,
        situacion_texto=x.situacion_texto, fecha_publicacion_sat=x.fecha_publicacion_sat,
        fecha_publicacion_dof=x.fecha_publicacion_dof, fecha_carga=momento, datos=x.datos,
    ) for x in renglones)
    carga.registros, carga.sha256, carga.cargada_en, carga.error = (
        len(renglones), huella, momento, None)
    r.registros = len(renglones)
    db.flush()
    return r


def registrar_error(db: Session, lista: str, error: str) -> None:
    carga = db.get(CargaListaSat, lista) or CargaListaSat(lista=lista)
    db.add(carga)
    carga.revisada_en = datetime.now(UTC)
    carga.error = error[:2000]
    db.flush()


def estado_listas(db: Session) -> list[dict[str, Any]]:
    cargas = {c.lista: c for c in db.scalars(select(CargaListaSat))}
    salida = []
    for lista, (_url, descripcion) in LISTAS.items():
        c = cargas.get(lista)
        salida.append({
            "lista": lista, "descripcion": descripcion,
            "registros": c.registros if c else 0,
            "cargada_en": c.cargada_en.isoformat() if c and c.cargada_en else None,
            "revisada_en": c.revisada_en.isoformat() if c and c.revisada_en else None,
            "url": c.url if c else "", "error": c.error if c else None,
        })
    return salida


# ── cruce ──


def nivel_de(lista: str, situacion: str) -> tuple[str, bool]:
    """(nivel, se marca en rojo)."""
    if lista == "69b":
        for norm, nivel, rojo in SITUACIONES_69B.values():
            if norm == situacion:
                return nivel, rojo
        return "medio", True
    return "medio", False


@dataclass
class Riesgo:
    rfc: str
    nombre: str
    lista: str
    situacion: str
    situacion_texto: str
    relacion: str
    nivel: str
    rojo: bool
    comprobantes: int
    total: str
    fecha_publicacion_sat: date | None
    fecha_publicacion_dof: date | None

    def como_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        for k in ("fecha_publicacion_sat", "fecha_publicacion_dof"):
            d[k] = d[k].isoformat() if d[k] else None
        return d


def _contrapartes(db: Session, cliente: Cliente) -> dict[tuple[str, str], tuple[int, Any]]:
    """{(rfc, relacion): (n comprobantes, total)} de las contrapartes del cliente."""
    from sqlalchemy import func

    salida: dict[tuple[str, str], tuple[int, Any]] = {}
    for direccion, columna, relacion in (
        ("recibido", Comprobante.rfc_emisor, "proveedor"),
        ("emitido", Comprobante.rfc_receptor, "cliente"),
    ):
        filas = db.execute(
            select(columna, func.count(Comprobante.id), func.sum(Comprobante.total))
            .where(Comprobante.cliente_id == cliente.id, Comprobante.direccion == direccion)
            .group_by(columna)
        )
        for rfc, n, total in filas:
            salida[(rfc, relacion)] = (int(n), total or 0)
    return salida


def riesgos_de(db: Session, cliente: Cliente) -> list[Riesgo]:
    """Contrapartes del cliente (y él mismo) que están en algún listado cargado."""
    contrapartes = _contrapartes(db, cliente)
    rfcs = {rfc for rfc, _ in contrapartes}
    propio = (cliente.rfc or str((cliente.datos or {}).get("rfc") or "")).strip().upper()
    if propio:
        rfcs.add(propio)
    if not rfcs:
        return []
    en_lista = list(db.scalars(select(ContribuyenteListaSat)
                              .where(ContribuyenteListaSat.rfc.in_(rfcs))))
    salida: list[Riesgo] = []
    for x in en_lista:
        nivel, rojo = nivel_de(x.lista, x.situacion)
        relaciones = [rel for (rfc, rel) in contrapartes if rfc == x.rfc]
        if x.rfc == propio:
            relaciones.append("propio")
        for rel in relaciones:
            n, total = contrapartes.get((x.rfc, rel), (0, 0))
            salida.append(Riesgo(
                rfc=x.rfc, nombre=x.nombre, lista=x.lista, situacion=x.situacion,
                situacion_texto=x.situacion_texto, relacion=rel, nivel=nivel,
                rojo=rojo and rel != "cliente", comprobantes=n, total=f"{total:.2f}",
                fecha_publicacion_sat=x.fecha_publicacion_sat,
                fecha_publicacion_dof=x.fecha_publicacion_dof,
            ))
    orden = {"alto": 0, "medio": 1, "info": 2}
    return sorted(salida, key=lambda r: (orden.get(r.nivel, 3), r.relacion, r.rfc))


def cruzar_cliente(db: Session, cliente: Cliente) -> list[AlertaRiesgo]:
    """Crea las alertas nuevas del cliente (idempotente por `clave`). Devuelve las nuevas."""
    existentes = set(db.scalars(select(AlertaRiesgo.clave)
                                .where(AlertaRiesgo.cliente_id == cliente.id)))
    nuevas: list[AlertaRiesgo] = []
    for r in riesgos_de(db, cliente):
        if r.nivel == "info" and r.relacion != "propio":
            continue  # desvirtuados / sentencia favorable: se ven, no alertan
        tipo = "propio_69b" if r.relacion == "propio" else (
            "art69b" if r.lista == "69b" else "art69")
        clave = f"{r.lista}:{r.situacion}:{r.relacion}:{r.rfc}"[:120]
        if clave in existentes:
            continue
        alerta = AlertaRiesgo(
            despacho_id=cliente.despacho_id, cliente_id=cliente.id, tipo=tipo, clave=clave,
            rfc=r.rfc, nombre=r.nombre[:400], lista=r.lista, situacion=r.situacion,
            relacion=r.relacion, nivel=r.nivel,
            detalle={"comprobantes": r.comprobantes, "total": r.total,
                     "situacion_texto": r.situacion_texto},
        )
        try:
            with db.begin_nested():
                db.add(alerta)
                db.flush()
        except IntegrityError:
            continue
        existentes.add(clave)
        nuevas.append(alerta)
    return nuevas


def clientes_con_contraparte_listada(db: Session) -> list[Cliente]:
    """Clientes (de todos los despachos) con alguna contraparte o RFC propio en un listado."""
    listados = select(ContribuyenteListaSat.rfc).distinct()
    ids = set(db.scalars(select(Comprobante.cliente_id).distinct().where(or_(
        and_(Comprobante.direccion == "recibido", Comprobante.rfc_emisor.in_(listados)),
        and_(Comprobante.direccion == "emitido", Comprobante.rfc_receptor.in_(listados)),
    ))))
    ids |= set(db.scalars(select(Cliente.id).where(Cliente.rfc.in_(listados))))
    if not ids:
        return []
    return list(db.scalars(select(Cliente).where(Cliente.id.in_(ids)).order_by(Cliente.id)))


def rfcs_marcados(db: Session, rfcs: Iterable[str]) -> dict[str, dict[str, str]]:
    """{rfc: {lista, situacion, nivel}} de los RFC que están en un listado y van en rojo
    o en ámbar. Lo usa la bóveda para la columna "Art. 69-B"."""
    rfcs = {r for r in rfcs if r}
    if not rfcs:
        return {}
    salida: dict[str, dict[str, str]] = {}
    for x in db.scalars(select(ContribuyenteListaSat)
                        .where(ContribuyenteListaSat.rfc.in_(rfcs))):
        nivel, _rojo = nivel_de(x.lista, x.situacion)
        previo = salida.get(x.rfc)
        if previo is None or (x.lista == "69b" and previo["lista"] != "69b"):
            salida[x.rfc] = {"lista": x.lista, "situacion": x.situacion, "nivel": nivel}
    return salida
