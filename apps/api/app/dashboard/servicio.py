"""
Dashboard del despacho (P5-02): la pantalla de entrada, en UNA llamada.

Junta, para los clientes que el usuario VE (`clientes_visibles`: el auxiliar sólo los
asignados), lo que hay que atender: vencimientos de la semana (P3-10), alertas abiertas por
severidad (P3-09), estado de la descarga SAT (P1-02), semáforo de la opinión (P1-05),
e.firma/CSD por vencer, nóminas por cerrar o timbrar (P4), la agenda del usuario y las
cuentas por cobrar vencidas (P5-03, sólo dueño y contador).

SIN N+1
-------
Cada tarjeta es una o pocas consultas agregadas sobre la lista de ids visibles (`IN`), nunca
una consulta por cliente: el calendario usa `agenda.servicio.precargar` (tres consultas para
toda la cartera) y el resto agrupa con `GROUP BY`. `tests/plan_p/test_dashboard.py` cuenta las
consultas y exige que no crezcan con el número de clientes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from app.agenda.servicio import NOMBRE_CREDENCIAL, obligaciones_cliente, precargar
from app.cobranza.servicio import ROLES_COBRANZA, dinero, saldos_por_cliente
from app.modelos.agenda import TareaAgenda
from app.modelos.alertas import SEVERIDADES, AlertaFiscal
from app.modelos.nomina import NominaPeriodo
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import (
    ESTADOS_VIVOS_SOLICITUD,
    AlertaDescargaSat,
    ConfigDescargaSat,
    SolicitudDescargaSat,
)
from app.sat_verificacion import cumplimiento
from app.tenancy import Contexto, clientes_visibles

DIAS_SEMANA = 7
DIAS_ATRAS_VENCIDAS = 30
DIAS_CREDENCIAL = 30
MAX_RENGLONES = 20


def _ficha(c: Cliente) -> str:
    return f"/app/clientes/{c.clave}"


def _vencimientos(ctx: Contexto, clientes: list[Cliente], hoy: date) -> dict[str, Any]:
    precarga = precargar(ctx.db, clientes)
    desde, hasta = hoy - timedelta(days=DIAS_ATRAS_VENCIDAS), hoy + timedelta(days=DIAS_SEMANA)
    obligaciones = []
    for c in clientes:
        obligaciones += obligaciones_cliente(ctx.db, c, desde, hasta, hoy, precarga=precarga)
    abiertas = sorted((o for o in obligaciones if o.estado != "presentada"
                       and o.tipo != "credencial"),
                      key=lambda o: (o.fecha_limite, o.cliente_nombre, o.clave))
    semana = [o for o in abiertas if o.fecha_limite >= hoy]
    vencidas = [o for o in abiertas if o.fecha_limite < hoy]
    renglones = [{**o.a_dict(), "enlace": f"/app/calendario?cliente={o.cliente}"}
                 for o in (vencidas + semana)[:MAX_RENGLONES]]
    # La e.firma y el CSD salen de la misma precarga (sin consultas extra).
    limite_cred = hoy + timedelta(days=DIAS_CREDENCIAL)
    por_id = {c.id: c for c in clientes}
    creds = []
    for cid, lista in precarga.credenciales.items():
        for cred in lista:
            vence = cred.valido_hasta.date()
            if vence <= limite_cred:
                c = por_id[cid]
                creds.append({"cliente": c.clave, "cliente_nombre": c.nombre, "tipo": cred.tipo,
                              "nombre": NOMBRE_CREDENCIAL.get(cred.tipo, cred.tipo),
                              "vence": vence.isoformat(), "dias": (vence - hoy).days,
                              "vencida": vence < hoy, "enlace": _ficha(c)})
    creds.sort(key=lambda x: (x["vence"], x["cliente_nombre"]))
    return {
        "vencimientos": {"semana": len(semana), "vencidas": len(vencidas),
                         "renglones": renglones, "enlace": "/app/calendario"},
        "credenciales": {"total": len(creds), "vencidas": sum(1 for x in creds if x["vencida"]),
                         "renglones": creds[:MAX_RENGLONES],
                         "enlace": "/app/calendario?tipo=credencial"},
    }


def _alertas(ctx: Contexto, ids: list[int]) -> dict[str, Any]:
    conteo = dict.fromkeys(SEVERIDADES, 0)
    if ids:
        for severidad, n in ctx.db.execute(
                select(AlertaFiscal.severidad, func.count()).where(
                    AlertaFiscal.despacho_id == ctx.despacho_id,
                    AlertaFiscal.cliente_id.in_(ids), AlertaFiscal.resuelta.is_(False))
                .group_by(AlertaFiscal.severidad)):
            conteo[severidad] = int(n)
    return {"total": sum(conteo.values()), **conteo,
            "enlaces": {s: f"/app/alertas?severidad={s}" for s in SEVERIDADES},
            "enlace": "/app/alertas"}


def _descarga_sat(ctx: Contexto, clientes: list[Cliente], ids: list[int]) -> dict[str, Any]:
    if not ids:
        return {"renglones": [], "resumen": {}, "enlace": "/app/sat"}
    db = ctx.db
    configs = {c.cliente_id: c for c in db.scalars(
        select(ConfigDescargaSat).where(ConfigDescargaSat.cliente_id.in_(ids)))}
    ultima = dict(db.execute(
        select(SolicitudDescargaSat.cliente_id, func.max(SolicitudDescargaSat.terminada_en))
        .where(SolicitudDescargaSat.cliente_id.in_(ids),
               SolicitudDescargaSat.estado.in_(("terminada", "sin_datos")))
        .group_by(SolicitudDescargaSat.cliente_id)).all())
    vivas = dict(db.execute(
        select(SolicitudDescargaSat.cliente_id, func.count())
        .where(SolicitudDescargaSat.cliente_id.in_(ids),
               SolicitudDescargaSat.estado.in_(ESTADOS_VIVOS_SOLICITUD))
        .group_by(SolicitudDescargaSat.cliente_id)).all())
    alertas = dict(db.execute(
        select(AlertaDescargaSat.cliente_id, func.count())
        .where(AlertaDescargaSat.cliente_id.in_(ids), AlertaDescargaSat.resuelta.is_(False))
        .group_by(AlertaDescargaSat.cliente_id)).all())
    renglones, resumen = [], {"al_dia": 0, "en_proceso": 0, "con_error": 0, "pausada": 0,
                              "sin_configurar": 0}
    for c in clientes:
        cfg = configs.get(c.id)
        if alertas.get(c.id):
            estado = "con_error"
        elif cfg is None or not cfg.activa:
            estado = "sin_configurar"
        elif cfg.pausada_por:
            estado = "pausada"
        elif vivas.get(c.id):
            estado = "en_proceso"
        else:
            estado = "al_dia"
        resumen[estado] += 1
        t = ultima.get(c.id)
        renglones.append({"cliente": c.clave, "cliente_nombre": c.nombre, "estado": estado,
                          "ultima_descarga": t.isoformat() if t else None,
                          "en_proceso": int(vivas.get(c.id, 0)),
                          "alertas": int(alertas.get(c.id, 0)),
                          "pausada_por": cfg.pausada_por if cfg else "",
                          "enlace": _ficha(c)})
    orden = {"con_error": 0, "pausada": 1, "sin_configurar": 2, "en_proceso": 3, "al_dia": 4}
    renglones.sort(key=lambda r: (orden[r["estado"]], r["cliente_nombre"]))
    return {"renglones": renglones[:MAX_RENGLONES], "resumen": resumen, "enlace": "/app/sat"}


def _opinion(ctx: Contexto, clientes: list[Cliente], ids: list[int], hoy: date
             ) -> dict[str, Any]:
    docs = cumplimiento.ultimas(ctx.db, ids, "opinion")
    conteo = {"verde": 0, "amarillo": 0, "rojo": 0, "gris": 0}
    renglones = []
    for c in clientes:
        doc = docs.get(c.id)
        det = cumplimiento.detalle_semaforo(doc, hoy)
        conteo[det["semaforo"]] += 1
        renglones.append({"cliente": c.clave, "cliente_nombre": c.nombre, **det,
                          "resultado": doc.resultado if doc else None,
                          "fecha": doc.fecha.isoformat() if doc else None,
                          "enlace": _ficha(c)})
    orden = {"rojo": 0, "amarillo": 1, "gris": 2, "verde": 3}
    renglones.sort(key=lambda r: (orden[r["semaforo"]], r["cliente_nombre"]))
    return {**conteo, "renglones": renglones[:MAX_RENGLONES], "enlace": "/app/clientes"}


def _nominas(ctx: Contexto, por_id: dict[int, Cliente], ids: list[int]) -> dict[str, Any]:
    if not ids:
        return {"por_cerrar": 0, "por_timbrar": 0, "renglones": []}
    filas = list(ctx.db.scalars(
        select(NominaPeriodo).where(NominaPeriodo.cliente_id.in_(ids),
                                    NominaPeriodo.estado.in_(("borrador", "calculada",
                                                              "cerrada")))
        .order_by(NominaPeriodo.fecha_pago, NominaPeriodo.id)))
    renglones = []
    for n in filas[:MAX_RENGLONES]:
        c = por_id[n.cliente_id]
        renglones.append({"id": n.id, "cliente": c.clave, "cliente_nombre": c.nombre,
                          "tipo": n.tipo, "inicio": n.inicio.isoformat(),
                          "fin": n.fin.isoformat(), "fecha_pago": n.fecha_pago.isoformat(),
                          "estado": n.estado,
                          "accion": "timbrar" if n.estado == "cerrada" else "cerrar",
                          "enlace": f"/app/clientes/{c.clave}/nomina"})
    return {"por_cerrar": sum(1 for n in filas if n.estado != "cerrada"),
            "por_timbrar": sum(1 for n in filas if n.estado == "cerrada"),
            "renglones": renglones}


def _agenda(ctx: Contexto, por_id: dict[int, Cliente], ids: list[int], hoy: date
            ) -> dict[str, Any]:
    q = select(TareaAgenda).where(
        TareaAgenda.despacho_id == ctx.despacho_id, TareaAgenda.responsable_uid == ctx.uid,
        TareaAgenda.estado != "hecha", TareaAgenda.fecha <= hoy + timedelta(days=DIAS_SEMANA))
    q = q.where(TareaAgenda.cliente_id.is_(None) | TareaAgenda.cliente_id.in_(ids)) if ids \
        else q.where(TareaAgenda.cliente_id.is_(None))
    tareas = list(ctx.db.scalars(q.order_by(TareaAgenda.fecha, TareaAgenda.id)))
    renglones = []
    for t in tareas[:MAX_RENGLONES]:
        c = por_id.get(t.cliente_id) if t.cliente_id else None
        renglones.append({"id": t.id, "titulo": t.titulo, "fecha": t.fecha.isoformat(),
                          "estado": t.estado, "atrasada": t.fecha < hoy,
                          "cliente": c.clave if c else None,
                          "cliente_nombre": c.nombre if c else "",
                          "enlace": "/app/calendario?vista=agenda"})
    return {"total": len(tareas), "atrasadas": sum(1 for t in tareas if t.fecha < hoy),
            "renglones": renglones, "enlace": "/app/calendario?vista=agenda"}


def _cobranza(ctx: Contexto, por_id: dict[int, Cliente], ids: list[int], hoy: date
              ) -> dict[str, Any] | None:
    if ctx.rol not in ROLES_COBRANZA:
        return None
    saldos = saldos_por_cliente(ctx.db, ids, hoy)
    vencidos = [(cid, s) for cid, s in saldos.items() if s.vencido > 0]
    vencidos.sort(key=lambda x: (-x[1].vencido, por_id[x[0]].nombre))
    total = sum((s.vencido for _, s in vencidos), Decimal("0"))
    return {"vencido": str(dinero(total)), "clientes": len(vencidos),
            "renglones": [{"cliente": por_id[cid].clave, "cliente_nombre": por_id[cid].nombre,
                           "vencido": str(dinero(s.vencido)), "saldo": str(s.saldo),
                           "vencido_desde": s.vencido_desde.isoformat()
                           if s.vencido_desde else None,
                           "enlace": f"/app/cobranza?cliente={por_id[cid].clave}"}
                          for cid, s in vencidos[:MAX_RENGLONES]],
            "enlace": "/app/cobranza"}


def dashboard(ctx: Contexto, hoy: date | None = None) -> dict[str, Any]:
    """Todas las tarjetas del dashboard para el usuario del contexto."""
    hoy = hoy or date.today()
    clientes = clientes_visibles(ctx)
    ids = [c.id for c in clientes]
    por_id = {c.id: c for c in clientes}
    return {
        "exito": True, "hoy": hoy.isoformat(), "rol": ctx.rol, "clientes": len(clientes),
        **_vencimientos(ctx, clientes, hoy),
        "alertas": _alertas(ctx, ids),
        "descarga_sat": _descarga_sat(ctx, clientes, ids),
        "opinion": _opinion(ctx, clientes, ids, hoy),
        "nominas": _nominas(ctx, por_id, ids),
        "agenda": _agenda(ctx, por_id, ids, hoy),
        "cobranza": _cobranza(ctx, por_id, ids, hoy),
    }
