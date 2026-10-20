"""
Cierre de periodo y de ejercicio (P2-08).

CIERRE MENSUAL
--------------
Un mes cerrado (`PeriodoCerrado`) no acepta pólizas nuevas, ediciones ni cancelaciones
(`polizas.exigir_abierto`; el generador también lo respeta). Antes de cerrar se valida:
- que la balanza del mes cuadre (Σ cargos = Σ abonos y saldos en cero) — nunca se fuerza;
- que no haya CFDI vigentes del mes sin póliza. Esto SÍ se puede forzar con motivo (hay
  despachos que contabilizan a mano CFDI que el generador omite por configuración); el
  motivo queda en la bitácora.
Reabrir pide rol dueño o contador y un motivo; queda en `historial_periodos` y en la
auditoría general.

CIERRE ANUAL
------------
Con la balanza del ejercicio cuadrada y sin CFDI pendientes, se generan tres pólizas de
diario (no se pueden capturar a mano: `origen` cierre/apertura):
1. **Cierre de resultados** (31-dic, `cierre:<año>:resultados`): salda cada cuenta de
   resultados (rubros 4xx–7xx del código agrupador, ver `reportes.seccion`) contra
   305.01 utilidad del ejercicio o 305.02 pérdida del ejercicio (cuentas por rol de
   `config.ROLES`, configurables por cliente).
2. **Cierre de balance** (31-dic, `cierre:<año>:balance`): salda todas las cuentas de
   balance y de orden, incluido el resultado del ejercicio ya traspasado.
3. **Apertura** (1-ene siguiente, `apertura:<año+1>`): reabre los mismos saldos. Con
   `traspasar_resultado` (default **apagado**: la apertura refleja tal cual el balance de
   cierre y el traspaso lo decide el contador) el resultado del ejercicio se abre ya en
   304.01 / 304.02 (resultados de ejercicios anteriores).
Después se cierran los doce meses. Cómo cuentan estas pólizas en balanza y reportes:
`balanza.py`, PÓLIZAS DE CIERRE Y APERTURA.

Deshacer el cierre anual (dueño/contador, con motivo) cancela las tres pólizas, siempre que
enero del año siguiente siga abierto, y reabre diciembre.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.contabilidad import catalogo, polizas, reportes
from app.contabilidad.asientos import CERO
from app.contabilidad.balanza import balanza, totales_por_cuenta
from app.contabilidad.config import efectiva
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import (
    ConfigContable,
    CuentaContable,
    HistorialPeriodo,
    MovimientoPoliza,
    PeriodoCerrado,
    Poliza,
)
from app.modelos.nucleo import Cliente

ROLES_REABRIR = ("dueno", "contador")
MAX_LISTA = 200


def _fin_de_mes(anio: int, mes: int) -> date:
    return reportes._fin_de_mes(anio, mes)


def _validar_mes(anio: int, mes: int) -> None:
    if not (2000 <= anio <= 2100 and 1 <= mes <= 12):
        raise FiscalAgentError("Periodo inválido.", 422)


def _historial(db: Session, cliente: Cliente, anio: int, mes: int, accion: str, motivo: str,
               uid: str) -> None:
    db.add(HistorialPeriodo(cliente_id=cliente.id, anio=anio, mes=mes, accion=accion,
                            motivo=(motivo or "")[:500], uid=uid, fecha=datetime.now(UTC)))


# ── validaciones ──


def cfdi_sin_poliza(db: Session, cliente: Cliente, desde: date,
                    hasta: date) -> tuple[list[dict[str, Any]], int]:
    """
    CFDI vigentes del rango que deberían tener póliza y no la tienen.

    Cuenta como "con póliza" cualquier póliza (automática por su UUID, o manual que cite el
    UUID en el encabezado o en un movimiento), activa o cancelada a mano: cancelar es una
    decisión del contador. No aplican los traslados ni la nómina recibida.
    """
    inicio = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta, datetime.max.time())
    comps = list(db.scalars(comprobantes_vigentes(
        select(Comprobante).where(Comprobante.cliente_id == cliente.id,
                                  Comprobante.fecha >= inicio, Comprobante.fecha <= fin,
                                  Comprobante.tipo != "T"))
        .order_by(Comprobante.fecha)))
    comps = [c for c in comps if not (c.tipo == "N" and c.direccion != "emitido")]
    if not comps:
        return [], 0
    uuids = {c.uuid for c in comps}
    lista_uuids = list(uuids)
    con: set[str] = set()
    con.update(u for u in db.scalars(select(Poliza.uuid_cfdi).where(
        Poliza.cliente_id == cliente.id, Poliza.uuid_cfdi.in_(lista_uuids))) if u)
    claves = [f"cfdi:{u}" for u in lista_uuids]
    con.update((k or "")[5:] for k in db.scalars(select(Poliza.clave_origen).where(
        Poliza.cliente_id == cliente.id, Poliza.clave_origen.in_(claves))))
    con.update(u for u in db.scalars(
        select(MovimientoPoliza.uuid_cfdi).join(Poliza, Poliza.id == MovimientoPoliza.poliza_id)
        .where(Poliza.cliente_id == cliente.id, MovimientoPoliza.uuid_cfdi.in_(lista_uuids)))
        if u)
    faltan = [c for c in comps if c.uuid not in con]
    return [{"uuid": c.uuid, "fecha": c.fecha.date().isoformat(), "tipo": c.tipo,
             "direccion": c.direccion, "rfc": c.rfc_receptor if c.direccion == "emitido"
             else c.rfc_emisor, "total": f"{c.total:.2f}", "moneda": c.moneda}
            for c in faltan[:MAX_LISTA]], len(faltan)


def _inicio_ejercicio(db: Session, cliente: Cliente, anio: int) -> date:
    """1 de enero, o la fecha de saldos iniciales si la contabilidad arrancó ese año."""
    config = db.get(ConfigContable, cliente.id)
    inicio = date(anio, 1, 1)
    if config and config.fecha_saldos_iniciales and \
            config.fecha_saldos_iniciales.year == anio and config.fecha_saldos_iniciales > inicio:
        return config.fecha_saldos_iniciales
    return inicio


def validar(db: Session, cliente: Cliente, desde: date, hasta: date) -> dict[str, Any]:
    """Lo que impide cerrar el rango: descuadre de la balanza y CFDI sin póliza."""
    bal = balanza(db, cliente, desde, hasta, solo="con_movimiento")
    lista, total = cfdi_sin_poliza(db, cliente, desde, hasta)
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "balanza_cuadra": bal["cuadra"], "diferencias": bal["diferencias"],
            "cfdi_sin_poliza": lista, "total_cfdi_sin_poliza": total,
            "se_puede_cerrar": bal["cuadra"] and total == 0}


def _exigir_validacion(v: dict[str, Any], forzar: bool, motivo: str) -> None:
    if not v["balanza_cuadra"]:
        d = v["diferencias"]
        raise FiscalAgentError(
            f"La balanza no cuadra (movimientos {d['movimientos']}, saldo final "
            f"{d['saldo_final']}): corrige antes de cerrar.", 409)
    if v["total_cfdi_sin_poliza"] and not forzar:
        raise FiscalAgentError(
            f"Hay {v['total_cfdi_sin_poliza']} CFDI vigentes del periodo sin póliza. "
            "Genera sus pólizas o cierra forzando con un motivo.", 409)
    if v["total_cfdi_sin_poliza"] and forzar and len((motivo or "").strip()) < 5:
        raise FiscalAgentError("Para cerrar con CFDI sin póliza escribe el motivo.", 422)


# ── cierre mensual ──


def cerrar_mes(db: Session, cliente: Cliente, anio: int, mes: int, uid: str, *,
               forzar: bool = False, motivo: str = "") -> dict[str, Any]:
    _validar_mes(anio, mes)
    if polizas.periodo_cerrado(db, cliente.id, date(anio, mes, 1)):
        raise FiscalAgentError(f"El periodo {anio}-{mes:02d} ya está cerrado.", 409)
    v = validar(db, cliente, date(anio, mes, 1), _fin_de_mes(anio, mes))
    _exigir_validacion(v, forzar, motivo)
    polizas.cerrar_periodo(db, cliente, anio, mes, uid)
    nota = motivo if v["total_cfdi_sin_poliza"] else ""
    if v["total_cfdi_sin_poliza"]:
        nota = f"Forzado con {v['total_cfdi_sin_poliza']} CFDI sin póliza: {motivo}"
    _historial(db, cliente, anio, mes, "cerrar", nota, uid)
    db.flush()
    return v


def reabrir_mes(db: Session, cliente: Cliente, anio: int, mes: int, uid: str, rol: str,
                motivo: str) -> None:
    _validar_mes(anio, mes)
    if rol not in ROLES_REABRIR:
        raise FiscalAgentError("Sólo el dueño o un contador del despacho reabren periodos.", 403)
    if len((motivo or "").strip()) < 5:
        raise FiscalAgentError("Para reabrir un periodo escribe el motivo.", 422)
    if not polizas.periodo_cerrado(db, cliente.id, date(anio, mes, 1)):
        raise FiscalAgentError("Ese periodo no está cerrado.", 404)
    polizas.abrir_periodo(db, cliente, anio, mes)
    _historial(db, cliente, anio, mes, "reabrir", motivo, uid)
    db.flush()


# ── cierre anual ──


def _polizas_cierre(db: Session, cliente: Cliente, anio: int) -> list[Poliza]:
    claves = [f"cierre:{anio}:resultados", f"cierre:{anio}:balance", f"apertura:{anio + 1}"]
    return list(db.scalars(select(Poliza).where(
        Poliza.cliente_id == cliente.id, Poliza.clave_origen.in_(claves),
        Poliza.estado == "activa").order_by(Poliza.fecha, Poliza.id)))


def _cuenta_rol(cuentas: dict[str, CuentaContable], numero: str, rol: str) -> CuentaContable:
    c = cuentas.get(numero)
    if c is None or not c.afectable:
        raise FiscalAgentError(
            f"La cuenta {numero} ({rol}) no existe o no es afectable: revísala en la "
            "configuración de pólizas antes del cierre anual.", 409)
    return c


def _poliza(db: Session, cliente: Cliente, fecha: date, origen: str, clave: str, concepto: str,
            movs: list[tuple[int, Decimal]], uid: str) -> Poliza | None:
    """movs: (cuenta_id, importe deudor con signo). Omite ceros; None si no hay nada."""
    renglones = [MovimientoPoliza(cuenta_id=cid, cargo=v if v > 0 else CERO,
                                  abono=-v if v < 0 else CERO, concepto=concepto[:300])
                 for cid, v in movs if v != 0]
    if not renglones:
        return None
    cargos = sum((m.cargo for m in renglones), CERO)
    abonos = sum((m.abono for m in renglones), CERO)
    if cargos != abonos:  # defensa: el ejercicio se validó cuadrado
        raise FiscalAgentError(f"La póliza '{concepto}' no cuadra ({cargos} ≠ {abonos}).", 409)
    p = Poliza(cliente_id=cliente.id, tipo="diario", fecha=fecha, concepto=concepto[:500],
               origen=origen, estado="activa", clave_origen=clave, diferencia=CERO,
               advertencias=[], creado_por=uid)
    return polizas.guardar(db, p, renglones)


def cierre_anual(db: Session, cliente: Cliente, anio: int, uid: str, *,
                 traspasar_resultado: bool = False, forzar: bool = False,
                 motivo: str = "") -> dict[str, Any]:
    """Pólizas de cierre y apertura del ejercicio `anio` y cierre de sus doce meses."""
    _validar_mes(anio, 12)
    if _polizas_cierre(db, cliente, anio):
        raise FiscalAgentError(f"El ejercicio {anio} ya tiene cierre anual.", 409)
    apertura = date(anio + 1, 1, 1)
    polizas.exigir_abierto(db, cliente.id, apertura)
    inicio, fin = _inicio_ejercicio(db, cliente, anio), date(anio, 12, 31)
    v = validar(db, cliente, inicio, fin)
    _exigir_validacion(v, forzar, motivo)

    ef = efectiva(db, cliente)
    cuentas = catalogo.por_numero(db, cliente)
    por_id = {c.id: c for c in cuentas.values()}
    utilidad = _cuenta_rol(cuentas, ef.cuenta("resultado_utilidad"), "utilidad del ejercicio")
    perdida = _cuenta_rol(cuentas, ef.cuenta("resultado_perdida"), "pérdida del ejercicio")

    saldos = {cid: t.final for cid, t in totales_por_cuenta(db, cliente, inicio, fin).items()
              if cid in por_id and t.final != 0}
    # 1. Resultados contra el resultado del ejercicio.
    de_resultados = {cid: s for cid, s in saldos.items() if reportes.es_de_resultados(por_id[cid])}
    neto = sum(de_resultados.values(), CERO)  # deudor positivo: >0 pérdida, <0 utilidad
    movs = [(cid, -s) for cid, s in sorted(de_resultados.items(),
                                           key=lambda x: por_id[x[0]].numero)]
    cuenta_resultado = perdida if neto > 0 else utilidad
    movs.append((cuenta_resultado.id, neto))
    p_res = _poliza(db, cliente, fin, "cierre", f"cierre:{anio}:resultados",
                    f"Cierre de cuentas de resultados {anio}", movs, uid)
    # 2. Balance (con el resultado ya traspasado) y 3. apertura.
    balance = {cid: s for cid, s in saldos.items() if cid not in de_resultados}
    balance[cuenta_resultado.id] = balance.get(cuenta_resultado.id, CERO) + neto
    balance = {cid: s for cid, s in balance.items() if s != 0}
    orden = sorted(balance.items(), key=lambda x: por_id[x[0]].numero)
    p_bal = _poliza(db, cliente, fin, "cierre", f"cierre:{anio}:balance",
                    f"Cierre de cuentas de balance {anio}", [(c, -s) for c, s in orden], uid)
    reabre: list[tuple[int, Decimal]] = []
    for cid, s in orden:
        if traspasar_resultado and cid in (utilidad.id, perdida.id):
            rol = "utilidad_anteriores" if cid == utilidad.id else "perdida_anteriores"
            destino = _cuenta_rol(cuentas, ef.cuenta(rol), "resultados de ejercicios anteriores")
            cid = destino.id
        reabre.append((cid, s))
    p_ape = _poliza(db, cliente, apertura, "apertura", f"apertura:{anio + 1}",
                    f"Apertura del ejercicio {anio + 1}", reabre, uid)
    for mes in range(1, 13):
        polizas.cerrar_periodo(db, cliente, anio, mes, uid)
    _historial(db, cliente, anio, 0, "cierre_anual",
               f"Forzado con {v['total_cfdi_sin_poliza']} CFDI sin póliza: {motivo}"
               if v["total_cfdi_sin_poliza"] else motivo, uid)
    db.flush()
    resultado = -neto
    return {
        "anio": anio, "resultado": f"{resultado:.2f}",
        "tipo_resultado": "utilidad" if resultado >= 0 else "perdida",
        "polizas": [polizas.como_dict(db, p) for p in (p_res, p_bal, p_ape) if p is not None],
        "validacion": v,
    }


def deshacer_cierre_anual(db: Session, cliente: Cliente, anio: int, uid: str, rol: str,
                          motivo: str) -> int:
    if rol not in ROLES_REABRIR:
        raise FiscalAgentError("Sólo el dueño o un contador deshacen un cierre anual.", 403)
    if len((motivo or "").strip()) < 5:
        raise FiscalAgentError("Para deshacer el cierre anual escribe el motivo.", 422)
    existentes = _polizas_cierre(db, cliente, anio)
    if not existentes:
        raise FiscalAgentError(f"El ejercicio {anio} no tiene cierre anual.", 404)
    polizas.exigir_abierto(db, cliente.id, date(anio + 1, 1, 1))
    ahora = datetime.now(UTC)
    for p in existentes:
        p.estado, p.cancelada_en = "cancelada", ahora
        p.motivo_cancelacion = f"Cierre anual deshecho: {motivo}"[:300]
        # Libera la clave para que el ejercicio pueda volver a cerrarse.
        p.clave_origen = f"{p.clave_origen}:cancelada:{p.id}"[:60]
    polizas.abrir_periodo(db, cliente, anio, 12)
    _historial(db, cliente, anio, 0, "deshacer_cierre_anual", motivo, uid)
    _historial(db, cliente, anio, 12, "reabrir", f"Cierre anual deshecho: {motivo}", uid)
    db.flush()
    return len(existentes)


# ── pantalla de periodos ──


def estado_ejercicio(db: Session, cliente: Cliente, anio: int) -> dict[str, Any]:
    """Los doce meses con su estado, conteos y bitácora; y el cierre anual."""
    _validar_mes(anio, 1)
    cerrados = {p.mes: p for p in db.scalars(select(PeriodoCerrado).where(
        PeriodoCerrado.cliente_id == cliente.id, PeriodoCerrado.anio == anio))}
    conteo = dict(db.execute(
        select(Poliza.mes, func.count(Poliza.id)).where(
            Poliza.cliente_id == cliente.id, Poliza.anio == anio, Poliza.estado == "activa",
            Poliza.origen.not_in(("cierre", "apertura")))
        .group_by(Poliza.mes)).all())
    meses = []
    for mes in range(1, 13):
        c = cerrados.get(mes)
        meses.append({"mes": mes, "estado": "cerrado" if c else "abierto",
                      "cerrado_en": c.cerrado_en.isoformat() if c else None,
                      "cerrado_por": c.cerrado_por if c else None,
                      "polizas": int(conteo.get(mes, 0))})
    historial = [{"mes": h.mes, "accion": h.accion, "motivo": h.motivo, "uid": h.uid,
                  "fecha": h.fecha.isoformat()} for h in db.scalars(
        select(HistorialPeriodo).where(HistorialPeriodo.cliente_id == cliente.id,
                                       HistorialPeriodo.anio == anio)
        .order_by(HistorialPeriodo.fecha.desc(), HistorialPeriodo.id.desc()).limit(200))]
    cierre = _polizas_cierre(db, cliente, anio)
    return {"anio": anio, "meses": meses, "historial": historial,
            "cierre_anual": {"hecho": bool(cierre),
                             "polizas": [polizas.como_dict(db, p) for p in cierre]}}
