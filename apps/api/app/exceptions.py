"""
Jerarquía de excepciones de dominio para el agente fiscal.

Estas excepciones permiten manejar errores fiscales de forma estructurada
sin depender directamente de HTTPException en la lógica de negocio.
"""

import math


class FiscalAgentError(Exception):
    """Excepción base para el agente fiscal."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class FiscalValidationError(FiscalAgentError):
    """Error de validación de datos fiscales (ej: RFC inválido, periodo fuera de rango)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class FiscalCalculationError(FiscalAgentError):
    """Error en cálculo fiscal (ej: tabla ISR no encontrada, división por cero)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class LimiteExcedido(FiscalAgentError):
    """
    Demasiadas peticiones o tope de gasto alcanzado (P0-02): 429 con `Retry-After`.

    `reintentar_en` son segundos enteros (hacia arriba, mínimo 1): `Retry-After` no admite
    fracciones, y un 0 invitaría al cliente a reintentar en un loop.
    """

    def __init__(self, message: str, reintentar_en: float) -> None:
        super().__init__(message, status_code=429)
        self.reintentar_en = max(1, math.ceil(reintentar_en))
