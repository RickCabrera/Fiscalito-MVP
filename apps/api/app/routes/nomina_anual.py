"""
PTU y cálculo anual del ISR del cliente. (P4-07, P4-08)

Rutas delgadas sobre `nomina_engine/ptu.py` y `ajuste_anual.py`. La renta gravable
y los acumulados se capturan; si el ajuste anual no trae acumulados, se suman del
historial de nóminas guardadas del ejercicio.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends

from app import nomina_servicio as srv
from app.exceptions import FiscalValidationError
from app.nomina_acumulados import acumulados_del_ejercicio
from app.nomina_engine.ajuste_anual import DatosAnuales, ajuste_anual
from app.nomina_engine.ptu import TrabajadorPTU, repartir_ptu
from app.nomina_traduccion import a_json, fichas_por_numero, guardar_calculo, ordinario_mensual
from app.schemas.declaraciones import ErrorResponse
from app.schemas.nomina_p4 import AjusteAnualRequest, CalculoResponse, PTURequest
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina — anuales"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
CERO = Decimal("0.00")


@router.post(
    "/nomina/clientes/{cliente_id}/ptu",
    response_model=CalculoResponse,
    responses=_ERR,
    summary="Reparto de utilidades (Arts. 117-127 LFT; 15 UMA exentas)",
)
def ptu(
    cliente_id: str, req: PTURequest, ctx: Contexto = Depends(contexto_actual)
) -> CalculoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    criterios = srv.criterios_del_cliente(cliente)
    fichas = fichas_por_numero(ctx, cliente)
    trabajadores = []
    for t in req.trabajadores:
        f = fichas.get(t.empleado_no)
        if f is None:
            raise FiscalValidationError(
                f"El empleado {t.empleado_no} no está en la cartera del cliente."
            )
        trabajadores.append(
            TrabajadorPTU(
                t.empleado_no,
                t.dias_trabajados,
                f.salario_diario,
                t.salarios_devengados,
                t.tipo,
                t.promedio_ptu_3_anios,
            )
        )
    r = repartir_ptu(
        req.renta_gravable,
        tuple(trabajadores),
        req.fecha_pago,
        {k: ordinario_mensual(f) for k, f in fichas.items()},
        criterios.isr_extraordinario,
        criterios.ptu_remanente,
    )
    filas = [
        {
            "empleado_no": x.empleado_no,
            "nombre": fichas[x.empleado_no].nombre,
            "zona": fichas[x.empleado_no].zona.value,
            "percepciones": [
                {
                    "tipo": "003",
                    "concepto": "PTU",
                    "importe": x.ptu,
                    "gravado": x.gravado,
                    "exento": x.exento,
                }
            ],
            "total_percepciones": x.ptu,
            "isr": x.isr.isr if x.isr else CERO,
            "total_deducciones": x.isr.isr if x.isr else CERO,
            "neto": x.ptu - (x.isr.isr if x.isr else CERO),
            "detalle": asdict(x),
        }
        for x in r.trabajadores
        if x.participa
    ]
    resultado = {**asdict(r), "recibos": filas}
    avisos = r.avisos  # incluye la nota del remanente según el criterio del cliente
    pid = (
        guardar_calculo(
            ctx,
            cliente,
            "ptu",
            date(req.ejercicio, 1, 1),
            date(req.ejercicio, 12, 31),
            req.fecha_pago,
            req.model_dump(),
            resultado,
            filas,
        )
        if req.guardar and filas
        else None
    )
    return CalculoResponse(
        tipo="ptu", periodo_id=pid, resultado=a_json(resultado), advertencias=avisos
    )


@router.post(
    "/nomina/clientes/{cliente_id}/ajuste-anual",
    response_model=CalculoResponse,
    responses=_ERR,
    summary="Cálculo anual del ISR de sueldos (Art. 97 LISR, tarifa del Art. 152)",
)
def ajuste(
    cliente_id: str, req: AjusteAnualRequest, ctx: Contexto = Depends(contexto_actual)
) -> CalculoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    fichas = fichas_por_numero(ctx, cliente)
    capturados = {t.empleado_no: t for t in req.trabajadores}
    acumulados = {} if capturados else acumulados_del_ejercicio(ctx.db, cliente, req.ejercicio)
    filas, avisos = [], []
    if not capturados:
        avisos.append(
            "Acumulados tomados del historial de nóminas guardadas del ejercicio: "
            "si faltan periodos, el cálculo queda incompleto."
        )
    for no in sorted(set(capturados) | set(acumulados)):
        f = fichas.get(no)
        if f is None:
            raise FiscalValidationError(f"El empleado {no} no está en la cartera del cliente.")
        t, a = capturados.get(no), acumulados.get(no, {})
        datos = DatosAnuales(
            ejercicio=req.ejercicio,
            fecha_alta=f.fecha_alta,
            fecha_baja=f.fecha_baja,
            ingresos_gravados=t.ingresos_gravados if t else a.get("gravado", CERO),
            ingresos_exentos=t.ingresos_exentos if t else a.get("exento", CERO),
            isr_retenido=t.isr_retenido if t else a.get("isr", CERO),
            subsidio_correspondido=t.subsidio_correspondido if t else a.get("subsidio", CERO),
            comunico_que_declara=t.comunico_que_declara if t else False,
            impuesto_local_retenido=t.impuesto_local_retenido if t else CERO,
            tasa_impuesto_local=t.tasa_impuesto_local if t else None,
        )
        filas.append({"empleado_no": no, "nombre": f.nombre, **asdict(ajuste_anual(datos))})
    return CalculoResponse(
        tipo="ajuste_anual",
        resultado=a_json({"ejercicio": req.ejercicio, "trabajadores": filas}),
        advertencias=tuple(avisos),
    )
