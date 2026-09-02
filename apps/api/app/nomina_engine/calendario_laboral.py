"""
Catálogo de obligaciones patronales de un ejercicio (F1-06, entregado
parcialmente por E-07).

Qué debe enterar, presentar o pagar un PATRÓN, y cuándo. **Produce FECHAS, no
importes**: los porcentajes de cada ramo viven en `cuotas.py`.

Las reglas de plazo —cinco, y se ven iguales sin serlo— están en
`plazos_patronales.py`. La doctrina completa, con citas y con lo que este módulo
deliberadamente NO emite (el ISN), está en
`knowledge_base/nomina/25_calendario_laboral_2026.md` §5, que es también la
fuente de la tabla de 2026 contra la que se contrasta el test.

NO ES, Y NO DEBE SER, EL CALENDARIO DEL SAT
-------------------------------------------
`fiscal_engine/calendario.py` genera el del CONTRIBUYENTE (día 17 corrido por el
sexto dígito del RFC). `dias_habiles.py` advierte que los dos **no deben
fusionarse**, y este módulo tampoco lo llama: su `_fecha_limite_dia_17()` con
`dias_extra=0` devuelve el día 17 crudo, domingos incluidos. Ese defecto es
**preexistente y fuera del alcance de E-07** (anotado en el backlog).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.exceptions import FiscalValidationError
from app.nomina_engine.avisos import fecha_limite_aviso_variable
from app.nomina_engine.dias_habiles import es_habil
from app.nomina_engine.plazos_patronales import (
    Personalidad,
    RegimenDePlazo,
    fecha_limite_aguinaldo,
    fecha_limite_cuotas,
    fecha_limite_entero_isr,
    fecha_limite_prima_riesgo,
    fecha_limite_ptu,
)

# Rango de años admisible. No es una regla fiscal: es la barrera contra un
# `anio` absurdo que produciría un calendario sin sentido.
ANIO_MINIMO = 2000
ANIO_MAXIMO = 2100

NOTA_SALARIO_VARIABLE = (
    "El modelo de cliente no registra el tipo de salario de sus trabajadores. Si el patrón "
    "tiene trabajadores de salario variable o mixto, esta obligación es firme."
)
NOTA_PERSONALIDAD = (
    "El modelo de cliente no registra la personalidad jurídica del patrón. Sólo una de las dos "
    "fechas de PTU le aplica."
)
NOTA_PRIMA_RT = (
    "No se aplica la prórroga del Art. 3 RACERF: correr la fecha hacia adelante es la "
    "dirección permisiva. Decisión provisional, ver docs/decisiones-nomina.md §D23."
)

_RAMOS_MENSUALES = "Riesgos de Trabajo, Enfermedades y Maternidad, Invalidez y Vida, Guarderías"
_RAMOS_BIMESTRALES = "Retiro, Cesantía y Vejez, Infonavit"
_NOTA_ISR = (
    "Se rige por la regla del SAT, no por la del IMSS: el viernes es hábil. No se aplica el "
    "ajuste por sexto dígito del RFC, que sólo puede correr la fecha hacia adelante."
)

_NOMBRE_MES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
_NOMBRE_DIA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@dataclass(frozen=True)
class ObligacionPatronal:
    """
    Una obligación del patrón con su vencimiento y su fundamento.

    `condicional` es `True` cuando la obligación **puede no aplicarle** a este
    patrón y el modelo de datos no alcanza para saberlo. No significa "opcional":
    significa "verifícalo, porque aquí no consta". Siempre viaja con `nota`.
    """

    clave: str
    nombre: str
    descripcion: str
    fecha_limite: date
    periodicidad: str
    periodo_cubierto: str
    fundamento: str
    regimen_de_plazo: RegimenDePlazo
    condicional: bool = False
    nota: str = ""


def _nota_si_cae_inhabil(dia: date, sufijo: str = "") -> str:
    """
    Advertencia para las obligaciones que **no** se prorrogan.

    Una fecha fija de ley que cae en sábado se reporta tal cual —moverla sin
    norma que lo autorice sería inventarse un plazo—, pero callar que cae en
    inhábil deja al patrón planeando un trámite en un día en que no puede
    hacerlo. La nota **describe** el dato; nunca propone una segunda fecha.
    """
    if es_habil(dia):
        return sufijo
    base = f"El {dia.isoformat()} cae en {_NOMBRE_DIA[dia.weekday()]}."
    return f"{base} {sufijo}".strip()


def _mensuales(anio: int) -> list[ObligacionPatronal]:
    """Entero mensual del IMSS y entero del ISR retenido: mismo día 17, dos reglas."""
    obligaciones: list[ObligacionPatronal] = []
    for mes in range(1, 13):
        periodo = f"{_NOMBRE_MES[mes - 1]} {anio}"
        obligaciones.append(
            ObligacionPatronal(
                clave="imss_mensual",
                nombre=f"Cuotas IMSS de {periodo}",
                descripcion=f"Entero mensual: {_RAMOS_MENSUALES}.",
                fecha_limite=fecha_limite_cuotas(anio, mes),
                periodicidad="mensual",
                periodo_cubierto=periodo,
                fundamento="Art. 39 LSS",
                regimen_de_plazo=RegimenDePlazo.IMSS,
            )
        )
        obligaciones.append(
            ObligacionPatronal(
                clave="isr_retenido",
                nombre=f"Entero del ISR retenido de {periodo}",
                descripcion="ISR retenido a los trabajadores por sueldos y salarios.",
                fecha_limite=fecha_limite_entero_isr(anio, mes),
                periodicidad="mensual",
                periodo_cubierto=periodo,
                fundamento="LISR Art. 96; CFF Art. 12",
                regimen_de_plazo=RegimenDePlazo.SAT,
                nota=_NOTA_ISR,
            )
        )
    return obligaciones


def _bimestrales(anio: int, tiene_salario_variable: bool | None) -> list[ObligacionPatronal]:
    obligaciones: list[ObligacionPatronal] = []
    for bimestre in range(1, 7):
        primero = _NOMBRE_MES[2 * bimestre - 2]
        segundo = _NOMBRE_MES[2 * bimestre - 1]
        periodo = f"bimestre {bimestre} ({primero}-{segundo} {anio})"
        obligaciones.append(
            ObligacionPatronal(
                clave="imss_bimestral",
                nombre=f"Cuotas RCV e Infonavit del {periodo}",
                descripcion=f"Entero bimestral: {_RAMOS_BIMESTRALES}.",
                fecha_limite=fecha_limite_cuotas(anio, 2 * bimestre),
                periodicidad="bimestral",
                periodo_cubierto=periodo,
                fundamento="Art. 39 LSS; Ley del Infonavit Art. 35",
                regimen_de_plazo=RegimenDePlazo.IMSS,
            )
        )
        if tiene_salario_variable is False:
            continue
        # La obligación bimestral existe aunque el promedio no cambie: lo que se
        # presenta es la determinación del bimestre. Lo que no consta es si HAY
        # trabajadores de salario variable.
        desconocido = tiene_salario_variable is None
        obligaciones.append(
            ObligacionPatronal(
                clave="aviso_variables",
                nombre=f"Aviso de modificación de salario variable — {periodo}",
                descripcion="Determinación del promedio de la parte variable del SBC del "
                "bimestre, ante el IMSS.",
                fecha_limite=fecha_limite_aviso_variable(bimestre, anio),
                periodicidad="bimestral",
                periodo_cubierto=periodo,
                fundamento="Art. 34 fr. II LSS",
                regimen_de_plazo=RegimenDePlazo.IMSS_AVISO,
                condicional=desconocido,
                nota=NOTA_SALARIO_VARIABLE if desconocido else "",
            )
        )
    return obligaciones


def _anuales(anio: int, personalidad: Personalidad | None) -> list[ObligacionPatronal]:
    ejercicio_anterior = f"ejercicio {anio - 1}"
    prima = fecha_limite_prima_riesgo(anio)
    aguinaldo = fecha_limite_aguinaldo(anio)

    obligaciones = [
        ObligacionPatronal(
            clave="prima_rt",
            nombre="Declaración Anual de Prima de Riesgo de Trabajo",
            descripcion="Autodeterminación de la prima con la siniestralidad del ejercicio "
            "anterior, ante el IMSS.",
            fecha_limite=prima,
            periodicidad="anual",
            # Se presenta en febrero de `anio` pero REPORTA el ejercicio
            # anterior (Art. 74 LSS). Decir "anio" sería un dato falso.
            periodo_cubierto=ejercicio_anterior,
            fundamento="Art. 74 LSS; Art. 32 RACERF",
            regimen_de_plazo=RegimenDePlazo.IMSS_SIN_PRORROGA,
            nota=_nota_si_cae_inhabil(prima, NOTA_PRIMA_RT),
        ),
        ObligacionPatronal(
            clave="aguinaldo",
            nombre="Pago del aguinaldo",
            descripcion="Al menos quince días de salario, antes del día veinte de diciembre.",
            fecha_limite=aguinaldo,
            periodicidad="anual",
            # El aguinaldo sí es del propio ejercicio, a diferencia de la prima
            # de RT y del PTU.
            periodo_cubierto=f"ejercicio {anio}",
            fundamento="LFT Art. 87",
            regimen_de_plazo=RegimenDePlazo.LFT,
            nota=_nota_si_cae_inhabil(aguinaldo),
        ),
    ]

    for cual in (Personalidad.MORAL, Personalidad.FISICA):
        if personalidad is not None and personalidad is not cual:
            continue
        desconocida = personalidad is None
        fecha = fecha_limite_ptu(anio, cual)
        etiqueta = "persona moral" if cual is Personalidad.MORAL else "persona física"
        obligaciones.append(
            ObligacionPatronal(
                clave=f"ptu_{cual.value}",
                nombre=f"Reparto de utilidades (PTU) — {etiqueta}",
                descripcion="Sesenta días siguientes a la fecha en que debe pagarse el "
                f"impuesto anual del {etiqueta} patrón.",
                fecha_limite=fecha,
                periodicidad="anual",
                periodo_cubierto=ejercicio_anterior,
                fundamento="LFT Art. 122",
                regimen_de_plazo=RegimenDePlazo.LFT,
                condicional=desconocida,
                nota=_nota_si_cae_inhabil(fecha, NOTA_PERSONALIDAD if desconocida else ""),
            )
        )
    return obligaciones


def calendario_patronal(
    anio_de_las_cuotas: int,
    *,
    tiene_salario_variable: bool | None = None,
    personalidad: Personalidad | None = None,
) -> tuple[ObligacionPatronal, ...]:
    """
    Obligaciones patronales del año, ordenadas por fecha límite.

    Args:
        anio_de_las_cuotas: año **del periodo que se reporta**, no del
            vencimiento. Las cuotas de diciembre de 2026 vencen en enero de 2027
            y **sí** están aquí; las de diciembre de 2025, que vencen en enero de
            2026, **no** — por eso el parámetro no se llama `anio`. Es la
            convención del doc 25 §2.

            Las anuales fijas (prima de RT, PTU, aguinaldo) son las que
            **vencen** dentro del año pedido; su `periodo_cubierto` dice qué
            ejercicio reportan, que para la prima de RT y el PTU es el anterior.
        tiene_salario_variable: `True` → el aviso del Art. 34 fr. II es firme;
            `False` → no se emite; `None` → se emite `condicional`, porque no
            consta. `None` no es "no tiene": es "no se sabe".
        personalidad: `None` → se emiten las **dos** fechas de PTU como
            condicionales, porque el plazo depende de algo que no consta.

    Raises:
        FiscalValidationError: si el año está fuera de `ANIO_MINIMO..ANIO_MAXIMO`.
    """
    if not ANIO_MINIMO <= anio_de_las_cuotas <= ANIO_MAXIMO:
        raise FiscalValidationError(
            f"Año fuera de rango: {anio_de_las_cuotas}. "
            f"Debe estar entre {ANIO_MINIMO} y {ANIO_MAXIMO}."
        )

    obligaciones = [
        *_mensuales(anio_de_las_cuotas),
        *_bimestrales(anio_de_las_cuotas, tiene_salario_variable),
        *_anuales(anio_de_las_cuotas, personalidad),
    ]
    # Orden estable: por fecha y, dentro del día, por clave y periodo. Sin el
    # desempate, dos corridas podrían devolver el mismo día en distinto orden y
    # la pantalla se reacomodaría sola entre refrescos.
    obligaciones.sort(key=lambda o: (o.fecha_limite, o.clave, o.periodo_cubierto))
    return tuple(obligaciones)
