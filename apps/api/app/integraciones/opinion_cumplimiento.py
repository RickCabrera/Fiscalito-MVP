"""
Opinión de cumplimiento (32-D) y constancia de situación fiscal (P1-05, DP-2).

`FISCALITO_OPINION_CUMPLIMIENTO` = falso | portal_sat | proveedor | manual.

El SAT no tiene API oficial para estos dos documentos, así que hay cuatro vías y **la elección
es de Ricardo (DP-2)**. En las cuatro, el despacho puede además subir el PDF a mano
(`POST .../opinion/pdf`): esa ruta no pasa por el adaptador.

- `falso`: sin red; arma un PDF sintético con el texto de una opinión positiva (o la que se
  le fije por RFC). Pasa por el mismo lector de PDF que uno real.
- `portal_sat`: automatiza el portal del SAT con httpx, autenticándose con la **e.firma del
  cliente** (`obtener_firmante`). Zona gris: el SAT no lo documenta y puede cambiar sin
  aviso. Cada paso que no se pudo verificar con una e.firma real lleva
  `# POR CONFIRMAR CON E.FIRMA REAL:` y cada paso falla con un mensaje que dice CUÁL paso
  dejó de reconocer, para que un cambio del portal se diagnostique en minutos.
  Flujo tomado de `SAT-CFDI/python-satcfdi` (MIT), `satcfdi/portal/__init__.py`
  (`SATPortalOpinionCumplimiento`, `SATPortalConstancia`, `fiel_login`) y
  `portal/utils.py::generate_token`, consultado 2026-10-19.
- `proveedor`: cliente HTTP genérico para un proveedor externo, todo por variables (URL,
  API key, encabezado, mapeo de campos). Ver `docs/servicios-externos.md`.
- `manual`: no consulta nada; "obtener ahora" responde 409 y pide subir el PDF.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid as uuidlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

import httpx
from cryptography import x509

from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno, cliente_http, env, revisar

TIPOS = ("opinion", "constancia")
RESULTADOS = ("positiva", "negativa", "sin_obligaciones", "desconocido")


@dataclass(frozen=True)
class SolicitudCumplimiento:
    """
    Qué pedir y de quién. `firmante` es perezoso: sólo `portal_sat` lo llama, así un
    cliente sin e.firma puede usar el falso, el proveedor o el manual.
    """

    rfc: str
    tipo: str
    firmante: Callable[[], Any] | None = None


@dataclass(frozen=True)
class DocumentoObtenido:
    """El PDF y, si el origen lo sabe sin leer el PDF, el resultado/folio/fecha."""

    pdf: bytes
    resultado: str | None = None
    folio: str = ""
    fecha: date | None = None
    datos: dict[str, Any] = field(default_factory=dict)


class OpinionCumplimiento(Protocol):
    nombre: str

    def obtener(self, solicitud: SolicitudCumplimiento) -> DocumentoObtenido: ...


def _validar_tipo(tipo: str) -> None:
    if tipo not in TIPOS:
        raise FiscalAgentError(f"Tipo de documento desconocido: {tipo}.", status_code=422)


# ── falso ──


@dataclass
class OpinionFalsa:
    """Determinística. `resultados[rfc]` fija el sentido (default positiva)."""

    nombre: str = "falso"
    resultados: dict[str, str] = field(default_factory=dict)
    solicitudes: list[SolicitudCumplimiento] = field(default_factory=list)
    fecha_fija: date | None = None

    def obtener(self, solicitud: SolicitudCumplimiento) -> DocumentoObtenido:
        from app.sat_verificacion.pdf import pdf_texto  # evita ciclo de importación

        _validar_tipo(solicitud.tipo)
        self.solicitudes.append(solicitud)
        hoy = self.fecha_fija or date.today()
        fecha_txt = f"{hoy.day} de {_MES[hoy.month]} de {hoy.year}"
        huella = hashlib.sha256(f"{solicitud.rfc}|{hoy.isoformat()}".encode()).hexdigest()
        folio = f"26NA{int(huella[:12], 16) % 10**10:010d}"
        if solicitud.tipo == "constancia":
            pdf = pdf_texto([
                "CONSTANCIA DE SITUACION FISCAL (SINTETICA - ADAPTADOR FALSO)",
                f"RFC: {solicitud.rfc}",
                "idCIF: 12345678901",
                f"Lugar y Fecha de Emision: CIUDAD DE MEXICO A {fecha_txt.upper()}",
            ])
            return DocumentoObtenido(pdf=pdf, folio="12345678901", fecha=hoy)
        sentido = self.resultados.get(solicitud.rfc, "positiva")
        frase = {
            "positiva": "se emite opinion del cumplimiento de obligaciones fiscales en sentido "
                        "POSITIVO",
            "negativa": "se emite opinion del cumplimiento de obligaciones fiscales en sentido "
                        "NEGATIVO",
            "sin_obligaciones": "el contribuyente se encuentra INSCRITO SIN OBLIGACIONES",
        }.get(sentido, "documento sin sentido reconocible")
        pdf = pdf_texto([
            "OPINION DEL CUMPLIMIENTO DE OBLIGACIONES FISCALES (SINTETICA - ADAPTADOR FALSO)",
            f"Folio: {folio}",
            f"RFC: {solicitud.rfc}",
            f"Revision practicada el dia {fecha_txt}",
            frase,
        ])
        return DocumentoObtenido(pdf=pdf, resultado=None, folio=folio, fecha=hoy)


_MES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio",
        8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}


# ── manual ──


class OpinionManual:
    """El despacho sube el PDF; esta vía nunca consulta nada."""

    nombre = "manual"

    def obtener(self, solicitud: SolicitudCumplimiento) -> DocumentoObtenido:
        raise FiscalAgentError(
            "Este despacho obtiene la opinión y la constancia a mano "
            "(FISCALITO_OPINION_CUMPLIMIENTO=manual): descárgala del portal del SAT y súbela "
            "en PDF.",
            status_code=409,
        )


# ── proveedor externo genérico ──


def _por_ruta(datos: Any, ruta: str) -> Any:
    """`data.items.0.pdf` sobre dicts/listas. None si no existe."""
    actual = datos
    for parte in ruta.split("."):
        if isinstance(actual, dict):
            actual = actual.get(parte)
        elif isinstance(actual, list) and parte.isdigit() and int(parte) < len(actual):
            actual = actual[int(parte)]
        else:
            return None
    return actual


CAMPOS_DEFAULT = {"pdf_base64": "pdf", "resultado": "resultado", "folio": "folio",
                  "fecha": "fecha"}


class OpinionProveedor:
    """
    Proveedor externo configurable. Variables (todas `FISCALITO_OPINION_PROVEEDOR_*`):
    `URL` (con `{rfc}` y `{tipo}`), `API_KEY`, `ENCABEZADO` (default `Authorization`, valor
    `Bearer <key>`; con otro encabezado va la key sola), `METODO` (GET | POST; POST manda
    `{"rfc", "tipo"}` en JSON), `CAMPOS` (JSON: dónde viene cada dato en la respuesta) y
    `RESULTADOS` (JSON: valor del proveedor → positiva | negativa | sin_obligaciones).
    Si el proveedor responde `application/pdf`, el cuerpo es el PDF.
    """

    nombre = "proveedor"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.url = env("FISCALITO_OPINION_PROVEEDOR_URL")
        self.api_key = env("FISCALITO_OPINION_PROVEEDOR_API_KEY")
        self.encabezado = env("FISCALITO_OPINION_PROVEEDOR_ENCABEZADO", "Authorization")
        self.metodo = env("FISCALITO_OPINION_PROVEEDOR_METODO", "GET").upper()
        self.campos = {**CAMPOS_DEFAULT, **self._json("FISCALITO_OPINION_PROVEEDOR_CAMPOS")}
        self.resultados = {str(k).lower(): v for k, v in
                           self._json("FISCALITO_OPINION_PROVEEDOR_RESULTADOS").items()}
        self.http = cliente_http(http)

    @staticmethod
    def _json(variable: str) -> dict[str, str]:
        valor = os.environ.get(variable, "").strip()
        if not valor:
            return {}
        try:
            datos = json.loads(valor)
        except json.JSONDecodeError as e:
            raise FiscalAgentError(f"{variable} no es JSON válido: {e}", status_code=503) from e
        if not isinstance(datos, dict):
            raise FiscalAgentError(f"{variable} debe ser un objeto JSON.", status_code=503)
        return datos

    def obtener(self, solicitud: SolicitudCumplimiento) -> DocumentoObtenido:
        _validar_tipo(solicitud.tipo)
        url = self.url.replace("{rfc}", solicitud.rfc).replace("{tipo}", solicitud.tipo)
        valor = f"Bearer {self.api_key}" if self.encabezado.lower() == "authorization" \
            else self.api_key
        encabezados = {self.encabezado: valor, "Accept": "application/json, application/pdf"}
        try:
            if self.metodo == "POST":
                r = self.http.post(url, json={"rfc": solicitud.rfc, "tipo": solicitud.tipo},
                                   headers=encabezados)
            else:
                r = self.http.get(url, headers=encabezados)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo consultar al proveedor: {e}") from e
        revisar(r, "Proveedor de opinión de cumplimiento")
        if "application/pdf" in r.headers.get("content-type", ""):
            return DocumentoObtenido(pdf=r.content)
        try:
            cuerpo = r.json()
        except ValueError as e:
            raise ErrorServicioExterno("El proveedor no respondió JSON ni PDF.") from e
        b64 = _por_ruta(cuerpo, self.campos["pdf_base64"])
        if not b64:
            raise ErrorServicioExterno(
                f"La respuesta del proveedor no trae el PDF en '{self.campos['pdf_base64']}' "
                "(revisa FISCALITO_OPINION_PROVEEDOR_CAMPOS)."
            )
        try:
            pdf = base64.b64decode(str(b64), validate=False)
        except ValueError as e:
            raise ErrorServicioExterno("El PDF del proveedor no es base64 válido.") from e
        crudo = _por_ruta(cuerpo, self.campos["resultado"])
        resultado = None
        if crudo is not None:
            resultado = self.resultados.get(str(crudo).lower(), str(crudo).lower())
            if resultado not in RESULTADOS:
                resultado = "desconocido"
        fecha_txt = _por_ruta(cuerpo, self.campos["fecha"])
        fecha = None
        if fecha_txt:
            try:
                fecha = date.fromisoformat(str(fecha_txt)[:10])
            except ValueError:
                fecha = None
        folio = _por_ruta(cuerpo, self.campos["folio"])
        return DocumentoObtenido(pdf=pdf, resultado=resultado,
                                 folio=str(folio or ""), fecha=fecha)


# ── portal del SAT con e.firma ──


class PortalCambio(ErrorServicioExterno):
    """El portal del SAT ya no se ve como se esperaba en un paso del flujo."""

    def __init__(self, paso: str, detalle: str) -> None:
        super().__init__(
            f"El portal del SAT cambió en el paso '{paso}': {detalle}. La automatización "
            "necesita ajuste; mientras tanto sube el PDF a mano."
        )


def formulario(html: str, url: str, id_form: str | None = None
               ) -> tuple[str | None, dict[str, str]]:
    """(action absoluta, {input: valor}) del primer `<form method=post>` (o el de `id`)."""
    from lxml import html as lhtml

    if not html.strip():
        return None, {}
    try:
        doc = lhtml.fromstring(html)
    except (ValueError, Exception):  # noqa: BLE001 — HTML vacío o roto = sin formulario
        return None, {}
    formas = doc.xpath(f'//form[@id="{id_form}"]' if id_form else "//form")
    if not formas:
        return None, {}
    forma = formas[0]
    datos = {i.get("name"): i.get("value") or "" for i in forma.xpath(".//input")
             if i.get("name")}
    accion = forma.get("action") or url
    return urljoin(url, accion), datos


def token_fiel(firmante: Any, guid: str) -> str:
    """
    Token del login con e.firma: base64( base64(guid|rfc|serie) + "#" +
    base64(base64(firma SHA1withRSA)) ). Igual que `generate_token` de python-satcfdi.
    """
    cadena = f"{guid}|{firmante.rfc}|{firmante.numero_certificado}".encode()
    firma_b64 = base64.b64encode(firmante.firmar_sha1(cadena))
    return base64.b64encode(base64.b64encode(cadena) + b"#" + base64.b64encode(firma_b64)
                            ).decode()


def fert_de(firmante: Any) -> str:
    """Fin de vigencia del certificado como `AAMMDDhhmmssZ` (campo `fert` del login)."""
    cert = x509.load_der_x509_certificate(firmante.certificado_der)
    return cert.not_valid_after_utc.strftime("%y%m%d%H%M%SZ")


URL_OPINION = "https://ptsc32d.clouda.sat.gob.mx/?/reporteOpinion32DContribuyente"
URL_OPINION_PDF = (
    "https://ptsc32d.clouda.sat.gob.mx/RespuestaCompleta/ObtenerRespuestaCompletaPdf"
)
URL_CONSTANCIA_LOGIN = "https://login.siat.sat.gob.mx/nidp/idff/sso?id=fiel_Aviso"
URL_CONSTANCIA_BROKER = (
    "https://rfcampc.siat.sat.gob.mx/app/seg/SessionBroker?url=/PTSC/IdcSiat/autc/"
    "ReimpresionTramite/ConsultaTramite.jsf&parametro=c&idSessionBit=&idSessionBit=null"
)
URL_CONSTANCIA_REIMP = (
    "https://rfcampc.siat.sat.gob.mx/PTSC/IdcSiat/autc/ReimpresionTramite/ConsultaTramite.jsf"
)
URL_CONSTANCIA_PDF = "https://rfcampc.siat.sat.gob.mx/PTSC/IdcSiat/IdcGeneraConstancia.jsf"
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


class OpinionPortalSat:
    """Portal del SAT con la e.firma del cliente. Ver el docstring del módulo."""

    nombre = "portal_sat"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self._http_inyectado = http

    def _sesion(self) -> httpx.Client:
        # Una sesión (cookies) por consulta: nunca se comparten cookies entre clientes.
        if self._http_inyectado is not None:
            self._http_inyectado.cookies.clear()
            return self._http_inyectado
        return httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True,
                            headers={"User-Agent": AGENTE})

    @staticmethod
    def _post_form(http: httpx.Client, accion: str, referer: str, datos: dict[str, str],
                   paso: str) -> httpx.Response:
        partes = urlparse(referer)
        try:
            r = http.post(accion, data=datos, follow_redirects=True, headers={
                "Origin": f"{partes.scheme}://{partes.netloc}", "Referer": referer,
            })
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso '{paso}': {e}") from e
        if r.status_code != 200:
            raise PortalCambio(paso, f"respondió {r.status_code}")
        return r

    def _login_fiel(self, http: httpx.Client, r: httpx.Response, firmante: Any
                    ) -> httpx.Response:
        # POR CONFIRMAR CON E.FIRMA REAL: el formulario `certform` con su campo `guid` y los
        # campos `token` y `fert` son los que usa python-satcfdi; no se vio la página real.
        accion, datos = formulario(r.text, str(r.url), "certform")
        if not accion or "guid" not in datos:
            raise PortalCambio("login e.firma", "no está el formulario 'certform' con 'guid'")
        datos = {**datos, "token": token_fiel(firmante, datos["guid"]),
                 "fert": fert_de(firmante)}
        respuesta = self._post_form(http, accion, str(r.url), datos, "login e.firma")
        if "certform" in respuesta.text and "guid" in respuesta.text:
            raise FiscalAgentError(
                "El SAT rechazó la e.firma del cliente (¿vencida o revocada?).", status_code=502
            )
        return respuesta

    def _seguir_formularios(self, http: httpx.Client, r: httpx.Response, paso: str
                            ) -> httpx.Response:
        # POR CONFIRMAR CON E.FIRMA REAL: SAML/OAuth del SAT se encadena con formularios que
        # se auto-envían y un `location.href` en JS; se siguen hasta 10.
        for m in re.finditer(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r.text):
            try:
                r = http.get(urljoin(str(r.url), m.group(1)), follow_redirects=True)
            except httpx.HTTPError as e:
                raise ErrorServicioExterno(f"Portal del SAT, paso '{paso}': {e}") from e
            break
        for _ in range(10):
            accion, datos = formulario(r.text, str(r.url))
            if not accion:
                break
            r = self._post_form(http, accion, str(r.url), datos, paso)
        return r

    def _opinion(self, http: httpx.Client, solicitud: SolicitudCumplimiento, firmante: Any
                 ) -> DocumentoObtenido:
        # POR CONFIRMAR CON E.FIRMA REAL: el reporte 32-D redirige al login CIEC; se cambia
        # `id=ciec` por `id=fiel` en la acción del formulario.
        try:
            r = http.get(URL_OPINION, follow_redirects=True)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso 'abrir 32-D': {e}") from e
        if r.status_code != 200:
            raise PortalCambio("abrir 32-D", f"respondió {r.status_code}")
        accion, datos = formulario(r.text, str(r.url))
        if accion and "loginda.siat.sat.gob.mx/nidp/app/login" in accion:
            r = self._post_form(http, accion.replace("id=ciec", "id=fiel"), str(r.url), datos,
                                "cambiar a e.firma")
            r = self._login_fiel(http, r, firmante)
        r = self._seguir_formularios(http, r, "regreso del login")
        # POR CONFIRMAR CON E.FIRMA REAL: cuerpo JSON y campo `ContenidoBase64` tomados de
        # python-satcfdi; `ip` 127.0.0.1 y `canal` G como ahí.
        try:
            pdf_r = http.post(URL_OPINION_PDF, json={
                "canal": "G", "curp": "", "idCorrelacion": str(uuidlib.uuid4()),
                "ip": "127.0.0.1", "rfc": firmante.rfc, "tipoConsulta": "COMPLETA",
                "tipoReporte": "32D", "usuario": firmante.rfc, "rfcCorto": firmante.rfc,
            }, headers={"Accept": "application/json",
                        "Origin": "https://ptsc32d.clouda.sat.gob.mx",
                        "Referer": "https://ptsc32d.clouda.sat.gob.mx/"})
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso 'descargar 32-D': {e}") from e
        if pdf_r.status_code != 200:
            raise PortalCambio("descargar 32-D", f"respondió {pdf_r.status_code}")
        try:
            contenido = pdf_r.json().get("ContenidoBase64")
        except ValueError:
            contenido = None
        if not contenido:
            raise PortalCambio("descargar 32-D", "la respuesta no trae 'ContenidoBase64'")
        return DocumentoObtenido(pdf=base64.b64decode(contenido))

    def _constancia(self, http: httpx.Client, firmante: Any) -> DocumentoObtenido:
        # POR CONFIRMAR CON E.FIRMA REAL: login por `fiel_Aviso`, SessionBroker, SAML y la
        # llamada AJAX de JSF (`formReimpAcuse:j_idt50`) antes de pedir el PDF — así lo hace
        # python-satcfdi. El id `j_idt50` es generado por JSF y es lo más frágil del flujo.
        try:
            r = http.get(URL_CONSTANCIA_LOGIN, follow_redirects=True)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso 'abrir constancia': {e}") from e
        accion, datos = formulario(r.text, str(r.url))
        if not accion:
            raise PortalCambio("abrir constancia", "no hay formulario de login")
        r = self._post_form(http, accion, str(r.url), datos, "login constancia")
        self._login_fiel(http, r, firmante)
        try:
            r = http.get(URL_CONSTANCIA_BROKER, follow_redirects=True)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso 'SessionBroker': {e}") from e
        accion, datos = formulario(r.text, str(r.url))
        if accion == "https://login.siat.sat.gob.mx/nidp/saml2/sso":
            r = self._post_form(http, accion, str(r.url), datos, "SAML solicitud")
            accion, datos = formulario(r.text, str(r.url))
            r = self._post_form(http, accion or str(r.url), str(r.url), datos, "SAML respuesta")
            accion, datos = formulario(r.text, str(r.url))
        if accion == URL_CONSTANCIA_REIMP and "javax.faces.ViewState" in datos:
            self._post_form(http, accion, str(r.url), {
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": "formReimpAcuse:j_idt50",
                "javax.faces.partial.execute": "@all",
                "formReimpAcuse:j_idt50": "formReimpAcuse:j_idt50",
                "formReimpAcuse": "formReimpAcuse",
                "formReimpAcuse:tipoTramite_input": "0",
                "formReimpAcuse:tipoTramite_focus": "",
                "formReimpAcuse:fechaInicio_input:": "",
                "formReimpAcuse:fechaFin_input": "",
                "formReimpAcuse:folio": "",
                "javax.faces.ViewState": datos["javax.faces.ViewState"],
            }, "reimpresión")
        try:
            pdf_r = http.get(URL_CONSTANCIA_PDF)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"Portal del SAT, paso 'descargar constancia': {e}") from e
        if pdf_r.status_code != 200 or not pdf_r.content.lstrip().startswith(b"%PDF-"):
            raise PortalCambio("descargar constancia", "la respuesta no es un PDF")
        return DocumentoObtenido(pdf=pdf_r.content)

    def obtener(self, solicitud: SolicitudCumplimiento) -> DocumentoObtenido:
        _validar_tipo(solicitud.tipo)
        if solicitud.firmante is None:
            raise FiscalAgentError("El portal del SAT necesita la e.firma del cliente.", 422)
        firmante = solicitud.firmante()
        http = self._sesion()
        try:
            if solicitud.tipo == "opinion":
                return self._opinion(http, solicitud, firmante)
            return self._constancia(http, firmante)
        finally:
            if self._http_inyectado is None:
                http.close()


_DESCRIPCION = "Opinión de cumplimiento 32-D y constancia de situación fiscal (DP-2)"
registro.registrar("opinion_cumplimiento", "falso", OpinionFalsa, _DESCRIPCION)
registro.registrar("opinion_cumplimiento", "portal_sat", OpinionPortalSat, _DESCRIPCION)
registro.registrar("opinion_cumplimiento", "proveedor", OpinionProveedor, _DESCRIPCION)
registro.registrar("opinion_cumplimiento", "manual", OpinionManual, _DESCRIPCION)


def obtener_opinion_cumplimiento() -> OpinionCumplimiento:
    return registro.obtener("opinion_cumplimiento")
