"""
Bóveda de CFDI por cliente (plan P, P0-03).

Todo cuelga de `/api/v1/boveda/clientes/{clave}/...`, pasa por `contexto_actual` y obtiene
al cliente con `cliente_o_404`: el cliente de otro despacho es 404, igual que uno que no
existe. Contrato en `docs/api-contract.md`, sección "Bóveda de CFDI".
"""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.boveda_cfdi import servicio
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/boveda", tags=["boveda"])

MAX_ARCHIVOS = 200


def _filtros(
    desde: date | None = Query(None, description="Fecha inicial (inclusive), AAAA-MM-DD"),
    hasta: date | None = Query(None, description="Fecha final (inclusive), AAAA-MM-DD"),
    tipo: Literal["I", "E", "P", "N", "T"] | None = Query(None),
    direccion: Literal["emitido", "recibido"] | None = Query(None),
    rfc: str | None = Query(None, max_length=13, description="RFC de la contraparte"),
    estatus: Literal["vigente", "cancelado", "desconocido"] | None = Query(None),
) -> servicio.Filtros:
    if desde and hasta and desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", status_code=422)
    return servicio.Filtros(desde=desde, hasta=hasta, tipo=tipo, direccion=direccion,
                            rfc=rfc, estatus=estatus)


def _fila(c: Comprobante) -> dict[str, Any]:
    return {
        "uuid": c.uuid, "version": c.version, "tipo": c.tipo,
        "fecha": c.fecha.isoformat(), "serie": c.serie, "folio": c.folio,
        "rfc_emisor": c.rfc_emisor, "nombre_emisor": c.nombre_emisor,
        "rfc_receptor": c.rfc_receptor, "nombre_receptor": c.nombre_receptor,
        "direccion": c.direccion,
        "subtotal": f"{c.subtotal:.2f}", "descuento": f"{c.descuento:.2f}",
        "total": f"{c.total:.2f}", "moneda": c.moneda,
        "metodo_pago": c.metodo_pago, "forma_pago": c.forma_pago, "uso_cfdi": c.uso_cfdi,
        "iva_trasladado": f"{c.iva_trasladado:.2f}", "iva_retenido": f"{c.iva_retenido:.2f}",
        "isr_retenido": f"{c.isr_retenido:.2f}", "ieps": f"{c.ieps:.2f}",
        "estatus_sat": c.estatus_sat, "origen": c.origen,
    }


@router.post("/clientes/{clave}/cfdi")
def importar_cfdi(
    clave: str,
    archivos: list[UploadFile] = File(..., description="XML sueltos y/o ZIP"),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Importa XML y ZIP a la bóveda del cliente; devuelve el reporte."""
    cliente = cliente_o_404(ctx, clave)
    if len(archivos) > MAX_ARCHIVOS:
        raise FiscalAgentError(
            f"Máximo {MAX_ARCHIVOS} archivos por carga; mete los demás en un ZIP.", 422
        )
    reporte = servicio.importar(
        ctx.db, cliente, [(a.filename or "sin-nombre", a.file) for a in archivos]
    )
    return {"exito": True, **reporte.como_dict()}


@router.get("/clientes/{clave}/cfdi")
def listar_cfdi(
    clave: str,
    filtros: servicio.Filtros = Depends(_filtros),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Comprobantes del cliente, filtrados y paginados (más recientes primero)."""
    cliente = cliente_o_404(ctx, clave)
    filas, total = servicio.listar(ctx.db, cliente, filtros, pagina, por_pagina)
    return {
        "exito": True, "total": total, "pagina": pagina, "por_pagina": por_pagina,
        "comprobantes": [_fila(c) for c in filas],
    }


@router.get("/clientes/{clave}/cfdi/{uuid}/xml")
def descargar_xml(
    clave: str, uuid: str, ctx: Contexto = Depends(contexto_actual)
) -> Response:
    """El XML original, byte por byte."""
    cliente = cliente_o_404(ctx, clave)
    comp = servicio.obtener(ctx.db, cliente, uuid)
    datos = servicio.leer_xml_original(comp)
    return Response(
        content=datos,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{comp.uuid}.xml"'},
    )


@router.delete("/clientes/{clave}/cfdi/{uuid}")
def borrar_cfdi(clave: str, uuid: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Quita un CFDI de la bóveda (y su XML del almacenamiento)."""
    cliente = cliente_o_404(ctx, clave)
    servicio.borrar(ctx.db, cliente, uuid)
    return {"exito": True, "uuid": uuid.strip().upper()}


@router.get("/clientes/{clave}/resumen")
def resumen_boveda(
    clave: str,
    filtros: servicio.Filtros = Depends(_filtros),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Conteos y totales por mes, tipo y dirección."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "renglones": servicio.resumen(ctx.db, cliente, filtros)}
