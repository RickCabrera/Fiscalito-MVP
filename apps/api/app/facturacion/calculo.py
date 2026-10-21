"""
Motor DETERMINÍSTICO de importes del CFDI 4.0 de ingreso/egreso y del complemento de pagos 2.0
(P5-04). El LLM no toca nada de aquí. REVISOR DE MOTOR.

REGLAS (Anexo 20, Guía de llenado del CFDI 4.0 y del complemento de recepción de pagos 2.0)
-------------------------------------------------------------------------------------------
Por concepto:
- `Importe` = Cantidad × ValorUnitario, redondeado a los decimales de la moneda (MXN: 2) con
  ROUND_HALF_UP (`app.redondeo.redondear`, decisión D2 del sistema).
- `Base` del impuesto = Importe − Descuento (debe ser > 0).
- `Importe` del traslado o retención = Base × TasaOCuota, redondeado a 2 decimales. El Anexo 20
  admite hasta 6 decimales dentro de los límites [(Base − ½·10⁻ᵈ)·Tasa truncado,
  (Base + ½·10⁻ᵈ)·Tasa redondeado hacia arriba]; con Base de 2 decimales, el valor redondeado a
  2 decimales siempre cae dentro de ese intervalo.
  # FUENTE POR CONFIRMAR: número de página/apartado de "Límites" en la Guía de llenado vigente.
- `Exento`: lleva Base, sin TasaOCuota ni Importe.
Por comprobante:
- Traslados agrupados por (Impuesto, TipoFactor, TasaOCuota): suma de Bases y de Importes.
- Retenciones agrupadas por Impuesto: suma de Importes.
- `TotalImpuestosTrasladados` = suma de traslados NO exentos (se omite si todos son exentos).
- `Total` = SubTotal − Descuento + TotalImpuestosTrasladados − TotalImpuestosRetenidos.
Complemento de pagos 2.0 (sólo MXN, EquivalenciaDR = 1):
- `ImpSaldoInsoluto` = ImpSaldoAnt − ImpPagado (≥ 0); `NumParcialidad` = pagos previos + 1.
- Impuestos del documento relacionado PROPORCIONALES al pago: BaseDR = Base × ImpPagado ÷
  Total del documento, ImporteDR = BaseDR × TasaOCuotaDR, ambos con 6 decimales (ROUND_HALF_UP).
- `ImpuestosP`: suma de los DR agrupados igual que arriba (6 decimales). `Totales`: las sumas de
  ImpuestosP por IVA 16 / 8 / 0 / exento y retenciones de IVA e ISR, a 2 decimales;
  `MontoTotalPagos` = suma de `Monto`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.exceptions import FiscalAgentError
from app.facturacion.catalogos import OBJETO_IMP, TASA_MAXIMA, TASAS_IVA_TRASLADO
from app.redondeo import redondear

CERO = Decimal("0.00")
SEIS = Decimal("0.000001")


def seis(v: Decimal) -> Decimal:
    return v.quantize(SEIS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ImpuestoEntrada:
    tipo: str  # traslado | retencion
    impuesto: str  # 001 ISR | 002 IVA
    tipo_factor: str = "Tasa"  # Tasa | Exento
    tasa: Decimal | None = None


@dataclass(frozen=True)
class ConceptoEntrada:
    clave_prod_serv: str
    cantidad: Decimal
    clave_unidad: str
    descripcion: str
    valor_unitario: Decimal
    objeto_imp: str = "02"
    descuento: Decimal = CERO
    impuestos: tuple[ImpuestoEntrada, ...] = ()
    unidad: str = ""
    no_identificacion: str = ""


@dataclass(frozen=True)
class ImpuestoCalculado:
    tipo: str
    impuesto: str
    tipo_factor: str
    tasa: Decimal | None
    base: Decimal
    importe: Decimal | None

    def a_dict(self) -> dict[str, str | None]:
        return {"tipo": self.tipo, "impuesto": self.impuesto, "tipo_factor": self.tipo_factor,
                "tasa": f"{self.tasa:.6f}" if self.tasa is not None else None,
                "base": str(self.base),
                "importe": str(self.importe) if self.importe is not None else None}


@dataclass(frozen=True)
class ConceptoCalculado:
    entrada: ConceptoEntrada
    importe: Decimal
    impuestos: tuple[ImpuestoCalculado, ...]


@dataclass
class Comprobante:
    conceptos: list[ConceptoCalculado]
    subtotal: Decimal
    descuento: Decimal
    traslados: list[ImpuestoCalculado] = field(default_factory=list)
    retenciones: list[ImpuestoCalculado] = field(default_factory=list)
    total_traslados: Decimal | None = None
    total_retenciones: Decimal | None = None
    total: Decimal = CERO
    # Agrupación de retenciones por (impuesto, tasa) con su base: la necesita el complemento de
    # pago (RetencionDR lleva BaseDR y TasaOCuotaDR) aunque el comprobante sólo declare Importe.
    retenciones_detalle: list[ImpuestoCalculado] = field(default_factory=list)


def _error(msg: str) -> FiscalAgentError:
    return FiscalAgentError(msg, 422)


def _impuesto(i: ImpuestoEntrada, base: Decimal, n: int) -> ImpuestoCalculado:
    if i.tipo not in ("traslado", "retencion") or i.impuesto not in ("001", "002"):
        raise _error(f"Concepto {n}: impuesto no soportado ({i.tipo} {i.impuesto}).")
    if i.tipo == "traslado" and i.impuesto != "002":
        raise _error(f"Concepto {n}: sólo se traslada IVA (002).")
    if i.tipo_factor == "Exento":
        if i.tipo != "traslado":
            raise _error(f"Concepto {n}: una retención no puede ser exenta.")
        return ImpuestoCalculado(i.tipo, i.impuesto, "Exento", None, base, None)
    if i.tipo_factor != "Tasa" or i.tasa is None:
        raise _error(f"Concepto {n}: falta la tasa del impuesto {i.impuesto}.")
    tasa = Decimal(i.tasa)
    tope = TASA_MAXIMA[(i.tipo, i.impuesto)]
    if tasa < 0 or tasa > tope or tasa != tasa.quantize(SEIS):
        raise _error(f"Concepto {n}: tasa {tasa} fuera de rango (0 a {tope}, seis decimales).")
    if (i.tipo, i.impuesto) == ("traslado", "002") and tasa not in TASAS_IVA_TRASLADO:
        raise _error(f"Concepto {n}: tasa de IVA {tasa} fuera del catálogo c_TasaOCuota "
                     "(0.000000, 0.080000 o 0.160000).")
    return ImpuestoCalculado(i.tipo, i.impuesto, "Tasa", tasa.quantize(SEIS), base,
                             redondear(base * tasa))


def concepto(c: ConceptoEntrada, n: int = 1) -> ConceptoCalculado:
    """Importe e impuestos de un concepto."""
    if c.cantidad <= 0 or c.valor_unitario < 0:
        raise _error(f"Concepto {n}: la cantidad debe ser mayor a cero y el valor no negativo.")
    if c.objeto_imp not in OBJETO_IMP:
        raise _error(f"Concepto {n}: ObjetoImp {c.objeto_imp} no soportado (01, 02 o 03).")
    importe = redondear(c.cantidad * c.valor_unitario)
    descuento = redondear(c.descuento)
    if descuento < 0 or descuento > importe:
        raise _error(f"Concepto {n}: el descuento no puede exceder el importe.")
    if c.objeto_imp != "02":
        if c.impuestos:
            raise _error(f"Concepto {n}: con ObjetoImp {c.objeto_imp} no se desglosan "
                         "impuestos.")
        return ConceptoCalculado(c, importe, ())
    if not c.impuestos:
        raise _error(f"Concepto {n}: con ObjetoImp 02 hay que capturar al menos un impuesto.")
    base = importe - descuento
    if base <= 0:
        raise _error(f"Concepto {n}: la base del impuesto debe ser mayor a cero.")
    vistos = set()
    for i in c.impuestos:
        llave = (i.tipo, i.impuesto)
        if llave in vistos:
            raise _error(f"Concepto {n}: impuesto repetido ({i.tipo} {i.impuesto}).")
        vistos.add(llave)
    return ConceptoCalculado(c, importe, tuple(_impuesto(i, base, n) for i in c.impuestos))


def _agrupar(impuestos: list[ImpuestoCalculado], por_tasa: bool) -> list[ImpuestoCalculado]:
    grupos: dict[tuple, list[ImpuestoCalculado]] = {}
    for i in impuestos:
        llave = (i.impuesto, i.tipo_factor, i.tasa) if por_tasa else (i.impuesto,)
        grupos.setdefault(llave, []).append(i)
    salida = []
    for g in grupos.values():
        primero = g[0]
        importes = [i.importe for i in g if i.importe is not None]
        salida.append(ImpuestoCalculado(
            primero.tipo, primero.impuesto, primero.tipo_factor,
            primero.tasa if por_tasa else None, sum((i.base for i in g), start=CERO),
            sum(importes, start=CERO) if importes else None))
    return salida


def comprobante(conceptos: list[ConceptoEntrada]) -> Comprobante:
    """Los importes del comprobante completo."""
    if not conceptos:
        raise _error("Captura al menos un concepto.")
    calc = [concepto(c, n) for n, c in enumerate(conceptos, start=1)]
    impuestos = [i for c in calc for i in c.impuestos]
    traslados = _agrupar([i for i in impuestos if i.tipo == "traslado"], True)
    ret_detalle = _agrupar([i for i in impuestos if i.tipo == "retencion"], True)
    retenciones = _agrupar([i for i in impuestos if i.tipo == "retencion"], False)
    subtotal = sum((c.importe for c in calc), start=CERO)
    descuento = sum((redondear(c.entrada.descuento) for c in calc), start=CERO)
    no_exentos = [t.importe for t in traslados if t.importe is not None]
    total_t = sum(no_exentos, start=CERO) if no_exentos else None
    total_r = sum((r.importe or CERO for r in retenciones), start=CERO) if retenciones else None
    total = subtotal - descuento + (total_t or CERO) - (total_r or CERO)
    if total < 0:
        raise _error("El total del comprobante no puede ser negativo.")
    return Comprobante(calc, subtotal, descuento, traslados, retenciones, total_t, total_r,
                       total, ret_detalle)


# ── complemento de pagos 2.0 ──


@dataclass(frozen=True)
class DocumentoPagado:
    """Una factura PPD a la que se aplica (parte de) un pago."""

    uuid: str
    serie: str
    folio: str
    total: Decimal
    saldo_anterior: Decimal
    num_parcialidad: int
    importe_pagado: Decimal
    # Del comprobante original: traslados por (impuesto, factor, tasa) y retenciones por
    # (impuesto, tasa), cada uno con su base.
    traslados: tuple[ImpuestoCalculado, ...] = ()
    retenciones: tuple[ImpuestoCalculado, ...] = ()

    @property
    def objeto_imp(self) -> str:
        return "02" if (self.traslados or self.retenciones) else "01"


@dataclass
class DocumentoCalculado:
    doc: DocumentoPagado
    saldo_insoluto: Decimal
    traslados: list[ImpuestoCalculado]
    retenciones: list[ImpuestoCalculado]


@dataclass
class Pago:
    documentos: list[DocumentoCalculado]
    monto: Decimal
    traslados_p: list[ImpuestoCalculado]
    retenciones_p: list[ImpuestoCalculado]
    totales: dict[str, Decimal]


def _proporcional(i: ImpuestoCalculado, factor: Decimal) -> ImpuestoCalculado:
    base = seis(i.base * factor)
    importe = seis(base * i.tasa) if i.tasa is not None and i.tipo_factor == "Tasa" else None
    return ImpuestoCalculado(i.tipo, i.impuesto, i.tipo_factor, i.tasa, base, importe)


def documento(d: DocumentoPagado) -> DocumentoCalculado:
    if d.importe_pagado <= 0:
        raise _error(f"El importe pagado de {d.uuid} debe ser mayor a cero.")
    if d.importe_pagado != redondear(d.importe_pagado):
        raise _error("El importe pagado va con dos decimales.")
    if d.importe_pagado > d.saldo_anterior:
        raise _error(f"El pago a {d.uuid} ({d.importe_pagado}) excede su saldo "
                     f"({d.saldo_anterior}).")
    if d.total <= 0:
        raise _error(f"La factura {d.uuid} no tiene total que pagar.")
    factor = d.importe_pagado / d.total
    return DocumentoCalculado(
        d, d.saldo_anterior - d.importe_pagado,
        [_proporcional(t, factor) for t in d.traslados],
        [_proporcional(r, factor) for r in d.retenciones])


def _sumar(grupo: list[ImpuestoCalculado], por_tasa: bool) -> list[ImpuestoCalculado]:
    salida = _agrupar(grupo, por_tasa)
    return [ImpuestoCalculado(i.tipo, i.impuesto, i.tipo_factor, i.tasa, seis(i.base),
                              seis(i.importe) if i.importe is not None else None)
            for i in salida]


def pago(documentos: list[DocumentoPagado]) -> Pago:
    """El nodo `Pago` (un solo pago, MXN) con sus documentos relacionados y los `Totales`."""
    if not documentos:
        raise _error("El pago debe aplicarse al menos a una factura.")
    if len({d.uuid for d in documentos}) != len(documentos):
        raise _error("Una factura aparece dos veces en el mismo pago.")
    calc = [documento(d) for d in documentos]
    traslados_p = _sumar([t for c in calc for t in c.traslados], True)
    retenciones_p = _sumar([r for c in calc for r in c.retenciones], False)
    monto = sum((d.importe_pagado for d in documentos), start=CERO)
    totales: dict[str, Decimal] = {"MontoTotalPagos": redondear(monto)}
    for t in traslados_p:
        if t.tipo_factor == "Exento":
            totales["TotalTrasladosBaseIVAExento"] = redondear(t.base)
            continue
        sufijo = {Decimal("0.160000"): "16", Decimal("0.080000"): "8",
                  Decimal("0.000000"): "0"}.get(t.tasa or CERO)
        if sufijo is None:
            raise _error(f"Tasa de IVA {t.tasa} sin total en el complemento de pagos.")
        totales[f"TotalTrasladosBaseIVA{sufijo}"] = redondear(t.base)
        totales[f"TotalTrasladosImpuestoIVA{sufijo}"] = redondear(t.importe or CERO)
    for r in retenciones_p:
        nombre = "TotalRetencionesIVA" if r.impuesto == "002" else "TotalRetencionesISR"
        totales[nombre] = redondear(r.importe or CERO)
    return Pago(calc, monto, traslados_p, retenciones_p, totales)
