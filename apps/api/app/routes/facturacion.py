"""
Facturación CFDI 4.0 (P5-04). Contrato: `docs/api-contract.md` §"Facturación".

- `/facturacion/catalogos`, `/facturacion/config` (qué cliente es el propio despacho) y
  `/facturacion/cargos/{id}/borrador` (factura sugerida para un cargo de cobranza).
- `/clientes/{clave}/facturas`: emisión de ingreso/egreso, pagos (complemento 2.0), XML, PDF
  con QR y cancelación. El cliente de la URL es el EMISOR. Tenencia: `cliente_o_404`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.facturacion import armado, calculo, catalogos, pdf, servicio
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Facturación"])
Importe = Field(ge=0, max_digits=18, decimal_places=6)


class ImpuestoIn(BaseModel):
    tipo: Literal["traslado", "retencion"]
    impuesto: Literal["001", "002"]
    tipo_factor: Literal["Tasa", "Exento"] = "Tasa"
    tasa: Decimal | None = Field(None, ge=0, le=1, decimal_places=6)


class ConceptoIn(BaseModel):
    clave_prod_serv: str = Field(pattern=r"^[0-9]{8}$")
    cantidad: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    clave_unidad: str = Field(min_length=1, max_length=3)
    unidad: str = Field("", max_length=20)
    descripcion: str = Field(min_length=1, max_length=1000)
    valor_unitario: Decimal = Importe
    descuento: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    objeto_imp: Literal["01", "02", "03"] = "02"
    no_identificacion: str = Field("", max_length=100)
    impuestos: list[ImpuestoIn] = Field(default_factory=list, max_length=4)


class ReceptorIn(BaseModel):
    clave_cliente: str | None = None
    rfc: str = Field("", max_length=13)
    nombre: str = Field("", max_length=254)
    regimen: str = Field("", max_length=3)
    codigo_postal: str = Field("", pattern=r"^([0-9]{5})?$")
    uso_cfdi: str = Field("G03", max_length=4)


class RelacionIn(BaseModel):
    tipo_relacion: str = Field(pattern=r"^0[1-9]$")
    uuids: list[str] = Field(min_length=1, max_length=50)


class FacturaIn(BaseModel):
    tipo: Literal["I", "E"] = "I"
    receptor: ReceptorIn
    conceptos: list[ConceptoIn] = Field(min_length=1, max_length=200)
    forma_pago: str = Field(pattern=r"^[0-9]{2}$")
    metodo_pago: Literal["PUE", "PPD"]
    serie: str | None = Field(None, max_length=25, pattern=r"^[^|]{1,25}$")
    condiciones_pago: str = Field("", max_length=1000)
    relacionados: list[RelacionIn] = Field(default_factory=list, max_length=5)
    cargo_id: int | None = None


class DocPagoIn(BaseModel):
    factura_id: int
    importe_pagado: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PagoIn(BaseModel):
    fecha_pago: datetime
    forma_pago: str = Field(pattern=r"^[0-9]{2}$")
    documentos: list[DocPagoIn] = Field(min_length=1, max_length=50)
    num_operacion: str = Field("", max_length=100, pattern=r"^[^|]{0,100}$")
    serie: str | None = Field(None, max_length=25, pattern=r"^[^|]{1,25}$")
    relacionados: list[RelacionIn] = Field(default_factory=list, max_length=5)


class CancelarIn(BaseModel):
    motivo: Literal["01", "02", "03", "04"]
    folio_sustitucion: str | None = None


class ConfigIn(BaseModel):
    cliente_propio: str | None = None


def _rels(rs: list[RelacionIn]) -> list[armado.Relacion]:
    return [armado.Relacion(r.tipo_relacion, tuple(u.strip() for u in r.uuids)) for r in rs]


def _entrada(b: FacturaIn) -> servicio.EntradaFactura:
    conceptos = [calculo.ConceptoEntrada(
        clave_prod_serv=c.clave_prod_serv, cantidad=c.cantidad, clave_unidad=c.clave_unidad,
        descripcion=c.descripcion, valor_unitario=c.valor_unitario, objeto_imp=c.objeto_imp,
        descuento=c.descuento, unidad=c.unidad, no_identificacion=c.no_identificacion,
        impuestos=tuple(calculo.ImpuestoEntrada(i.tipo, i.impuesto, i.tipo_factor, i.tasa)
                        for i in c.impuestos)) for c in b.conceptos]
    r = b.receptor
    return servicio.EntradaFactura(
        tipo=b.tipo, receptor=servicio.ReceptorEntrada(r.rfc, r.nombre, r.regimen,
                                                       r.codigo_postal, r.uso_cfdi,
                                                       r.clave_cliente),
        conceptos=conceptos, forma_pago=b.forma_pago, metodo_pago=b.metodo_pago, serie=b.serie,
        condiciones_pago=b.condiciones_pago, relacionados=_rels(b.relacionados),
        cargo_id=b.cargo_id)


@router.get("/facturacion/catalogos", summary="Catálogos SAT mínimos para facturar")
def obtener_catalogos(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return {"exito": True, **catalogos.todos()}


@router.get("/facturacion/config", summary="Qué cliente de la cartera es el propio despacho")
def obtener_config(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return {"exito": True, "cliente_propio": servicio.clave_propio(ctx)}


@router.put("/facturacion/config", summary="Marcar el cliente que es el propio despacho")
def guardar_config(cuerpo: ConfigIn, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    servicio.guardar_config(ctx, cuerpo.cliente_propio)
    return {"exito": True, "cliente_propio": servicio.clave_propio(ctx)}


@router.get("/facturacion/cargos/{cargo_id}/borrador",
            summary="Factura sugerida para un cargo de cobranza (honorarios del despacho)")
def borrador(cargo_id: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return {"exito": True, "borrador": servicio.borrador_de_cargo(ctx, cargo_id)}


@router.get("/clientes/{clave}/facturas", summary="Facturas emitidas por el cliente")
def listar(clave: str, tipo: Literal["I", "E", "P"] | None = Query(None),
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "es_propio": servicio.es_propio(ctx.db, cliente),
            "facturas": [servicio.factura_json(ctx.db, f)
                         for f in servicio.listar(ctx.db, cliente, tipo)]}


@router.post("/clientes/{clave}/facturas", summary="Emitir CFDI de ingreso o egreso")
def emitir(clave: str, cuerpo: FacturaIn,
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    f = servicio.emitir_factura(ctx, cliente, _entrada(cuerpo))
    return {"exito": True, "factura": servicio.factura_json(ctx.db, f)}


@router.post("/clientes/{clave}/facturas/pagos",
             summary="Emitir CFDI de pago (complemento de recepción de pagos 2.0)")
def emitir_pago(clave: str, cuerpo: PagoIn,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    f = servicio.emitir_pago(ctx, cliente, servicio.EntradaPago(
        fecha_pago=cuerpo.fecha_pago, forma_pago=cuerpo.forma_pago,
        documentos=[servicio.PagoDocEntrada(d.factura_id, d.importe_pagado)
                    for d in cuerpo.documentos],
        num_operacion=cuerpo.num_operacion, serie=cuerpo.serie,
        relacionados=_rels(cuerpo.relacionados)))
    return {"exito": True, "factura": servicio.factura_json(ctx.db, f)}


@router.get("/clientes/{clave}/facturas/{factura_id}", summary="Detalle de una factura")
def detalle(clave: str, factura_id: int,
            ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    f = servicio.obtener(ctx.db, cliente_o_404(ctx, clave), factura_id)
    return {"exito": True, "factura": servicio.factura_json(ctx.db, f)}


@router.get("/clientes/{clave}/facturas/{factura_id}/xml", summary="XML timbrado")
def xml(clave: str, factura_id: int, ctx: Contexto = Depends(contexto_actual)) -> Response:
    f = servicio.obtener(ctx.db, cliente_o_404(ctx, clave), factura_id)
    return Response(servicio.leer_xml(f), media_type="application/xml", headers={
        "Content-Disposition": f'attachment; filename="{f.serie}-{f.folio}_{f.uuid}.xml"'})


@router.get("/clientes/{clave}/facturas/{factura_id}/pdf", summary="PDF con QR")
def descargar_pdf(clave: str, factura_id: int,
                  ctx: Contexto = Depends(contexto_actual)) -> Response:
    f = servicio.obtener(ctx.db, cliente_o_404(ctx, clave), factura_id)
    return Response(pdf.factura(servicio.leer_xml(f), f.es_prueba),
                    media_type="application/pdf", headers={
                        "Content-Disposition":
                        f'attachment; filename="{f.serie}-{f.folio}_{f.uuid}.pdf"'})


@router.post("/clientes/{clave}/facturas/{factura_id}/cancelar",
             summary="Cancelar con motivo 01 (con sustituta), 02, 03 o 04")
def cancelar(clave: str, factura_id: int, cuerpo: CancelarIn,
             ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    f = servicio.cancelar(ctx, cliente, factura_id, cuerpo.motivo, cuerpo.folio_sustitucion)
    return {"exito": True, "factura": servicio.factura_json(ctx.db, f)}
