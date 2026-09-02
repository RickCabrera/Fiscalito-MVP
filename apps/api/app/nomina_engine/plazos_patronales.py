"""
Las reglas de plazo de las obligaciones patronales. **Sólo fechas.**

Cuatro reglas que se ven iguales y no lo son. La doctrina completa, con sus
citas y el porqué de cada una, vive en
`knowledge_base/nomina/25_calendario_laboral_2026.md` §5; aquí va el resumen:

| `RegimenDePlazo` | Regla | Fundamento |
|---|---|---|
| `IMSS` | inhábil **o viernes** → siguiente hábil | Art. 3 RACERF |
| `IMSS_SIN_PRORROGA` | fecha fija; no se corre (decisión §D23) | Art. 74 LSS; Art. 32 RACERF |
| `IMSS_AVISO` | no se prorroga nunca | Art. 3 RACERF, que excluye los avisos afiliatorios |
| `SAT` | inhábil → siguiente hábil, **sin** la regla del viernes | CFF Art. 12 |
| `LFT` | fecha fija de ley | LFT Arts. 87 y 122 |

Se ve en 2026: las cuotas del IMSS de marzo vencen el **20-abr** y el entero del
ISR de marzo el **17-abr**, porque para el SAT el viernes es hábil.

Quién produce cada obligación con estas reglas: `calendario_laboral.py`.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum

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


class RegimenDePlazo(str, Enum):
    """
    Qué regla de cómputo produjo la fecha límite.

    Viaja como **dato** hasta la respuesta HTTP, no como comentario: el doc 25
    §4 advierte que juntar obligaciones del IMSS y del SAT en una vista "sin
    distinguir su regla es un bug esperando".

    `IMSS_SIN_PRORROGA` existe porque `IMSS` promete una prórroga que la
    declaración anual de prima de RT no recibe (§D23). Etiquetarla `IMSS`
    pondría el sábado 28-feb-2026 bajo el rótulo "se corre al siguiente hábil".
    """

    IMSS = "imss"
    IMSS_SIN_PRORROGA = "imss_sin_prorroga"
    IMSS_AVISO = "imss_aviso"
    SAT = "sat"
    LFT = "lft"


class Personalidad(str, Enum):
    """Personalidad jurídica del patrón. Decide el plazo del PTU (Art. 122 LFT)."""

    FISICA = "fisica"
    MORAL = "moral"


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def ultimo_dia_del_mes(anio: int, mes: int) -> date:
    anio_sig, mes_sig = _mes_siguiente(anio, mes)
    return date(anio_sig, mes_sig, 1) - timedelta(days=1)


def prorroga_racerf(dia: date) -> date:
    """
    Cómputo del plazo del IMSS (Art. 3 RACERF): si el último día es **inhábil o
    viernes**, corre al siguiente hábil.

    Que el viernes también corra es específico del IMSS; sin esa mitad de la
    regla, 2026 sale con dos fechas mal. **No aplica a los avisos
    afiliatorios**, que el propio Art. 3 excluye y `avisos.py` ya resuelve.
    """
    while (not es_habil(dia)) or dia.weekday() == _VIERNES:
        dia += timedelta(days=1)
    return dia


def prorroga_cff(dia: date) -> date:
    """
    Cómputo del plazo del SAT (CFF Art. 12): si vence en inhábil, corre al
    siguiente hábil. **Sin la regla del viernes**, que es del IMSS.

    OJO CON "INHÁBIL": se usan los descansos del Art. 74 LFT, que **no** son los
    del SAT — el CFF suma el 1 de diciembre sexenal y la RMF las vacaciones
    generales, y ninguno de los dos está en el repo. Contar de menos inhábiles
    deja la fecha antes o igual que la legal, que es la dirección conservadora.
    Misma advertencia que `dias_habiles.py`; ver `docs/decisiones-nomina.md` §D13.
    """
    while not es_habil(dia):
        dia += timedelta(days=1)
    return dia


def fecha_limite_cuotas(anio_de_las_cuotas: int, mes: int) -> date:
    """
    Vencimiento del entero de cuotas del IMSS del mes indicado (Art. 39 LSS).

    Se nombra por el **mes de las cuotas**, no por el del vencimiento: las de
    marzo vencen en abril. Es la convención del doc 25 §2.
    """
    anio_venc, mes_venc = _mes_siguiente(anio_de_las_cuotas, mes)
    return prorroga_racerf(date(anio_venc, mes_venc, DIA_DE_ENTERO))


def fecha_limite_entero_isr(anio_de_las_retenciones: int, mes: int) -> date:
    """
    Vencimiento del entero del ISR retenido de salarios (LISR Art. 96).

    Día 17 del mes siguiente con el cómputo del CFF Art. 12. **No se aplica el
    ajuste por sexto dígito del RFC** (facilidad de la RMF): sólo puede correr
    la fecha hacia adelante, y el modelo de cliente de la demo no guarda RFC.
    """
    anio_venc, mes_venc = _mes_siguiente(anio_de_las_retenciones, mes)
    return prorroga_cff(date(anio_venc, mes_venc, DIA_DE_ENTERO))


def fecha_limite_prima_riesgo(anio_de_presentacion: int) -> date:
    """
    Declaración Anual de Prima de Riesgo de Trabajo (Art. 74 LSS; Art. 32
    RACERF): durante febrero, a más tardar el último día.

    # DECISIÓN PROVISIONAL (nocturno, §D23): NO se le aplica la prórroga del
    # Art. 3 RACERF. El cómputo de ese artículo sí le alcanza —se presenta bajo
    # el mismo reglamento— pero correr la fecha hacia adelante es la dirección
    # permisiva. En 2026 cae en sábado 28. Pregunta abierta a la contadora.
    """
    return ultimo_dia_del_mes(anio_de_presentacion, 2)


def fecha_limite_aguinaldo(anio: int) -> date:
    """
    Pago del aguinaldo (LFT Art. 87).

    El artículo dice **"antes del día veinte de diciembre"**, así que el límite
    es el **19**: el día 20 ya está fuera del plazo. Un día de más aquí es un
    día que la ley no concede.
    """
    return date(anio, 12, 19)


def fecha_limite_ptu(anio_de_pago: int, personalidad: Personalidad) -> date:
    """
    Reparto de utilidades (LFT Art. 122): sesenta días siguientes a la fecha en
    que deba pagarse el impuesto anual — 31 de marzo para personas morales y 30
    de abril para físicas.

    Se deriva de la regla en vez de teclear el 30 de mayo y el 29 de junio, para
    que el fundamento esté en el código y un año raro no pase desapercibido.
    """
    mes, dia = _ANUAL_MORAL if personalidad is Personalidad.MORAL else _ANUAL_FISICA
    return date(anio_de_pago, mes, dia) + timedelta(days=DIAS_PARA_REPARTIR_PTU)
