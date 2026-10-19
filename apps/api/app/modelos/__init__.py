"""
Modelos ORM del plan P. Importar este paquete registra todas las tablas en `Base.metadata`.

Cada dominio vive en su archivo y se importa aquí. Al agregar uno nuevo, impórtalo abajo.
"""

from app.modelos import cfdi, credenciales, nucleo  # noqa: F401
