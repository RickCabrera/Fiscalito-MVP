"""
Consultas de datos de UN cliente para el asistente (P5-07) y el bot de WhatsApp (P5-06).

TODA CIFRA SALE DE AQUÍ, NUNCA DEL MODELO
-----------------------------------------
Cada función lee la base o corre un motor determinístico y devuelve un dict serializable con
los importes como texto con dos decimales (`"1234.50"`). El LLM recibe ese dict como resultado
de una herramienta y sólo lo explica; la respuesta de la API además devuelve los mismos
datos aparte (`herramientas_servidor`), para que la pantalla —y los tests— vean las cifras del
motor sin pasar por el texto del modelo.

La tenencia NO se resuelve aquí: quien llama ya obtuvo `cliente` con `cliente_o_404` (el
asistente) o por el contacto registrado del número (el bot). Estas funciones jamás buscan un
cliente por su cuenta.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import nomina_servicio
from app.agenda import servicio as agenda
from app.alertas.reglas import alerta_json
from app.contabilidad import balanza as motor_balanza
from app.exceptions import FiscalAgentError
from app.fiscal_engine.actualizacion import fecha_limite_mensual
from app.fiscal_engine.resumen_impuestos import OpcionesResumen, armar_resumen, resumen_dict
from app.impuestos import servicio as impuestos
from app.modelos.alertas import SEVERIDADES, AlertaFiscal
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente

MAX_RENGLONES_BALANZA = 60
MAX_PERIODOS_NOMINA = 12
MAX_RECIBOS = 100
MAX_DIAS_VENCIMIENTOS = 120
MAX_ALERTAS = 30


def rango_mes(anio: int, mes: int) -> tuple[date, date]:
    """Primer y último día del mes, o 422 si el mes no es válido."""
    if not (2000 <= anio <= 2100 and 1 <= mes <= 12):
        raise FiscalAgentError(f"Periodo inválido: {anio}-{mes}.", 422)
    return date(anio, mes, 1), date(anio, mes, monthrange(anio, mes)[1])


def _por_tipo(db: Session, cliente: Cliente, desde: date, hasta: date,
              cancelados: bool) -> list[dict[str, Any]]:
    estatus = (Comprobante.estatus_sat == "cancelado") if cancelados \
        else (Comprobante.estatus_sat != "cancelado")
    filas = db.execute(
        select(Comprobante.tipo, Comprobante.direccion, func.count(Comprobante.id),
               func.sum(Comprobante.total))
        .where(Comprobante.cliente_id == cliente.id, estatus,
               Comprobante.fecha >= datetime.combine(desde, time.min),
               Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), time.min))
        .group_by(Comprobante.tipo, Comprobante.direccion)
        .order_by(Comprobante.tipo, Comprobante.direccion))
    return [{"tipo": t, "direccion": d, "cantidad": int(n), "total": f"{(s or 0):.2f}"}
            for t, d, n, s in filas]


def boveda_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> dict[str, Any]:
    """CFDI del mes por tipo y dirección, sin cancelar y cancelados, con conteo y total."""
    desde, hasta = rango_mes(anio, mes)
    activos = _por_tipo(db, cliente, desde, hasta, cancelados=False)
    cancelados = _por_tipo(db, cliente, desde, hasta, cancelados=True)
    return {
        "periodo": f"{anio:04d}-{mes:02d}",
        "total_comprobantes": sum(r["cantidad"] for r in activos + cancelados),
        "no_cancelados": activos,
        "cancelados": cancelados,
        "nota": "Tipos: I ingreso, E egreso, P pago, N nómina, T traslado. Importes totales "
                "con impuestos. 'no_cancelados' incluye los que aún no se verifican contra el "
                "SAT.",
    }


def balanza_mes(db: Session, cliente: Cliente, anio: int, mes: int,
                nivel: int = 1) -> dict[str, Any]:
    """La balanza de comprobación del mes hasta `nivel` (1 = cuentas de mayor)."""
    desde, hasta = rango_mes(anio, mes)
    nivel = max(1, min(int(nivel), 3))
    b = motor_balanza.balanza(db, cliente, desde, hasta, nivel=nivel)
    renglones = b["renglones"]
    return {
        "periodo": f"{anio:04d}-{mes:02d}", "nivel": nivel, "cuadra": b["cuadra"],
        "totales": b["totales"], "diferencias": b["diferencias"],
        "renglones": renglones[:MAX_RENGLONES_BALANZA],
        "renglones_omitidos": max(len(renglones) - MAX_RENGLONES_BALANZA, 0),
    }


def _periodo_json(p: Any) -> dict[str, Any]:
    r = nomina_servicio.resumen(p)
    return {
        "id": r["id"], "tipo": r["tipo"], "inicio": r["inicio"].isoformat(),
        "fin": r["fin"].isoformat(), "fecha_pago": r["fecha_pago"].isoformat(),
        "estado": r["estado"], "empleados": r["empleados"],
        **{k: f"{r[k]:.2f}" for k in ("total_percepciones", "total_deducciones",
                                      "total_isr", "total_neto")},
    }


def nomina(db: Session, cliente: Cliente, periodo_id: int | None = None) -> dict[str, Any]:
    """
    Sin `periodo_id`: los últimos periodos guardados con sus totales y netos. Con él: ese
    periodo y el neto de cada recibo. Es lo GUARDADO (no recalcula), igual que el historial.
    """
    if periodo_id is not None:
        p = nomina_servicio.periodo_o_404(db, cliente, int(periodo_id))
        recibos = nomina_servicio.recibos_de(db, p)
        return {
            "periodo": _periodo_json(p),
            "recibos": [{"empleado_no": r.empleado_no, "nombre": r.nombre,
                         "percepciones": f"{r.total_percepciones:.2f}",
                         "isr": f"{r.isr:.2f}", "neto": f"{r.neto:.2f}"}
                        for r in recibos[:MAX_RECIBOS]],
        }
    periodos = nomina_servicio.historial(db, cliente)[:MAX_PERIODOS_NOMINA]
    return {"periodos": [_periodo_json(p) for p in periodos],
            "nota": "" if periodos else "El cliente no tiene nóminas guardadas."}


def vencimientos(db: Session, cliente: Cliente, hoy: date, dias: int = 30) -> dict[str, Any]:
    """Obligaciones del calendario: las vencidas sin presentar y las que vencen en `dias`."""
    dias = max(1, min(int(dias), MAX_DIAS_VENCIMIENTOS))
    desde, hasta = hoy - timedelta(days=60), hoy + timedelta(days=dias)
    obligaciones = agenda.obligaciones_cliente(db, cliente, desde, hasta, hoy=hoy)
    salida = [o for o in obligaciones
              if o.estado == "vencida" or (o.estado == "pendiente" and o.fecha_limite >= hoy)]
    salida.sort(key=lambda o: (o.fecha_limite, o.clave))
    return {
        "hoy": hoy.isoformat(), "hasta": hasta.isoformat(),
        "obligaciones": [{k: o.a_dict()[k] for k in (
            "nombre", "tipo", "periodo", "fecha_limite", "estado", "fundamento")}
            for o in salida],
    }


def alertas(db: Session, cliente: Cliente) -> dict[str, Any]:
    """Alertas fiscales abiertas del cliente, las más graves primero."""
    orden = {s: i for i, s in enumerate(SEVERIDADES)}
    filas = sorted(db.scalars(select(AlertaFiscal).where(
        AlertaFiscal.despacho_id == cliente.despacho_id, AlertaFiscal.cliente_id == cliente.id,
        AlertaFiscal.resuelta.is_(False))),
        key=lambda a: (orden.get(a.severidad, 9), -a.fecha.toordinal(), a.id))
    return {"alertas": [{k: alerta_json(a, cliente)[k] for k in (
        "tipo", "severidad", "titulo", "detalle", "fecha")} for a in filas[:MAX_ALERTAS]]}


def periodo_que_vence(hoy: date) -> tuple[int, int]:
    """
    El periodo cuya declaración mensual vence en el mes de `hoy`: el mes anterior.

    # DECISIÓN PROVISIONAL (nocturno): "¿cuánto pago este mes?" se interpreta como la
    # declaración que se presenta este mes (la del mes anterior, que vence el día 17 de
    # éste, Art. 31 RCFF / Art. 5-D LIVA). Es lo que el contribuyente paga este mes.
    """
    return (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)


def impuestos_mes(db: Session, cliente: Cliente, anio: int, mes: int,
                  hoy: date) -> dict[str, Any]:
    """
    El resumen de impuestos del periodo (P3-07) con los importes del sistema, a pagar el
    día límite o, si ya pasó, hoy (con actualización y recargos del motor). Sin capturas:
    es lo que calcula el sistema, no lo que el contador ajustó a mano.
    """
    rango_mes(anio, mes)
    cfg = impuestos.config_de(db, cliente)
    importes, notas = impuestos.importes_del_periodo(db, cliente, anio, mes)
    limite = fecha_limite_mensual(anio, mes)
    r = armar_resumen(anio, mes, limite, max(hoy, limite), importes, {},
                      OpcionesResumen(cfg.modo_factor, cfg.tipo_recargo, cfg.tope_meses_recargos))
    r.notas = notas + r.notas
    d = resumen_dict(r)
    return {
        "periodo": f"{anio:04d}-{mes:02d}", "fecha_limite": d["fecha_limite"],
        "fecha_pago": d["fecha_pago"], "total_a_pagar": d["total_a_pagar_ajustado"],
        "conceptos": [{k: x[k] for k in ("concepto", "importe_a_pagar", "actualizacion",
                                         "recargos", "total")}
                      for x in d["renglones"] if x["aplica"] and x["total"] != "0.00"],
        "notas": d["notas"],
        "aviso": "Estimación del sistema con los CFDI de la bóveda; tu contador la confirma "
                 "antes de presentar.",
    }
