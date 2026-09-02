"""
El modelo canónico de un empleado de la cartera (G-01).

QUIÉN GUARDA ESTO
-----------------
**El backend NO lo persiste.** `apps/api/CLAUDE.md` declara el servicio
*stateless*, y el único lugar que rompe esa regla —`asistencia/almacen.py`— lo
hace de forma acotada, lo dice en su encabezado y se borra en F2. Un CRUD de
empleados necesita persistencia de verdad, y hoy sólo podría ser (i) otro
almacén en RAM, que haría **literalmente falso** el criterio de G-01 después de
cualquier reinicio —o sea, a media demo—, o (ii) `firebase-admin` con service
account: dependencia nueva, secreto nuevo y pregunta de deploy nueva.

Así que el dueño del dato es **Firestore, bajo el uid del despacho**
(`users/{uid}/clientes/{id}/empleados/{id}`, PLAN_NOMINA §3.3), y este módulo es
el dueño del **modelo**: la forma, la validación y la semilla. El front escribe
contra este contrato en vez de inventar el suyo.

LAS DOS LLAVES SON DISTINTAS, Y ESO ES LO IMPORTANTE DE G-02
------------------------------------------------------------
`docs/D-DEMO-CHECADOR.md` dice que el `employeeNo` del Hikvision **es** el id del
empleado en Fiscalito. Aquí se separan, a propósito:

- **`empleado_no`** — la llave del CÁLCULO. Siempre presente. Es la que ya usan
  `EmpleadoNominaSchema` y las incidencias, y la que `despacho_demo.py` declara
  única entre clientes.
- **`employee_no`** — la llave del CHECADOR. Puede ser `None`: un empleado
  recién dado de alta todavía no está enrolado en el aparato.

Fundirlas obligaría a que la llave del cálculo fuera nullable, y ahí se pierde
gente de dos maneras: o el request revienta con 422 y **la nómina entera falla**,
o dos empleados sin vincular entran ambos con `""` y **colisionan**. Eso último
es exactamente "sus checadas se pierden en silencio", causado por la tarea que
venía a evitarlo.

EL NSS
------
Lo pide G-01 y aquí está, pero **opcional y vacío en la semilla**, nunca
inventado. Un NSS de 11 dígitos bien formado es el NSS de alguien. Se sigue el
precedente que ya escribió `despacho_demo.py` para `fecha_alta`: `None` cuando
no se conoce, *y no se inventa*. Requerirlo además tumbaría la semilla en tiempo
de import, y con ella la demo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.integracion import (
    DIAS_AGUINALDO_DE_LEY,
    PRIMA_VACACIONAL_DE_LEY,
    dias_vacaciones_de_ley,
)


class TipoContrato(str, Enum):
    """
    Tipo de relación de trabajo (Art. 35 LFT).

    **Hoy no cambia ningún cálculo** y por eso no vive en `nomina_engine`: es un
    dato de la ficha. Cuando F1-09 emita avisos afiliatorios sí importará, porque
    la baja de un contrato por obra determinada no se avisa igual que la de uno
    indeterminado.
    """

    INDETERMINADO = "indeterminado"
    DETERMINADO = "determinado"
    OBRA_DETERMINADA = "obra_determinada"
    PRUEBA = "prueba"


class EstatusEnrolamiento(str, Enum):
    """
    Si la persona ya tiene su rostro dado de alta en el checador.

    **El rostro se captura en el aparato, no en la app** (menú Usuario → Agregar,
    o HikConnect Teams; ver `docs/D-DEMO-CHECADOR.md`). Aquí sólo se guarda que
    ya se hizo, para que el despacho sepa a quién le falta.
    """

    PENDIENTE = "pendiente"
    ENROLADO = "enrolado"


def vacaciones_efectivas(dias_capturados: int, anios_servicio_cumplidos: int) -> int:
    """
    Los días de vacaciones capturados, o los de ley si se dejaron en 0.

    **Vive aquí y no en dos lados.** Es una convención de captura —"0 significa
    los que le tocan"—, no una regla fiscal: el Art. 76 sigue entero en
    `dias_vacaciones_de_ley`. Pero tenerla duplicada en el schema y en la ruta
    del SBC sería la misma segunda verdad que ese endpoint existe para evitar,
    sólo que movida de TypeScript a Python: el día que alguien cambie el
    centinela a `None`, cambiaría una sola.

    Es función suelta y no método del schema porque `POST /nomina/sbc` la
    necesita **sin** la validación del schema: ahí los rangos los tiene que
    rechazar el MOTOR, para que el 422 traiga su mensaje (el que explica que 25
    no es 0.25) y no el genérico de pydantic.
    """
    if dias_capturados > 0:
        return dias_capturados
    return dias_vacaciones_de_ley(anios_servicio_cumplidos)


class PrestacionesSchema(BaseModel):
    """
    Las prestaciones con las que se integra el SBC (Art. 27 LSS).

    Los mínimos son los de ley y se leen del motor —no se copian—, así que si
    `integracion.py` cambia su fundamento, esto cambia con él. Se validan aquí
    además de en el motor porque un aguinaldo de 10 días capturado en el modal
    debe rebotar en el formulario, no 3 pantallas después.
    """

    dias_aguinaldo: int = Field(
        default=DIAS_AGUINALDO_DE_LEY,
        ge=DIAS_AGUINALDO_DE_LEY,
        description=f"Mínimo de ley: {DIAS_AGUINALDO_DE_LEY} días (Art. 87 LFT).",
    )
    dias_vacaciones: int = Field(
        default=0,
        ge=0,
        description="0 = usa los de ley que le tocan a su antigüedad (Art. 76 LFT).",
    )
    prima_vacacional: Decimal = Field(
        default=PRIMA_VACACIONAL_DE_LEY,
        ge=PRIMA_VACACIONAL_DE_LEY,
        le=Decimal("1"),
        description="Proporción, no porcentaje: 0.25 es el mínimo de ley (Art. 80 LFT). "
        "Pasar 25 en vez de 0.25 infla el SBC 77% sin que ninguna tabla lo detecte, "
        "y por eso el rango se valida aquí y en el motor.",
    )

    def vacaciones_efectivas(self, anios_servicio_cumplidos: int) -> int:
        """Los días capturados, o los de ley. Delega: una sola implementación."""
        return vacaciones_efectivas(self.dias_vacaciones, anios_servicio_cumplidos)


class EmpleadoCarteraSchema(BaseModel):
    """
    Un empleado tal como lo guarda el despacho.

    **Superconjunto compatible de `EmpleadoNominaSchema`**: `empleado_no`,
    `nombre`, `salario_diario`, `salario_diario_integrado` y `zona` se llaman y
    se tipan igual, para que la pantalla pueda mandarlos a
    `POST /nomina/calcular-periodo` sin remapear. Es la misma disciplina que ya
    sigue `EmpleadoClienteSchema` (E-02).
    """

    empleado_no: str = Field(
        min_length=1,
        description="Llave del CÁLCULO. Siempre presente, única dentro del cliente.",
    )
    nombre: str = Field(min_length=1)
    puesto: str = ""

    salario_diario: Decimal = Field(gt=0)
    salario_diario_integrado: Decimal = Field(
        gt=0,
        description="Dato de entrada (§D9). Para un alta nueva lo calcula "
        "`POST /nomina/sbc` y el front lo manda ya resuelto; para el caso real "
        "viene del CFDI timbrado y **no se recalcula**.",
    )
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    fecha_alta: date | None = Field(
        default=None,
        description="`null` cuando no se conoce, y NO se inventa (§D9).",
    )

    tipo_contrato: TipoContrato = TipoContrato.INDETERMINADO
    prestaciones: PrestacionesSchema = Field(default_factory=PrestacionesSchema)

    nss: str = Field(
        default="",
        max_length=11,
        description="Número de Seguridad Social. **Vacío cuando no se conoce y nunca "
        "inventado**: un NSS bien formado es el NSS de alguien. La semilla va vacía.",
    )

    employee_no: str | None = Field(
        default=None,
        description="Llave del CHECADOR (`employeeNoString` del Hikvision). `null` = "
        "el empleado NO está vinculado: sus checadas no se pueden atribuir. Es "
        "distinta de `empleado_no`, que es la del cálculo y nunca es nula.",
    )
    enrolamiento: EstatusEnrolamiento = EstatusEnrolamiento.PENDIENTE

    @property
    def vinculado_al_checador(self) -> bool:
        """`False` = sus checadas no tienen con qué casarse. Lo pinta la UI."""
        return bool(self.employee_no)


class EmpleadosClienteResponse(BaseModel):
    """
    La semilla de empleados de un cliente.

    `origen` dice de dónde salieron para que la pantalla no tenga que adivinar si
    está viendo el catálogo de demostración o la cartera real del despacho.
    """

    cliente_id: str
    origen: str
    total: int
    sin_vincular: int = Field(
        description="Cuántos NO tienen `employee_no`. Se cuenta aquí y no en la UI "
        "para que el aviso no dependa de que alguien se acuerde de filtrar."
    )
    empleados: tuple[EmpleadoCarteraSchema, ...]
