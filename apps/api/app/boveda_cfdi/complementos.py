"""
Conceptos, CFDI relacionados y complementos (pagos 1.0/2.0, nómina 1.2) del CFDI.

Salieron de `parser.py` en P6-05 (tope de 300 líneas), sin cambiar comportamiento.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.boveda_cfdi.xml_base import NS_NOMINA12, NS_PAGOS, _attrs, _dec, _hijo, _hijos


def _conceptos(raiz: Any, ns: str) -> list[dict[str, Any]]:
    salida = []
    for c in _hijos(raiz, ns, "Conceptos/Concepto"):
        concepto: dict[str, Any] = _attrs(
            c, "ClaveProdServ", "NoIdentificacion", "Cantidad", "ClaveUnidad", "Unidad",
            "Descripcion", "ValorUnitario", "Importe", "Descuento", "ObjetoImp",
        )
        imp = _hijo(c, ns, "Impuestos")
        tras = [_attrs(n, "Base", "Impuesto", "TipoFactor", "TasaOCuota", "Importe")
                for n in _hijos(imp, ns, "Traslados/Traslado")]
        ret = [_attrs(n, "Base", "Impuesto", "TipoFactor", "TasaOCuota", "Importe")
               for n in _hijos(imp, ns, "Retenciones/Retencion")]
        if tras:
            concepto["traslados"] = tras
        if ret:
            concepto["retenciones"] = ret
        salida.append(concepto)
    return salida


def _relacionados(raiz: Any, ns: str) -> list[dict[str, Any]]:
    """CfdiRelacionados: en 3.3 hay uno solo; en 4.0 puede repetirse por TipoRelacion."""
    salida = []
    for grupo in _hijos(raiz, ns, "CfdiRelacionados"):
        uuids = [n.get("UUID", "").upper() for n in _hijos(grupo, ns, "CfdiRelacionado")]
        salida.append({"tipo_relacion": grupo.get("TipoRelacion", ""), "uuids": uuids})
    return salida


def _complemento_pagos(complemento: Any) -> dict[str, Any] | None:
    """Recepción de pagos 1.0 o 2.0: cada pago con sus documentos relacionados."""
    if complemento is None:
        return None
    for version, ns in NS_PAGOS.items():
        nodo = complemento.find(f"{{{ns}}}Pagos")
        if nodo is None:
            continue
        pagos = []
        for p in _hijos(nodo, ns, "Pago"):
            documentos = []
            for d in _hijos(p, ns, "DoctoRelacionado"):
                doc = _attrs(d, "IdDocumento", "Serie", "Folio", "MonedaDR", "EquivalenciaDR",
                             "TipoCambioDR", "MetodoDePagoDR", "NumParcialidad",
                             "ImpSaldoAnt", "ImpPagado", "ImpSaldoInsoluto", "ObjetoImpDR")
                if "IdDocumento" in doc:
                    doc["IdDocumento"] = doc["IdDocumento"].upper()
                documentos.append(doc)
            pagos.append({
                **_attrs(p, "FechaPago", "FormaDePagoP", "MonedaP", "TipoCambioP", "Monto",
                         "NumOperacion"),
                "documentos": documentos,
            })
        totales = _attrs(
            nodo.find(f"{{{ns}}}Totales"),
            "TotalRetencionesIVA", "TotalRetencionesISR", "TotalRetencionesIEPS",
            "TotalTrasladosBaseIVA16", "TotalTrasladosImpuestoIVA16",
            "TotalTrasladosBaseIVA8", "TotalTrasladosImpuestoIVA8",
            "TotalTrasladosBaseIVA0", "TotalTrasladosImpuestoIVA0",
            "TotalTrasladosBaseIVAExento", "MontoTotalPagos",
        )
        uuids = sorted({d["IdDocumento"] for p in pagos for d in p["documentos"]
                        if d.get("IdDocumento")})
        monto = sum((_dec(p.get("Monto")) for p in pagos), Decimal("0"))
        return {
            "version": version,
            "pagos": pagos,
            "totales": totales,
            "uuids_relacionados": uuids,
            "monto_total": str(monto),
        }
    return None


def _complemento_nomina(complemento: Any) -> dict[str, Any] | None:
    """Nómina 1.2: totales de percepciones, deducciones, otros pagos e ISR retenido."""
    if complemento is None:
        return None
    nodo = complemento.find(f"{{{NS_NOMINA12}}}Nomina")
    if nodo is None:
        return None
    ns = NS_NOMINA12
    deducciones = _hijo(nodo, ns, "Deducciones")
    isr = sum((_dec(d.get("Importe")) for d in _hijos(deducciones, ns, "Deduccion")
               if d.get("TipoDeduccion") == "002"), Decimal("0"))
    # Por tipo (c_TipoDeduccion / c_TipoOtroPago): la póliza de nómina separa IMSS obrero,
    # otras deducciones, subsidio, viáticos y reintegros en cuentas propias (revisión P2).
    deducciones_por_tipo: dict[str, Decimal] = {}
    for d in _hijos(deducciones, ns, "Deduccion"):
        tipo = d.get("TipoDeduccion", "")
        deducciones_por_tipo[tipo] = deducciones_por_tipo.get(tipo, Decimal("0")) + \
            _dec(d.get("Importe"))
    otros_por_tipo: dict[str, Decimal] = {}
    for o in _hijos(nodo, ns, "OtrosPagos/OtroPago"):
        tipo = o.get("TipoOtroPago", "")
        otros_por_tipo[tipo] = otros_por_tipo.get(tipo, Decimal("0")) + _dec(o.get("Importe"))
    receptor = _hijo(nodo, ns, "Receptor")
    subsidio = sum(
        (_dec(s.get("SubsidioCausado"))
         for s in _hijos(nodo, ns, "OtrosPagos/OtroPago/SubsidioAlEmpleo")),
        Decimal("0"),
    )
    return {
        "version": nodo.get("Version", ""),
        **_attrs(nodo, "TipoNomina", "FechaPago", "FechaInicialPago", "FechaFinalPago",
                 "NumDiasPagados", "TotalPercepciones", "TotalDeducciones", "TotalOtrosPagos"),
        "percepciones": _attrs(_hijo(nodo, ns, "Percepciones"), "TotalSueldos",
                               "TotalSeparacionIndemnizacion", "TotalJubilacionPensionRetiro",
                               "TotalGravado", "TotalExento"),
        "deducciones": _attrs(deducciones, "TotalOtrasDeducciones", "TotalImpuestosRetenidos"),
        "isr_retenido": str(isr),
        "deducciones_por_tipo": {k: str(v) for k, v in sorted(deducciones_por_tipo.items())},
        "otros_pagos_por_tipo": {k: str(v) for k, v in sorted(otros_por_tipo.items())},
        "subsidio_causado": str(subsidio),
        "receptor": _attrs(receptor, "NumEmpleado", "Curp", "NumSeguridadSocial",
                           "PeriodicidadPago", "TipoRegimen"),
        "registro_patronal": (_hijo(nodo, ns, "Emisor").get("RegistroPatronal", "")
                              if _hijo(nodo, ns, "Emisor") is not None else ""),
    }
