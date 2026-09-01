"""
Genera el XML de un CFDI de nomina 4.0 con complemento 1.2, **sin timbrar**.

QUE ES Y QUE NO ES LO QUE SALE DE AQUI
--------------------------------------
Es un **pre-recibo**: estructuralmente valido contra los XSD del SAT, y
fiscalmente **nada**. Tres cosas lo hacen inconfundible:

1. **No lleva `tfd:TimbreFiscalDigital`.** Ahi muere la confusion: un CFDI
   timbrado siempre lo trae, con su UUID y la fecha de timbrado. El XSD no lo
   exige —`Complemento` es un wildcard— asi que su ausencia es legal y
   verificable. Es la salvaguarda que sobrevive a cualquier reserializacion.
2. Los atributos de sello llevan **centinelas explicitos** en vez de un sello.
   El XSD los exige (`Sello`, `Certificado` y `NoCertificado` son
   `use="required"`), asi que no se pueden omitir; lo que si se puede es que
   digan lo que son.
3. Un comentario de cabecera. Es cortesia, no salvaguarda: cualquier
   reserializacion lo borra. Las garantias son las dos de arriba.

ALCANCE DE LA VALIDACION XSD
----------------------------
El XSD valida **estructura y catalogos**. NO valida las reglas de la Guia de
llenado ni las validaciones adicionales del Anexo 20. Un XML que valida aqui
**no es evidencia de que un PAC lo aceptaria** (§D7: el timbrado real es F3).

POR QUE NO SE USA lxml AQUI
---------------------------
`lxml` es dependencia de **tests**, no de runtime: validar necesita lxml, pero
generar no. Si este modulo lo importara, `lxml` se volveria dependencia del
contenedor de Cloud Run, donde `pyproject.toml` no lo instala. Se genera con
`xml.etree.ElementTree` de la stdlib.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

from app.nomina_engine.recibo import (
    CLAVE_OTRO_PAGO_SUBSIDIO,
    DatosPatron,
    DatosTrabajador,
    Recibo,
)

NS_CFDI = "http://www.sat.gob.mx/cfd/4"
NS_NOMINA = "http://www.sat.gob.mx/nomina12"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# `Antigüedad` lleva dieresis. Se nombra por constante para que ningun editor
# la rompa en silencio, igual que hace `tests/nomina_inventario.py`.
ATRIBUTO_ANTIGUEDAD = "Antigüedad"

# Centinelas de los atributos que el XSD exige y un pre-recibo no tiene.
# `Sello` y `Certificado` son xs:string sin patron, asi que admiten texto.
# `NoCertificado` tiene pattern [0-9]{20}, asi que solo admite veinte digitos.
SELLO_SIN_TIMBRAR = "PRE-RECIBO-SIN-TIMBRAR"
CERTIFICADO_SIN_TIMBRAR = "PRE-RECIBO-SIN-TIMBRAR"
NO_CERTIFICADO_SIN_TIMBRAR = "0" * 20

COMENTARIO_CABECERA = (
    " PRE-RECIBO SIN TIMBRAR. No es un CFDI fiscalmente valido: no lleva "
    "TimbreFiscalDigital y sus atributos de sello son centinelas. "
)

# El CFDI de nomina siempre usa esta clave de producto y esta unidad.
CLAVE_PROD_SERV_NOMINA = "84111505"
CLAVE_UNIDAD_NOMINA = "ACT"


def _importe(valor: Decimal) -> str:
    """Los importes del CFDI van con 2 decimales."""
    return f"{valor:.2f}"


def _sub(padre: ET.Element, etiqueta: str, atributos: dict[str, str]) -> ET.Element:
    """Subelemento con solo los atributos que traen valor."""
    return ET.SubElement(padre, etiqueta, {k: v for k, v in atributos.items() if v})


def _comprobante(recibo: Recibo, patron: DatosPatron, fecha: datetime, serie, folio):
    raiz = ET.Element(
        f"{{{NS_CFDI}}}Comprobante",
        {
            f"{{{NS_XSI}}}schemaLocation": (
                "http://www.sat.gob.mx/cfd/4 "
                "http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd "
                "http://www.sat.gob.mx/nomina12 "
                "http://www.sat.gob.mx/sitio_internet/cfd/nomina/nomina12.xsd"
            ),
            "Version": "4.0",
            "Fecha": fecha.strftime("%Y-%m-%dT%H:%M:%S"),
            "Sello": SELLO_SIN_TIMBRAR,
            "NoCertificado": NO_CERTIFICADO_SIN_TIMBRAR,
            "Certificado": CERTIFICADO_SIN_TIMBRAR,
            "SubTotal": _importe(recibo.subtotal),
            "Descuento": _importe(recibo.descuento),
            "Moneda": "MXN",
            "Total": _importe(recibo.total),
            "TipoDeComprobante": "N",
            "Exportacion": "01",
            "MetodoPago": "PUE",
            "LugarExpedicion": patron.codigo_postal,
        },
    )
    if serie:
        raiz.set("Serie", serie)
    if folio:
        raiz.set("Folio", folio)
    return raiz


def _nodo_percepciones(nomina: ET.Element, recibo: Recibo) -> None:
    atributos = {
        "TotalSueldos": _importe(recibo.total_sueldos),
        "TotalGravado": _importe(recibo.total_gravado),
        "TotalExento": _importe(recibo.total_exento),
    }
    if recibo.total_separacion_indemnizacion:
        atributos["TotalSeparacionIndemnizacion"] = _importe(
            recibo.total_separacion_indemnizacion
        )
    if recibo.total_jubilacion_pension_retiro:
        atributos["TotalJubilacionPensionRetiro"] = _importe(
            recibo.total_jubilacion_pension_retiro
        )
    nodo = _sub(nomina, f"{{{NS_NOMINA}}}Percepciones", atributos)
    for p in recibo.percepciones:
        _sub(
            nodo,
            f"{{{NS_NOMINA}}}Percepcion",
            {
                "TipoPercepcion": p.tipo,
                "Clave": p.clave,
                "Concepto": p.concepto,
                "ImporteGravado": _importe(p.gravado),
                "ImporteExento": _importe(p.exento),
            },
        )


def _nodo_deducciones(nomina: ET.Element, recibo: Recibo) -> None:
    if not recibo.deducciones:
        return
    atributos = {}
    if recibo.total_impuestos_retenidos:
        atributos["TotalImpuestosRetenidos"] = _importe(recibo.total_impuestos_retenidos)
    if recibo.total_otras_deducciones:
        atributos["TotalOtrasDeducciones"] = _importe(recibo.total_otras_deducciones)
    nodo = _sub(nomina, f"{{{NS_NOMINA}}}Deducciones", atributos)
    for d in recibo.deducciones:
        _sub(
            nodo,
            f"{{{NS_NOMINA}}}Deduccion",
            {
                "TipoDeduccion": d.tipo,
                "Clave": d.clave,
                "Concepto": d.concepto,
                "Importe": _importe(d.importe),
            },
        )


def _nodo_otros_pagos(nomina: ET.Element, recibo: Recibo) -> None:
    if not recibo.otros_pagos:
        return
    nodo = ET.SubElement(nomina, f"{{{NS_NOMINA}}}OtrosPagos")
    for o in recibo.otros_pagos:
        otro = _sub(
            nodo,
            f"{{{NS_NOMINA}}}OtroPago",
            {
                "TipoOtroPago": o.tipo,
                "Clave": o.clave,
                "Concepto": o.concepto,
                "Importe": _importe(o.importe),
            },
        )
        if o.tipo == CLAVE_OTRO_PAGO_SUBSIDIO and o.subsidio_causado is not None:
            _sub(
                otro,
                f"{{{NS_NOMINA}}}SubsidioAlEmpleo",
                {"SubsidioCausado": _importe(o.subsidio_causado)},
            )


def generar_cfdi_nomina(
    recibo: Recibo,
    patron: DatosPatron,
    trabajador: DatosTrabajador,
    fecha_emision: datetime,
    fecha_inicial_pago: date,
    fecha_final_pago: date,
    fecha_pago: date,
    dias_pagados: Decimal,
    tipo_nomina: str = "O",
    serie: str = "",
    folio: str = "",
) -> str:
    """
    Serializa un pre-recibo de nomina a XML.

    El resultado valida contra los XSD del SAT versionados en `tests/xsd/` pero
    **no esta timbrado**: sin `TimbreFiscalDigital` y con centinelas en los
    atributos de sello. Ver el docstring del modulo.
    """
    ET.register_namespace("cfdi", NS_CFDI)
    ET.register_namespace("nomina12", NS_NOMINA)
    ET.register_namespace("xsi", NS_XSI)

    raiz = _comprobante(recibo, patron, fecha_emision, serie, folio)
    _sub(
        raiz,
        f"{{{NS_CFDI}}}Emisor",
        {"Rfc": patron.rfc, "Nombre": patron.nombre, "RegimenFiscal": patron.regimen_fiscal},
    )
    _sub(
        raiz,
        f"{{{NS_CFDI}}}Receptor",
        {
            "Rfc": trabajador.rfc,
            "Nombre": trabajador.nombre,
            "DomicilioFiscalReceptor": trabajador.codigo_postal,
            "RegimenFiscalReceptor": "605",
            "UsoCFDI": "CN01",
        },
    )
    conceptos = ET.SubElement(raiz, f"{{{NS_CFDI}}}Conceptos")
    _sub(
        conceptos,
        f"{{{NS_CFDI}}}Concepto",
        {
            "ClaveProdServ": CLAVE_PROD_SERV_NOMINA,
            "Cantidad": "1",
            "ClaveUnidad": CLAVE_UNIDAD_NOMINA,
            "Descripcion": "Pago de nómina",
            "ValorUnitario": _importe(recibo.subtotal),
            "Importe": _importe(recibo.subtotal),
            "Descuento": _importe(recibo.descuento),
            "ObjetoImp": "01",
        },
    )

    complemento = ET.SubElement(raiz, f"{{{NS_CFDI}}}Complemento")
    nomina = _sub(
        complemento,
        f"{{{NS_NOMINA}}}Nomina",
        {
            "Version": "1.2",
            "TipoNomina": tipo_nomina,
            "FechaPago": fecha_pago.isoformat(),
            "FechaInicialPago": fecha_inicial_pago.isoformat(),
            "FechaFinalPago": fecha_final_pago.isoformat(),
            "NumDiasPagados": f"{dias_pagados:.3f}",
            "TotalPercepciones": _importe(recibo.total_percepciones),
            "TotalDeducciones": _importe(recibo.total_deducciones),
            "TotalOtrosPagos": _importe(recibo.total_otros_pagos),
        },
    )
    _sub(
        nomina,
        f"{{{NS_NOMINA}}}Emisor",
        {"RegistroPatronal": patron.registro_patronal},
    )
    _sub(
        nomina,
        f"{{{NS_NOMINA}}}Receptor",
        {
            "Curp": trabajador.curp,
            "NumSeguridadSocial": trabajador.numero_seguridad_social,
            "FechaInicioRelLaboral": trabajador.fecha_inicio_relacion_laboral.isoformat(),
            ATRIBUTO_ANTIGUEDAD: trabajador.antiguedad,
            "TipoContrato": trabajador.tipo_contrato,
            "Sindicalizado": trabajador.sindicalizado,
            "TipoJornada": trabajador.tipo_jornada,
            "TipoRegimen": trabajador.tipo_regimen,
            "NumEmpleado": trabajador.numero_empleado,
            "Departamento": trabajador.departamento,
            "Puesto": trabajador.puesto,
            "RiesgoPuesto": trabajador.riesgo_puesto,
            "PeriodicidadPago": trabajador.periodicidad_pago,
            "SalarioBaseCotApor": _importe(trabajador.salario_base_cotizacion),
            "SalarioDiarioIntegrado": _importe(trabajador.salario_diario_integrado),
            "ClaveEntFed": patron.clave_entidad,
        },
    )
    _nodo_percepciones(nomina, recibo)
    _nodo_deducciones(nomina, recibo)
    _nodo_otros_pagos(nomina, recibo)

    cuerpo = ET.tostring(raiz, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<!--{COMENTARIO_CABECERA}-->\n"
        f"{cuerpo}"
    )
