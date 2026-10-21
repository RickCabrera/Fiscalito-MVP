"""
Tipos de columna portables entre Postgres y SQLite.

`FechaUTC` EXISTE PORQUE SQLITE TIRA LA ZONA HORARIA
---------------------------------------------------
`DateTime(timezone=True)` en SQLite guarda el texto sin offset y lo compara como texto: un
`ejecutar_en` de las 12:00 en Ciudad de México (18:00 UTC) quedaba como "12:00" y la cola
lo consideraba vencido seis horas antes. Este tipo convierte TODO a UTC al escribir y
devuelve fechas con `tzinfo=UTC` al leer, en los dos motores. Una fecha sin zona se
rechaza: adivinarla es exactamente el error que se quiere evitar.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class FechaUTC(TypeDecorator[datetime]):
    """Momento absoluto: se guarda en UTC, se lee con `tzinfo=UTC`."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("FechaUTC no acepta fechas sin zona horaria.")
        utc = value.astimezone(UTC)
        # SQLite compara texto: se guarda sin offset, ya normalizado a UTC.
        return utc.replace(tzinfo=None) if dialect.name == "sqlite" else utc

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
