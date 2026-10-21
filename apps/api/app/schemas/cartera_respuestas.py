"""
Respuestas de las rutas de la cartera (R-07, R-10). Salieron de `schemas/cartera.py` por el
tope de 300 líneas (P6-07); sólo se movió el código. Los nombres de los esquemas no cambian,
así que el OpenAPI y los tipos generados del front quedan iguales.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.empleado import EmpleadoCarteraSchema


class ClientesCarteraResponse(BaseModel):
    exito: bool = True
    total: int
    clientes: tuple[dict, ...] = Field(
        description="Los documentos tal como están guardados, con su `id`. No se tipan "
        "estrictamente al leer: una cartera escrita por una versión anterior de la app "
        "puede traer campos que este modelo todavía no conoce, y rechazarla dejaría al "
        "contador sin sus clientes por un campo de más."
    )


class EmpleadoIlegible(BaseModel):
    """Un empleado guardado que no pasa la validación actual, y por qué (R-10)."""

    empleado_no: str
    nombre: str = Field(default="", description="El nombre guardado, si lo tiene.")
    razon: str = Field(description="Primera causa del rechazo, legible: `nss: ...`.")


class EmpleadosCarteraResponse(BaseModel):
    exito: bool = True
    cliente_id: str
    total: int
    sin_vincular: int = Field(
        description="Cuántos NO tienen `employee_no`. Sus checadas no se pueden atribuir."
    )
    ilegibles: tuple[str, ...] = Field(
        default=(),
        description="Empleados guardados que **no pasan la validación actual** —un NSS de "
        "una versión anterior, un campo que falta— y por eso NO vienen en `empleados`. Se "
        "reportan en vez de tumbar la respuesta: un documento legado dejaba la cartera "
        "completa en cero. Y se reportan en vez de esconderse, porque un empleado que queda "
        "fuera del cálculo en silencio es el modo de falla que la épica G viene evitando.",
    )
    ilegibles_detalle: tuple[EmpleadoIlegible, ...] = Field(
        default=(),
        description="Los mismos `ilegibles`, con nombre y razón para pintarlos en la ficha "
        "(R-10). `ilegibles` se conserva como lista de `empleado_no` por compatibilidad.",
    )
    empleados: tuple[EmpleadoCarteraSchema, ...]


class OperacionResponse(BaseModel):
    exito: bool = True
    mensaje: str
