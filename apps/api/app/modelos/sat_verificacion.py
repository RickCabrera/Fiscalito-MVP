"""
Verificaciones contra el SAT (plan P, P1-03/04/05).

- `VerificacionCfdi`: el detalle de la última consulta de estatus de un CFDI de la bóveda
  (P1-03). El resumen (`vigente`/`cancelado`/`desconocido`) vive en
  `Comprobante.estatus_sat`; aquí queda lo que el SAT respondió tal cual (CodigoEstatus,
  EsCancelable, EstatusCancelacion, ValidacionEFOS), para no perder el "en proceso".
- `ContribuyenteListaSat` y `CargaListaSat`: los listados públicos del SAT (art. 69-B y 69
  del CFF) tal como se descargaron (P1-04). **Son datos públicos y globales**, no de un
  despacho: no llevan `despacho_id`. Lo que sí es del despacho es el cruce con sus CFDI
  (`AlertaRiesgo`).
- `DocumentoCumplimiento` y `ConfigCumplimiento`: opinión de cumplimiento 32-D y constancia
  de situación fiscal por cliente, con el PDF en el almacenamiento (P1-05).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo, ahora
from app.db.tipos import FechaUTC


class VerificacionCfdi(Base):
    """Última respuesta del servicio de estatus del SAT para un comprobante."""

    __tablename__ = "verificaciones_cfdi"

    comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="CASCADE"), primary_key=True
    )
    # Textos tal cual del SAT: "S - Comprobante obtenido satisfactoriamente.", "Vigente",
    # "Cancelable con aceptación", "En proceso", "200"...
    codigo_estatus: Mapped[str] = mapped_column(String(200), default="")
    estado: Mapped[str] = mapped_column(String(40), default="")
    es_cancelable: Mapped[str] = mapped_column(String(60), default="")
    estatus_cancelacion: Mapped[str] = mapped_column(String(60), default="")
    validacion_efos: Mapped[str] = mapped_column(String(20), default="")
    consultado_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora)


class ContribuyenteListaSat(Base):
    """Un renglón de un listado público del SAT (69-B o 69)."""

    __tablename__ = "contribuyentes_lista_sat"
    __table_args__ = (
        UniqueConstraint("lista", "rfc", name="uq_lista_sat_rfc"),
        Index("ix_lista_sat_rfc", "rfc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 69b | 69_no_localizados | 69_firmes | 69_exigibles | 69_cancelados | 69_sentencias ...
    lista: Mapped[str] = mapped_column(String(40))
    rfc: Mapped[str] = mapped_column(String(13))
    nombre: Mapped[str] = mapped_column(String(400), default="")
    # Normalizada: presunto | definitivo | desvirtuado | sentencia_favorable | <supuesto 69>.
    situacion: Mapped[str] = mapped_column(String(60), default="")
    situacion_texto: Mapped[str] = mapped_column(String(200), default="")
    fecha_publicacion_sat: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_publicacion_dof: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_carga: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora)
    # Todas las columnas del CSV, por si el SAT agrega alguna que aquí no se interpreta.
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CargaListaSat(Base):
    """La última descarga de cada listado: cuándo, de dónde, cuántos y si falló."""

    __tablename__ = "cargas_lista_sat"

    lista: Mapped[str] = mapped_column(String(40), primary_key=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    registros: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    # Última descarga exitosa (con o sin cambios) y último intento.
    cargada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    revisada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class AlertaRiesgo(ConMarcasDeTiempo, Base):
    """
    Una contraparte de un cliente apareció en un listado del SAT.

    `clave` hace idempotente al cruce: el mismo RFC en la misma lista y situación genera una
    sola alerta por cliente aunque el trabajo corra todos los días.
    """

    __tablename__ = "alertas_riesgo"
    __table_args__ = (
        UniqueConstraint("cliente_id", "clave", name="uq_alerta_cliente_clave"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True
    )
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    # art69b | art69 | propio_69b (el RFC del propio cliente está en la lista)
    tipo: Mapped[str] = mapped_column(String(20))
    clave: Mapped[str] = mapped_column(String(120))
    rfc: Mapped[str] = mapped_column(String(13))
    nombre: Mapped[str] = mapped_column(String(400), default="")
    lista: Mapped[str] = mapped_column(String(40))
    situacion: Mapped[str] = mapped_column(String(60))
    # proveedor (emisor de recibidos) | cliente (receptor de emitidos) | propio
    relacion: Mapped[str] = mapped_column(String(12))
    nivel: Mapped[str] = mapped_column(String(10))  # alto | medio | info
    detalle: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    atendida: Mapped[bool] = mapped_column(default=False)
    atendida_por: Mapped[str | None] = mapped_column(String(128), nullable=True)


class DocumentoCumplimiento(ConMarcasDeTiempo, Base):
    """Opinión de cumplimiento (32-D) o constancia de situación fiscal de un cliente."""

    __tablename__ = "documentos_cumplimiento"
    __table_args__ = (Index("ix_doc_cumpl_cliente_tipo", "cliente_id", "tipo", "fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(12))  # opinion | constancia
    # Fecha del documento (la que dice el PDF; si no se pudo leer, la de obtención).
    fecha: Mapped[date] = mapped_column(Date)
    # positiva | negativa | sin_obligaciones | desconocido (constancia: desconocido).
    resultado: Mapped[str] = mapped_column(String(20), default="desconocido")
    folio: Mapped[str] = mapped_column(String(80), default="")
    # falso | portal_sat | proveedor | manual
    origen: Mapped[str] = mapped_column(String(20))
    ruta_pdf: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    # Cómo se determinó el resultado: adaptador | pdf | sin_lectura.
    lectura: Mapped[str] = mapped_column(String(20), default="sin_lectura")
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ConfigCumplimiento(ConMarcasDeTiempo, Base):
    """
    Programación mensual por cliente. Sin renglón = default (automática, día 1).

    El default es "automática" porque la opinión vence a los 30 días y el despacho la
    necesita vigente para licitaciones y subsidios; el despacho la apaga por cliente.
    """

    __tablename__ = "config_cumplimiento"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    automatico: Mapped[bool] = mapped_column(default=True)
    dia_del_mes: Mapped[int] = mapped_column(Integer, default=1)
    constancia: Mapped[bool] = mapped_column(default=True)
