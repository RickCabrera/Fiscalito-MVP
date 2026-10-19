"""
Contabilidad electrónica — Anexo 24 (P2-07): `/api/v1/contabilidad-electronica/...`.

Todo pasa por `contexto_actual` + `cliente_o_404` (otro despacho = 404). Contrato en
`docs/api-contract.md` §Contabilidad electrónica.
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auditoria import registrar
from app.contabilidad.anexo24 import esquemas, generador
from app.credenciales.servicio import obtener_firmante
from app.integraciones import registro
from app.integraciones.buzon_sat import EnvioContabilidad
from app.modelos.nucleo import Cliente
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/contabilidad-electronica", tags=["contabilidad-electronica"])

Documento = Literal["catalogo", "balanza", "polizas", "auxiliar_cuentas", "auxiliar_folios"]


class SolicitudEntrada(BaseModel):
    documento: Documento
    anio: int = Field(..., ge=2015, le=2100)
    mes: int = Field(..., ge=1, le=12)
    tipo_envio: Literal["N", "C"] = "N"
    fecha_mod_bal: date | None = None
    tipo_solicitud: Literal["", "AF", "FC", "DE", "CO"] = ""
    num_orden: str = Field("", max_length=13)
    num_tramite: str = Field("", max_length=14)
    sellar: bool = False


def _generar(ctx: Contexto, cliente: Cliente, e: SolicitudEntrada) -> generador.Documento:
    firmante = obtener_firmante(ctx.db, cliente, "efirma") if e.sellar else None
    s = generador.Solicitud(e.documento, e.anio, e.mes, e.tipo_envio, e.fecha_mod_bal,
                            e.tipo_solicitud, e.num_orden.strip().upper(),
                            e.num_tramite.strip().upper())
    return generador.generar(ctx.db, cliente, s, firmante=firmante)


@router.get("/documentos")
def documentos(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Documentos que se generan y cómo se entregan (no hay API del SAT para el envío)."""
    return {"exito": True,
            "documentos": [{"clave": t.clave, "nombre": t.nombre, "sufijo": t.sufijo,
                            "a_solicitud": t.clave in ("polizas", "auxiliar_cuentas",
                                                       "auxiliar_folios")}
                           for t in esquemas.TIPOS.values()],
            "instrucciones_portal": list(generador.INSTRUCCIONES_PORTAL)}


@router.post("/clientes/{clave}/validar")
def validar(clave: str, entrada: SolicitudEntrada,
            ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Genera y valida contra el XSD oficial. Devuelve errores, advertencias y el XML."""
    cliente = cliente_o_404(ctx, clave)
    doc = _generar(ctx, cliente, entrada)
    return {"exito": True, "nombre": doc.nombre, "valido": doc.valido, "errores": doc.errores,
            "advertencias": doc.advertencias, "sellado": doc.sellado,
            "xml": doc.xml.decode("utf-8")}


@router.post("/clientes/{clave}/zip")
def descargar_zip(clave: str, entrada: SolicitudEntrada,
                  ctx: Contexto = Depends(contexto_actual)) -> Response:
    """El ZIP con el nombre que exige el SAT (RFC+AAAA+MM+tipo). 422 si no valida."""
    cliente = cliente_o_404(ctx, clave)
    doc = _generar(ctx, cliente, entrada)
    datos = generador.empaquetar(doc)
    registrar(ctx, "contabilidad_electronica.generar", "cliente", cliente.id,
              {"archivo": doc.nombre, "sellado": doc.sellado}, cliente)
    return Response(datos, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{doc.nombre}.zip"',
                             "X-Nombre-Archivo": f"{doc.nombre}.zip"})


@router.post("/clientes/{clave}/enviar")
def enviar(clave: str, entrada: SolicitudEntrada,
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Envía por el adaptador `buzon_sat` (falso = simulación; portal_sat POR CONFIRMAR)."""
    cliente = cliente_o_404(ctx, clave)
    doc = _generar(ctx, cliente, entrada)
    datos = generador.empaquetar(doc)
    buzon = registro.obtener("buzon_sat")
    acuse = buzon.enviar(EnvioContabilidad(
        (cliente.rfc or "").upper(), f"{doc.nombre}.zip", datos,
        lambda: obtener_firmante(ctx.db, cliente, "efirma")))
    registrar(ctx, "contabilidad_electronica.enviar", "cliente", cliente.id,
              {"archivo": doc.nombre, "acuse": acuse.folio, "via": buzon.nombre}, cliente)
    return {"exito": True, "via": buzon.nombre, "acuse": {
        "folio": acuse.folio, "estado": acuse.estado, "mensaje": acuse.mensaje},
        "zip_base64": base64.b64encode(datos).decode("ascii")}
