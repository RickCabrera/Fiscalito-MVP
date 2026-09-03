"""
Que la duracion del periodo case con la clave de periodicidad. (O-03)

EL AGUJERO QUE ESTO CIERRA, Y POR QUE ES DE LOS CAROS
-----------------------------------------------------
`calcular_periodo` recibe `clave_periodicidad` y elige con ella la tarifa del
Art. 96 (`tarifas_isr_periodicas.tarifa_por_periodicidad`). Hasta O-03 **nadie
comprobaba que esa clave correspondiera a la duracion real del periodo**:
`periodo.py` solo verificaba que todas las incidencias midieran lo mismo entre
si.

Consecuencia, escrita en `backlog.md` seccion G desde la corrida G:

- Un patron marcado **Mensual (05)** con una base de 15-16 dias recibe la
  tarifa MENSUAL sobre esa base. La tarifa mensual tiene limites inferiores
  mucho mas altos, asi que el ingreso cae en un renglon mas bajo y el ISR sale
  **subestimado, con un recibo perfectamente creible y sin un solo error**.
- El simetrico —punto 6 de esa misma seccion, que **nadie cubria**— es un
  patron **Quincenal (04)** al que el operador le arrastra las fechas a un mes
  completo: tarifa quincenal sobre base mensual, e ISR **sobrestimado**.

Los dos inputs de fecha de la pantalla son libres, asi que las dos direcciones
son alcanzables con dos clics.

DE DONDE SALEN LOS RANGOS: SE DERIVAN, NO SE AFIRMAN
-----------------------------------------------------
No son numeros de gusto. Cada uno es el minimo y el maximo de dias naturales
que puede tener un periodo de esa clave, contados como los cuenta
`asistencia/incidencias.py:_dias_del_periodo` — **inclusivo en los dos
extremos**, que es como `dias_periodo` llega aqui.

- **01 diaria** -> exactamente 1.
- **02 semanal** -> exactamente 7.
- **04 quincenal** -> **13 a 16**, y ninguno de los dos extremos es arbitrario:
  * El **minimo 13** es la segunda quincena de febrero en año no bisiesto: del
    16 al 28 son 13 dias. Es **el periodo que la propia app propone** entre el
    1 y el 15 de marzo (`demo_nomina.quincena`), asi que un rango que empezara
    en 14 haria que el motor rechazara su propio default. Lo cazo el revisor
    del plan de esta tarea: el rango que yo habia escrito era (14, 17).
  * El **maximo 16** es del 16 al 31 de un mes de 31 dias. **17 no es nunca una
    quincena**, y admitirlo seria tolerar dos dias de base sin tarifa: la
    quincenal se deriva a **exactamente 15 dias**
    (`tablas_isr_periodicas.py`, `_derivar_tarifa(TARIFA_MENSUAL_2026, 15)`).
- **05 mensual** -> **28 a 31**: febrero comun, febrero bisiesto, y los meses
  de 30 y 31.

Las claves que no estan aqui **no se validan por duracion** y no es un olvido:
`tarifa_por_periodicidad` ya las rechaza con su propio motivo (catorcenal y
decenal por falta de tarifa publicada, §D10; bimestral, unidad de obra,
comision y precio alzado porque no son periodos). Duplicar ese rechazo aqui
daria dos mensajes distintos para la misma causa.

QUE ESTA GUARDA BLOQUEA Y NO DEBERIA — DECISION PROVISIONAL
------------------------------------------------------------
Un **periodo parcial legitimo**: un alta o una baja a media quincena produce
hoy un periodo corto que si se calcula, y a partir de aqui es un 422.

Es la opcion conservadora y es el default correcto —cobrar de mas o de menos en
silencio es peor que no calcular— pero **es una regresion funcional** respecto
de lo que la app hacia ayer, y hay que decirlo. La pregunta de fondo (tabla del
Art. 96 sobre base parcial, o prorrateo) **no esta resuelta en el repo**:
`backlog.md` §G punto 5 la deja rozando `PLAN_NOMINA.md` §5, y ahora esta
abierta como §D26 en `docs/decisiones-nomina.md`.

Por eso el mensaje de error **distingue las dos causas**. Sin eso, el operador
va a "corregir" la periodicidad de la empresa para que le deje calcular —que es
mucho peor que el 422— en vez de entender que su periodo es parcial.
"""

from __future__ import annotations

from app.exceptions import FiscalValidationError

# DECISIÓN PROVISIONAL (nocturno): los rangos son de duracion NATURAL del
# periodo, derivados del calendario (ver el docstring). Bloquean el periodo
# parcial de un alta o una baja, que es lo conservador mientras §D26 sigue
# abierta con la contadora.
DURACION_ESPERADA: dict[str, tuple[int, int]] = {
    "01": (1, 1),
    "02": (7, 7),
    "04": (13, 16),
    "05": (28, 31),
}

NOMBRE_PERIODICIDAD: dict[str, str] = {
    "01": "diaria",
    "02": "semanal",
    "04": "quincenal",
    "05": "mensual",
}


def validar_duracion_periodo(clave_periodicidad: str, dias_periodo: int) -> None:
    """
    Rechaza un periodo cuya duracion no corresponde a su periodicidad.

    Args:
        clave_periodicidad: clave de `c_PeriodicidadPago`.
        dias_periodo: dias **naturales** del periodo, inclusivo en los dos
            extremos. Es el mismo `dias_periodo` que produce
            `asistencia/incidencias.cerrar_periodo`.

    Raises:
        FiscalValidationError: si no casan. El mensaje distingue las dos causas
            posibles —la clave equivocada y el periodo parcial— porque tienen
            arreglos opuestos y confundirlas lleva a cambiar la periodicidad de
            la empresa, que es el dato bueno.
    """
    rango = DURACION_ESPERADA.get(clave_periodicidad)
    # Clave sin rango: la rechaza `tarifa_por_periodicidad` con su propio
    # motivo, o es una clave valida sin restriccion de duracion. Aqui se deja
    # pasar a proposito para no dar dos mensajes de la misma causa.
    if rango is None:
        return

    minimo, maximo = rango
    if minimo <= dias_periodo <= maximo:
        return

    nombre = NOMBRE_PERIODICIDAD.get(clave_periodicidad, clave_periodicidad)
    esperado = f"{minimo} días" if minimo == maximo else f"{minimo} a {maximo} días"
    raise FiscalValidationError(
        f"El periodo mide {dias_periodo} días naturales y la periodicidad registrada es "
        f"{nombre} ({clave_periodicidad}), que son {esperado}. Calcularlo aplicaría la "
        f"tarifa de ISR de {nombre} sobre una base que no le corresponde, y el resultado "
        f"sería incorrecto sin avisar. "
        f"Corrige la periodicidad de la empresa, o las fechas del periodo. "
        f"Si lo que quieres es un periodo PARCIAL —un alta o una baja a mitad de "
        f"periodo— eso todavía no se puede calcular aquí: está pendiente de definir con "
        f"la contadora si va tabla del Art. 96 sobre base parcial o prorrateo "
        f"(docs/decisiones-nomina.md §D26)."
    )
