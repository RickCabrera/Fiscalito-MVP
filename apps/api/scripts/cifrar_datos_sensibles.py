"""
Cifra los datos bancarios que hayan quedado en claro (P6-01).

USO (con `FISCALITO_LLAVE_MAESTRA` y `DATABASE_URL` del entorno):
    cd apps/api && PYTHONPATH=. python -m scripts.cifrar_datos_sensibles

La migración `p6_cifrado_datos_sensibles` ya lo hace al subir el esquema si la llave existe;
este script es para cuando la llave se configura DESPUÉS (o para correrlo otra vez: es
idempotente).
"""

from __future__ import annotations

from app.db.cifrado_columnas import cifrar_existentes
from app.db.session import motor


def main() -> None:
    with motor.begin() as conexion:
        print(cifrar_existentes(conexion))


if __name__ == "__main__":
    main()
