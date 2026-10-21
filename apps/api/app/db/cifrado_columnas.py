"""
Columnas cifradas en reposo con la llave maestra de la bóveda (P6-01).

QUÉ SE CIFRA Y CÓMO
-------------------
Datos bancarios de personas: la CLABE y el número de cuenta del empleado (dentro del JSON
`empleados.datos`) y la CLABE/número de las cuentas bancarias del cliente
(`cuentas_bancarias`). Se usa el mismo `MultiFernet` de `app/credenciales/cifrado.py`
(`FISCALITO_LLAVE_MAESTRA`): una sola llave que cuidar y rotar.

El valor guardado lleva el prefijo `enc:` + token Fernet. Un valor SIN prefijo se devuelve tal
cual: así los renglones escritos antes de esta tarea siguen leyéndose, y la migración
`p6_cifrado_datos_sensibles` (o `scripts/cifrar_datos_sensibles.py`) los re-escribe cifrados
cuando la llave real está configurada. Al leer, un token que ninguna llave descifra lanza 503
(`BovedaNoDisponible`), igual que la bóveda: nunca se devuelve basura como si fuera una CLABE.

Estas columnas NO se pueden filtrar en SQL por su valor (cada cifrado es distinto). Las
búsquedas que haga el dominio son en memoria sobre lo descifrado.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import JSON, Connection, String, text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

PREFIJO = "enc:"
# Un token Fernet de una CLABE de 18 dígitos mide ~120 caracteres; 400 deja holgura.
LARGO_CIFRADO = 400


def llave_configurada() -> bool:
    from app.credenciales.cifrado import _llaves_configuradas

    return bool(_llaves_configuradas())


def cifrar_texto(valor: str) -> str:
    """
    `enc:<token>` de `valor`; vacío se queda vacío; lo ya cifrado no se vuelve a cifrar.

    SIN LLAVE MAESTRA: en producción, 503 (`cifrador()` falla cerrado). En desarrollo se
    guarda EN CLARO, a diferencia de la bóveda: con la llave efímera la CLABE sería ilegible
    tras reiniciar el proceso, y perder la cuenta de un trabajador es peor que tenerla en
    claro en una base local. Al configurar la llave, `cifrar_existentes` la cifra.
    """
    from app.config import settings
    from app.credenciales.cifrado import cifrar

    if not valor or valor.startswith(PREFIJO):
        return valor
    if not llave_configurada() and settings.ENTORNO != "produccion":
        return valor
    return PREFIJO + cifrar(valor.encode("utf-8")).decode("ascii")


def descifrar_texto(valor: str) -> str:
    """El texto en claro; un valor sin prefijo (legado) se devuelve tal cual."""
    from app.credenciales.cifrado import descifrar

    if not valor or not valor.startswith(PREFIJO):
        return valor
    return descifrar(valor[len(PREFIJO):].encode("ascii")).decode("utf-8")


def esta_cifrado(valor: Any) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIJO)


class TextoCifrado(TypeDecorator[str]):
    """Una columna de texto que se guarda cifrada."""

    impl = String(LARGO_CIFRADO)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return cifrar_texto(str(value))

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return descifrar_texto(value)


class JSONConCamposCifrados(TypeDecorator[dict[str, Any]]):
    """Un JSON cuyos campos `campos` (de primer nivel, texto) se guardan cifrados."""

    impl = JSON
    cache_ok = True

    def __init__(self, campos: Iterable[str] = (), *args: Any, **kwargs: Any) -> None:
        self.campos = tuple(campos)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Any) -> Any:
        if not isinstance(value, dict):
            return value
        copia = dict(value)
        for campo in self.campos:
            v = copia.get(campo)
            if isinstance(v, str) and v:
                copia[campo] = cifrar_texto(v)
        return copia

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if not isinstance(value, dict):
            return value
        copia = dict(value)
        for campo in self.campos:
            v = copia.get(campo)
            if isinstance(v, str) and v:
                copia[campo] = descifrar_texto(v)
        return copia


# Los campos del JSON del empleado que se cifran (ver `app/schemas/empleado_pago.py`).
CAMPOS_EMPLEADO_CIFRADOS = ("clabe", "numero_cuenta")


def cifrar_existentes(conexion: Connection) -> dict[str, int]:
    """
    Cifra en sitio lo que quedó en claro (renglones de antes de P6-01, o escritos sin llave).
    Idempotente: lo que ya trae `enc:` no se toca. Sin llave maestra no hace nada (y lo dice):
    cifrar con una efímera sería destruir el dato. Lo usan la migración
    `p6_cifrado_datos_sensibles` y `scripts/cifrar_datos_sensibles.py` (tras poner la llave).
    SQL directo, sin el ORM: corre dentro de Alembic, donde los modelos pueden ir adelante.
    """
    if not llave_configurada():
        logger.warning("Sin FISCALITO_LLAVE_MAESTRA: los datos bancarios quedan en claro. "
                       "Configúrala y corre scripts/cifrar_datos_sensibles.py.")
        return {"empleados": 0, "cuentas_bancarias": 0}
    empleados = 0
    for id_, crudo in conexion.execute(text("SELECT id, datos FROM empleados")).all():
        datos = json.loads(crudo) if isinstance(crudo, str) else crudo
        if not isinstance(datos, dict):
            continue
        cambia = False
        for campo in CAMPOS_EMPLEADO_CIFRADOS:
            v = datos.get(campo)
            if isinstance(v, str) and v and not esta_cifrado(v):
                datos[campo], cambia = cifrar_texto(v), True
        if cambia:
            # Postgres no convierte solo un texto a JSON; en SQLite un CAST a JSON lo rompería.
            valor = "CAST(:d AS JSON)" if conexion.dialect.name == "postgresql" else ":d"
            conexion.execute(text(f"UPDATE empleados SET datos = {valor} WHERE id = :i"),
                             {"d": json.dumps(datos, ensure_ascii=False), "i": id_})
            empleados += 1
    cuentas = 0
    filas = conexion.execute(text("SELECT id, numero, clabe FROM cuentas_bancarias")).all()
    for id_, numero, clabe in filas:
        if (numero and not esta_cifrado(numero)) or (clabe and not esta_cifrado(clabe)):
            conexion.execute(
                text("UPDATE cuentas_bancarias SET numero = :n, clabe = :c WHERE id = :i"),
                {"n": cifrar_texto(numero or ""), "c": cifrar_texto(clabe or ""), "i": id_})
            cuentas += 1
    return {"empleados": empleados, "cuentas_bancarias": cuentas}
