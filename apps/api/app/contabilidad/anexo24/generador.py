"""
Contabilidad electrónica (P2-07): XML del Anexo 24 de la RMF, versión 1.3.

Fuente de la estructura: los XSD oficiales 1.3 versionados en `sat/esquemas/` (ver
`esquemas.py`). Cada XML se valida contra su XSD antes de entregarse; uno que no valida no
se empaqueta.

DOCUMENTOS
----------
- `catalogo` (CatalogoCuentas): todas las cuentas del cliente con su código agrupador,
  nivel, naturaleza (D/A) y `SubCtaDe` = número de la cuenta padre.
- `balanza` (BalanzaComprobacion): las cuentas con saldo o movimiento del mes (todos los
  niveles, como la balanza de P2-04). `TipoEnvio` N (normal) o C (complementaria, exige
  `FechaModBal`).
- `polizas` (PolizasPeriodo): las pólizas activas del mes con sus transacciones y, en cada
  transacción con UUID, el nodo `CompNal` (UUID, RFC de la contraparte, monto total del CFDI).
  Sólo se entrega a solicitud del SAT: `TipoSolicitud` AF (acto de fiscalización) o FC
  (fiscalización compulsa) exigen `NumOrden`; DE (devolución) o CO (compensación) exigen
  `NumTramite`.
- `auxiliar_cuentas` (AuxiliarCtas) y `auxiliar_folios` (AuxiliarFolios / RepAuxFol): mismas
  reglas de solicitud que las pólizas.

SALDOS SEGÚN LA NATURALEZA
--------------------------
El Anexo 24 pide SaldoIni/SaldoFin "de acuerdo a la naturaleza de la cuenta": positivo en su
sentido natural, negativo si quedó al revés. Internamente todo es deudor positivo, así que
para las cuentas acreedoras se invierte el signo.

NOMBRE DEL ARCHIVO
------------------
RFC + AAAA + MM + sufijo: CT (catálogo), BN/BC (balanza normal/complementaria), PL
(pólizas), XC (auxiliar de cuentas), XF (auxiliar de folios). El ZIP lleva el mismo nombre
con `.zip` y adentro el `.xml`. Fuente: Anexo 24 RMF, apartado de "Envío de la contabilidad
electrónica" (nomenclatura de archivos); coincide con `satcfdi/accounting/contabilidad.py`
(`filename`). # FUENTE POR CONFIRMAR: el texto vigente del Anexo 24 no se pudo descargar del
DOF desde este entorno; la nomenclatura se tomó de la implementación de referencia citada.

SELLO
-----
Opcional en el XSD. Si se pide, se calcula la cadena original con el XSLT OFICIAL del SAT
(`*_1_2.xslt` + `utilerias.xslt`), se firma con la e.firma del contribuyente (RSA PKCS#1
v1.5) y se ponen `Sello`, `noCertificado` y `Certificado`.
# POR CONFIRMAR: el algoritmo del sello. Se usa SHA-256 por default, igual que
# `satcfdi` (`CFDI.sign` → `sign_sha256`) para estos mismos documentos; versiones anteriores
# del instructivo hablaban de SHA-1. Es un parámetro (`algoritmo`) para cambiarlo sin código.
# El portal del SAT acepta los XML sin sello (el envío se firma con la e.firma en el portal).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contabilidad import balanza, catalogo, polizas
from app.contabilidad.anexo24 import esquemas
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, Poliza
from app.modelos.nucleo import Cliente

XSI = "http://www.w3.org/2001/XMLSchema-instance"
RE_RFC = re.compile(r"^[A-ZÑ&]{3,4}[0-9]{2}[0-1][0-9][0-3][0-9][A-Z0-9]{3}$")
RE_UUID = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-"
                     r"[a-fA-F0-9]{12}$")
RE_NUM_ORDEN = re.compile(r"^[A-Z]{3}[0-9]{7}/[0-9]{2}$")
RE_NUM_TRAMITE = re.compile(r"^[A-Z]{2}[0-9]{12}$")
SOLICITUDES = ("AF", "FC", "DE", "CO")
CERO = Decimal("0")


@dataclass
class Solicitud:
    """Parámetros del documento a generar."""

    documento: str
    anio: int
    mes: int
    tipo_envio: str = "N"
    fecha_mod_bal: date | None = None
    tipo_solicitud: str = ""
    num_orden: str = ""
    num_tramite: str = ""


@dataclass
class Documento:
    nombre: str  # sin extensión
    xml: bytes
    errores: list[str]
    advertencias: list[str] = field(default_factory=list)
    sellado: bool = False

    @property
    def valido(self) -> bool:
        return not self.errores


def _imp(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01'))}"


def _texto(v: str, n: int, defecto: str) -> str:
    t = re.sub(r"\s+", " ", (v or "")).strip()
    return (t or defecto)[:n]


def _natural(c: CuentaContable, saldo: Decimal) -> Decimal:
    return saldo if c.naturaleza == "deudora" else -saldo


def _periodo(anio: int, mes: int) -> tuple[date, date]:
    if not 1 <= mes <= 12:
        raise FiscalAgentError("El mes va de 1 a 12. # POR CONFIRMAR: la balanza de cierre "
                               "(mes 13) depende del cierre de ejercicio (P2-08).", 422)
    if not 2015 <= anio <= 2100:
        raise FiscalAgentError("El año debe ser 2015 o posterior (XSD del Anexo 24).", 422)
    fin = date(anio + (mes == 12), mes % 12 + 1, 1)
    return date(anio, mes, 1), date.fromordinal(fin.toordinal() - 1)


def _validar_solicitud(s: Solicitud) -> None:
    if s.documento in ("polizas", "auxiliar_cuentas", "auxiliar_folios"):
        if s.tipo_solicitud not in SOLICITUDES:
            raise FiscalAgentError("Las pólizas y los auxiliares se entregan a solicitud: "
                                   "indica TipoSolicitud AF, FC, DE o CO.", 422)
        if s.tipo_solicitud in ("AF", "FC") and not RE_NUM_ORDEN.match(s.num_orden):
            raise FiscalAgentError("AF y FC requieren NumOrden con formato AAA0000000/00.",
                                   422)
        if s.tipo_solicitud in ("DE", "CO") and not RE_NUM_TRAMITE.match(s.num_tramite):
            raise FiscalAgentError("DE y CO requieren NumTramite con formato AA000000000000.",
                                   422)
    if s.documento == "balanza":
        if s.tipo_envio not in ("N", "C"):
            raise FiscalAgentError("TipoEnvio es N (normal) o C (complementaria).", 422)
        if s.tipo_envio == "C" and s.fecha_mod_bal is None:
            raise FiscalAgentError("La balanza complementaria exige la fecha de la "
                                   "modificación (FechaModBal).", 422)


def nombre_archivo(rfc: str, s: Solicitud) -> str:
    t = esquemas.TIPOS[s.documento]
    sufijo = t.sufijo + (s.tipo_envio if s.documento == "balanza" else "")
    return f"{rfc}{s.anio:04d}{s.mes:02d}{sufijo}"


def _raiz(s: Solicitud, rfc: str) -> etree._Element:
    t = esquemas.TIPOS[s.documento]
    raiz = etree.Element(f"{{{t.ns}}}{t.raiz}", nsmap={t.prefijo: t.ns, "xsi": XSI})
    raiz.set(f"{{{XSI}}}schemaLocation", t.schema_location)
    raiz.set("Version", "1.3")
    raiz.set("RFC", rfc)
    raiz.set("Mes", f"{s.mes:02d}")
    raiz.set("Anio", str(s.anio))
    if s.documento == "balanza":
        raiz.set("TipoEnvio", s.tipo_envio)
        if s.tipo_envio == "C" and s.fecha_mod_bal:
            raiz.set("FechaModBal", s.fecha_mod_bal.isoformat())
    if s.documento in ("polizas", "auxiliar_cuentas", "auxiliar_folios"):
        raiz.set("TipoSolicitud", s.tipo_solicitud)
        if s.num_orden:
            raiz.set("NumOrden", s.num_orden)
        if s.num_tramite:
            raiz.set("NumTramite", s.num_tramite)
    return raiz


def _hijo(padre: etree._Element, ns: str, nombre: str, **attrs: str) -> etree._Element:
    e = etree.SubElement(padre, f"{{{ns}}}{nombre}")
    for k, v in attrs.items():
        if v is not None and v != "":
            e.set(k, v)
    return e


# ── documentos ──


def _catalogo(db: Session, cliente: Cliente, raiz: etree._Element, ns: str,
              adv: list[str]) -> None:
    cuentas = catalogo.cuentas(db, cliente)
    por_id = {c.id: c for c in cuentas}
    for c in sorted(cuentas, key=lambda x: x.numero):
        padre = por_id.get(c.padre_id) if c.padre_id else None
        _hijo(raiz, ns, "Ctas", CodAgrup=c.codigo_agrupador, NumCta=c.numero[:100],
              Desc=_texto(c.nombre, 400, c.numero), SubCtaDe=padre.numero if padre else "",
              Nivel=str(c.nivel), Natur="D" if c.naturaleza == "deudora" else "A")
    if not cuentas:
        adv.append("El cliente no tiene catálogo de cuentas.")


def _balanza(db: Session, cliente: Cliente, raiz: etree._Element, ns: str, desde: date,
             hasta: date, adv: list[str]) -> None:
    b = balanza.balanza(db, cliente, desde, hasta, solo="con_saldo_o_movimiento")
    if not b["cuadra"]:
        adv.append(f"La balanza no cuadra: {b['diferencias']}.")
    por_id = {c.id: c for c in catalogo.cuentas(db, cliente)}
    for r in b["renglones"]:
        c = por_id[r["cuenta_id"]]
        _hijo(raiz, ns, "Ctas", NumCta=c.numero[:100],
              SaldoIni=_imp(_natural(c, Decimal(r["saldo_inicial"]))),
              Debe=_imp(Decimal(r["cargos"])), Haber=_imp(Decimal(r["abonos"])),
              SaldoFin=_imp(_natural(c, Decimal(r["saldo_final"]))))
    if not b["renglones"]:
        adv.append("Sin saldos ni movimientos en el mes.")


def _movimientos_mes(db: Session, cliente: Cliente, desde: date, hasta: date
                     ) -> list[tuple[Poliza, MovimientoPoliza, CuentaContable]]:
    return list(db.execute(
        select(Poliza, MovimientoPoliza, CuentaContable)
        .join(MovimientoPoliza, MovimientoPoliza.poliza_id == Poliza.id)
        .join(CuentaContable, CuentaContable.id == MovimientoPoliza.cuenta_id)
        .where(Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
               Poliza.fecha >= desde, Poliza.fecha <= hasta)
        .order_by(Poliza.fecha, Poliza.tipo, Poliza.numero, MovimientoPoliza.orden)).all())


def _comprobantes(db: Session, cliente: Cliente, uuids: set[str]) -> dict[str, Comprobante]:
    if not uuids:
        return {}
    return {c.uuid: c for c in db.scalars(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.uuid.in_(uuids)))}


def _compnal(comp: Comprobante | None, uuid: str, rfc: str) -> dict[str, str] | None:
    """Atributos del CompNal (o ComprNal), o None si falta un dato obligatorio."""
    if not RE_UUID.match(uuid or ""):
        return None
    if comp is not None:
        rfc = rfc or (comp.rfc_receptor if comp.direccion == "emitido" else comp.rfc_emisor)
    rfc = (rfc or "").upper()
    if not RE_RFC.match(rfc) or comp is None:
        return None
    attrs = {"UUID_CFDI": uuid.upper(), "RFC": rfc, "MontoTotal": _imp(comp.total)}
    if comp.moneda and comp.moneda not in ("MXN", "XXX"):
        attrs["Moneda"] = comp.moneda
        if comp.tipo_cambio:
            attrs["TipCamb"] = f"{comp.tipo_cambio.quantize(Decimal('0.00001'))}"
    return attrs


def _polizas(db: Session, cliente: Cliente, raiz: etree._Element, ns: str, desde: date,
             hasta: date, adv: list[str]) -> None:
    filas = _movimientos_mes(db, cliente, desde, hasta)
    comps = _comprobantes(db, cliente, {m.uuid_cfdi for _p, m, _c in filas if m.uuid_cfdi})
    actual: tuple[int, etree._Element] | None = None
    sin_comp = 0
    for p, m, c in filas:
        if actual is None or actual[0] != p.id:
            nodo = _hijo(raiz, ns, "Poliza", NumUnIdenPol=polizas.folio(p),
                         Fecha=p.fecha.isoformat(), Concepto=_texto(p.concepto, 300,
                                                                    polizas.folio(p)))
            actual = (p.id, nodo)
        t = _hijo(actual[1], ns, "Transaccion", NumCta=c.numero[:100],
                  DesCta=_texto(c.nombre, 100, c.numero),
                  Concepto=_texto(m.concepto or p.concepto, 200, polizas.folio(p)),
                  Debe=_imp(m.cargo), Haber=_imp(m.abono))
        if m.uuid_cfdi:
            attrs = _compnal(comps.get(m.uuid_cfdi.upper()), m.uuid_cfdi, m.rfc_tercero)
            if attrs:
                _hijo(t, ns, "CompNal", **attrs)
            else:
                sin_comp += 1
    if sin_comp:
        adv.append(f"{sin_comp} transacciones con UUID sin CompNal (el CFDI no está en la "
                   "bóveda o la contraparte no tiene RFC válido).")
    if not filas:
        adv.append("Sin pólizas activas en el mes.")


def _auxiliar_cuentas(db: Session, cliente: Cliente, raiz: etree._Element, ns: str,
                      desde: date, hasta: date, adv: list[str]) -> None:
    filas = _movimientos_mes(db, cliente, desde, hasta)
    hojas = balanza.totales_por_cuenta(db, cliente, desde, hasta)
    por_cuenta: dict[int, list[tuple[Poliza, MovimientoPoliza]]] = {}
    cuentas: dict[int, CuentaContable] = {}
    for p, m, c in filas:
        por_cuenta.setdefault(c.id, []).append((p, m))
        cuentas[c.id] = c
    for cid in sorted(por_cuenta, key=lambda i: cuentas[i].numero):
        c = cuentas[cid]
        t = hojas.get(cid, balanza.Totales())
        nodo = _hijo(raiz, ns, "Cuenta", NumCta=c.numero[:100],
                     DesCta=_texto(c.nombre, 100, c.numero),
                     SaldoIni=_imp(_natural(c, t.inicial)), SaldoFin=_imp(_natural(c, t.final)))
        for p, m in por_cuenta[cid]:
            _hijo(nodo, ns, "DetalleAux", Fecha=p.fecha.isoformat(),
                  NumUnIdenPol=polizas.folio(p),
                  Concepto=_texto(m.concepto or p.concepto, 200, polizas.folio(p)),
                  Debe=_imp(m.cargo), Haber=_imp(m.abono))
    if not filas:
        adv.append("Sin movimientos en el mes: el XSD exige al menos una cuenta.")


def _auxiliar_folios(db: Session, cliente: Cliente, raiz: etree._Element, ns: str,
                     desde: date, hasta: date, adv: list[str]) -> None:
    filas = _movimientos_mes(db, cliente, desde, hasta)
    comps = _comprobantes(db, cliente, {m.uuid_cfdi for _p, m, _c in filas if m.uuid_cfdi})
    por_poliza: dict[int, tuple[Poliza, dict[str, dict[str, str]]]] = {}
    for p, m, _c in filas:
        if not m.uuid_cfdi:
            continue
        attrs = _compnal(comps.get(m.uuid_cfdi.upper()), m.uuid_cfdi, m.rfc_tercero)
        if attrs:
            por_poliza.setdefault(p.id, (p, {}))[1].setdefault(attrs["UUID_CFDI"], attrs)
    for p, uuids in por_poliza.values():
        nodo = _hijo(raiz, ns, "DetAuxFol", NumUnIdenPol=polizas.folio(p),
                     Fecha=p.fecha.isoformat())
        for attrs in uuids.values():
            comp = comps.get(attrs["UUID_CFDI"])
            extra = {}
            if comp and comp.forma_pago and re.fullmatch(r"\d{2}", comp.forma_pago):
                forma = comp.forma_pago if comp.forma_pago in {
                    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12",
                    "13", "14", "15", "16", "17", "98", "99"} else "99"
                extra["MetPagoAux"] = forma
            _hijo(nodo, ns, "ComprNal", **{k: v for k, v in attrs.items()}, **extra)
    if not por_poliza:
        adv.append("Ninguna póliza del mes trae CFDI con datos completos.")


CONSTRUCTORES = {
    "catalogo": lambda db, cl, r, ns, d, h, a: _catalogo(db, cl, r, ns, a),
    "balanza": _balanza,
    "polizas": _polizas,
    "auxiliar_cuentas": _auxiliar_cuentas,
    "auxiliar_folios": _auxiliar_folios,
}


def generar(db: Session, cliente: Cliente, s: Solicitud, *, firmante: Any = None,
            algoritmo: str = "sha256") -> Documento:
    """Arma, (opcionalmente) sella y valida contra el XSD un documento del Anexo 24."""
    if s.documento not in esquemas.TIPOS:
        raise FiscalAgentError(f"Documento inválido; usa uno de {', '.join(esquemas.TIPOS)}.",
                               422)
    rfc = (cliente.rfc or "").strip().upper()
    if not RE_RFC.match(rfc):
        raise FiscalAgentError("Captura un RFC válido del cliente antes de generar la "
                               "contabilidad electrónica.", 422)
    desde, hasta = _periodo(s.anio, s.mes)
    _validar_solicitud(s)
    raiz = _raiz(s, rfc)
    adv: list[str] = []
    CONSTRUCTORES[s.documento](db, cliente, raiz, esquemas.TIPOS[s.documento].ns, desde,
                               hasta, adv)
    sellado = False
    if firmante is not None:
        if (firmante.rfc or "").upper() != rfc:
            raise FiscalAgentError("La e.firma cargada no es del RFC del cliente.", 422)
        cadena = esquemas.cadena_original(s.documento, raiz)
        raiz.set("Sello", firmante.firmar_base64(cadena.encode("utf-8"), algoritmo))
        raiz.set("noCertificado", firmante.numero_certificado)
        raiz.set("Certificado", firmante.certificado_base64)
        sellado = True
    errores = esquemas.validar(s.documento, raiz)
    xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")
    return Documento(nombre_archivo(rfc, s), xml, errores, adv, sellado)


def empaquetar(doc: Documento) -> bytes:
    """ZIP con el nombre que pide el SAT y el XML adentro."""
    if not doc.valido:
        raise FiscalAgentError("El XML no valida contra el XSD; corrige antes de descargar.",
                               422)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{doc.nombre}.xml", doc.xml)
    return salida.getvalue()


INSTRUCCIONES_PORTAL = (
    "El SAT no tiene una API para recibir la contabilidad electrónica: se sube en el portal.",
    "1. Entra a sat.gob.mx → Empresas/Personas → Contabilidad electrónica → Envío de "
    "archivos, con la e.firma del contribuyente.",
    "2. Selecciona el ZIP descargado aquí (un ZIP por documento; el nombre ya trae RFC, "
    "año, mes y tipo).",
    "3. Confirma y firma el envío con la e.firma. El portal valida el XML contra el mismo "
    "XSD que aquí y emite el acuse de recepción (y después el de aceptación o rechazo).",
    "4. Guarda los acuses: el de aceptación es la evidencia del cumplimiento.",
    "Plazos (regla 2.8.1.7 RMF, POR CONFIRMAR para el ejercicio vigente): catálogo cuando "
    "cambie, balanza a más tardar el día 3 del segundo mes posterior (PM) o el 5 (PF); "
    "pólizas y auxiliares sólo cuando el SAT los solicite.",
)
