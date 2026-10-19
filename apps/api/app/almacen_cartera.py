"""
La cartera del despacho en SQL: clientes, empleados y dispositivos. (P0-01)

EL BACKEND ES EL ÚNICO DUEÑO DEL DATO
-------------------------------------
Hasta P0-01 la cartera vivía en Firestore y había dos caminos para escribirla: el
navegador directo (`carteraFirestore.ts`, el default) y este backend con
`firebase-admin` detrás de `VITE_CARTERA_BACKEND` (R-07, apagado). Ahora sólo hay uno:
`/api/v1/cartera/*` sobre las tablas de `app/modelos/nucleo.py`. Lo que había en
Firestore se trae una vez con `scripts/migrar_firestore.py`.

LA TENENCIA NO SE DECIDE AQUÍ
-----------------------------
Las funciones de este módulo reciben un `Cliente` **ya resuelto** por
`cliente_o_404` (`app/tenancy.py`), o un `despacho_id` que sale del contexto
autenticado. Nunca buscan un cliente por su clave sin filtrar por despacho.

GUARDAR ES *MERGE*, NO REEMPLAZO
--------------------------------
Era la semántica de Firestore (`set(merge=True)`) y se conserva: un documento escrito
por una versión anterior de la app —o traído por la migración— puede tener campos que
este esquema todavía no conoce, y editarlo no debe borrarlos en silencio.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente, Dispositivo, Empleado

# Cotas de lo que un despacho puede guardar por la API. No son reglas de negocio: sin
# tope, un bucle de `curl` con un token válido llena la base. Se aplican sólo a ALTAS
# (editar uno existente nunca rebota) y la migración no las aplica: traer lo que ya
# existía sin perder nada pesa más que la cota.
MAX_CLIENTES_POR_DESPACHO = 500
MAX_EMPLEADOS_POR_CLIENTE = 2_000
MAX_DISPOSITIVOS_POR_CLIENTE = 100

# Largo de las columnas indexadas que se copian de `datos` (ver `nucleo.py`). El valor
# completo siempre queda en `datos`; la columna sólo sirve para buscar.
_LARGO_NOMBRE = 300
_LARGO_RFC = 13


def _fusionar(previo: dict[str, Any] | None, nuevo: dict[str, Any]) -> dict[str, Any]:
    """`{**previo, **nuevo}` sin la llave `id`: el id ya es la clave de la fila."""
    base = dict(previo or {})
    base.update(nuevo)
    base.pop("id", None)
    return base


def _texto(valor: object, largo: int) -> str:
    return str(valor or "")[:largo]


# ── Clientes ──────────────────────────────────────────────────


def buscar_cliente(db: Session, despacho_id: str, clave: str) -> Cliente | None:
    """El cliente `clave` de ESE despacho, o `None`. Uso interno y de la migración."""
    return db.scalar(
        select(Cliente).where(Cliente.despacho_id == despacho_id, Cliente.clave == clave)
    )


def documento_cliente(cliente: Cliente) -> dict[str, Any]:
    """El cliente como lo devuelve la API: sus `datos` más el `id` público."""
    return {**(cliente.datos or {}), "id": cliente.clave}


def crear_cliente(
    db: Session, despacho_id: str, clave: str, datos: dict[str, Any], *, con_tope: bool = True
) -> Cliente:
    """Alta de un cliente que no existe. Con `con_tope`, respeta la cota del despacho."""
    if con_tope:
        cuantos = db.scalar(
            select(func.count()).select_from(Cliente).where(Cliente.despacho_id == despacho_id)
        )
        if (cuantos or 0) >= MAX_CLIENTES_POR_DESPACHO:
            raise FiscalAgentError(
                f"Llegaste al tope de {MAX_CLIENTES_POR_DESPACHO} clientes.", status_code=409
            )
    cliente = Cliente(despacho_id=despacho_id, clave=clave)
    actualizar_cliente(cliente, datos)
    db.add(cliente)
    db.flush()
    return cliente


def actualizar_cliente(cliente: Cliente, datos: dict[str, Any]) -> None:
    """Fusiona `datos` en el cliente y refresca las columnas que se consultan."""
    cliente.datos = _fusionar(cliente.datos, datos)
    cliente.nombre = _texto(cliente.datos.get("nombre"), _LARGO_NOMBRE)
    cliente.rfc = _texto(cliente.datos.get("rfc"), _LARGO_RFC)


def borrar_cliente(db: Session, cliente: Cliente) -> None:
    """
    Baja del cliente con sus empleados y dispositivos.

    Los hijos se borran EXPLÍCITAMENTE antes del cliente, además del `ON DELETE CASCADE`
    de las llaves foráneas: SQLite sólo aplica la cascada con `PRAGMA foreign_keys=ON`,
    y una conexión sin él dejaría empleados huérfanos —con su salario y su NSS— que
    reaparecerían al recrear un cliente con la misma clave.
    """
    db.execute(delete(Empleado).where(Empleado.cliente_id == cliente.id))
    db.execute(delete(Dispositivo).where(Dispositivo.cliente_id == cliente.id))
    db.delete(cliente)
    db.flush()


# ── Empleados ─────────────────────────────────────────────────


def empleados_de(db: Session, cliente: Cliente) -> list[Empleado]:
    return list(
        db.scalars(
            select(Empleado)
            .where(Empleado.cliente_id == cliente.id)
            .order_by(Empleado.empleado_no)
        )
    )


def buscar_empleado(db: Session, cliente: Cliente, empleado_no: str) -> Empleado | None:
    return db.scalar(
        select(Empleado).where(
            Empleado.cliente_id == cliente.id, Empleado.empleado_no == empleado_no
        )
    )


def guardar_empleado(
    db: Session,
    cliente: Cliente,
    empleado_no: str,
    datos: dict[str, Any],
    *,
    con_tope: bool = True,
) -> Empleado:
    """Alta o edición (merge) del empleado `empleado_no` del cliente."""
    empleado = buscar_empleado(db, cliente, empleado_no)
    if empleado is None:
        if con_tope:
            cuantos = db.scalar(
                select(func.count())
                .select_from(Empleado)
                .where(Empleado.cliente_id == cliente.id)
            )
            if (cuantos or 0) >= MAX_EMPLEADOS_POR_CLIENTE:
                raise FiscalAgentError(
                    f"Llegaste al tope de {MAX_EMPLEADOS_POR_CLIENTE} empleados.",
                    status_code=409,
                )
        empleado = Empleado(cliente_id=cliente.id, empleado_no=empleado_no, datos={})
        db.add(empleado)
    empleado.datos = _fusionar(empleado.datos, datos)
    db.flush()
    return empleado


# ── Dispositivos ──────────────────────────────────────────────


def dispositivos_de(db: Session, cliente: Cliente) -> list[Dispositivo]:
    return list(
        db.scalars(
            select(Dispositivo)
            .where(Dispositivo.cliente_id == cliente.id)
            .order_by(Dispositivo.creado_en, Dispositivo.clave)
        )
    )


def buscar_dispositivo(db: Session, cliente: Cliente, clave: str) -> Dispositivo | None:
    return db.scalar(
        select(Dispositivo).where(Dispositivo.cliente_id == cliente.id, Dispositivo.clave == clave)
    )


def documento_dispositivo(dispositivo: Dispositivo) -> dict[str, Any]:
    return {**(dispositivo.datos or {}), "id": dispositivo.clave}


def guardar_dispositivo(
    db: Session,
    cliente: Cliente,
    clave: str,
    datos: dict[str, Any],
    *,
    con_tope: bool = True,
) -> Dispositivo:
    """Alta o edición (merge) del dispositivo `clave` del cliente."""
    dispositivo = buscar_dispositivo(db, cliente, clave)
    if dispositivo is None:
        if con_tope:
            cuantos = db.scalar(
                select(func.count())
                .select_from(Dispositivo)
                .where(Dispositivo.cliente_id == cliente.id)
            )
            if (cuantos or 0) >= MAX_DISPOSITIVOS_POR_CLIENTE:
                raise FiscalAgentError(
                    f"Llegaste al tope de {MAX_DISPOSITIVOS_POR_CLIENTE} dispositivos.",
                    status_code=409,
                )
        dispositivo = Dispositivo(cliente_id=cliente.id, clave=clave, datos={})
        db.add(dispositivo)
    dispositivo.datos = _fusionar(dispositivo.datos, datos)
    db.flush()
    return dispositivo
