"""
Nómina del periodo (D-06): periodo sugerido, plantilla de la demo, cálculo y SBC.

**Orquestador, no motor.** Traduce el request a los tipos del dominio, llama a
`nomina_engine.periodo.calcular_periodo` y traduce el resultado de vuelta. No
hay una sola fórmula fiscal en este archivo.

DEMO — ver `docs/D-DEMO-CHECADOR.md`: no se despliega. La sesión la exige `app/main.py`
para todo `/api/v1` (P0-02).
"""

from __future__ import annotations

from datetime import date

from fastapi import Query

from app.constants import CLIENTE_DEMO
from app.demo_nomina import (
    CLAVE_PERIODICIDAD_DEMO,
    PLANTILLA_DEMO,
    PRIMA_RIESGO_DEMO,
    ZONA_DEMO,
    quincena,
)
from app.exceptions import FiscalValidationError
from app.nomina_engine.duracion_periodo import validar_duracion_periodo
from app.nomina_engine.integracion import (
    clamp_sbc,
    dias_vacaciones_efectivos,
    factor_integracion,
    sbc_fijo,
    validar_tabla_vacaciones,
)
from app.nomina_engine.periodo_sugerido import periodo_sugerido
from app.routes.nomina._comun import _AVISO, router
from app.schemas.declaraciones import ErrorResponse
from app.schemas.empleado import vacaciones_efectivas
from app.schemas.nomina import (
    EmpleadoDemoSchema,
    PeriodoNomina,
    PeriodoSugeridoResponse,
    PlantillaDemoResponse,
    SBCRequest,
    SBCResponse,
)


@router.get(
    "/nomina/periodo-sugerido",
    response_model=PeriodoSugeridoResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Último periodo terminado para una periodicidad de pago",
    description="El periodo que la app propone, **según la periodicidad del patrón**. "
    "Antes de O-03 el front proponía siempre una quincena —copiaba la del cliente de "
    "demostración a todos, sin mirar su clave— así que elegir Mensual dejaba a la empresa "
    "con un periodo que el propio motor rechaza. La regla vive aquí y no en TypeScript "
    "porque de la `fecha_pago` dependen la UMA, el salario mínimo, la tarifa del Anexo 8 y "
    "el transitorio de enero del subsidio (§D18). "
    "Siempre el último periodo **terminado**, nunca el que está en curso: `cerrar_periodo` "
    "marca falta todo día laborable sin checada, incluidos los que aún no llegan.",
)
async def periodo_para_la_periodicidad(
    clave_periodicidad: str = Query(
        description="Clave de `c_PeriodicidadPago`: 01 diaria, 02 semanal, 04 quincenal, "
        "05 mensual. Las demás no tienen tarifa publicada (§D10) y devuelven 422.",
    ),
    fecha: date | None = Query(
        default=None,
        description="Desde qué día se mira. Por defecto, hoy en el servidor.",
    ),
) -> PeriodoSugeridoResponse:
    hoy = fecha or date.today()
    sugerido = periodo_sugerido(clave_periodicidad, hoy)
    dias = (sugerido.fin - sugerido.inicio).days + 1
    # Se valida lo que se propone. Proponer un periodo que el propio motor
    # rechazaría al calcular es el callejón sin salida que O-03 viene a cerrar,
    # y sin esta línea sería una promesa del docstring en vez de una garantía.
    validar_duracion_periodo(clave_periodicidad, dias)
    return PeriodoSugeridoResponse(
        clave_periodicidad=clave_periodicidad,
        # `fecha_pago` explícita, no None: la pantalla tiene que poder mostrar
        # con qué fecha se va a calcular sin replicar el default (§D18).
        periodo=PeriodoNomina(
            inicio=sugerido.inicio, fin=sugerido.fin, fecha_pago=sugerido.fin
        ),
        dias_naturales=dias,
    )


@router.get(
    "/nomina/demo/plantilla",
    response_model=PlantillaDemoResponse,
    summary=_AVISO + "Plantilla del cliente de demostración",
    description=_AVISO
    + "Los empleados, la prima de riesgo, la periodicidad y el periodo sugerido del "
    "cliente de la demo. Existe para que la pantalla no tenga que hardcodear ninguna "
    "constante fiscal: `prima_riesgo` tiene fundamento legal y `periodo_sugerido` sale "
    "de la regla de quincena, no de las fechas de las checadas.",
)
async def plantilla_demo(
    cliente: str = Query(default=CLIENTE_DEMO, description="Sólo el cliente de la demo"),
) -> PlantillaDemoResponse:
    if cliente != CLIENTE_DEMO:
        raise FiscalValidationError(
            f"El cliente {cliente!r} tiene que mandar su propia plantilla en "
            f"`empleados`. La plantilla por omisión es la del cliente de demostración "
            f"({CLIENTE_DEMO!r}) y no es la nómina de nadie más."
        )
    sugerido = quincena(date.today())
    return PlantillaDemoResponse(
        cliente=cliente,
        empleados=tuple(
            EmpleadoDemoSchema(empleado_no=e.empleado_no, nombre=e.nombre)
            for e in PLANTILLA_DEMO
        ),
        prima_riesgo=PRIMA_RIESGO_DEMO,
        clave_periodicidad=CLAVE_PERIODICIDAD_DEMO,
        zona=ZONA_DEMO,
        # `fecha_pago` explícita, no None: la pantalla tiene que poder mostrar
        # con qué fecha se va a calcular sin replicar el default (§D18).
        periodo_sugerido=PeriodoNomina(
            inicio=sugerido.inicio, fin=sugerido.fin, fecha_pago=sugerido.fin
        ),
    )


@router.post(
    "/nomina/sbc",
    response_model=SBCResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Integrar un salario diario a SBC",
    description="Integra un salario **fijo** (Art. 30 fr. I LSS) con el factor del "
    "Art. 27 y lo acota entre 1 salario mínimo y 25 UMA (Art. 28). Es lo que la "
    "pantalla de alta de empleado llama mientras se teclea el salario, para que el "
    "front **no reimplemente la fórmula**.\n\n"
    "**Orquestador, no motor:** llama a `factor_integracion`, `sbc_fijo` y `clamp_sbc` "
    "de `nomina_engine/integracion.py` y no calcula nada por su cuenta.\n\n"
    "**Lo que NO hace, a propósito:** no recalcula un SDI que ya venga dado (§D9: "
    "cuando sale de un CFDI timbrado es dato de entrada); no acepta conceptos "
    "integrables (§D5: el motor no decide qué integra, y mandar una despensa completa "
    "sobreintegraría); no acota en silencio (devuelve las banderas); y no usa LLM ni "
    "acepta `incluir_explicacion` — aquí no hay nada que explicar que no sea el número.",
)
async def integrar_sbc(req: SBCRequest) -> SBCResponse:
    # Los días de vacaciones se resuelven ANTES de llamar al motor y se
    # devuelven: si el motor recibiera 0 y aplicara el de ley por su cuenta, la
    # pantalla no podría decir con cuántos días integró.
    #
    # La convención "0 = los de ley" se pide a `PrestacionesSchema`, no se
    # reescribe aquí. Tenerla en dos lugares es la misma segunda verdad que este
    # endpoint existe para evitar, sólo que movida de TypeScript a Python: el día
    # que alguien cambie el centinela a `None`, cambiaría una sola.
    #
    # O-03: con TABLA del patrón manda la tabla, y se valida antes de usarla.
    # `dias_vacaciones_efectivos` devuelve `max(renglón, ley)`, así que una
    # tabla corta no puede bajarle los días a quien gana antigüedad — el
    # Art. 27 LSS integra lo que el patrón otorga, no el mínimo.
    if req.tabla_vacaciones:
        validar_tabla_vacaciones(req.tabla_vacaciones)
        dias_vacaciones = dias_vacaciones_efectivos(
            req.anios_servicio_cumplidos, req.tabla_vacaciones
        )
    else:
        dias_vacaciones = vacaciones_efectivas(
            req.dias_vacaciones, req.anios_servicio_cumplidos
        )

    # `factor_integracion` levanta `FiscalValidationError` con aguinaldo < 15 y
    # con prima fuera de [0.25, 1]. NO se atrapa: ese segundo guard es el que
    # caza el 25 en vez de 0.25, que infla el SBC 77% sin que ninguna tabla lo
    # detecte. Un "mejor esfuerzo" aquí mataría la validación; el handler global
    # lo convierte en 422 con su mensaje.
    factor = factor_integracion(req.dias_aguinaldo, dias_vacaciones, req.prima_vacacional)
    sin_acotar = sbc_fijo(req.salario_diario, factor)
    acotado = clamp_sbc(sin_acotar, req.fecha, req.zona)

    return SBCResponse(
        factor=factor,
        dias_vacaciones_aplicados=dias_vacaciones,
        sbc_sin_acotar=sin_acotar,
        sbc=acotado.valor,
        piso_aplicado=acotado.piso_aplicado,
        tope_aplicado=acotado.tope_aplicado,
        piso=acotado.piso,
        tope=acotado.tope,
        fundamento="Arts. 27, 28 y 30 fr. I LSS; Arts. 76, 80 y 87 LFT.",
    )


