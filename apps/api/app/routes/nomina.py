"""
Endpoint de nómina del periodo (D-06).

**Orquestador, no motor.** Traduce el request a los tipos del dominio, llama a
`nomina_engine.periodo.calcular_periodo` y traduce el resultado de vuelta. No
hay una sola fórmula fiscal en este archivo.

DEMO — ver `docs/D-DEMO-CHECADOR.md`: sin autenticación (la del resto de
`/api/v1` está en S-00b) y no se despliega.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Query

from app.constants import CLIENTE_DEMO
from app.demo_nomina import (
    CLAVE_PERIODICIDAD_DEMO,
    PLANTILLA_DEMO,
    PRIMA_RIESGO_DEMO,
    ZONA_DEMO,
    quincena,
)
from app.exceptions import FiscalValidationError
from app.nomina_engine.cfdi_nomina_xml import generar_cfdi_nomina
from app.nomina_engine.cuotas import Consolidado
from app.nomina_engine.duracion_periodo import validar_duracion_periodo
from app.nomina_engine.integracion import (
    clamp_sbc,
    dias_vacaciones_efectivos,
    factor_integracion,
    sbc_fijo,
    validar_tabla_vacaciones,
)
from app.nomina_engine.periodo import (
    EmpleadoPeriodo,
    IncidenciasPeriodo,
    ReciboPeriodo,
    ResultadoPeriodo,
    calcular_periodo,
)
from app.nomina_engine.periodo_sugerido import periodo_sugerido
from app.nomina_engine.recibo import (
    DatosPatron,
    DatosTrabajador,
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)
from app.schemas.declaraciones import ErrorResponse
from app.schemas.empleado import vacaciones_efectivas
from app.schemas.nomina import (
    CalcularPeriodoRequest,
    CalcularPeriodoResponse,
    CFDINominaRequest,
    CFDINominaResponse,
    CuotaRamoSchema,
    EmpleadoDemoSchema,
    PartidaSchema,
    PeriodoNomina,
    PeriodoSugeridoResponse,
    PlantillaDemoResponse,
    PorcionConsolidada,
    ReciboSchema,
    SBCRequest,
    SBCResponse,
)
from app.services.llm_nomina import generar_explicacion_nomina_periodo

router = APIRouter(tags=["Nómina (demo)"])

_AVISO = "DEMO — sin autenticación, no desplegar. "


def _plantilla(req: CalcularPeriodoRequest) -> tuple[tuple[EmpleadoPeriodo, ...], str]:
    """
    Resuelve la plantilla y de dónde salió.

    El default SÓLO aplica al cliente de la demo: calcularle a un cliente real
    la nómina de otras nueve personas —y exportarla en PDF— sería mucho peor
    que responder un error.
    """
    if req.empleados:
        return (
            tuple(
                EmpleadoPeriodo(
                    empleado_no=e.empleado_no,
                    nombre=e.nombre,
                    salario_diario=e.salario_diario,
                    salario_diario_integrado=e.salario_diario_integrado,
                    zona=e.zona,
                )
                for e in req.empleados
            ),
            "request",
        )
    if req.cliente != CLIENTE_DEMO:
        raise FiscalValidationError(
            f"El cliente {req.cliente!r} tiene que mandar su propia plantilla en "
            f"`empleados`. La plantilla por omisión es la del cliente de demostración "
            f"({CLIENTE_DEMO!r}) y no es la nómina de nadie más."
        )
    return PLANTILLA_DEMO, "demo"


def _partidas_percepcion(recibo: ReciboPeriodo) -> tuple[PartidaSchema, ...]:
    return tuple(
        PartidaSchema(
            tipo=p.tipo,
            clave=p.clave,
            concepto=p.concepto,
            importe=p.importe,
            gravado=p.gravado,
            exento=p.exento,
        )
        for p in recibo.recibo.percepciones
    )


def _a_schema(resultado: ReciboPeriodo) -> ReciboSchema:
    recibo = resultado.recibo
    return ReciboSchema(
        empleado_no=resultado.empleado_no,
        nombre=resultado.nombre,
        sbc=resultado.sbc.valor,
        sbc_piso_aplicado=resultado.sbc.piso_aplicado,
        sbc_tope_aplicado=resultado.sbc.tope_aplicado,
        es_salario_minimo=resultado.es_salario_minimo,
        dias_periodo=resultado.dias.dias_periodo,
        dias_ausentismo=resultado.dias.dias_ausentismo,
        dias_pagados=resultado.dias_pagados,
        percepciones=_partidas_percepcion(resultado),
        deducciones=tuple(
            PartidaSchema(tipo=d.tipo, clave=d.clave, concepto=d.concepto, importe=d.importe)
            for d in recibo.deducciones
        ),
        otros_pagos=tuple(
            PartidaSchema(
                tipo=o.tipo,
                clave=o.clave,
                concepto=o.concepto,
                importe=o.importe,
                subsidio_causado=o.subsidio_causado,
            )
            for o in recibo.otros_pagos
        ),
        total_percepciones=recibo.total_percepciones,
        total_deducciones=recibo.total_deducciones,
        neto=recibo.total,
        cuota_obrera=resultado.cuotas.total_obrero,
        cuota_patronal=resultado.cuotas.total_patron,
        absorbio_cuota_obrera=resultado.cuotas.absorbio_cuota_obrera,
        ramos=tuple(
            CuotaRamoSchema(
                clave=r.clave,
                nombre=r.nombre,
                base_diaria=r.base_diaria,
                dias=r.dias,
                patron=r.patron,
                obrero=r.obrero,
                fundamento=r.fundamento,
            )
            for r in resultado.cuotas.ramos
        ),
    )


def _porcion(consolidado: Consolidado) -> PorcionConsolidada:
    return PorcionConsolidada(
        periodicidad=consolidado.periodicidad.value,
        por_ramo=consolidado.por_ramo,
        total_patron=consolidado.total_patron,
        total_obrero=consolidado.total_obrero,
        total=consolidado.total,
        empleados=consolidado.empleados,
    )


def _resumen_para_llm(
    req: CalcularPeriodoRequest, resultado: ResultadoPeriodo
) -> dict:
    """Números YA calculados. El LLM redacta; no suma ni deriva nada."""
    return {
        "periodo": f"{req.periodo.inicio} a {req.periodo.fin}",
        "fecha_pago": str(req.periodo.pago),
        "empleados": len(resultado.recibos),
        "total_percepciones": float(resultado.total_percepciones),
        "total_neto": float(resultado.total_neto),
        "total_isr": float(resultado.total_isr),
        "cuota_obrera": float(resultado.total_obrero),
        "cuota_patronal": float(resultado.total_patron),
        "porcion_mensual": {k: float(v) for k, v in resultado.porcion_mensual.por_ramo.items()},
        "porcion_bimestral": {
            k: float(v) for k, v in resultado.porcion_bimestral.por_ramo.items()
        },
        "advertencias": list(resultado.advertencias),
    }


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
    "/nomina/calcular-periodo",
    response_model=CalcularPeriodoResponse,
    summary=_AVISO + "Calcular la nómina de un periodo",
    description=_AVISO
    + "Recibe la plantilla y las incidencias del checador y devuelve los recibos y "
    "las cuotas por ramo. `porcion_mensual` y `porcion_bimestral` son lo DEVENGADO "
    "en este periodo, no el entero del Art. 39 LSS.",
)
async def calcular(req: CalcularPeriodoRequest) -> CalcularPeriodoResponse:
    empleados, origen = _plantilla(req)
    resultado = calcular_periodo(
        empleados=empleados,
        incidencias=tuple(
            IncidenciasPeriodo(
                empleado_no=i.empleado_no,
                dias_periodo=i.dias_periodo,
                faltas=i.faltas,
                dias_ausentismo=i.dias_ausentismo,
                dias_incapacidad=i.dias_incapacidad,
            )
            for i in req.incidencias
        ),
        fecha_pago=req.periodo.pago,
        prima_riesgo=req.parametros.prima_riesgo,
        clave_periodicidad=req.parametros.clave_periodicidad,
        dias_pagados_override=req.parametros.dias_pagados,
    )

    explicacion = None
    if req.incluir_explicacion:
        explicacion = await generar_explicacion_nomina_periodo(
            _resumen_para_llm(req, resultado)
        )

    return CalcularPeriodoResponse(
        cliente=req.cliente,
        periodo=req.periodo,
        fecha_pago_efectiva=req.periodo.pago,
        origen_plantilla=origen,
        recibos=tuple(_a_schema(r) for r in resultado.recibos),
        porcion_mensual=_porcion(resultado.porcion_mensual),
        porcion_bimestral=_porcion(resultado.porcion_bimestral),
        # O-04: los totales salen del MOTOR y no se recomponen en el cliente.
        # Son el ancla del cuadre de los exportadores: comparar el PDF contra
        # los TXT cuando los dos derivan del mismo módulo del front sería
        # tautológico — sólo cazaría un campo mal posicionado, no una suma mal
        # hecha.
        total_percepciones=resultado.total_percepciones,
        total_neto=resultado.total_neto,
        total_isr=resultado.total_isr,
        advertencias=resultado.advertencias,
        explicacion=explicacion,
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


# ── CFDI de nómina sin timbrar (T4) ─────────────────────────────────────────


def _percepciones_cfdi(partidas: tuple[PartidaSchema, ...]) -> tuple[PartidaPercepcion, ...]:
    """
    Las percepciones tal como llegaron, partidas en gravado y exento.

    `gravado` y `exento` son opcionales en `PartidaSchema` porque deducciones y
    otros pagos no los usan. En una percepción, que llegue `null` NO significa
    cero exento: significa que el emisor no partió la percepción. Se rechaza en
    vez de asumir, porque asumir "todo gravado" o "todo exento" cambia la base
    del ISR de un recibo que alguien va a firmar.
    """
    partidas_cfdi = []
    for p in partidas:
        if p.gravado is None or p.exento is None:
            raise FiscalValidationError(
                f"La percepción {p.tipo} ({p.concepto}) no trae el desglose "
                f"gravado/exento que el CFDI exige. Sale de "
                f"`/nomina/calcular-periodo`, que siempre lo manda."
            )
        partidas_cfdi.append(
            PartidaPercepcion(
                tipo=p.tipo,
                clave=p.clave,
                concepto=p.concepto,
                gravado=p.gravado,
                exento=p.exento,
            )
        )
    return tuple(partidas_cfdi)


def _antiguedad_en_semanas(inicio: date, fin_del_periodo: date) -> str:
    """
    `Antigüedad` del complemento, en el formato ISO 8601 `P##W` del doc 24 §2.

    **Semanas COMPLETAS transcurridas**, medidas contra la fecha final del
    periodo que se paga y no contra hoy: un recibo de una quincena de agosto
    emitido en septiembre no le agrega semanas al trabajador.

    Es aritmética de calendario, no de dinero, y por eso vive en la ruta y no
    en el motor: no toca ninguna base gravable. El emisor que ya la traiga
    —porque su histórico viene de un CFDI timbrado— la manda y ésta no se usa.
    """
    dias = (fin_del_periodo - inicio).days
    if dias < 0:
        raise FiscalValidationError(
            f"La relación laboral empieza el {inicio}, después del fin del "
            f"periodo ({fin_del_periodo}): no hay antigüedad que declarar."
        )
    return f"P{dias // 7}W"


@router.post(
    "/nomina/cfdi",
    response_model=CFDINominaResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Generar el CFDI de nómina 4.0 + complemento 1.2, SIN TIMBRAR",
    description="Serializa un recibo ya calculado a XML **estructuralmente válido contra "
    "los XSD del SAT y fiscalmente nada**: sin `tfd:TimbreFiscalDigital` y con centinelas "
    "explícitos en los atributos de sello.\n\n"
    "**No timbra y no habla con ningún PAC** — está fuera de alcance por el `CLAUDE.md` de "
    "la raíz. `timbrado` viaja en la respuesta y siempre vale `false`.\n\n"
    "**No calcula nada.** Los importes llegan de `/nomina/calcular-periodo` y aquí sólo se "
    "suman para los totales que el comprobante exige (`nomina_engine/recibo.py` es "
    "aritmética pura sobre partidas dadas). Ni ISR ni cuotas se tocan.\n\n"
    "**No inventa identidades:** RFC, CURP, NSS, códigos postales, registro patronal y "
    "clave de entidad son obligatorios. Sin ellos responde 422 diciendo cuál falta, que es "
    "lo único honesto — un CFDI con datos de relleno lleva el nombre de una persona real.\n\n"
    "**Lo que el XSD NO valida:** las reglas de la Guía de llenado ni las validaciones "
    "adicionales del Anexo 20. Que valide aquí no es evidencia de que un PAC lo aceptaría.",
)
async def cfdi_de_nomina(req: CFDINominaRequest) -> CFDINominaResponse:
    trabajador = req.trabajador
    recibo = Recibo(
        percepciones=_percepciones_cfdi(req.recibo.percepciones),
        deducciones=tuple(
            PartidaDeduccion(tipo=d.tipo, clave=d.clave, concepto=d.concepto, importe=d.importe)
            for d in req.recibo.deducciones
        ),
        otros_pagos=tuple(
            PartidaOtroPago(
                tipo=o.tipo,
                clave=o.clave,
                concepto=o.concepto,
                importe=o.importe,
                subsidio_causado=o.subsidio_causado,
            )
            for o in req.recibo.otros_pagos
        ),
    )

    xml = generar_cfdi_nomina(
        recibo=recibo,
        patron=DatosPatron(
            rfc=req.patron.rfc,
            nombre=req.patron.nombre,
            regimen_fiscal=req.patron.regimen_fiscal,
            registro_patronal=req.patron.registro_patronal,
            codigo_postal=req.patron.codigo_postal,
            clave_entidad=req.patron.clave_entidad,
        ),
        trabajador=DatosTrabajador(
            rfc=trabajador.rfc,
            nombre=trabajador.nombre,
            curp=trabajador.curp,
            numero_seguridad_social=trabajador.numero_seguridad_social,
            codigo_postal=trabajador.codigo_postal,
            fecha_inicio_relacion_laboral=trabajador.fecha_inicio_relacion_laboral,
            antiguedad=trabajador.antiguedad
            or _antiguedad_en_semanas(
                trabajador.fecha_inicio_relacion_laboral, req.periodo.fin
            ),
            tipo_contrato=trabajador.tipo_contrato,
            tipo_regimen=trabajador.tipo_regimen,
            numero_empleado=trabajador.numero_empleado,
            puesto=trabajador.puesto,
            departamento=trabajador.departamento,
            riesgo_puesto=trabajador.riesgo_puesto,
            periodicidad_pago=trabajador.periodicidad_pago,
            salario_base_cotizacion=trabajador.salario_base_cotizacion,
            salario_diario_integrado=trabajador.salario_diario_integrado,
            sindicalizado=trabajador.sindicalizado,
            tipo_jornada=trabajador.tipo_jornada,
        ),
        # La hora de emisión es la del servidor y NO es un dato del negocio: el
        # comprobante no está timbrado, así que no hay plazo de 72 horas que
        # cumplir ni fecha que conciliar. Lo que sí importa —y viene del
        # periodo— son las tres fechas de pago del complemento.
        fecha_emision=datetime.now(),
        fecha_inicial_pago=req.periodo.inicio,
        fecha_final_pago=req.periodo.fin,
        fecha_pago=req.periodo.pago,
        # `NumDiasPagados` es fraccionable (doc 24 §2) y el motor lo devuelve
        # entero: se promueve sin redondear a nada.
        dias_pagados=Decimal(req.recibo.dias_pagados),
        tipo_nomina=req.tipo_nomina,
        serie=req.serie,
        folio=req.folio,
    )

    return CFDINominaResponse(
        xml=xml,
        nombre_archivo=(
            f"cfdi-nomina-sin-timbrar-{req.recibo.empleado_no}-"
            f"{req.periodo.inicio}-{req.periodo.fin}.xml"
        ),
        advertencia=(
            "Pre-recibo SIN TIMBRAR. No tiene valor fiscal: no lleva Timbre Fiscal "
            "Digital y sus atributos de sello son centinelas. Para que sea un CFDI "
            "hay que timbrarlo con un PAC."
        ),
    )
