"""
Armado y sellado del CFDI de Retenciones e información de pagos 2.0 (P3-04).

Estructura y orden de nodos: `retencionpagov2.xsd` (Emisor, Receptor, Periodo, Totales con
`ImpRetenidos`, Complemento). Catálogos: `catRetenciones.xsd` —c_CveRetenc (01 Servicios
profesionales, 05 Arrendamiento, 25 Otro tipo de retenciones...), c_TipoPagoRet (01 Pago
definitivo IVA, 02 Pago definitivo IEPS, 03 Pago definitivo ISR, 04 Pago provisional ISR)—
y `catCFDI.xsd` (c_Impuesto 001 ISR, 002 IVA). Descripciones de los catálogos tomadas de la
base de catálogos de `satcfdi` 26.10.1.

Sello: SHA256withRSA (PKCS#1 v1.5) sobre la cadena original del XSLT oficial, con el CSD del
emisor (`app.credenciales.servicio.obtener_firmante(db, cliente, "csd")`), igual que el CFDI
4.0 (Anexo 20). El generador NO calcula impuestos: recibe los importes ya sumados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from lxml import etree

from app.retenciones_cfdi import esquemas

NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
CENTAVO = Decimal("0.01")

CVE_RETENC = {
    "01": "Servicios profesionales", "02": "Regalías por derechos de autor",
    "03": "Autotransporte terrestre de carga", "04": "Servicios prestados por comisionistas",
    "05": "Arrendamiento", "14": "Dividendos o utilidades distribuidas", "16": "Intereses",
    "18": "Pagos realizados a favor de residentes en el extranjero",
    "25": "Otro tipo de retenciones", "26": "Servicios mediante Plataformas Tecnológicas",
}
TIPO_PAGO_RET = {"01": "Pago definitivo IVA", "02": "Pago definitivo IEPS",
                 "03": "Pago definitivo ISR", "04": "Pago provisional ISR"}


class FirmanteCsd(Protocol):
    numero_certificado: str

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str: ...

    @property
    def certificado_base64(self) -> str: ...


@dataclass(frozen=True)
class ImpuestoRetenido:
    impuesto: str  # 001 ISR | 002 IVA
    base: Decimal
    monto: Decimal
    tipo_pago: str  # c_TipoPagoRet


@dataclass
class DatosRetencion:
    """Todo lo que lleva el comprobante, ya calculado."""

    rfc_emisor: str
    nombre_emisor: str
    regimen_emisor: str
    lugar_expedicion: str
    rfc_receptor: str
    nombre_receptor: str
    domicilio_receptor: str
    ejercicio: int
    mes_ini: int
    mes_fin: int
    cve_retenc: str
    monto_operacion: Decimal
    monto_gravado: Decimal
    monto_exento: Decimal
    impuestos: list[ImpuestoRetenido] = field(default_factory=list)
    desc_retenc: str = ""
    folio_interno: str = ""
    curp_receptor: str = ""
    fecha_expedicion: datetime | None = None
    uuid_relacionado: str = ""

    @property
    def monto_retenido(self) -> Decimal:
        return sum((i.monto for i in self.impuestos), Decimal("0"))


def importe(v: Decimal) -> str:
    """t_ImporteMXN: dos decimales, redondeo half-up."""
    return str(Decimal(v).quantize(CENTAVO, rounding=ROUND_HALF_UP))


def armar(d: DatosRetencion) -> etree._Element:
    """El XML SIN sellar (Sello, NoCertificado y Certificado vacíos)."""
    ns = esquemas.NS
    r = etree.Element(f"{{{ns}}}Retenciones", nsmap={"retenciones": ns, "xsi": NS_XSI})
    r.set(f"{{{NS_XSI}}}schemaLocation", f"{ns} {esquemas.XSD_URL}")
    fecha = (d.fecha_expedicion or datetime.now()).replace(microsecond=0, tzinfo=None)
    atributos: list[tuple[str, str]] = [("Version", "2.0")]
    if d.folio_interno:
        atributos.append(("FolioInt", d.folio_interno))
    atributos += [
        ("Sello", ""), ("NoCertificado", ""), ("Certificado", ""),
        ("FechaExp", fecha.isoformat()), ("LugarExpRetenc", d.lugar_expedicion),
        ("CveRetenc", d.cve_retenc),
    ]
    if d.desc_retenc or d.cve_retenc == "25":
        atributos.append(("DescRetenc", (d.desc_retenc or "Otro tipo de retenciones")[:100]))
    for k, v in atributos:
        r.set(k, v)
    if d.uuid_relacionado:
        etree.SubElement(r, f"{{{ns}}}CfdiRetenRelacionados", TipoRelacion="04",
                         UUID=d.uuid_relacionado.upper())
    etree.SubElement(r, f"{{{ns}}}Emisor", RfcE=d.rfc_emisor, NomDenRazSocE=d.nombre_emisor,
                     RegimenFiscalE=d.regimen_emisor)
    receptor = etree.SubElement(r, f"{{{ns}}}Receptor", NacionalidadR="Nacional")
    nacional = etree.SubElement(receptor, f"{{{ns}}}Nacional", RfcR=d.rfc_receptor,
                                NomDenRazSocR=d.nombre_receptor)
    if d.curp_receptor:
        nacional.set("CurpR", d.curp_receptor)
    nacional.set("DomicilioFiscalR", d.domicilio_receptor)
    etree.SubElement(r, f"{{{ns}}}Periodo", MesIni=f"{d.mes_ini:02d}", MesFin=f"{d.mes_fin:02d}",
                     Ejercicio=str(d.ejercicio))
    totales = etree.SubElement(
        r, f"{{{ns}}}Totales", MontoTotOperacion=importe(d.monto_operacion),
        MontoTotGrav=importe(d.monto_gravado), MontoTotExent=importe(d.monto_exento),
        MontoTotRet=importe(d.monto_retenido))
    for i in d.impuestos:
        etree.SubElement(totales, f"{{{ns}}}ImpRetenidos", BaseRet=importe(i.base),
                         ImpuestoRet=i.impuesto, MontoRet=importe(i.monto),
                         TipoPagoRet=i.tipo_pago)
    return r


def sellar(doc: etree._Element, firmante: FirmanteCsd) -> str:
    """Pone NoCertificado y Certificado, calcula la cadena original y el Sello. Devuelve la
    cadena original (la usa la representación impresa)."""
    doc.set("NoCertificado", firmante.numero_certificado)
    doc.set("Certificado", firmante.certificado_base64)
    cadena = esquemas.cadena_original(doc)
    doc.set("Sello", firmante.firmar_base64(cadena.encode("utf-8"), "sha256"))
    return cadena


def a_bytes(doc: etree._Element) -> bytes:
    return etree.tostring(doc, xml_declaration=True, encoding="UTF-8")


def leer(xml: bytes) -> dict[str, Any]:
    """Los datos que pinta la constancia, leídos del XML (timbrado o no)."""
    raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {"r": esquemas.NS, "tfd": esquemas.NS_TFD}

    def at(ruta: str) -> dict[str, str]:
        n = raiz.find(ruta, ns)
        return dict(n.attrib) if n is not None else {}

    tfd = raiz.find("r:Complemento/tfd:TimbreFiscalDigital", ns)
    return {
        "raiz": dict(raiz.attrib), "emisor": at("r:Emisor"), "receptor": at("r:Receptor/r:Nacional")
        or at("r:Receptor/r:Extranjero"), "periodo": at("r:Periodo"), "totales": at("r:Totales"),
        "impuestos": [dict(n.attrib) for n in raiz.findall("r:Totales/r:ImpRetenidos", ns)],
        "timbre": dict(tfd.attrib) if tfd is not None else {},
        "cadena_tfd": esquemas.cadena_original_tfd(tfd) if tfd is not None else "",
    }
