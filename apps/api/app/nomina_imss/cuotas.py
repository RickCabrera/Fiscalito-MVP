"""
Cuotas del mes (EMA) y del bimestre (EBA) de la plantilla de un cliente (P4-10).

Orquestador: lee la cartera, el historial de SBC y las nóminas CERRADAS; calcula cada
trabajador con `nomina_engine/cuotas_mensuales.cuotas_del_mes`, que a su vez usa el motor de
cuotas existente (`cuotas.cuotas_empleado`). No hay un porcentaje en este archivo.

AUSENCIAS
---------
Salen de los recibos (`dias_ausentismo`, `dias_incapacidad`) de las nóminas ORDINARIAS
cerradas o timbradas. DECISIÓN PROVISIONAL: un periodo que cruza de mes se asigna al mes de su
fecha final (las incidencias no traen fecha, sólo días). Con nóminas mensuales o quincenales
no hay cruce; con semanales se puede mover a lo más una semana de ausencias de mes.

SIN HISTORIAL DE SBC
--------------------
Un trabajador sin historial (cartera anterior a P4-09) se calcula con el SBC de su ficha desde
su alta, y la respuesta lo advierte: el SBC de la ficha es el de HOY, no necesariamente el que
se declaró en el periodo.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app import nomina_servicio as srv
from app.exceptions import FiscalAgentError, FiscalValidationError
from app.modelos.nucleo import Cliente
from app.nomina_engine.cuotas_mensuales import (
    TOPE_AUSENTISMO_MES,
    CuotaRamoMes,
    CuotasMes,
    TramoSBC,
    cuotas_del_mes,
    meses_del_bimestre,
    ramos_bimestrales,
)
from app.nomina_engine.tablas_imss import PeriodicidadCuota
from app.nomina_imss.bimestre_variable import periodos_cerrados
from app.nomina_imss.historial import historial_de

CERO = Decimal("0.00")


def ausencias_por_mes(
    db: Session, cliente: Cliente, ejercicio: int
) -> dict[tuple[str, int], tuple[int, int]]:
    """(empleado, mes) → (ausentismo, incapacidad), de las nóminas cerradas del año."""
    acumulado: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    for p in periodos_cerrados(db, cliente, date(ejercicio, 1, 1), date(ejercicio, 12, 31)):
        for r in (p.resultado or {}).get("recibos", []):
            celda = acumulado[(r.get("empleado_no"), p.fin.month)]
            celda[0] += int(r.get("dias_ausentismo") or 0)
            celda[1] += int(r.get("dias_incapacidad") or 0)
    return {k: (v[0], v[1]) for k, v in acumulado.items()}


def _ramos_json(ramos: tuple[CuotaRamoMes, ...]) -> dict[str, dict[str, str]]:
    return {r.clave: {"nombre": r.nombre, "patron": str(r.patron), "obrero": str(r.obrero),
                      "total": str(r.total)} for r in ramos}


def calcular(
    db: Session, cliente: Cliente, ejercicio: int, *, mes: int | None = None,
    bimestre: int | None = None, tope_ausentismo: int | None = TOPE_AUSENTISMO_MES,
) -> dict[str, Any]:
    """`mes` → cuotas mensuales (EMA); `bimestre` → RCV e Infonavit (EBA)."""
    if (mes is None) == (bimestre is None):
        raise FiscalAgentError("Pide un mes (EMA) o un bimestre (EBA), no los dos.", 422)
    tipo = "EMA" if mes is not None else "EBA"
    meses = (mes,) if mes is not None else meses_del_bimestre(bimestre or 0)
    prima = srv.prima_riesgo_del_cliente(cliente)
    ausencias = ausencias_por_mes(db, cliente, ejercicio)
    historial: dict[str, list[TramoSBC]] = defaultdict(list)
    for h in historial_de(db, cliente):
        historial[h.empleado_no].append(TramoSBC(h.fecha, h.sbc))
    filas, avisos = [], []
    totales: dict[str, Decimal] = defaultdict(lambda: CERO)
    for f in srv.fichas_del_cliente(db, cliente)[0]:
        if f.tipo_regimen != "02":
            continue
        tramos = tuple(historial.get(f.empleado_no, ()))
        if not tramos:
            if not f.fecha_alta:
                avisos.append(f"{f.empleado_no}: sin fecha de alta ni historial de SBC; no entra.")
                continue
            tramos = (TramoSBC(f.fecha_alta, f.salario_diario_integrado),)
            avisos.append(f"{f.empleado_no}: sin historial de SBC; se usa el SBC de la ficha "
                          f"({f.salario_diario_integrado}) desde su alta.")
        calculados: list[CuotasMes] = []
        for m in meses:
            aus, inc = ausencias.get((f.empleado_no, m), (0, 0))
            try:
                c = cuotas_del_mes(tramos, ejercicio, m, f.zona, prima, alta=f.fecha_alta,
                                   baja=f.fecha_baja, dias_ausentismo=aus, dias_incapacidad=inc,
                                   tope_ausentismo=tope_ausentismo)
            except FiscalValidationError as e:
                avisos.append(f"{f.empleado_no}: {e}")
                continue
            if c is not None:
                calculados.append(c)
                avisos += [f"{f.empleado_no}: {a}" for a in c.avisos]
        if not calculados:
            continue
        if tipo == "EMA":
            ramos = tuple(r for r in calculados[0].ramos
                          if r.periodicidad is PeriodicidadCuota.MENSUAL)
        else:
            ramos = ramos_bimestrales(tuple(calculados))
        total = sum((r.total for r in ramos), start=CERO)
        for r in ramos:
            totales[r.clave] += r.total
        filas.append({
            "empleado_no": f.empleado_no, "nss": f.nss, "nombre": f.nombre,
            "dias": sum(c.dias for c in calculados),
            "dias_ausentismo": sum(c.dias_ausentismo for c in calculados),
            "dias_incapacidad": sum(c.dias_incapacidad for c in calculados),
            "dias_cotizados": sum(c.dias_cotizados for c in calculados),
            "sbc": str(calculados[-1].sbc),
            "tramos": [{"desde": s.desde.isoformat(), "hasta": s.hasta.isoformat(),
                        "sbc": str(s.sbc), "dias": s.dias} for c in calculados
                       for s in c.segmentos],
            "absorbio_cuota_obrera": any(c.absorbio_cuota_obrera for c in calculados),
            "ramos": _ramos_json(ramos), "total": str(total),
        })
    gran_total = sum(totales.values(), start=CERO)
    return {
        "tipo": tipo, "ejercicio": ejercicio, "mes": mes, "bimestre": bimestre,
        "prima_riesgo": str(prima), "trabajadores": filas,
        "por_ramo": {k: str(v) for k, v in totales.items()}, "total": str(gran_total),
        "advertencias": avisos,
        "fundamento": "Arts. 25, 31, 39, 106, 107, 147, 168, 211 LSS; Art. 29 Ley del Infonavit",
    }
