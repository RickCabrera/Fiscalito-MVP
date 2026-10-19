"""
Vencimientos de obligaciones fiscales de un contribuyente (P3-10). Motor puro: no lee la base.

FUENTES
-------
- Pagos mensuales de ISR e IVA (provisionales o definitivos, incluidas retenciones): día 17
  del mes inmediato posterior (Arts. 14 y 106 LISR, 96 LISR retenciones, 5-D LIVA, 113-E LISR
  RESICO PF).
- Prórroga por sexto dígito numérico del RFC: Decreto que compila diversos beneficios
  fiscales y establece medidas de simplificación administrativa (DOF 26-dic-2013), art. 5.1:
  **sólo personas físicas**, que podrán presentar a más tardar el día 17 más 1 día hábil
  (sexto dígito 1 o 2), 2 (3 o 4), 3 (5 o 6), 4 (7 o 8) o 5 (9 o 0). Exceptuadas las personas
  físicas con actividades empresariales que dictaminen sus estados financieros (Arts. 32-A y
  52 CFF). Texto consultado en vLex ("Personas físicas. Mayo de 2025"), 2026-10-19.
- Día inhábil: si el último día del plazo es inhábil, se prorroga al siguiente hábil
  (Art. 12 CFF). Días inhábiles: sábados, domingos y los del Art. 12 primer párrafo
  (`actualizacion.dias_inhabiles_cff`). Los periodos vacacionales que el SAT declara en la
  RMF de cada año no están: el calendario puede quedar ANTES de la fecha legal, nunca después
  (dirección conservadora).
- Cómo se combinan: se parte del día 17, se suman los días hábiles de la prórroga (contados
  después del 17) y, si no hay prórroga, el 17 inhábil corre al siguiente hábil. Así el día 17
  inhábil queda corregido en los dos casos.
- DIOT: a más tardar el último día del mes inmediato posterior (regla 4.5.1 RMF; IMCP, Folio
  21/2024-2025 "Presentación de la DIOT en línea"). Personas físicas en RESICO y las de 612/606
  con ingresos del ejercicio anterior ≤ 4 millones están relevadas (regla 2.8.1.17 RMF 2026,
  `knowledge_base/09_diot.md`): para 612/606 se emite `condicional`.
- Contabilidad electrónica (balanza mensual, Anexo 24): # FUENTE POR CONFIRMAR: regla 2.8.1.7
  fr. II RMF — personas morales a más tardar el día 3 y personas físicas el día 5 del segundo
  mes posterior. Configurable con `DIA_BALANZA_PM` / `DIA_BALANZA_PF`.
- Anual: personas morales 31 de marzo (Art. 76 fr. V LISR); personas físicas 30 de abril
  (Art. 150 LISR).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.fiscal_engine.actualizacion import dias_inhabiles_cff, siguiente_dia_habil

DIA_BALANZA_PM = 3  # FUENTE POR CONFIRMAR: regla 2.8.1.7 fr. II RMF
DIA_BALANZA_PF = 5  # FUENTE POR CONFIRMAR: regla 2.8.1.7 fr. II RMF
DIAS_PRORROGA = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 0: 5}
MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
# Regímenes de personas morales (c_RegimenFiscal): 601 general, 603 no lucrativas, 620, 622,
# 623, 624, 626 (RESICO PM, Título VII Cap. XII LISR).
REGIMENES_MENSUALES = {"601", "603", "606", "612", "620", "621", "622", "623", "624", "625",
                       "626"}


def es_habil(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in dias_inhabiles_cff(dia.year)


def sexto_digito(rfc: str) -> int | None:
    """Sexto dígito NUMÉRICO del RFC (el último de la fecha): 'ABCD210199XY1' → 9."""
    digitos = [c for c in rfc if c.isdigit()]
    return int(digitos[5]) if len(digitos) >= 6 else None


def es_persona_fisica(rfc: str) -> bool:
    return len(rfc.strip()) == 13


def dias_prorroga(rfc: str, dictamina: bool = False) -> int:
    """Días hábiles que el decreto (art. 5.1) suma al día 17. 0 para morales y dictaminadas."""
    if not es_persona_fisica(rfc) or dictamina:
        return 0
    d = sexto_digito(rfc)
    return DIAS_PRORROGA[d] if d is not None else 0


def sumar_habiles(inicio: date, dias: int) -> date:
    actual, contados = inicio, 0
    while contados < dias:
        actual += timedelta(days=1)
        if es_habil(actual):
            contados += 1
    return actual


def fecha_dia_17(anio: int, mes: int, prorroga: int = 0) -> date:
    """Vencimiento del día 17 de (anio, mes) con la prórroga y la corrección por inhábil."""
    base = date(anio, mes, 17)
    return sumar_habiles(base, prorroga) if prorroga else siguiente_dia_habil(base)


def _siguiente(anio: int, mes: int, n: int = 1) -> tuple[int, int]:
    total = anio * 12 + (mes - 1) + n
    return total // 12, total % 12 + 1


def ultimo_dia(anio: int, mes: int) -> date:
    a, m = _siguiente(anio, mes)
    return date(a, m, 1) - timedelta(days=1)


@dataclass(frozen=True)
class Vencimiento:
    """Una obligación fiscal de un periodo con su fecha límite y su fundamento."""

    clave: str
    nombre: str
    tipo: str  # fiscal
    periodo: str  # "2026-03" | "2026"
    fecha_limite: date
    fundamento: str
    condicional: bool = False
    nota: str = ""


def vencimientos_fiscales(
    rfc: str, regimen: str, anio: int, *, dictamina: bool = False
) -> list[Vencimiento]:
    """Las obligaciones fiscales cuyo PERIODO es del año `anio` (diciembre vence en enero)."""
    rfc = rfc.strip().upper()
    pf = es_persona_fisica(rfc)
    prorroga = dias_prorroga(rfc, dictamina)
    nota_prorroga = (f"Incluye {prorroga} día(s) hábil(es) de prórroga por el sexto dígito del "
                     "RFC (Decreto DOF 26-12-2013, art. 5.1)." if prorroga else "")
    salida: list[Vencimiento] = []
    for mes in range(1, 13):
        a, m = _siguiente(anio, mes)
        periodo = f"{anio}-{mes:02d}"
        etiqueta = f"{MESES[mes]} {anio}"
        if regimen in REGIMENES_MENSUALES:
            salida.append(Vencimiento(
                f"mensual:{periodo}", f"Declaración mensual ISR e IVA de {etiqueta}", "fiscal",
                periodo, fecha_dia_17(a, m, prorroga),
                "Arts. 14/106 LISR, 5-D LIVA; Art. 12 CFF", nota=nota_prorroga))
        diot_aplica = (not pf and regimen in {"601", "603", "620", "622", "623", "624"}) or \
            regimen in {"612", "606"}
        if diot_aplica:
            salida.append(Vencimiento(
                f"diot:{periodo}", f"DIOT de {etiqueta}", "fiscal", periodo,
                siguiente_dia_habil(ultimo_dia(a, m)),
                "Art. 32 fr. VIII LIVA; regla 4.5.1 RMF; Art. 12 CFF",
                condicional=pf,
                nota="Relevada si los ingresos del ejercicio anterior no pasaron de 4 millones "
                     "(regla 2.8.1.17 RMF)." if pf else ""))
        if regimen in {"601", "603", "620", "622", "623", "624", "612", "606"}:
            a2, m2 = _siguiente(anio, mes, 2)
            dia = DIA_BALANZA_PF if pf else DIA_BALANZA_PM
            salida.append(Vencimiento(
                f"balanza:{periodo}", f"Contabilidad electrónica (balanza) de {etiqueta}",
                "fiscal", periodo, siguiente_dia_habil(date(a2, m2, dia)),
                "Art. 28 fr. IV CFF; regla 2.8.1.7 RMF (FUENTE POR CONFIRMAR)",
                condicional=pf,
                nota="Personas físicas: no aplica si registran en Mis cuentas." if pf else ""))
    # La anual aplica a todos; sueldos y RESICO PF, sólo en los supuestos de ley.
    supuestos = regimen in {"605", "626"} and pf
    salida.append(Vencimiento(
        f"anual:{anio}", f"Declaración anual {anio}", "fiscal", str(anio),
        siguiente_dia_habil(date(anio + 1, 4, 30) if pf else date(anio + 1, 3, 31)),
        "Art. 150 LISR" if pf else "Art. 76 fr. V LISR", condicional=supuestos,
        nota="Sueldos y RESICO PF: obligatoria sólo en los supuestos de ley." if supuestos
        else ""))
    return sorted(salida, key=lambda v: (v.fecha_limite, v.clave))
