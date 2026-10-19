"""
CFDI sintéticos para los tests de la bóveda (P0-03).

RFC, nombres y UUID inventados: nada de datos reales. Los sellos son relleno; la bóveda no
valida sellos (eso es estatus SAT, P1-03).
"""

from __future__ import annotations

NS = {"3.3": "http://www.sat.gob.mx/cfd/3", "4.0": "http://www.sat.gob.mx/cfd/4"}

RFC_CLIENTE = "XEXX010101AB1"
RFC_PROVEEDOR = "PRO010101AA1"
RFC_COMPRADOR = "COM010101BB2"


def uuid_n(n: int, prefijo: str = "AAAAAAAA") -> str:
    """UUID sintético determinístico."""
    return f"{prefijo}-0000-4000-8000-{n:012d}"


def cfdi(
    uuid: str,
    *,
    version: str = "4.0",
    tipo: str = "I",
    emisor: str = RFC_CLIENTE,
    receptor: str = RFC_COMPRADOR,
    fecha: str = "2026-03-10T10:00:00",
    subtotal: str = "1000.00",
    total: str = "1160.00",
    iva: str = "160.00",
    complemento_extra: str = "",
    sin_timbre: bool = False,
    extra_attrs: str = "",
) -> bytes:
    """Un CFDI I/E (o el tipo pedido) con un concepto y su IVA al 16 %."""
    ns = NS[version]
    impuestos = (
        f'<cfdi:Impuestos TotalImpuestosTrasladados="{iva}"><cfdi:Traslados>'
        f'<cfdi:Traslado Base="{subtotal}" Impuesto="002" TipoFactor="Tasa" '
        f'TasaOCuota="0.160000" Importe="{iva}"/></cfdi:Traslados></cfdi:Impuestos>'
        if tipo in {"I", "E"} else ""
    )
    timbre = "" if sin_timbre else (
        '<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
        f'Version="1.1" UUID="{uuid}" FechaTimbrado="{fecha}" RfcProvCertif="SAT970701NN3" '
        'SelloCFD="X" NoCertificadoSAT="00000000000000000000" SelloSAT="X"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<cfdi:Comprobante xmlns:cfdi="{ns}" Version="{version}" Serie="T" Folio="1" '
        f'Fecha="{fecha}" SubTotal="{subtotal}" Moneda="MXN" Total="{total}" '
        f'TipoDeComprobante="{tipo}" MetodoPago="PUE" FormaPago="03" LugarExpedicion="91000" '
        f'Sello="X" NoCertificado="00000000000000000000" Certificado="X" {extra_attrs}>'
        f'<cfdi:Emisor Rfc="{emisor}" Nombre="EMISOR SINTETICO" RegimenFiscal="601"/>'
        f'<cfdi:Receptor Rfc="{receptor}" Nombre="RECEPTOR SINTETICO" UsoCFDI="G03"/>'
        '<cfdi:Conceptos><cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" '
        f'ClaveUnidad="E48" Descripcion="Servicio" ValorUnitario="{subtotal}" '
        f'Importe="{subtotal}"/></cfdi:Conceptos>'
        f'{impuestos}<cfdi:Complemento>{timbre}{complemento_extra}</cfdi:Complemento>'
        '</cfdi:Comprobante>'
    ).encode("utf-8")


def pago(uuid: str, relacionados: list[str], *, version_pagos: str = "2.0",
         version: str = "4.0", emisor: str = RFC_CLIENTE,
         receptor: str = RFC_COMPRADOR) -> bytes:
    """Complemento de recepción de pagos 1.0 (con CFDI 3.3) o 2.0 (con 4.0)."""
    if version_pagos == "1.0":
        ns, pref = "http://www.sat.gob.mx/Pagos", "pago10"
        docs = "".join(
            f'<{pref}:DoctoRelacionado IdDocumento="{u}" MonedaDR="MXN" MetodoDePagoDR="PPD" '
            f'NumParcialidad="1" ImpSaldoAnt="1160.00" ImpPagado="1160.00" '
            f'ImpSaldoInsoluto="0.00"/>' for u in relacionados
        )
        nodo = (f'<{pref}:Pagos xmlns:{pref}="{ns}" Version="1.0"><{pref}:Pago '
                f'FechaPago="2026-03-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" '
                f'Monto="{1160 * len(relacionados)}.00">{docs}</{pref}:Pago></{pref}:Pagos>')
    else:
        ns, pref = "http://www.sat.gob.mx/Pagos20", "pago20"
        docs = "".join(
            f'<{pref}:DoctoRelacionado IdDocumento="{u}" MonedaDR="MXN" EquivalenciaDR="1" '
            f'NumParcialidad="1" ImpSaldoAnt="1160.00" ImpPagado="1160.00" '
            f'ImpSaldoInsoluto="0.00" ObjetoImpDR="02"/>' for u in relacionados
        )
        nodo = (f'<{pref}:Pagos xmlns:{pref}="{ns}" Version="2.0">'
                f'<{pref}:Totales TotalTrasladosBaseIVA16="1000.00" '
                f'TotalTrasladosImpuestoIVA16="160.00" MontoTotalPagos="1160.00"/>'
                f'<{pref}:Pago FechaPago="2026-03-20T12:00:00" FormaDePagoP="03" '
                f'MonedaP="MXN" TipoCambioP="1" Monto="1160.00">{docs}</{pref}:Pago>'
                f'</{pref}:Pagos>')
    xml = cfdi(uuid, version=version, tipo="P", emisor=emisor, receptor=receptor,
               subtotal="0", total="0", complemento_extra=nodo)
    # El tipo P no lleva MetodoPago ni FormaPago.
    return xml.replace(b' MetodoPago="PUE" FormaPago="03"', b"")
