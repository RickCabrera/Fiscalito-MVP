"""
Modelos ORM del plan P. Importar este paquete registra todas las tablas en `Base.metadata`.

Cada dominio vive en su archivo y se importa aquí. Al agregar uno nuevo, impórtalo abajo.
"""

from app.modelos import acceso  # noqa: F401, I001
from app.modelos import auditoria  # noqa: F401, I001
from app.modelos import cfdi  # noqa: F401, I001
from app.modelos import credenciales  # noqa: F401, I001
from app.modelos import impuestos  # noqa: F401, I001
from app.modelos import nucleo  # noqa: F401, I001
from app.modelos import sat_descarga  # noqa: F401, I001
from app.modelos import sat_verificacion  # noqa: F401, I001
from app.modelos import trabajos  # noqa: F401, I001
from app.modelos import contabilidad  # noqa: F401, I001
from app.modelos import conciliacion  # noqa: F401, I001
from app.modelos import retenciones_cfdi  # noqa: F401, I001 — P3-04
from app.modelos import diot  # noqa: F401, I001 — P3-05
from app.modelos import alertas  # noqa: F401, I001 — P3-09
from app.modelos import agenda  # noqa: F401, I001 — P3-10
