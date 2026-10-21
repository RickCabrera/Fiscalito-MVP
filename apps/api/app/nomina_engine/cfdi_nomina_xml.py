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

from app.nomina_engine.cfdi_nomina_nodos import (  # noqa: F401 — movido en P6-05, se reexporta
    ATRIBUTO_ANTIGUEDAD,
    CERTIFICADO_SIN_TIMBRAR,
    CLAVE_PROD_SERV_NOMINA,
    CLAVE_UNIDAD_NOMINA,
    COMENTARIO_CABECERA,
    NO_CERTIFICADO_SIN_TIMBRAR,
    NS_CFDI,
    NS_NOMINA,
    NS_XSI,
    SELLO_SIN_TIMBRAR,
    ExtrasNomina,
    HorasExtraCfdi,
    IncapacidadCfdi,
    JubilacionCfdi,
    SeparacionCfdi,
    _comprobante,
    _importe,
    _nodo_deducciones,
    _nodo_incapacidades,
    _nodo_otros_pagos,
    _nodo_percepciones,
    _sub,
)
from app.nomina_engine.recibo import (
    DatosPatron,
    DatosTrabajador,
    Recibo,
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
    extras: ExtrasNomina | None = None,
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
            # Guía de llenado: TotalDeducciones/TotalOtrosPagos sólo si existe su nodo.
            "TotalDeducciones": _importe(recibo.total_deducciones) if recibo.deducciones else "",
            "TotalOtrosPagos": _importe(recibo.total_otros_pagos) if recibo.otros_pagos else "",
        },
    )
    # Guía de llenado: si NO hay RegistroPatronal (asimilados, régimen 13) no debe existir
    # ninguno de NumSeguridadSocial, FechaInicioRelLaboral, Antigüedad, RiesgoPuesto,
    # SalarioBaseCotApor ni SalarioDiarioIntegrado.
    con_imss = bool(patron.registro_patronal)
    emisor = {"Curp": patron.curp, "RegistroPatronal": patron.registro_patronal}
    if any(emisor.values()):
        _sub(nomina, f"{{{NS_NOMINA}}}Emisor", emisor)
    inicio = trabajador.fecha_inicio_relacion_laboral
    sbc, sdi = trabajador.salario_base_cotizacion, trabajador.salario_diario_integrado
    _sub(
        nomina,
        f"{{{NS_NOMINA}}}Receptor",
        {
            "Curp": trabajador.curp,
            "NumSeguridadSocial": trabajador.numero_seguridad_social if con_imss else "",
            "FechaInicioRelLaboral": inicio.isoformat() if con_imss and inicio else "",
            ATRIBUTO_ANTIGUEDAD: trabajador.antiguedad if con_imss else "",
            "TipoContrato": trabajador.tipo_contrato,
            "Sindicalizado": trabajador.sindicalizado,
            "TipoJornada": trabajador.tipo_jornada,
            "TipoRegimen": trabajador.tipo_regimen,
            "NumEmpleado": trabajador.numero_empleado,
            "Departamento": trabajador.departamento,
            "Puesto": trabajador.puesto,
            "RiesgoPuesto": trabajador.riesgo_puesto if con_imss else "",
            "PeriodicidadPago": trabajador.periodicidad_pago,
            "SalarioBaseCotApor": _importe(sbc) if con_imss and sbc is not None else "",
            "SalarioDiarioIntegrado": _importe(sdi) if con_imss and sdi is not None else "",
            "ClaveEntFed": patron.clave_entidad,
        },
    )
    _nodo_percepciones(nomina, recibo, extras)
    _nodo_deducciones(nomina, recibo)
    _nodo_otros_pagos(nomina, recibo)
    _nodo_incapacidades(nomina, extras)

    cuerpo = ET.tostring(raiz, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<!--{COMENTARIO_CABECERA}-->\n"
        f"{cuerpo}"
    )
