"""
Horario, parámetros salariales y criterios de nómina de un cliente de la cartera (R-07, O-03,
P4). Salieron de `schemas/cartera.py` en P6-05 (tope de 300 líneas) sin cambiar nada;
`schemas.cartera` los reexporta.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.nomina_engine.integracion import (
    DIAS_AGUINALDO_DE_LEY,
    PRIMA_VACACIONAL_DE_LEY,
    validar_tabla_vacaciones,
)

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
    def _tabla_sobre_la_ley(cls, valor: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
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


class CriteriosNominaSchema(BaseModel):
    """
    Criterios de nómina del cliente (P4, DP-3). Opciones y explicación en
    `app/nomina_engine/criterios.py:OPCIONES`; los defaults son los documentados ahí.
    """

    parcial: Literal["tarifa_proporcional", "tarifa_periodo"] = "tarifa_proporcional"
    febrero: Literal["quince_siempre", "dias_calendario"] = "quince_siempre"
    prestaciones: Literal["mayor", "ficha"] = "mayor"
    isr_extraordinario: Literal["art_96", "art_174"] = "art_96"
    ptu_remanente: Literal["no_se_reparte", "redistribuir", "sumar_siguiente_ejercicio"] = (
        "no_se_reparte"
    )
