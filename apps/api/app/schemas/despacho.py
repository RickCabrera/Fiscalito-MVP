"""
Schemas de la cartera de clientes del despacho (E-02).

**Demo — datos estáticos, sin autenticación, no desplegar.** Mismo estatus que
la épica D: la persistencia y el alta de clientes reales son F1-09.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.constants import ZonaSalarioMinimo
from app.schemas.nomina import PeriodoNomina


class EmpleadoClienteSchema(BaseModel):
    """
    Un empleado en la ficha del cliente.

    **Superconjunto compatible de `EmpleadoNominaSchema`**: `empleado_no`,
    `nombre`, `salario_diario`, `salario_diario_integrado` y `zona` se llaman y
    se tipan igual, para que la pantalla pueda mandar estos objetos a
    `POST /nomina/calcular-periodo` sin remapear. `zona` va por empleado —no
    sólo por cliente— porque el motor la lee por empleado para el piso del SBC.
    """

    empleado_no: str
    nombre: str
    salario_diario: Decimal
    salario_diario_integrado: Decimal
    zona: ZonaSalarioMinimo

    puesto: str = Field(
        default="",
        description="Vacío cuando no se conoce: el CFDI del caso real no lo trae.",
    )
    fecha_alta: date | None = Field(
        default=None,
        description="`null` cuando no se conoce. En el caso real el CFDI timbrado no "
        "trae la fecha de alta y **no se inventa**: §D9 documenta que el SDI de ese "
        "caso no se deriva de la antigüedad, así que un alta inventada invitaría a "
        "comparar factor contra antigüedad y a concluir que el motor está mal.",
    )
    antiguedad_anios: int | None = Field(
        default=None,
        description="Años cumplidos **a la fecha de referencia de la demo**, no a hoy. "
        "`null` si no hay fecha de alta.",
    )
    factor: Decimal = Field(
        description="SDI ÷ salario diario, a 4 decimales. Ver `factor_implicito`.",
    )
    factor_implicito: bool = Field(
        description="`true` cuando el factor es un cociente OBSERVADO y no el de ley "
        "(Art. 27 LSS): puede incluir prestaciones superiores que el CFDI no desglosa, "
        "así que no es comparable con el factor mínimo de una antigüedad.",
    )


class ClienteResumen(BaseModel):
    """Lo que necesita la lista de clientes y el selector del header."""

    id: str
    nombre: str
    giro: str
    origen: str = Field(
        description="`fixtures-s04` (caso real anonimizado) o `sintetico` "
        "(persona, salarios y fechas inventados)."
    )
    num_empleados: int
    prima_riesgo: Decimal = Field(
        description="Prima de Riesgos de Trabajo. Del caso real es la autodeterminada "
        "por ese patrón; de los sintéticos es la **prima media de su clase** "
        "(Art. 73 LSS). Nunca es tasa de ley."
    )
    clase_riesgo: int | None = Field(
        default=None,
        description="Clase de riesgo **SUPUESTA** para los clientes sintéticos: la "
        "asignación giro → clase sale del catálogo del RACERF, que no está en el repo "
        "(ver `docs/decisiones-nomina.md` D22). `null` para el caso real, cuya prima es "
        "autodeterminada y no se dedujo de una clase.",
    )
    clave_periodicidad: str
    zona: ZonaSalarioMinimo


class ClienteDetalle(ClienteResumen):
    """
    La ficha del cliente.

    Trae `periodo_sugerido` por la misma razón que `PlantillaDemoResponse`: para
    que la pantalla **no derive la quincena de las fechas de las checadas**.
    Deducirla de la primera y la última da 15 días donde la quincena tiene 16
    —el día 16 puede caer en fin de semana— y ese día de menos entra a
    `DiasDelPeriodo` y a los días pagados, o sea a las cuotas del IMSS y al ISR.
    """

    exito: bool = True
    empleados: tuple[EmpleadoClienteSchema, ...]
    periodo_sugerido: PeriodoNomina
    fecha_referencia: date = Field(
        description="Fecha contra la que se midieron antigüedad y factor de los "
        "clientes sintéticos. Fija, no es `hoy`."
    )


class ClientesResponse(BaseModel):
    exito: bool = True
    clientes: tuple[ClienteResumen, ...]
