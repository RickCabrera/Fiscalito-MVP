"""
Ciclo de vida de una solicitud de descarga masiva (P1-01).

    pendiente ──solicitar──▶ solicitada ──verificar──▶ en_proceso ─┐ (horas o días)
        ▲                                   │                     │
        │ (5004/vencida, 1 vez)             ▼ EstadoSolicitud=3   │
        └───────────────────────────── descargando ──▶ terminada ◀┘
    Terminales: terminada · sin_datos (5004) · fallida · dividida (5003 → hijas)

`avanzar(db, solicitud, …)` da UN paso y deja escrito qué sigue y cuándo
(`proxima_verificacion`). Nunca lanza por un error del SAT: lo traduce a español en `mensaje`
y decide si reintentar (con backoff), esperar, partir el rango o fallar.

IDEMPOTENCIA
------------
- La solicitud se identifica por su `huella` (cliente + parámetros). Pedir lo mismo otra vez
  devuelve la misma fila y no manda nada al SAT (`crear_o_reusar`).
- `veces_solicitada` cuenta las veces que se mandó al SAT: el SAT permite DOS solicitudes de
  por vida con los mismos parámetros (5002). Sólo se re-solicita si el SAT perdió la anterior
  (5004 en verificación, paquetes vencidos) y nunca más de `MAX_VECES_SOLICITADA`.
- Cada paquete importado queda en `paquetes_procesados` y se confirma (commit) al terminarlo:
  un worker que muere a media descarga retoma en el siguiente paquete. La bóveda además
  deduplica por UUID, así que repetir un paquete sólo cuenta duplicados.
- El ZIP de cada paquete se guarda en el almacenamiento (`ruta_paquete`) ANTES de importarlo:
  si el proceso muere durante la importación, la siguiente corrida lo lee de ahí y no lo
  vuelve a pedir al SAT (que sólo entrega cada paquete dos veces).
- Dos workers no avanzan la misma solicitud: `bloquear` toma la fila con
  `FOR UPDATE SKIP LOCKED` (Postgres); el que no la obtiene se retira.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.boveda_cfdi import servicio as boveda
from app.db.base import ahora as _ahora_db
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.integraciones.sat_descarga import ClienteDescargaSat, ErrorSat, obtener_cliente_sat
from app.integraciones.sat_soap import Firmante, ParametrosSolicitud
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import (
    ESTADOS_VIVOS_SOLICITUD,
    AlertaDescargaSat,
    SolicitudDescargaSat,
)
from app.sat_descarga import metadata

logger = logging.getLogger(__name__)


def reloj() -> datetime:
    """Momento actual (UTC). Un solo punto para que los tests adelanten el tiempo."""
    return _ahora_db()

# ── parámetros (configurables por entorno; defaults documentados en servicios-externos.md) ──


def _env_int(nombre: str, default: int) -> int:
    try:
        return int(os.environ.get(nombre, "") or default)
    except ValueError:
        return default


def dias_max_espera() -> int:
    """Días que se espera a que el SAT termine una solicitud antes de darla por fallida."""
    return _env_int("FISCALITO_SAT_DIAS_MAX_ESPERA", 7)


def horas_aviso_atorada() -> int:
    """Horas en proceso a partir de las cuales se deja una alerta de solicitud atorada."""
    return _env_int("FISCALITO_SAT_HORAS_AVISO", 24)


PRIMERA_VERIFICACION = timedelta(minutes=2)
TECHO_VERIFICACION = timedelta(hours=2)
MAX_INTENTOS_ERROR = 8
MAX_VECES_SOLICITADA = 2
# Un rango que el SAT rechaza por tope (5003) se parte mientras dure más que esto.
RANGO_MINIMO = timedelta(hours=1)

TERMINALES = ("terminada", "sin_datos", "fallida", "dividida")

# ── mensajes en español de cada código documentado ──

MENSAJES: dict[str, str] = {
    "300": "El SAT no reconoce al usuario (300). Revisa que la e.firma sea del RFC del cliente.",
    "301": "El SAT dice que la solicitud está mal formada (301). Revisa RFC y fechas.",
    "302": "El SAT dice que el sello está mal formado (302).",
    "303": "El sello no corresponde con el RFC solicitante (303): la e.firma es de otro RFC.",
    "304": "La e.firma está revocada o caduca (304). Renuévala en el SAT y súbela de nuevo.",
    "305": "El SAT considera inválido el certificado (305). Sube la e.firma (no el CSD).",
    "404": "El SAT tuvo un error no controlado (404). Se reintenta más tarde.",
    "5000": "Solicitud recibida con éxito.",
    "5001": "El SAT dice que este RFC no está autorizado para descargar estos comprobantes "
            "(5001, tercero no autorizado).",
    "5002": "Se agotaron las solicitudes de por vida con estos mismos parámetros (5002). El "
            "SAT sólo permite pedir dos veces el mismo rango; pide un rango distinto.",
    "5003": "El rango rebasa el tope de comprobantes del SAT (5003): se parte en rangos más "
            "chicos.",
    "5004": "El SAT no encontró comprobantes con estos filtros (5004).",
    "5005": "Ya hay una solicitud vigente con los mismos parámetros en el SAT (5005). Se "
            "espera y se reintenta.",
    "5006": "Error interno del SAT (5006). Se reintenta más tarde.",
    "5007": "El paquete ya no existe en el SAT (5007): los paquetes sólo duran 72 horas.",
    "5008": "El SAT ya entregó este paquete el máximo de dos veces (5008).",
    "5011": "Se alcanzó el límite de descargas por folio por día (5011).",
    "5012": "El SAT no permite descargar XML cancelados (5012).",
}
ESTADOS_SAT = {1: "Aceptada", 2: "En proceso", 3: "Terminada", 4: "Error", 5: "Rechazada",
               6: "Vencida"}
TRANSITORIOS = {"404", "5006", "5011"}
DEFINITIVOS = {"300", "301", "302", "303", "304", "305", "5001", "5012"}


def mensaje_de(codigo: str, original: str = "") -> str:
    """El mensaje en español de un código del SAT (con el texto del SAT si no se conoce)."""
    if codigo in MENSAJES:
        return MENSAJES[codigo]
    return f"El SAT respondió {codigo or 'sin código'}: {original or 'sin mensaje'}."


# ── creación idempotente ──


@dataclass(frozen=True)
class Pedido:
    """Lo que se pide al SAT, en hora local de la Ciudad de México."""

    direccion: str
    tipo: str
    fecha_inicial: datetime
    fecha_final: datetime
    estado: str = "todos"
    rfc_contraparte: str = ""
    tipo_comprobante: str = ""

    def parametros(self) -> ParametrosSolicitud:
        return ParametrosSolicitud(
            self.direccion, self.tipo, self.fecha_inicial, self.fecha_final, self.estado,
            self.rfc_contraparte, self.tipo_comprobante,
        )


def huella(cliente_id: int, p: Pedido) -> str:
    texto = "|".join([
        str(cliente_id), p.direccion, p.tipo, p.estado,
        p.fecha_inicial.isoformat(), p.fecha_final.isoformat(),
        p.rfc_contraparte.upper(), p.tipo_comprobante,
    ])
    return hashlib.sha256(texto.encode()).hexdigest()


def pedido_de(s: SolicitudDescargaSat) -> Pedido:
    return Pedido(s.direccion, s.tipo, s.fecha_inicial, s.fecha_final, s.estado_comprobante,
                  s.rfc_contraparte, s.tipo_comprobante)


def crear_o_reusar(
    db: Session, cliente: Cliente, p: Pedido, origen: str = "manual",
    padre_id: int | None = None,
) -> tuple[SolicitudDescargaSat, bool]:
    """
    La solicitud con esos parámetros: la existente si ya hay, o una nueva `pendiente`.

    Devuelve `(solicitud, nueva)`. Una `fallida` que el SAT nunca agotó vuelve a `pendiente`
    (p. ej. falló porque faltaba la e.firma y ya se subió); las demás se devuelven tal cual.
    """
    h = huella(cliente.id, p)
    existente = db.scalar(select(SolicitudDescargaSat).where(
        SolicitudDescargaSat.cliente_id == cliente.id, SolicitudDescargaSat.huella == h
    ))
    if existente is not None:
        if existente.estado == "fallida" and existente.codigo != "5002":
            existente.estado = "pendiente"
            existente.intentos = 0
            existente.proxima_verificacion = reloj()
            existente.mensaje = "Se volvió a pedir."
            db.flush()
        return existente, False
    s = SolicitudDescargaSat(
        cliente_id=cliente.id, direccion=p.direccion, tipo=p.tipo,
        estado_comprobante=p.estado, fecha_inicial=p.fecha_inicial,
        fecha_final=p.fecha_final, rfc_contraparte=p.rfc_contraparte.upper(),
        tipo_comprobante=p.tipo_comprobante, huella=h, origen=origen, padre_id=padre_id,
        estado="pendiente", proxima_verificacion=reloj(), paquetes=[],
        paquetes_procesados=[],
    )
    # Dos peticiones simultáneas con la misma huella: el índice único decide.
    try:
        with db.begin_nested():
            db.add(s)
            db.flush()
    except IntegrityError:
        otra = db.scalar(select(SolicitudDescargaSat).where(
            SolicitudDescargaSat.cliente_id == cliente.id, SolicitudDescargaSat.huella == h
        ))
        if otra is None:
            raise
        return otra, False
    return s, True


# ── ventanas ──


def inicio_dia(d: date) -> datetime:
    return datetime.combine(d, time.min)


def fin_dia(d: date) -> datetime:
    return datetime.combine(d, time(23, 59, 59))


def ventanas_por_mes(desde: date, hasta: date) -> list[tuple[datetime, datetime]]:
    """[desde, hasta] partido por mes calendario: (día 1 00:00:00, último día 23:59:59)."""
    if desde > hasta:
        return []
    salida = []
    actual = desde
    while actual <= hasta:
        siguiente = (actual.replace(day=1) + timedelta(days=32)).replace(day=1)
        fin = min(hasta, siguiente - timedelta(days=1))
        salida.append((inicio_dia(actual), fin_dia(fin)))
        actual = siguiente
    return salida


def partir(inicio: datetime, fin: datetime) -> list[tuple[datetime, datetime]]:
    """Dos mitades de un rango (para el tope 5003). Por día si dura más de un día."""
    if fin - inicio > timedelta(days=1):
        dias = (fin.date() - inicio.date()).days
        corte = inicio.date() + timedelta(days=dias // 2)
        return [(inicio, fin_dia(corte)), (inicio_dia(corte + timedelta(days=1)), fin)]
    mitad = inicio + (fin - inicio) / 2
    mitad = mitad.replace(microsecond=0)
    return [(inicio, mitad), (mitad + timedelta(seconds=1), fin)]


# ── alertas ──


def alertar(db: Session, cliente_id: int, tipo: str, mensaje: str,
            solicitud_id: int | None = None) -> AlertaDescargaSat:
    """Una alerta abierta por (cliente, tipo, solicitud): no se repite."""
    previa = db.scalar(select(AlertaDescargaSat).where(
        AlertaDescargaSat.cliente_id == cliente_id, AlertaDescargaSat.tipo == tipo,
        AlertaDescargaSat.solicitud_id == solicitud_id,
        AlertaDescargaSat.resuelta.is_(False),
    ))
    if previa is not None:
        previa.mensaje = mensaje
        db.flush()
        return previa
    alerta = AlertaDescargaSat(cliente_id=cliente_id, tipo=tipo, mensaje=mensaje,
                               solicitud_id=solicitud_id)
    db.add(alerta)
    db.flush()
    logger.warning("Alerta SAT %s cliente_id=%s: %s", tipo, cliente_id, mensaje)
    return alerta


# ── concurrencia ──


def consulta_bloqueo(solicitud_id: int) -> Any:
    """
    SELECT … FOR UPDATE SKIP LOCKED de una solicitud. En Postgres, dos workers que toman la
    misma solicitud no la pisan: el segundo no la obtiene y se retira (no espera). SQLite no
    tiene bloqueo de fila y SQLAlchemy omite la cláusula: ahí sigue igual (un solo worker).
    """
    return (select(SolicitudDescargaSat).where(SolicitudDescargaSat.id == solicitud_id)
            .with_for_update(skip_locked=True))


def bloquear(db: Session, solicitud_id: int) -> SolicitudDescargaSat | None:
    """La solicitud con su fila bloqueada hasta el siguiente commit; None si otro la tiene."""
    return db.scalar(consulta_bloqueo(solicitud_id).execution_options(populate_existing=True))


# ── el paso ──


def primera_verificacion() -> timedelta:
    """
    Cuánto se espera para la primera verificación (default 2 min, `PRIMERA_VERIFICACION`).

    `FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION` lo acorta para las pruebas de punta a
    punta (P6-04), que con el SAT falso no tienen por qué esperar dos minutos. Las esperas
    siguientes escalan desde aquí.
    """
    segundos = _env_int("FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION", 0)
    return timedelta(seconds=segundos) if segundos > 0 else PRIMERA_VERIFICACION


def _espera(verificaciones: int) -> timedelta:
    """2, 4, 8, 16, 32, 64 min… con techo de 2 h."""
    return min(primera_verificacion() * (2 ** max(verificaciones - 1, 0)), TECHO_VERIFICACION)


def _fallar(db: Session, s: SolicitudDescargaSat, codigo: str, mensaje: str,
            tipo_alerta: str = "error_sat") -> None:
    s.estado, s.codigo, s.mensaje = "fallida", codigo, mensaje
    s.proxima_verificacion = None
    s.terminada_en = reloj()
    alertar(db, s.cliente_id, tipo_alerta, mensaje, s.id)


def _reintentar_despues(db: Session, s: SolicitudDescargaSat, codigo: str, mensaje: str,
                        momento: datetime) -> None:
    """Error transitorio: se anota y se reprograma con backoff, hasta MAX_INTENTOS_ERROR."""
    s.intentos += 1
    s.codigo, s.mensaje = codigo, mensaje
    if s.intentos >= MAX_INTENTOS_ERROR:
        _fallar(db, s, codigo, f"{mensaje} Se intentó {s.intentos} veces; se dejó de intentar.")
        return
    s.proxima_verificacion = momento + _espera(s.intentos)


def _re_solicitar(db: Session, s: SolicitudDescargaSat, codigo: str, mensaje: str,
                  momento: datetime) -> None:
    """El SAT perdió la solicitud o sus paquetes: se pide otra vez si quedan oportunidades."""
    if s.veces_solicitada >= MAX_VECES_SOLICITADA:
        _fallar(db, s, codigo, f"{mensaje} Ya se pidió {s.veces_solicitada} veces, que es lo "
                "que el SAT permite con los mismos parámetros.", "agotada")
        return
    s.estado, s.codigo, s.mensaje = "pendiente", codigo, f"{mensaje} Se vuelve a solicitar."
    s.id_solicitud = ""
    s.paquetes = []
    s.verificaciones = 0
    s.proxima_verificacion = momento


def _dividir(db: Session, cliente: Cliente, s: SolicitudDescargaSat, momento: datetime) -> None:
    if s.fecha_final - s.fecha_inicial <= RANGO_MINIMO:
        _fallar(db, s, "5003", "El SAT tiene más comprobantes de los que entrega en una "
                "solicitud aun en un rango de una hora (5003). Pide por RFC contraparte o "
                "por tipo de comprobante.")
        return
    base = pedido_de(s)
    for ini, fin in partir(s.fecha_inicial, s.fecha_final):
        hija, _ = crear_o_reusar(
            db, cliente,
            Pedido(base.direccion, base.tipo, ini, fin, base.estado, base.rfc_contraparte,
                   base.tipo_comprobante),
            origen="division", padre_id=s.id,
        )
        hija.proxima_verificacion = momento
    s.estado, s.codigo, s.mensaje = "dividida", "5003", MENSAJES["5003"]
    s.proxima_verificacion = None
    s.terminada_en = momento


@dataclass
class Contexto:
    """Lo que necesita un paso: el cliente del SAT, la e.firma y el almacén."""

    sat: ClienteDescargaSat
    firmante: Firmante
    almacen: Almacenamiento


def _paso_solicitar(db: Session, cliente: Cliente, s: SolicitudDescargaSat,
                    c: Contexto, momento: datetime) -> None:
    p = pedido_de(s).parametros()
    errores = p.errores(hoy=momento.replace(tzinfo=None))
    if errores:
        _fallar(db, s, "local", " ".join(errores))
        return
    r = c.sat.solicitar(c.firmante, p)
    s.codigo, s.mensaje = r.codigo, mensaje_de(r.codigo, r.mensaje)
    if r.codigo == "5000" and r.id_solicitud:
        s.estado, s.id_solicitud = "solicitada", r.id_solicitud
        s.veces_solicitada += 1
        s.intentos = 0
        s.verificaciones = 0
        s.solicitada_en = s.solicitada_en or momento
        s.proxima_verificacion = momento + primera_verificacion()
    elif r.codigo == "5003":
        _dividir(db, cliente, s, momento)
    elif r.codigo == "5004":
        s.estado, s.terminada_en, s.proxima_verificacion = "sin_datos", momento, None
    elif r.codigo == "5002":
        _fallar(db, s, r.codigo, s.mensaje, "agotada")
    elif r.codigo == "5005":
        # Existe una igual vigente en el SAT pero no tenemos su id (se perdió la respuesta).
        # Se espera a que venza (72 h) con backoff largo; no se cuenta como error del SAT.
        s.intentos += 1
        if s.intentos >= MAX_INTENTOS_ERROR:
            _fallar(db, s, r.codigo, s.mensaje)
        else:
            s.proxima_verificacion = momento + timedelta(hours=min(2 ** s.intentos, 24))
    elif r.codigo in DEFINITIVOS:
        _fallar(db, s, r.codigo, s.mensaje)
    else:
        _reintentar_despues(db, s, r.codigo, s.mensaje, momento)


def _paso_verificar(db: Session, cliente: Cliente, s: SolicitudDescargaSat,
                    c: Contexto, momento: datetime) -> None:
    r = c.sat.verificar(c.firmante, s.id_solicitud)
    s.verificaciones += 1
    if r.codigo != "5000":
        msg = mensaje_de(r.codigo, r.mensaje)
        if r.codigo == "5004":
            _re_solicitar(db, s, r.codigo, "El SAT no encontró la solicitud.", momento)
        elif r.codigo in DEFINITIVOS:
            _fallar(db, s, r.codigo, msg)
        else:
            _reintentar_despues(db, s, r.codigo, msg, momento)
        return
    s.estado_sat = r.estado
    s.numero_cfdis = r.numero_cfdis
    s.intentos = 0
    if r.estado in (1, 2):
        s.estado = "en_proceso"
        s.codigo = r.codigo_estado or r.codigo
        inicio = s.solicitada_en or momento
        esperado = momento - inicio
        s.mensaje = (f"El SAT sigue procesando la solicitud ({ESTADOS_SAT[r.estado]}); "
                     f"lleva {_duracion(esperado)}.")
        if esperado >= timedelta(days=dias_max_espera()):
            _fallar(db, s, "atorada", f"El SAT no terminó la solicitud en "
                    f"{dias_max_espera()} días. Se puede volver a pedir.", "atorada")
            return
        if esperado >= timedelta(hours=horas_aviso_atorada()) and not s.aviso_atorada:
            s.aviso_atorada = True
            alertar(db, s.cliente_id, "atorada",
                    f"La solicitud {s.id_solicitud} lleva {_duracion(esperado)} en proceso en "
                    "el SAT. Se sigue verificando sola; no hace falta hacer nada.", s.id)
        s.proxima_verificacion = momento + _espera(s.verificaciones)
    elif r.estado == 3:
        s.paquetes = list(r.paquetes)
        s.estado = "descargando"
        s.codigo, s.mensaje = "5000", f"Lista en el SAT: {len(r.paquetes)} paquete(s)."
        s.proxima_verificacion = momento
        if not r.paquetes:
            s.estado, s.terminada_en, s.proxima_verificacion = "sin_datos", momento, None
    elif r.estado == 5:
        cod = r.codigo_estado
        if cod == "5004":
            s.estado, s.codigo, s.mensaje = "sin_datos", cod, MENSAJES["5004"]
            s.terminada_en, s.proxima_verificacion = momento, None
        elif cod == "5003":
            _dividir(db, cliente, s, momento)
        elif cod == "5002":
            _fallar(db, s, cod, MENSAJES["5002"], "agotada")
        else:
            _fallar(db, s, cod or "5", f"El SAT rechazó la solicitud. {mensaje_de(cod)}")
    elif r.estado == 6:
        _re_solicitar(db, s, "6", "La solicitud venció en el SAT (paquetes de más de 72 h).",
                      momento)
    else:  # 4 error u otro
        _re_solicitar(db, s, str(r.estado), f"El SAT marcó la solicitud con error "
                      f"({ESTADOS_SAT.get(r.estado, r.estado)}).", momento)


def ruta_paquete(cliente: Cliente, s: SolicitudDescargaSat, paquete: str) -> str:
    """Dónde queda el ZIP de un paquete en el almacén (por despacho, cliente y solicitud)."""
    limpio = "".join(ch for ch in paquete if ch.isalnum() or ch in "-_") or "paquete"
    return f"sat/paquetes/{cliente.despacho_id}/{cliente.id}/{s.id}/{limpio}.zip"


def _paso_descargar(db: Session, cliente: Cliente, s: SolicitudDescargaSat,
                    c: Contexto, momento: datetime) -> None:
    hechos = list(s.paquetes_procesados or [])
    for paquete in list(s.paquetes or []):
        if paquete in hechos:
            continue
        ruta = ruta_paquete(cliente, s, paquete)
        with tempfile.TemporaryFile() as zipf:
            if c.almacen.existe(ruta):
                # Ya se había descargado y guardado (el proceso murió al importarlo): se
                # retoma desde el almacén; el SAT sólo entrega cada paquete dos veces.
                zipf.write(c.almacen.leer(ruta))
            else:
                r = c.sat.descargar(c.firmante, paquete, zipf)
                if r.codigo != "5000":
                    msg = mensaje_de(r.codigo, r.mensaje)
                    if r.codigo in ("5007", "5008"):
                        _re_solicitar(db, s, r.codigo, msg, momento)
                    elif r.codigo in DEFINITIVOS:
                        _fallar(db, s, r.codigo, msg)
                    else:
                        _reintentar_despues(db, s, r.codigo, msg, momento)
                    return
                # Se guarda ANTES de importar: si el proceso muere a media importación, la
                # siguiente corrida no vuelve a pedir el paquete al SAT.
                zipf.seek(0)
                c.almacen.guardar(zipf.read(), ruta)
            zipf.seek(0)
            if s.tipo == "metadata":
                s.metadata_registros += metadata.guardar(db, cliente, zipf, c.firmante.rfc)
            else:
                rep = boveda.importar(db, cliente, [(f"{paquete}.zip", zipf)], c.almacen,
                                      origen="sat", rfc=c.firmante.rfc, detalle=False)
                s.xml_importados += rep.importados
                s.duplicados += rep.duplicados
                s.rechazados += len(rep.rechazados)
        hechos.append(paquete)
        s.paquetes_procesados = list(hechos)
        s.mensaje = f"Paquete {len(hechos)} de {len(s.paquetes)} importado."
        # Cada paquete se confirma al terminarlo: si el proceso muere, se retoma en el
        # siguiente y no se vuelve a pedir uno ya importado (el SAT sólo da dos descargas).
        db.commit()
        # El commit soltó el bloqueo de la fila: se vuelve a tomar antes del siguiente
        # paquete. Si otro worker la tomó en ese instante, él sigue y éste se retira.
        if bloquear(db, s.id) is None:
            return
    s.estado, s.terminada_en, s.proxima_verificacion = "terminada", momento, None
    s.codigo = "5000"
    if s.tipo == "metadata":
        s.mensaje = f"Terminada: {s.metadata_registros} registro(s) de metadata."
    else:
        s.mensaje = (f"Terminada: {s.xml_importados} XML nuevos en la bóveda, "
                     f"{s.duplicados} ya existían.")


def _duracion(t: timedelta) -> str:
    horas = int(t.total_seconds() // 3600)
    if horas >= 48:
        return f"{horas // 24} días"
    if horas >= 1:
        return f"{horas} h"
    return f"{max(int(t.total_seconds() // 60), 0)} min"


def avanzar(
    db: Session, solicitud: SolicitudDescargaSat, ctx: Contexto,
    ahora: datetime | None = None,
) -> SolicitudDescargaSat:
    """Da el paso que toque. Los errores del SAT quedan escritos en la solicitud."""
    momento = ahora or reloj()
    s = solicitud
    if s.estado in TERMINALES:
        return s
    cliente = db.get(Cliente, s.cliente_id)
    assert cliente is not None
    try:
        if s.estado == "pendiente":
            _paso_solicitar(db, cliente, s, ctx, momento)
        elif s.estado in ("solicitada", "en_proceso"):
            _paso_verificar(db, cliente, s, ctx, momento)
        if s.estado == "descargando":
            _paso_descargar(db, cliente, s, ctx, momento)
    except ErrorSat as e:
        if e.transitorio:
            _reintentar_despues(db, s, "red", e.message, momento)
        else:
            _fallar(db, s, "auth", e.message)
    db.flush()
    return s


def correr_hasta_esperar(
    db: Session, solicitud: SolicitudDescargaSat, ctx: Contexto,
    ahora: datetime | None = None, max_pasos: int = 10,
) -> SolicitudDescargaSat:
    """Avanza mientras el siguiente paso toque YA (p. ej. verificar → descargar)."""
    momento = ahora or reloj()
    for _ in range(max_pasos):
        antes = (solicitud.estado, solicitud.verificaciones, solicitud.veces_solicitada)
        avanzar(db, solicitud, ctx, momento)
        if solicitud.estado in TERMINALES:
            break
        prox = solicitud.proxima_verificacion
        if prox is None or prox > momento:
            break
        if (solicitud.estado, solicitud.verificaciones, solicitud.veces_solicitada) == antes:
            break
    return solicitud


def contexto_por_default(firmante: Firmante) -> Contexto:
    return Contexto(obtener_cliente_sat(), firmante, obtener_almacenamiento())


def vivas_vencidas(db: Session, momento: datetime, limite: int = 500) -> list[int]:
    """Ids de solicitudes vivas cuyo siguiente paso ya toca."""
    return list(db.scalars(
        select(SolicitudDescargaSat.id).where(
            SolicitudDescargaSat.estado.in_(ESTADOS_VIVOS_SOLICITUD),
            (SolicitudDescargaSat.proxima_verificacion.is_(None))
            | (SolicitudDescargaSat.proxima_verificacion <= momento),
        ).order_by(SolicitudDescargaSat.proxima_verificacion).limit(limite)
    ))


def como_dict(s: SolicitudDescargaSat) -> dict[str, Any]:
    def iso(d: datetime | None) -> str | None:
        return d.isoformat() if d else None

    return {
        "id": s.id, "direccion": s.direccion, "tipo": s.tipo,
        "estado_comprobante": s.estado_comprobante,
        "fecha_inicial": s.fecha_inicial.isoformat(), "fecha_final": s.fecha_final.isoformat(),
        "rfc_contraparte": s.rfc_contraparte, "tipo_comprobante": s.tipo_comprobante,
        "origen": s.origen, "padre_id": s.padre_id, "id_solicitud": s.id_solicitud,
        "estado": s.estado, "codigo": s.codigo, "mensaje": s.mensaje,
        "numero_cfdis": s.numero_cfdis, "paquetes": len(s.paquetes or []),
        "paquetes_procesados": len(s.paquetes_procesados or []),
        "xml_importados": s.xml_importados, "duplicados": s.duplicados,
        "rechazados": s.rechazados, "metadata_registros": s.metadata_registros,
        "veces_solicitada": s.veces_solicitada, "verificaciones": s.verificaciones,
        "intentos": s.intentos, "proxima_verificacion": iso(s.proxima_verificacion),
        "solicitada_en": iso(s.solicitada_en), "terminada_en": iso(s.terminada_en),
        "creado_en": iso(s.creado_en),
    }
