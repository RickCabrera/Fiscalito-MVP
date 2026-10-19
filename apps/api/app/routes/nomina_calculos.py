"""
Nóminas extraordinarias del cliente: aguinaldo y finiquito. (P4-06, P4-08)

Rutas delgadas sobre `nomina_engine/aguinaldo.py` y `finiquito.py`. Los datos del
trabajador salen de la cartera (P4-01); la causa de la baja se captura. Cada
cálculo se guarda en el historial con su tipo (P4-02) salvo `guardar=false`.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends

from app import nomina_servicio as srv
from app.exceptions import FiscalValidationError
from app.nomina_engine.aguinaldo import calcular_aguinaldo, dias_trabajados_en_el_anio
from app.nomina_engine.criterios import prestacion_efectiva
from app.nomina_engine.finiquito import DatosSeparacion, calcular_finiquito
from app.nomina_engine.integracion import dias_vacaciones_efectivos
from app.nomina_traduccion import (
    a_json,
    dias_aguinaldo_efectivos,
    fichas_por_numero,
    guardar_calculo,
    ordinario_mensual,
    parametros_patron,
)
from app.schemas.declaraciones import ErrorResponse
from app.schemas.nomina_p4 import AguinaldoRequest, CalculoResponse, FiniquitoRequest
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina — extraordinarias"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
CERO = Decimal("0.00")


@router.post(
    "/nomina/clientes/{cliente_id}/aguinaldo",
    response_model=CalculoResponse,
    responses=_ERR,
    summary="Aguinaldo del ejercicio (Art. 87 LFT, 30 UMA exentas, Art. 96 o 174 RLISR)",
)
def aguinaldo(
    cliente_id: str, req: AguinaldoRequest, ctx: Contexto = Depends(contexto_actual)
) -> CalculoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    criterios = srv.criterios_del_cliente(cliente)
    fichas = fichas_por_numero(ctx, cliente)
    elegidos = req.empleados or tuple(k for k, f in fichas.items() if f.tipo_regimen == "02")
    filas, avisos = [], []
    for no in elegidos:
        f = fichas.get(no)
        if f is None:
            raise FiscalValidationError(f"El empleado {no} no está en la cartera del cliente.")
        hasta = min(req.fecha_pago, f.fecha_baja) if f.fecha_baja else date(req.ejercicio, 12, 31)
        dias = dias_trabajados_en_el_anio(f.fecha_alta, req.ejercicio, hasta)
        if f.fecha_alta is None:
            avisos.append(f"{no}: sin fecha de alta; se toma el año completo.")
        r = calcular_aguinaldo(
            f.salario_diario,
            dias_aguinaldo_efectivos(cliente, f),
            dias,
            req.fecha_pago,
            ordinario_mensual(f),
            criterios.isr_extraordinario,
            req.exento_ya_aplicado.get(no, CERO),
        )
        filas.append(
            {
                "empleado_no": no,
                "nombre": f.nombre,
                "zona": f.zona.value,
                "percepciones": [
                    {
                        "tipo": "002",
                        "concepto": "AGUINALDO",
                        "importe": r.importe,
                        "gravado": r.gravado,
                        "exento": r.exento,
                    }
                ],
                "deducciones": [{"tipo": "002", "importe": r.isr.isr}] if r.isr.isr else [],
                "total_percepciones": r.importe,
                "total_deducciones": r.isr.isr,
                "isr": r.isr.isr,
                "neto": r.neto,
                "detalle": asdict(r),
            }
        )
    resultado = {
        "ejercicio": req.ejercicio,
        "metodo_isr": criterios.isr_extraordinario,
        "recibos": filas,
    }
    pid = (
        guardar_calculo(
            ctx,
            cliente,
            "aguinaldo",
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
        tipo="aguinaldo", periodo_id=pid, resultado=a_json(resultado), advertencias=tuple(avisos)
    )


@router.post(
    "/nomina/clientes/{cliente_id}/finiquito",
    response_model=CalculoResponse,
    responses=_ERR,
    summary="Finiquito o liquidación (LFT 48-50, 79, 87, 162; LISR 93 fr. XIII, 95, 96)",
)
def finiquito(
    cliente_id: str, req: FiniquitoRequest, ctx: Contexto = Depends(contexto_actual)
) -> CalculoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    f = fichas_por_numero(ctx, cliente).get(req.empleado_no)
    if f is None:
        raise FiscalValidationError(
            f"El empleado {req.empleado_no} no está en la cartera del cliente."
        )
    if f.fecha_alta is None:
        raise FiscalValidationError(
            f"{req.empleado_no}: sin fecha de alta no hay antigüedad que calcular."
        )
    criterios = srv.criterios_del_cliente(cliente)
    patron = parametros_patron(cliente)
    anios = max((req.fecha_baja - f.fecha_alta).days // 365, 0)
    vacaciones = dias_vacaciones_efectivos(
        anios + 1, tuple(tuple(x) for x in patron.get("tabla_vacaciones", ()))
    )
    prima = prestacion_efectiva(
        Decimal(str(patron.get("prima_vacacional", "0.25"))),
        f.prestaciones.prima_vacacional,
        criterios.prestaciones,
    )
    d = DatosSeparacion(
        fecha_alta=f.fecha_alta,
        fecha_baja=req.fecha_baja,
        salario_diario=f.salario_diario,
        salario_diario_integrado=f.salario_diario_integrado,
        causa=req.causa,
        zona=f.zona,
        dias_aguinaldo=dias_aguinaldo_efectivos(cliente, f),
        dias_vacaciones_anio=vacaciones,
        prima_vacacional=prima,
        dias_vacaciones_pendientes=req.dias_vacaciones_pendientes,
        dias_salario_pendientes=req.dias_salario_pendientes,
        aguinaldo_ya_pagado=req.aguinaldo_ya_pagado,
        incluir_20_dias=req.incluir_20_dias,
    )
    # B5: lo gravado ordinario se apila sobre el ingreso del mes (Art. 96 LISR). Default
    # conservador: salario diario × 30.4, igual que aguinaldo y PTU.
    r = calcular_finiquito(d, ordinario_mensual(f))
    resultado = {**asdict(r), "empleado_no": f.empleado_no, "nombre": f.nombre, "causa": req.causa}
    fila = {
        "empleado_no": f.empleado_no,
        "nombre": f.nombre,
        "zona": f.zona.value,
        "percepciones": [
            {
                "tipo": c.clave,
                "concepto": c.concepto,
                "importe": c.importe,
                "gravado": c.gravado,
                "exento": c.exento,
            }
            for c in r.conceptos
        ],
        "total_percepciones": r.total,
        "isr": r.isr_ordinario + r.isr_separacion,
        "total_deducciones": r.isr_ordinario + r.isr_separacion,
        "neto": r.neto,
    }
    pid = (
        guardar_calculo(
            ctx,
            cliente,
            "finiquito",
            req.fecha_baja,
            req.fecha_baja,
            req.fecha_baja,
            req.model_dump(),
            resultado,
            [fila],
        )
        if req.guardar
        else None
    )
    return CalculoResponse(
        tipo="finiquito", periodo_id=pid, resultado=a_json(resultado), advertencias=r.notas
    )
