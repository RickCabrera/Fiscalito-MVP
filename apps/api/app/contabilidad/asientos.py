"""
Esquemas de asiento de las pólizas automáticas (P2-03). Contabilidad, no cálculo de impuesto:
cada importe sale del CFDI (columnas y `datos` del parser de la bóveda); aquí sólo se decide
a qué cuenta y de qué lado va.

CUADRE POR CONSTRUCCIÓN
-----------------------
La contraparte (clientes o proveedores) no se copia del `Total` del CFDI: se calcula como
base + IVA + IEPS − retenciones, con los importes de columna. Así Σ cargos = Σ abonos siempre,
aunque el XML traiga un impuesto que el parser no lee (impuestos locales). La diferencia
contra el `Total` se guarda en `Poliza.diferencia` y se enseña, en vez de esconderla en un
renglón de ajuste. Las asignaciones por concepto (cuenta de gasto, tipo de ingreso) se
redondean a centavos y el residuo de redondeo va al renglón más grande, así que la suma por
grupo es exactamente la de columna.

ESQUEMAS (cuentas por rol de `config.ROLES`)
--------------------------------------------
Factura emitida (I):   Cargo clientes = base + IVA + IEPS − retenciones
                       Abono ingresos (tasa general / 0 % / exentos, por concepto) = base
                       Abono IVA trasladado: PUE → cobrado (208.01); PPD → no cobrado (209.01)
                       Abono IEPS trasladado (igual que IVA)
                       Cargo IVA/ISR que nos retuvo el cliente (113.01 / 113.02)
                       PUE con forma de pago que mueve dinero: Cargo bancos/caja, Abono clientes.
Factura recibida (I):  Cargo gasto/costo/activo por concepto (reglas) = base (+ IEPS)
                       Cargo IVA acreditable: PUE → pagado (118.01); PPD → pendiente (119.01).
                         El IVA de un concepto no deducible va a la misma cuenta no deducible.
                       Abono IVA retenido por enterar (216.10) y ISR retenido (216.04 servicios
                         profesionales; 216.03 si un concepto es arrendamiento de inmuebles)
                       Abono proveedores = base + IVA + IEPS − retenciones
                       PUE con forma de pago que mueve dinero: Cargo proveedores, Abono bancos.
Nota de crédito (E):   El esquema de la factura con cargos y abonos invertidos; en las emitidas
                       la cuenta de ingresos se sustituye por devoluciones sobre ventas (402.01).
Pago (P):              Por cada pago: Cargo bancos (forma de pago) = Monto; por documento
                       Abono clientes = ImpPagado (emitido). Recibido: Cargo proveedores, Abono
                       bancos. IVA efectivamente cobrado/pagado: traspaso de la parte
                       proporcional (ImpPagado / Total del documento) del IVA pendiente de la
                       factura PPD: Cargo 209.01 / Abono 208.01 (cobrado) o Cargo 118.01 /
                       Abono 119.01 (pagado). Lo pendiente se toma de la póliza de la factura
                       si existe (respeta el IVA que se mandó a no deducibles); si no, del CFDI
                       en la bóveda; si tampoco está, de los Totales del complemento 2.0.
Nómina (N emitida):    Cargo sueldos (o asimilados) = TotalPercepciones; Cargo otros pagos
                       (110.01 subsidio) = TotalOtrosPagos; Abono ISR retenido (216.01/216.02);
                       Abono otras deducciones (216.11); Abono bancos = neto.

MONEDA EXTRANJERA
-----------------
Se convierte a MXN con el `TipoCambio` del CFDI (o `TipoCambioP` del pago). Sin tipo de
cambio la póliza no se genera (se reporta). La utilidad o pérdida cambiaria entre la fecha
de la factura y la del pago NO se registra: queda como saldo en clientes/proveedores y se
advierte en la póliza del pago.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.contabilidad.config import TOPE_EFECTIVO, USO_ACTIVO, ConfigEfectiva, regla_aplicable
from app.modelos.cfdi import Comprobante

CERO = Decimal("0")
CENTAVO = Decimal("0.01")
IVA, IEPS = "002", "003"
# c_TipoRegimen 02 sueldos, 03 jubilados, 04 pensionados; 05-11 son asimilados.
REGIMEN_ASIMILADOS = {"05", "06", "07", "08", "09", "10", "11"}
PREFIJO_ARRENDAMIENTO = "801315"  # c_ClaveProdServ: arrendamiento de bienes inmuebles


class NoContabilizable(Exception):
    """El CFDI no genera póliza; el mensaje dice por qué."""


def d(valor: Any) -> Decimal:
    if valor is None or str(valor).strip() == "":
        return CERO
    try:
        return Decimal(str(valor).strip())
    except InvalidOperation:
        return CERO


def c(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass
class Renglon:
    """Un movimiento por número de cuenta (se traduce a `cuenta_id` al guardar)."""

    cuenta: str
    cargo: Decimal = CERO
    abono: Decimal = CERO
    concepto: str = ""
    uuid: str = ""
    rfc: str = ""


@dataclass
class Asiento:
    tipo: str  # ingreso | egreso | diario
    renglones: list[Renglon] = field(default_factory=list)
    diferencia: Decimal = CERO
    advertencias: list[str] = field(default_factory=list)

    def cargo(self, cuenta: str, importe: Decimal, **kw: str) -> None:
        if importe > 0:
            self.renglones.append(Renglon(cuenta, cargo=importe, **kw))
        elif importe < 0:
            self.renglones.append(Renglon(cuenta, abono=-importe, **kw))

    def abono(self, cuenta: str, importe: Decimal, **kw: str) -> None:
        self.cargo(cuenta, -importe, **kw)

    def invertir(self) -> None:
        for r in self.renglones:
            r.cargo, r.abono = r.abono, r.cargo

    @property
    def total_cargos(self) -> Decimal:
        return sum((r.cargo for r in self.renglones), CERO)

    @property
    def total_abonos(self) -> Decimal:
        return sum((r.abono for r in self.renglones), CERO)


def repartir(montos: dict[str, Decimal], objetivo: Decimal) -> dict[str, Decimal]:
    """Redondea cada monto a centavos y deja el residuo en el más grande: Σ = objetivo."""
    if not montos:
        return {}
    salida = {k: c(v) for k, v in montos.items()}
    residuo = objetivo - sum(salida.values(), CERO)
    if residuo:
        mayor = max(salida, key=lambda k: (abs(montos[k]), k))
        salida[mayor] += residuo
    return {k: v for k, v in salida.items() if v != 0}


def factor_moneda(moneda: str, tipo_cambio: Any) -> Decimal:
    if (moneda or "MXN").upper() in ("MXN", "XXX"):
        return Decimal("1")
    tc = d(tipo_cambio)
    if tc <= 0:
        raise NoContabilizable(f"CFDI en {moneda} sin tipo de cambio: no se puede pasar a pesos.")
    return tc


def _impuesto(lista: list[dict[str, Any]] | None, clave: str) -> Decimal:
    return sum((d(t.get("Importe")) for t in (lista or []) if t.get("Impuesto") == clave), CERO)


def _base_concepto(concepto: dict[str, Any]) -> Decimal:
    return d(concepto.get("Importe")) - d(concepto.get("Descuento"))


def _rol_ingreso(concepto: dict[str, Any]) -> str:
    ivas = [t for t in concepto.get("traslados") or [] if t.get("Impuesto") == IVA]
    if not ivas or any(t.get("TipoFactor") == "Exento" for t in ivas):
        return "ingresos_exentos"
    return "ingresos" if any(d(t.get("TasaOCuota")) > 0 for t in ivas) else "ingresos_tasa_0"


# ── facturas ──


def factura_emitida(comp: Comprobante, ef: ConfigEfectiva, *, nota: bool) -> Asiento:
    """Ingreso emitido (o nota de crédito emitida, que se invierte después)."""
    f = factor_moneda(comp.moneda, comp.tipo_cambio)
    rfc, uuid = comp.rfc_receptor, comp.uuid
    base = c((comp.subtotal - comp.descuento) * f)
    iva, ieps = c(comp.iva_trasladado * f), c(comp.ieps * f)
    ret_iva, ret_isr = c(comp.iva_retenido * f), c(comp.isr_retenido * f)
    conceptos = (comp.datos or {}).get("conceptos") or []

    por_rol: dict[str, Decimal] = defaultdict(lambda: CERO)
    for con in conceptos:
        rol = "devoluciones_ingresos" if nota else _rol_ingreso(con)
        por_rol[rol] += _base_concepto(con) * f
    if not por_rol:
        por_rol["devoluciones_ingresos" if nota else "ingresos"] = base

    pue = comp.metodo_pago == "PUE"
    banco = ef.cuenta_forma_pago(comp.forma_pago) if pue and ef.config.pue_registra_cobro else None
    asiento = Asiento("ingreso" if banco else "diario")
    contraparte = base + iva + ieps - ret_iva - ret_isr
    kw = {"uuid": uuid, "rfc": rfc}
    asiento.cargo(ef.cuenta("clientes"), contraparte, concepto="Clientes", **kw)
    for rol, monto in repartir(dict(por_rol), base).items():
        asiento.abono(ef.cuenta(rol), monto, concepto="Ingreso", **kw)
    sufijo = "cobrado" if pue else "no_cobrado"
    asiento.abono(ef.cuenta(f"iva_trasladado_{sufijo}"), iva, concepto="IVA trasladado", **kw)
    asiento.abono(ef.cuenta(f"ieps_trasladado_{sufijo}"), ieps, concepto="IEPS trasladado", **kw)
    asiento.cargo(ef.cuenta("iva_retenido_por_clientes"), ret_iva, concepto="IVA retenido", **kw)
    asiento.cargo(ef.cuenta("isr_retenido_por_clientes"), ret_isr, concepto="ISR retenido", **kw)
    if banco:
        asiento.cargo(banco, contraparte, concepto="Cobro", **kw)
        asiento.abono(ef.cuenta("clientes"), contraparte, concepto="Cobro", **kw)
    asiento.diferencia = c(comp.total * f) - contraparte
    if nota:
        asiento.invertir()
        asiento.tipo = "egreso" if banco else "diario"
    return asiento


def _cuenta_egreso(ef: ConfigEfectiva, comp: Comprobante, con: dict[str, Any],
                   existentes: set[str]) -> tuple[str, bool]:
    """(cuenta, es_no_deducible) del concepto de un CFDI recibido."""
    clave = str(con.get("ClaveProdServ") or "")
    regla = regla_aplicable(ef.reglas, rfc=comp.rfc_emisor, clave=clave, uso=comp.uso_cfdi,
                            descripcion=str(con.get("Descripcion") or ""))
    no_deducible = ef.cuenta("gastos_no_deducibles")
    if regla is not None:
        return regla.cuenta_numero, regla.cuenta_numero == no_deducible
    cfg = ef.config
    if cfg.uso_s01_no_deducible and comp.uso_cfdi == "S01":
        return no_deducible, True
    if cfg.efectivo_no_deducible and comp.forma_pago == "01" and comp.total > TOPE_EFECTIVO:
        return no_deducible, True
    if comp.uso_cfdi in USO_ACTIVO:
        numero = USO_ACTIVO[comp.uso_cfdi]
        return (numero if numero in existentes else ef.cuenta("activo_fijo")), False
    if cfg.tope_activo > 0 and _base_concepto(con) >= cfg.tope_activo:
        return ef.cuenta("activo_fijo"), False
    if comp.uso_cfdi == "G01":
        return ef.cuenta("compras"), False
    return ef.cuenta("gastos"), False


def factura_recibida(comp: Comprobante, ef: ConfigEfectiva, existentes: set[str], *,
                     nota: bool) -> Asiento:
    """Gasto/compra recibido (o nota de crédito recibida, invertida)."""
    f = factor_moneda(comp.moneda, comp.tipo_cambio)
    rfc, uuid = comp.rfc_emisor, comp.uuid
    base = c((comp.subtotal - comp.descuento) * f)
    iva, ieps = c(comp.iva_trasladado * f), c(comp.ieps * f)
    ret_iva, ret_isr = c(comp.iva_retenido * f), c(comp.isr_retenido * f)
    conceptos = (comp.datos or {}).get("conceptos") or []
    pue = comp.metodo_pago == "PUE"
    cuenta_iva = ef.cuenta("iva_acreditable_pagado" if pue else "iva_acreditable_pendiente")

    gasto: dict[str, Decimal] = defaultdict(lambda: CERO)
    iva_conceptos = ieps_conceptos = CERO
    arrendamiento = False
    for con in conceptos:
        cuenta, no_deducible = _cuenta_egreso(ef, comp, con, existentes)
        iva_c, ieps_c = _impuesto(con.get("traslados"), IVA), _impuesto(con.get("traslados"), IEPS)
        iva_conceptos += iva_c
        ieps_conceptos += ieps_c
        # El IEPS que se paga en una compra es costo; el IVA de lo no deducible, también.
        gasto[cuenta] += (_base_concepto(con) + ieps_c + (iva_c if no_deducible else CERO)) * f
        if not no_deducible:
            gasto[cuenta_iva] += iva_c * f
        arrendamiento |= str(con.get("ClaveProdServ") or "").startswith(PREFIJO_ARRENDAMIENTO)
    if not conceptos:
        gasto[ef.cuenta("gastos")] += base
    # Impuestos que el CFDI declara pero no por concepto: IVA a acreditable, IEPS al gasto.
    if iva_conceptos == 0 and iva:
        gasto[cuenta_iva] += iva
    if ieps_conceptos == 0 and ieps:
        mayor = max((k for k in gasto if k != cuenta_iva), key=lambda k: gasto[k],
                    default=ef.cuenta("gastos"))
        gasto[mayor] += ieps

    banco = ef.cuenta_forma_pago(comp.forma_pago) if pue and ef.config.pue_registra_cobro else None
    asiento = Asiento("egreso" if banco else "diario")
    kw = {"uuid": uuid, "rfc": rfc}
    contraparte = base + iva + ieps - ret_iva - ret_isr
    for cuenta, monto in repartir(dict(gasto), base + iva + ieps).items():
        asiento.cargo(cuenta, monto, concepto="IVA acreditable" if cuenta == cuenta_iva
                      else "Gasto", **kw)
    asiento.abono(ef.cuenta("iva_retenido_por_enterar"), ret_iva, concepto="IVA retenido", **kw)
    rol_isr = "isr_retenido_arrendamiento" if arrendamiento else "isr_retenido_honorarios"
    asiento.abono(ef.cuenta(rol_isr), ret_isr, concepto="ISR retenido", **kw)
    asiento.abono(ef.cuenta("proveedores"), contraparte, concepto="Proveedores", **kw)
    if banco:
        asiento.cargo(ef.cuenta("proveedores"), contraparte, concepto="Pago", **kw)
        asiento.abono(banco, contraparte, concepto="Pago", **kw)
    asiento.diferencia = c(comp.total * f) - contraparte
    if nota:
        asiento.invertir()
        asiento.tipo = "ingreso" if banco else "diario"
    return asiento


# ── nómina ──


def nomina(comp: Comprobante, ef: ConfigEfectiva) -> Asiento:
    """Recibo de nómina emitido por el cliente patrón."""
    nom = (comp.datos or {}).get("nomina") or {}
    f = factor_moneda(comp.moneda, comp.tipo_cambio)
    percepciones = c(d(nom.get("TotalPercepciones")) * f) if nom.get("TotalPercepciones") \
        else c(comp.subtotal * f)
    otros = c(d(nom.get("TotalOtrosPagos")) * f)
    deducciones = c(d(nom.get("TotalDeducciones")) * f)
    isr = min(c(d(nom.get("isr_retenido")) * f), deducciones)
    asimilado = (nom.get("receptor") or {}).get("TipoRegimen") in REGIMEN_ASIMILADOS
    kw = {"uuid": comp.uuid, "rfc": comp.rfc_receptor}
    asiento = Asiento("egreso")
    asiento.cargo(ef.cuenta("asimilados" if asimilado else "sueldos"), percepciones,
                  concepto="Percepciones", **kw)
    asiento.cargo(ef.cuenta("otros_pagos_nomina"), otros, concepto="Otros pagos", **kw)
    asiento.abono(ef.cuenta("isr_retenido_asimilados" if asimilado else "isr_retenido_salarios"),
                  isr, concepto="ISR retenido", **kw)
    asiento.abono(ef.cuenta("otras_deducciones_nomina"), deducciones - isr,
                  concepto="Otras deducciones", **kw)
    neto = percepciones + otros - deducciones
    asiento.abono(ef.cuenta("bancos"), neto, concepto="Pago de nómina", **kw)
    asiento.diferencia = c(comp.total * f) - neto
    return asiento


# ── pagos ──


@dataclass
class DocumentoPagado:
    """Lo que el generador sabe de la factura que se paga (puede no estar en la bóveda)."""

    total: Decimal  # en la moneda del documento
    iva_pendiente: Decimal  # IVA pendiente de la factura, en MXN (0 si era PUE)
    ieps_pendiente: Decimal
    conocido: bool


def pago(comp: Comprobante, ef: ConfigEfectiva,
         documentos: dict[str, DocumentoPagado]) -> Asiento:
    """Complemento de pago: mueve efectivo y traspasa el IVA a efectivamente cobrado/pagado."""
    pagos = (comp.datos or {}).get("pagos") or {}
    emitido = comp.direccion == "emitido"
    rfc = comp.rfc_receptor if emitido else comp.rfc_emisor
    contra = ef.cuenta("clientes" if emitido else "proveedores")
    if emitido:
        pend, efec = ef.cuenta("iva_trasladado_no_cobrado"), ef.cuenta("iva_trasladado_cobrado")
        pend_ieps = ef.cuenta("ieps_trasladado_no_cobrado")
        efec_ieps = ef.cuenta("ieps_trasladado_cobrado")
    else:
        pend, efec = ef.cuenta("iva_acreditable_pendiente"), ef.cuenta("iva_acreditable_pagado")
        pend_ieps = efec_ieps = ""
    asiento = Asiento("ingreso" if emitido else "egreso")
    # Cobro: la cuenta de clientes se abona. Pago: la de proveedores se carga.
    aplicar = asiento.abono if emitido else asiento.cargo
    sin_documento: list[str] = []
    iva_traspasado = CERO
    for p in pagos.get("pagos") or []:
        tc = factor_moneda(p.get("MonedaP") or "MXN", p.get("TipoCambioP"))
        if (p.get("MonedaP") or "MXN").upper() not in ("MXN", "XXX"):
            asiento.advertencias.append(
                "Pago en moneda extranjera: la utilidad o pérdida cambiaria no se registra.")
        monto = c(d(p.get("Monto")) * tc)
        banco = ef.cuenta_forma_pago(str(p.get("FormaDePagoP") or "")) or ef.cuenta("bancos")
        aplicado = CERO
        for doc in p.get("documentos") or []:
            uuid_doc = str(doc.get("IdDocumento") or "").upper()
            equivalencia = d(doc.get("EquivalenciaDR")) or Decimal("1")
            pagado_dr = d(doc.get("ImpPagado"))
            importe = c(pagado_dr / equivalencia * tc)
            aplicado += importe
            kw = {"uuid": uuid_doc, "rfc": rfc}
            aplicar(contra, importe, concepto="Aplicación de pago", **kw)
            info = documentos.get(uuid_doc)
            if info is None or not info.conocido or info.total <= 0:
                sin_documento.append(uuid_doc)
                continue
            proporcion = min(pagado_dr / info.total, Decimal("1"))
            iva = c(info.iva_pendiente * proporcion)
            ieps = c(info.ieps_pendiente * proporcion) if pend_ieps else CERO
            iva_traspasado += iva
            _traspaso(asiento, emitido, pend, efec, iva, "IVA", kw)
            _traspaso(asiento, emitido, pend_ieps, efec_ieps, ieps, "IEPS", kw)
        kw = {"uuid": comp.uuid, "rfc": rfc}
        if emitido:
            asiento.cargo(banco, monto, concepto="Cobro", **kw)
        else:
            asiento.abono(banco, monto, concepto="Pago", **kw)
        if monto != aplicado:
            # Pago mayor a lo aplicado (anticipo) o redondeo de conversión: queda en la
            # contraparte sin documento, a la vista.
            aplicar(contra, monto - aplicado, concepto="Pago no aplicado", **kw)
            asiento.advertencias.append(
                f"El monto del pago ({monto}) no es igual a lo aplicado a documentos ({aplicado}).")
    if sin_documento:
        _iva_desde_totales(asiento, pagos, emitido, pend, efec, sin_documento,
                           comp, iva_traspasado)
    return asiento


def _traspaso(asiento: Asiento, emitido: bool, pendiente: str, efectivo: str, importe: Decimal,
              etiqueta: str, kw: dict[str, str]) -> None:
    if not importe or not pendiente:
        return
    if emitido:  # 209 (acreedora) → 208
        asiento.cargo(pendiente, importe, concepto=f"{etiqueta} cobrado", **kw)
        asiento.abono(efectivo, importe, concepto=f"{etiqueta} cobrado", **kw)
    else:  # 119 (deudora) → 118
        asiento.cargo(efectivo, importe, concepto=f"{etiqueta} pagado", **kw)
        asiento.abono(pendiente, importe, concepto=f"{etiqueta} pagado", **kw)


def _iva_desde_totales(asiento: Asiento, pagos: dict[str, Any], emitido: bool, pend: str,
                       efec: str, sin_documento: list[str], comp: Comprobante,
                       ya_traspasado: Decimal) -> None:
    """Facturas que no están en la bóveda: el IVA sale de los Totales del pago 2.0."""
    totales = pagos.get("totales") or {}
    iva_total = d(totales.get("TotalTrasladosImpuestoIVA16")) + \
        d(totales.get("TotalTrasladosImpuestoIVA8"))
    resto = c(iva_total - ya_traspasado)
    if pagos.get("version") == "2.0" and totales and resto > 0:
        _traspaso(asiento, emitido, pend, efec, resto, "IVA",
                  {"uuid": comp.uuid, "rfc": comp.rfc_receptor if emitido else comp.rfc_emisor})
        asiento.advertencias.append(
            "Facturas pagadas que no están en la bóveda: el IVA se tomó de los totales del "
            f"complemento ({', '.join(sin_documento)}).")
    else:
        asiento.advertencias.append(
            "Facturas pagadas que no están en la bóveda: el IVA no se traspasó a "
            f"efectivamente {'cobrado' if emitido else 'pagado'} ({', '.join(sin_documento)}).")
