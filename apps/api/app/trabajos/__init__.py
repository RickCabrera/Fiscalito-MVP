"""
Trabajos en segundo plano (P0-04): cola en la base, worker y programación recurrente.

Uso:

    from app.trabajos import encolar, manejador

    @manejador("sat.descarga")
    def descargar(db, trabajo):
        ...
        return {"paquetes": 3}

    encolar(db, "sat.descarga", {"rfc": "..."}, despacho_id=ctx.despacho_id,
            cliente_id=cliente.id, clave_unica=f"sat.descarga:{cliente.id}:2026-10")

El worker (`python -m app.trabajos.worker`) toma los pendientes vencidos y las tareas
recurrentes de `app/trabajos/programacion.py`. Ver `docs/arquitectura-p.md`.
"""

from app.trabajos.cola import (
    backoff,
    cancelar,
    encolar,
    manejador,
    manejadores,
    procesar_siguiente,
    recuperar_huerfanos,
    reintentar,
)

__all__ = [
    "backoff",
    "cancelar",
    "encolar",
    "manejador",
    "manejadores",
    "procesar_siguiente",
    "recuperar_huerfanos",
    "reintentar",
]
