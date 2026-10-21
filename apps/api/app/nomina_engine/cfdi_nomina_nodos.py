"""
Constantes, datos extra (horas extra, incapacidades, separación, jubilación) y nodos del
complemento de nómina 1.2 que arma `generar_cfdi_nomina`. Salió de `cfdi_nomina_xml.py` en
P6-05 (tope de 300 líneas) sin cambiar nada; ese módulo lo reexporta.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.nomina_engine.recibo import (
    CLAVE_OTRO_PAGO_SUBSIDIO,
    DatosPatron,
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


@dataclass(frozen=True)
class HorasExtraCfdi:
    """Nodo `HorasExtra` de una percepción 019 (Guía de llenado: obligatorio con la 019)."""

    clave_percepcion: str  # la `Clave` interna de la percepción a la que cuelga
    dias: int
    tipo_horas: str  # c_TipoHoras: 01 dobles, 02 triples, 03 simples
    horas: int
    importe: Decimal


@dataclass(frozen=True)
class IncapacidadCfdi:
    """Nodo `Incapacidad`. `importe` sólo si hay deducción 006 o percepción 014."""

    dias: int
    tipo: str  # c_TipoIncapacidad: 01 riesgo de trabajo, 02 enfermedad general, 03 maternidad
    importe: Decimal | None = None


@dataclass(frozen=True)
class SeparacionCfdi:
    """Nodo `SeparacionIndemnizacion` (percepciones 022, 023 y 025)."""

    total_pagado: Decimal
    anios_servicio: int
    ultimo_sueldo_mensual: Decimal
    ingreso_acumulable: Decimal
    ingreso_no_acumulable: Decimal


@dataclass(frozen=True)
class JubilacionCfdi:
    """Nodo `JubilacionPensionRetiro` (039 una exhibición; 044 parcialidades)."""

    ingreso_acumulable: Decimal
    ingreso_no_acumulable: Decimal
    total_una_exhibicion: Decimal | None = None
    total_parcialidad: Decimal | None = None
    monto_diario: Decimal | None = None


@dataclass(frozen=True)
class ExtrasNomina:
    """Los nodos opcionales del complemento que el recibo no trae por sí solo (P4-11)."""

    horas_extra: tuple[HorasExtraCfdi, ...] = field(default_factory=tuple)
    incapacidades: tuple[IncapacidadCfdi, ...] = field(default_factory=tuple)
    separacion: SeparacionCfdi | None = None
    jubilacion: JubilacionCfdi | None = None


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


def _nodo_percepciones(
    nomina: ET.Element, recibo: Recibo, extras: ExtrasNomina | None = None
) -> None:
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
    extras = extras or ExtrasNomina()
    for p in recibo.percepciones:
        percepcion = _sub(
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
        if p.tipo == "019":
            for h in extras.horas_extra:
                if h.clave_percepcion == p.clave:
                    _sub(percepcion, f"{{{NS_NOMINA}}}HorasExtra", {
                        "Dias": str(h.dias), "TipoHoras": h.tipo_horas,
                        "HorasExtra": str(h.horas), "ImportePagado": _importe(h.importe),
                    })
    if extras.jubilacion is not None:
        j = extras.jubilacion
        _sub(nodo, f"{{{NS_NOMINA}}}JubilacionPensionRetiro", {
            "TotalUnaExhibicion": _importe(j.total_una_exhibicion)
            if j.total_una_exhibicion is not None else "",
            "TotalParcialidad": _importe(j.total_parcialidad)
            if j.total_parcialidad is not None else "",
            "MontoDiario": _importe(j.monto_diario) if j.monto_diario is not None else "",
            "IngresoAcumulable": _importe(j.ingreso_acumulable),
            "IngresoNoAcumulable": _importe(j.ingreso_no_acumulable),
        })
    if extras.separacion is not None:
        sep = extras.separacion
        _sub(nodo, f"{{{NS_NOMINA}}}SeparacionIndemnizacion", {
            "TotalPagado": _importe(sep.total_pagado),
            "NumAñosServicio": str(sep.anios_servicio),
            "UltimoSueldoMensOrd": _importe(sep.ultimo_sueldo_mensual),
            "IngresoAcumulable": _importe(sep.ingreso_acumulable),
            "IngresoNoAcumulable": _importe(sep.ingreso_no_acumulable),
        })


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


def _nodo_incapacidades(nomina: ET.Element, extras: ExtrasNomina | None) -> None:
    if extras is None or not extras.incapacidades:
        return
    nodo = ET.SubElement(nomina, f"{{{NS_NOMINA}}}Incapacidades")
    for i in extras.incapacidades:
        _sub(nodo, f"{{{NS_NOMINA}}}Incapacidad", {
            "DiasIncapacidad": str(i.dias), "TipoIncapacidad": i.tipo,
            "ImporteMonetario": _importe(i.importe) if i.importe is not None else "",
        })
