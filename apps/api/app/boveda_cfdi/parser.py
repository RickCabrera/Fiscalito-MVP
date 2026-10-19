"""
Parser de CFDI para la bóveda (plan P, P0-03).

Lee CFDI 3.3 y 4.0 de cualquier tipo (I, E, P, N, T) con su timbre fiscal digital, el
complemento de recepción de pagos 1.0 y 2.0 y el de nómina 1.2. No valida sellos ni contra el
XSD: la bóveda guarda lo que el SAT timbró; la validez la confirma el estatus del SAT (P1-03).

SEGURIDAD
---------
El XML llega de fuera. El parser de lxml se configura sin resolver entidades, sin red y sin
árboles gigantes: un XML con DTD hostil (billion laughs, XXE) se rechaza en vez de expandirse.

QUÉ SE DEVUELVE
---------------
`CfdiLeido`: las columnas de `app.modelos.cfdi.Comprobante` ya tipadas (`Decimal`, `datetime`)
más `datos` (JSON serializable) con conceptos, impuestos por tasa y los complementos.
Los importes de columna se redondean a centavos; los de `datos` se guardan como texto tal
cual vienen en el XML, para no perder precisión que el SAT sí aceptó.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from lxml import etree

NS_CFDI = {"3.3": "http://www.sat.gob.mx/cfd/3", "4.0": "http://www.sat.gob.mx/cfd/4"}
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"
NS_PAGOS = {"1.0": "http://www.sat.gob.mx/Pagos", "2.0": "http://www.sat.gob.mx/Pagos20"}
NS_NOMINA12 = "http://www.sat.gob.mx/nomina12"

TIPOS = {"I", "E", "P", "N", "T"}
# Catálogo c_Impuesto del SAT.
ISR, IVA, IEPS = "001", "002", "003"

_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=False
)
CENTAVO = Decimal("0.01")


_RE_UUID = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}")


class CfdiInvalido(ValueError):
    """El archivo no es un CFDI timbrado que la bóveda pueda guardar."""


@dataclass
class CfdiLeido:
    """Lo que la bóveda necesita de un CFDI."""

    uuid: str
    version: str
    tipo: str
    fecha: datetime
    fecha_timbrado: datetime | None
    serie: str
    folio: str
    rfc_emisor: str
    nombre_emisor: str
    rfc_receptor: str
    nombre_receptor: str
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    moneda: str
    tipo_cambio: Decimal | None
    metodo_pago: str
    forma_pago: str
    uso_cfdi: str
    iva_trasladado: Decimal
    iva_retenido: Decimal
    isr_retenido: Decimal
    ieps: Decimal
    datos: dict[str, Any] = field(default_factory=dict)


# ── utilidades ──


def _dec(valor: str | None) -> Decimal:
    if valor is None or str(valor).strip() == "":
        return Decimal("0")
    try:
        return Decimal(str(valor).strip())
    except InvalidOperation as e:
        raise CfdiInvalido(f"Importe inválido: {valor!r}") from e


def _centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _fecha(valor: str | None, campo: str) -> datetime:
    if not valor:
        raise CfdiInvalido(f"Falta {campo}.")
    try:
        # Sin zona: el CFDI expresa la hora local del lugar de expedición.
        return datetime.fromisoformat(valor.strip()[:19])
    except ValueError as e:
        raise CfdiInvalido(f"{campo} inválida: {valor!r}") from e


def _hijo(nodo: Any, ns: str, nombre: str) -> Any:
    return nodo.find(f"{{{ns}}}{nombre}") if nodo is not None else None


def _hijos(nodo: Any, ns: str, ruta: str) -> list[Any]:
    if nodo is None:
        return []
    partes = "/".join(f"{{{ns}}}{p}" for p in ruta.split("/"))
    return list(nodo.findall(partes))


def _attrs(nodo: Any, *nombres: str) -> dict[str, str]:
    """Los atributos pedidos que traiga el nodo, como texto."""
    if nodo is None:
        return {}
    return {n: nodo.get(n) for n in nombres if nodo.get(n) is not None}


# ── lectura ──


def leer_xml(contenido: bytes) -> etree._Element:
    """Parsea bytes a un árbol, con el parser endurecido."""
    if not contenido or not contenido.strip():
        raise CfdiInvalido("El archivo está vacío.")
    try:
        raiz = etree.fromstring(contenido, parser=_PARSER)
    except etree.XMLSyntaxError as e:
        raise CfdiInvalido(f"No es un XML válido: {e.msg}") from e
    # Un CFDI nunca trae DTD. Si viene una, es un XML armado a mano o un ataque de
    # entidades: se rechaza en vez de confiar en que el parser no la expanda.
    if raiz.getroottree().docinfo.doctype:
        raise CfdiInvalido("El XML trae una declaración DOCTYPE; un CFDI no la lleva.")
    return raiz


def parsear_cfdi(contenido: bytes) -> CfdiLeido:
    """Lee un CFDI 3.3/4.0 timbrado. Lanza `CfdiInvalido` con la razón si no lo es."""
    raiz = leer_xml(contenido)
    qname = etree.QName(raiz)
    if qname.localname != "Comprobante":
        raise CfdiInvalido("El XML no es un CFDI (la raíz no es Comprobante).")
    version = raiz.get("Version") or raiz.get("version") or ""
    ns = NS_CFDI.get(version)
    if ns is None or qname.namespace != ns:
        raise CfdiInvalido(
            f"Versión de CFDI no soportada: {version or 'sin versión'} (se aceptan 3.3 y 4.0)."
        )

    tipo = (raiz.get("TipoDeComprobante") or "").upper()
    if tipo not in TIPOS:
        raise CfdiInvalido(f"TipoDeComprobante inválido: {tipo!r}.")

    complemento = _hijo(raiz, ns, "Complemento")
    timbre = complemento.find(f"{{{NS_TFD}}}TimbreFiscalDigital") if complemento is not None \
        else None
    if timbre is None or not timbre.get("UUID"):
        raise CfdiInvalido("El CFDI no está timbrado (falta el TimbreFiscalDigital con UUID).")

    emisor = _hijo(raiz, ns, "Emisor")
    receptor = _hijo(raiz, ns, "Receptor")
    if emisor is None or receptor is None or not emisor.get("Rfc") or not receptor.get("Rfc"):
        raise CfdiInvalido("Faltan el RFC del emisor o del receptor.")

    impuestos = _hijo(raiz, ns, "Impuestos")
    traslados = _hijos(impuestos, ns, "Traslados/Traslado")
    retenciones = _hijos(impuestos, ns, "Retenciones/Retencion")

    def suma(nodos: list[Any], impuesto: str) -> Decimal:
        return sum((_dec(n.get("Importe")) for n in nodos if n.get("Impuesto") == impuesto),
                   Decimal("0"))

    iva_trasladado = suma(traslados, IVA)
    ieps = suma(traslados, IEPS)
    iva_retenido = suma(retenciones, IVA)
    isr_retenido = suma(retenciones, ISR)

    datos: dict[str, Any] = {
        "conceptos": _conceptos(raiz, ns),
        "impuestos": {
            "traslados": [_attrs(n, "Base", "Impuesto", "TipoFactor", "TasaOCuota", "Importe")
                          for n in traslados],
            "retenciones": [_attrs(n, "Impuesto", "Importe") for n in retenciones],
            **_attrs(impuestos, "TotalImpuestosTrasladados", "TotalImpuestosRetenidos"),
        },
        "timbre": _attrs(timbre, "Version", "UUID", "FechaTimbrado", "RfcProvCertif",
                         "NoCertificadoSAT"),
        "emisor": _attrs(emisor, "Rfc", "Nombre", "RegimenFiscal"),
        "receptor": _attrs(receptor, "Rfc", "Nombre", "RegimenFiscalReceptor",
                           "DomicilioFiscalReceptor", "UsoCFDI"),
        "cfdi_relacionados": _relacionados(raiz, ns),
        "lugar_expedicion": raiz.get("LugarExpedicion", ""),
    }

    pagos = _complemento_pagos(complemento)
    if pagos:
        datos["pagos"] = pagos
    nomina = _complemento_nomina(complemento)
    if nomina:
        datos["nomina"] = nomina
        # En nómina el ISR retenido viaja en las deducciones, no en Impuestos (CFDI 4.0
        # de nómina no lleva nodo Impuestos). TipoDeduccion 002 = ISR (c_TipoDeduccion).
        if isr_retenido == 0:
            isr_retenido = _dec(nomina.get("isr_retenido"))

    tipo_cambio = raiz.get("TipoCambio")
    uuid = (timbre.get("UUID") or "").strip().upper()
    # El UUID va a rutas de almacenamiento y a encabezados HTTP: se exige su formato.
    if not _RE_UUID.fullmatch(uuid):
        raise CfdiInvalido(f"UUID del timbre inválido: {uuid!r}")
    return CfdiLeido(
        uuid=uuid,
        version=version,
        tipo=tipo,
        fecha=_fecha(raiz.get("Fecha"), "Fecha"),
        fecha_timbrado=_fecha(timbre.get("FechaTimbrado"), "FechaTimbrado")
        if timbre.get("FechaTimbrado") else None,
        serie=raiz.get("Serie", ""),
        folio=raiz.get("Folio", ""),
        rfc_emisor=emisor.get("Rfc").strip().upper(),
        nombre_emisor=emisor.get("Nombre", ""),
        rfc_receptor=receptor.get("Rfc").strip().upper(),
        nombre_receptor=receptor.get("Nombre", ""),
        subtotal=_centavos(_dec(raiz.get("SubTotal"))),
        descuento=_centavos(_dec(raiz.get("Descuento"))),
        total=_centavos(_dec(raiz.get("Total"))),
        moneda=raiz.get("Moneda", "MXN"),
        tipo_cambio=_dec(tipo_cambio) if tipo_cambio else None,
        metodo_pago=raiz.get("MetodoPago", ""),
        forma_pago=raiz.get("FormaPago", ""),
        uso_cfdi=receptor.get("UsoCFDI", ""),
        iva_trasladado=_centavos(iva_trasladado),
        iva_retenido=_centavos(iva_retenido),
        isr_retenido=_centavos(isr_retenido),
        ieps=_centavos(ieps),
        datos=datos,
    )


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
        "subsidio_causado": str(subsidio),
        "receptor": _attrs(receptor, "NumEmpleado", "Curp", "NumSeguridadSocial",
                           "PeriodicidadPago", "TipoRegimen"),
        "registro_patronal": (_hijo(nodo, ns, "Emisor").get("RegistroPatronal", "")
                              if _hijo(nodo, ns, "Emisor") is not None else ""),
    }
