"""
Dispersión bancaria de una nómina cerrada (P4-12). Contrato: `docs/api-contract.md`
§"Nómina — dispersión bancaria".

Tenencia: `cliente_o_404` + `periodo_o_404`; la cuenta de cargo se busca junto con el cliente.
El archivo viaja en base64 dentro del JSON junto con su reporte (incluidos, excluidos y
cuadre), para que la pantalla muestre los excluidos ANTES de que alguien descargue.
"""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app import nomina_servicio as srv
from app.auditoria import registrar
from app.dispersion import servicio
from app.dispersion.bancos.generico import COLUMNAS, DEFAULT
from app.dispersion.catalogo import LAYOUTS, descripcion, layout_por_id
from app.dispersion.clabe import BANCOS, nombre_banco
from app.schemas.declaraciones import ErrorResponse
from app.suscripciones.vigencia import exigir_modulo
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina — dispersión"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
        409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


class DatoBancoSchema(BaseModel):
    clave: str
    etiqueta: str
    patron: str
    obligatorio: bool
    default: str


class LayoutSchema(BaseModel):
    id: str
    nombre: str
    banco: str | None
    estado: str = Field(description="verificado | por_confirmar")
    fuente: str
    interbancario: bool
    datos_requeridos: list[DatoBancoSchema]


class LayoutsResponse(BaseModel):
    exito: bool = True
    layouts: list[LayoutSchema]
    columnas_genericas: dict[str, str]
    columnas_default: list[str]
    bancos: dict[str, str]
    datos_guardados: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="Lo último que se usó por layout, si se pidió cliente."
    )


class DispersionRequest(BaseModel):
    layout: str = Field(description="bbva | banamex | santander | banorte | hsbc | scotiabank | "
                        "banbajio | generico")
    cuenta_cargo_id: int | None = Field(default=None, description="Cuenta bancaria del cliente "
                                        "(conciliación P2-06). Obligatoria salvo en el genérico.")
    fecha_aplicacion: date | None = None
    datos_banco: dict[str, str] = Field(default_factory=dict)
    columnas: list[str] | None = Field(default=None, description="Sólo genérico.")
    separador: str = Field(default=",", description="Sólo genérico: , | ; tab")
    formato: str = Field(default="csv", description="Sólo genérico: csv | xlsx")
    encabezado: bool = True


class ArchivoSchema(BaseModel):
    nombre: str
    mime: str
    base64: str
    sha256: str


class IncluidoSchema(BaseModel):
    empleado_no: str
    nombre: str
    importe: Decimal
    banco: str
    banco_nombre: str
    tipo_cuenta: str
    cuenta: str = Field(description="Enmascarada: sólo los últimos 4 dígitos.")
    interbancario: bool


class ExcluidoSchema(BaseModel):
    empleado_no: str
    nombre: str
    neto: Decimal
    causa: str = Field(description="sin_ficha | neto_cero | efectivo | cheque | sin_cuenta | "
                       "layout")
    motivo: str


class DispersionResponse(BaseModel):
    exito: bool = True
    layout: LayoutSchema
    archivo: ArchivoSchema | None
    incluidos: list[IncluidoSchema]
    excluidos: list[ExcluidoSchema]
    total_nomina: Decimal
    total_archivo: Decimal
    total_excluidos: Decimal
    cuadra: bool
    advertencias: list[str]


@router.get("/nomina/dispersion/layouts", response_model=LayoutsResponse, responses=_ERR,
            summary="Layouts de dispersión disponibles, con su fuente y estado")
def layouts(cliente: str | None = Query(default=None),
            ctx: Contexto = Depends(contexto_actual)) -> LayoutsResponse:
    guardados: dict[str, dict[str, str]] = {}
    if cliente:
        guardados = dict((cliente_o_404(ctx, cliente).datos or {}).get("dispersion") or {})
    return LayoutsResponse(
        layouts=[LayoutSchema(**descripcion(c)) for c in LAYOUTS.values()],
        columnas_genericas=COLUMNAS, columnas_default=list(DEFAULT), bancos=BANCOS,
        datos_guardados=guardados,
    )


@router.post("/nomina/clientes/{cliente_id}/periodos/{periodo_id}/dispersion",
             response_model=DispersionResponse, responses=_ERR,
             summary="Generar el archivo de dispersión de una nómina cerrada")
def dispersar(cliente_id: str, periodo_id: int, req: DispersionRequest,
              ctx: Contexto = Depends(contexto_actual)) -> DispersionResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    exigir_modulo(ctx.db, ctx.despacho_id, "dispersion")  # P5-08: módulo por plan
    periodo = srv.periodo_o_404(ctx.db, cliente, periodo_id)
    servicio.exigir_cerrada(periodo)
    config: dict[str, Any] = {}
    if req.layout == "generico":
        config = {"columnas": req.columnas, "separador": req.separador,
                  "formato": req.formato, "encabezado": req.encabezado}
    layout = layout_por_id(req.layout, **config)
    cargo = servicio.cuenta_de_cargo(ctx.db, cliente, req.cuenta_cargo_id, layout)
    r = servicio.generar(ctx.db, cliente, periodo, layout, cargo,
                         fecha_aplicacion=req.fecha_aplicacion, datos_banco=req.datos_banco)
    if req.datos_banco:  # se recuerdan para la siguiente vez (no son secretos: son del contrato)
        previos = dict((cliente.datos or {}).get("dispersion") or {})
        previos[layout.id] = servicio.validar_datos_banco(layout, req.datos_banco)
        cliente.datos = {**(cliente.datos or {}), "dispersion": previos}
    registrar(ctx, "nomina.dispersion.generar", "nomina_periodo", periodo.id, {
        "layout": layout.id, "estado_layout": layout.estado, "incluidos": len(r.incluidos),
        "excluidos": len(r.excluidos), "total_archivo": str(r.total_archivo),
        "total_nomina": str(r.total_nomina), "sha256": r.sha256,
    }, cliente)
    archivo = None
    if r.contenido is not None and r.nombre_archivo:
        archivo = ArchivoSchema(nombre=r.nombre_archivo, mime=layout.mime, sha256=r.sha256,
                                base64=base64.b64encode(r.contenido).decode("ascii"))
    return DispersionResponse(
        layout=LayoutSchema(**descripcion(type(layout))),
        archivo=archivo,
        incluidos=[IncluidoSchema(
            empleado_no=p.empleado_no, nombre=p.nombre, importe=servicio.de_centavos(p.centavos),
            banco=a.banco, banco_nombre=nombre_banco(a.banco), tipo_cuenta=a.tipo,
            cuenta=f"****{a.numero[-4:]}", interbancario=a.interbancario,
        ) for p, a in r.incluidos],
        excluidos=[ExcluidoSchema(**e.__dict__) for e in r.excluidos],
        total_nomina=r.total_nomina, total_archivo=r.total_archivo,
        total_excluidos=r.total_excluidos, cuadra=r.cuadra, advertencias=r.advertencias,
    )
