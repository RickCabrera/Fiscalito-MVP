"""
Servicio de nómina del despacho (P4): plantilla desde la cartera SQL e historial.

Aquí vive lo que toca la base; el cálculo es de `app/nomina_engine/`. La tenencia
llega resuelta: toda función recibe un `Cliente` que ya pasó por `cliente_o_404`.

P4-01 — LA PLANTILLA LA PONE EL BACKEND
---------------------------------------
`plantilla_del_cliente` lee los empleados de `app/almacen_cartera.py`. Lo que el
navegador mande como `empleados` se ignora: afirmar un cliente y calcular otro
ya no cabe en un JSON (R-08).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import almacen_cartera as almacen
from app.constants import (
    ZonaSalarioMinimo,
    salario_minimo_vigente,
    uma_mensual_vigente,
    uma_vigente,
)
from app.exceptions import FiscalAgentError
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nucleo import Cliente
from app.nomina_engine.criterios import CriteriosNomina, criterios_de
from app.nomina_engine.periodo_completo import EmpleadoNomina
from app.nomina_engine.subsidio import porcentaje_subsidio_vigente, tope_ingreso_subsidio
from app.nomina_engine.tablas_isr_periodicas import (
    TARIFAS_DERIVADAS,
    tarifa_por_periodicidad,
)
from app.schemas.empleado import EmpleadoCarteraSchema

VERSION_MOTOR = "P4-2026.10"
CERO = Decimal("0.00")


def criterios_del_cliente(cliente: Cliente) -> CriteriosNomina:
    return criterios_de((cliente.datos or {}).get("criterios_nomina"))


def prima_riesgo_del_cliente(cliente: Cliente) -> Decimal:
    prima = (cliente.datos or {}).get("prima_riesgo")
    if prima in (None, ""):
        raise FiscalAgentError(
            f"El cliente {cliente.clave!r} no tiene prima de riesgo capturada.", status_code=422
        )
    return Decimal(str(prima))


def periodicidad_del_cliente(cliente: Cliente) -> str:
    return str((cliente.datos or {}).get("clave_periodicidad") or "04")


def fichas_del_cliente(
    db: Session, cliente: Cliente
) -> tuple[list[EmpleadoCarteraSchema], list[str]]:
    """Empleados legibles de la cartera y los `empleado_no` que no pasan validación."""
    legibles, ilegibles = [], []
    for fila in almacen.empleados_de(db, cliente):
        try:
            legibles.append(
                EmpleadoCarteraSchema(**{**(fila.datos or {}), "empleado_no": fila.empleado_no})
            )
        except ValidationError:
            ilegibles.append(fila.empleado_no)
    return legibles, ilegibles


def a_empleado_nomina(f: EmpleadoCarteraSchema) -> EmpleadoNomina:
    return EmpleadoNomina(
        empleado_no=f.empleado_no,
        nombre=f.nombre,
        salario_diario=f.salario_diario,
        salario_diario_integrado=f.salario_diario_integrado,
        zona=f.zona,
        fecha_alta=f.fecha_alta,
        fecha_baja=f.fecha_baja,
        tipo_regimen=f.tipo_regimen,
        es_consejero=f.es_consejero,
        consejero_es_trabajador=f.consejero_es_trabajador,
    )


def plantilla_del_cliente(
    db: Session, cliente: Cliente, inicio: date, fin: date, asimilados: bool
) -> tuple[list[EmpleadoNomina], list[str]]:
    """Plantilla vigente en el periodo, del régimen pedido, y avisos de quién quedó fuera."""
    fichas, ilegibles = fichas_del_cliente(db, cliente)
    avisos = []
    if ilegibles:
        avisos.append(
            f"Empleados que no pasan la validación de la ficha y NO entran: {', '.join(ilegibles)}."
        )
    plantilla = []
    for f in fichas:
        e = a_empleado_nomina(f)
        if e.es_asimilado != asimilados:
            continue
        if (e.fecha_alta and e.fecha_alta > fin) or (e.fecha_baja and e.fecha_baja < inicio):
            continue
        plantilla.append(e)
    return plantilla, avisos


def parametros_vigentes(fecha: date, clave: str, zona: ZonaSalarioMinimo) -> dict[str, Any]:
    """Las magnitudes con las que se calculó, para que el periodo se pueda explicar después."""
    try:
        tarifa = [
            [
                str(r.limite_inferior),
                str(r.limite_superior),
                str(r.cuota_fija),
                str(r.tasa_excedente),
            ]
            for r in tarifa_por_periodicidad(clave, fecha)
        ]
    except FiscalAgentError:
        tarifa = []
    return {
        "version_motor": VERSION_MOTOR,
        "fecha_vigencia": fecha.isoformat(),
        "uma_diaria": str(uma_vigente(fecha)),
        "uma_mensual": str(uma_mensual_vigente(fecha)),
        "salario_minimo": str(salario_minimo_vigente(fecha, zona)),
        "subsidio_porcentaje": str(porcentaje_subsidio_vigente(fecha)),
        "subsidio_tope_mensual": str(tope_ingreso_subsidio(fecha)),
        "clave_periodicidad": clave,
        "tarifa_derivada": clave in TARIFAS_DERIVADAS,
        "tarifa_isr": tarifa,
        "fuente_tarifa": "Anexo 8 RMF 2026, DOF 28-12-2025 (Art. 96 LISR)",
    }


def _dec(v: Any) -> Decimal:
    return Decimal(str(v or "0"))


def guardar_periodo(
    db: Session,
    cliente: Cliente,
    despacho_id: str,
    uid: str,
    *,
    tipo: str,
    clave: str,
    inicio: date,
    fin: date,
    fecha_pago: date,
    criterios: dict[str, Any],
    parametros: dict[str, Any],
    entrada: dict[str, Any],
    resultado: dict[str, Any],
    recibos: list[dict[str, Any]],
) -> NominaPeriodo:
    """
    Guarda (o recalcula) el periodo. Uno por cliente + tipo + fechas.

    Un periodo `cerrada` o `timbrada` no se recalcula: 409.
    """
    existente = db.scalar(
        select(NominaPeriodo).where(
            NominaPeriodo.cliente_id == cliente.id,
            NominaPeriodo.tipo == tipo,
            NominaPeriodo.inicio == inicio,
            NominaPeriodo.fin == fin,
        )
    )
    if existente is not None and existente.estado in ("cerrada", "timbrada"):
        raise FiscalAgentError(
            f"El periodo {inicio} a {fin} ({tipo}) está {existente.estado}: no se recalcula.",
            status_code=409,
        )
    periodo = existente or NominaPeriodo(
        cliente_id=cliente.id, despacho_id=despacho_id, tipo=tipo, inicio=inicio, fin=fin
    )
    if existente is not None:
        for r in db.scalars(select(ReciboNomina).where(ReciboNomina.periodo_id == existente.id)):
            db.delete(r)
    periodo.periodicidad = clave
    periodo.fecha_pago = fecha_pago
    periodo.estado = "calculada"
    periodo.criterios, periodo.parametros = criterios, parametros
    periodo.entrada, periodo.resultado = entrada, resultado
    periodo.calculado_por = uid
    periodo.empleados = len(recibos)
    periodo.total_percepciones = sum(
        (_dec(r.get("total_percepciones")) for r in recibos), start=CERO
    )
    periodo.total_deducciones = sum((_dec(r.get("total_deducciones")) for r in recibos), start=CERO)
    periodo.total_isr = sum((_dec(r.get("isr")) for r in recibos), start=CERO)
    periodo.total_neto = sum((_dec(r.get("neto")) for r in recibos), start=CERO)
    db.add(periodo)
    db.flush()
    for r in recibos:
        db.add(
            ReciboNomina(
                periodo_id=periodo.id,
                empleado_no=r["empleado_no"],
                nombre=r.get("nombre", ""),
                percepciones=r.get("percepciones", []),
                deducciones=r.get("deducciones", []),
                otros_pagos=r.get("otros_pagos", []),
                total_percepciones=_dec(r.get("total_percepciones")),
                total_deducciones=_dec(r.get("total_deducciones")),
                isr=_dec(r.get("isr")),
                subsidio=_dec(r.get("subsidio")),
                cuota_obrera=_dec(r.get("cuota_obrera")),
                neto=_dec(r.get("neto")),
            )
        )
    db.flush()
    return periodo


def periodo_o_404(db: Session, cliente: Cliente, periodo_id: int) -> NominaPeriodo:
    """El periodo de ESE cliente, o 404 (nunca 403)."""
    periodo = db.scalar(
        select(NominaPeriodo).where(
            NominaPeriodo.id == periodo_id, NominaPeriodo.cliente_id == cliente.id
        )
    )
    if periodo is None:
        raise FiscalAgentError(
            f"No existe el periodo {periodo_id} de este cliente.", status_code=404
        )
    return periodo


def historial(db: Session, cliente: Cliente, tipo: str | None = None) -> list[NominaPeriodo]:
    consulta = select(NominaPeriodo).where(NominaPeriodo.cliente_id == cliente.id)
    if tipo:
        consulta = consulta.where(NominaPeriodo.tipo == tipo)
    return list(db.scalars(consulta.order_by(NominaPeriodo.inicio.desc(), NominaPeriodo.id.desc())))


def recibos_de(db: Session, periodo: NominaPeriodo) -> list[ReciboNomina]:
    return list(db.scalars(select(ReciboNomina).where(ReciboNomina.periodo_id == periodo.id)))


def resumen(p: NominaPeriodo) -> dict[str, Any]:
    return {
        "id": p.id,
        "tipo": p.tipo,
        "periodicidad": p.periodicidad,
        "inicio": p.inicio,
        "fin": p.fin,
        "fecha_pago": p.fecha_pago,
        "estado": p.estado,
        "empleados": p.empleados,
        "total_percepciones": p.total_percepciones,
        "total_deducciones": p.total_deducciones,
        "total_isr": p.total_isr,
        "total_neto": p.total_neto,
    }
