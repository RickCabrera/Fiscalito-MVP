"""
IVA mensual completo sobre flujo de efectivo (P3-03). Motor puro: no lee la base de datos.

FUENTES (Ley del IVA)
---------------------
- Art. 1o.-B: el IVA se causa cuando se cobran efectivamente las contraprestaciones →
  trasladado **efectivamente cobrado** (PUE en el mes del CFDI; PPD en el mes del pago, por el
  complemento de recepción de pagos, en proporción a lo pagado).
- Art. 5o. fr. III: el IVA acreditable debe haber sido **efectivamente pagado** en el mes.
- Art. 5o. fr. IV: el IVA retenido se acredita cuando la retención se entera.
- Art. 5o. fr. V inciso c): cuando la erogación se usa indistintamente en actividades gravadas
  y exentas, "el acreditamiento procederá únicamente en la proporción en la que el valor de las
  actividades por las que deba pagarse el impuesto ... represente en el valor total de las
  actividades del mes". Las actividades a tasa 0 % cuentan como gravadas. Desde la reforma
  de 2022 (DOF 12-nov-2021), el valor total incluye los **actos o actividades no objeto** del
  impuesto (Art. 4o.-A: los no realizados en territorio nacional y los distintos del Art. 1o.
  realizados en él) → entran al DENOMINADOR (corrección B4 del revisor de motor).
- Art. 5o.-C: conceptos que NO se incluyen en el valor de los actos para la proporción (I
  importaciones; II activo fijo, cargos diferidos y terrenos; III dividendos, salvo actividad
  preponderante; IV acciones, partes sociales y títulos de crédito; V moneda y piezas de oro o
  plata; VI intereses y ganancia cambiaria; VII arrendamiento financiero; VIII bienes
  adjudicados; IX operaciones financieras derivadas; X certificados de participación
  inmobiliaria no amortizables). Si un CFDI emitido con valor "no objeto" corresponde a uno de
  esos conceptos (o no es un acto del Art. 4o.-A), el despacho lo excluye por UUID con
  `ConfigIVA.no_objeto_excluidos` (`iva_no_objeto_excluidos` en la configuración del cliente).
  Default: todo el no objeto cobrado entra (lo conservador: proporción menor, acredita menos).
- Art. 5o.-B: opción de usar la proporción del año de calendario anterior (aquí: proporción
  fija capturada por cliente). (Antes se citaba como 5o.-C: el 5o.-C es la lista de
  exclusiones; texto consultado en diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf.)
- Art. 6o.: el saldo a favor "únicamente podrá acreditarlo contra el impuesto a su cargo" de
  los meses siguientes hasta agotarlo o pedir su devolución; "Cuando se solicite la devolución
  deberá ser sobre el total del saldo a favor"; "Los saldos cuya devolución se solicite no
  podrán acreditarse en declaraciones posteriores".
- Art. 1o.-A: el retenedor entera el IVA retenido a terceros (renglón aparte: no se compensa
  con el saldo a favor, que sólo se acredita contra el impuesto "a su cargo").
- Tasas: 16 % (Art. 1o.), 0 % (Art. 2o.-A), exento (Arts. 9, 15, 20, 25), 8 % región
  fronteriza por **estímulo** (Decreto de estímulos fiscales región fronteriza norte y sur,
  prorrogado al 31-dic-2026 por decreto DOF 31-dic-2025). Las tasas salen de cada CFDI
  (`TasaOCuota`), no se suponen: el 8 % sólo se marca como inconsistencia si el cliente no está
  configurado como fronterizo.

REDONDEO
--------
Importes a centavos con ROUND_HALF_UP (`app.redondeo.redondear`), por concepto. La proporción
se corta al diezmilésimo (Art. 17-A CFF último párrafo) con el mismo criterio de corte del
cliente que el factor de actualización (`ModoFactor`, default truncar — DP-3).

DECISIONES PROVISIONALES
------------------------
- El saldo a favor arrastrado NO se actualiza por inflación (conservador: acredita de menos).
- `compensacion`: el Art. 6o. vigente sólo prevé acreditar o pedir devolución; se ofrece como
  opción porque el despacho la usa con otros saldos, pero se trata igual que devolución (el
  saldo deja de arrastrarse). FUENTE POR CONFIRMAR.
- Mes sin actividades: si no hay actos exentos ni no objeto, la proporción es 1 (todos los
  actos del mes —ninguno— son gravados); con exentos o no objeto y sin gravados, 0.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.actualizacion import MODO_FACTOR_DEFAULT, ModoFactor, cortar_diezmilesimo
from app.redondeo import redondear

Direccion = Literal["emitido", "recibido"]
Asignacion = Literal["gravado", "exento", "indistinto"]
OpcionSaldo = Literal["acreditar", "devolucion", "compensacion"]
CERO = Decimal("0.00")


@dataclass(frozen=True)
class MovimientoIVA:
    """
    Un cobro o un pago del mes ya llevado a pesos y a flujo de efectivo.

    `signo` = -1 para notas de crédito (CFDI tipo E): restan de lo cobrado o de lo pagado.
    """

    uuid: str
    direccion: Direccion
    base_16: Decimal = CERO
    iva_16: Decimal = CERO
    base_8: Decimal = CERO
    iva_8: Decimal = CERO
    base_0: Decimal = CERO
    base_exento: Decimal = CERO
    base_no_objeto: Decimal = CERO
    iva_retenido: Decimal = CERO
    signo: int = 1
    origen: str = "PUE"
    deducible: bool = True


@dataclass(frozen=True)
class ConfigIVA:
    """Criterio del despacho por cliente (DP-3)."""

    region_fronteriza: bool = False
    proporcion_modo: Literal["calculada", "fija"] = "calculada"
    proporcion_fija: Decimal | None = None
    modo_corte: ModoFactor = MODO_FACTOR_DEFAULT
    # UUID (mayúsculas) de CFDI emitidos cuyo valor no objeto NO es acto del Art. 4o.-A o es
    # concepto excluido por el Art. 5o.-C (dividendos, etc.): no entra al denominador.
    no_objeto_excluidos: frozenset[str] = frozenset()


@dataclass
class ResultadoIVAMes:
    """El IVA de un mes, renglón por renglón como en la declaración."""

    anio: int
    mes: int
    valor_actos_16: Decimal = CERO
    valor_actos_8: Decimal = CERO
    valor_actos_0: Decimal = CERO
    valor_actos_exentos: Decimal = CERO
    valor_no_objeto: Decimal = CERO
    valor_no_objeto_en_proporcion: Decimal = CERO
    iva_trasladado_cobrado: Decimal = CERO
    iva_retenido_por_clientes: Decimal = CERO
    proporcion: Decimal = Decimal("1")
    iva_pagado_total: Decimal = CERO
    iva_pagado_no_deducible: Decimal = CERO
    iva_acreditable_identificado: Decimal = CERO
    iva_no_acreditable_exentos: Decimal = CERO
    iva_uso_indistinto: Decimal = CERO
    iva_acreditable_proporcional: Decimal = CERO
    iva_acreditable: Decimal = CERO
    iva_a_cargo_del_mes: Decimal = CERO
    saldo_favor_anterior: Decimal = CERO
    saldo_favor_aplicado: Decimal = CERO
    iva_a_pagar: Decimal = CERO
    saldo_favor_del_mes: Decimal = CERO
    opcion_saldo: OpcionSaldo = "acreditar"
    saldo_favor_solicitado: Decimal = CERO
    saldo_favor_siguiente: Decimal = CERO
    iva_retenido_a_terceros: Decimal = CERO
    movimientos: int = 0
    notas: list[str] = field(default_factory=list)


def _suma(movs: Iterable[MovimientoIVA], campo: str) -> Decimal:
    return sum((getattr(m, campo) * m.signo for m in movs), CERO)


def calcular_proporcion(r: ResultadoIVAMes, config: ConfigIVA) -> Decimal:
    """
    Proporción del Art. 5o. fr. V inciso c) (o la fija del Art. 5o.-B): gravados (16 %, 8 %,
    0 %) ÷ (gravados + exentos + no objeto del Art. 4o.-A no excluido por el despacho).
    """
    if config.proporcion_modo == "fija":
        if config.proporcion_fija is None or not (0 <= config.proporcion_fija <= 1):
            raise FiscalValidationError(
                "La proporción fija (Art. 5o.-B LIVA) debe estar entre 0 y 1."
            )
        return config.proporcion_fija
    gravados = r.valor_actos_16 + r.valor_actos_8 + r.valor_actos_0
    no_gravados = r.valor_actos_exentos + r.valor_no_objeto_en_proporcion
    total = gravados + no_gravados
    if no_gravados <= 0:
        return Decimal("1")
    if total <= 0:
        return Decimal("0")
    return cortar_diezmilesimo(gravados / total, config.modo_corte)


def calcular_iva_mes(
    anio: int,
    mes: int,
    movimientos: Iterable[MovimientoIVA],
    saldo_favor_anterior: Decimal = CERO,
    config: ConfigIVA | None = None,
    asignaciones: dict[str, Asignacion] | None = None,
    opcion_saldo: OpcionSaldo = "acreditar",
) -> ResultadoIVAMes:
    """IVA del mes (Arts. 1o.-B, 5o., 6o. LIVA). Ver el docstring del módulo."""
    config = config or ConfigIVA()
    asignaciones = asignaciones or {}
    if saldo_favor_anterior < 0:
        raise FiscalValidationError("El saldo a favor anterior no puede ser negativo.")
    movs = list(movimientos)
    emit = [m for m in movs if m.direccion == "emitido"]
    reci = [m for m in movs if m.direccion == "recibido"]
    r = ResultadoIVAMes(anio=anio, mes=mes, movimientos=len(movs), opcion_saldo=opcion_saldo)

    r.valor_actos_16 = redondear(_suma(emit, "base_16"))
    r.valor_actos_8 = redondear(_suma(emit, "base_8"))
    r.valor_actos_0 = redondear(_suma(emit, "base_0"))
    r.valor_actos_exentos = redondear(_suma(emit, "base_exento"))
    r.valor_no_objeto = redondear(_suma(emit, "base_no_objeto"))
    r.valor_no_objeto_en_proporcion = redondear(_suma(
        [m for m in emit if m.uuid.upper() not in config.no_objeto_excluidos], "base_no_objeto"))
    r.iva_trasladado_cobrado = redondear(_suma(emit, "iva_16") + _suma(emit, "iva_8"))
    r.iva_retenido_por_clientes = redondear(_suma(emit, "iva_retenido"))
    if r.valor_actos_8 and not config.region_fronteriza:
        r.notas.append("Hay cobros al 8 % y el cliente no está configurado en región "
                       "fronteriza: revisa el estímulo (Decreto región fronteriza).")

    r.proporcion = calcular_proporcion(r, config)
    identificado = exentos = indistinto = no_deducible = CERO
    for m in reci:
        iva = (m.iva_16 + m.iva_8) * m.signo
        if not m.deducible:
            no_deducible += iva
            continue
        destino = asignaciones.get(m.uuid.upper(), "indistinto")
        if destino == "gravado":
            identificado += iva
        elif destino == "exento":
            exentos += iva
        else:
            indistinto += iva
    r.iva_pagado_total = redondear(identificado + exentos + indistinto + no_deducible)
    r.iva_pagado_no_deducible = redondear(no_deducible)
    r.iva_acreditable_identificado = redondear(identificado)
    r.iva_no_acreditable_exentos = redondear(exentos)
    r.iva_uso_indistinto = redondear(indistinto)
    r.iva_acreditable_proporcional = redondear(indistinto * r.proporcion)
    r.iva_acreditable = r.iva_acreditable_identificado + r.iva_acreditable_proporcional
    r.iva_retenido_a_terceros = redondear(_suma(reci, "iva_retenido"))

    a_cargo = r.iva_trasladado_cobrado - r.iva_retenido_por_clientes - r.iva_acreditable
    r.iva_a_cargo_del_mes = a_cargo
    r.saldo_favor_anterior = redondear(saldo_favor_anterior)
    if a_cargo > 0:
        r.saldo_favor_aplicado = min(r.saldo_favor_anterior, a_cargo)
        r.iva_a_pagar = a_cargo - r.saldo_favor_aplicado
        remanente = r.saldo_favor_anterior - r.saldo_favor_aplicado
    else:
        r.saldo_favor_del_mes = -a_cargo
        remanente = r.saldo_favor_anterior + r.saldo_favor_del_mes
    if opcion_saldo != "acreditar" and r.saldo_favor_del_mes > 0:
        # Art. 6o.: la devolución es sobre el TOTAL del saldo y lo solicitado ya no se acredita.
        r.saldo_favor_solicitado = remanente
        r.saldo_favor_siguiente = CERO
        if opcion_saldo == "compensacion":
            r.notas.append("Compensación: el Art. 6o. LIVA vigente sólo prevé acreditar o "
                           "pedir devolución (FUENTE POR CONFIRMAR). El saldo deja de arrastrarse.")
    else:
        r.saldo_favor_siguiente = remanente
    if r.saldo_favor_anterior:
        r.notas.append("El saldo a favor arrastrado no se actualiza por inflación "
                       "(DECISIÓN PROVISIONAL: conservador).")
    return r


def calcular_iva_periodos(
    anio: int,
    meses: Iterable[int],
    movimientos_por_mes: dict[int, list[MovimientoIVA]],
    saldo_inicial: Decimal = CERO,
    config: ConfigIVA | None = None,
    asignaciones: dict[str, Asignacion] | None = None,
    opciones_saldo: dict[int, OpcionSaldo] | None = None,
) -> list[ResultadoIVAMes]:
    """Varios meses seguidos: el saldo a favor de un mes se acredita en el siguiente (Art. 6o.)."""
    resultados = []
    saldo = saldo_inicial
    opciones_saldo = opciones_saldo or {}
    for mes in sorted(set(meses)):
        if not 1 <= mes <= 12:
            raise FiscalValidationError(f"Mes inválido: {mes}.")
        r = calcular_iva_mes(anio, mes, movimientos_por_mes.get(mes, []), saldo, config,
                             asignaciones, opciones_saldo.get(mes, "acreditar"))
        resultados.append(r)
        saldo = r.saldo_favor_siguiente
    return resultados


def resultado_iva_dict(r: ResultadoIVAMes) -> dict[str, object]:
    """Serialización para la API: importes como texto con dos decimales."""
    salida: dict[str, object] = {}
    for nombre, valor in vars(r).items():
        if isinstance(valor, Decimal):
            salida[nombre] = str(valor) if nombre == "proporcion" else f"{valor:.2f}"
        else:
            salida[nombre] = valor
    return salida
