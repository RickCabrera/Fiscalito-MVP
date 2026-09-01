"""
Endpoint de nómina del periodo (D-06).

**Orquestador, no motor.** Traduce el request a los tipos del dominio, llama a
`nomina_engine.periodo.calcular_periodo` y traduce el resultado de vuelta. No
hay una sola fórmula fiscal en este archivo.

DEMO — ver `docs/D-DEMO-CHECADOR.md`: sin autenticación (la del resto de
`/api/v1` está en S-00b) y no se despliega.
"""

from __future__ import annotations

from datetime import date

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
from app.nomina_engine.cuotas import Consolidado
from app.nomina_engine.periodo import (
    EmpleadoPeriodo,
    IncidenciasPeriodo,
    ReciboPeriodo,
    ResultadoPeriodo,
    calcular_periodo,
)
from app.schemas.nomina import (
    CalcularPeriodoRequest,
    CalcularPeriodoResponse,
    CuotaRamoSchema,
    EmpleadoDemoSchema,
    PartidaSchema,
    PeriodoNomina,
    PlantillaDemoResponse,
    PorcionConsolidada,
    ReciboSchema,
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
        advertencias=resultado.advertencias,
        explicacion=explicacion,
    )
