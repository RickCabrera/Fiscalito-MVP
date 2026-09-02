"""
Esquemas de la cartera del despacho cuando el backend es su dueño. (R-07)

POR QUÉ HAY UN `ClienteCarteraSchema` NUEVO
-------------------------------------------
`ClienteResumen` y `ClienteDetalle` (E-02) describen el **catálogo de
demostración**: son de sólo lectura, salen de `despacho_demo.py` y llevan campos
derivados (`num_empleados`, `fecha_referencia`) que un cliente capturado por el
contador no tiene. Reusarlos aquí obligaría a inventar esos campos al guardar,
que es exactamente el tipo de dato falso que este repo evita en todos lados.

Éste describe lo que el DESPACHO captura, con la misma forma que el front ya
escribe en Firestore — para que encender R-07 no exija migrar un solo documento.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.tablas_imss import PRIMA_RT_MAXIMA, PRIMA_RT_MINIMA
from app.schemas.empleado import EmpleadoCarteraSchema
from app.schemas.nomina import PeriodoNomina


class ClienteCarteraSchema(BaseModel):
    """Un cliente tal como lo captura el despacho."""

    id: str = Field(min_length=1, max_length=120)
    nombre: str = Field(min_length=1)
    giro: str = ""
    origen: str = Field(
        default="propio",
        description="`propio` = lo capturó el contador. `sintetico` y `fixtures-s04` son "
        "los clientes de DEMOSTRACIÓN, y el front los oculta fuera de cuentas de "
        "desarrollo (R-06).",
    )

    prima_riesgo: Decimal = Field(
        ge=PRIMA_RT_MINIMA,
        le=PRIMA_RT_MAXIMA,
        description=f"Fracción, no porcentaje. Arts. 72 y 73 LSS acotan a "
        f"[{PRIMA_RT_MINIMA}, {PRIMA_RT_MAXIMA}]. Se valida aquí porque capturar "
        f"5.4355 en vez de 0.0054355 multiplica Riesgos de Trabajo por mil y ninguna "
        f"tabla lo detecta después.",
    )
    clase_riesgo: int | None = Field(default=None, ge=1, le=5)
    clave_periodicidad: str = Field(
        default="04",
        description="Clave de `c_PeriodicidadPago`. Hoy el front sólo ofrece `04` "
        "(quincenal): nadie valida que la duración del periodo case con la clave, y un "
        "cliente Mensual recibiría la tarifa mensual del Art. 96 sobre 15-16 días — ISR "
        "subestimado con recibo creíble (backlog, sección G).",
    )
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    periodo_sugerido: PeriodoNomina | None = Field(
        default=None,
        description="Puede faltar: el primer cliente de una cuenta nueva nace sin él y la "
        "pantalla de nómina pide capturar las fechas (R-06).",
    )


class ClientesCarteraResponse(BaseModel):
    exito: bool = True
    total: int
    clientes: tuple[dict, ...] = Field(
        description="Los documentos tal como están guardados, con su `id`. No se tipan "
        "estrictamente al leer: una cartera escrita por una versión anterior de la app "
        "puede traer campos que este modelo todavía no conoce, y rechazarla dejaría al "
        "contador sin sus clientes por un campo de más."
    )


class EmpleadosCarteraResponse(BaseModel):
    exito: bool = True
    cliente_id: str
    total: int
    sin_vincular: int = Field(
        description="Cuántos NO tienen `employee_no`. Sus checadas no se pueden atribuir."
    )
    empleados: tuple[EmpleadoCarteraSchema, ...]


class OperacionResponse(BaseModel):
    exito: bool = True
    mensaje: str
