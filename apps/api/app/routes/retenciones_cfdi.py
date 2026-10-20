"""
CFDI de retenciones e información de pagos 2.0 por cliente (P3-04).

`/api/v1/clientes/{clave}/retenciones-cfdi/...`: terceros del periodo (desde la bóveda),
emisión (sella con el CSD, valida contra el XSD, timbra con el PAC de `FISCALITO_PAC`),
descarga del XML y del PDF, y cancelación.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.integraciones.almacenamiento import obtener_almacenamiento
from app.retenciones_cfdi import pdf, servicio
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/clientes/{clave}/retenciones-cfdi", tags=["retenciones-cfdi"])


class EmitirRetencion(BaseModel):
    rfc_tercero: str = Field(min_length=12, max_length=13)
    ejercicio: int = Field(ge=2019, le=2027)
    mes_ini: int = Field(ge=1, le=12)
    mes_fin: int = Field(ge=1, le=12)
    cve_retenc: str | None = Field(None, pattern=r"^(0[1-9]|1[0-9]|2[0-8])$")
    desc_retenc: str = Field("", max_length=100)
    domicilio_fiscal: str | None = Field(None, pattern=r"^[0-9]{5}$")
    nombre: str | None = Field(None, max_length=254)


class CancelarRetencion(BaseModel):
    motivo: str = Field(pattern=r"^0[1-4]$")
    folio_sustitucion: str | None = None


@router.get("/terceros")
def terceros(
    clave: str, ejercicio: int = Query(..., ge=2019, le=2027),
    mes_ini: int = Query(..., ge=1, le=12), mes_fin: int = Query(..., ge=1, le=12),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Terceros con retenciones en el periodo y los CFDI de retenciones ya emitidos."""
    cliente = cliente_o_404(ctx, clave)
    lista = servicio.terceros_del_periodo(ctx.db, cliente, ejercicio, mes_ini, mes_fin)
    emitidos = [servicio.fila_json(f) for f in servicio.listar(ctx.db, cliente, ejercicio)
                if f.mes_ini == mes_ini and f.mes_fin == mes_fin]
    return {"exito": True, "terceros": [t.a_dict() for t in lista], "emitidos": emitidos}


@router.get("")
def listar(
    clave: str, ejercicio: int | None = None, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "cfdi": [servicio.fila_json(f)
                                    for f in servicio.listar(ctx.db, cliente, ejercicio)]}


@router.post("")
def emitir(
    clave: str, cuerpo: EmitirRetencion, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Genera, valida y timbra el CFDI de retenciones de un tercero y lo guarda."""
    cliente = cliente_o_404(ctx, clave)
    fila = servicio.emitir(
        ctx.db, cliente, cuerpo.rfc_tercero, cuerpo.ejercicio, cuerpo.mes_ini, cuerpo.mes_fin,
        servicio.OpcionesEmision(cuerpo.cve_retenc, cuerpo.desc_retenc, cuerpo.domicilio_fiscal,
                                 cuerpo.nombre),
        ctx.uid,
    )
    return {"exito": True, "cfdi": servicio.fila_json(fila)}


def _xml(ctx: Contexto, clave: str, uuid: str) -> tuple[bytes, Any]:
    cliente = cliente_o_404(ctx, clave)
    fila = servicio.obtener(ctx.db, cliente, uuid)
    return obtener_almacenamiento().leer(fila.ruta_xml), fila


@router.get("/{uuid}/xml")
def descargar_xml(clave: str, uuid: str, ctx: Contexto = Depends(contexto_actual)) -> Response:
    xml, fila = _xml(ctx, clave, uuid)
    return Response(xml, media_type="application/xml", headers={
        "Content-Disposition": f'attachment; filename="retenciones-{fila.uuid}.xml"'})


@router.get("/{uuid}/pdf")
def descargar_pdf(clave: str, uuid: str, ctx: Contexto = Depends(contexto_actual)) -> Response:
    xml, fila = _xml(ctx, clave, uuid)
    return Response(pdf.constancia(xml, fila.es_prueba), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="retenciones-{fila.uuid}.pdf"'})


@router.post("/{uuid}/cancelar")
def cancelar(
    clave: str, uuid: str, cuerpo: CancelarRetencion, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    fila = servicio.cancelar(ctx.db, cliente, uuid, cuerpo.motivo, cuerpo.folio_sustitucion)
    return {"exito": True, "cfdi": servicio.fila_json(fila)}

