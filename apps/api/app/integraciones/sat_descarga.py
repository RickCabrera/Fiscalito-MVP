"""
Descarga masiva de CFDI del SAT (P1-01). `FISCALITO_SAT_DESCARGA` = falso | sat.

Interfaz (`ClienteDescargaSat`):
- `solicitar(firmante, parametros)` → `ResultadoSolicitud` (CodEstatus, Mensaje, IdSolicitud)
- `verificar(firmante, id_solicitud)` → `ResultadoVerificacion` (EstadoSolicitud, paquetes…)
- `descargar(firmante, id_paquete, destino)` → `ResultadoDescarga`; escribe el ZIP en
  `destino` (un archivo) sin tenerlo entero en memoria.

`sat` es implementación propia del web service oficial (mensajes en `sat_soap.py`): autentica
con WS-Security firmado con la e.firma, guarda el token por RFC y lo renueva cuando vence
(≈5 min) o cuando el SAT lo rechaza. `falso` no toca la red: responde lo que el test o la
pantalla de desarrollo le programen, y por default "sin información" (5004).

Las reglas de negocio (reintentos, días de espera, partir rangos, idempotencia) NO viven aquí:
viven en `app/sat_descarga/servicio.py`, que es el que decide qué hacer con cada código.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Protocol

import httpx

from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.sat_soap import (
    ACCION_AUTENTICA,
    ACCION_DESCARGA,
    ACCION_VERIFICA,
    Firmante,
    ParametrosSolicitud,
    RespuestaIlegible,
    ResultadoDescarga,
    ResultadoSolicitud,
    ResultadoVerificacion,
    Token,
    extraer_paquete,
    falla_soap,
    leer,
    leer_solicitud,
    leer_token,
    leer_verificacion,
    sobre_autenticacion,
    sobre_descarga,
    sobre_solicitud,
    sobre_verificacion,
)

# URLs de producción del servicio de CFDI (las publica el SAT en su portal; las mismas que usa
# phpcfdi/sat-ws-descarga-masiva desde la versión 1.5 del servicio, 2025-05-30).
URL_AUTENTICACION = (
    "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
)
URL_SOLICITUD = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
URL_VERIFICACION = (
    "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
)
URL_DESCARGA = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"

# El paquete puede pesar cientos de MB: la lectura tiene más paciencia que el resto.
TIMEOUT = httpx.Timeout(60.0, connect=15.0, read=300.0)
VIDA_TOKEN = timedelta(minutes=5)


class ErrorSat(FiscalAgentError):
    """El SAT no respondió lo que se esperaba. `transitorio`: vale la pena reintentar."""

    def __init__(self, mensaje: str, transitorio: bool = True) -> None:
        super().__init__(mensaje, status_code=502)
        self.transitorio = transitorio


class ClienteDescargaSat(Protocol):
    def solicitar(self, firmante: Firmante, p: ParametrosSolicitud) -> ResultadoSolicitud: ...

    def verificar(self, firmante: Firmante, id_solicitud: str) -> ResultadoVerificacion: ...

    def descargar(
        self, firmante: Firmante, id_paquete: str, destino: IO[bytes]
    ) -> ResultadoDescarga: ...


# ── falso ──


@dataclass
class DescargaSatFalso:
    """
    Sin red y determinístico.

    - `al_solicitar(p)` → lista de ZIP (bytes) que "generará" esa solicitud; None = sin datos.
    - `en_proceso`: cuántas verificaciones responden "en proceso" antes de terminar.
    - `codigo_solicitud`: fuerza el CodEstatus de `solicitar` (p. ej. "5003", "5002").
    - `llamadas` registra cada operación, para que los tests cuenten.
    """

    al_solicitar: Callable[[ParametrosSolicitud], list[bytes] | None] | None = None
    en_proceso: int = 0
    codigo_solicitud: str = "5000"
    llamadas: list[tuple[str, str]] = field(default_factory=list)
    _solicitudes: dict[str, list[str]] = field(default_factory=dict)
    _paquetes: dict[str, bytes] = field(default_factory=dict)
    _verificadas: dict[str, int] = field(default_factory=dict)

    def solicitar(self, firmante, p):
        self.llamadas.append(("solicitar", f"{p.direccion}:{p.tipo}:{p.fecha_inicial}"))
        if self.codigo_solicitud != "5000":
            return ResultadoSolicitud(self.codigo_solicitud, "Respuesta programada del falso")
        ident = f"falso-{len(self._solicitudes) + 1:06d}"
        zips = (self.al_solicitar(p) if self.al_solicitar else None) or []
        ids = []
        for n, contenido in enumerate(zips, start=1):
            pid = f"{ident}_{n:02d}"
            self._paquetes[pid] = contenido
            ids.append(pid)
        self._solicitudes[ident] = ids
        return ResultadoSolicitud("5000", "Solicitud Aceptada", ident)

    def verificar(self, firmante, id_solicitud):
        self.llamadas.append(("verificar", id_solicitud))
        if id_solicitud not in self._solicitudes:
            return ResultadoVerificacion("5004", "No se encontró la solicitud")
        vista = self._verificadas.get(id_solicitud, 0) + 1
        self._verificadas[id_solicitud] = vista
        if vista <= self.en_proceso:
            return ResultadoVerificacion("5000", "Solicitud Aceptada", 2, "5000")
        ids = self._solicitudes[id_solicitud]
        if not ids:
            return ResultadoVerificacion("5000", "Solicitud Aceptada", 5, "5004")
        return ResultadoVerificacion("5000", "Solicitud Aceptada", 3, "5000", len(ids), list(ids))

    def descargar(self, firmante, id_paquete, destino):
        self.llamadas.append(("descargar", id_paquete))
        datos = self._paquetes.get(id_paquete)
        if datos is None:
            return ResultadoDescarga("5007", "No existe el paquete solicitado")
        destino.write(datos)
        return ResultadoDescarga("5000", "Solicitud Aceptada", len(datos))


# ── real ──


class DescargaSatReal:
    """El web service del SAT por SOAP sobre httpx."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        reloj: Callable[[], datetime] | None = None,
        urls: dict[str, str] | None = None,
    ) -> None:
        self._http = http if http is not None else httpx.Client(timeout=TIMEOUT)
        self._reloj = reloj or (lambda: datetime.now(UTC))
        u = urls or {}
        self.url_autenticacion = u.get("autenticacion", URL_AUTENTICACION)
        self.url_solicitud = u.get("solicitud", URL_SOLICITUD)
        self.url_verificacion = u.get("verificacion", URL_VERIFICACION)
        self.url_descarga = u.get("descarga", URL_DESCARGA)
        self._tokens: dict[str, Token] = {}

    # token

    def token(self, firmante: Firmante, forzar: bool = False) -> str:
        """Token vigente del RFC; autentica si no hay, si venció o si se pide `forzar`."""
        ahora = self._reloj()
        actual = self._tokens.get(firmante.rfc)
        if actual and actual.vigente(ahora) and not forzar:
            return actual.valor
        cuerpo = sobre_autenticacion(firmante, ahora, ahora + VIDA_TOKEN)
        r = self._post(self.url_autenticacion, ACCION_AUTENTICA, cuerpo, None)
        raiz = self._xml(r, "la autenticación")
        falla = falla_soap(raiz)
        if falla:
            raise ErrorSat(
                "El SAT rechazó la autenticación con la e.firma: "
                f"{falla[1] or falla[0]}. Revisa que la e.firma esté vigente y no revocada.",
                transitorio=False,
            )
        self._exigir_2xx(r, "la autenticación")
        token = leer_token(r.content, ahora)
        self._tokens[firmante.rfc] = token
        return token.valor

    def olvidar_token(self, rfc: str) -> None:
        self._tokens.pop(rfc, None)

    # http

    def _post(self, url: str, accion: str, cuerpo: str, token: str | None) -> httpx.Response:
        encabezados = {"SOAPAction": accion, "Content-Type": 'text/xml; charset="utf-8"'}
        if token is not None:
            encabezados["Authorization"] = f'WRAP access_token="{token}"'
        try:
            return self._http.post(url, content=cuerpo.encode("utf-8"), headers=encabezados)
        except httpx.TransportError as e:
            raise ErrorSat(f"No hubo conexión con el SAT ({type(e).__name__}).") from e

    @staticmethod
    def _xml(r: httpx.Response, que: str):
        try:
            return leer(r.content)
        except RespuestaIlegible as e:
            if r.status_code >= 500 or not r.content:
                raise ErrorSat(f"El SAT falló en {que} (HTTP {r.status_code}).") from e
            raise ErrorSat(f"El SAT respondió algo ilegible en {que}.") from e

    @staticmethod
    def _exigir_2xx(r: httpx.Response, que: str) -> None:
        if not r.is_success:
            raise ErrorSat(f"El SAT respondió HTTP {r.status_code} en {que}.")

    @staticmethod
    def _rechazo_de_token(r: httpx.Response, falla: tuple[str, str] | None) -> bool:
        if r.status_code in (401, 403):
            return True
        texto = " ".join(falla).lower() if falla else ""
        return any(p in texto for p in ("token", "autentica", "authentication", "security"))

    def _llamar(self, firmante: Firmante, url: str, accion: str, cuerpo: str, que: str):
        """POST con token; si el SAT dice que el token no sirve, se renueva UNA vez."""
        for intento in (1, 2):
            r = self._post(url, accion, cuerpo, self.token(firmante, forzar=intento == 2))
            raiz = self._xml(r, que)
            falla = falla_soap(raiz)
            if self._rechazo_de_token(r, falla) and intento == 1:
                self.olvidar_token(firmante.rfc)
                continue
            if falla:
                raise ErrorSat(f"El SAT respondió un error en {que}: {falla[1] or falla[0]}")
            self._exigir_2xx(r, que)
            return r
        raise ErrorSat(f"El SAT rechazó el token dos veces en {que}.")  # pragma: no cover

    # operaciones

    def solicitar(self, firmante: Firmante, p: ParametrosSolicitud) -> ResultadoSolicitud:
        accion, cuerpo = sobre_solicitud(firmante, p)
        r = self._llamar(firmante, self.url_solicitud, accion, cuerpo, "la solicitud")
        return leer_solicitud(r.content)

    def verificar(self, firmante: Firmante, id_solicitud: str) -> ResultadoVerificacion:
        cuerpo = sobre_verificacion(firmante, id_solicitud)
        r = self._llamar(firmante, self.url_verificacion, ACCION_VERIFICA, cuerpo,
                         "la verificación")
        return leer_verificacion(r.content)

    def descargar(
        self, firmante: Firmante, id_paquete: str, destino: IO[bytes]
    ) -> ResultadoDescarga:
        """La respuesta va a un archivo temporal en trozos y de ahí se decodifica el ZIP."""
        cuerpo = sobre_descarga(firmante, id_paquete).encode("utf-8")
        for intento in (1, 2):
            token = self.token(firmante, forzar=intento == 2)
            encabezados = {
                "SOAPAction": ACCION_DESCARGA,
                "Content-Type": 'text/xml; charset="utf-8"',
                "Authorization": f'WRAP access_token="{token}"',
            }
            with tempfile.TemporaryFile() as crudo:
                try:
                    with self._http.stream("POST", self.url_descarga, content=cuerpo,
                                           headers=encabezados) as r:
                        for trozo in r.iter_bytes():
                            crudo.write(trozo)
                        estado = r.status_code
                except httpx.TransportError as e:
                    raise ErrorSat(f"Se cortó la descarga del paquete ({type(e).__name__}).") \
                        from e
                if estado in (401, 403) and intento == 1:
                    self.olvidar_token(firmante.rfc)
                    continue
                try:
                    resultado = extraer_paquete(crudo, destino)
                except RespuestaIlegible as e:
                    raise ErrorSat(str(e)) from e
                if resultado.codigo == "fault" and intento == 1 and any(
                    p in resultado.mensaje.lower() for p in ("token", "autentica", "security")
                ):
                    self.olvidar_token(firmante.rfc)
                    destino.seek(0)
                    destino.truncate()
                    continue
                if resultado.codigo == "fault":
                    raise ErrorSat(f"El SAT respondió un error en la descarga: "
                                   f"{resultado.mensaje}")
                if estado >= 400 and not resultado.codigo:
                    raise ErrorSat(f"El SAT respondió HTTP {estado} en la descarga.")
                return resultado
        raise ErrorSat("El SAT rechazó el token dos veces en la descarga.")  # pragma: no cover


def _real() -> DescargaSatReal:
    urls = {
        k: v for k, v in {
            "autenticacion": os.environ.get("FISCALITO_SAT_URL_AUTENTICACION", ""),
            "solicitud": os.environ.get("FISCALITO_SAT_URL_SOLICITUD", ""),
            "verificacion": os.environ.get("FISCALITO_SAT_URL_VERIFICACION", ""),
            "descarga": os.environ.get("FISCALITO_SAT_URL_DESCARGA", ""),
        }.items() if v
    }
    return DescargaSatReal(urls=urls)


def paquetes_de_carpeta(carpeta: Path) -> Callable[[ParametrosSolicitud], list[bytes] | None]:
    """
    `al_solicitar` que entrega los XML de `carpeta/<emitidos|recibidos>/` (P6-04).

    Un ZIP por solicitud con los CFDI cuya `Fecha` cae en el rango pedido; la metadata no
    se simula (responde "sin información"). Es lo que hace que el recorrido e2e baje
    comprobantes de verdad a la bóveda sin tocar la red.
    """

    def al_solicitar(p: ParametrosSolicitud) -> list[bytes] | None:
        if p.tipo != "cfdi":
            return None
        buf = io.BytesIO()
        n = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for xml in sorted((carpeta / p.direccion).glob("*.xml")):
                fecha = re.search(rb'Fecha="([0-9T:-]{19})"', xml.read_bytes())
                if fecha is None:
                    continue
                momento = datetime.fromisoformat(fecha.group(1).decode())
                if p.fecha_inicial <= momento <= p.fecha_final:
                    zf.write(xml, xml.name)
                    n += 1
        return [buf.getvalue()] if n else None

    return al_solicitar


def _falso() -> DescargaSatFalso:
    """
    `falso` sin datos (5004 en todo); con `FISCALITO_SAT_FALSO_DIR` entrega los XML de esa
    carpeta. Sólo es para desarrollo y e2e: con `FISCALITO_ENTORNO=produccion` no hay
    default `falso` (ver `registro.elegida`).
    """
    carpeta = os.environ.get("FISCALITO_SAT_FALSO_DIR", "").strip()
    if not carpeta:
        return DescargaSatFalso()
    return DescargaSatFalso(al_solicitar=paquetes_de_carpeta(Path(carpeta)))


registro.registrar(
    "sat_descarga", "falso", _falso,
    "Descarga masiva de CFDI y metadata del web service del SAT (P1-01)",
)
registro.registrar("sat_descarga", "sat", _real)


def obtener_cliente_sat() -> ClienteDescargaSat:
    """El cliente configurado por `FISCALITO_SAT_DESCARGA`."""
    return registro.obtener("sat_descarga")
