"""
Archivos para el IMSS: lotes IDSE por tipo de movimiento y archivos de importación al SUA.

Las posiciones viven en `app/nomina_engine/imss_layouts.py` (con su fuente). Aquí sólo se
juntan los datos de la ficha, del cliente y del movimiento.

QUIÉN QUEDA FUERA, Y POR QUÉ SE DICE
------------------------------------
Un movimiento sin NSS de 11 dígitos, sin apellido paterno o nombre de pila capturados por
separado (no se parten a la adivina), o sin la causa de una baja, NO entra al archivo: sale en
`no_exportables` con su razón y se queda `pendiente`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import nomina_servicio as srv
from app.exceptions import FiscalAgentError, FiscalValidationError
from app.modelos.imss import LoteImss, MovimientoImss
from app.modelos.nucleo import Cliente
from app.nomina_engine import imss_layouts as L
from app.nomina_engine.cuotas_mensuales import TramoSBC, sbc_vigente
from app.nomina_imss.historial import historial_de
from app.schemas.empleado import EmpleadoCarteraSchema

CRLF = "\r\n"
DESTINOS = ("idse_08", "idse_07", "idse_02", "sua_trabajadores", "sua_movimientos")


@dataclass
class Generado:
    lote: LoteImss
    no_exportables: list[dict[str, str]] = field(default_factory=list)
    transliterados: list[str] = field(default_factory=list)


def _datos_patron(cliente: Cliente) -> tuple[str, str, str]:
    datos = cliente.datos or {}
    rp_base, rp_dig = L.partir_registro_patronal(str(datos.get("registro_patronal") or ""))
    guia = str(datos.get("guia_subdelegacion") or "").strip()
    if not guia:
        raise FiscalAgentError(
            "Falta la guía de la subdelegación del cliente: va en las posiciones 134-138 de "
            "cada movimiento y en las cifras de control.", status_code=422)
    return rp_base, rp_dig, guia


def faltantes(f: EmpleadoCarteraSchema, tipo: str) -> list[str]:
    falta = []
    if len(f.nss) != 11:
        falta.append("el NSS (11 dígitos)")
    if not f.apellido_paterno.strip():
        falta.append("el apellido paterno")
    if not f.nombres.strip():
        falta.append("el nombre de pila")
    if len(f.empleado_no) > 10:
        falta.append("una clave de trabajador de máximo 10 caracteres")
    return falta


def _identidad(f: EmpleadoCarteraSchema, rp_base: str, rp_dig: str) -> dict[str, str]:
    return {
        "registro_patronal": rp_base, "digito_rp": rp_dig,
        "nss": f.nss[:10], "digito_nss": f.nss[10:],
        "apellido_paterno": f.apellido_paterno.upper(),
        "apellido_materno": f.apellido_materno.upper(),
        "nombres": f.nombres.upper(), "clave_trabajador": f.empleado_no,
        "identificador": L.IDENTIFICADOR_FORMATO,
    }


def _registro_idse(
    mov: MovimientoImss, f: EmpleadoCarteraSchema, rp_base: str, rp_dig: str, guia: str
) -> tuple[str, list[str]]:
    valores = {
        **_identidad(f, rp_base, rp_dig),
        "fecha_movimiento": L.fecha_ddmmaaaa(mov.fecha),
        "tipo_movimiento": mov.tipo, "guia": guia,
    }
    if mov.tipo == L.TIPO_BAJA:
        if mov.causa_baja not in L.CAUSAS_BAJA:
            raise FiscalValidationError("falta la causa de baja (catálogo IMSS)")
        valores["causa_baja"] = mov.causa_baja
    else:
        if mov.sbc is None:
            raise FiscalValidationError("falta el SBC del movimiento")
        valores.update({
            "sbc": L.importe_implicito(mov.sbc, 4), "tipo_salario": mov.tipo_salario,
            "jornada": f.jornada, "curp": f.curp,
        })
        if mov.tipo == L.TIPO_ALTA_REINGRESO:
            valores.update({"tipo_trabajador": f.tipo_trabajador, "umf": f.umf})
    return L.escribir_registro(L.LAYOUT_IDSE[mov.tipo], valores, L.LARGO_IDSE)


def _guardar_lote(
    db: Session, cliente: Cliente, tipo: str, nombre: str, lineas: list[str], uid: str
) -> LoteImss:
    texto = CRLF.join(lineas) + CRLF if lineas else ""
    lote = LoteImss(cliente_id=cliente.id, tipo=tipo, nombre_archivo=nombre,
                    registros=len(lineas), contenido=texto,
                    sha256=hashlib.sha256(texto.encode("ascii")).hexdigest(), creado_por=uid)
    db.add(lote)
    db.flush()
    return lote


def generar_idse(
    db: Session, cliente: Cliente, tipo: str, uid: str, ids: list[int] | None = None
) -> Generado:
    """Lote IDSE (DISPMAG) de un tipo de movimiento, con sus cifras de control."""
    if tipo not in L.LAYOUT_IDSE:
        raise FiscalAgentError(f"Tipo de movimiento inválido: {tipo!r} (08, 07 o 02).", 422)
    rp_base, rp_dig, guia = _datos_patron(cliente)
    q = select(MovimientoImss).where(MovimientoImss.cliente_id == cliente.id,
                                     MovimientoImss.tipo == tipo)
    q = q.where(MovimientoImss.id.in_(ids)) if ids else q.where(
        MovimientoImss.estado == "pendiente")
    movimientos = list(db.scalars(q.order_by(MovimientoImss.fecha, MovimientoImss.id)))
    fichas = {f.empleado_no: f for f in srv.fichas_del_cliente(db, cliente)[0]}
    lineas: list[str] = []
    incluidos: list[MovimientoImss] = []
    salida = Generado(lote=None)  # type: ignore[arg-type]
    for mov in movimientos:
        f = fichas.get(mov.empleado_no)
        razon = "" if f else "el empleado ya no está en la cartera"
        if f and (falta := faltantes(f, tipo)):
            razon = "falta " + ", ".join(falta)
        if not razon and f is not None:
            try:
                linea, cambios = _registro_idse(mov, f, rp_base, rp_dig, guia)
            except FiscalValidationError as e:
                razon = str(e)
            else:
                lineas.append(linea)
                incluidos.append(mov)
                salida.transliterados += [f"{mov.empleado_no} ({c})" for c in cambios]
                continue
        salida.no_exportables.append({"movimiento_id": str(mov.id),
                                      "empleado_no": mov.empleado_no, "motivo": razon})
    if not lineas:
        raise FiscalAgentError(
            "No hay movimientos exportables de ese tipo. "
            + "; ".join(f"{x['empleado_no']}: {x['motivo']}" for x in salida.no_exportables),
            status_code=422)
    control, _ = L.escribir_registro(L.CIFRAS_CONTROL, {
        "asteriscos": "*" * 13, "total_registros": str(len(lineas)), "guia": guia,
        "identificador": L.IDENTIFICADOR_FORMATO}, L.LARGO_IDSE)
    nombre = f"IDSE_{tipo}_{cliente.clave}_{date.today():%Y%m%d}.txt"
    salida.lote = _guardar_lote(db, cliente, f"idse_{tipo}", nombre, [*lineas, control], uid)
    for mov in incluidos:
        mov.estado, mov.lote_id = "generado", salida.lote.id
    db.flush()
    return salida


def _tramos(db: Session, cliente: Cliente) -> dict[str, tuple[TramoSBC, ...]]:
    por_empleado: dict[str, list[TramoSBC]] = {}
    for h in historial_de(db, cliente):
        por_empleado.setdefault(h.empleado_no, []).append(TramoSBC(h.fecha, h.sbc))
    return {k: tuple(v) for k, v in por_empleado.items()}


def sbc_al(
    tramos: dict[str, tuple[TramoSBC, ...]], f: EmpleadoCarteraSchema, dia: date
) -> Decimal:
    """SBC vigente según el historial; sin historial, el de la ficha."""
    return sbc_vigente(tramos.get(f.empleado_no, ()), dia) or f.salario_diario_integrado


def generar_sua_trabajadores(db: Session, cliente: Cliente, uid: str, al: date) -> Generado:
    """Trabajadores de sueldos vigentes en `al`, para importarlos al SUA."""
    rp = str((cliente.datos or {}).get("registro_patronal") or "").strip().upper()
    L.partir_registro_patronal(rp)
    tramos = _tramos(db, cliente)
    salida = Generado(lote=None)  # type: ignore[arg-type]
    lineas = []
    for f in srv.fichas_del_cliente(db, cliente)[0]:
        if f.tipo_regimen != "02" or not f.fecha_alta or f.fecha_alta > al or (
                f.fecha_baja and f.fecha_baja < al):
            continue
        falta = faltantes(f, "sua") + ([] if f.rfc else ["el RFC"])
        nombre = f"{f.apellido_paterno}${f.apellido_materno}${f.nombres}".upper()
        if falta:
            salida.no_exportables.append({"empleado_no": f.empleado_no,
                                          "motivo": "falta " + ", ".join(falta)})
            continue
        try:
            linea, cambios = L.escribir_registro(L.SUA_TRABAJADOR, {
                "registro_patronal": rp, "nss": f.nss, "rfc": f.rfc, "curp": f.curp,
                "nombre": nombre, "tipo_trabajador": f.tipo_trabajador, "jornada": f.jornada,
                "fecha_alta": L.fecha_ddmmaaaa(f.fecha_alta),
                "sdi": L.importe_implicito(sbc_al(tramos, f, al), 5),
            }, L.LARGO_SUA_TRABAJADOR)
        except FiscalValidationError as e:
            salida.no_exportables.append({"empleado_no": f.empleado_no, "motivo": str(e)})
            continue
        lineas.append(linea)
        salida.transliterados += [f"{f.empleado_no} ({c})" for c in cambios]
    if not lineas:
        raise FiscalAgentError("No hay trabajadores exportables al SUA.", status_code=422)
    nombre = f"SUA_TRABAJADORES_{cliente.clave}_{al:%Y%m%d}.txt"
    salida.lote = _guardar_lote(db, cliente, "sua_trabajadores", nombre, lineas, uid)
    return salida


def generar_sua_movimientos(
    db: Session, cliente: Cliente, uid: str, desde: date, hasta: date
) -> Generado:
    """Movimientos afiliatorios (02, 07, 08) con fecha en el rango, para importarlos al SUA."""
    rp = str((cliente.datos or {}).get("registro_patronal") or "").strip().upper()
    L.partir_registro_patronal(rp)
    fichas = {f.empleado_no: f for f in srv.fichas_del_cliente(db, cliente)[0]}
    salida = Generado(lote=None)  # type: ignore[arg-type]
    lineas = []
    movimientos = db.scalars(select(MovimientoImss).where(
        MovimientoImss.cliente_id == cliente.id, MovimientoImss.fecha >= desde,
        MovimientoImss.fecha <= hasta, MovimientoImss.estado != "cancelado",
    ).order_by(MovimientoImss.fecha, MovimientoImss.id))
    for mov in movimientos:
        f = fichas.get(mov.empleado_no)
        if f is None or len(f.nss) != 11:
            salida.no_exportables.append({"empleado_no": mov.empleado_no,
                                          "motivo": "falta el NSS (11 dígitos)"})
            continue
        linea, _ = L.escribir_registro(L.SUA_MOVIMIENTO, {
            "registro_patronal": rp, "nss": f.nss, "tipo_movimiento": mov.tipo,
            "fecha_movimiento": L.fecha_ddmmaaaa(mov.fecha),
            "sdi": L.importe_implicito(mov.sbc or Decimal("0"), 5),
        }, L.LARGO_SUA_MOVIMIENTO)
        lineas.append(linea)
    if not lineas:
        raise FiscalAgentError("No hay movimientos en ese rango para el SUA.", status_code=422)
    nombre = f"SUA_MOVIMIENTOS_{cliente.clave}_{desde:%Y%m%d}_{hasta:%Y%m%d}.txt"
    salida.lote = _guardar_lote(db, cliente, "sua_movimientos", nombre, lineas, uid)
    return salida


def marcar(
    db: Session, cliente: Cliente, ids: list[int], estado: str, acuse: str = ""
) -> list[MovimientoImss]:
    """generado → enviado → acuse; o cancelar uno que no se ha enviado."""
    from app.db.base import ahora

    permitidos = {"enviado": ("generado", "pendiente"), "acuse": ("enviado", "generado"),
                  "cancelado": ("pendiente", "generado")}
    if estado not in permitidos:
        raise FiscalAgentError(f"Estado inválido: {estado!r}.", status_code=422)
    if estado == "acuse" and not acuse.strip():
        raise FiscalAgentError("Captura el folio o lote del acuse del IMSS.", status_code=422)
    movs = list(db.scalars(select(MovimientoImss).where(
        MovimientoImss.cliente_id == cliente.id, MovimientoImss.id.in_(ids))))
    if len(movs) != len(set(ids)):
        raise FiscalAgentError("Algún movimiento no existe en este cliente.", status_code=404)
    for m in movs:
        if m.estado not in permitidos[estado]:
            raise FiscalAgentError(
                f"El movimiento {m.id} está {m.estado}: no puede pasar a {estado}.", 409)
        m.estado = estado
        if estado == "enviado":
            m.enviado_en = ahora()
        if acuse:
            m.acuse = acuse.strip()
    db.flush()
    return movs


def movimiento_json(m: MovimientoImss, f: EmpleadoCarteraSchema | None) -> dict[str, Any]:
    return {
        "id": m.id, "empleado_no": m.empleado_no, "nombre": f.nombre if f else "",
        "tipo": m.tipo, "fecha": m.fecha.isoformat(),
        "sbc": str(m.sbc) if m.sbc is not None else None, "tipo_salario": m.tipo_salario,
        "causa_baja": m.causa_baja, "estado": m.estado, "lote_id": m.lote_id,
        "acuse": m.acuse, "origen": m.origen,
    }
