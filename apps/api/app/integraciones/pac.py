"""
Proveedor Autorizado de Certificación (PAC): timbrado, cancelación y estatus (P3-04).

`FISCALITO_PAC` = falso | finkok | sw_sapien | facturama. Lo usan el CFDI de retenciones
(P3-04) y lo reusarán nómina (P4) y facturación: el contrato es GENÉRICO.

CONTRATO
--------
- `timbrar(xml_sellado, tipo="cfdi"|"retenciones") -> Timbre(xml_timbrado, uuid, fecha)`.
  Recibe el XML YA SELLADO con el CSD del emisor (Fiscalito sella; el PAC sólo certifica).
- `cancelar(uuid, rfc, motivo, folio_sustitucion=None, *, tipo, firmante) -> AcuseCancelacion`.
  Motivos del SAT: 01 (con relación, exige folio de sustitución), 02, 03, 04.
- `consultar_estatus(uuid, rfc, *, tipo) -> EstatusPac`.

IMPLEMENTACIONES
----------------
- `falso`: sin red. Inserta un `TimbreFiscalDigital` 1.1 SINTÉTICO que valida contra su XSD,
  con UUID aleatorio, `NoCertificadoSAT` en ceros y la `Leyenda` "NO FISCAL". **No tiene
  validez ante el SAT**: es para desarrollo y pruebas.
- `finkok`: SOAP (stamp.wsdl / cancel.wsdl). Forma de los mensajes tomada de la
  documentación pública de Finkok (wiki.finkok.com) y de la implementación abierta de
  `satcfdi` 26.10.1 (`satcfdi/pacs/finkok.py`, MIT).
- `sw_sapien`: REST (services.sw.com.mx). Rutas tomadas de developers.sw.com.mx y de
  `satcfdi/pacs/swsapien.py`.
- `facturama`: REST (api.facturama.mx). Facturama NO timbra XML presellado: sella con el CSD
  que el despacho subió a su cuenta Multiemisor, a partir de un JSON. El adaptador traduce el
  XML a ese JSON (sólo retenciones 2.0 por ahora) — ver `PacFacturama`.

Lo marcado `# POR CONFIRMAR CON CUENTA DE PRUEBAS` no se pudo verificar sin una cuenta de
pruebas del PAC: las pruebas usan respuestas grabadas construidas desde la documentación
pública (`tests/fixtures/pac/`), no respuestas reales capturadas.
"""

from __future__ import annotations

import base64
import hashlib
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, NamedTuple, Protocol
from zoneinfo import ZoneInfo

import httpx
from lxml import etree

from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno, cliente_http, env, revisar

TipoDocumento = Literal["cfdi", "retenciones"]
MOTIVOS = {"01", "02", "03", "04"}
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"
XSD_TFD = "http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
ZONA = ZoneInfo("America/Mexico_City")
LEYENDA_FALSA = "NO FISCAL - timbre sintetico de pruebas de Fiscalito sin validez ante el SAT"
RFC_PAC_FALSO = "FAL010101AA0"


class Timbre(NamedTuple):
    """Lo que devuelve un timbrado: el XML con el TFD, su UUID y la fecha de timbrado."""

    xml_timbrado: bytes
    uuid: str
    fecha: datetime


@dataclass(frozen=True)
class AcuseCancelacion:
    """Respuesta de una cancelación. `estatus`: cancelado | en_proceso | rechazado."""

    uuid: str
    estatus: str
    codigo: str = ""
    mensaje: str = ""
    acuse_xml: bytes | None = None


@dataclass(frozen=True)
class EstatusPac:
    """Estado de un comprobante: vigente | cancelado | en_proceso | no_encontrado."""

    uuid: str
    estado: str
    detalle: dict[str, Any] = field(default_factory=dict)


class ErrorTimbrado(ErrorServicioExterno):
    """El PAC rechazó el comprobante (422: el problema es el XML, no la red)."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.status_code = 422


class Pac(Protocol):
    nombre: str

    def timbrar(self, xml_sellado: bytes, tipo: TipoDocumento = "cfdi") -> Timbre: ...

    def cancelar(
        self, uuid: str, rfc: str, motivo: str, folio_sustitucion: str | None = None, *,
        tipo: TipoDocumento = "cfdi", firmante: Any = None,
    ) -> AcuseCancelacion: ...

    def consultar_estatus(
        self, uuid: str, rfc: str, *, tipo: TipoDocumento = "cfdi"
    ) -> EstatusPac: ...


# ── utilidades comunes ──


def validar_motivo(motivo: str, folio_sustitucion: str | None) -> None:
    """Motivos del SAT (Anexo 20, cancelación 2022): el 01 exige el UUID que sustituye."""
    if motivo not in MOTIVOS:
        raise ValueError(f"Motivo de cancelación inválido: {motivo!r} (01, 02, 03 o 04).")
    if motivo == "01" and not folio_sustitucion:
        raise ValueError("El motivo 01 exige el UUID del comprobante que sustituye.")


def leer_timbre(xml_timbrado: bytes) -> tuple[str, datetime]:
    """UUID y FechaTimbrado del TFD de un XML timbrado (cualquier tipo de documento)."""
    raiz = etree.fromstring(xml_timbrado, etree.XMLParser(resolve_entities=False, no_network=True))
    tfd = raiz.find(f".//{{{NS_TFD}}}TimbreFiscalDigital")
    if tfd is None or not tfd.get("UUID"):
        raise ErrorServicioExterno("El PAC devolvió un XML sin TimbreFiscalDigital.")
    return tfd.get("UUID", "").upper(), datetime.fromisoformat(tfd.get("FechaTimbrado", ""))


def insertar_complemento(xml_sellado: bytes, nodo: etree._Element) -> bytes:
    """Mete `nodo` en el `Complemento` del documento (lo crea antes de `Addenda` si falta)."""
    raiz = etree.fromstring(xml_sellado, etree.XMLParser(resolve_entities=False, no_network=True))
    ns = etree.QName(raiz).namespace
    complemento = raiz.find(f"{{{ns}}}Complemento")
    if complemento is None:
        complemento = etree.Element(f"{{{ns}}}Complemento")
        addenda = raiz.find(f"{{{ns}}}Addenda")
        if addenda is not None:
            addenda.addprevious(complemento)
        else:
            raiz.append(complemento)
    complemento.append(nodo)
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")


def _local(nodo: Any) -> str:
    return etree.QName(nodo).localname if isinstance(nodo.tag, str) else ""


def _buscar(raiz: Any, nombre: str) -> Any:
    """Primer descendiente con ese nombre local (los PAC cambian prefijos entre versiones)."""
    for n in raiz.iter():
        if _local(n) == nombre:
            return n
    return None


def _texto(raiz: Any, nombre: str) -> str:
    n = _buscar(raiz, nombre)
    return (n.text or "").strip() if n is not None else ""


# ── falso ──


@dataclass
class PacFalso:
    """
    Sin red. Timbre SINTÉTICO, marcado NO FISCAL; recuerda lo que timbró y canceló.

    `SelloSAT` es un SHA-256 en base64 de la cadena del TFD: tiene la forma, no la firma.
    """

    nombre: str = "falso"
    timbrados: dict[str, bytes] = field(default_factory=dict)
    cancelados: dict[str, str] = field(default_factory=dict)

    def timbrar(self, xml_sellado: bytes, tipo: TipoDocumento = "cfdi") -> Timbre:
        raiz = etree.fromstring(xml_sellado)
        sello = raiz.get("Sello") or ""
        if not sello:
            raise ErrorTimbrado("El comprobante no está sellado (falta el atributo Sello).")
        uuid = str(uuid_mod.uuid4()).upper()
        fecha = datetime.now(ZONA).replace(tzinfo=None, microsecond=0)
        tfd = etree.Element(f"{{{NS_TFD}}}TimbreFiscalDigital", nsmap={
            "tfd": NS_TFD, "xsi": NS_XSI})
        tfd.set(f"{{{NS_XSI}}}schemaLocation", f"{NS_TFD} {XSD_TFD}")
        cadena = f"||1.1|{uuid}|{fecha.isoformat()}|{RFC_PAC_FALSO}|{LEYENDA_FALSA}|{sello}|" \
                 f"{'0' * 20}||"
        for k, v in (
            ("Version", "1.1"), ("UUID", uuid), ("FechaTimbrado", fecha.isoformat()),
            ("RfcProvCertif", RFC_PAC_FALSO), ("Leyenda", LEYENDA_FALSA), ("SelloCFD", sello),
            ("NoCertificadoSAT", "0" * 20),
            ("SelloSAT", base64.b64encode(hashlib.sha256(cadena.encode()).digest()).decode()),
        ):
            tfd.set(k, v)
        xml = insertar_complemento(xml_sellado, tfd)
        self.timbrados[uuid] = xml
        return Timbre(xml, uuid, fecha)

    def cancelar(
        self, uuid: str, rfc: str, motivo: str, folio_sustitucion: str | None = None, *,
        tipo: TipoDocumento = "cfdi", firmante: Any = None,
    ) -> AcuseCancelacion:
        validar_motivo(motivo, folio_sustitucion)
        uuid = uuid.upper()
        self.cancelados[uuid] = motivo
        acuse = (f'<Acuse Fecha="{datetime.now(ZONA).replace(tzinfo=None, microsecond=0)}'
                 f'" RfcEmisor="{rfc}"><Folios><UUID>{uuid}</UUID><EstatusUUID>201'
                 f'</EstatusUUID></Folios><Leyenda>{LEYENDA_FALSA}</Leyenda></Acuse>')
        return AcuseCancelacion(uuid, "cancelado", "201", "Cancelación sintética (NO FISCAL).",
                                acuse.encode())

    def consultar_estatus(
        self, uuid: str, rfc: str, *, tipo: TipoDocumento = "cfdi"
    ) -> EstatusPac:
        u = uuid.upper()
        if u in self.cancelados:
            return EstatusPac(u, "cancelado", {"motivo": self.cancelados[u]})
        if u in self.timbrados:
            return EstatusPac(u, "vigente")
        return EstatusPac(u, "no_encontrado")


# ── Finkok (SOAP) ──

NS_SOAPENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS_FK_STAMP = "http://facturacion.finkok.com/stamp"
NS_FK_CANCEL = "http://facturacion.finkok.com/cancel"
# POR CONFIRMAR CON CUENTA DE PRUEBAS: servicio y namespace de retenciones de Finkok
# (wiki.finkok.com documenta `retentions.wsdl` con las mismas operaciones `stamp`/`cancel`).
NS_FK_RET = "http://facturacion.finkok.com/retentions"
NS_CANCELACION = "http://cancelacfd.sat.gob.mx"
# POR CONFIRMAR CON CUENTA DE PRUEBAS: namespace del documento de cancelación de retenciones.
NS_CANCELACION_RET = "http://www.sat.gob.mx/esquemas/retencionpago/1"
TIMBRADO_OK = "Comprobante timbrado satisfactoriamente"


class PacFinkok:
    """Finkok por SOAP. Variables: FISCALITO_FINKOK_USUARIO, _PASSWORD, _URL."""

    nombre = "finkok"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = cliente_http(http)

    @property
    def base(self) -> str:
        return env("FISCALITO_FINKOK_URL", "https://demo-facturacion.finkok.com").rstrip("/")

    def _sobre(self, ns: str, operacion: str, campos: list[tuple[str, str]]) -> bytes:
        env_ = etree.Element(f"{{{NS_SOAPENV}}}Envelope", nsmap={"soapenv": NS_SOAPENV, "fk": ns})
        etree.SubElement(env_, f"{{{NS_SOAPENV}}}Header")
        cuerpo = etree.SubElement(env_, f"{{{NS_SOAPENV}}}Body")
        op = etree.SubElement(cuerpo, f"{{{ns}}}{operacion}")
        for nombre, valor in campos + [
            ("username", env("FISCALITO_FINKOK_USUARIO")),
            ("password", env("FISCALITO_FINKOK_PASSWORD")),
        ]:
            etree.SubElement(op, f"{{{ns}}}{nombre}").text = valor
        return etree.tostring(env_, xml_declaration=True, encoding="UTF-8")

    def _post(self, servicio: str, cuerpo: bytes) -> Any:
        url = f"{self.base}/servicios/soap/{servicio}.wsdl"
        try:
            r = self.http.post(url, content=cuerpo,
                               headers={"Content-Type": "text/xml; charset=utf-8"})
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo contactar a Finkok: {e}") from e
        revisar(r, "Finkok")
        return etree.fromstring(r.content, etree.XMLParser(resolve_entities=False,
                                                           no_network=True))

    def timbrar(self, xml_sellado: bytes, tipo: TipoDocumento = "cfdi") -> Timbre:
        ns, servicio = (NS_FK_RET, "retentions") if tipo == "retenciones" else (
            NS_FK_STAMP, "stamp")
        raiz = self._post(servicio, self._sobre(
            ns, "stamp", [("xml", base64.b64encode(xml_sellado).decode("ascii"))]))
        return leer_respuesta_finkok_timbrado(raiz)

    def cancelar(
        self, uuid: str, rfc: str, motivo: str, folio_sustitucion: str | None = None, *,
        tipo: TipoDocumento = "cfdi", firmante: Any = None,
    ) -> AcuseCancelacion:
        validar_motivo(motivo, folio_sustitucion)
        if firmante is None:
            raise ValueError("Finkok cancela con la solicitud firmada con el CSD del emisor.")
        doc = documento_cancelacion(firmante, rfc, uuid, motivo, folio_sustitucion, tipo)
        ns, servicio = (NS_FK_RET, "retentions") if tipo == "retenciones" else (
            NS_FK_CANCEL, "cancel")
        raiz = self._post(servicio, self._sobre(
            ns, "cancel_signature", [("xml", base64.b64encode(doc).decode("ascii"))]))
        return leer_respuesta_finkok_cancelacion(raiz, uuid)

    def consultar_estatus(
        self, uuid: str, rfc: str, *, tipo: TipoDocumento = "cfdi"
    ) -> EstatusPac:
        raiz = self._post("cancel", self._sobre(
            NS_FK_CANCEL, "get_sat_status",
            [("taxpayer_id", rfc), ("rtaxpayer_id", ""), ("uuid", uuid), ("total", "")]))
        return EstatusPac(uuid.upper(), _estado_sat(_texto(raiz, "Estado")),
                          {"codigo": _texto(raiz, "CodigoEstatus"),
                           "es_cancelable": _texto(raiz, "EsCancelable"),
                           "estatus_cancelacion": _texto(raiz, "EstatusCancelacion")})


def _estado_sat(texto: str) -> str:
    t = texto.lower()
    if "cancel" in t:
        return "cancelado"
    if "vigente" in t:
        return "vigente"
    if "proceso" in t:
        return "en_proceso"
    return "no_encontrado"


def leer_respuesta_finkok_timbrado(raiz: Any) -> Timbre:
    """`stampResult`: xml, UUID, Fecha, CodEstatus e Incidencias (CodigoError + Mensaje)."""
    estatus = _texto(raiz, "CodEstatus")
    incidencias = [
        f"{_texto(i, 'CodigoError')} - {_texto(i, 'MensajeIncidencia')}".strip(" -")
        for i in raiz.iter() if _local(i) == "Incidencia"
    ]
    xml = _texto(raiz, "xml")
    if not xml or (incidencias and estatus != TIMBRADO_OK):
        raise ErrorTimbrado("Finkok no timbró: " + ("; ".join(incidencias) or estatus or
                                                    "respuesta sin XML"))
    xml_bytes = xml.encode("utf-8")
    uuid, fecha = leer_timbre(xml_bytes)
    return Timbre(xml_bytes, uuid, fecha)


def leer_respuesta_finkok_cancelacion(raiz: Any, uuid: str) -> AcuseCancelacion:
    """`cancelResult`: Folios/Folio{UUID, EstatusUUID, EstatusCancelacion}, Acuse, CodEstatus."""
    error = _texto(raiz, "CodEstatus") or _texto(raiz, "error")
    estatus_uuid = _texto(raiz, "EstatusUUID")
    acuse = _texto(raiz, "Acuse")
    if not estatus_uuid:
        raise ErrorServicioExterno(f"Finkok no canceló: {error or 'respuesta sin folio'}")
    cancelacion = _texto(raiz, "EstatusCancelacion").lower()
    # 201 = solicitud recibida; 202 = ya estaba cancelado (catálogo de acuses del SAT).
    if estatus_uuid in ("201", "202"):
        estado = "en_proceso" if "proceso" in cancelacion else "cancelado"
    else:
        estado = "rechazado"
    return AcuseCancelacion(uuid.upper(), estado, estatus_uuid, error or cancelacion,
                            acuse.encode("utf-8") if acuse else None)


def documento_cancelacion(
    firmante: Any, rfc: str, uuid: str, motivo: str, folio: str | None, tipo: TipoDocumento
) -> bytes:
    """
    Solicitud de cancelación firmada (XMLDSig enveloped) para `cancel_signature`.

    El texto se arma ya canónico y se firma con `sat_soap.firma` (exc-c14n, rsa-sha1), igual
    que los mensajes de la descarga masiva. # POR CONFIRMAR CON CUENTA DE PRUEBAS: que el SAT
    acepte exc-c14n/rsa-sha1 en la cancelación por PAC (la documentación muestra c14n).
    """
    from app.integraciones.sat_soap import _esc, firma

    ns = NS_CANCELACION_RET if tipo == "retenciones" else NS_CANCELACION
    fecha = datetime.now(ZONA).replace(tzinfo=None, microsecond=0).isoformat()
    folio_txt = f' FolioSustitucion="{_esc(folio)}"' if folio else ""
    folios = (f'<Folios><Folio Motivo="{motivo}"{folio_txt} UUID="{_esc(uuid.upper())}">'
              f"</Folio></Folios>")
    canonico = f'<Cancelacion xmlns="{ns}" Fecha="{fecha}" RfcEmisor="{_esc(rfc)}">{folios}' \
               "</Cancelacion>"
    signature = firma(firmante, canonico)
    return canonico.replace("</Cancelacion>", f"{signature}</Cancelacion>").encode("utf-8")


# ── SW Sapien (REST) ──


class PacSwSapien:
    """SW Sapien. Variables: FISCALITO_SW_TOKEN (o _USUARIO + _PASSWORD), FISCALITO_SW_URL."""

    nombre = "sw_sapien"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = cliente_http(http)
        self._token: str | None = None

    @property
    def base(self) -> str:
        return env("FISCALITO_SW_URL", "https://services.test.sw.com.mx").rstrip("/")

    def _autorizacion(self) -> str:
        token = env("FISCALITO_SW_TOKEN", "")
        if token:
            return f"Bearer {token}"
        if self._token is None:
            r = self.http.post(f"{self.base}/security/authenticate", headers={
                "user": env("FISCALITO_SW_USUARIO"), "password": env("FISCALITO_SW_PASSWORD")})
            revisar(r, "SW Sapien (autenticación)")
            self._token = str(r.json()["data"]["token"])
        return f"Bearer {self._token}"

    def _post(self, ruta: str, **kwargs: Any) -> dict[str, Any]:
        try:
            r = self.http.post(f"{self.base}/{ruta}",
                               headers={"Authorization": self._autorizacion()}, **kwargs)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo contactar a SW Sapien: {e}") from e
        datos = _json(r)
        if r.status_code >= 400 or datos.get("status") != "success":
            mensaje = f"{datos.get('message', '')} {datos.get('messageDetail', '')}".strip()
            if 400 <= r.status_code < 500:
                raise ErrorTimbrado(f"SW Sapien rechazó el comprobante: {mensaje or r.text[:200]}")
            raise ErrorServicioExterno(f"SW Sapien respondió {r.status_code}: {mensaje}")
        return datos

    def timbrar(self, xml_sellado: bytes, tipo: TipoDocumento = "cfdi") -> Timbre:
        # v4 devuelve el CFDI completo en `data.cfdi`. POR CONFIRMAR CON CUENTA DE PRUEBAS: la
        # ruta de retenciones (`retencion/stamp/v3`, documentada como "Timbrado Retenciones").
        ruta = "retencion/stamp/v3" if tipo == "retenciones" else "v4/cfdi33/stamp/v4"
        datos = self._post(ruta, files={"xml": ("xml", xml_sellado, "text/xml")})
        return leer_respuesta_sw_timbrado(datos)

    def cancelar(
        self, uuid: str, rfc: str, motivo: str, folio_sustitucion: str | None = None, *,
        tipo: TipoDocumento = "cfdi", firmante: Any = None,
    ) -> AcuseCancelacion:
        validar_motivo(motivo, folio_sustitucion)
        # Cancelación por UUID con el CSD que el despacho cargó en su cuenta de SW.
        # POR CONFIRMAR CON CUENTA DE PRUEBAS: ruta de cancelación de retenciones.
        prefijo = "retencion/cancel" if tipo == "retenciones" else "cfdi33/cancel"
        ruta = f"{prefijo}/{rfc}/{uuid.upper()}/{motivo}"
        if folio_sustitucion:
            ruta += f"/{folio_sustitucion}"
        return leer_respuesta_sw_cancelacion(self._post(ruta), uuid)

    def consultar_estatus(
        self, uuid: str, rfc: str, *, tipo: TipoDocumento = "cfdi"
    ) -> EstatusPac:
        # POR CONFIRMAR CON CUENTA DE PRUEBAS: SW no documenta una consulta de estatus propia;
        # se usa la de relaciones/pendientes. El estatus SAT de la bóveda va por `sat_estatus`.
        datos = self._post(f"relations/{rfc}/{uuid.upper()}")
        codigo = str(datos.get("data", {}).get("statusCode", ""))
        return EstatusPac(uuid.upper(), "vigente" if codigo else "no_encontrado", datos)


def _json(r: httpx.Response) -> dict[str, Any]:
    try:
        datos = r.json()
    except ValueError:
        return {"status": "error", "message": r.text[:300]}
    return datos if isinstance(datos, dict) else {"status": "error", "message": str(datos)}


def leer_respuesta_sw_timbrado(datos: dict[str, Any]) -> Timbre:
    d = datos.get("data") or {}
    xml = str(d.get("cfdi") or d.get("retencion") or "")
    if not xml:
        raise ErrorServicioExterno("SW Sapien respondió sin el XML timbrado.")
    xml_bytes = xml.encode("utf-8")
    uuid, fecha = leer_timbre(xml_bytes)
    return Timbre(xml_bytes, uuid, fecha)


def leer_respuesta_sw_cancelacion(datos: dict[str, Any], uuid: str) -> AcuseCancelacion:
    d = datos.get("data") or {}
    folios = d.get("uuid") or {}
    codigo = str(folios.get(uuid.upper()) or folios.get(uuid.lower()) or "")
    estado = "cancelado" if codigo in ("201", "202") else "rechazado"
    acuse = d.get("acuse")
    return AcuseCancelacion(uuid.upper(), estado, codigo, "",
                            str(acuse).encode("utf-8") if acuse else None)


# ── Facturama (REST, JSON) ──


class PacFacturama:
    """
    Facturama Multiemisor. Variables: FISCALITO_FACTURAMA_USUARIO, _PASSWORD, _URL.

    Facturama no recibe XML sellado: sella con el CSD cargado en la cuenta (`api-lite/csds`).
    `timbrar` traduce el XML de retenciones 2.0 al JSON de `POST /2/retenciones` (campos de
    facturama.mx/api/cfdi-retenciones) y descarga el XML timbrado. El sello de Fiscalito se
    descarta: el que vale es el de Facturama. Para CFDI de ingreso/nómina hará falta el mapeo
    completo (ver `satcfdi/pacs/facturama.py`): hoy responde 501.
    """

    nombre = "facturama"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = cliente_http(http)

    @property
    def base(self) -> str:
        return env("FISCALITO_FACTURAMA_URL", "https://apisandbox.facturama.mx").rstrip("/")

    def _pedir(self, metodo: str, ruta: str, **kwargs: Any) -> Any:
        try:
            r = self.http.request(metodo, f"{self.base}/{ruta}", auth=(
                env("FISCALITO_FACTURAMA_USUARIO"), env("FISCALITO_FACTURAMA_PASSWORD")),
                **kwargs)
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo contactar a Facturama: {e}") from e
        if r.status_code == 400:
            raise ErrorTimbrado(f"Facturama rechazó el comprobante: {r.text[:300]}")
        revisar(r, "Facturama")
        return r.json() if r.content else {}

    def timbrar(self, xml_sellado: bytes, tipo: TipoDocumento = "cfdi") -> Timbre:
        if tipo != "retenciones":
            from app.exceptions import FiscalAgentError

            raise FiscalAgentError(
                "Facturama sólo está conectado para CFDI de retenciones; usa otro PAC.", 501)
        creado = self._pedir("POST", "2/retenciones", json=retenciones_a_json_facturama(
            xml_sellado))
        ident = str(creado.get("Id") or "")
        # POR CONFIRMAR CON CUENTA DE PRUEBAS: descarga del XML de una retención por Id.
        archivo = self._pedir("GET", f"api/Retenciones/xml/{ident}")
        xml = base64.b64decode(str(archivo.get("Content") or ""))
        uuid, fecha = leer_timbre(xml)
        return Timbre(xml, uuid, fecha)

    def cancelar(
        self, uuid: str, rfc: str, motivo: str, folio_sustitucion: str | None = None, *,
        tipo: TipoDocumento = "cfdi", firmante: Any = None,
    ) -> AcuseCancelacion:
        validar_motivo(motivo, folio_sustitucion)
        ident = self._id_de(uuid, tipo)
        params = {"motive": motivo}
        if folio_sustitucion:
            params["uuidReplacement"] = folio_sustitucion
        # POR CONFIRMAR CON CUENTA DE PRUEBAS: ruta de cancelación de retenciones.
        ruta = f"api/Retenciones/{ident}" if tipo == "retenciones" else f"api-lite/cfdis/{ident}"
        datos = self._pedir("DELETE", ruta, params=params)
        estado = str(datos.get("Status") or "").lower()
        acuse = datos.get("AcuseXmlBase64")
        return AcuseCancelacion(
            uuid.upper(),
            "cancelado" if estado in ("canceled", "cancelado") else (
                "en_proceso" if "pend" in estado or "proceso" in estado else "rechazado"),
            estado, str(datos.get("Message") or ""),
            base64.b64decode(acuse) if acuse else None)

    def consultar_estatus(
        self, uuid: str, rfc: str, *, tipo: TipoDocumento = "cfdi"
    ) -> EstatusPac:
        ident = self._id_de(uuid, tipo)
        ruta = f"api/Retenciones/{ident}" if tipo == "retenciones" else f"api-lite/cfdis/{ident}"
        datos = self._pedir("GET", ruta)
        cancelado = bool(datos.get("IsCanceled")) or str(datos.get("Status", "")).lower() in (
            "canceled", "cancelado")
        return EstatusPac(uuid.upper(), "cancelado" if cancelado else "vigente", datos)

    def _id_de(self, uuid: str, tipo: TipoDocumento) -> str:
        ruta = "api/Retenciones" if tipo == "retenciones" else "api-lite/cfdis"
        lista = self._pedir("GET", ruta, params={"keyword": uuid})
        for item in lista if isinstance(lista, list) else []:
            if str(item.get("Uuid") or item.get("UUID") or "").upper() == uuid.upper():
                return str(item["Id"])
        raise ErrorServicioExterno(f"Facturama no encontró el comprobante {uuid}.")


def retenciones_a_json_facturama(xml: bytes) -> dict[str, Any]:
    """Retenciones 2.0 (XML) → JSON de Facturama (campos de facturama.mx/api/cfdi-retenciones)."""
    raiz = etree.fromstring(xml)
    ns = {"r": etree.QName(raiz).namespace}
    emisor = raiz.find("r:Emisor", ns)
    nacional = raiz.find("r:Receptor/r:Nacional", ns)
    extranjero = raiz.find("r:Receptor/r:Extranjero", ns)
    periodo = raiz.find("r:Periodo", ns)
    totales = raiz.find("r:Totales", ns)
    assert emisor is not None and periodo is not None and totales is not None
    receptor: dict[str, Any] = {"Nationality": "Nacional" if nacional is not None else "Extranjero"}
    if nacional is not None:
        receptor.update({"RFCRecep": nacional.get("RfcR"), "NomDenRazSocR":
                         nacional.get("NomDenRazSocR"),
                         "DomicilioFiscalR": nacional.get("DomicilioFiscalR")})
    elif extranjero is not None:
        receptor.update({"NumRegIdTribR": extranjero.get("NumRegIdTribR"),
                         "NomDenRazSocR": extranjero.get("NomDenRazSocR")})
    return {
        "FechaExp": raiz.get("FechaExp"), "CveRetenc": raiz.get("CveRetenc"),
        "DescRetenc": raiz.get("DescRetenc"), "LugarExpRetenc": raiz.get("LugarExpRetenc"),
        "FolioInt": raiz.get("FolioInt"),
        "Emisor": {"RFCEmisor": emisor.get("RfcE"), "NomDenRazSocE": emisor.get("NomDenRazSocE"),
                   "RegimenFiscalE": emisor.get("RegimenFiscalE")},
        "Receptor": receptor,
        "Periodo": {"MesIni": int(periodo.get("MesIni", "1")),
                    "MesFin": int(periodo.get("MesFin", "1")),
                    "Ejercicio": int(periodo.get("Ejercicio", "2026"))},
        "Totales": {
            "montoTotOperacion": float(totales.get("MontoTotOperacion", "0")),
            "montoTotGrav": float(totales.get("MontoTotGrav", "0")),
            "montoTotExent": float(totales.get("MontoTotExent", "0")),
            "montoTotRet": float(totales.get("MontoTotRet", "0")),
            "ImpRetenidos": [
                {"BaseRet": float(i.get("BaseRet", "0")), "Impuesto": i.get("ImpuestoRet"),
                 "montoRet": float(i.get("MontoRet", "0")), "TipoPagoRet": i.get("TipoPagoRet")}
                for i in totales.findall("r:ImpRetenidos", ns)
            ],
        },
    }


_DESCRIPCION = "PAC: timbrado y cancelación de CFDI y CFDI de retenciones"
registro.registrar("pac", "falso", PacFalso, _DESCRIPCION)
registro.registrar("pac", "finkok", PacFinkok, _DESCRIPCION)
registro.registrar("pac", "sw_sapien", PacSwSapien, _DESCRIPCION)
registro.registrar("pac", "facturama", PacFacturama, _DESCRIPCION)


def obtener_pac() -> Pac:
    return registro.obtener("pac")
