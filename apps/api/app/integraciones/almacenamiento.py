"""
Almacenamiento de archivos (XML de CFDI, PDF, papeles de trabajo) — plan P, P0-03.

La app sólo necesita cuatro operaciones sobre rutas relativas (`cfdi/<despacho>/<cliente>/
<uuid>.xml`): guardar, leer, borrar y saber si existe. Las rutas las arma el dominio y son
siempre relativas: un adaptador nunca acepta `..` ni rutas absolutas.

Implementaciones (`FISCALITO_ALMACENAMIENTO`):
- `falso` / `local`: disco bajo `FISCALITO_ALMACEN_DIR` (default `./almacen`). Es la misma
  clase con dos nombres: `falso` es el default fuera de producción y debe sobrevivir a un
  reinicio igual que el SQLite de desarrollo; si viviera en memoria, la base diría que un XML
  existe y el almacén ya lo habría olvidado.
- `s3`: cualquier S3 compatible (AWS S3, Cloudflare R2, MinIO) vía boto3. Variables en
  `docs/servicios-externos.md`.

`AlmacenamientoMemoria` existe para pruebas unitarias; no se registra.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from app.exceptions import FiscalAgentError
from app.integraciones import registro


class Almacenamiento(Protocol):
    """Lo que la app necesita de un almacén de archivos."""

    def guardar(self, datos: bytes, ruta: str) -> str:
        """Guarda `datos` en `ruta` (sobrescribe) y devuelve la ruta guardada."""

    def leer(self, ruta: str) -> bytes:
        """Los bytes exactos guardados en `ruta`. 404 si no existe."""

    def borrar(self, ruta: str) -> None:
        """Borra `ruta`. No falla si ya no existía."""

    def existe(self, ruta: str) -> bool:
        """Si hay algo guardado en `ruta`."""


def normalizar_ruta(ruta: str) -> str:
    """
    Ruta relativa limpia con `/`. Rechaza absolutas, `..` y vacías.

    Es la única defensa contra que una ruta armada con datos del usuario escape del
    almacén, así que la aplican TODAS las implementaciones.
    """
    limpia = (ruta or "").replace("\\", "/").strip()
    # Se parte a mano y no con PurePosixPath: ésta colapsa `a/./b` y `a//b` en silencio,
    # y una ruta que el dominio armó mal debe fallar, no normalizarse a otra.
    partes = limpia.split("/")
    if not limpia or limpia.startswith("/") or any(p in {"", ".", ".."} for p in partes):
        raise FiscalAgentError(f"Ruta de almacenamiento inválida: {ruta!r}", status_code=400)
    if ":" in partes[0]:  # C:/... en Windows
        raise FiscalAgentError(f"Ruta de almacenamiento inválida: {ruta!r}", status_code=400)
    return "/".join(partes)


def _no_existe(ruta: str) -> FiscalAgentError:
    return FiscalAgentError(f"No existe el archivo '{ruta}' en el almacenamiento.", 404)


class AlmacenamientoLocal:
    """Disco local bajo una carpeta raíz."""

    def __init__(self, raiz: str | Path | None = None) -> None:
        self.raiz = Path(raiz or os.environ.get("FISCALITO_ALMACEN_DIR") or "./almacen").resolve()

    def _destino(self, ruta: str) -> Path:
        destino = (self.raiz / normalizar_ruta(ruta)).resolve()
        if self.raiz not in destino.parents:
            raise FiscalAgentError(f"Ruta de almacenamiento inválida: {ruta!r}", 400)
        return destino

    def guardar(self, datos: bytes, ruta: str) -> str:
        destino = self._destino(ruta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".tmp")
        temporal.write_bytes(datos)
        temporal.replace(destino)  # atómico: nunca queda un XML a medias
        return normalizar_ruta(ruta)

    def leer(self, ruta: str) -> bytes:
        destino = self._destino(ruta)
        if not destino.is_file():
            raise _no_existe(ruta)
        return destino.read_bytes()

    def borrar(self, ruta: str) -> None:
        self._destino(ruta).unlink(missing_ok=True)

    def existe(self, ruta: str) -> bool:
        return self._destino(ruta).is_file()


class AlmacenamientoMemoria:
    """Diccionario en memoria. Sólo para pruebas unitarias."""

    def __init__(self) -> None:
        self.archivos: dict[str, bytes] = {}

    def guardar(self, datos: bytes, ruta: str) -> str:
        llave = normalizar_ruta(ruta)
        self.archivos[llave] = bytes(datos)
        return llave

    def leer(self, ruta: str) -> bytes:
        llave = normalizar_ruta(ruta)
        if llave not in self.archivos:
            raise _no_existe(ruta)
        return self.archivos[llave]

    def borrar(self, ruta: str) -> None:
        self.archivos.pop(normalizar_ruta(ruta), None)

    def existe(self, ruta: str) -> bool:
        return normalizar_ruta(ruta) in self.archivos


class AlmacenamientoS3:
    """
    S3 compatible (AWS S3, Cloudflare R2, MinIO).

    Para R2: `FISCALITO_S3_ENDPOINT=https://<cuenta>.r2.cloudflarestorage.com` y
    `FISCALITO_S3_REGION=auto`. `cliente` se inyecta en tests (boto3 + Stubber, sin red).
    """

    def __init__(self, cliente: Any = None, bucket: str | None = None, prefijo: str | None = None):
        self.bucket = bucket or os.environ.get("FISCALITO_S3_BUCKET", "")
        if not self.bucket:
            raise FiscalAgentError(
                "Falta FISCALITO_S3_BUCKET para el almacenamiento S3.", status_code=503
            )
        self.prefijo = (prefijo if prefijo is not None else os.environ.get(
            "FISCALITO_S3_PREFIJO", "")).strip("/")
        self.cliente = cliente or self._cliente_desde_entorno()

    @staticmethod
    def _cliente_desde_entorno() -> Any:
        import boto3  # perezoso: importar el registro no debe cargar boto3

        return boto3.client(
            "s3",
            endpoint_url=os.environ.get("FISCALITO_S3_ENDPOINT") or None,
            region_name=os.environ.get("FISCALITO_S3_REGION") or "auto",
            aws_access_key_id=os.environ.get("FISCALITO_S3_ACCESS_KEY") or None,
            aws_secret_access_key=os.environ.get("FISCALITO_S3_SECRET_KEY") or None,
        )

    def _llave(self, ruta: str) -> str:
        limpia = normalizar_ruta(ruta)
        return f"{self.prefijo}/{limpia}" if self.prefijo else limpia

    @staticmethod
    def _es_404(error: Exception) -> bool:
        respuesta = getattr(error, "response", None) or {}
        codigo = str(respuesta.get("Error", {}).get("Code", ""))
        return codigo in {"404", "NoSuchKey", "NotFound"}

    def guardar(self, datos: bytes, ruta: str) -> str:
        self.cliente.put_object(Bucket=self.bucket, Key=self._llave(ruta), Body=datos)
        return normalizar_ruta(ruta)

    def leer(self, ruta: str) -> bytes:
        try:
            respuesta = self.cliente.get_object(Bucket=self.bucket, Key=self._llave(ruta))
        except Exception as e:  # botocore.exceptions.ClientError
            if self._es_404(e):
                raise _no_existe(ruta) from e
            raise
        return respuesta["Body"].read()

    def borrar(self, ruta: str) -> None:
        self.cliente.delete_object(Bucket=self.bucket, Key=self._llave(ruta))

    def existe(self, ruta: str) -> bool:
        try:
            self.cliente.head_object(Bucket=self.bucket, Key=self._llave(ruta))
        except Exception as e:
            if self._es_404(e):
                return False
            raise
        return True


_DESCRIPCION = "Archivos (XML de CFDI, PDF) en disco local o S3/R2"
registro.registrar("almacenamiento", "falso", AlmacenamientoLocal, _DESCRIPCION)
registro.registrar("almacenamiento", "local", AlmacenamientoLocal, _DESCRIPCION)
registro.registrar("almacenamiento", "s3", AlmacenamientoS3, _DESCRIPCION)


def obtener_almacenamiento() -> Almacenamiento:
    """El almacén configurado por `FISCALITO_ALMACENAMIENTO`."""
    return registro.obtener("almacenamiento")
