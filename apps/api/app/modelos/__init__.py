"""
Modelos ORM del plan P. Importar este paquete registra todas las tablas en `Base.metadata`.

Cada dominio vive en su archivo y se importa aquí. Al agregar uno nuevo, impórtalo abajo.
"""

from app.modelos import acceso  # noqa: F401, I001
from app.modelos import auditoria  # noqa: F401, I001
from app.modelos import cfdi  # noqa: F401, I001
from app.modelos import credenciales  # noqa: F401, I001
from app.modelos import nucleo  # noqa: F401, I001
from app.modelos import trabajos  # noqa: F401, I001
