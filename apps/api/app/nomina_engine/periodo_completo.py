"""
Nómina del periodo con criterios, variables, periodos parciales y asimilados. (P4-03/04/05)

`periodo.calcular_periodo` (D-06) sigue intacto: lo miden los tests del caso real
al centavo. Este módulo es el orquestador que usa la ruta autenticada y reutiliza
las mismas piezas del motor (`clamp_sbc`, `exentar`, `isr_retenido`,
`cuotas_empleado`); su aritmética propia es la de las partidas variables
(`variables.py`) y la de los días, que se declara abajo.

DÍAS (§D26 y §D27, configurables)
---------------------------------
- `dias_en_periodo`: días naturales del periodo en que hubo relación laboral
  (alta/baja a mitad de periodo). Son los días de cotización.
- Días pagados base: 15 si la periodicidad es quincenal, el periodo está completo
  y el criterio de febrero es `quince_siempre`; si no, `dias_en_periodo`.
- `dias_pagados = base − faltas − días de incapacidad` (las incapacidades las
  paga el IMSS como subsidio, LSS Arts. 58, 96 y 101).
- Periodo parcial: con `tarifa_proporcional` la tarifa es la del Art. 96 derivada
  a `dias_en_periodo` (`tarifa_por_dias`); con `tarifa_periodo`, la publicada.

ASIMILADOS (P4-04, Art. 94 LISR)
--------------------------------
Sin cuotas IMSS (no hay relación laboral, Art. 12 LSS), sin exenciones del
Art. 93 (son de trabajadores) y **sin subsidio**: el decreto lo otorga a los
ingresos del primer párrafo y la fr. I del Art. 94. ISR con la tarifa del Art. 96
de la periodicidad. Percepción 046 "Ingresos asimilados a salarios".
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.constants import DIAS_MES_FISCAL, uma_vigente
from app.exceptions import FiscalValidationError
from app.fiscal_engine.tablas_isr import TABLA_ISR_ANUAL
from app.nomina_engine import variables as var
from app.nomina_engine.ceav import es_trabajador_de_salario_minimo
from app.nomina_engine.criterios import CriteriosNomina
from app.nomina_engine.cuotas import DiasDelPeriodo, cuotas_empleado
from app.nomina_engine.duracion_periodo import validar_duracion_periodo
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.isr_nomina import (
    ContextoExencion,
    Percepcion,
    PercepcionGravada,
    exentar,
    isr_retenido,
)
from app.nomina_engine.jornada import tope_horas_extra_periodo, tope_horas_extra_semanal
from app.nomina_engine.periodo_completo_tipos import (  # noqa: F401 — re-exportados
    REGIMEN_SUELDOS,
    REGIMENES_ASIMILADOS,
    EmpleadoNomina,
    Incidencia,
    ReciboCompleto,
)
from app.nomina_engine.recibo import PartidaDeduccion, PartidaOtroPago, PartidaPercepcion, Recibo
from app.nomina_engine.reglas_periodo import aplicar_tope_diario, avisos_consejero
from app.nomina_engine.tablas_isr_periodicas import (
    TARIFAS_DERIVADAS,
    isr_con_tarifa,
    tarifa_por_dias,
    tarifa_por_periodicidad,
)
from app.redondeo import redondear

CERO = Decimal("0.00")
UMAS_PRIMA_VACACIONAL = 15  # Art. 93 fr. XIV LISR, por año calendario
# Tasa del último renglón de la tarifa anual del Art. 152 (Anexo 8 RMF 2026). Se lee de la
# tabla transcrita, no se reescribe.
TASA_MAXIMA_ART_152 = Decimal(str(TABLA_ISR_ANUAL[-1][3]))


def dias_con_relacion(e: EmpleadoNomina, inicio: date, fin: date) -> int:
    """Días naturales del periodo en que hubo relación laboral."""
    desde = max(inicio, e.fecha_alta) if e.fecha_alta else inicio
    hasta = min(fin, e.fecha_baja) if e.fecha_baja else fin
    return max((hasta - desde).days + 1, 0)


def _gravada(c: var.ConceptoVariable, ctx: ContextoExencion, asimilado: bool) -> PercepcionGravada:
    if asimilado or c.sin_exencion:
        return PercepcionGravada(
            c.clave,
            c.concepto,
            c.importe,
            c.importe,
            CERO,
            c.fundamento if c.sin_exencion else "Asimilado: sin exención (Art. 93)",
        )
    return exentar(Percepcion(c.clave, c.concepto, c.importe), ctx)


def calcular_recibo(
    e: EmpleadoNomina,
    inc: Incidencia,
    v: var.VariablesEmpleado | None,
    inicio: date,
    fin: date,
    fecha_pago: date,
    clave: str,
    prima_riesgo: Decimal,
    criterios: CriteriosNomina,
    dias_pagados_override: int | None = None,
    prima_vacacional_exenta_en_el_anio: Decimal = CERO,
) -> ReciboCompleto:
    """El recibo de un empleado. Ver el docstring del módulo."""
    v = v or var.VariablesEmpleado(e.empleado_no)
    avisos: list[str] = []
    en_periodo = dias_con_relacion(e, inicio, fin)
    if en_periodo == 0:
        raise FiscalValidationError(f"{e.empleado_no}: no tiene relación laboral en el periodo.")
    parcial = en_periodo < inc.dias_periodo
    base = (
        15
        if (clave == "04" and not parcial and criterios.febrero == "quince_siempre")
        else en_periodo
    )
    incapacidad = inc.dias_incapacidad + v.dias_incapacidad
    faltas = inc.faltas + v.faltas_adicionales
    pagados = (
        dias_pagados_override if dias_pagados_override is not None else base - faltas - incapacidad
    )
    if pagados < 0:
        raise FiscalValidationError(
            f"{e.empleado_no}: faltas e incapacidades exceden los días pagados."
        )
    ausentismo = inc.dias_ausentismo + v.faltas_adicionales
    sbc = clamp_sbc(e.salario_diario_integrado, fecha_pago, e.zona)
    minimo = (not e.es_asimilado) and es_trabajador_de_salario_minimo(sbc.valor, fecha_pago, e.zona)

    sueldo_clave, sueldo_nombre = (
        ("046", "ASIMILADOS A SALARIOS") if e.es_asimilado else ("001", "SUELDO")
    )
    conceptos = [
        var.ConceptoVariable(
            sueldo_clave,
            f"P{sueldo_clave}",
            sueldo_nombre,
            redondear(e.salario_diario * pagados),
            CERO,
            "Art. 82 LFT",
        )
    ]
    v, avisos_he = aplicar_tope_diario(v, inc.dias_periodo, fin, e.empleado_no)
    avisos.extend(avisos_he)
    # B2: Art. 66 LFT y Transitorio Cuarto (DOF 01-05-2026). Las dobles que pasan del
    # tope de la fecha se pagan triples (Art. 68) y van 100 % gravadas e integran.
    tope_dobles = redondear(tope_horas_extra_periodo(fin, inc.dias_periodo))
    if v.horas_dobles > tope_dobles:
        exceso = v.horas_dobles - tope_dobles
        avisos.append(
            f"{e.empleado_no}: {v.horas_dobles} horas dobles exceden el tope de {tope_dobles} "
            f"del periodo ({tope_horas_extra_semanal(fin)} por semana, Art. 66 LFT); las "
            f"{exceso} de más se pagan triples (Art. 68) y van 100 % gravadas."
        )
        v = replace(v, horas_dobles=tope_dobles, horas_triples=v.horas_triples + exceso)
    extra, efecto = var.percepciones_variables(v, e.salario_diario, sbc.valor, pagados)
    conceptos.extend(extra)
    ctx = ContextoExencion(
        fecha=fecha_pago,
        domingos_trabajados=max(v.domingos_trabajados, 1),
        es_trabajador_de_salario_minimo=minimo,
        semanas_del_periodo=Decimal(inc.dias_periodo) / 7,
    )
    gravadas = []
    for c in conceptos:
        if c.clave == "046":
            gravadas.append(
                PercepcionGravada("046", c.concepto, c.importe, c.importe, CERO, "Art. 94 LISR")
            )
        else:
            g = _gravada(c, ctx, e.es_asimilado)
            if g.clave == "021" and g.exento:
                previo = prima_vacacional_exenta_en_el_anio + v.prima_vacacional_exenta_previa
                g = var.con_exencion_anual(
                    g, previo, redondear(uma_vigente(fecha_pago) * UMAS_PRIMA_VACACIONAL)
                )
            gravadas.append(g)
    base_isr = sum((g.gravado for g in gravadas), start=CERO)

    if parcial and criterios.parcial == "tarifa_proporcional":
        tarifa, nombre_tarifa = (
            tarifa_por_dias(en_periodo, fecha_pago),
            f"proporcional a {en_periodo} días (derivada)",
        )
    else:
        tarifa = tarifa_por_periodicidad(clave, fecha_pago)
        nombre_tarifa = f"periodicidad {clave}" + (
            " (derivada, §D10)" if clave in TARIFAS_DERIVADAS else ""
        )
    if e.es_asimilado:
        causado = isr_con_tarifa(base_isr, tarifa)
        isr_ret, subsidio = causado, CERO
        avisos.extend(avisos_consejero(e))
        if e.aplica_retencion_minima_consejero:
            # O2 / P6-07: Art. 96 LISR, quinto párrafo: la retención a consejeros,
            # administradores, comisarios y gerentes generales no será menor a la tasa máxima
            # del Art. 152 sobre el excedente del límite inferior (el primero es $0.01: todo
            # el monto), salvo que además haya relación de trabajo con el retenedor.
            minima = redondear(base_isr * TASA_MAXIMA_ART_152)
            if minima > isr_ret:
                isr_ret = causado = minima
                avisos.append(
                    f"{e.empleado_no}: consejero sin relación de trabajo: retención a la tasa "
                    f"máxima del Art. 152 ({TASA_MAXIMA_ART_152 * 100:.0f} %) por el Art. 96 "
                    "LISR, quinto párrafo."
                )
    else:
        r = isr_retenido(
            base_isr,
            clave,
            fecha_pago,
            redondear(sbc.valor * DIAS_MES_FISCAL),
            en_periodo,
            minimo,
            tarifa=tarifa,
        )
        causado, isr_ret, subsidio = r.causado, r.retenido, r.subsidio

    cuotas = None
    obrera = CERO
    if not e.es_asimilado:
        dias = DiasDelPeriodo(en_periodo, ausentismo, incapacidad)
        cuotas = cuotas_empleado(sbc, dias, fecha_pago, e.zona, prima_riesgo)
        obrera = cuotas.total_obrero

    percepciones = tuple(
        PartidaPercepcion(g.clave, c.clave_interna, g.descripcion, g.gravado, g.exento)
        for g, c in zip(gravadas, conceptos)
    )
    bruto = sum((p.importe for p in percepciones), start=CERO)
    ded: list[PartidaDeduccion] = []
    if isr_ret > 0:
        ded.append(PartidaDeduccion("002", "D001", "ISR", isr_ret))
    if obrera > 0:
        ded.append(PartidaDeduccion("001", "D002", "IMSS", obrera))
    cotizados = (
        cuotas.dias.dias_periodo - cuotas.dias.dias_ausentismo - cuotas.dias.dias_incapacidad
        if cuotas
        else None
    )
    capturadas, avisos_ded = var.descuentos_capturados(
        v, conceptos[0].importe, bruto, bruto - isr_ret - obrera, sbc.valor, cotizados, en_periodo
    )
    ded.extend(capturadas)
    avisos.extend(avisos_ded)
    otros = []
    if subsidio > 0:
        otros.append(PartidaOtroPago("002", "D100", "SUBSIDIO PARA EL EMPLEO", CERO, subsidio))
    if v.viaticos_comprobados:
        otros.append(PartidaOtroPago("003", "O003", "VIÁTICOS COMPROBADOS", v.viaticos_comprobados))
    total_ded = sum((d.importe for d in ded), start=CERO)
    if total_ded > bruto + sum((o.importe for o in otros), start=CERO):
        raise FiscalValidationError(f"{e.empleado_no}: las deducciones exceden las percepciones.")
    return ReciboCompleto(
        e.empleado_no,
        e.nombre,
        e.tipo_regimen,
        sbc.valor,
        sbc.piso_aplicado,
        sbc.tope_aplicado,
        minimo,
        inc.dias_periodo,
        en_periodo,
        pagados,
        ausentismo,
        incapacidad,
        parcial,
        nombre_tarifa,
        Recibo(percepciones, tuple(ded), tuple(otros)),
        cuotas,
        causado,
        subsidio,
        efecto.integrable,
        efecto.detalle,
        tuple(avisos),
    )


def validar_periodo(clave: str, incidencias: tuple[Incidencia, ...]) -> int:
    """Una sola duración natural y la guarda de O-03 (que se conserva)."""
    if not incidencias:
        raise FiscalValidationError("Se requieren incidencias del periodo.")
    duraciones = sorted({i.dias_periodo for i in incidencias})
    if len(duraciones) > 1:
        raise FiscalValidationError(
            f"Las incidencias traen periodos de distinta duración: {duraciones} días."
        )
    validar_duracion_periodo(clave, duraciones[0])
    return duraciones[0]
