"""
Cuentas por cobrar del despacho (P5-03): igualas, cargos, pagos, estado de cuenta y
recordatorios. Sólo dueño y contador (`app/cobranza/servicio.ROLES_COBRANZA`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auditoria import registrar
from app.cobranza import documentos, recordatorios
from app.cobranza import servicio as cob
from app.exceptions import FiscalAgentError
from app.modelos.cobranza import RecordatorioCobro
from app.modelos.nucleo import Cliente, Despacho
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual

router = APIRouter(prefix="/cobranza", tags=["cobranza"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Honorarios(BaseModel):
    iguala_mensual: Decimal = Field(ge=0, le=Decimal("99999999"))
    concepto: str = Field("Honorarios contables", min_length=1, max_length=300)
    dia_cargo: int = Field(1, ge=1, le=28)
    dias_credito: int = Field(10, ge=0, le=180)
    activo: bool = True
    facturar: bool = False
    correo: str = Field("", max_length=320)
    telefono: str = Field("", max_length=20)
    recordatorio_automatico: bool = False
    canal_recordatorio: Literal["correo", "whatsapp"] = "correo"
    dias_entre_recordatorios: int = Field(7, ge=1, le=90)


class CargoNuevo(BaseModel):
    concepto: str = Field(min_length=1, max_length=300)
    importe: Decimal = Field(gt=0, le=Decimal("99999999"))
    fecha: date
    vencimiento: date | None = None
    facturar: bool = False


class FacturaCargo(BaseModel):
    facturar: bool
    uuid_cfdi: str | None = Field(None, max_length=36)


class PagoNuevo(BaseModel):
    fecha: date
    importe: Decimal = Field(gt=0, le=Decimal("99999999"))
    forma_pago: str = Field("", max_length=40)
    referencia: str = Field("", max_length=120)
    cfdi_uuid: str | None = Field(None, max_length=36)
    nota: str = Field("", max_length=1000)


class GenerarIgualas(BaseModel):
    periodo: str | None = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class RecordatorioNuevo(BaseModel):
    canal: Literal["correo", "whatsapp"]
    programado_para: datetime | None = None


def _hoy(hoy: date | None) -> date:
    return hoy or date.today()


def _cliente(ctx: Contexto, clave: str) -> Cliente:
    cob.exigir_cobranza(ctx)
    return cliente_o_404(ctx, clave)


@router.get("/resumen")
def resumen(hoy: date | None = None, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Saldo, vencido y antigüedad por cliente visible, con totales."""
    cob.exigir_cobranza(ctx)
    return cob.resumen_cartera(ctx, clientes_visibles(ctx), _hoy(hoy))


@router.get("/clientes/{clave}")
def detalle(clave: str, hoy: date | None = None,
            ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Estado de cuenta, configuración de honorarios y recordatorios del cliente."""
    cliente = _cliente(ctx, clave)
    ec = cob.estado_cuenta(ctx.db, cliente, _hoy(hoy))
    recs = ctx.db.scalars(select(RecordatorioCobro).where(
        RecordatorioCobro.cliente_id == cliente.id).order_by(RecordatorioCobro.id.desc())
        .limit(50))
    return {**ec, "honorarios": cob.config_json(cob.config_de(ctx.db, cliente)),
            "recordatorios": [recordatorios.recordatorio_json(r) for r in recs]}


@router.put("/clientes/{clave}/honorarios")
def guardar_honorarios(clave: str, cuerpo: Honorarios,
                       ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = _cliente(ctx, clave)
    h = cob.guardar_config(ctx, cliente, cuerpo.model_dump())
    return {"exito": True, "honorarios": cob.config_json(h)}


@router.post("/clientes/{clave}/cargos")
def nuevo_cargo(clave: str, cuerpo: CargoNuevo,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Servicio extra (la iguala se genera sola cada mes)."""
    cliente = _cliente(ctx, clave)
    c = cob.crear_servicio(ctx, cliente, concepto=cuerpo.concepto, importe=cuerpo.importe,
                           fecha=cuerpo.fecha, vencimiento=cuerpo.vencimiento,
                           facturar=cuerpo.facturar)
    return {"exito": True, "cargo": cob.cargo_json(c)}


@router.delete("/clientes/{clave}/cargos/{cargo_id}")
def cancelar_cargo(clave: str, cargo_id: int,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    c = cob.cancelar_cargo(ctx, _cliente(ctx, clave), cargo_id)
    return {"exito": True, "cargo": cob.cargo_json(c)}


@router.put("/clientes/{clave}/cargos/{cargo_id}/factura")
def factura_cargo(clave: str, cargo_id: int, cuerpo: FacturaCargo,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Gancho de P5-04: marca el cargo para facturar y guarda el UUID cuando exista."""
    c = cob.marcar_factura(ctx, _cliente(ctx, clave), cargo_id, facturar=cuerpo.facturar,
                           uuid_cfdi=cuerpo.uuid_cfdi)
    return {"exito": True, "cargo": cob.cargo_json(c)}


@router.post("/clientes/{clave}/pagos")
def nuevo_pago(clave: str, cuerpo: PagoNuevo,
               ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    p = cob.registrar_pago(ctx, _cliente(ctx, clave), fecha=cuerpo.fecha,
                           importe=cuerpo.importe, forma_pago=cuerpo.forma_pago,
                           referencia=cuerpo.referencia, cfdi_uuid=cuerpo.cfdi_uuid,
                           nota=cuerpo.nota)
    return {"exito": True, "pago": cob.pago_json(p)}


@router.delete("/clientes/{clave}/pagos/{pago_id}")
def borrar_pago(clave: str, pago_id: int,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cob.borrar_pago(ctx, _cliente(ctx, clave), pago_id)
    return {"exito": True}


@router.post("/cargos/generar")
def generar(cuerpo: GenerarIgualas, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Genera ya las igualas de un mes (default: el actual) de los clientes visibles."""
    cob.exigir_cobranza(ctx)
    if cuerpo.periodo:
        anio, mes = (int(x) for x in cuerpo.periodo.split("-"))
        base = date(anio, mes, 1)
    else:
        base = date.today().replace(day=1)
    ids = {c.id for c in clientes_visibles(ctx)}
    nuevos = cob.generar_igualas(ctx.db, base, despacho_id=ctx.despacho_id, cliente_ids=ids,
                                 forzar_dia=True, usuario=ctx.uid)
    registrar(ctx, "cobranza.generar_igualas", "periodo", base.strftime("%Y-%m"),
              {"cargos": len(nuevos)})
    return {"exito": True, "periodo": base.strftime("%Y-%m"), "cargos": len(nuevos)}


@router.get("/clientes/{clave}/estado-cuenta")
def estado_cuenta_archivo(clave: str, formato: Literal["pdf", "xlsx"] = Query("pdf"),
                          hoy: date | None = None,
                          ctx: Contexto = Depends(contexto_actual)) -> Response:
    cliente = _cliente(ctx, clave)
    ec = cob.estado_cuenta(ctx.db, cliente, _hoy(hoy))
    despacho = ctx.db.get(Despacho, ctx.despacho_id)
    nombre = (despacho.nombre if despacho else "") or "Despacho"
    nombre_archivo = f"estado-cuenta-{cliente.clave}-{ec['hoy']}"
    if formato == "xlsx":
        return Response(documentos.excel(ec, nombre), media_type=XLSX, headers={
            "Content-Disposition": f'attachment; filename="{nombre_archivo}.xlsx"'})
    return Response(documentos.pdf(ec, nombre), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{nombre_archivo}.pdf"'})


@router.post("/clientes/{clave}/recordatorios")
def nuevo_recordatorio(clave: str, cuerpo: RecordatorioNuevo,
                       ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Sin `programado_para` (o en el pasado) se manda ya; si no, se programa en la cola."""
    cliente = _cliente(ctx, clave)
    destino = recordatorios.destino_de(cob.config_de(ctx.db, cliente), cuerpo.canal)
    cuando = cuerpo.programado_para
    if cuando is not None and cuando.tzinfo is None:
        raise FiscalAgentError("`programado_para` necesita zona horaria.", 422)
    ahora = datetime.now(UTC)
    rec = recordatorios.crear(ctx.db, cliente, cuerpo.canal, destino, usuario=ctx.uid,
                              programado_para=cuando if cuando and cuando > ahora else ahora)
    if cuando is not None and cuando > ahora:
        recordatorios.programar(ctx.db, rec)
    else:
        recordatorios.enviar(ctx.db, rec)
    registrar(ctx, "cobranza.recordatorio", "recordatorio", rec.id,
              {"canal": rec.canal, "estado": rec.estado}, cliente)
    return {"exito": True, "recordatorio": recordatorios.recordatorio_json(rec)}


@router.delete("/clientes/{clave}/recordatorios/{rec_id}")
def cancelar_recordatorio(clave: str, rec_id: int,
                          ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = _cliente(ctx, clave)
    rec = ctx.db.get(RecordatorioCobro, rec_id)
    if rec is None or rec.cliente_id != cliente.id:
        raise FiscalAgentError("No existe ese recordatorio.", 404)
    if rec.estado != "programado":
        raise FiscalAgentError("Sólo se cancela un recordatorio programado.", 409)
    rec.estado = "cancelado"
    ctx.db.flush()
    registrar(ctx, "cobranza.cancelar_recordatorio", "recordatorio", rec.id, {}, cliente)
    return {"exito": True, "recordatorio": recordatorios.recordatorio_json(rec)}
