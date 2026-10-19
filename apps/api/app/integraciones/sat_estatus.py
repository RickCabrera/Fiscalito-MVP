"""
Estatus de un CFDI ante el SAT (P1-03). `FISCALITO_SAT_ESTATUS` = falso | sat.

EL SERVICIO
-----------
`ConsultaCFDIService` es el web service PÚBLICO del SAT detrás de "Verificación de CFDI"
(no pide e.firma ni contrato). Es SOAP 1.1:

- URL: `https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc`
  (variable `FISCALITO_SAT_ESTATUS_URL` para cambiarla).
- `SOAPAction: http://tempuri.org/IConsultaCFDIService/Consulta`.
- Cuerpo: `<Consulta xmlns="http://tempuri.org/"><expresionImpresa>` con la **expresión
  impresa** del CFDI (el texto del QR de la representación impresa):
  `?re=<RFC emisor>&rr=<RFC receptor>&tt=<total>&id=<UUID>`.
- Respuesta: `ConsultaResult` con `CodigoEstatus` ("S - Comprobante obtenido
  satisfactoriamente." / "N - 60x: ..."), `Estado` (Vigente | Cancelado | No Encontrado),
  `EsCancelable` (No cancelable | Cancelable sin aceptación | Cancelable con aceptación),
  `EstatusCancelacion` (En proceso | Plazo vencido | Cancelado con aceptación | Cancelado sin
  aceptación | Solicitud rechazada | vacío) y `ValidacionEFOS` ("200"/"201" = el emisor NO
  está en la lista de EFOS; otro valor = sí).

FUENTES (verificadas 2026-10-19)
--------------------------------
- SAT, "Servicio de Consulta de CFDI" v1.4 (nov-2022), documento enlazado desde
  https://github.com/phpcfdi/sat-estado-cfdi (README: endpoint, SOAPAction y tabla de estados).
- Cliente de referencia `phpcfdi/sat-estado-cfdi` (MIT): `Contracts/Constants.php` (URL,
  SOAPAction, namespaces), `Clients/Http/Internal/SoapXml.php` (sobre SOAP) y
  `tests/_files/soap-response.xml` (respuesta grabada; la nuestra se modela igual).
- Cliente de referencia `SAT-CFDI/python-satcfdi` (MIT), `pacs/sat.py::status` — usa la
  misma URL, SOAPAction y expresión `?re=&rr=&tt=&id=` en producción.
- Formato de `tt` de CFDI 3.3/4.0: `phpcfdi/cfdi-expresiones`
  (`Standards/FormatTotal18x6`): seis decimales sin ceros a la derecha, mínimo uno.

POR CONFIRMAR CON EL SERVICIO REAL: el sandbox de desarrollo no tiene salida a sat.gob.mx,
así que la petición nunca se mandó desde aquí; se probó contra la respuesta grabada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from xml.sax.saxutils import escape

import httpx
from lxml import etree

from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno, cliente_http, env, revisar

URL_SAT = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"
NS_TEMPURI = "http://tempuri.org/"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


@dataclass(frozen=True)
class ExpresionCfdi:
    """Lo que identifica a un CFDI ante el servicio."""

    uuid: str
    rfc_emisor: str
    rfc_receptor: str
    total: Decimal

    def texto(self) -> str:
        """La expresión impresa (`?re=...&rr=...&tt=...&id=...`)."""
        return (
            f"?re={self.rfc_emisor}&rr={self.rfc_receptor}"
            f"&tt={formatear_total(self.total)}&id={self.uuid}"
        )


def formatear_total(total: Decimal) -> str:
    """`tt` de CFDI 3.3/4.0: seis decimales sin ceros sobrantes (1160.00 → "1160.0")."""
    texto = f"{Decimal(total):.6f}".rstrip("0")
    return texto + "0" if texto.endswith(".") else texto


@dataclass(frozen=True)
class EstatusCfdi:
    """La respuesta del SAT, con los textos tal cual."""

    codigo_estatus: str = ""
    estado: str = ""
    es_cancelable: str = ""
    estatus_cancelacion: str = ""
    validacion_efos: str = ""

    @property
    def encontrado(self) -> bool:
        return self.codigo_estatus.startswith("S - ")

    @property
    def resumen(self) -> str:
        """`vigente` | `cancelado` | `desconocido` (lo que va a `Comprobante.estatus_sat`)."""
        if not self.encontrado:
            return "desconocido"
        estado = self.estado.strip().lower()
        if estado == "cancelado":
            return "cancelado"
        if estado == "vigente":
            return "vigente"
        return "desconocido"

    @property
    def en_proceso_de_cancelacion(self) -> bool:
        return self.estado.strip().lower() == "vigente" and \
            self.estatus_cancelacion.strip().lower() == "en proceso"

    @property
    def emisor_en_efos(self) -> bool:
        """El SAT dice que el emisor está en la lista de EFOS (200/201 = no está)."""
        valor = self.validacion_efos.strip()
        return bool(valor) and valor not in {"200", "201"}


class SatEstatus(Protocol):
    def consultar(self, expresion: ExpresionCfdi) -> EstatusCfdi: ...


VIGENTE = EstatusCfdi(
    "S - Comprobante obtenido satisfactoriamente.", "Vigente", "Cancelable con aceptación",
    "", "200",
)
CANCELADO = EstatusCfdi(
    "S - Comprobante obtenido satisfactoriamente.", "Cancelado", "Cancelable con aceptación",
    "Cancelado con aceptación", "200",
)
NO_ENCONTRADO = EstatusCfdi("N - 602: Comprobante no encontrado.", "No Encontrado", "", "", "")


@dataclass
class SatEstatusFalso:
    """
    Sin red. Todo CFDI es vigente salvo los UUID en `cancelados` o `no_encontrados`.

    `respuestas` permite fijar la respuesta completa de un UUID (p. ej. "En proceso").
    `consultas` guarda lo que se preguntó, para que los tests lo cuenten.
    """

    cancelados: set[str] = field(default_factory=set)
    no_encontrados: set[str] = field(default_factory=set)
    respuestas: dict[str, EstatusCfdi] = field(default_factory=dict)
    consultas: list[ExpresionCfdi] = field(default_factory=list)

    def consultar(self, expresion: ExpresionCfdi) -> EstatusCfdi:
        self.consultas.append(expresion)
        uuid = expresion.uuid.upper()
        if uuid in self.respuestas:
            return self.respuestas[uuid]
        if uuid in self.cancelados:
            return CANCELADO
        if uuid in self.no_encontrados:
            return NO_ENCONTRADO
        return VIGENTE


def sobre_soap(expresion: ExpresionCfdi) -> bytes:
    """El sobre SOAP 1.1 de la consulta (igual al de phpcfdi `SoapXml::createXmlRequest`)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<s:Envelope xmlns:s="{NS_SOAP}"><s:Body>'
        f'<c:Consulta xmlns:c="{NS_TEMPURI}">'
        f"<c:expresionImpresa>{escape(expresion.texto())}</c:expresionImpresa>"
        "</c:Consulta></s:Body></s:Envelope>"
    ).encode("utf-8")


def leer_respuesta(contenido: bytes) -> EstatusCfdi:
    """Extrae los cinco campos de `ConsultaResult`. 502 si la respuesta no es la esperada."""
    try:
        raiz = etree.fromstring(contenido, parser=etree.XMLParser(resolve_entities=False))
    except etree.XMLSyntaxError as e:
        raise ErrorServicioExterno(f"El SAT respondió algo que no es XML: {e}") from e
    resultado = raiz.find(f".//{{{NS_TEMPURI}}}ConsultaResult")
    if resultado is None:
        falla = raiz.find(f".//{{{NS_SOAP}}}Fault")
        detalle = "".join(falla.itertext()).strip()[:200] if falla is not None else ""
        raise ErrorServicioExterno(
            "La respuesta del SAT no trae ConsultaResult"
            + (f" (Fault: {detalle})." if detalle else ".")
        )
    valores = {etree.QName(h).localname: (h.text or "").strip() for h in resultado
               if isinstance(h.tag, str)}
    return EstatusCfdi(
        codigo_estatus=valores.get("CodigoEstatus", ""),
        estado=valores.get("Estado", ""),
        es_cancelable=valores.get("EsCancelable", ""),
        estatus_cancelacion=valores.get("EstatusCancelacion", ""),
        validacion_efos=valores.get("ValidacionEFOS", ""),
    )


class SatEstatusSoap:
    """El servicio real del SAT."""

    def __init__(self, http: httpx.Client | None = None, url: str | None = None) -> None:
        self.url = url or env("FISCALITO_SAT_ESTATUS_URL", URL_SAT)
        self.http = cliente_http(http)

    def consultar(self, expresion: ExpresionCfdi) -> EstatusCfdi:
        try:
            r = self.http.post(
                self.url,
                content=sobre_soap(expresion),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": SOAP_ACTION},
            )
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo consultar el SAT: {e}") from e
        return leer_respuesta(revisar(r, "SAT (estatus de CFDI)").content)


_DESCRIPCION = "Estatus de CFDI (servicio público ConsultaCFDIService del SAT)"
registro.registrar("sat_estatus", "falso", SatEstatusFalso, _DESCRIPCION)
registro.registrar("sat_estatus", "sat", SatEstatusSoap, _DESCRIPCION)


def obtener_sat_estatus() -> SatEstatus:
    return registro.obtener("sat_estatus")
