"""
Schemas del calendario de obligaciones patronales (E-07 / F1-06).

**Demo — datos estáticos, sin autenticación, no desplegar**, igual que el resto
de la cartera del despacho: la persistencia y el alta de clientes son F1-09.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.nomina_engine.plazos_patronales import RegimenDePlazo


class ObligacionPatronalSchema(BaseModel):
    """
    Una obligación del patrón, ya etiquetada con el cliente al que pertenece.

    **`regimen_de_plazo` no es decorativo.** Dice qué regla produjo
    `fecha_limite`, y existe para que una vista que junta obligaciones del IMSS
    y del SAT no las presente como si obedecieran la misma norma: el viernes es
    inhábil para el IMSS (Art. 3 RACERF) y hábil para el SAT (CFF Art. 12), así
    que el mismo mes puede tener dos fechas distintas. `imss_sin_prorroga` es
    del IMSS pero **no** se corre (§D23): son cinco valores, no cuatro, porque
    etiquetar esa como `imss` prometería una prórroga que no ocurre. Ver
    `knowledge_base/nomina/25_calendario_laboral_2026.md` §4 y §5.
    """

    cliente_id: str
    cliente_nombre: str

    clave: str = Field(
        description="Identificador estable del tipo de obligación (`imss_mensual`, "
        "`imss_bimestral`, `aviso_variables`, `isr_retenido`, `prima_rt`, `aguinaldo`, "
        "`ptu_moral`, `ptu_fisica`). Es lo que debe usarse para agrupar, nunca el `nombre`."
    )
    nombre: str
    descripcion: str
    fecha_limite: date
    periodicidad: str = Field(description="`mensual`, `bimestral` o `anual`.")
    periodo_cubierto: str = Field(
        description="Qué periodo REPORTA la obligación, que no es el de su vencimiento: "
        "las cuotas de marzo vencen en abril, y la prima de RT que se presenta en febrero "
        "reporta el ejercicio anterior."
    )
    fundamento: str
    regimen_de_plazo: RegimenDePlazo
    condicional: bool = Field(
        description="`true` cuando la obligación **puede no aplicarle** a este patrón y el "
        "modelo de cliente no alcanza para saberlo (no se registra el tipo de salario ni la "
        "personalidad jurídica). No significa opcional: significa verifícalo. Siempre viene "
        "con `nota`."
    )
    nota: str = Field(
        default="",
        description="Advertencia sobre este dato: qué hay que verificar si es condicional, o "
        "que la fecha cae en día inhábil y **no** se prorroga.",
    )


class CalendarioPatronalResponse(BaseModel):
    """
    Calendario patronal de toda la cartera, ordenado por fecha límite.

    `anio_de_las_cuotas` es el año **del periodo que se reporta**, no el del
    vencimiento: las cuotas de diciembre de ese año vencen en enero del
    siguiente y sí están aquí; las de diciembre del año anterior, que vencen en
    enero de éste, no.
    """

    exito: bool = True
    anio_de_las_cuotas: int
    cubre_desde: date = Field(
        description="Primer vencimiento de la respuesta. **No es el 1 de enero**: las cuotas de "
        "enero vencen en febrero, así que un calendario pedido por año de las cuotas empieza "
        "en febrero. Va en el cuerpo para que la pantalla pueda decir qué rango está "
        "enseñando en vez de mostrar un enero vacío sin explicación."
    )
    cubre_hasta: date = Field(
        description="Último vencimiento, que cae en **enero del año siguiente** (las cuotas de "
        "diciembre)."
    )
    total_obligaciones: int
    obligaciones: tuple[ObligacionPatronalSchema, ...]
    advertencias: tuple[str, ...] = Field(
        description="Lo que la respuesta NO cubre. Va en el cuerpo y no sólo en la "
        "documentación para que una pantalla pueda imprimirlo sin volver a redactarlo."
    )
