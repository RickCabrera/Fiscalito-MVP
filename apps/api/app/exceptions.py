"""
Jerarquía de excepciones de dominio para el agente fiscal.

Estas excepciones permiten manejar errores fiscales de forma estructurada
sin depender directamente de HTTPException en la lógica de negocio.
"""


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
