"""
XML del CFDI 4.0 de ingreso (I), egreso (E) y pago (P, complemento Pagos 2.0) — P5-04.

Estructura y orden de nodos: `cfdv40.xsd` (CfdiRelacionados, Emisor, Receptor, Conceptos,
Impuestos, Complemento; en el concepto Traslados antes que Retenciones; en el comprobante
Retenciones antes que Traslados) y `Pagos20.xsd` (Totales, Pago; en cada nivel Retenciones antes
que Traslados). Los importes vienen YA calculados por `app.facturacion.calculo`: aquí no se
suma nada. El XML sale SIN sellar (`Sello`, `NoCertificado` y `Certificado` vacíos); lo sella
`app.nomina_cfdi.servicio.sellar` (misma cadena original XSLT y mismo CSD que nómina).

CFDI de pago (Guía de llenado del complemento de recepción de pagos 2.0): `SubTotal` 0,
`Total` 0, `Moneda` XXX, sin `FormaPago` ni `MetodoPago`, `UsoCFDI` CP01 y un solo concepto
84111506 / ACT / "Pago" con valor 0 y `ObjetoImp` 01. `TipoCambioP` = 1 y `EquivalenciaDR` = 1
porque sólo se admiten pagos en MXN a facturas en MXN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from lxml import etree

from app.facturacion import calculo
from app.facturacion.catalogos import CONCEPTO_PAGO
from app.facturacion.esquemas import NS_CFDI, NS_PAGOS, XSD_PAGOS

NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD_CFDI = "http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"


@dataclass(frozen=True)
class Emisor:
    rfc: str
    nombre: str
    regimen: str


@dataclass(frozen=True)
class Receptor:
    rfc: str
    nombre: str
    regimen: str
    domicilio_fiscal: str
    uso_cfdi: str


@dataclass(frozen=True)
class Relacion:
    tipo_relacion: str
    uuids: tuple[str, ...]


@dataclass
class Encabezado:
    serie: str
    folio: str
    fecha: datetime
    lugar_expedicion: str
    emisor: Emisor
    receptor: Receptor
    relacionados: list[Relacion] = field(default_factory=list)


@dataclass
class DatosFactura:
    tipo: str  # I | E
    encabezado: Encabezado
    forma_pago: str
    metodo_pago: str
    comprobante: calculo.Comprobante
    condiciones_pago: str = ""


@dataclass
class DatosPago:
    encabezado: Encabezado
    fecha_pago: datetime
    forma_pago: str
    pago: calculo.Pago
    num_operacion: str = ""


def dos(v: Decimal) -> str:
    return f"{v:.2f}"


def seis(v: Decimal) -> str:
    return f"{v:.6f}"


def libre(v: Decimal) -> str:
    """Cantidad / ValorUnitario: hasta 6 decimales, al menos 2, sin exponente."""
    texto = f"{v:.6f}".rstrip("0")
    entero, _, dec = texto.partition(".")
    return f"{entero}.{dec.ljust(2, '0')}"


def _q(nombre: str, ns: str = NS_CFDI) -> str:
    return f"{{{ns}}}{nombre}"


def _sub(padre: etree._Element, nombre: str, attrs: list[tuple[str, str | None]],
         ns: str = NS_CFDI) -> etree._Element:
    n = etree.SubElement(padre, _q(nombre, ns))
    for k, v in attrs:
        if v not in (None, ""):
            n.set(k, str(v))
    return n


def _raiz(enc: Encabezado, extra_ns: dict[str, str], ubicaciones: str,
          attrs: list[tuple[str, str | None]]) -> etree._Element:
    r = etree.Element(_q("Comprobante"), nsmap={"cfdi": NS_CFDI, "xsi": NS_XSI, **extra_ns})
    r.set(f"{{{NS_XSI}}}schemaLocation", ubicaciones)
    base: list[tuple[str, str | None]] = [
        ("Version", "4.0"), ("Serie", enc.serie), ("Folio", enc.folio),
        ("Fecha", enc.fecha.replace(microsecond=0, tzinfo=None).isoformat()),
        ("Sello", ""), ("NoCertificado", ""), ("Certificado", ""),
    ]
    for k, v in base + attrs + [("Exportacion", "01"), ("LugarExpedicion",
                                                          enc.lugar_expedicion)]:
        if v is not None and (v != "" or k in ("Sello", "NoCertificado", "Certificado")):
            r.set(k, v)
    for rel in enc.relacionados:
        nodo = _sub(r, "CfdiRelacionados", [("TipoRelacion", rel.tipo_relacion)])
        for u in rel.uuids:
            _sub(nodo, "CfdiRelacionado", [("UUID", u.upper())])
    e, rc = enc.emisor, enc.receptor
    _sub(r, "Emisor", [("Rfc", e.rfc), ("Nombre", e.nombre), ("RegimenFiscal", e.regimen)])
    _sub(r, "Receptor", [("Rfc", rc.rfc), ("Nombre", rc.nombre),
                         ("DomicilioFiscalReceptor", rc.domicilio_fiscal),
                         ("RegimenFiscalReceptor", rc.regimen), ("UsoCFDI", rc.uso_cfdi)])
    return r


def _impuesto_attrs(i: calculo.ImpuestoCalculado, sufijo: str = "",
                    con_base: bool = True) -> list[tuple[str, str | None]]:
    attrs: list[tuple[str, str | None]] = []
    if con_base:
        attrs.append((f"Base{sufijo}", dos(i.base) if not sufijo else seis(i.base)))
    attrs.append((f"Impuesto{sufijo}", i.impuesto))
    attrs.append((f"TipoFactor{sufijo}", i.tipo_factor))
    if i.tasa is not None:
        attrs.append((f"TasaOCuota{sufijo}", seis(i.tasa)))
    if i.importe is not None:
        attrs.append((f"Importe{sufijo}", dos(i.importe) if not sufijo else seis(i.importe)))
    return attrs


def factura(d: DatosFactura) -> etree._Element:
    """XML sin sellar de un CFDI de ingreso o egreso."""
    c = d.comprobante
    r = _raiz(d.encabezado, {}, f"{NS_CFDI} {XSD_CFDI}", [
        ("FormaPago", d.forma_pago), ("CondicionesDePago", d.condiciones_pago),
        ("SubTotal", dos(c.subtotal)), ("Descuento", dos(c.descuento) if c.descuento else None),
        ("Moneda", "MXN"), ("Total", dos(c.total)), ("TipoDeComprobante", d.tipo),
        ("MetodoPago", d.metodo_pago),
    ])
    conceptos = _sub(r, "Conceptos", [])
    for cc in c.conceptos:
        e = cc.entrada
        nodo = _sub(conceptos, "Concepto", [
            ("ClaveProdServ", e.clave_prod_serv), ("NoIdentificacion", e.no_identificacion),
            ("Cantidad", libre(e.cantidad)), ("ClaveUnidad", e.clave_unidad),
            ("Unidad", e.unidad), ("Descripcion", e.descripcion),
            ("ValorUnitario", libre(e.valor_unitario)), ("Importe", dos(cc.importe)),
            ("Descuento", dos(e.descuento) if e.descuento else None),
            ("ObjetoImp", e.objeto_imp)])
        if not cc.impuestos:
            continue
        imp = _sub(nodo, "Impuestos", [])
        tras = [i for i in cc.impuestos if i.tipo == "traslado"]
        rets = [i for i in cc.impuestos if i.tipo == "retencion"]
        if tras:
            t = _sub(imp, "Traslados", [])
            for i in tras:
                _sub(t, "Traslado", _impuesto_attrs(i))
        if rets:
            t = _sub(imp, "Retenciones", [])
            for i in rets:
                _sub(t, "Retencion", _impuesto_attrs(i))
    if c.traslados or c.retenciones:
        imp = _sub(r, "Impuestos", [
            ("TotalImpuestosRetenidos", dos(c.total_retenciones)
             if c.total_retenciones is not None else None),
            ("TotalImpuestosTrasladados", dos(c.total_traslados)
             if c.total_traslados is not None else None)])
        if c.retenciones:
            t = _sub(imp, "Retenciones", [])
            for i in c.retenciones:
                _sub(t, "Retencion", [("Impuesto", i.impuesto), ("Importe", dos(i.importe))])
        if c.traslados:
            t = _sub(imp, "Traslados", [])
            for i in c.traslados:
                _sub(t, "Traslado", _impuesto_attrs(i))
    return r


def pago(d: DatosPago) -> etree._Element:
    """XML sin sellar de un CFDI de pago con complemento Pagos 2.0."""
    r = _raiz(d.encabezado, {"pago20": NS_PAGOS},
              f"{NS_CFDI} {XSD_CFDI} {NS_PAGOS} {XSD_PAGOS}",
              [("SubTotal", "0"), ("Moneda", "XXX"), ("Total", "0"),
               ("TipoDeComprobante", "P")])
    conceptos = _sub(r, "Conceptos", [])
    _sub(conceptos, "Concepto", list(CONCEPTO_PAGO.items()))
    comp = _sub(r, "Complemento", [])
    p = d.pago
    pagos = _sub(comp, "Pagos", [("Version", "2.0")], NS_PAGOS)
    orden = ("TotalRetencionesIVA", "TotalRetencionesISR", "TotalTrasladosBaseIVA16",
             "TotalTrasladosImpuestoIVA16", "TotalTrasladosBaseIVA8",
             "TotalTrasladosImpuestoIVA8", "TotalTrasladosBaseIVA0",
             "TotalTrasladosImpuestoIVA0", "TotalTrasladosBaseIVAExento", "MontoTotalPagos")
    _sub(pagos, "Totales", [(k, dos(p.totales[k])) for k in orden if k in p.totales], NS_PAGOS)
    nodo = _sub(pagos, "Pago", [
        ("FechaPago", d.fecha_pago.replace(microsecond=0, tzinfo=None).isoformat()),
        ("FormaDePagoP", d.forma_pago), ("MonedaP", "MXN"), ("TipoCambioP", "1"),
        ("Monto", dos(p.monto)), ("NumOperacion", d.num_operacion)], NS_PAGOS)
    for dc in p.documentos:
        doc = dc.doc
        dr = _sub(nodo, "DoctoRelacionado", [
            ("IdDocumento", doc.uuid.upper()), ("Serie", doc.serie), ("Folio", doc.folio),
            ("MonedaDR", "MXN"), ("EquivalenciaDR", "1"),
            ("NumParcialidad", str(doc.num_parcialidad)),
            ("ImpSaldoAnt", dos(doc.saldo_anterior)), ("ImpPagado", dos(doc.importe_pagado)),
            ("ImpSaldoInsoluto", dos(dc.saldo_insoluto)), ("ObjetoImpDR", doc.objeto_imp)],
            NS_PAGOS)
        if doc.objeto_imp != "02":
            continue
        imp = _sub(dr, "ImpuestosDR", [], NS_PAGOS)
        if dc.retenciones:
            g = _sub(imp, "RetencionesDR", [], NS_PAGOS)
            for i in dc.retenciones:
                _sub(g, "RetencionDR", _impuesto_attrs(i, "DR"), NS_PAGOS)
        if dc.traslados:
            g = _sub(imp, "TrasladosDR", [], NS_PAGOS)
            for i in dc.traslados:
                _sub(g, "TrasladoDR", _impuesto_attrs(i, "DR"), NS_PAGOS)
    if p.retenciones_p or p.traslados_p:
        imp = _sub(nodo, "ImpuestosP", [], NS_PAGOS)
        if p.retenciones_p:
            g = _sub(imp, "RetencionesP", [], NS_PAGOS)
            for i in p.retenciones_p:
                _sub(g, "RetencionP", [("ImpuestoP", i.impuesto),
                                       ("ImporteP", seis(i.importe or Decimal(0)))], NS_PAGOS)
        if p.traslados_p:
            g = _sub(imp, "TrasladosP", [], NS_PAGOS)
            for i in p.traslados_p:
                _sub(g, "TrasladoP", _impuesto_attrs(i, "P"), NS_PAGOS)
    return r


def a_bytes(doc: etree._Element) -> bytes:
    return etree.tostring(doc, xml_declaration=True, encoding="UTF-8")
