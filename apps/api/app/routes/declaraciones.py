"""
Endpoints de declaraciones fiscales.

POST /api/v1/pre-declaracion          → Pre-declaracion mensual o bimestral
POST /api/v1/pre-declaracion-anual    → Pre-declaracion anual
"""

from fastapi import APIRouter, HTTPException
from app.schemas.declaraciones import (
    PreDeclaracionRequest,
    PreDeclaracionResponse,
    ErrorResponse,
)
from app.schemas.deducciones import (
    DeduccionesPersonalesRequest,
    DeduccionesPersonalesResponse,
    DeduccionDetalle,
)
from app.fiscal_engine.calculadora import calcular_declaracion
from app.fiscal_engine.deducciones_personales import calcular_deducciones_personales
from app.fiscal_engine.tablas_isr import TABLA_ISR_ANUAL
from app.services.llm_service import generar_explicacion, generar_explicacion_deducciones
from app.constants import NOMBRES_MESES, NOMBRES_BIMESTRES, NOMBRES_REGIMEN

router = APIRouter(tags=["Declaraciones"])


@router.post(
    "/pre-declaracion",
    response_model=PreDeclaracionResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Generar pre-declaracion mensual o bimestral",
    description="Recibe perfil del contribuyente y facturas del periodo. "
    "Calcula ISR/IVA y devuelve desglose con explicacion en lenguaje natural.",
)
async def pre_declaracion(req: PreDeclaracionRequest):
    # Validaciones
    if not req.facturas:
        raise HTTPException(
            status_code=400,
            detail="Se requiere al menos una factura para calcular la declaracion.",
        )

    # Determinar tipo de declaracion
    es_bimestral = req.periodo_bimestre is not None
    es_anual = req.periodo_month is None and req.periodo_bimestre is None

    if es_anual:
        raise HTTPException(
            status_code=400,
            detail="Para declaracion anual usa el endpoint /pre-declaracion-anual.",
        )

    # Determinar periodo
    if es_bimestral:
        bim = req.periodo_bimestre or 1
        if bim < 1 or bim > 6:
            raise HTTPException(status_code=400, detail="Bimestre debe ser entre 1 y 6.")
        periodo_str = f"{NOMBRES_BIMESTRES[bim]} {req.periodo_year}"
        tipo_decl = "bimestral"
    else:
        mes = req.periodo_month or 1
        if mes < 1 or mes > 12:
            raise HTTPException(status_code=400, detail="Mes debe ser entre 1 y 12.")
        periodo_str = f"{NOMBRES_MESES[mes]} {req.periodo_year}"
        tipo_decl = "mensual"

    # Calcular
    mes = req.periodo_month if not es_bimestral else None
    desglose = calcular_declaracion(
        contribuyente=req.contribuyente,
        facturas=req.facturas,
        es_anual=False,
        periodo_month=mes,
        pagos_provisionales_anteriores=req.pagos_provisionales_anteriores,
        predial_pagado=req.predial_pagado,
        ingresos_acumulados_anteriores=req.ingresos_acumulados_anteriores,
        deducciones_acumuladas_anteriores=req.deducciones_acumuladas_anteriores,
    )

    regimen_nombre = NOMBRES_REGIMEN.get(req.contribuyente.regimen, req.contribuyente.regimen)

    # Generar explicacion con LLM (si se pidio)
    explicacion = None
    if req.incluir_explicacion:
        contributor_type = getattr(req.contribuyente, 'contributor_type', None)
        explicacion = await generar_explicacion(
            desglose=desglose,
            regimen=regimen_nombre,
            periodo=periodo_str,
            tipo_declaracion=tipo_decl,
            contributor_type=contributor_type.value if contributor_type else None,
        )

    # Generar advertencias automaticas
    advertencias = _generar_advertencias(req, desglose)
    recomendaciones = _generar_recomendaciones(req, desglose)

    return PreDeclaracionResponse(
        tipo_declaracion=tipo_decl,
        periodo=periodo_str,
        regimen=regimen_nombre,
        desglose=desglose,
        explicacion=explicacion,
        advertencias=advertencias,
        recomendaciones=recomendaciones,
    )


@router.post(
    "/pre-declaracion-anual",
    response_model=PreDeclaracionResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Generar pre-declaracion anual",
    description="Recibe perfil del contribuyente y TODAS las facturas del ejercicio fiscal. "
    "Calcula ISR/IVA anual con deducciones personales.",
)
async def pre_declaracion_anual(req: PreDeclaracionRequest):
    if not req.facturas:
        raise HTTPException(
            status_code=400,
            detail="Se requiere al menos una factura para calcular la declaracion anual.",
        )

    periodo_str = f"Ejercicio fiscal {req.periodo_year}"

    desglose = calcular_declaracion(
        contribuyente=req.contribuyente,
        facturas=req.facturas,
        es_anual=True,
    )

    regimen_nombre = NOMBRES_REGIMEN.get(req.contribuyente.regimen, req.contribuyente.regimen)

    explicacion = None
    if req.incluir_explicacion:
        contributor_type = getattr(req.contribuyente, 'contributor_type', None)
        explicacion = await generar_explicacion(
            desglose=desglose,
            regimen=regimen_nombre,
            periodo=periodo_str,
            tipo_declaracion="anual",
            contributor_type=contributor_type.value if contributor_type else None,
        )

    advertencias = _generar_advertencias(req, desglose)
    recomendaciones = _generar_recomendaciones(req, desglose)

    return PreDeclaracionResponse(
        tipo_declaracion="anual",
        periodo=periodo_str,
        regimen=regimen_nombre,
        desglose=desglose,
        explicacion=explicacion,
        advertencias=advertencias,
        recomendaciones=recomendaciones,
    )


def _generar_advertencias(req: PreDeclaracionRequest, desglose) -> list[str]:
    """Genera advertencias automaticas basadas en los datos."""
    advertencias = []

    if desglose.cantidad_facturas_ingreso == 0:
        advertencias.append(
            "No se encontraron facturas de ingreso en este periodo. "
            "Verifica que hayas incluido todas tus facturas emitidas."
        )

    if req.contribuyente.regimen == "626" and desglose.total_ingresos_gravados > 0:
        mes = req.periodo_month or 1
        proyeccion = (desglose.total_ingresos_gravados / mes) * 12
        if proyeccion > 3_500_000:
            advertencias.append(
                f"Tus ingresos proyectados (${proyeccion:,.0f}) superan el tope RESICO de $3,500,000. "
                "Debes considerar cambiar al regimen de Actividad Empresarial (612)."
            )
        elif proyeccion > 2_800_000:  # 80% del tope
            advertencias.append(
                f"Tus ingresos proyectados representan el {proyeccion/3_500_000*100:.0f}% del tope RESICO."
            )
        if desglose.total_ingresos_gravados > 291_666.67:
            advertencias.append(
                "Tus ingresos mensuales superan el rango maximo de RESICO ($291,666.67). "
                "Si esto es recurrente, el SAT podria cambiarte de regimen automaticamente."
            )

    if desglose.isr_retenido > desglose.isr_causado:
        saldo = desglose.isr_retenido - desglose.isr_causado
        if req.contribuyente.regimen == "606":
            advertencias.append(
                f"Las retenciones de ISR superan el ISR causado en ${saldo:,.2f}. "
                "En arrendamiento, este saldo a favor se acumula y se recupera "
                "en tu declaracion anual (abril). Guarda tus CFDIs de retencion."
            )
        else:
            advertencias.append(
                f"Las retenciones de ISR superan el ISR causado. "
                f"Saldo a favor de ISR: ${saldo:,.2f}. "
                "Puedes solicitar devolucion o compensar en periodos siguientes."
            )

    if desglose.iva_a_pagar < 0:
        advertencias.append(
            f"Tienes un saldo a favor de IVA de ${abs(desglose.iva_a_pagar):,.2f}. "
            "Puedes solicitar devolucion o acreditarlo en periodos siguientes."
        )

    return advertencias


def _generar_recomendaciones(req: PreDeclaracionRequest, desglose) -> list[str]:
    """Genera recomendaciones para optimizar la carga fiscal."""
    recomendaciones = []
    regimen = req.contribuyente.regimen

    # Arrendamiento (606) esta legalmente excluido de RESICO.
    # Ofrecer recomendaciones especificas en su lugar.
    if regimen == "606":
        if desglose.cantidad_facturas_egreso == 0:
            recomendaciones.append(
                "No tienes facturas de gastos registradas. Evalua si te conviene mas "
                "la deduccion ciega del 35% (sin comprobar gastos) o documentar tus "
                "gastos reales de mantenimiento, predial, seguros, etc."
            )
        if (desglose.total_deducciones_autorizadas > 0 and
                desglose.total_deducciones_autorizadas > desglose.total_ingresos_gravados * 0.35):
            recomendaciones.append(
                "Tus gastos reales documentados superan el 35% de tus ingresos. "
                "En este caso las deducciones reales te convienen mas que la deduccion ciega. "
                "Asegurate de tener todos los CFDIs de tus gastos."
            )
        return recomendaciones

    if regimen != "626" and desglose.cantidad_facturas_egreso == 0:
        recomendaciones.append(
            "No tienes facturas de egreso (gastos deducibles). "
            "Revisa si tienes gastos del negocio sin facturar: "
            "renta, internet, software, transporte, etc."
        )

    if (regimen == "612" and
            desglose.total_deducciones_autorizadas < desglose.total_ingresos_gravados * 0.10):
        recomendaciones.append(
            "Tus deducciones son menores al 10% de tus ingresos. "
            "Considera facturar mas gastos operativos para reducir tu base gravable."
        )

    # Regimenes que NO pueden cambiarse a RESICO: 606 (ya filtrado arriba) y 605
    if (regimen not in ("626", "606", "605") and
            desglose.total_ingresos_gravados > 0 and
            desglose.total_ingresos_gravados <= 291_666.67):
        recomendaciones.append(
            "Con tu nivel de ingresos podrias beneficiarte del regimen RESICO, "
            "que tiene tasas fijas del 1% al 2.5%. Consulta con un contador "
            "si el cambio te conviene."
        )

    return recomendaciones


@router.post(
    "/deducciones-personales",
    response_model=DeduccionesPersonalesResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Calcular deducciones personales para declaracion anual",
    description="Calcula deducciones personales aplicando topes individuales y globales. "
    "Estima saldo a favor de ISR.",
)
async def deducciones_personales(req: DeduccionesPersonalesRequest):
    if req.ingresos_anuales <= 0:
        raise HTTPException(
            status_code=400,
            detail="Los ingresos anuales deben ser mayores a cero.",
        )

    resultado = calcular_deducciones_personales(
        ingresos_anuales=req.ingresos_anuales,
        gastos_medicos=req.gastos_medicos,
        colegiaturas=req.colegiaturas,
        nivel_educativo=req.nivel_educativo,
        intereses_hipotecarios=req.intereses_hipotecarios,
        donativos=req.donativos,
        aportaciones_voluntarias_retiro=req.aportaciones_voluntarias_retiro,
        seguros_gastos_medicos=req.seguros_gastos_medicos,
        transporte_escolar=req.transporte_escolar,
        funeral=req.funeral,
    )

    # Estimar saldo a favor: calcular ISR sin deducciones vs con deducciones
    from app.fiscal_engine.calculadora import calcular_isr_general
    isr_sin = calcular_isr_general(req.ingresos_anuales, es_anual=True)[0]
    base_con_deducciones = max(req.ingresos_anuales - resultado.total_deducible, 0)
    isr_con = calcular_isr_general(base_con_deducciones, es_anual=True)[0]
    saldo_a_favor = round(isr_sin - isr_con, 2)

    desglose_response = [
        DeduccionDetalle(
            concepto=d.concepto,
            monto_solicitado=d.monto_solicitado,
            tope_aplicable=d.tope_aplicable,
            monto_aceptado=d.monto_aceptado,
        )
        for d in resultado.desglose
    ]

    explicacion = None
    if req.incluir_explicacion:
        explicacion = await generar_explicacion_deducciones(
            resultado=resultado,
            saldo_a_favor=saldo_a_favor,
            ingresos_anuales=req.ingresos_anuales,
        )

    return DeduccionesPersonalesResponse(
        desglose=desglose_response,
        total_solicitado=resultado.total_solicitado,
        total_antes_tope=resultado.total_antes_tope,
        tope_global=resultado.tope_global,
        tope_tipo=resultado.tope_tipo,
        total_deducible=resultado.total_deducible,
        excedente_no_aprovechado=resultado.excedente_no_aprovechado,
        saldo_a_favor_estimado=saldo_a_favor,
        explicacion=explicacion,
    )
