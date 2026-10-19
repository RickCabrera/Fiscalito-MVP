"""
Calculadoras laborales sueltas: aguinaldo, PTU y finiquito (`/api/v1/calculadoras/...`).

Mismas URLs que P3-08; desde la integración con P4 llaman al motor de nómina
(`nomina_engine.aguinaldo`, `ptu.ptu_individual`, `finiquito`) — una sola implementación
de cada cálculo. La versión mínima `fiscal_engine.calculadoras_laborales` se retiró por
duplicada y con errores (O1 del revisor de motor).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends

from app.constants import DIAS_MES_FISCAL
from app.nomina_engine.aguinaldo import calcular_aguinaldo
from app.nomina_engine.finiquito import DatosSeparacion, anios_de_servicio, calcular_finiquito
from app.nomina_engine.integracion import factor_integracion_de_ley
from app.nomina_engine.ptu import ptu_individual
from app.nomina_engine.vacaciones import dias_vacaciones_de_ley
from app.redondeo import redondear
from app.schemas.impuestos import AguinaldoRequest, FiniquitoRequest, PtuRequest
from app.tenancy import Contexto, contexto_actual

router = APIRouter(prefix="/calculadoras", tags=["calculadoras"])


def _txt(v: Decimal) -> str:
    return f"{v:.2f}"


def _ordinario(salario_diario: Decimal) -> Decimal:
    # El ingreso ordinario del mes contra el que se apila lo gravado (Art. 96 LISR).
    return redondear(salario_diario * DIAS_MES_FISCAL)


@router.post("/aguinaldo")
def aguinaldo(req: AguinaldoRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Aguinaldo proporcional (Art. 87 LFT), 30 UMA exentas y su ISR (Art. 96 LISR)."""
    r = calcular_aguinaldo(
        req.salario_diario,
        req.dias_aguinaldo,
        req.dias_trabajados_en_el_anio,
        req.fecha_pago,
        _ordinario(req.salario_diario),
    )
    partida = {
        "clave": "002",
        "concepto": "Aguinaldo",
        "importe": _txt(r.importe),
        "exento": _txt(r.exento),
        "gravado": _txt(r.gravado),
        "fundamento": r.fundamento,
    }
    return {
        "exito": True,
        "dias_trabajados": r.dias_trabajados,
        "importe": _txt(r.importe),
        "partidas": [partida],
        "isr": _txt(r.isr.isr),
        "neto": _txt(r.neto),
        "fundamento": r.fundamento,
    }


@router.post("/ptu")
def ptu(req: PtuRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """PTU de un trabajador con los totales de la empresa (Arts. 123 y 127 LFT) y su ISR."""
    r = ptu_individual(
        req.utilidad_repartible,
        req.dias_trabajador,
        req.salario_trabajador,
        req.total_dias_todos,
        req.total_salarios_todos,
        req.salario_diario,
        req.promedio_ptu_3_anios,
        req.fecha_pago,
        _ordinario(req.salario_diario),
    )
    isr = r.isr.isr if r.isr else Decimal("0.00")
    return {
        "exito": True,
        "por_dias": _txt(r.por_dias),
        "por_salario": _txt(r.por_salarios),
        "calculada": _txt(r.antes_de_tope),
        "tope": _txt(r.tope),
        "topada": r.antes_de_tope > r.tope,
        "importe": _txt(r.ptu),
        "exento": _txt(r.exento),
        "gravado": _txt(r.gravado),
        "isr": _txt(isr),
        "neto": _txt(r.ptu - isr),
        "fundamento": "Arts. 123 y 127 LFT; Art. 93 fr. XIV y 96 LISR.",
    }


@router.post("/finiquito")
def finiquito(req: FiniquitoRequest, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """
    Finiquito o liquidación con el motor de P4 (Arts. 48-50, 79, 87, 162 LFT; 93, 95, 96 LISR).

    Sin SDI capturado se integra con el factor de prestaciones mínimas de ley a la
    antigüedad cumplida: la indemnización va con salario integrado (Art. 84 LFT), no con
    el diario.
    """
    anios = int(anios_de_servicio(req.fecha_ingreso, req.fecha_baja))
    sdi = req.salario_diario_integrado or redondear(
        req.salario_diario * factor_integracion_de_ley(anios)
    )
    d = DatosSeparacion(
        fecha_alta=req.fecha_ingreso,
        fecha_baja=req.fecha_baja,
        salario_diario=req.salario_diario,
        salario_diario_integrado=sdi,
        causa=req.tipo,
        zona=req.zona,
        dias_aguinaldo=req.dias_aguinaldo,
        dias_vacaciones_anio=dias_vacaciones_de_ley(anios + 1),
        prima_vacacional=req.prima_vacacional,
        dias_vacaciones_pendientes=req.dias_vacaciones_pendientes,
        dias_salario_pendientes=int(req.dias_pendientes_de_pago),
        incluir_20_dias=req.incluir_20_dias,
    )
    r = calcular_finiquito(d, _ordinario(req.salario_diario))
    sep = [c for c in r.conceptos if c.separacion]
    return {
        "exito": True,
        "anios_servicio": str(r.anios_servicio),
        "salario_diario_integrado": _txt(sdi),
        "partidas": [
            {
                "clave": c.clave,
                "concepto": c.concepto,
                "importe": _txt(c.importe),
                "exento": _txt(c.exento),
                "gravado": _txt(c.gravado),
                "fundamento": c.fundamento,
            }
            for c in r.conceptos
            if not c.separacion
        ],
        "separacion": [
            {"concepto": c.concepto, "importe": _txt(c.importe), "fundamento": c.fundamento}
            for c in sep
        ],
        "separacion_exento": _txt(sum((c.exento for c in sep), Decimal("0.00"))),
        "separacion_gravado": _txt(sum((c.gravado for c in sep), Decimal("0.00"))),
        "isr_ordinario": _txt(r.isr_ordinario),
        "isr_separacion": _txt(r.isr_separacion),
        "total_bruto": _txt(r.total),
        "isr": _txt(r.isr_ordinario + r.isr_separacion),
        "neto": _txt(r.neto),
        "notas": list(r.notas),
        "fundamento": "Arts. 48-50, 76, 79, 80, 84, 87, 162, 485-486 LFT; Arts. 93 fr. XIII y "
        "XIV, 95 y 96 LISR.",
    }
