"""
Verificaciones contra el SAT por cliente (P1-03/04/05): `/api/v1/sat/...`.

Todo pasa por `contexto_actual` + `cliente_o_404` (cliente de otro despacho = 404). Las
consultas al SAT corren en la cola (trabajos): las rutas encolan y responden con el trabajo.
Contrato en `docs/api-contract.md` §Verificación SAT.
"""

from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auditoria import registrar
from app.contabilidad.polizas import TIPO_ALERTA_REVERSA
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.modelos.cfdi import Comprobante
from app.modelos.sat_verificacion import AlertaRiesgo, ConfigCumplimiento
from app.sat_verificacion import cumplimiento, listas
from app.sat_verificacion import trabajos as sat_trabajos
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual

router = APIRouter(prefix="/sat", tags=["sat-verificacion"])

TipoDoc = Literal["opinion", "constancia"]
MAX_DIAS_RANGO = 5 * 366
MAX_BYTES_PDF = 10 * 1024 * 1024


class RangoEstatus(BaseModel):
    desde: date
    hasta: date


class ConfigEntrada(BaseModel):
    automatico: bool = True
    dia_del_mes: int = Field(1, ge=1, le=28)
    constancia: bool = True


def _trabajo(t: Any) -> dict[str, Any]:
    return {"id": t.id, "tipo": t.tipo, "estado": t.estado}


# ── P1-03: estatus ──


@router.post("/clientes/{clave}/verificar-estatus")
def verificar_estatus(
    clave: str, rango: RangoEstatus, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Encola la verificación de estatus de los CFDI del rango (los no cancelados)."""
    cliente = cliente_o_404(ctx, clave)
    if rango.desde > rango.hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", status_code=422)
    if (rango.hasta - rango.desde).days > MAX_DIAS_RANGO:
        raise FiscalAgentError("El rango máximo es de cinco años.", status_code=422)
    por_revisar = ctx.db.scalar(select(func.count(Comprobante.id)).where(
        Comprobante.cliente_id == cliente.id, Comprobante.estatus_sat != "cancelado",
        Comprobante.fecha >= datetime.combine(rango.desde, time.min),
        Comprobante.fecha < datetime.combine(rango.hasta + timedelta(days=1), time.min),
    )) or 0
    trabajo = sat_trabajos.encolar_verificacion(ctx.db, cliente, rango.desde, rango.hasta)
    registrar(ctx, "sat.verificar_estatus", "trabajo", trabajo.id,
              {"desde": rango.desde.isoformat(), "hasta": rango.hasta.isoformat(),
               "comprobantes": int(por_revisar)}, cliente)
    return {"exito": True, "trabajo": _trabajo(trabajo), "comprobantes": int(por_revisar)}


# ── P1-04: listas 69-B ──


@router.get("/listas/estado")
def estado_listas(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Última carga de cada listado del SAT. Son datos públicos, iguales para todo despacho."""
    return {"exito": True, "listas": listas.estado_listas(ctx.db)}


@router.get("/clientes/{clave}/riesgos-69b")
def riesgos_69b(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Contrapartes del cliente en listados del SAT, más sus alertas."""
    cliente = cliente_o_404(ctx, clave)
    riesgos = [r.como_dict() for r in listas.riesgos_de(ctx.db, cliente)]
    alertas = ctx.db.scalars(select(AlertaRiesgo).where(AlertaRiesgo.cliente_id == cliente.id)
                             .order_by(AlertaRiesgo.id.desc()).limit(200))
    return {
        "exito": True,
        "riesgos": riesgos,
        "en_rojo": sum(1 for r in riesgos if r["rojo"]),
        "alertas": [{
            "id": a.id, "tipo": a.tipo, "rfc": a.rfc, "nombre": a.nombre, "lista": a.lista,
            "situacion": a.situacion, "relacion": a.relacion, "nivel": a.nivel,
            "atendida": a.atendida, "creada_en": a.creado_en.isoformat() if a.creado_en else None,
            "detalle": a.detalle,
        } for a in alertas],
        "listas": listas.estado_listas(ctx.db),
    }


@router.post("/clientes/{clave}/alertas/{alerta_id}/atender")
def atender_alerta(clave: str, alerta_id: int, ctx: Contexto = Depends(contexto_actual)
                   ) -> dict[str, Any]:
    """Marca la alerta como atendida (sigue en el historial)."""
    cliente = cliente_o_404(ctx, clave)
    alerta = ctx.db.get(AlertaRiesgo, alerta_id)
    if alerta is None or alerta.cliente_id != cliente.id:
        raise FiscalAgentError("No existe esa alerta para este cliente.", status_code=404)
    alerta.atendida, alerta.atendida_por = True, ctx.uid
    registrar(ctx, "sat.alerta_atendida", "alerta", alerta.id, {"rfc": alerta.rfc}, cliente)
    return {"exito": True}


# ── P1-05: opinión y constancia ──


def _ultimo_y_semaforo(ctx: Contexto, cliente_id: int, tipo: str) -> dict[str, Any]:
    ultimo = cumplimiento.ultimas(ctx.db, [cliente_id], tipo).get(cliente_id)
    d = cumplimiento.detalle_semaforo(ultimo)
    return {"ultimo": cumplimiento.fila(ultimo) if ultimo else None,
            "semaforo": d["semaforo"], "origen": d["origen"], "marca": d["marca"]}


def _historial(ctx: Contexto, clave: str, tipo: str) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    config = cumplimiento.config_de(ctx.db, cliente)
    return {
        "exito": True, "tipo": tipo,
        **_ultimo_y_semaforo(ctx, cliente.id, tipo),
        "historial": [cumplimiento.fila(d) for d in cumplimiento.historial(ctx.db, cliente, tipo)],
        "via": registro.elegida("opinion_cumplimiento") or None,
        "dias_vigencia": cumplimiento.dias_vigencia(),
        "config": {"automatico": config.automatico, "dia_del_mes": config.dia_del_mes,
                   "constancia": config.constancia},
    }


@router.get("/clientes/{clave}/opinion")
def historial_opinion(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Semáforo, última opinión e historial."""
    return _historial(ctx, clave, "opinion")


@router.get("/clientes/{clave}/constancia")
def historial_constancia(clave: str, ctx: Contexto = Depends(contexto_actual)
                         ) -> dict[str, Any]:
    """Última constancia de situación fiscal e historial."""
    return _historial(ctx, clave, "constancia")


@router.post("/clientes/{clave}/opinion/obtener")
def obtener_ahora(
    clave: str, tipo: TipoDoc = Query("opinion"), ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """"Obtener ahora": encola la consulta con el adaptador configurado."""
    cliente = cliente_o_404(ctx, clave)
    if registro.elegida("opinion_cumplimiento") == "manual":
        raise FiscalAgentError(
            "La vía configurada es manual: descarga el PDF del portal del SAT y súbelo.", 409)
    if not cumplimiento.rfc_de(cliente):
        raise FiscalAgentError("Captura el RFC del cliente antes de pedir su opinión.", 422)
    trabajo = sat_trabajos.encolar_cumplimiento(ctx.db, cliente, tipo, ctx.uid)
    registrar(ctx, "sat.cumplimiento_obtener", "trabajo", trabajo.id, {"tipo": tipo}, cliente)
    return {"exito": True, "trabajo": _trabajo(trabajo)}


@router.post("/clientes/{clave}/opinion/pdf")
async def subir_pdf(
    clave: str,
    archivo: UploadFile = File(...),
    tipo: TipoDoc = Form("opinion"),
    resultado: Literal["positiva", "negativa", "sin_obligaciones", "desconocido"] | None
    = Form(None),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """El despacho sube el PDF a mano (opinión o constancia). Funciona con cualquier vía."""
    cliente = cliente_o_404(ctx, clave)
    datos = await archivo.read(MAX_BYTES_PDF + 1)
    doc = cumplimiento.guardar_pdf(ctx.db, cliente, tipo, datos, ctx.uid, resultado)
    registrar(ctx, "sat.cumplimiento_subir", "documento", doc.id,
              {"tipo": tipo, "resultado": doc.resultado}, cliente)
    return {"exito": True, "documento": cumplimiento.fila(doc),
            "semaforo": cumplimiento.semaforo(doc) if tipo == "opinion" else None,
            "marca": cumplimiento.marca(doc) if tipo == "opinion" else None}


@router.get("/clientes/{clave}/opinion/{doc_id}/pdf")
def descargar_pdf(clave: str, doc_id: int, ctx: Contexto = Depends(contexto_actual)
                  ) -> Response:
    """El PDF guardado (opinión o constancia), byte por byte."""
    cliente = cliente_o_404(ctx, clave)
    doc = cumplimiento.documento(ctx.db, cliente, doc_id)
    nombre = f"{doc.tipo}-{cumplimiento.rfc_de(cliente) or cliente.clave}-{doc.fecha}.pdf"
    return Response(content=cumplimiento.leer_pdf(doc), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.put("/clientes/{clave}/opinion/config")
def guardar_config(clave: str, entrada: ConfigEntrada, ctx: Contexto = Depends(contexto_actual)
                   ) -> dict[str, Any]:
    """Programación mensual del cliente (automática sí/no, día del mes, constancia)."""
    cliente = cliente_o_404(ctx, clave)
    config = ctx.db.get(ConfigCumplimiento, cliente.id) or ConfigCumplimiento(
        cliente_id=cliente.id)
    ctx.db.add(config)
    config.automatico, config.dia_del_mes, config.constancia = (
        entrada.automatico, entrada.dia_del_mes, entrada.constancia)
    registrar(ctx, "sat.cumplimiento_config", "cliente", cliente.id, entrada.model_dump(),
              cliente)
    return {"exito": True, "config": entrada.model_dump()}


# ── cartera ──


@router.get("/cartera/semaforo")
def semaforo_cartera(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Por cliente visible: semáforo de la opinión y riesgos 69-B en rojo / alertas abiertas."""
    clientes = clientes_visibles(ctx)
    ids = [c.id for c in clientes]
    ultimas = cumplimiento.ultimas(ctx.db, ids, "opinion")
    def abiertas(*cond: Any) -> dict[int, int]:
        if not ids:
            return {}
        return dict(ctx.db.execute(
            select(AlertaRiesgo.cliente_id, func.count(AlertaRiesgo.id))
            .where(AlertaRiesgo.cliente_id.in_(ids), AlertaRiesgo.atendida.is_(False), *cond)
            .group_by(AlertaRiesgo.cliente_id)).all())

    riesgos = abiertas(AlertaRiesgo.nivel.in_(("alto", "medio")),
                       AlertaRiesgo.tipo != TIPO_ALERTA_REVERSA)
    contables = abiertas(AlertaRiesgo.tipo == TIPO_ALERTA_REVERSA)
    return {"exito": True, "clientes": [{
        "clave": c.clave,
        "opinion": {
            **cumplimiento.detalle_semaforo(ultimas.get(c.id)),
            "resultado": ultimas[c.id].resultado if c.id in ultimas else None,
            "fecha": ultimas[c.id].fecha.isoformat() if c.id in ultimas else None,
        },
        "riesgos_69b": int(riesgos.get(c.id, 0)),
        "alertas_contables": int(contables.get(c.id, 0)),
    } for c in clientes]}
