"""
Manejadores que vienen con la cola. Los de cada dominio viven en su módulo y se importan
en `cargar_manejadores()` para que el worker los conozca.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.base import ahora
from app.modelos.nucleo import Empleado
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import manejador

# Los trabajos terminados se conservan este tiempo para que se vean en pantalla.
DIAS_RETENCION_TRABAJOS = 30


@manejador("diagnostico.cliente")
def diagnostico_cliente(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    """
    Trabajo de prueba de la ficha del cliente: cuenta sus empleados en la base.

    Sólo lee, así que es idempotente. `fallar_intentos: n` en la carga lo hace fallar en
    sus primeros `n` intentos, para ver en pantalla el reintento con backoff.
    """
    fallar = int(trabajo.carga.get("fallar_intentos", 0))
    if trabajo.intentos <= fallar:
        raise RuntimeError(f"Falla de prueba (intento {trabajo.intentos} de {fallar}).")
    empleados = db.scalar(
        select(func.count()).select_from(Empleado).where(Empleado.cliente_id == trabajo.cliente_id)
    )
    return {"empleados": int(empleados or 0), "intentos": trabajo.intentos}


@manejador("mantenimiento.purgar_trabajos")
def purgar_trabajos(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    """Borra trabajos `hecho` o `cancelado` de más de DIAS_RETENCION_TRABAJOS días.

    Los `fallido` se quedan: son los que alguien tiene que mirar."""
    dias = int(trabajo.carga.get("dias", DIAS_RETENCION_TRABAJOS))
    limite = ahora() - timedelta(days=dias)
    borrados = db.execute(
        delete(Trabajo).where(
            Trabajo.estado.in_(("hecho", "cancelado")),
            Trabajo.terminado_en < limite,
            Trabajo.id != trabajo.id,
        )
    )
    return {"borrados": borrados.rowcount, "dias": dias}


def cargar_manejadores() -> None:
    """Importa los módulos que registran manejadores. Agrega aquí los de cada dominio."""
    # P1-01/P1-02: descarga masiva del SAT (manejadores y sus tareas recurrentes).
    import app.sat_descarga.trabajos  # noqa: F401
