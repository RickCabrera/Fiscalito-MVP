"""
CFDI 4.0 sintéticos con varios conceptos por tasa y retenciones (P3-04, P3-05).

RFC, nombres y UUID inventados. Los sellos son relleno: la bóveda no los valida.
"""

from __future__ import annotations

from decimal import Decimal

NS = "http://www.sat.gob.mx/cfd/4"


def _d(v: Decimal) -> str:
    return f"{v:.2f}"


def cfdi_tasas(
    uuid: str, *, emisor: str, receptor: str, fecha: str,
    conceptos: list[tuple[str, str]], tipo: str = "I", metodo: str = "PUE",
    isr_ret: str = "0", iva_ret: str = "0", regimen_emisor: str = "601",
    lugar: str = "91000", nombre_emisor: str = "PROVEEDOR SINTETICO",
    clave_prod: str = "84111506", uso: str = "G03",
) -> bytes:
    """
    Un CFDI con un concepto por renglón de `conceptos`: (base, tasa) donde tasa es
    "0.160000", "0.080000", "0.000000", "Exento" o "" (no objeto).
    """
    trasl: dict[tuple[str, str], list[Decimal]] = {}
    xml_conceptos = []
    subtotal = Decimal("0")
    for base, tasa in conceptos:
        b = Decimal(base)
        subtotal += b
        if tasa == "":
            imp, objeto = "", "01"
        elif tasa == "Exento":
            imp, objeto = (f'<cfdi:Impuestos><cfdi:Traslados><cfdi:Traslado Base="{_d(b)}" '
                           'Impuesto="002" TipoFactor="Exento"/></cfdi:Traslados>'
                           "</cfdi:Impuestos>"), "02"
            trasl.setdefault(("Exento", ""), [Decimal("0"), Decimal("0")])[0] += b
        else:
            importe = (b * Decimal(tasa)).quantize(Decimal("0.01"))
            imp, objeto = (f'<cfdi:Impuestos><cfdi:Traslados><cfdi:Traslado Base="{_d(b)}" '
                           f'Impuesto="002" TipoFactor="Tasa" TasaOCuota="{tasa}" '
                           f'Importe="{_d(importe)}"/></cfdi:Traslados></cfdi:Impuestos>'), "02"
            acum = trasl.setdefault(("Tasa", tasa), [Decimal("0"), Decimal("0")])
            acum[0] += b
            acum[1] += importe
        xml_conceptos.append(
            f'<cfdi:Concepto ClaveProdServ="{clave_prod}" Cantidad="1" ClaveUnidad="E48" '
            f'Descripcion="Concepto" ValorUnitario="{_d(b)}" Importe="{_d(b)}" '
            f'ObjetoImp="{objeto}">{imp}</cfdi:Concepto>')
    iva = sum((v[1] for v in trasl.values()), Decimal("0"))
    isr_r, iva_r = Decimal(isr_ret), Decimal(iva_ret)
    total = subtotal + iva - isr_r - iva_r
    nodos_t = "".join(
        f'<cfdi:Traslado Base="{_d(v[0])}" Impuesto="002" TipoFactor="{k[0]}"'
        + (f' TasaOCuota="{k[1]}" Importe="{_d(v[1])}"' if k[0] == "Tasa" else "") + "/>"
        for k, v in trasl.items())
    nodos_r = "".join(
        f'<cfdi:Retencion Impuesto="{i}" Importe="{_d(m)}"/>'
        for i, m in (("001", isr_r), ("002", iva_r)) if m)
    total_ret = f' TotalImpuestosRetenidos="{_d(isr_r + iva_r)}"' if nodos_r else ""
    impuestos = (
        f'<cfdi:Impuestos{total_ret} TotalImpuestosTrasladados="{_d(iva)}">'
        + (f"<cfdi:Retenciones>{nodos_r}</cfdi:Retenciones>" if nodos_r else "")
        + (f"<cfdi:Traslados>{nodos_t}</cfdi:Traslados>" if nodos_t else "")
        + "</cfdi:Impuestos>")
    timbre = (
        '<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
        f'Version="1.1" UUID="{uuid}" FechaTimbrado="{fecha}" RfcProvCertif="SAT970701NN3" '
        'SelloCFD="X" NoCertificadoSAT="00000000000000000000" SelloSAT="X"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<cfdi:Comprobante xmlns:cfdi="{NS}" Version="4.0" Serie="P" Folio="1" Fecha="{fecha}" '
        f'SubTotal="{_d(subtotal)}" Moneda="MXN" Total="{_d(total)}" TipoDeComprobante="{tipo}" '
        f'MetodoPago="{metodo}" FormaPago="03" LugarExpedicion="{lugar}" Exportacion="01" '
        'Sello="X" NoCertificado="00000000000000000000" Certificado="X">'
        f'<cfdi:Emisor Rfc="{emisor}" Nombre="{nombre_emisor}" RegimenFiscal="{regimen_emisor}"/>'
        f'<cfdi:Receptor Rfc="{receptor}" Nombre="RECEPTOR SINTETICO" UsoCFDI="{uso}" '
        'DomicilioFiscalReceptor="91000" RegimenFiscalReceptor="601"/>'
        f'<cfdi:Conceptos>{"".join(xml_conceptos)}</cfdi:Conceptos>{impuestos}'
        f"<cfdi:Complemento>{timbre}</cfdi:Complemento></cfdi:Comprobante>"
    ).encode("utf-8")
