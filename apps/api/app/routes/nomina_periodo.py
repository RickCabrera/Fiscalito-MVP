"""
Nómina del periodo, autenticada y con historial. (P4-01, P4-02, P4-03, P4-04, P4-05)

P4-01: `POST /nomina/calcular-periodo` ya no le cree al navegador. La plantilla sale
de la cartera SQL del cliente (`contexto_actual` + `cliente_o_404`); si el cuerpo trae
`empleados` se IGNORAN y la respuesta lo advierte. Se eligió ignorar y no 422 para no
romper a un front viejo en pleno despacho: lo que importa es que no cambien el
resultado, y eso lo fija un test.

Orquestador, no motor: las fórmulas viven en `app/nomina_engine/`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends

from app import nomina_servicio as srv
from app.exceptions import FiscalValidationError
from app.nomina_engine.criterios import OPCIONES, CriteriosNomina
from app.nomina_engine.cuotas import consolidado_bimestral, consolidado_mensual
from app.nomina_engine.duracion_periodo import validar_duracion_periodo
from app.nomina_engine.periodo import DIAS_AUSENTISMO_REVISION_MANUAL
from app.nomina_engine.periodo_completo import (
    Incidencia,
    ReciboCompleto,
    calcular_recibo,
    validar_periodo,
)
from app.nomina_engine.tablas_isr_periodicas import TARIFAS_DERIVADAS
from app.nomina_traduccion import recibo_como_dict, variables_del_schema
from app.schemas.declaraciones import ErrorResponse
from app.schemas.nomina import CalcularPeriodoRequest, CalcularPeriodoResponse
from app.schemas.nomina_p4 import (
    CriteriosResponse,
)
from app.services.llm_nomina import generar_explicacion_nomina_periodo
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
CERO = Decimal("0.00")


def _porcion(c: Any) -> dict[str, Any]:
    return {
        "periodicidad": c.periodicidad.value,
        "por_ramo": c.por_ramo,
        "total_patron": c.total_patron,
        "total_obrero": c.total_obrero,
        "total": c.total,
        "empleados": c.empleados,
    }


@router.post(
    "/nomina/calcular-periodo",
    response_model=CalcularPeriodoResponse,
    responses=_ERR,
    summary="Calcular (y guardar) la nómina de un periodo del cliente",
    description="La plantilla sale de la cartera del cliente (P4-01); `empleados` del cuerpo "
    "se ignora. Aplica los criterios del cliente (§D26/§D27/§D28), las variables capturadas "
    "(P4-05) y, con `tipo=asimilados`, el Art. 94 LISR sin IMSS ni subsidio (P4-04). Guarda "
    "el periodo en el historial (P4-02) salvo `guardar=false`.",
)
async def calcular(
    req: CalcularPeriodoRequest, ctx: Contexto = Depends(contexto_actual)
) -> CalcularPeriodoResponse:
    cliente = cliente_o_404(ctx, req.cliente)
    criterios = srv.criterios_del_cliente(cliente)
    clave = req.parametros.clave_periodicidad or srv.periodicidad_del_cliente(cliente)
    prima = req.parametros.prima_riesgo or srv.prima_riesgo_del_cliente(cliente)
    inicio, fin, pago = req.periodo.inicio, req.periodo.fin, req.periodo.pago
    incidencias = tuple(
        Incidencia(i.empleado_no, i.dias_periodo, i.faltas, i.dias_ausentismo, i.dias_incapacidad)
        for i in req.incidencias
    )
    dias = (fin - inicio).days + 1
    if incidencias and validar_periodo(clave, incidencias) != dias:
        raise FiscalValidationError(
            f"Las incidencias no miden lo mismo que el periodo {inicio} a {fin} ({dias} días)."
        )
    validar_duracion_periodo(clave, dias)
    asimilados = req.tipo == "asimilados"
    plantilla, avisos = srv.plantilla_del_cliente(ctx.db, cliente, inicio, fin, asimilados)
    if req.empleados:
        avisos.append(
            "Se ignoró la plantilla enviada en `empleados`: la nómina se calcula con "
            "los empleados de la cartera del cliente (P4-01)."
        )
    por_no = {i.empleado_no: i for i in incidencias}
    de_plantilla = {e.empleado_no for e in plantilla}
    # Las incidencias del otro régimen (sueldos en una de asimilados) no son huérfanas:
    # simplemente no entran a esta nómina.
    de_la_cartera = {f.empleado_no for f in srv.fichas_del_cliente(ctx.db, cliente)[0]}
    huerfanas = sorted(set(por_no) - de_la_cartera)
    if huerfanas:
        raise FiscalValidationError(
            f"Hay incidencias de empleados que no están en la plantilla: {', '.join(huerfanas)}."
        )
    variables = {v.empleado_no: variables_del_schema(v) for v in req.variables}
    ajenas = sorted(set(variables) - de_plantilla)
    if ajenas:
        raise FiscalValidationError(
            f"Variables de empleados fuera de la plantilla: {', '.join(ajenas)}."
        )
    sin_incidencias = sorted(e.empleado_no for e in plantilla if e.empleado_no not in por_no)
    if sin_incidencias and not asimilados:
        avisos.append(
            f"Sin incidencias del cierre, NO entran en este cálculo: {', '.join(sin_incidencias)}."
        )
    recibos: list[ReciboCompleto] = []
    for e in plantilla:
        inc = por_no.get(e.empleado_no) or (Incidencia(e.empleado_no, dias) if asimilados else None)
        if inc is None:
            continue
        r = calcular_recibo(
            e,
            inc,
            variables.get(e.empleado_no),
            inicio,
            fin,
            pago,
            clave,
            prima,
            criterios,
            req.parametros.dias_pagados,
        )
        recibos.append(r)
        avisos.extend(r.avisos)
        if r.parcial:
            avisos.append(
                f"{e.empleado_no}: periodo PARCIAL ({r.dias_en_periodo} de {dias} días), "
                f"criterio §D26 = {criterios.parcial}."
            )
    prolongado = sorted(
        r.empleado_no for r in recibos if r.dias_ausentismo > DIAS_AUSENTISMO_REVISION_MANUAL
    )
    if prolongado:
        avisos.append(
            f"Estos empleados superan {DIAS_AUSENTISMO_REVISION_MANUAL} días de ausentismo en el "
            f"periodo: {', '.join(prolongado)}. El ausentismo prolongado puede tener un "
            f"tratamiento distinto que el motor NO aplica: se cobran las cuotas completas de "
            f"cada ramo (§D20). Requiere revisión manual."
        )
    if not recibos:
        raise FiscalValidationError(
            "No hay a quién calcularle: la plantilla del periodo está vacía."
        )
    if clave in TARIFAS_DERIVADAS:
        avisos.append("Tarifa DERIVADA, no publicada: " + TARIFAS_DERIVADAS[clave] + ".")
    cuotas = tuple(r.cuotas for r in recibos if r.cuotas)
    mensual, bimestral = consolidado_mensual(cuotas), consolidado_bimestral(cuotas)
    avisos.insert(
        0,
        f"Las cuotas son la porción devengada en este periodo de {dias} días "
        f"naturales, NO el entero mensual ni el bimestral del Art. 39 LSS.",
    )
    if any(r.sbc_variable_integrable for r in recibos):
        avisos.append(
            "Hay percepciones variables que integran al SBC: se reflejan en el SBC del "
            "bimestre siguiente (Art. 30 fr. II LSS), no en éste."
        )
    datos = [recibo_como_dict(r) for r in recibos]
    respuesta = CalcularPeriodoResponse(
        cliente=req.cliente,
        periodo=req.periodo,
        fecha_pago_efectiva=pago,
        origen_plantilla="cartera",
        recibos=tuple(datos),
        porcion_mensual=_porcion(mensual),
        porcion_bimestral=_porcion(bimestral),
        total_percepciones=sum((r.recibo.total_percepciones for r in recibos), start=CERO),
        total_neto=sum((r.recibo.total for r in recibos), start=CERO),
        total_isr=sum((r.recibo.total_impuestos_retenidos for r in recibos), start=CERO),
        advertencias=tuple(avisos),
        tipo=req.tipo,
        criterios=criterios.como_dict(),
        clave_periodicidad=clave,
    )
    if req.incluir_explicacion:
        respuesta.explicacion = await generar_explicacion_nomina_periodo(
            {
                "periodo": f"{inicio} a {fin}",
                "fecha_pago": str(pago),
                "empleados": len(recibos),
                "total_percepciones": float(respuesta.total_percepciones),
                "total_neto": float(respuesta.total_neto),
                "total_isr": float(respuesta.total_isr),
                "cuota_obrera": float(mensual.total_obrero + bimestral.total_obrero),
                "cuota_patronal": float(mensual.total_patron + bimestral.total_patron),
                "porcion_mensual": {k: float(v) for k, v in mensual.por_ramo.items()},
                "porcion_bimestral": {k: float(v) for k, v in bimestral.por_ramo.items()},
                "advertencias": list(avisos),
            }
        )
    if req.guardar:
        resultado = respuesta.model_dump(mode="json")
        filas = [
            {
                **d,
                "isr": next((x["importe"] for x in d["deducciones"] if x["tipo"] == "002"), CERO),
                "subsidio": d["subsidio_causado"],
            }
            for d in resultado["recibos"]
        ]
        periodo = srv.guardar_periodo(
            ctx.db,
            cliente,
            ctx.despacho_id,
            ctx.uid,
            tipo=req.tipo,
            clave=clave,
            inicio=inicio,
            fin=fin,
            fecha_pago=pago,
            criterios=criterios.como_dict(),
            parametros=srv.parametros_vigentes(pago, clave, plantilla[0].zona),
            entrada=req.model_dump(mode="json", exclude={"empleados"}),
            resultado=resultado,
            recibos=filas,
        )
        periodo.resultado = {**resultado, "periodo_id": periodo.id}
        respuesta.periodo_id = periodo.id
    return respuesta


@router.get(
    "/nomina/criterios",
    response_model=CriteriosResponse,
    summary="Opciones de los criterios de nómina, con su explicación y default",
)
def criterios_disponibles(ctx: Contexto = Depends(contexto_actual)) -> CriteriosResponse:
    return CriteriosResponse(defaults=CriteriosNomina().como_dict(), opciones=OPCIONES)
