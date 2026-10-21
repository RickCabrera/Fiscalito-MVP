"""
Flujo de efectivo de los CFDI de la bóveda (P3-02, P3-03).

Un CFDI cuenta en el mes en que se cobra o se paga (Art. 1o.-B LIVA; Arts. 102 y 105 LISR):

- **PUE** (o sin método, como las notas de crédito): en el mes de su fecha.
- **PPD**: en el mes de cada `FechaPago` de los complementos de recepción de pagos (tipo P)
  que lo relacionan, en la proporción `ImpPagado / Total` del documento.

Sólo se leen comprobantes vigentes (`comprobantes_vigentes`, P1-03): un cancelado no cuenta.
Los importes en moneda extranjera se llevan a pesos con el `TipoCambio` del CFDI original
(DECISIÓN PROVISIONAL: el Art. 20 CFF manda el tipo de cambio del día del pago para los
cobros en moneda extranjera; el parser no conserva el `TipoCambioP` por documento).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente

UNO = Decimal("1")


@dataclass(frozen=True)
class Efectivo:
    """Un CFDI (I o E) cobrado o pagado en el mes, con la proporción que cuenta."""

    comprobante: Comprobante
    proporcion: Decimal
    fecha: date
    origen: str  # "PUE" | "PPD"

    @property
    def factor_pesos(self) -> Decimal:
        """Proporción × tipo de cambio (1 en MXN)."""
        tc = self.comprobante.tipo_cambio
        if self.comprobante.moneda not in ("MXN", "XXX", "") and tc:
            return self.proporcion * tc
        return self.proporcion


def _dec(v: object) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _rango_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    inicio = datetime(anio, mes, 1)
    fin = datetime(anio + 1, 1, 1) if mes == 12 else datetime(anio, mes + 1, 1)
    return inicio, fin


def flujo_del_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> list[Efectivo]:
    """Los I y E del cliente que cuentan en (anio, mes) por flujo de efectivo."""
    inicio, fin = _rango_mes(anio, mes)
    base = comprobantes_vigentes(select(Comprobante).where(Comprobante.cliente_id == cliente.id))
    salida: list[Efectivo] = []
    directos = db.scalars(base.where(
        Comprobante.tipo.in_(("I", "E")), Comprobante.metodo_pago != "PPD",
        Comprobante.fecha >= inicio, Comprobante.fecha < fin,
    ).order_by(Comprobante.fecha, Comprobante.uuid))
    for c in directos:
        salida.append(Efectivo(c, UNO, c.fecha.date(), "PUE"))

    # Complementos: el CFDI P se emite en o después de la fecha de pago (hasta el día 5 del
    # mes siguiente, regla 2.7.1.32 RMF); se buscan hasta 3 meses después para tolerar
    # complementos tardíos.
    pagos = db.scalars(base.where(
        Comprobante.tipo == "P", Comprobante.fecha >= inicio,
        Comprobante.fecha < fin + timedelta(days=93),
    ).order_by(Comprobante.fecha, Comprobante.uuid))
    for p in pagos:
        for pago in (p.datos or {}).get("pagos", {}).get("pagos", []):
            try:
                fecha_pago = datetime.fromisoformat(str(pago.get("FechaPago", ""))[:19])
            except ValueError:
                fecha_pago = p.fecha
            if not inicio <= fecha_pago < fin:
                continue
            for doc in pago.get("documentos", []):
                original = db.scalar(base.where(
                    Comprobante.uuid == str(doc.get("IdDocumento", "")).upper(),
                    Comprobante.tipo.in_(("I", "E")),
                ))
                if original is None or not original.total:
                    continue
                prop = min(_dec(doc.get("ImpPagado")) / original.total, UNO)
                if prop > 0:
                    salida.append(Efectivo(original, prop, fecha_pago.date(), "PPD"))
    return salida


def flujo_rango(
    db: Session, cliente: Cliente, anio: int, meses: range
) -> dict[int, list[Efectivo]]:
    """`flujo_del_mes` para varios meses del mismo año."""
    return {m: flujo_del_mes(db, cliente, anio, m) for m in meses}


def nominas_del_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> list[Comprobante]:
    """CFDI de nómina (N) EMITIDOS por el cliente con fecha de pago en (anio, mes)."""
    inicio, fin = _rango_mes(anio, mes)
    candidatos = db.scalars(comprobantes_vigentes(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.tipo == "N",
        Comprobante.direccion == "emitido",
        Comprobante.fecha >= inicio - timedelta(days=40),
        Comprobante.fecha < fin + timedelta(days=40),
    )).order_by(Comprobante.fecha, Comprobante.uuid))
    salida = []
    for c in candidatos:
        valor = (c.datos or {}).get("nomina", {}).get("FechaPago") or c.fecha.date().isoformat()
        try:
            fp = date.fromisoformat(str(valor)[:10])
        except ValueError:
            fp = c.fecha.date()
        if inicio <= datetime.combine(fp, time.min) < fin:
            salida.append(c)
    return salida
