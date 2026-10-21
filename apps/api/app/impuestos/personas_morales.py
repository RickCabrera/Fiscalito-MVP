"""
Personas morales desde la bóveda y la contabilidad (P3-01). Arma la entrada del motor puro
`app/fiscal_engine/personas_morales.py`; no calcula impuestos por su cuenta.

De dónde sale cada importe, las cuentas de créditos y deudas del ajuste anual por inflación
y sus decisiones: docstring de `app/impuestos/pm_fuentes.py`, donde vive esa lectura (P6-07,
partido por el tope de 300 líneas; sólo se movió el código).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import FiscalValidationError
from app.fiscal_engine import personas_morales as motor
from app.fiscal_engine.actualizacion import cortar_diezmilesimo
from app.fiscal_engine.resumen_impuestos import ImporteSistema
from app.impuestos.pm_fuentes import (  # noqa: F401 — re-exportados
    CERO,
    CREDITOS_DEFAULT,
    DEUDAS_DEFAULT,
    MESES,
    NO_DEDUCIBLES,
    CuentaFiscal,
    _prefijo,
    art28_xxx_boveda,
    boveda_devengada,
    boveda_flujo,
    clase_cuenta,
    contabilidad_por_mes,
    hay_polizas,
    saldos_aai,
)
from app.impuestos.servicio import config_de, regimen_de
from app.modelos.impuestos import DatosAnualesPM
from app.modelos.nucleo import Cliente
from app.redondeo import redondear
from app.schemas.personas_morales import DatosAnualesPMSchema

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
                "quinto párrafo): captura el importe o las cuentas donde los registras.")
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
