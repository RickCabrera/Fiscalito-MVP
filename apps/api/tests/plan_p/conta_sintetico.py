"""
CFDI sintéticos para los tests de contabilidad (P2). RFC, nombres y UUID inventados.

`factura()` arma un CFDI 4.0 I/E con conceptos a la medida (ClaveProdServ, IVA por tasa,
retenciones), método y forma de pago y uso. `pago20()` y `nomina()` arman los complementos.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_COMPRADOR, RFC_PROVEEDOR, uuid_n

NS = "http://www.sat.gob.mx/cfd/4"
TIMBRE = ('<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
          'Version="1.1" UUID="{uuid}" FechaTimbrado="{fecha}" RfcProvCertif="SAT970701NN3" '
          'SelloCFD="X" NoCertificadoSAT="00000000000000000000" SelloSAT="X"/>')

__all__ = ["RFC_CLIENTE", "RFC_COMPRADOR", "RFC_PROVEEDOR", "uuid_n", "Concepto", "factura",
           "pago20", "nomina"]


@dataclass
class Concepto:
    importe: str = "1000.00"
    clave: str = "84111506"
    descripcion: str = "Servicio"
    tasa: str = "0.160000"  # "" = exento
    ret_isr: str = ""
    ret_iva: str = ""


def _q(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01'))}"


def factura(uuid: str, *, tipo: str = "I", emisor: str = RFC_CLIENTE,
            receptor: str = RFC_COMPRADOR, fecha: str = "2026-03-10T10:00:00",
            metodo: str = "PUE", forma: str = "03", uso: str = "G03",
            conceptos: list[Concepto] | None = None, moneda: str = "MXN",
            tipo_cambio: str = "") -> bytes:
    conceptos = conceptos or [Concepto()]
    subtotal = Decimal("0")
    iva = ret_isr = ret_iva = Decimal("0")
    nodos = []
    for c in conceptos:
        base = Decimal(c.importe)
        subtotal += base
        tras = ret = ""
        if c.tasa:
            imp = (base * Decimal(c.tasa)).quantize(Decimal("0.01"))
            iva += imp
            tras = (f'<cfdi:Traslados><cfdi:Traslado Base="{_q(base)}" Impuesto="002" '
                    f'TipoFactor="Tasa" TasaOCuota="{c.tasa}" Importe="{_q(imp)}"/>'
                    '</cfdi:Traslados>')
        else:
            tras = (f'<cfdi:Traslados><cfdi:Traslado Base="{_q(base)}" Impuesto="002" '
                    'TipoFactor="Exento"/></cfdi:Traslados>')
        rets = []
        if c.ret_isr:
            ret_isr += Decimal(c.ret_isr)
            rets.append(f'<cfdi:Retencion Base="{_q(base)}" Impuesto="001" TipoFactor="Tasa" '
                        f'TasaOCuota="0.100000" Importe="{c.ret_isr}"/>')
        if c.ret_iva:
            ret_iva += Decimal(c.ret_iva)
            rets.append(f'<cfdi:Retencion Base="{_q(base)}" Impuesto="002" TipoFactor="Tasa" '
                        f'TasaOCuota="0.106667" Importe="{c.ret_iva}"/>')
        if rets:
            ret = f'<cfdi:Retenciones>{"".join(rets)}</cfdi:Retenciones>'
        nodos.append(
            f'<cfdi:Concepto ClaveProdServ="{c.clave}" Cantidad="1" ClaveUnidad="E48" '
            f'Descripcion="{c.descripcion}" ValorUnitario="{c.importe}" Importe="{c.importe}" '
            f'ObjetoImp="02"><cfdi:Impuestos>{tras}{ret}</cfdi:Impuestos></cfdi:Concepto>')
    total = subtotal + iva - ret_isr - ret_iva
    retenciones = ""
    if ret_isr or ret_iva:
        partes = []
        if ret_isr:
            partes.append(f'<cfdi:Retencion Impuesto="001" Importe="{_q(ret_isr)}"/>')
        if ret_iva:
            partes.append(f'<cfdi:Retencion Impuesto="002" Importe="{_q(ret_iva)}"/>')
        retenciones = f'<cfdi:Retenciones>{"".join(partes)}</cfdi:Retenciones>'
    traslados = ""
    if iva:
        traslados = (f'<cfdi:Traslados><cfdi:Traslado Base="{_q(subtotal)}" Impuesto="002" '
                     f'TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{_q(iva)}"/>'
                     '</cfdi:Traslados>')
    tc = f' TipoCambio="{tipo_cambio}"' if tipo_cambio else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<cfdi:Comprobante xmlns:cfdi="{NS}" Version="4.0" Serie="T" Folio="1" Fecha="{fecha}" '
        f'SubTotal="{_q(subtotal)}" Moneda="{moneda}"{tc} Total="{_q(total)}" '
        f'TipoDeComprobante="{tipo}" MetodoPago="{metodo}" FormaPago="{forma}" '
        'LugarExpedicion="91000" Sello="X" NoCertificado="0" Certificado="X">'
        f'<cfdi:Emisor Rfc="{emisor}" Nombre="EMISOR" RegimenFiscal="601"/>'
        f'<cfdi:Receptor Rfc="{receptor}" Nombre="RECEPTOR" UsoCFDI="{uso}"/>'
        f'<cfdi:Conceptos>{"".join(nodos)}</cfdi:Conceptos>'
        f'<cfdi:Impuestos TotalImpuestosTrasladados="{_q(iva)}">{retenciones}{traslados}'
        '</cfdi:Impuestos>'
        f'<cfdi:Complemento>{TIMBRE.format(uuid=uuid, fecha=fecha)}</cfdi:Complemento>'
        '</cfdi:Comprobante>'
    ).encode()


def pago20(uuid: str, documentos: list[tuple[str, str, str]], *, emisor: str = RFC_CLIENTE,
           receptor: str = RFC_COMPRADOR, fecha: str = "2026-04-05T12:00:00",
           forma: str = "03", iva_totales: str = "") -> bytes:
    """documentos: (uuid, saldo_anterior, pagado)."""
    monto = sum((Decimal(p) for _u, _s, p in documentos), Decimal("0"))
    docs = "".join(
        f'<pago20:DoctoRelacionado IdDocumento="{u}" MonedaDR="MXN" EquivalenciaDR="1" '
        f'NumParcialidad="1" ImpSaldoAnt="{s}" ImpPagado="{p}" '
        f'ImpSaldoInsoluto="{_q(Decimal(s) - Decimal(p))}" ObjetoImpDR="02"/>'
        for u, s, p in documentos)
    totales_iva = f' TotalTrasladosImpuestoIVA16="{iva_totales}"' if iva_totales else ""
    nodo = ('<pago20:Pagos xmlns:pago20="http://www.sat.gob.mx/Pagos20" Version="2.0">'
            f'<pago20:Totales MontoTotalPagos="{_q(monto)}"{totales_iva}/>'
            f'<pago20:Pago FechaPago="{fecha}" FormaDePagoP="{forma}" MonedaP="MXN" '
            f'TipoCambioP="1" Monto="{_q(monto)}">{docs}</pago20:Pago></pago20:Pagos>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<cfdi:Comprobante xmlns:cfdi="{NS}" Version="4.0" Serie="P" Folio="1" Fecha="{fecha}" '
        'SubTotal="0" Moneda="XXX" Total="0" TipoDeComprobante="P" LugarExpedicion="91000" '
        'Sello="X" NoCertificado="0" Certificado="X">'
        f'<cfdi:Emisor Rfc="{emisor}" Nombre="EMISOR" RegimenFiscal="601"/>'
        f'<cfdi:Receptor Rfc="{receptor}" Nombre="RECEPTOR" UsoCFDI="CP01"/>'
        '<cfdi:Conceptos><cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" '
        'ClaveUnidad="ACT" Descripcion="Pago" ValorUnitario="0" Importe="0" ObjetoImp="01"/>'
        f'</cfdi:Conceptos><cfdi:Complemento>{TIMBRE.format(uuid=uuid, fecha=fecha)}{nodo}'
        '</cfdi:Complemento></cfdi:Comprobante>'
    ).encode()


def nomina(uuid: str, *, receptor: str = "TRAB010101AA1", fecha: str = "2026-03-15T10:00:00",
           percepciones: str = "10000.00", isr: str = "1000.00", imss: str = "250.00",
           otros_pagos: str = "0.00", regimen: str = "02",
           mas_deducciones: tuple[tuple[str, str], ...] = (),
           mas_otros_pagos: tuple[tuple[str, str], ...] = ()) -> bytes:
    """`mas_deducciones` / `mas_otros_pagos`: (TipoDeduccion|TipoOtroPago, importe) extra."""
    extra_ded = sum((Decimal(i) for _t, i in mas_deducciones), Decimal("0"))
    extra_otros = sum((Decimal(i) for _t, i in mas_otros_pagos), Decimal("0"))
    deducciones = _q(Decimal(isr) + Decimal(imss) + extra_ded)
    total_otros = _q(Decimal(otros_pagos) + extra_otros)
    total = _q(Decimal(percepciones) + Decimal(total_otros) - Decimal(deducciones))
    subtotal = _q(Decimal(percepciones) + Decimal(total_otros))
    nodos_otros = (f'<nomina12:OtroPago TipoOtroPago="002" Clave="002" '
                   f'Concepto="Subsidio" Importe="{otros_pagos}"><nomina12:SubsidioAlEmpleo '
                   f'SubsidioCausado="{otros_pagos}"/></nomina12:OtroPago>'
                   if Decimal(otros_pagos) else "")
    nodos_otros += "".join(f'<nomina12:OtroPago TipoOtroPago="{t}" Clave="{t}" Concepto="Otro" '
                           f'Importe="{i}"/>' for t, i in mas_otros_pagos)
    otros = f"<nomina12:OtrosPagos>{nodos_otros}</nomina12:OtrosPagos>" if nodos_otros else ""
    otras_ded = "".join(f'<nomina12:Deduccion TipoDeduccion="{t}" Clave="{t}" Concepto="Otra" '
                        f'Importe="{i}"/>' for t, i in mas_deducciones)
    otros_pagos = total_otros
    nodo = (
        '<nomina12:Nomina xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="1.2" '
        'TipoNomina="O" FechaPago="2026-03-15" FechaInicialPago="2026-03-01" '
        f'FechaFinalPago="2026-03-15" NumDiasPagados="15" TotalPercepciones="{percepciones}" '
        f'TotalDeducciones="{deducciones}" TotalOtrosPagos="{otros_pagos}">'
        '<nomina12:Emisor RegistroPatronal="Y0000000000"/>'
        f'<nomina12:Receptor Curp="XEXX010101HDFXXX01" TipoRegimen="{regimen}" NumEmpleado="1" '
        'PeriodicidadPago="04" TipoContrato="01" ClaveEntFed="VER"/>'
        f'<nomina12:Percepciones TotalSueldos="{percepciones}" TotalGravado="{percepciones}" '
        'TotalExento="0.00"/>'
        f'<nomina12:Deducciones TotalOtrasDeducciones="{_q(Decimal(imss) + extra_ded)}" '
        f'TotalImpuestosRetenidos="{isr}">'
        f'<nomina12:Deduccion TipoDeduccion="002" Clave="002" Concepto="ISR" Importe="{isr}"/>'
        f'<nomina12:Deduccion TipoDeduccion="001" Clave="001" Concepto="IMSS" Importe="{imss}"/>'
        f'{otras_ded}</nomina12:Deducciones>{otros}</nomina12:Nomina>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<cfdi:Comprobante xmlns:cfdi="{NS}" Version="4.0" Serie="N" Folio="1" Fecha="{fecha}" '
        f'SubTotal="{subtotal}" Descuento="{deducciones}" Moneda="MXN" Total="{total}" '
        'TipoDeComprobante="N" MetodoPago="PUE" LugarExpedicion="91000" Sello="X" '
        'NoCertificado="0" Certificado="X">'
        f'<cfdi:Emisor Rfc="{RFC_CLIENTE}" Nombre="PATRON" RegimenFiscal="601"/>'
        f'<cfdi:Receptor Rfc="{receptor}" Nombre="TRABAJADOR" UsoCFDI="CN01"/>'
        '<cfdi:Conceptos><cfdi:Concepto ClaveProdServ="84111505" Cantidad="1" ClaveUnidad="ACT" '
        f'Descripcion="Pago de nómina" ValorUnitario="{subtotal}" Importe="{subtotal}" '
        f'Descuento="{deducciones}" ObjetoImp="01"/></cfdi:Conceptos>'
        f'<cfdi:Complemento>{TIMBRE.format(uuid=uuid, fecha=fecha)}{nodo}</cfdi:Complemento>'
        '</cfdi:Comprobante>'
    ).encode()
