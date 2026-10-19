"""
Personas morales y anual del cliente (P3-01, P3-06): `/api/v1/impuestos/clientes/{clave}/...`.

- `GET/PUT .../pm/datos/{anio}` — datos anuales de la persona moral (`DatosAnualesPM`).
- `POST .../pm/pagos-provisionales` — pagos provisionales de enero al mes (Art. 14 / Art. 211).
- `POST .../anual` — cálculo anual (PF 612/606/625/626, PM 601 y RESICO PM).
- `POST .../anual/papeles` — el mismo cálculo como papeles de trabajo en Excel.

Todo por `contexto_actual` + `cliente_o_404` (otro despacho = 404). El motor es
`app/fiscal_engine/personas_morales.py` / `anual_pf.py`; nada se guarda salvo los datos
capturados. Contrato en `docs/api-contract.md` §Personas morales y anual.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.exceptions import FiscalValidationError
from app.fiscal_engine import personas_morales as motor
from app.fiscal_engine.actualizacion import fecha_limite_mensual
from app.impuestos import personas_morales as pm
from app.impuestos.anual import anual_cliente
from app.impuestos.papeles import papeles_xlsx
from app.modelos.nucleo import Cliente
from app.schemas.personas_morales import (
    AnualRequest,
    DatosAnualesPMSchema,
    PagosProvisionalesPMRequest,
)
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/impuestos", tags=["impuestos"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _tipo_o_422(cliente: Cliente) -> str:
    tipo = pm.tipo_pm(cliente)
    if tipo is None:
        raise FiscalValidationError(
            "El cliente no es persona moral (régimen 601, o 626 con RFC de persona moral).")
    return tipo


@router.get("/clientes/{clave}/pm/datos/{anio}")
def leer_datos_pm(clave: str, anio: int, ctx: Contexto = Depends(contexto_actual)
                  ) -> dict[str, Any]:
    """Datos anuales capturados de la persona moral (defaults si no hay)."""
    cliente = cliente_o_404(ctx, clave)
    _tipo_o_422(cliente)
    return {"exito": True, "anio": anio,
            "datos": pm.datos_de(ctx.db, cliente, anio).model_dump(mode="json")}


@router.put("/clientes/{clave}/pm/datos/{anio}")
def guardar_datos_pm(clave: str, anio: int, datos: DatosAnualesPMSchema,
                     ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Guarda (reemplaza) los datos anuales de la persona moral."""
    cliente = cliente_o_404(ctx, clave)
    _tipo_o_422(cliente)
    pm.guardar_datos(ctx.db, cliente, anio, datos)
    return {"exito": True, "anio": anio, "datos": datos.model_dump(mode="json")}


@router.post("/clientes/{clave}/pm/pagos-provisionales")
def pagos_provisionales_pm(clave: str, req: PagosProvisionalesPMRequest,
                           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Pagos provisionales de enero al mes pedido, con cada paso del cálculo."""
    cliente = cliente_o_404(ctx, clave)
    tipo = _tipo_o_422(cliente)
    pagos, coef, origen, b = pm.pagos_provisionales(ctx.db, cliente, req.anio, req.mes, tipo)
    return {
        "exito": True, "anio": req.anio, "mes": req.mes,
        "tipo": "pm" if tipo == "general" else "resico_pm", "fuente": b.fuente,
        "coeficiente": f"{coef:.4f}", "origen_coeficiente": origen,
        "tasa": f"{motor.TASA_ISR_PM:.2f}",
        "fecha_limite": fecha_limite_mensual(req.anio, req.mes).isoformat(),
        "pagos": [motor.pago_dict(p) for p in pagos],
        "notas": b.notas + pm.notas_provisionales(tipo, coef, origen, req.mes),
    }


@router.post("/clientes/{clave}/anual")
def anual(clave: str, req: AnualRequest, ctx: Contexto = Depends(contexto_actual)
          ) -> dict[str, Any]:
    """Cálculo anual del cliente según su régimen, con el detalle mes a mes."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **anual_cliente(ctx.db, cliente, req.anio, req.pagos_provisionales)}


@router.post("/clientes/{clave}/anual/papeles", response_model=None)
def papeles(clave: str, req: AnualRequest, ctx: Contexto = Depends(contexto_actual)
            ) -> Response:
    """Papeles de trabajo de la anual (xlsx), del mismo cálculo que `/anual`."""
    cliente = cliente_o_404(ctx, clave)
    r = anual_cliente(ctx.db, cliente, req.anio, req.pagos_provisionales)
    nombre = f"papeles-anual-{clave}-{req.anio}.xlsx"
    return Response(papeles_xlsx(r, cliente.nombre or clave), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
