"""
Historial de SBC y movimientos afiliatorios pendientes, alimentados por la ficha (P4-09).

CUÁNDO NACE UN MOVIMIENTO
-------------------------
Al guardar la ficha de un empleado de SUELDOS (los asimilados no cotizan al IMSS):

- **Alta** (empleado nuevo con `fecha_alta`): SBC en el historial (motivo `alta`) y un 08.
- **Reingreso** (tenía `fecha_baja` y ahora no, con `fecha_alta` posterior): SBC y un 08.
- **Baja** (`fecha_baja` nueva o distinta): un 02 con la causa de la ficha.
- **Cambio de SBC** (`salario_diario_integrado` distinto): SBC en el historial y un 07. Si el
  08 del alta sigue pendiente (aún no se presentó), se corrige ese 08 en vez de crear un 07:
  el IMSS todavía no conoce al trabajador.

Para un cambio de SBC con FECHA y MOTIVO propios (aumento, prestaciones, bimestre variable,
Art. 30 LSS) está `registrar_sbc`, que es lo que usa el endpoint dedicado.

DECISIÓN PROVISIONAL: la edición directa de la ficha no trae fecha de efecto, así que el 07
se fecha HOY (zona de la Ciudad de México). Es la lectura conservadora para el plazo de 5
días hábiles del Art. 34 fr. I LSS: nunca fecha el aviso antes de que existiera el dato.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.modelos.imss import HistorialSBC, MovimientoImss
from app.modelos.nucleo import Cliente
from app.schemas.empleado import EmpleadoCarteraSchema

ZONA = ZoneInfo("America/Mexico_City")
MOTIVOS_SBC = (
    "alta", "reingreso", "aumento", "prestaciones", "bimestre_variable", "edicion_ficha",
    "correccion",
)


def hoy() -> date:
    return datetime.now(ZONA).date()


def _fecha(v: Any) -> date | None:
    if v in (None, ""):
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _dec(v: Any) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v))


def historial_de(
    db: Session, cliente: Cliente, empleado_no: str | None = None
) -> list[HistorialSBC]:
    q = select(HistorialSBC).where(HistorialSBC.cliente_id == cliente.id)
    if empleado_no is not None:
        q = q.where(HistorialSBC.empleado_no == empleado_no)
    orden = (HistorialSBC.empleado_no, HistorialSBC.fecha, HistorialSBC.id)
    return list(db.scalars(q.order_by(*orden)))


def guardar_sbc(
    db: Session, cliente: Cliente, empleado_no: str, fecha: date, sbc: Decimal, *,
    tipo_salario: str, motivo: str, uid: str, salario_diario: Decimal | None = None,
    nota: str = "",
) -> HistorialSBC:
    """Upsert por (empleado, fecha): un día tiene un solo SBC."""
    if sbc <= 0:
        raise FiscalAgentError("El SBC debe ser mayor que cero.", status_code=422)
    if motivo not in MOTIVOS_SBC:
        raise FiscalAgentError(f"Motivo de SBC inválido: {motivo!r}.", status_code=422)
    fila = db.scalar(select(HistorialSBC).where(
        HistorialSBC.cliente_id == cliente.id, HistorialSBC.empleado_no == empleado_no,
        HistorialSBC.fecha == fecha))
    if fila is None:
        fila = HistorialSBC(cliente_id=cliente.id, empleado_no=empleado_no, fecha=fecha)
        db.add(fila)
    fila.sbc, fila.tipo_salario, fila.motivo = sbc, tipo_salario, motivo
    fila.salario_diario, fila.nota, fila.creado_por = salario_diario, nota, uid
    db.flush()
    return fila


def _pendiente(db: Session, cliente: Cliente, empleado_no: str, tipo: str) -> MovimientoImss | None:
    return db.scalar(select(MovimientoImss).where(
        MovimientoImss.cliente_id == cliente.id, MovimientoImss.empleado_no == empleado_no,
        MovimientoImss.tipo == tipo, MovimientoImss.estado == "pendiente",
    ).order_by(MovimientoImss.id.desc()))


def nuevo_movimiento(
    db: Session, cliente: Cliente, empleado_no: str, tipo: str, fecha: date, *, uid: str,
    origen: str, sbc: Decimal | None = None, tipo_salario: str = "0", causa_baja: str = "",
) -> MovimientoImss:
    mov = MovimientoImss(
        cliente_id=cliente.id, empleado_no=empleado_no, tipo=tipo, fecha=fecha, sbc=sbc,
        tipo_salario=tipo_salario, causa_baja=causa_baja, estado="pendiente", origen=origen,
        creado_por=uid,
    )
    db.add(mov)
    db.flush()
    return mov


def registrar_sbc(
    db: Session, cliente: Cliente, ficha: EmpleadoCarteraSchema, fecha: date, sbc: Decimal, *,
    tipo_salario: str, motivo: str, uid: str, nota: str = "",
) -> tuple[HistorialSBC, MovimientoImss | None]:
    """Cambio de SBC con fecha de efecto: historial + 07 (o corrige el 08 pendiente)."""
    if ficha.tipo_regimen != "02":
        raise FiscalAgentError(
            f"{ficha.empleado_no} es asimilado a salarios: no cotiza al IMSS.", status_code=422)
    alta = _pendiente(db, cliente, ficha.empleado_no, "08")
    if alta is not None and alta.fecha <= fecha and motivo != "bimestre_variable":
        # El IMSS aún no conoce al trabajador: se corrige el alta, no se avisa un 07.
        fila = guardar_sbc(db, cliente, ficha.empleado_no, alta.fecha, sbc,
                           tipo_salario=tipo_salario, motivo=alta.origen or "alta", uid=uid,
                           salario_diario=ficha.salario_diario, nota=nota)
        alta.sbc, alta.tipo_salario = sbc, tipo_salario
        db.flush()
        return fila, alta
    fila = guardar_sbc(db, cliente, ficha.empleado_no, fecha, sbc, tipo_salario=tipo_salario,
                       motivo=motivo, uid=uid, salario_diario=ficha.salario_diario, nota=nota)
    previo = _pendiente(db, cliente, ficha.empleado_no, "07")
    if previo is not None and previo.fecha == fecha:
        previo.sbc, previo.tipo_salario = sbc, tipo_salario
        db.flush()
        return fila, previo
    return fila, nuevo_movimiento(db, cliente, ficha.empleado_no, "07", fecha, uid=uid,
                                  origen=motivo, sbc=sbc, tipo_salario=tipo_salario)


def registrar_desde_ficha(
    db: Session, cliente: Cliente, previo: dict[str, Any] | None, nueva: EmpleadoCarteraSchema,
    uid: str,
) -> list[MovimientoImss]:
    """Compara la ficha anterior con la nueva y deja los movimientos pendientes que tocan."""
    if nueva.tipo_regimen != "02":
        return []
    no, creados = nueva.empleado_no, []
    sdi, tipo_sal = nueva.salario_diario_integrado, nueva.tipo_salario
    if not previo:
        if nueva.fecha_alta:
            guardar_sbc(db, cliente, no, nueva.fecha_alta, sdi, tipo_salario=tipo_sal,
                        motivo="alta", uid=uid, salario_diario=nueva.salario_diario)
            creados.append(nuevo_movimiento(db, cliente, no, "08", nueva.fecha_alta, uid=uid,
                                            origen="alta", sbc=sdi, tipo_salario=tipo_sal))
        if nueva.fecha_baja:
            creados.append(nuevo_movimiento(db, cliente, no, "02", nueva.fecha_baja, uid=uid,
                                            origen="baja", causa_baja=nueva.causa_baja))
        return creados

    baja_antes, baja_ahora = _fecha(previo.get("fecha_baja")), nueva.fecha_baja
    alta_antes = _fecha(previo.get("fecha_alta"))
    if baja_antes and not baja_ahora and nueva.fecha_alta and nueva.fecha_alta > baja_antes:
        guardar_sbc(db, cliente, no, nueva.fecha_alta, sdi, tipo_salario=tipo_sal,
                    motivo="reingreso", uid=uid, salario_diario=nueva.salario_diario)
        creados.append(nuevo_movimiento(db, cliente, no, "08", nueva.fecha_alta, uid=uid,
                                        origen="reingreso", sbc=sdi, tipo_salario=tipo_sal))
        return creados
    if not alta_antes and nueva.fecha_alta and _pendiente(db, cliente, no, "08") is None:
        guardar_sbc(db, cliente, no, nueva.fecha_alta, sdi, tipo_salario=tipo_sal,
                    motivo="alta", uid=uid, salario_diario=nueva.salario_diario)
        creados.append(nuevo_movimiento(db, cliente, no, "08", nueva.fecha_alta, uid=uid,
                                        origen="alta", sbc=sdi, tipo_salario=tipo_sal))
    if baja_ahora and baja_ahora != baja_antes:
        pendiente = _pendiente(db, cliente, no, "02")
        if pendiente is not None:
            pendiente.fecha, pendiente.causa_baja = baja_ahora, nueva.causa_baja
        else:
            creados.append(nuevo_movimiento(db, cliente, no, "02", baja_ahora, uid=uid,
                                            origen="baja", causa_baja=nueva.causa_baja))
    elif baja_ahora and nueva.causa_baja != (previo.get("causa_baja") or ""):
        pendiente = _pendiente(db, cliente, no, "02")
        if pendiente is not None:
            pendiente.causa_baja = nueva.causa_baja
    sdi_antes = _dec(previo.get("salario_diario_integrado"))
    if sdi_antes is not None and sdi_antes != sdi and not baja_ahora and nueva.fecha_alta:
        fecha = max(hoy(), nueva.fecha_alta)
        _, mov = registrar_sbc(db, cliente, nueva, fecha, sdi, tipo_salario=tipo_sal,
                               motivo="edicion_ficha", uid=uid)
        if mov is not None and mov not in creados:
            creados.append(mov)
    db.flush()
    return creados
