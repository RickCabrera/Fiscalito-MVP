"""
De la bóveda a los cálculos (plan P, P1-06).

`facturas_para_calculo(db, cliente, desde, hasta)` devuelve los CFDI del periodo **ya en la
forma del esquema `CFDI`** de `app/schemas/fiscal.py`, que es lo que reciben todos los
endpoints de cálculo (pre-declaración, anual, DIOT, retenciones, multi-periodo, estado de
cuenta). Aquí no se calcula ningún impuesto: sólo se acomodan los importes que el XML trae.

REGLAS (las mismas que ya aplicaba el front con `facturasFiscales`)
-------------------------------------------------------------------
- **Cancelados fuera**: se filtra con `servicio.comprobantes_vigentes` (P1-03). Los que no
  se han verificado (`desconocido`) sí cuentan.
- **Nómina fuera**: un CFDI tipo `N` lo emite el patrón a su trabajador; no es ingreso ni
  gasto del contribuyente en estos cálculos y `TipoFactura` no lo conoce (sería un 422).
  Se cuenta aparte en el resumen para que la pantalla diga cuántos se dejaron fuera.
- **Complementos de pago (P)**: uno por cada `DoctoRelacionado`, con `uuid_relacionado` y
  `monto_pago = ImpPagado`. El motor (`clasificar_facturas`) los cruza con la factura PPD
  original; por eso, si el original PPD es de un periodo ANTERIOR, va en `relacionados`
  (sigue sin sumar por sí mismo: el motor ignora los PPD que no son pago). Si un P paga
  varias facturas, cada documento sale con el UUID del pago seguido de `#1`, `#2`…: el front
  sólo tomaba el primero y perdía los demás.
- **Moneda**: los importes se pasan a pesos con el `TipoCambio` del propio CFDI (Anexo 20:
  el tipo de cambio "conforme a la moneda registrada", contra MXN). Un CFDI en moneda
  extranjera sin `TipoCambio` va tal cual y se reporta en `advertencias`.
- `fecha` es la del comprobante (también la del filtro del periodo) para I/E/T. **Para un
  pago es la `FechaPago` de cada pago del complemento** (§D-C1, revisión P2): el ingreso y el
  IVA se causan al cobrar (arts. 1-B LIVA y 102 LISR), así que un cobro del 31 de octubre
  timbrado el 3 de noviembre es de octubre, y un complemento con pagos de fechas distintas
  reparte cada documento en el periodo de su pago.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.fechas_pago import (
    VENTANA_ANTES,
    VENTANA_DESPUES,
    fecha_de_pago,
    pagos_por_fecha,
)
from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.schemas.fiscal import CFDI

# Los tipos que el motor acepta (`TipoFactura`). `N` nunca: ver el docstring.
TIPOS_CALCULO: tuple[str, ...] = ("I", "E", "P", "T")
# XXX = "sin moneda" (catálogo c_Moneda), propio de los complementos de pago y traslados.
MONEDAS_SIN_CONVERSION = {"MXN", "XXX", ""}
CENTAVO = Decimal("0.01")
LOTE_IN = 500


@dataclass
class FacturasCalculo:
    """Lo que la bóveda le da a un cálculo."""

    facturas: list[CFDI] = field(default_factory=list)
    relacionados: list[CFDI] = field(default_factory=list)
    resumen: dict[str, Any] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)

    def todas(self) -> list[CFDI]:
        """Las del periodo más los originales PPD de otros periodos (para el motor)."""
        return [*self.facturas, *self.relacionados]


def rango_del_periodo(
    anio: int, mes: int | None = None, bimestre: int | None = None
) -> tuple[date, date]:
    """`(desde, hasta)` inclusivos de un mes, un bimestre o el ejercicio completo."""
    if bimestre is not None:
        inicio_mes, meses = 2 * bimestre - 1, 2
    elif mes is not None:
        inicio_mes, meses = mes, 1
    else:
        return date(anio, 1, 1), date(anio, 12, 31)
    desde = date(anio, inicio_mes, 1)
    fin_mes = inicio_mes + meses
    siguiente = date(anio + 1, 1, 1) if fin_mes > 12 else date(anio, fin_mes, 1)
    return desde, siguiente - timedelta(days=1)


def _dec(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor).strip()) if valor not in (None, "") else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _pesos(valor: Decimal, tc: Decimal) -> float:
    return float((valor * tc).quantize(CENTAVO, rounding=ROUND_HALF_UP))


def _tipo_cambio(c: Comprobante, advertencias: list[str]) -> Decimal:
    moneda = (c.moneda or "").upper()
    if moneda in MONEDAS_SIN_CONVERSION:
        return Decimal("1")
    if c.tipo_cambio:
        return Decimal(c.tipo_cambio)
    advertencias.append(
        f"{c.uuid}: viene en {moneda} sin TipoCambio; sus importes van sin convertir a pesos."
    )
    return Decimal("1")


def _primer_concepto(c: Comprobante) -> dict[str, Any]:
    conceptos = (c.datos or {}).get("conceptos") or []
    return conceptos[0] if conceptos else {}


def a_cfdi(c: Comprobante, advertencias: list[str]) -> CFDI:
    """Un comprobante I/E/T (o PPD original) en la forma del esquema de cálculo."""
    tc = _tipo_cambio(c, advertencias)
    concepto = _primer_concepto(c)
    return CFDI(
        uuid=c.uuid,
        fecha=c.fecha.date(),
        tipo=c.tipo,
        rfc_emisor=c.rfc_emisor,
        rfc_receptor=c.rfc_receptor,
        subtotal=_pesos(c.subtotal, tc),
        total=_pesos(c.total, tc),
        iva_trasladado=_pesos(c.iva_trasladado, tc),
        iva_retenido=_pesos(c.iva_retenido, tc),
        isr_retenido=_pesos(c.isr_retenido, tc),
        descuento=_pesos(c.descuento, tc),
        uso_cfdi=c.uso_cfdi or "G03",
        descripcion=str(concepto.get("Descripcion", "")),
        clave_prod_serv=str(concepto.get("ClaveProdServ", "")),
        metodo_pago=c.metodo_pago or "PUE",
    )


def pagos_a_cfdi(
    c: Comprobante, originales: dict[str, Comprobante], advertencias: list[str],
    desde: date | None = None, hasta: date | None = None,
) -> list[CFDI]:
    """
    Un complemento de pago → un CFDI tipo P por cada documento que paga, con la fecha de SU
    pago (`FechaPago`). Con `desde`/`hasta` sólo los documentos cuyo pago cae en el rango.
    """
    complemento = (c.datos or {}).get("pagos") or {}
    documentos: list[tuple[dict[str, Any], dict[str, Any]]] = [
        (p, d) for p in complemento.get("pagos", []) for d in p.get("documentos", [])
    ]

    def en_rango(f: date) -> bool:
        return (desde is None or f >= desde) and (hasta is None or f <= hasta)

    base = {
        "tipo": "P", "rfc_emisor": c.rfc_emisor,
        "rfc_receptor": c.rfc_receptor, "subtotal": 0.0, "total": 0.0,
        "uso_cfdi": c.uso_cfdi or "CP01", "metodo_pago": "PUE",
    }
    if not documentos:
        pagos = complemento.get("pagos") or []
        fecha = fecha_de_pago(pagos[0], c.fecha.date()) if pagos else c.fecha.date()
        if not en_rango(fecha):
            return []
        return [CFDI(uuid=c.uuid, fecha=fecha,
                     monto_pago=float(_dec(complemento.get("monto_total"))), **base)]

    salida = []
    for n, (pago, doc) in enumerate(documentos, start=1):
        fecha = fecha_de_pago(pago, c.fecha.date())
        if not en_rango(fecha):
            continue
        relacionado = str(doc.get("IdDocumento", "")).upper() or None
        monto = _dec(doc.get("ImpPagado"))
        if monto == 0 and len(documentos) == 1:
            monto = _dec(pago.get("Monto"))  # Pagos 1.0 permite omitir ImpPagado
        moneda_dr = str(doc.get("MonedaDR", "MXN")).upper()
        tc = Decimal("1")
        if moneda_dr not in MONEDAS_SIN_CONVERSION:
            original = originales.get(relacionado or "")
            if original is not None and original.tipo_cambio:
                # Mismo tipo de cambio que el original: la proporción pagada no cambia.
                tc = Decimal(original.tipo_cambio)
            else:
                advertencias.append(
                    f"{c.uuid}: pago en {moneda_dr} sin factura original con TipoCambio "
                    "en la bóveda; el monto va sin convertir."
                )
        uuid = c.uuid if len(documentos) == 1 else f"{c.uuid}#{n}"
        salida.append(CFDI(uuid=uuid, uuid_relacionado=relacionado, fecha=fecha,
                           monto_pago=_pesos(monto, tc), **base))
    return salida


def _en_lotes(valores: list[str]) -> Iterable[list[str]]:
    for i in range(0, len(valores), LOTE_IN):
        yield valores[i:i + LOTE_IN]


def facturas_para_calculo(
    db: Session,
    cliente: Cliente,
    desde: date,
    hasta: date,
    tipos: Iterable[str] = TIPOS_CALCULO,
) -> FacturasCalculo:
    """Los CFDI vigentes del periodo (inclusivo) listos para el motor. Ver el docstring."""
    tipos = {t.upper() for t in tipos} & set(TIPOS_CALCULO)
    cond = [
        Comprobante.cliente_id == cliente.id,
        Comprobante.fecha >= datetime.combine(desde, time.min),
        Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), time.min),
    ]
    vigentes = list(db.scalars(
        comprobantes_vigentes(select(Comprobante).where(*cond, Comprobante.tipo != "P"))
        .order_by(Comprobante.fecha, Comprobante.id)
    ))
    # Los P entran por su FechaPago (§D-C1): ventana amplia por fecha de emisión y filtro
    # por pago. Uno emitido en el rango con todos sus pagos fuera no cuenta en el periodo.
    if "P" in tipos:
        candidatos = db.scalars(comprobantes_vigentes(select(Comprobante).where(
            Comprobante.cliente_id == cliente.id, Comprobante.tipo == "P",
            Comprobante.fecha >= datetime.combine(desde - VENTANA_ANTES, time.min),
            Comprobante.fecha < datetime.combine(hasta + VENTANA_DESPUES, time.min),
        )).order_by(Comprobante.fecha, Comprobante.id))
        vigentes.extend(
            p for p in candidatos
            if any(desde <= f <= hasta for f in pagos_por_fecha(p))
            or (not pagos_por_fecha(p) and desde <= p.fecha.date() <= hasta))
        vigentes.sort(key=lambda c: (c.fecha, c.id))
    cancelados = db.scalar(
        select(func.count(Comprobante.id)).where(*cond, Comprobante.estatus_sat == "cancelado")
    ) or 0
    usados = [c for c in vigentes if c.tipo in tipos]
    nomina = sum(1 for c in vigentes if c.tipo == "N")

    # Originales PPD de otros periodos que los pagos del periodo liquidan.
    en_periodo = {c.uuid for c in vigentes}
    buscados = sorted({
        str(u).upper()
        for c in usados if c.tipo == "P"
        for u in ((c.datos or {}).get("pagos") or {}).get("uuids_relacionados", [])
    } - en_periodo)
    externos: list[Comprobante] = []
    for lote in _en_lotes(buscados):
        externos.extend(db.scalars(comprobantes_vigentes(select(Comprobante).where(
            Comprobante.cliente_id == cliente.id, Comprobante.uuid.in_(lote),
            Comprobante.metodo_pago == "PPD", Comprobante.tipo.in_(("I", "E")),
        )).order_by(Comprobante.fecha, Comprobante.id)))

    originales = {c.uuid: c for c in [*vigentes, *externos] if c.tipo in ("I", "E")}
    resultado = FacturasCalculo()
    for c in usados:
        if c.tipo == "P":
            resultado.facturas.extend(pagos_a_cfdi(c, originales, resultado.advertencias,
                                                   desde, hasta))
        else:
            resultado.facturas.append(a_cfdi(c, resultado.advertencias))
    resultado.relacionados = [a_cfdi(c, resultado.advertencias) for c in externos]

    direcciones = Counter(c.direccion for c in usados)
    resultado.resumen = {
        "comprobantes": len(usados),
        "emitidos": direcciones.get("emitido", 0),
        "recibidos": direcciones.get("recibido", 0),
        "por_tipo": dict(sorted(Counter(c.tipo for c in usados).items())),
        "cancelados_excluidos": int(cancelados),
        "nomina_excluidos": nomina,
        "relacionados_fuera_del_periodo": len(externos),
    }
    return resultado
