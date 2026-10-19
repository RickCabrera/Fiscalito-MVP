"""
Núcleo multi-despacho: despachos, usuarios, clientes, empleados y dispositivos.

LA LLAVE DEL TENANT ES `despacho_id`
------------------------------------
Toda tabla con datos de un despacho lleva `despacho_id` y toda consulta filtra por él
(ver `app/tenancy.py`). Un usuario pertenece a un solo despacho. El dueño original de una
cuenta crea su despacho con id = su uid de Firebase, así que las rutas viejas de Firestore
(`users/{uid}/clientes/...`) migran sin traducir ids.

CLIENTE Y EMPLEADO GUARDAN SU DOCUMENTO COMO JSON
-------------------------------------------------
Los esquemas Pydantic de `app/schemas/cartera.py` y `app/schemas/empleado.py` ya validan
cada campo y crecen con frecuencia. Guardarlos como `datos` (JSON) conserva esa
validación como única fuente y evita una migración por cada campo nuevo; las columnas que
sí se consultan (clave, nombre, rfc) se copian aparte e indexadas.
"""

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo


class Despacho(ConMarcasDeTiempo, Base):
    """Un despacho contable: la unidad de tenencia y de facturación del plan."""

    __tablename__ = "despachos"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(300), default="")
    plan: Mapped[str] = mapped_column(String(40), default="contador")


class Usuario(ConMarcasDeTiempo, Base):
    """Persona que entra a la app (uid de Firebase) y su rol dentro de su despacho."""

    __tablename__ = "usuarios"

    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320), default="")
    nombre: Mapped[str] = mapped_column(String(300), default="")
    # dueno | contador | auxiliar (P5-01). El auxiliar sólo ve clientes asignados.
    rol: Mapped[str] = mapped_column(String(20), default="dueno")
    activo: Mapped[bool] = mapped_column(default=True)


class Cliente(ConMarcasDeTiempo, Base):
    """Empresa o persona que el despacho atiende."""

    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("despacho_id", "clave"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True
    )
    # El id público del cliente (el `id` de ClienteCarteraSchema, p. ej. "taller").
    clave: Mapped[str] = mapped_column(String(120))
    nombre: Mapped[str] = mapped_column(String(300), default="")
    rfc: Mapped[str] = mapped_column(String(13), default="", index=True)
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Empleado(ConMarcasDeTiempo, Base):
    """Trabajador de un cliente. `datos` es un EmpleadoCarteraSchema serializado."""

    __tablename__ = "empleados"
    __table_args__ = (UniqueConstraint("cliente_id", "empleado_no"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    empleado_no: Mapped[str] = mapped_column(String(60))
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Dispositivo(ConMarcasDeTiempo, Base):
    """Checador biométrico de un cliente (R-04, R-09)."""

    __tablename__ = "dispositivos"
    __table_args__ = (UniqueConstraint("cliente_id", "clave"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    clave: Mapped[str] = mapped_column(String(120))
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AsignacionCliente(Base):
    """Qué clientes ve un usuario con rol `auxiliar` (P5-01)."""

    __tablename__ = "asignaciones_cliente"
    __table_args__ = (Index("ix_asig_usuario", "usuario_uid"),)

    usuario_uid: Mapped[str] = mapped_column(
        ForeignKey("usuarios.uid", ondelete="CASCADE"), primary_key=True
    )
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
