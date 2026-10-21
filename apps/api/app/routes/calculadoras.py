"""
Calculadoras fiscales sueltas del despacho (P3-08): `/api/v1/calculadoras/...`.

Cada calculadora llama al MISMO motor que el módulo que la respalda — no hay una segunda
implementación aquí:

- isr-sueldos → `nomina_engine.isr_nomina.isr_retenido` (tarifa Art. 96 + subsidio).
- isr-resico → `fiscal_engine.calculadora.calcular_isr_resico` (Art. 113-E LISR).
- actualizacion-recargos → `fiscal_engine.actualizacion` (Arts. 17-A y 21 CFF).
- isn → `fiscal_engine.isn` (con cliente, vía `app.impuestos.isn_cliente`, igual que el módulo).
- aguinaldo / ptu / finiquito → `routes/calculadoras_laborales.py`, sobre el motor de
  nómina de P4 (O1 del revisor de motor: la versión mínima de `fiscal_engine` se retiró).

Autenticadas con `contexto_actual`; la de ISN con cliente usa `cliente_o_404`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends

from app.exceptions import FiscalAgentError
from app.fiscal_engine.actualizacion import (
    calcular_actualizacion_recargos,
    fecha_limite_mensual,
    resultado_como_dict,
)
from app.fiscal_engine.calculadora import calcular_isr_resico
from app.fiscal_engine.inpc import ultimo_publicado
from app.fiscal_engine.isn import (
    ConfigISN,
    PercepcionISN,
    calcular_isn,
    catalogo_isn,
    resultado_isn_dict,
)
from app.impuestos import isn_cliente
from app.nomina_engine.isr_nomina import isr_retenido
from app.redondeo import redondear
from app.schemas.impuestos import (
    ActualizacionRequest,
    IsnRequest,
    IsrResicoRequest,
    IsrSueldosRequest,
)
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/calculadoras", tags=["calculadoras"])


@router.post("/actualizacion-recargos")
def actualizacion_recargos(
    req: ActualizacionRequest, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Actualización (Art. 17-A CFF) y recargos (Art. 21 CFF) de un adeudo."""
    r = calcular_actualizacion_recargos(
        req.monto,
        req.fecha_limite,
        req.fecha_pago,
        tipo_recargo=req.tipo_recargo,
        modo_factor=req.modo_factor,
        tope_meses=req.tope_meses,
    )
    u = ultimo_publicado()
    return {
        "exito": True,
        **resultado_como_dict(r),
        "inpc_ultimo_publicado": f"{u.anio}-{u.mes:02d}",
    }


@router.get("/fecha-limite")
def fecha_limite(anio: int, mes: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Día 17 del mes siguiente corrido a hábil (Art. 12 CFF)."""
    if not 1 <= mes <= 12:
        raise FiscalAgentError("Mes inválido.", 422)
    return {"exito": True, "fecha_limite": fecha_limite_mensual(anio, mes).isoformat()}


@router.post("/isr-sueldos")
def isr_sueldos(req: IsrSueldosRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """ISR a retener de sueldos con el motor de nómina."""
    mensual = req.ingreso_gravado_mensual
    if mensual is None:
        mensual = (
            req.base_gravable
            if req.clave_periodicidad == "05"
            else redondear(req.base_gravable / Decimal(req.dias_periodo) * Decimal("30.4"))
        )
    r = isr_retenido(
        req.base_gravable,
        req.clave_periodicidad,
        req.fecha_pago,
        mensual,
        req.dias_periodo,
        req.es_trabajador_de_salario_minimo,
    )
    return {
        "exito": True,
        "base_gravable": f"{req.base_gravable:.2f}",
        "ingreso_gravado_mensual": f"{mensual:.2f}",
        "isr_causado": f"{r.causado:.2f}",
        "subsidio": f"{r.subsidio:.2f}",
        "subsidio_acreditado": f"{r.acreditado:.2f}",
        "isr_retenido": f"{r.retenido:.2f}",
        "subsidio_no_entregado": f"{r.subsidio_no_entregado:.2f}",
        "fundamento": "Art. 96 LISR (Anexo 8 RMF 2026); Decreto subsidio DOF 31-12-2025.",
    }


@router.post("/isr-resico")
def isr_resico(req: IsrResicoRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """ISR mensual RESICO PF con el mismo motor de la pre-declaración (Art. 113-E LISR)."""
    isr, tasa = calcular_isr_resico(float(req.ingresos_cobrados))
    causado = redondear(Decimal(str(isr)))
    a_pagar = max(causado - req.isr_retenido, Decimal("0"))
    return {
        "exito": True,
        "ingresos_cobrados": f"{req.ingresos_cobrados:.2f}",
        "tasa": str(Decimal(str(tasa))),
        "isr_causado": f"{causado:.2f}",
        "isr_retenido": f"{req.isr_retenido:.2f}",
        "isr_a_pagar": f"{a_pagar:.2f}",
        "fundamento": "Arts. 113-E y 113-J LISR.",
    }


@router.get("/isn/tasas")
def isn_tasas(
    fecha: date | None = None, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Catálogo de tasas ISN vigentes por entidad, con su fuente."""
    return {"exito": True, "entidades": catalogo_isn(fecha or date.today())}


@router.post("/isn")
def isn(req: IsnRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """ISN: con cliente (bóveda + entidad del cliente) o con datos capturados."""
    if req.cliente:
        if req.anio is None or req.mes is None:
            raise FiscalAgentError("Con cliente hacen falta 'anio' y 'mes'.", 422)
        cliente = cliente_o_404(ctx, req.cliente)
        r, n = isn_cliente.isn_del_cliente(
            ctx.db, cliente, req.anio, req.mes, req.aplicar_adicional, req.claves_excluidas
        )
        return {"exito": True, "nominas": n, **resultado_isn_dict(r)}
    if not req.entidad:
        raise FiscalAgentError("Indica la entidad o el cliente.", 422)
    percepciones = [PercepcionISN(p.clave, p.importe, p.descripcion) for p in req.percepciones]
    if req.total_erogaciones is not None:
        percepciones.append(PercepcionISN("038", req.total_erogaciones, "Total de erogaciones"))
    r = calcular_isn(
        req.entidad,
        req.fecha or date.today(),
        percepciones,
        ConfigISN(req.aplicar_adicional, frozenset(req.claves_excluidas)),
    )
    return {"exito": True, **resultado_isn_dict(r)}
