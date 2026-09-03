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
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.integracion import (
    DIAS_AGUINALDO_DE_LEY,
    PRIMA_VACACIONAL_DE_LEY,
    validar_tabla_vacaciones,
)
from app.nomina_engine.tablas_imss import PRIMA_RT_MAXIMA, PRIMA_RT_MINIMA
from app.schemas.empleado import EmpleadoCarteraSchema
from app.schemas.nomina import PeriodoNomina

# `\d{2}:\d{2}` aceptaba "99:99". Esto acota las dos mitades de verdad.
HORA = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


class HorarioSchema(BaseModel):
    """
    El horario contra el que el checador mide retardos y faltas. (O-03)

    Es el mismo `HorarioLaboral` de `schemas/asistencia.py`, con los mismos
    defaults (08:00-17:00, 15 minutos de tolerancia, lunes a viernes). Vive
    aparte porque **aquel es de transporte y éste es de almacenamiento**: el del
    cierre viaja en un request y se descarta; éste se guarda con la empresa y
    tiene que sobrevivir a un reinicio.

    `dias_laborables` usa la convención de `datetime.weekday()`: 0 = lunes.
    """

    hora_entrada: str = Field(default="08:00", pattern=HORA)
    hora_salida: str = Field(default="17:00", pattern=HORA)
    tolerancia_minutos: int = Field(default=15, ge=0, le=120)
    dias_laborables: tuple[Annotated[int, Field(ge=0, le=6)], ...] = Field(
        default=(0, 1, 2, 3, 4),
        description="0 = lunes, como `datetime.weekday()`.",
    )

    @model_validator(mode="after")
    def _horario_coherente(self) -> HorarioSchema:
        r"""
        Que la salida sea posterior a la entrada, y que haya al menos un día.

        **Estaba prometido y no se hacía.** El patrón `\d{2}:\d{2}` acepta
        `"99:99"`, `dias_laborables` aceptaba `(9, -4)`, y nada impedía una
        salida anterior a la entrada. Las tres cosas las bloqueaba sólo el
        navegador — y un número de nómina no puede depender de una validación
        de formulario.

        **Sin días laborables el cierre no marca una sola falta** y la nómina
        sale completa siempre: es dinero decidido por un campo vacío.
        """
        if not self.dias_laborables:
            raise ValueError(
                "Tiene que haber al menos un día laborable: sin ninguno, el cierre no "
                "marcaría una sola falta y la nómina saldría completa siempre."
            )
        if len(set(self.dias_laborables)) != len(self.dias_laborables):
            raise ValueError(f"Días laborables repetidos: {self.dias_laborables}.")
        if self.hora_salida <= self.hora_entrada:
            raise ValueError(
                f"La hora de salida ({self.hora_salida}) tiene que ser posterior a la "
                f"de entrada ({self.hora_entrada})."
            )
        return self


class ParametrosSalarialesSchema(BaseModel):
    """
    Las prestaciones del patrón, que alimentan el factor de integración. (O-03)

    **Los mínimos son de ley y se leen del motor, no se copian**: si
    `integracion.py` cambia su fundamento, esto cambia con él. Se validan aquí
    además de en el motor porque un aguinaldo de 10 días capturado en el
    formulario debe rebotar ahí, no tres pantallas después.

    Lo que NO está aquí, y es a propósito: las tablas de ISR, las cuotas del
    IMSS, la UMA y el salario mínimo. Son de ley, viven en el motor con su
    fuente publicada y se actualizan con el DOF, no con un formulario.
    """

    dias_aguinaldo: int = Field(
        default=DIAS_AGUINALDO_DE_LEY,
        ge=DIAS_AGUINALDO_DE_LEY,
        description=f"Mínimo de ley: {DIAS_AGUINALDO_DE_LEY} días (Art. 87 LFT).",
    )
    prima_vacacional: Decimal = Field(
        default=PRIMA_VACACIONAL_DE_LEY,
        ge=PRIMA_VACACIONAL_DE_LEY,
        le=Decimal("1"),
        description="Proporción, no porcentaje: 0.25 es el mínimo de ley (Art. 80 LFT).",
    )
    tabla_vacaciones: tuple[tuple[int, int], ...] = Field(
        default=(),
        description="Escala propia del patrón `[[años, días], ...]`. Vacía = manda la "
        "ley (Art. 76 LFT). **Se rechaza al guardar** renglón por renglón lo que quede "
        "por debajo del mínimo, con el mismo validador que usa `POST /nomina/sbc`.",
    )
    horario: HorarioSchema = Field(default_factory=HorarioSchema)

    @field_validator("tabla_vacaciones")
    @classmethod
    def _tabla_sobre_la_ley(
        cls, valor: tuple[tuple[int, int], ...]
    ) -> tuple[tuple[int, int], ...]:
        """
        La escala se valida **al guardar**, no sólo al integrar el SBC.

        La descripción de este campo decía "se rechaza renglón por renglón" y
        era falso: `ParametrosSalarialesSchema(tabla_vacaciones=[[5, 3]])` se
        construía sin error —la ley son 20 días al año 5— y se persistía tal
        cual. La validación real ocurría después, en `POST /nomina/sbc`, así que
        una tabla ilegal se quedaba guardada y reventaba cada vez que alguien
        abría el alta de un empleado.

        Es el patrón que este repo lleva tres corridas cazando: un contrato que
        declara una propiedad que el código no tiene. Se llama al **mismo**
        validador del motor, no a una copia.
        """
        validar_tabla_vacaciones(valor)
        return valor


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

    rfc: str = Field(
        default="",
        max_length=13,
        description="RFC del patrón. **Vacío cuando no se conoce y nunca inventado**, misma "
        "política que el NSS del empleado. Lo captura la Configuración de empresa (O-01).",
    )
    guia_subdelegacion: str = Field(
        default="",
        max_length=5,
        pattern=r"^\d{0,5}$",
        description="Número de guía que la subdelegación del IMSS asigna al patrón (O-04). "
        "Va en las posiciones 134-138 de cada movimiento afiliatorio y en el registro de "
        "cifras de control. **No se calcula ni se deduce**: lo asigna la subdelegación. "
        "Vacío = no se puede emitir el archivo, y el exportador lo dice.",
    )
    registro_patronal: str = Field(
        default="",
        max_length=11,
        description="Registro patronal del IMSS: **11 caracteres**, los 10 del registro más "
        "su dígito verificador (posiciones 01-10 y 11 del layout de movimientos "
        "afiliatorios del IMSS). Se guarda junto y se parte al exportar. El verificador "
        "**no se calcula**: no hay algoritmo publicado, y un dígito inventado junto a un "
        "registro real es peor que un campo vacío. Vacío = no se pueden emitir "
        "movimientos afiliatorios, y el exportador lo dice en vez de emitirlos mal.",
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
    parametros: ParametrosSalarialesSchema = Field(
        default_factory=ParametrosSalarialesSchema,
        description="Prestaciones y horario del patrón (O-03). Con default completo: una "
        "cartera escrita antes de O-03 no lo trae y tiene que seguir leyéndose — el "
        "default es el mínimo de ley, que es lo que la app aplicaba hasta ahora.",
    )
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
    ilegibles: tuple[str, ...] = Field(
        default=(),
        description="Empleados guardados que **no pasan la validación actual** —un NSS de "
        "una versión anterior, un campo que falta— y por eso NO vienen en `empleados`. Se "
        "reportan en vez de tumbar la respuesta: un documento legado dejaba la cartera "
        "completa en cero. Y se reportan en vez de esconderse, porque un empleado que queda "
        "fuera del cálculo en silencio es el modo de falla que la épica G viene evitando.",
    )
    empleados: tuple[EmpleadoCarteraSchema, ...]


class OperacionResponse(BaseModel):
    exito: bool = True
    mensaje: str
