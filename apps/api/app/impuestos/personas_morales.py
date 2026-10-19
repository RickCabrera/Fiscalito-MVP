"""
Personas morales desde la bóveda y la contabilidad (P3-01). Arma la entrada del motor puro
`app/fiscal_engine/personas_morales.py`; no calcula impuestos por su cuenta.

DE DÓNDE SALE CADA IMPORTE
--------------------------
- **Régimen general (601)** — ingresos acumulables y deducciones autorizadas, por mes:
  - `contabilidad` (P2): movimientos del mes de las cuentas de resultados. Ingresos = 401/402 +
    403 + 702 + 704 (abonos − cargos). Deducciones = costo (5xx), gastos (6xx) y otros gastos
    (701, 703) (cargos − abonos), SALVO las no deducibles: `NO_DEDUCIBLES` (PTU 607/610,
    participación en subsidiarias 608/609, ISR 611, no deducibles 612 y x.83/x.81, depreciación
    y amortización contables 504.07-504.24, 613, 614) y las que el despacho agregue. La
    deducción fiscal de inversiones (Arts. 31-38) se captura aparte.
  - `boveda`: CFDI vigentes por fecha de emisión (Art. 17 LISR: el ingreso se acumula al
    expedir el comprobante). Ingresos = emitidos I − emitidos E (las notas de crédito, que
    también aplican los anticipos). Deducciones = recibidos I − recibidos E sin UsoCFDI
    personal (D01-D10), sin efectos (S01, CN01) ni de inversión (I01-I08, que van a la
    deducción de inversiones), más la nómina emitida (gravado + `factor_exentos_nomina` ×
    exento, Art. 28 fr. XXX). DECISIÓN PROVISIONAL: la bóveda no distingue costo de lo vendido
    de compras (Art. 39); con inventarios, la contabilidad manda.
  - `auto` (default): contabilidad si el cliente tiene pólizas activas en el ejercicio.
- **RESICO PM** — flujo de efectivo (Arts. 207 y 210): los mismos CFDI por `flujo_del_mes`
  (PUE en su fecha, PPD por complemento de pago) y la nómina por fecha de pago.
- **No deducibles del Art. 28 fr. XXX para la renta gravable de PTU** (Art. 9 cuarto párrafo)
  — capturado (`no_deducibles_art28_xxx`); si no, con contabilidad, la suma de las cuentas
  `cuentas_art28_xxx` del despacho (el código agrupador del SAT no tiene una cuenta propia
  para esto); con bóveda, (1 − `factor_exentos_nomina`) × exentos de la nómina emitida. Con
  contabilidad y sin cuentas designadas: cero y nota (no se baja la PTU sin dato).
- **Ajuste anual por inflación** — saldos de fin de mes de la contabilidad en las cuentas de
  créditos y deudas (`CREDITOS_DEFAULT`, `DEUDAS_DEFAULT`, por código agrupador; criterio del
  despacho configurable) o los 12 saldos capturados.

CUENTAS DE CRÉDITOS Y DEUDAS (Arts. 45 y 46 LISR) — DEFAULT, CRITERIO DEL DESPACHO
-------------------------------------------------------------------------------------
Créditos: 102 bancos, 103 inversiones, 104 instrumentos financieros, 105 clientes, 106 cuentas
por cobrar, 107 deudores diversos, 113 impuestos a favor, 186 cuentas por cobrar a largo plazo,
190 instrumentos financieros a largo plazo. Fuera: 101 caja (el efectivo en caja no es
crédito), 114 pagos provisionales, 118/119 IVA acreditable, 120 anticipo a proveedores
(DECISIÓN PROVISIONAL conservadora: no es un derecho a recibir numerario), 188 acciones.
Deudas: 201-208, 210-218 y 251-256 (incluye anticipos de clientes y contribuciones causadas);
fuera 209 (IVA trasladado no cobrado: aún no se causa). El 213 puede incluir ISR propio por
pagar, que el Art. 46 excluye (partida no deducible): se avisa en notas.
FUENTE POR CONFIRMAR: la lista exacta de exclusiones de los Arts. 45 y 46 contra el texto
vigente; por eso es configurable por cliente (`cuentas_creditos`, `cuentas_deudas`).
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.contabilidad import catalogo
from app.contabilidad.balanza import totales_por_cuenta
from app.contabilidad.reportes import seccion
from app.exceptions import FiscalValidationError
from app.fiscal_engine import personas_morales as motor
from app.fiscal_engine.actualizacion import cortar_diezmilesimo
from app.fiscal_engine.resumen_impuestos import ImporteSistema
from app.impuestos.flujo import Efectivo, flujo_del_mes, nominas_del_mes
from app.impuestos.servicio import USOS_NO_ACREDITABLES, config_de, regimen_de
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, Poliza
from app.modelos.impuestos import DatosAnualesPM
from app.modelos.nucleo import Cliente
from app.redondeo import redondear
from app.schemas.personas_morales import DatosAnualesPMSchema

CERO = Decimal("0.00")
MESES = range(1, 13)
CREDITOS_DEFAULT = ("102", "103", "104", "105", "106", "107", "113", "186", "190")
DEUDAS_DEFAULT = ("201", "202", "203", "204", "205", "206", "207", "208", "210", "211", "212",
                  "213", "214", "215", "216", "217", "218", "251", "252", "253", "254", "255",
                  "256")
NO_DEDUCIBLES = (
    ("601.83", "602.83", "603.81", "604.81", "607", "608", "609", "610", "611", "612", "613",
     "614") + tuple(f"504.{n:02d}" for n in range(7, 25))
)
USOS_INVERSION = {f"I{n:02d}" for n in range(1, 9)}
SECCIONES_INGRESO = ("ingresos", "otros_ingresos")
SECCIONES_DEDUCCION = ("costo", "gastos", "otros_gastos", "impuestos")


def _prefijo(codigo: str, lista: Iterable[str]) -> bool:
    return any(codigo == p or codigo.startswith(p + ".") for p in lista)


# ── tipo y datos capturados ──


def tipo_pm(cliente: Cliente) -> str | None:
    """`general` (601), `resico` (626 con RFC de 12) o None si no es persona moral."""
    regimen = regimen_de(cliente)
    if regimen == "601":
        return "general"
    if regimen == "626" and len(cliente.rfc or "") == 12:
        return "resico"
    return None


def datos_de(db: Session, cliente: Cliente, anio: int) -> DatosAnualesPMSchema:
    fila = db.get(DatosAnualesPM, (cliente.id, anio))
    return DatosAnualesPMSchema.model_validate(fila.datos if fila else {})


def guardar_datos(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema) -> None:
    fila = db.get(DatosAnualesPM, (cliente.id, anio))
    datos = d.model_dump(mode="json")
    if fila is None:
        db.add(DatosAnualesPM(cliente_id=cliente.id, anio=anio, datos=datos))
    else:
        fila.datos = datos
    db.flush()


def perdidas_de(d: DatosAnualesPMSchema) -> list[motor.PerdidaPendiente]:
    salida = []
    for p in d.perdidas:
        act = None
        if p.actualizada_a:
            a, m = p.actualizada_a.split("-")
            act = (int(a), int(m))
        salida.append(motor.PerdidaPendiente(p.ejercicio, p.remanente, act))
    return salida


def estimulos_de(d: DatosAnualesPMSchema) -> list[motor.Estimulo]:
    return [motor.Estimulo(e.concepto, e.importe, e.fundamento, e.desde_mes, e.en_provisionales)
            for e in d.estimulos]


# ── bóveda ──


def _rango(anio: int) -> tuple[datetime, datetime]:
    return datetime(anio, 1, 1), datetime(anio + 1, 1, 1)


def _pesos(c: Comprobante, importe: Decimal) -> Decimal:
    if c.moneda not in ("MXN", "XXX", "") and c.tipo_cambio:
        return importe * c.tipo_cambio
    return importe


def _dec(v: object) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except Exception:  # noqa: BLE001 - importe ilegible: cuenta como cero
        return Decimal("0")


def _deducible_nomina(c: Comprobante, factor: Decimal) -> Decimal:
    p = (c.datos or {}).get("nomina", {}).get("percepciones", {})
    return _dec(p.get("TotalGravado")) + factor * _dec(p.get("TotalExento"))


def _no_deducible_nomina(c: Comprobante, factor: Decimal) -> Decimal:
    """Art. 28 fr. XXX: la parte del exento que NO se dedujo (1 − factor)."""
    p = (c.datos or {}).get("nomina", {}).get("percepciones", {})
    return (1 - factor) * _dec(p.get("TotalExento"))


def art28_xxx_boveda(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
                     ) -> Decimal:
    """No deducible del Art. 28 fr. XXX de la nómina emitida del ejercicio (bóveda)."""
    total = sum((_no_deducible_nomina(n, d.factor_exentos_nomina)
                 for m in MESES for n in nominas_del_mes(db, cliente, anio, m)), CERO)
    return redondear(total)


def _es_deduccion(c: Comprobante) -> bool:
    uso = (c.uso_cfdi or "").upper()
    return uso not in USOS_NO_ACREDITABLES and uso not in USOS_INVERSION


def boveda_devengada(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(ingresos, deducciones) por mes por fecha de emisión (Art. 17 LISR)."""
    ini, fin = _rango(anio)
    comps = db.scalars(comprobantes_vigentes(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.tipo.in_(("I", "E")),
        Comprobante.fecha >= ini, Comprobante.fecha < fin)))
    ing = {m: CERO for m in MESES}
    ded = {m: CERO for m in MESES}
    for c in comps:
        signo = -1 if c.tipo == "E" else 1
        neto = _pesos(c, c.subtotal - c.descuento) * signo
        if c.direccion == "emitido":
            ing[c.fecha.month] += neto
        elif _es_deduccion(c):
            ded[c.fecha.month] += neto
    for m in MESES:
        for n in nominas_del_mes(db, cliente, anio, m):
            ded[m] += _deducible_nomina(n, d.factor_exentos_nomina)
    return ({m: redondear(v) for m, v in ing.items()}, {m: redondear(v) for m, v in ded.items()})


def _neto_flujo(e: Efectivo) -> Decimal:
    c = e.comprobante
    return (c.subtotal - c.descuento) * e.factor_pesos * (-1 if c.tipo == "E" else 1)


def boveda_flujo(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(ingresos cobrados, deducciones pagadas) por mes (RESICO PM, Arts. 207 y 210)."""
    ing = {m: CERO for m in MESES}
    ded = {m: CERO for m in MESES}
    for m in MESES:
        for e in flujo_del_mes(db, cliente, anio, m):
            if e.comprobante.direccion == "emitido":
                ing[m] += _neto_flujo(e)
            elif _es_deduccion(e.comprobante):
                ded[m] += _neto_flujo(e)
        for n in nominas_del_mes(db, cliente, anio, m):
            ded[m] += _deducible_nomina(n, d.factor_exentos_nomina)
    return ({m: redondear(v) for m, v in ing.items()}, {m: redondear(v) for m, v in ded.items()})


# ── contabilidad ──


def hay_polizas(db: Session, cliente: Cliente, anio: int) -> bool:
    return bool(db.scalar(select(func.count(Poliza.id)).where(
        Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
        Poliza.fecha >= date(anio, 1, 1), Poliza.fecha <= date(anio, 12, 31))))


def _fin(anio: int, mes: int) -> date:
    return date(anio, mes, monthrange(anio, mes)[1])


@dataclass
class CuentaFiscal:
    numero: str
    nombre: str
    codigo: str
    clase: str  # ingreso | deduccion | no_deducible
    meses: dict[int, Decimal] = field(default_factory=lambda: {m: CERO for m in MESES})

    @property
    def total(self) -> Decimal:
        return sum(self.meses.values(), CERO)


def clase_cuenta(c: CuentaContable, no_deducibles: Iterable[str]) -> str | None:
    """Clase fiscal de una cuenta de resultados, o None si no es de resultados."""
    sec = seccion(c)
    codigo = c.codigo_agrupador or ""
    if sec in SECCIONES_INGRESO:
        return "ingreso"
    if sec not in SECCIONES_DEDUCCION:
        return None
    extra = list(no_deducibles)
    if (sec == "impuestos" or _prefijo(codigo, NO_DEDUCIBLES) or _prefijo(codigo, extra)
            or c.numero in extra):
        return "no_deducible"
    return "deduccion"


def contabilidad_por_mes(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> list[CuentaFiscal]:
    """Movimientos del mes de cada cuenta de resultados, con su clase fiscal."""
    cuentas = {c.id: c for c in catalogo.cuentas(db, cliente)}
    salida: dict[int, CuentaFiscal] = {}
    for m in MESES:
        for cid, t in totales_por_cuenta(db, cliente, date(anio, m, 1), _fin(anio, m)).items():
            c = cuentas.get(cid)
            clase = clase_cuenta(c, [*d.cuentas_no_deducibles, *d.cuentas_art28_xxx]
                                 ) if c else None
            if clase is None:
                continue
            importe = t.abonos - t.cargos if clase == "ingreso" else t.cargos - t.abonos
            if cid not in salida:
                salida[cid] = CuentaFiscal(c.numero, c.nombre, c.codigo_agrupador, clase)
            salida[cid].meses[m] += importe
    return sorted(salida.values(), key=lambda x: x.numero)


def saldos_aai(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema, fuente: str
) -> tuple[list[Decimal], list[Decimal], str]:
    """Saldos de fin de mes de créditos y deudas: capturados o de la contabilidad."""
    if d.saldos_creditos:
        return list(d.saldos_creditos), list(d.saldos_deudas), "capturados"
    if fuente != "contabilidad":
        return [], [], "sin datos"
    cuentas = {c.id: c for c in catalogo.cuentas(db, cliente)}
    cred_pref = d.cuentas_creditos or list(CREDITOS_DEFAULT)
    deud_pref = d.cuentas_deudas or list(DEUDAS_DEFAULT)
    creditos, deudas = [], []
    for m in MESES:
        sc = sd = CERO
        for cid, t in totales_por_cuenta(db, cliente, date(anio, m, 1), _fin(anio, m)).items():
            c = cuentas.get(cid)
            codigo = (c.codigo_agrupador if c else "") or ""
            if _prefijo(codigo, cred_pref):
                sc += t.final
            elif _prefijo(codigo, deud_pref):
                sd -= t.final  # acreedora: saldo deudor negativo
        creditos.append(redondear(sc))
        deudas.append(redondear(sd))
    return creditos, deudas, "contabilidad"


# ── base anual ──


@dataclass
class BaseAnual:
    tipo: str
    fuente: str
    ingresos_mes: dict[int, Decimal]
    deducciones_mes: dict[int, Decimal]
    no_deducibles_mes: dict[int, Decimal]
    cuentas: list[CuentaFiscal]
    aai: motor.ResultadoAAI | None
    origen_saldos: str
    notas: list[str]
    no_deducibles_art28_xxx: Decimal = CERO
    origen_art28_xxx: str = "sin dato"


def _es_cuenta_art28(c: CuentaFiscal, d: DatosAnualesPMSchema) -> bool:
    """Cuenta de gasto designada por el despacho para el no deducible del Art. 28 fr. XXX."""
    designada = c.numero in d.cuentas_art28_xxx or _prefijo(c.codigo or "", d.cuentas_art28_xxx)
    return designada and c.clase == "no_deducible"


def art28_xxx(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema, fuente: str,
              cuentas: list[CuentaFiscal]) -> tuple[Decimal, str, str | None]:
    """(importe, origen, nota) del no deducible del Art. 28 fr. XXX para la PTU."""
    if d.no_deducibles_art28_xxx is not None:
        return redondear(d.no_deducibles_art28_xxx), "capturado", None
    if fuente == "contabilidad":
        if not d.cuentas_art28_xxx:
            return CERO, "sin dato", (
                "Renta gravable de PTU sin restar los no deducibles del Art. 28 fr. XXX (Art. 9 "
                "cuarto párrafo): captura el importe o las cuentas donde los registras.")
        total = sum((c.total for c in cuentas if _es_cuenta_art28(c, d)), CERO)
        return redondear(total), "contabilidad", None
    return art28_xxx_boveda(db, cliente, anio, d), "boveda", None


def fuente_de(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema) -> str:
    if d.fuente != "auto":
        return d.fuente
    return "contabilidad" if hay_polizas(db, cliente, anio) else "boveda"


def base_anual(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema,
               tipo: str) -> BaseAnual:
    """Ingresos y deducciones por mes, y el ajuste anual por inflación."""
    modo = config_de(db, cliente).modo_factor
    notas: list[str] = []
    cuentas: list[CuentaFiscal] = []
    nd = {m: CERO for m in MESES}
    if tipo == "resico":
        fuente = "boveda"
        ing, ded = boveda_flujo(db, cliente, anio, d)
        notas.append("RESICO PM: ingresos cobrados y deducciones pagadas de la bóveda por "
                     "flujo de efectivo (Arts. 207 y 210 LISR).")
    else:
        fuente = fuente_de(db, cliente, anio, d)
        if fuente == "contabilidad":
            cuentas = contabilidad_por_mes(db, cliente, anio, d)
            ing = {m: sum((c.meses[m] for c in cuentas if c.clase == "ingreso"), CERO)
                   for m in MESES}
            ded = {m: sum((c.meses[m] for c in cuentas if c.clase == "deduccion"), CERO)
                   for m in MESES}
            nd = {m: sum((c.meses[m] for c in cuentas if c.clase == "no_deducible"), CERO)
                  for m in MESES}
            if any(c.codigo.startswith("502") and c.total for c in cuentas):
                notas.append("Hay compras (502) en resultados: la ley deduce el costo de lo "
                             "vendido (Art. 39 LISR); ajusta con deducciones o no deducibles "
                             "adicionales si llevas inventarios.")
        else:
            ing, ded = boveda_devengada(db, cliente, anio, d)
            notas.append("Ingresos y deducciones de la bóveda por fecha de emisión (sin "
                         "contabilidad en el ejercicio).")
    aai = None
    origen = "no aplica"
    if tipo == "general" or d.aai_en_resico:
        cred, deud, origen = saldos_aai(db, cliente, anio, d, fuente)
        aai = motor.ajuste_anual_inflacion(anio, cred, deud, modo)
        if origen == "contabilidad":
            notas.append("Ajuste anual por inflación con los saldos de fin de mes de la "
                         "contabilidad (cuentas de créditos y deudas del despacho).")
    xxx, origen_xxx, nota_xxx = art28_xxx(db, cliente, anio, d, fuente, cuentas)
    if nota_xxx:
        notas.append(nota_xxx)
    return BaseAnual(tipo, fuente, ing, ded, nd, cuentas, aai, origen, notas, xxx, origen_xxx)


def entrada_anual(b: BaseAnual, d: DatosAnualesPMSchema, anio: int, modo: Any,
                  pagos: Decimal = CERO, retenciones: Decimal = CERO) -> motor.EntradaAnual:
    """La entrada del motor anual con la base, los datos capturados y los pagos."""
    return motor.EntradaAnual(
        anio, sum(b.ingresos_mes.values(), CERO) + d.ingresos_adicionales,
        sum(b.deducciones_mes.values(), CERO) + d.deduccion_inversiones
        + d.deducciones_adicionales - d.no_deducibles_adicionales,
        b.aai, d.ptu_pagada, perdidas_de(d), estimulos_de(d), pagos, retenciones,
        d.anticipos_miembros_base, modo, b.no_deducibles_art28_xxx)


def utilidad_de_base(b: BaseAnual, d: DatosAnualesPMSchema, anio: int, modo: Any
                     ) -> motor.ResultadoAnualPM:
    """La anual sin pagos ni retenciones (para el coeficiente y para la anual completa)."""
    return motor.anual_pm(entrada_anual(b, d, anio, modo), resico=b.tipo == "resico")


def coeficiente_para(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
                     ) -> tuple[Decimal, str]:
    """Coeficiente del Art. 14 fr. I para los pagos de `anio`, con su origen."""
    modo = config_de(db, cliente).modo_factor
    if d.coeficiente_utilidad is not None:
        return cortar_diezmilesimo(d.coeficiente_utilidad, modo), "capturado"
    if d.utilidad_fiscal_base is not None and d.ingresos_nominales_base:
        coef = motor.coeficiente_utilidad(d.utilidad_fiscal_base, d.ingresos_nominales_base,
                                          d.anticipos_miembros_base, modo)
        return coef, "calculado con la utilidad fiscal y los ingresos nominales capturados"
    for anterior in range(anio - 1, anio - 1 - motor.ANIOS_COEFICIENTE, -1):
        da = datos_de(db, cliente, anterior)
        try:
            b = base_anual(db, cliente, anterior, da, "general")
            if not any(b.ingresos_mes.values()):
                continue
            r = utilidad_de_base(b, da, anterior, modo)
        except FiscalValidationError:  # p. ej. un INPC anterior a la serie cargada
            continue
        if r.coeficiente_siguiente > 0:
            return r.coeficiente_siguiente, f"calculado con la anual {anterior} del sistema"
    return Decimal("0.0000"), "sin coeficiente"


# ── pagos provisionales y anual ──


def entrada_provisionales(db: Session, cliente: Cliente, anio: int, mes: int, tipo: str,
                          d: DatosAnualesPMSchema, b: BaseAnual, coef: Decimal
                          ) -> motor.EntradaProvisionales:
    modo = config_de(db, cliente).modo_factor
    return motor.EntradaProvisionales(
        anio, mes, b.ingresos_mes, coef, d.ptu_pagada, d.mes_pago_ptu, perdidas_de(d),
        dict(d.retenciones_bancarias), dict(d.pagos_efectuados), estimulos_de(d),
        b.deducciones_mes if tipo == "resico" else {}, modo)


def pagos_provisionales(db: Session, cliente: Cliente, anio: int, mes: int, tipo: str
                        ) -> tuple[list[motor.PagoProvisionalPM], Decimal, str, BaseAnual]:
    d = datos_de(db, cliente, anio)
    b = base_anual(db, cliente, anio, d, tipo)
    coef, origen = (coeficiente_para(db, cliente, anio, d) if tipo == "general"
                    else (CERO, "no aplica"))
    e = entrada_provisionales(db, cliente, anio, mes, tipo, d, b, coef)
    if tipo == "general":
        return motor.pagos_provisionales_pm(e), coef, origen, b
    return motor.pagos_provisionales_resico_pm(e), coef, origen, b


def notas_provisionales(tipo: str, coef: Decimal, origen: str, mes: int) -> list[str]:
    notas = []
    if tipo == "general":
        notas.append(f"Coeficiente de utilidad {coef:.4f} ({origen}; Art. 14 fr. I LISR).")
        if coef == 0:
            notas.append("Sin coeficiente: en el primer ejercicio no hay pagos provisionales "
                         "(Art. 14 fr. I). Si no es el caso, captura el coeficiente en los "
                         "datos anuales del cliente.")
        notas.append("PTU pagada: se disminuye en octavos de mayo a diciembre (Art. 14 fr. II).")
    else:
        notas.append("RESICO PM: flujo acumulado − PTU pagada − pérdidas, por 30 % (Art. 211).")
    if mes <= 6:
        notas.append("Pérdidas de enero a junio con su última actualización; desde julio, "
                     "actualizadas a junio (DECISIÓN PROVISIONAL, FUENTE POR CONFIRMAR).")
    return notas


def isr_del_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> ImporteSistema | None:
    """Renglón de ISR propio del resumen de impuestos para una persona moral."""
    tipo = tipo_pm(cliente)
    if tipo is None:
        return None
    pagos, coef, origen, _b = pagos_provisionales(db, cliente, anio, mes, tipo)
    p = pagos[-1]
    clave = "isr_pm" if tipo == "general" else "isr_resico_pm"
    nota = (f"Pago provisional Art. 14 LISR, coeficiente {coef:.4f} ({origen})."
            if tipo == "general" else "Pago provisional RESICO PM (Art. 211 LISR).")
    return ImporteSistema(clave, p.pago_determinado, nota)
