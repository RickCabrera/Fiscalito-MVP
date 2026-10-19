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

from app.boveda_cfdi import calculo, servicio
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.sat_verificacion import estatus, listas
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
    # P1-03/04: detalle del SAT y marca de listas 69-B/69 de la contraparte.
    detalle = estatus.detalle(ctx.db, [c.id for c in filas])
    marcados = listas.rfcs_marcados(
        ctx.db, {c.rfc_receptor if c.direccion == "emitido" else c.rfc_emisor for c in filas})
    salida = []
    for c in filas:
        fila = _fila(c)
        v = detalle.get(c.id)
        fila["fecha_estatus"] = c.fecha_estatus.isoformat() if c.fecha_estatus else None
        fila["estatus_cancelacion"] = v.estatus_cancelacion if v else ""
        contraparte = c.rfc_receptor if c.direccion == "emitido" else c.rfc_emisor
        fila["art_69b"] = marcados.get(contraparte)
        salida.append(fila)
    return {
        "exito": True, "total": total, "pagina": pagina, "por_pagina": por_pagina,
        "comprobantes": salida,
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


@router.get("/clientes/{clave}/facturas-calculo")
def facturas_calculo(
    clave: str,
    desde: date = Query(..., description="Fecha inicial (inclusive), AAAA-MM-DD"),
    hasta: date = Query(..., description="Fecha final (inclusive), AAAA-MM-DD"),
    tipos: str | None = Query(
        None, max_length=20, description="Tipos separados por coma (I,E,P,T). Default: todos."
    ),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """
    Los CFDI vigentes del periodo en la forma del esquema `CFDI` de los cálculos (P1-06).

    Sin cancelados ni nómina; los pagos salen uno por documento relacionado. Ver
    `app/boveda_cfdi/calculo.py`.
    """
    cliente = cliente_o_404(ctx, clave)
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", status_code=422)
    lista = [t.strip().upper() for t in tipos.split(",") if t.strip()] if tipos else None
    if lista is not None:
        invalidos = sorted(set(lista) - set(calculo.TIPOS_CALCULO))
        if invalidos or not lista:
            raise FiscalAgentError(
                f"Tipos no válidos para cálculo: {', '.join(invalidos) or '(vacío)'}. "
                "Se aceptan I, E, P y T (la nómina no entra a los cálculos fiscales).",
                status_code=422,
            )
    r = calculo.facturas_para_calculo(
        ctx.db, cliente, desde, hasta, lista or calculo.TIPOS_CALCULO
    )
    return {
        "exito": True, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "facturas": [f.model_dump(mode="json") for f in r.facturas],
        "relacionados": [f.model_dump(mode="json") for f in r.relacionados],
        "resumen": r.resumen, "advertencias": r.advertencias,
    }


@router.get("/clientes/{clave}/resumen")
def resumen_boveda(
    clave: str,
    filtros: servicio.Filtros = Depends(_filtros),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Conteos y totales por mes, tipo y dirección."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "renglones": servicio.resumen(ctx.db, cliente, filtros)}
