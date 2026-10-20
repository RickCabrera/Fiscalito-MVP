"""
Modificación bimestral de la parte variable del SBC (Art. 30 fr. II y III, Art. 34 fr. II LSS).

Orquestador, no motor: el promedio lo hace `integracion.sbc_variable` (total de percepciones
variables integrables del bimestre ÷ días de salario devengado) y el redondeo es el del motor.

DE DÓNDE SALE CADA NÚMERO
-------------------------
- Percepciones variables integrables: `sbc_variable_integrable` de cada recibo de las nóminas
  ORDINARIAS CERRADAS (o timbradas) cuya fecha final cae en el bimestre. Es lo que ya calculó
  P4-05 por recibo; aquí sólo se suma.
- Días devengados: `dias_pagados` de esos mismos recibos.
- Parte fija: el `salario_diario_integrado` de la ficha para salario MIXTO (tipo 2); cero para
  salario VARIABLE puro (tipo 1). DECISIÓN PROVISIONAL: la ficha guarda el SBC fijo integrado
  (factor × salario, `POST /nomina/sbc`), no el SBC declarado; el declarado vive en el
  historial. Así el promedio de un bimestre no se acumula sobre el del anterior.
- Fecha de efecto: el día 1 del bimestre siguiente (Art. 30 fr. II: el promedio del bimestre
  anterior rige en el siguiente); el aviso se presenta en sus primeros 5 días hábiles (Art. 34
  fr. II).
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import nomina_servicio as srv
from app.exceptions import FiscalAgentError
from app.modelos.nomina import NominaPeriodo
from app.modelos.nucleo import Cliente
from app.nomina_engine.cuotas_mensuales import TramoSBC, meses_del_bimestre, sbc_vigente
from app.nomina_engine.integracion import sbc_variable
from app.nomina_imss.historial import historial_de, registrar_sbc
from app.redondeo import redondear

CERO = Decimal("0.00")
ESTADOS_CERRADOS = ("cerrada", "timbrada")


def periodos_cerrados(
    db: Session, cliente: Cliente, desde: date, hasta: date, tipos: tuple[str, ...] = ("ordinaria",)
) -> list[NominaPeriodo]:
    """Nóminas cerradas cuya fecha final cae en [desde, hasta]."""
    return list(db.scalars(select(NominaPeriodo).where(
        NominaPeriodo.cliente_id == cliente.id, NominaPeriodo.tipo.in_(tipos),
        NominaPeriodo.estado.in_(ESTADOS_CERRADOS), NominaPeriodo.fin >= desde,
        NominaPeriodo.fin <= hasta,
    ).order_by(NominaPeriodo.inicio)))


def _dec(v: Any) -> Decimal:
    return Decimal(str(v or "0"))


def inicio_bimestre_siguiente(ejercicio: int, bimestre: int) -> date:
    return date(ejercicio + 1, 1, 1) if bimestre == 6 else date(ejercicio, 2 * bimestre + 1, 1)


def calcular(
    db: Session, cliente: Cliente, ejercicio: int, bimestre: int, uid: str, aplicar: bool
) -> dict[str, Any]:
    """Nuevo SBC de cada trabajador variable o mixto; con `aplicar` registra historial y 07."""
    m1, m2 = meses_del_bimestre(bimestre)
    inicio = date(ejercicio, m1, 1)
    fin = date(ejercicio, m2, calendar.monthrange(ejercicio, m2)[1])
    efecto = inicio_bimestre_siguiente(ejercicio, bimestre)
    suma: dict[str, Decimal] = {}
    dias: dict[str, int] = {}
    for p in periodos_cerrados(db, cliente, inicio, fin):
        for r in (p.resultado or {}).get("recibos", []):
            no = r.get("empleado_no")
            suma[no] = suma.get(no, CERO) + _dec(r.get("sbc_variable_integrable"))
            dias[no] = dias.get(no, 0) + int(r.get("dias_pagados") or 0)
    tramos: dict[str, list[TramoSBC]] = {}
    for h in historial_de(db, cliente):
        tramos.setdefault(h.empleado_no, []).append(TramoSBC(h.fecha, h.sbc))
    filas, avisos = [], []
    for f in srv.fichas_del_cliente(db, cliente)[0]:
        if f.tipo_regimen != "02" or f.tipo_salario not in ("1", "2"):
            continue
        if f.fecha_baja and f.fecha_baja < efecto:
            continue
        if not dias.get(f.empleado_no):
            avisos.append(f"{f.empleado_no}: sin nóminas cerradas en el bimestre; no se promedia.")
            continue
        variable = sbc_variable(suma.get(f.empleado_no, CERO), dias[f.empleado_no])
        fijo = f.salario_diario_integrado if f.tipo_salario == "2" else CERO
        nuevo = redondear(fijo + variable)
        actual = sbc_vigente(tuple(tramos.get(f.empleado_no, ())), efecto)
        cambia = nuevo != actual and nuevo > 0
        fila = {
            "empleado_no": f.empleado_no, "nombre": f.nombre, "tipo_salario": f.tipo_salario,
            "percepciones_variables": str(suma.get(f.empleado_no, CERO)),
            "dias_devengados": dias[f.empleado_no], "parte_fija": str(fijo),
            "parte_variable": str(variable), "sbc_nuevo": str(nuevo),
            "sbc_actual": str(actual) if actual is not None else None,
            "fecha_efecto": efecto.isoformat(), "cambia": cambia, "movimiento_id": None,
        }
        if aplicar and cambia:
            _, mov = registrar_sbc(db, cliente, f, efecto, nuevo, tipo_salario=f.tipo_salario,
                                   motivo="bimestre_variable", uid=uid,
                                   nota=f"Bimestre {bimestre}/{ejercicio}")
            fila["movimiento_id"] = mov.id if mov else None
        filas.append(fila)
    if not filas and not avisos:
        raise FiscalAgentError(
            "No hay trabajadores de salario variable o mixto en la plantilla.", status_code=422)
    return {"ejercicio": ejercicio, "bimestre": bimestre, "fecha_efecto": efecto.isoformat(),
            "trabajadores": filas, "advertencias": avisos,
            "fundamento": "Arts. 30 fr. II y III, 34 fr. II LSS"}
