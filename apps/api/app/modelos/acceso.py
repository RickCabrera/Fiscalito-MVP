"""
Acceso a la API (P0-02): tokens de dispositivo y consumo diario de LLM por despacho.

TOKEN DE DISPOSITIVO: SÓLO SE GUARDA EL HASH
--------------------------------------------
El checador Hikvision no puede mandar un ID token de Firebase: su URL de push es fija y el
cuerpo lo arma el aparato. Se le da un secreto propio (`fdt_<43 caracteres>`, 256 bits de
`secrets.token_urlsafe`) que viaja como `?token=` en la URL o en `X-Token-Dispositivo`. Se
guarda su SHA-256: con 256 bits de entropía no hace falta sal ni un KDF lento, y quien lea
la base no puede hacerse pasar por el aparato. `prefijo` (los primeros 12 caracteres) sólo
sirve para que el despacho reconozca cuál es cuál en pantalla.

El token es del CLIENTE (y opcionalmente de un `Dispositivo` concreto): el evento que entra
con él se guarda bajo el despacho y el cliente dueños del token, nunca bajo lo que diga el
query string. Es una tabla aparte y no una columna de `Dispositivo` para poder rotar (dos
tokens vivos mientras se reconfigura el aparato) y revocar sin tocar el dispositivo.

CONSUMO DE LLM: UN RENGLÓN POR DESPACHO Y DÍA
---------------------------------------------
`llamadas` se incrementa con un `UPDATE ... WHERE llamadas < tope` (ver
`app/acceso/llm.py`), así que dos requests simultáneos no pueden pasarse del tope juntos.
`dia` es la fecha en la Ciudad de México: el tope se reinicia a la medianoche del despacho,
no a la de UTC.
"""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC


class TokenDispositivo(ConMarcasDeTiempo, Base):
    """Secreto con el que un checador empuja checadas de un cliente."""

    __tablename__ = "tokens_dispositivo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True
    )
    # `cliente_clave` es la que manda (es la llave del almacén de checadas). `cliente_id` se
    # llena cuando el cliente vive en `clientes`; los tres de la demo (`despacho_demo.py`) son
    # un catálogo estático sin renglón, y para ellos queda en NULL.
    cliente_clave: Mapped[str] = mapped_column(String(120))
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=True
    )
    dispositivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("dispositivos.id", ondelete="SET NULL"), nullable=True
    )
    etiqueta: Mapped[str] = mapped_column(String(120), default="")
    hash_token: Mapped[str] = mapped_column(String(64), unique=True)
    prefijo: Mapped[str] = mapped_column(String(16))
    activo: Mapped[bool] = mapped_column(default=True)
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    ultimo_uso: Mapped[datetime | None] = mapped_column(FechaUTC, nullable=True)


class ConsumoLLM(Base):
    """Llamadas al LLM de un despacho en un día (hora de la Ciudad de México)."""

    __tablename__ = "consumo_llm"

    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), primary_key=True
    )
    dia: Mapped[date] = mapped_column(Date, primary_key=True)
    llamadas: Mapped[int] = mapped_column(Integer, default=0)
