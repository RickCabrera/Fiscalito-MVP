"""
Plantilla del cliente de la demo (épica D). **Demo-only: se borra en F2.**

DE DONDE SALEN ESTOS DATOS
--------------------------
De las fixtures anonimizadas de S-04 (`tests/fixtures/nomina/semana-*/E-0X.xml`).
Las **identidades son sinteticas** —RFC, CURP, NSS y nombres inventados, ver
`tests/nomina_inventario.py`— y los **montos son reales**. No hay ninguna
persona identificable aqui, que es exactamente la forma que autoriza el
`CLAUDE.md` de la raiz para trabajar con el caso real.

POR QUE VIVE EN `app/` Y NO SE LEE DE LAS FIXTURES
--------------------------------------------------
`pyproject.toml` empaqueta `include = ["app*"]`. Un modulo de runtime que
leyera `tests/fixtures/` funcionaria en local y reventaria en el contenedor de
Cloud Run. Mismo razonamiento por el que el generador de D-05 se quedo en
`scripts/`.

El precio es una **copia**, y por eso `tests/nomina/test_plantilla_demo.py`
verifica contra las fixtures que no diverja. Sin ese test esto seria una
tercera copia sin dueño.

CUIDADO AL REGENERAR LAS FIXTURES
---------------------------------
`scripts/anonimizar_nomina.py` dice en su encabezado que **una segunda corrida
baraja de nuevo la asignacion de identidades** y moveria a las personas entre
E-01..E-09. Si eso llega a pasar, esta plantilla queda mal y el test de
no-divergencia es lo unico que lo detecta.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.periodo import EmpleadoPeriodo
from app.schemas.asistencia import Periodo

# Prima de Riesgos de Trabajo del patron de la demo. NO es tasa de ley: se
# autodetermina cada febrero (Art. 74 LSS). Es la misma que usan los tests del
# caso real de F1-03 y F1-04.
PRIMA_RIESGO_DEMO: Decimal = Decimal("0.0054355")

# Clave de `c_PeriodicidadPago`: 04 = quincenal. La demo es quincenal por
# regla del dia (ver docs/D-DEMO-CHECADOR.md).
CLAVE_PERIODICIDAD_DEMO: str = "04"

# `salario_diario` sale de la percepcion 001 dividida entre `NumDiasPagados`, y
# `salario_diario_integrado` del `SalarioBaseCotApor`. Cada empleado tiene un
# solo valor de cada uno en las nueve semanas del caso.
#
# El SDI es dato de entrada y **no se deriva de la antiguedad** (§D9): los
# factores implicitos del caso real son distintos entre empleados y no
# monotonos. Cualquier intento de recomputarlo aqui daria otros numeros.
PLANTILLA_DEMO: tuple[EmpleadoPeriodo, ...] = (
    EmpleadoPeriodo("E-01", "ANA BEATRIZ XALA MORA", Decimal("316.00"), Decimal("331.58")),
    EmpleadoPeriodo("E-02", "BRUNO CASTRO XIMENO", Decimal("326.84"), Decimal("357.44")),
    EmpleadoPeriodo("E-03", "CARLA DENISSE XOLO PEREZ", Decimal("368.05"), Decimal("399.52")),
    EmpleadoPeriodo("E-04", "DIEGO ELIAS XUNI ROMAN", Decimal("368.05"), Decimal("399.05")),
    EmpleadoPeriodo("E-05", "ELENA FABIOLA XEQUE SOLIS", Decimal("316.00"), Decimal("343.00")),
    EmpleadoPeriodo("E-06", "FELIPE GAEL XIRA TOVAR", Decimal("316.00"), Decimal("346.11")),
    EmpleadoPeriodo("E-07", "GLORIA HELENA XAMO VEGA", Decimal("368.05"), Decimal("387.23")),
    EmpleadoPeriodo("E-08", "HUGO IVAN XENA ZAMORA", Decimal("316.00"), Decimal("331.58")),
    EmpleadoPeriodo("E-09", "IRENE JIMENA XOCO AGUIRRE", Decimal("316.00"), Decimal("358.34")),
)

# Todos en zona general. El caso real es de Veracruz (ClaveEntFed se conserva
# en las fixtures por §5.8 del PLAN_NOMINA), que no es Zona Libre de la
# Frontera Norte.
ZONA_DEMO: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL


def quincena(hoy: date) -> Periodo:
    """
    La ultima quincena **ya terminada**.

    Vive aqui y no en `scripts/` porque **el endpoint la necesita en runtime**:
    `pip install -e .` solo empaqueta `app*`, y `periodo_sugerido` de
    `GET /nomina/demo/plantilla` sale de esta funcion. El simulador de D-05 la
    importa de aqui, para que sembrar y demostrar usen exactamente la misma
    regla — si divergieran, el panel saldria vacio.

    DECISIÓN PROVISIONAL (nocturno): se eligio la terminada y no la quincena en
    curso por dos consecuencias que se compensan mal:

    - A favor: `cerrar_periodo()` marca falta **todo** dia laborable sin
      checada, incluidos los que aun no llegan. Cerrar la quincena en curso el
      dia 2 daria ~9 faltas por empleado y las 2 sembradas serian invisibles.
    - En contra: el panel muestra checadas del mes pasado. Por eso D-07 pollea
      **sin `desde`** y toma el periodo de aqui en vez de deducirlo de las
      checadas.

    OJO CON EL BORDE: sembrar el dia 15 y demostrar el 16 da **dos quincenas
    distintas**, y el panel sale vacio. Sembrar y demostrar el mismo dia.

    Los dias del periodo salen de las fechas, nunca de una constante: del 16 al
    31 son **16 dias, no 15**. Deducirlos de la primera y la ultima checada da
    15 —el 16 cae en fin de semana— y ese dia de menos entra a `DiasDelPeriodo`
    y a los dias pagados, o sea a las cuotas del IMSS y al ISR.
    """
    if hoy.day > 15:
        return Periodo(inicio=hoy.replace(day=1), fin=hoy.replace(day=15))
    fin = hoy.replace(day=1) - timedelta(days=1)
    return Periodo(inicio=fin.replace(day=16), fin=fin)
