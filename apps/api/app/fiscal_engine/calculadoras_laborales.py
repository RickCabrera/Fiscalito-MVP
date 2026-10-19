"""
Aguinaldo, PTU y finiquito — versión mínima para las calculadoras (P3-08).

P4 (nómina completa) es dueña de estos cálculos y REEMPLAZA este módulo cuando cree sus
funciones en `app/nomina_engine/`. Hasta entonces la calculadora usa esto, que reusa el motor
de nómina para lo que ya existe (exenciones `isr_nomina.exentar`, tarifa `isr_periodo`).

FUENTES
-------
- Aguinaldo: Art. 87 LFT — "quince días de salario, por lo menos"; proporcional al tiempo
  trabajado.
- PTU: Art. 123 LFT — la utilidad repartible "se dividirá en dos partes iguales": una por días
  trabajados y otra por salarios. Art. 127 fr. IX — límite de "tres meses del salario del
  trabajador" o el promedio de la PTU de los últimos tres años, lo más favorable.
- Vacaciones: Arts. 76 (días), 79 (proporcionales al terminar la relación) y 80 (prima no
  menor de 25 %) LFT.
- Indemnización: Art. 50 fr. III LFT (tres meses de salario) para el despido injustificado.
- Prima de antigüedad: Art. 162 LFT (12 días por año; tope de salario Arts. 485-486: doble del
  salario mínimo); en renuncia sólo con 15 años o más.
- ISR: exenciones del Art. 93 fr. XIV (aguinaldo 30, PTU 15, prima vacacional 15 UMA) vía
  `isr_nomina.exentar`, y fr. XIII (separación: 90 veces por año de servicio; se leen en UMA
  como el resto del motor — decreto de desindexación DOF 27-01-2016). Indemnizaciones con la
  tasa del Art. 96 cuarto párrafo ("dividiendo el impuesto correspondiente al último sueldo
  mensual ordinario, entre dicho sueldo").

DECISIONES PROVISIONALES (FUENTE POR CONFIRMAR, para P4 y la contadora)
-----------------------------------------------------------------------
- ISR de aguinaldo/PTU/prima vacacional: diferencia de la tarifa mensual del Art. 96 entre
  (sueldo mensual + parte gravada) y el sueldo mensual. El procedimiento opcional del Art. 174
  RLISR NO se implementa (su texto no se pudo consultar).
- "Tres meses de salario" (Art. 127 fr. IX y Art. 50 fr. III) = 90 días de salario diario.
- Sueldo mensual ordinario = salario diario × 30.4 (`DIAS_MES_FISCAL`).
- Años de servicio para la prima de antigüedad y la exención: fracción mayor de seis meses
  cuenta como año (Art. 93 fr. XIII); para la prima se usa el proporcional exacto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import DIAS_MES_FISCAL, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.isr_nomina import ContextoExencion, Percepcion, exentar
from app.nomina_engine.tablas_isr_periodicas import isr_periodo
from app.nomina_engine.vacaciones import dias_vacaciones_de_ley
from app.redondeo import redondear

MENSUAL = "05"
DIAS_TRES_MESES = Decimal("90")


def isr_adicional_mensual(sueldo_mensual: Decimal, gravado: Decimal, fecha: date) -> Decimal:
    """ISR por sumar `gravado` al sueldo mensual (tarifa Art. 96, mensual)."""
    return isr_periodo(sueldo_mensual + gravado, MENSUAL, fecha) - isr_periodo(
        sueldo_mensual, MENSUAL, fecha
    )


def _partida(clave: str, nombre: str, importe: Decimal, fecha: date) -> dict[str, str]:
    g = exentar(Percepcion(clave, nombre, redondear(importe)), ContextoExencion(fecha=fecha))
    return {"clave": clave, "concepto": nombre, "importe": f"{g.importe:.2f}",
            "exento": f"{g.exento:.2f}", "gravado": f"{g.gravado:.2f}",
            "fundamento": g.fundamento}


def calcular_aguinaldo(
    salario_diario: Decimal, dias_aguinaldo: int, dias_trabajados: int, fecha_pago: date
) -> dict[str, object]:
    """Aguinaldo (Art. 87 LFT) proporcional y su ISR."""
    if dias_aguinaldo < 15:
        raise FiscalValidationError("El aguinaldo de ley es de 15 días por lo menos (Art. 87).")
    dias = Decimal(dias_aguinaldo) * Decimal(min(dias_trabajados, 365)) / Decimal("365")
    importe = redondear(salario_diario * dias)
    partida = _partida("002", "Aguinaldo", importe, fecha_pago)
    sueldo = redondear(salario_diario * DIAS_MES_FISCAL)
    isr = isr_adicional_mensual(sueldo, Decimal(partida["gravado"]), fecha_pago)
    return {"dias": str(redondear(dias)), "importe": f"{importe:.2f}", "partidas": [partida],
            "sueldo_mensual": f"{sueldo:.2f}", "isr": f"{isr:.2f}",
            "neto": f"{importe - isr:.2f}",
            "fundamento": "Art. 87 LFT; Art. 93 fr. XIV y 96 LISR."}


def calcular_ptu(
    utilidad_repartible: Decimal, dias_trabajador: int, salario_trabajador: Decimal,
    total_dias: int, total_salarios: Decimal, salario_diario: Decimal,
    promedio_3_anios: Decimal, fecha_pago: date,
) -> dict[str, object]:
    """PTU de un trabajador (Arts. 123 y 127 LFT) y su ISR."""
    mitad = utilidad_repartible / 2
    por_dias = redondear(mitad * Decimal(dias_trabajador) / Decimal(total_dias))
    por_salario = redondear(mitad * salario_trabajador / total_salarios)
    calculada = por_dias + por_salario
    tope = max(redondear(salario_diario * DIAS_TRES_MESES), redondear(promedio_3_anios))
    importe = min(calculada, tope)
    partida = _partida("003", "PTU", importe, fecha_pago)
    sueldo = redondear(salario_diario * DIAS_MES_FISCAL)
    isr = isr_adicional_mensual(sueldo, Decimal(partida["gravado"]), fecha_pago)
    return {"por_dias": f"{por_dias:.2f}", "por_salario": f"{por_salario:.2f}",
            "calculada": f"{calculada:.2f}", "tope": f"{tope:.2f}",
            "topada": calculada > tope, "importe": f"{importe:.2f}", "partidas": [partida],
            "isr": f"{isr:.2f}", "neto": f"{importe - isr:.2f}",
            "fundamento": "Arts. 123 y 127 fr. IX LFT; Art. 93 fr. XIV y 96 LISR."}


def _anios(ingreso: date, baja: date) -> Decimal:
    return Decimal((baja - ingreso).days + 1) / Decimal("365")


def calcular_finiquito(
    salario_diario: Decimal, fecha_ingreso: date, fecha_baja: date, dias_aguinaldo: int,
    prima_vacacional: Decimal, dias_vacaciones_pendientes: Decimal,
    dias_pendientes_de_pago: Decimal, tipo: str, zona: str,
) -> dict[str, object]:
    """Finiquito (renuncia) o liquidación (despido injustificado) con su ISR."""
    if fecha_baja < fecha_ingreso:
        raise FiscalValidationError("La fecha de baja es anterior a la de ingreso.")
    anios = _anios(fecha_ingreso, fecha_baja)
    inicio_anio = max(fecha_ingreso, date(fecha_baja.year, 1, 1))
    dias_anio = (fecha_baja - inicio_anio).days + 1
    agui = redondear(salario_diario * Decimal(dias_aguinaldo) * Decimal(dias_anio) / 365)
    # Vacaciones del año en curso proporcionales (Art. 79) + las pendientes capturadas.
    completos = int(anios)
    dias_vac_anio = Decimal(dias_vacaciones_de_ley(completos + 1)) * (anios - completos)
    dias_vac = redondear(dias_vac_anio + dias_vacaciones_pendientes)
    vac = redondear(salario_diario * dias_vac)
    prima_v = redondear(vac * prima_vacacional)
    sueldo_pend = redondear(salario_diario * dias_pendientes_de_pago)
    partidas = [
        _partida("001", "Salarios pendientes", sueldo_pend, fecha_baja),
        _partida("002", "Aguinaldo proporcional", agui, fecha_baja),
        _partida("001", "Vacaciones (Art. 79 LFT)", vac, fecha_baja),
        _partida("021", "Prima vacacional", prima_v, fecha_baja),
    ]
    separacion = Decimal("0")
    sep_partidas: list[dict[str, str]] = []
    tope_sal = salario_minimo_vigente(fecha_baja, zona) * 2
    if tipo == "despido_injustificado" or anios >= 15:
        prima_ant = redondear(min(salario_diario, tope_sal) * 12 * anios)
        sep_partidas.append({"concepto": "Prima de antigüedad (Art. 162 LFT)",
                             "importe": f"{prima_ant:.2f}"})
        separacion += prima_ant
    if tipo == "despido_injustificado":
        indem = redondear(salario_diario * DIAS_TRES_MESES)
        sep_partidas.append({"concepto": "Indemnización 3 meses (Art. 50 fr. III LFT)",
                             "importe": f"{indem:.2f}"})
        separacion += indem
    anios_exencion = int(anios) + (1 if anios - int(anios) > Decimal("0.5") else 0)
    exento_sep = min(separacion, redondear(uma_vigente(fecha_baja) * 90 * anios_exencion))
    gravado_sep = separacion - exento_sep
    sueldo = redondear(salario_diario * DIAS_MES_FISCAL)
    gravado_ordinario = sum((Decimal(p["gravado"]) for p in partidas), Decimal("0"))
    isr_ordinario = isr_adicional_mensual(sueldo, gravado_ordinario, fecha_baja)
    if gravado_sep > 0 and gravado_sep >= sueldo:
        tasa = isr_periodo(sueldo, MENSUAL, fecha_baja) / sueldo
        isr_sep = redondear(gravado_sep * tasa)
    else:
        isr_sep = isr_adicional_mensual(sueldo, gravado_sep, fecha_baja)
    bruto = sum((Decimal(p["importe"]) for p in partidas), Decimal("0")) + separacion
    isr = isr_ordinario + isr_sep
    return {
        "anios_servicio": str(redondear(anios)), "dias_vacaciones": str(dias_vac),
        "partidas": partidas, "separacion": sep_partidas,
        "separacion_exento": f"{exento_sep:.2f}", "separacion_gravado": f"{gravado_sep:.2f}",
        "isr_ordinario": f"{isr_ordinario:.2f}", "isr_separacion": f"{isr_sep:.2f}",
        "total_bruto": f"{bruto:.2f}", "isr": f"{isr:.2f}", "neto": f"{bruto - isr:.2f}",
        "fundamento": "Arts. 50, 76, 79, 80, 87, 162, 485-486 LFT; Arts. 93 fr. XIII y XIV, "
                      "95 y 96 LISR. Versión mínima: P4 la reemplaza.",
    }
