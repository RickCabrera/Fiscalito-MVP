"""
Calendario de obligaciones patronales (F1-06, entregado parcialmente por E-07).

Genera las fechas límite de lo que un PATRÓN debe enterar, presentar o pagar en
un ejercicio. Fuente de las fechas y de cada fundamento:
`knowledge_base/nomina/25_calendario_laboral_2026.md`, que trae la tabla
publicada de 2026 contra la que se contrasta el test.

**Este módulo produce FECHAS, no importes.** Los porcentajes de cada ramo viven
en `cuotas.py` y las tablas en `tablas_imss.py`; aquí no se calcula un peso.

CUATRO REGLAS DE PLAZO QUE SE VEN IGUALES Y NO LO SON
-----------------------------------------------------
Cada obligación viaja con su `regimen_de_plazo` **como dato**, no como
comentario, porque `25_calendario_laboral_2026.md` §4 advierte que fusionarlas
en una sola vista *"sin distinguir su regla es un bug esperando*". Son:

| `regimen_de_plazo` | Regla | Fundamento |
|---|---|---|
| `imss` | vence en inhábil **o viernes** → siguiente hábil | Art. 3 RACERF |
| `imss_aviso` | **no** se prorroga nunca | Art. 3 RACERF, que excluye los avisos afiliatorios |
| `sat` | vence en inhábil → siguiente hábil (**sin** la regla del viernes) | CFF Art. 12 |
| `lft` | fecha fija de ley, sin prórroga para estas obligaciones | LFT Arts. 87 y 122 |

La diferencia **se ve** en 2026: las cuotas del IMSS de marzo vencen el
**20-abr** (viernes corrido al lunes) y el entero del ISR retenido de marzo el
**17-abr**, porque para el SAT el viernes es hábil. Igual en junio/julio. En
cambio los tres domingos y sábados (mayo, octubre y enero de 2027) coinciden,
porque ahí las dos reglas corren.

Sobre `lft`: la afirmación se limita a las obligaciones **sustantivas** de pago
de los Arts. 87 y 122. La LFT sí tiene cómputo de términos (Arts. 733-735),
pero es **procesal** y no gobierna estas fechas.

QUÉ NO EMITE ESTE MÓDULO, Y POR QUÉ
------------------------------------
**El ISN (Impuesto Sobre Nóminas).** No por §D8 —que decide no calcular su
IMPORTE, y no dice nada de la fecha— sino porque `knowledge_base/` **no tiene
ninguna fuente estatal**: ni el Código Financiero de Veracruz ni el de ninguna
otra entidad, y `despacho_demo.ClienteDespacho` tampoco registra en qué estado
está el patrón. Escribir "día 10 o 17 según la entidad" sería un valor legal sin
cita, que es justo lo que `CLAUDE.md` prohíbe.

NO ES, Y NO DEBE SER, EL CALENDARIO DEL SAT
-------------------------------------------
`fiscal_engine/calendario.py` genera el calendario del CONTRIBUYENTE (día 17
corrido por el sexto dígito del RFC). `dias_habiles.py` advierte que los dos
**no deben fusionarse**. Este módulo tampoco lo llama: su
`_fecha_limite_dia_17()` con `dias_extra=0` devuelve el día 17 crudo, domingos
incluidos, porque sólo sabe sumar días hábiles hacia adelante y nunca corrige el
día de partida. Ese defecto es **preexistente y queda fuera del alcance de
E-07** (anotado en el backlog para F1-07/S-03); aquí la regla del CFF se
implementa delegando en `dias_habiles.es_habil`.

ADVERTENCIA SOBRE "DÍA INHÁBIL", HEREDADA DE `dias_habiles.py`
--------------------------------------------------------------
Se usan los descansos obligatorios del **Art. 74 LFT**. Ni el acuerdo anual de
días inhábiles del IMSS ni el calendario de vacaciones generales del SAT están
en el repo. Contar de menos días inhábiles deja la fecha límite **antes** o
igual que la legal, que es la dirección conservadora; ver §D13.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from app.exceptions import FiscalValidationError
from app.nomina_engine.avisos import fecha_limite_aviso_variable
from app.nomina_engine.dias_habiles import es_habil

# Día de entero de cuotas (Art. 39 LSS) y de retenciones (LISR Art. 96).
DIA_DE_ENTERO = 17

_VIERNES = 4

# LFT Art. 122: el reparto va "dentro de los sesenta días siguientes a la fecha
# en que deba pagarse el impuesto anual". Las dos fechas del reparto se DERIVAN
# de aquí en vez de teclearse, para que el fundamento sea visible en el código.
DIAS_PARA_REPARTIR_PTU = 60
_ANUAL_MORAL = (3, 31)  # personas morales: marzo
_ANUAL_FISICA = (4, 30)  # personas físicas: abril

# Rango de años admisible. No es una regla fiscal: es la barrera contra un
# `anio` absurdo que produciría un calendario sin sentido.
ANIO_MINIMO = 2000
ANIO_MAXIMO = 2100


class RegimenDePlazo(str, Enum):
    """Qué regla de cómputo gobierna la fecha límite. Ver la tabla del módulo."""

    IMSS = "imss"
    IMSS_AVISO = "imss_aviso"
    SAT = "sat"
    LFT = "lft"


class Personalidad(str, Enum):
    """Personalidad jurídica del patrón. Decide el plazo del PTU (Art. 122 LFT)."""

    FISICA = "fisica"
    MORAL = "moral"


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


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def _ultimo_dia_del_mes(anio: int, mes: int) -> date:
    anio_sig, mes_sig = _mes_siguiente(anio, mes)
    return date(anio_sig, mes_sig, 1) - timedelta(days=1)


def _siguiente_habil(dia: date) -> date:
    while not es_habil(dia):
        dia += timedelta(days=1)
    return dia


def prorroga_racerf(dia: date) -> date:
    """
    Cómputo del plazo del IMSS (Art. 3 RACERF).

    Si el último día del plazo es **inhábil o viernes**, corre al siguiente día
    hábil. Que el viernes también corra es específico del IMSS: sin esa mitad de
    la regla, 2026 sale con dos fechas mal (las cuotas de marzo y las de junio).

    **No aplica a los avisos afiliatorios**, que el propio Art. 3 excluye; ésos
    los resuelve `avisos.py` y aquí no se tocan.
    """
    while (not es_habil(dia)) or dia.weekday() == _VIERNES:
        dia += timedelta(days=1)
    return dia


def prorroga_cff(dia: date) -> date:
    """
    Cómputo del plazo del SAT (CFF Art. 12): si vence en día inhábil, corre al
    siguiente hábil. **Sin la regla del viernes**, que es del IMSS y no del CFF.
    """
    return _siguiente_habil(dia)


def fecha_limite_cuotas(anio_de_las_cuotas: int, mes: int) -> date:
    """
    Vencimiento del entero de cuotas del IMSS del mes indicado (Art. 39 LSS).

    Se nombra por el **mes de las cuotas**, no por el del vencimiento: las
    cuotas de marzo vencen en abril. Es la convención del doc 25 §2.
    """
    anio_venc, mes_venc = _mes_siguiente(anio_de_las_cuotas, mes)
    return prorroga_racerf(date(anio_venc, mes_venc, DIA_DE_ENTERO))


def fecha_limite_entero_isr(anio_de_las_retenciones: int, mes: int) -> date:
    """
    Vencimiento del entero del ISR retenido de salarios (LISR Art. 96).

    Día 17 del mes siguiente con el cómputo del CFF Art. 12. **No se aplica el
    ajuste por sexto dígito del RFC** (facilidad de la RMF): sólo puede correr
    la fecha hacia adelante, y el modelo de cliente de la demo no guarda RFC.
    Omitirlo deja la fecha igual o antes de la legal, que es lo conservador.
    """
    anio_venc, mes_venc = _mes_siguiente(anio_de_las_retenciones, mes)
    return prorroga_cff(date(anio_venc, mes_venc, DIA_DE_ENTERO))


def fecha_limite_prima_riesgo(anio_de_presentacion: int) -> date:
    """
    Vencimiento de la Declaración Anual de Prima de Riesgo de Trabajo
    (Art. 74 LSS; Art. 32 RACERF): durante febrero, a más tardar el último día.

    **No se le aplica la prórroga del Art. 3 RACERF**, y la razón NO es que el
    artículo la excluya —se presenta bajo el mismo reglamento, así que su
    cómputo sí le alcanza—, sino que correr la fecha hacia adelante es la
    dirección permisiva. Se toma la conservadora.

    # DECISIÓN PROVISIONAL (nocturno): en 2026 el último día de febrero cae en
    # sábado 28. Con el Art. 3 el plazo correría al lunes 2 de marzo. Pregunta
    # abierta para la contadora en `docs/decisiones-nomina.md` §D23.
    """
    return _ultimo_dia_del_mes(anio_de_presentacion, 2)


def fecha_limite_aguinaldo(anio: int) -> date:
    """
    Vencimiento del pago del aguinaldo (LFT Art. 87).

    El artículo dice **"antes del día veinte de diciembre"**, así que la fecha
    límite es el **19**, no el 20: el día 20 ya no está dentro del plazo. Un día
    de más aquí es un día que la ley no concede.
    """
    return date(anio, 12, 19)


def fecha_limite_ptu(anio_de_pago: int, personalidad: Personalidad) -> date:
    """
    Vencimiento del reparto de utilidades (LFT Art. 122): sesenta días
    siguientes a la fecha en que deba pagarse el impuesto anual — 31 de marzo
    para personas morales y 30 de abril para personas físicas.

    Se deriva de la regla en vez de teclear el 30 de mayo y el 29 de junio, para
    que el fundamento esté en el código y un año raro no pase desapercibido.
    """
    mes, dia = _ANUAL_MORAL if personalidad is Personalidad.MORAL else _ANUAL_FISICA
    return date(anio_de_pago, mes, dia) + timedelta(days=DIAS_PARA_REPARTIR_PTU)


_RAMOS_MENSUALES = "Riesgos de Trabajo, Enfermedades y Maternidad, Invalidez y Vida, Guarderías"
_RAMOS_BIMESTRALES = "Retiro, Cesantía y Vejez, Infonavit"

_NOMBRE_MES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _nota_si_cae_inhabil(dia: date, sufijo: str = "") -> str:
    """
    Advertencia para las obligaciones que **no** se prorrogan.

    Una fecha fija de ley que cae en sábado se sigue reportando tal cual —moverla
    sin norma que lo autorice sería inventarse un plazo—, pero callar que cae en
    inhábil deja al patrón planeando un trámite en un día en que no puede
    hacerlo. La nota **describe** el dato; nunca propone una segunda fecha.
    """
    if es_habil(dia):
        return ""
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    base = f"El {dia.isoformat()} cae en {dias[dia.weekday()]}."
    return f"{base} {sufijo}".strip()


@dataclass(frozen=True)
class _Contexto:
    """Lo que se sabe del patrón. `None` = el modelo no lo registra."""

    tiene_salario_variable: bool | None = None
    personalidad: Personalidad | None = None
    notas: dict[str, str] = field(default_factory=dict)


def _obligaciones_mensuales(anio: int) -> list[ObligacionPatronal]:
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
                nota="Se rige por la regla del SAT, no por la del IMSS: el viernes es hábil. "
                "No se aplica el ajuste por sexto dígito del RFC, que sólo puede correr la "
                "fecha hacia adelante.",
            )
        )
    return obligaciones


def _obligaciones_bimestrales(anio: int, ctx: _Contexto) -> list[ObligacionPatronal]:
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
        # El aviso existe aunque el promedio no cambie: lo que se presenta es la
        # determinación del bimestre. Lo que no se sabe es si HAY variables.
        condicional = ctx.tiene_salario_variable is None
        if ctx.tiene_salario_variable is False:
            continue
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
                condicional=condicional,
                nota=ctx.notas.get("aviso_variables", "") if condicional else "",
            )
        )
    return obligaciones


def _obligaciones_anuales(anio: int, ctx: _Contexto) -> list[ObligacionPatronal]:
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
            # Se presenta en febrero de `anio` pero REPORTA el ejercicio anterior
            # (Art. 74 LSS). Decirlo "anio" sería un dato falso.
            periodo_cubierto=ejercicio_anterior,
            fundamento="Art. 74 LSS; Art. 32 RACERF",
            regimen_de_plazo=RegimenDePlazo.IMSS,
            nota=_nota_si_cae_inhabil(
                prima,
                "No se aplica la prórroga del Art. 3 RACERF: correr la fecha hacia adelante "
                "es la dirección permisiva. Decisión provisional, ver §D23.",
            ),
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

    for personalidad in (Personalidad.MORAL, Personalidad.FISICA):
        if ctx.personalidad is not None and ctx.personalidad is not personalidad:
            continue
        condicional = ctx.personalidad is None
        fecha = fecha_limite_ptu(anio, personalidad)
        etiqueta = "persona moral" if personalidad is Personalidad.MORAL else "persona física"
        obligaciones.append(
            ObligacionPatronal(
                clave=f"ptu_{personalidad.value}",
                nombre=f"Reparto de utilidades (PTU) — {etiqueta}",
                descripcion="Sesenta días siguientes a la fecha en que debe pagarse el "
                f"impuesto anual del {etiqueta} patrón.",
                fecha_limite=fecha,
                periodicidad="anual",
                periodo_cubierto=ejercicio_anterior,
                fundamento="LFT Art. 122",
                regimen_de_plazo=RegimenDePlazo.LFT,
                condicional=condicional,
                nota=" ".join(
                    parte
                    for parte in (
                        ctx.notas.get("ptu", "") if condicional else "",
                        _nota_si_cae_inhabil(fecha),
                    )
                    if parte
                ),
            )
        )
    return obligaciones


NOTA_SALARIO_VARIABLE = (
    "El modelo de cliente no registra el tipo de salario de sus trabajadores. Si el patrón "
    "tiene trabajadores de salario variable o mixto, esta obligación es firme."
)
NOTA_PERSONALIDAD = (
    "El modelo de cliente no registra la personalidad jurídica del patrón. Sólo una de las dos "
    "fechas de PTU le aplica."
)


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
            vencimiento. Las cuotas de diciembre de 2026 vencen en enero de
            2027 y **sí** están aquí; las de diciembre de 2025, que vencen en
            enero de 2026, **no**. Es la convención del doc 25 §2, y por eso el
            parámetro se llama así y no `anio`.

            Las anuales fijas (prima de RT, PTU, aguinaldo) son las que
            **vencen** dentro del año pedido. Su `periodo_cubierto` dice qué
            ejercicio reportan, que para la prima de RT y el PTU es el
            **anterior**.
        tiene_salario_variable: `True` → el aviso bimestral del Art. 34 fr. II
            es firme; `False` → no se emite; `None` → se emite marcado
            `condicional`, porque no consta si el patrón tiene variables. `None`
            no es "no tiene": es "no se sabe".
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

    ctx = _Contexto(
        tiene_salario_variable=tiene_salario_variable,
        personalidad=personalidad,
        notas={"aviso_variables": NOTA_SALARIO_VARIABLE, "ptu": NOTA_PERSONALIDAD},
    )

    obligaciones = [
        *_obligaciones_mensuales(anio_de_las_cuotas),
        *_obligaciones_bimestrales(anio_de_las_cuotas, ctx),
        *_obligaciones_anuales(anio_de_las_cuotas, ctx),
    ]
    # Orden estable: por fecha y, dentro del día, por clave. Sin el desempate,
    # dos corridas podrían devolver el mismo día en distinto orden y la pantalla
    # se reacomodaría sola entre refrescos.
    obligaciones.sort(key=lambda o: (o.fecha_limite, o.clave, o.periodo_cubierto))
    return tuple(obligaciones)
