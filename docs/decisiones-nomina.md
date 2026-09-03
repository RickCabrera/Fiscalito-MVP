# Decisiones de nómina

Cierra **F0-03**. Cada entrada es una decisión tomada para desbloquear F1. Las marcadas
**PROVISIONAL** están pendientes de confirmación con la contadora: si su respuesta difiere,
se corrige aquí y en el código que la cite.

En modo autónomo este archivo es la fuente de verdad para decisiones que dependen del mundo.
Si una decisión no está cubierta aquí, se toma la opción más conservadora y se marca en el
código con `# DECISIÓN PROVISIONAL (nocturno):`.

## D1 · ISR periódico

Usar las tablas del **Anexo 8 de la RMF 2026** según la periodicidad del CFDI (en el caso
real, semanal). Validar contra el ISR retenido de las fixtures de S-04; si no cuadra, probar
el prorrateo de la tabla mensual y documentar aquí cuál de los dos cuadró.

## D2 · Redondeo

Por concepto y por empleado, a **2 decimales**, al estilo SUA. Validar contra las fixtures.

**Validado en F1-03, y el caso real trae los dos órdenes.** El empleado `XAHH010101AA8` tiene
deducción de IMSS de **$55.13 en marzo** y **$55.12 de abril en adelante**, con el mismo SBC
($331.58) y los mismos 7 días. Esos dos valores son, al centavo, los dos órdenes de redondeo
admisibles:

- por concepto (lo que manda D2 y hace el motor) → **$55.12**
- sobre el agregado → **$55.13**

O sea que el software del patrón **cambió de orden de redondeo en el corte marzo→abril**. No es
ruido: es una decisión de redondeo observable, y confirma que D2 es una decisión real y no una
formalidad. Ver §D14.

## D3 · Ausentismos e incapacidades — PROVISIONAL

Aplicar el **Art. 31 LSS** literal: las ausencias de hasta 7 días al mes descuentan días en
todos los ramos **excepto Enfermedades y Maternidad**; durante una incapacidad solo se cotiza
EyM. Confirmar con la contadora.

**Implementado en F1-03** con `DiasDelPeriodo` y `Ramo.se_reduce_por_ausentismo`.

**Límite conocido, no implementado:** D3 habla de ausencias *de hasta 7 días*. La **fr. II del
Art. 31** libera al patrón de **todas** las cuotas cuando la ausencia excede ese plazo (con la
baja del Art. 37). Hoy, con 20 días de ausencia, el motor sigue cobrando 30 días de EyM. La
dirección del error es la conservadora —cobra de más, no de menos— así que se dejó fijada por
un test en vez de adivinar. **S-04 no puede validar nada de esto:** los 70 recibos traen
`NumDiasPagados=7.000` y no hay ni una incapacidad.

## D4 · Quirk CEAV 2026 — PROVISIONAL

Aplicar la tabla literal por rango de UMA. El salario mínimo exacto cae en **3.150%**. Los
renglones inalcanzables se dejan en la tabla, sin lógica especial que los excluya.

**Afinado en F1-01 — la pregunta para la contadora es más filosa de lo que parecía.** Lo
implementado es `SBC == 1 SM`, y el SBC de un trabajador de salario mínimo **casi nunca** es
1 SM: es `SM × factor de integración` (≈1.0493) ≈ $330.57, o sea ~2.82 UMA, que cae en el
tramo 2.51–3.00 → **6.026%**. Con la lectura literal, el renglón de 3.150% solo se alcanza
cuando el clamp del Art. 28 subió un SBC al piso, cosa que a un trabajador de salario mínimo
de jornada completa no le pasa: el renglón es, en la práctica, casi inalcanzable.

> **¿El SUA lee "1.00 SM" como *SBC igual al salario mínimo* (lo implementado) o como
> *trabajador que percibe el salario mínimo*, es decir salario diario = SM con SBC integrado
> por encima?**

Las dos lecturas dan **3.150% vs 6.026% para todos los trabajadores de salario mínimo del
país**. El código no adivina: aplica la literal, la documenta y la prueba. Si la respuesta es
la segunda, lo que cambia es `ceav_patronal()` y sus tests, y se ve exactamente dónde.

**Ampliado en F1-04: y también los Arts. 93 fr. I y 96 de la LISR.** El predicado decide
cuatro cosas, no dos: el renglón de 3.150 % de CEAV, la absorción del Art. 36, el tiempo extra
100 % exento y la no retención de ISR. **Salvedad:** el predicado compara el **SBC** contra el
salario mínimo, y los artículos de la LISR hablan del **salario**, no del SBC. Es la misma
ambigüedad de esta decisión y por eso no se bifurcó el predicado; si la contadora responde que
son criterios distintos, se separa entonces y se ve exactamente dónde.

**Ampliado en F1-03: la misma respuesta gobierna el Art. 36 LSS**, la absorción de la cuota
obrera por el patrón. Son dos consecuencias de una sola pregunta legal, así que el motor tiene
un **predicado único** —`ceav.es_trabajador_de_salario_minimo()`— que usan tanto la tabla de
CEAV como el cálculo de cuotas. Si viviera contestado en dos archivos, la respuesta de la
contadora se aplicaría en uno y no en el otro.

## D5 · Prestaciones superiores a las de ley

Modelar vía `ConceptoIntegrable`. El default es el **mínimo de ley**.

## D6 · EMA / EBA

**Fuera de alcance hasta F3.**

## D7 · Timbrado con PAC

**Fuera de alcance hasta F3.**

## D8 · Entidad federativa

El patrón del caso real es de **Veracruz**: `ClaveEntFed=VER` en el CFDI. El **ISN del 3% es
solo informativo** — no se calcula en F1.

## D9 · El caso real no es "mínimo de ley" — PROVISIONAL, para la contadora

Hallazgo al construir las fixtures de S-04: los factores de integración implícitos del caso
real (`SalarioDiarioIntegrado` contra el salario diario) son **superiores al mínimo de ley**,
**distintos entre empleados** y **no derivables de la antigüedad** — el empleado con menos
antigüedad tiene uno de los factores más altos.

Consecuencias, que conviene tener claras antes de llegar a F1:

- **El `SalarioDiarioIntegrado` se toma como dato de entrada**, no se recomputa desde la
  antigüedad. Cualquier código que intente derivarlo de los días de vacaciones de ley va a
  discrepar con el caso real.
- **F1-02 no se valida contra el caso real**: su "Listo cuando" se mide contra la tabla de
  factores mínimos de PLAN_NOMINA §2.2, que es independiente de este patrón. F1-03 consume el
  SDI como entrada, así que no se ve afectada.
- La explicación probable es que el patrón otorga **prestaciones superiores a las de ley**,
  cuyos montos **no son visibles en el CFDI**. Esto matiza §D5, que fija el default en el
  mínimo de ley: el default sigue bien, pero este patrón no lo sigue.

**Pregunta para la contadora:** ¿qué prestaciones superiores otorga el patrón y cómo integran
al SBC? Sin esa respuesta, el SDI del caso real solo puede tratarse como dato observado.

*(Los factores por empleado no se documentan aquí a propósito: el salario diario no está en el
CFDI, y publicar el factor permitiría despejarlo.)*

## D10 · Periodicidades sin tarifa publicada — PROVISIONAL

El Anexo 8 publica tarifas **diaria, semanal, decenal, quincenal y mensual**, pero
`c_PeriodicidadPago` incluye además la **catorcenal** (clave 03), que ninguna autoridad
publica como tarifa.

Decisión del nocturno: `tarifa_por_periodicidad()` **levanta `FiscalValidationError`** en vez
de derivar una tarifa de 14 días. Generar un ISR que nadie publicó, aunque lleve etiqueta de
"derivada", es peor que fallar: F1-04 lo consumiría sin saberlo. El caso real es semanal, así
que no bloquea nada.

**Para la contadora:** si un patrón paga catorcenal, ¿qué hace su software — semanal × 2,
diaria × 14, o el procedimiento del RLISR?

La **decenal** (clave 10) queda fuera por una razón distinta: el Anexo 8 sí la publica, pero
sus once renglones no se pudieron verificar contra una fuente publicada al construir F1-01. No
se generó desde la fórmula porque las tablas periódicas de este módulo son legítimas
únicamente por estar validadas contra literales publicados. Agregarla es transcribir sus 22
celdas con su cita.

## D11 · Base mensual del tope del subsidio en nóminas sub-mensuales — ABIERTA

El decreto fija el tope del subsidio en **$11,492.66 mensuales**, y el caso real es de nómina
**semanal**. No está definido si el ingreso mensual que se compara contra el tope se
**proyecta** (semanal × 30.4 ÷ 7) o se **acumula por mes calendario**. Cambia quién tiene
derecho al subsidio, no solo cuánto.

`subsidio_empleo()` recibe el ingreso mensual ya resuelto y **no toma la decisión**: la
responsabilidad es del llamador (F1-04), y el docstring lo dice.

### Evidencia del caso real (F1-04) — PROVISIONAL, pero discrimina

En **abril de 2026** el patrón dejó de aplicar el subsidio a exactamente tres empleados. La
única lectura que reproduce esa separación es **`SBC × 30.4`**:

| Empleado | SBC | SBC × 30.4 | ¿subsidio en abril? |
|---|---|---|---|
| ...AA3 | 399.52 | 12,145.41 | **no** |
| ...AA4 | 399.05 | 12,131.12 | **no** |
| ...AA7 | 387.23 | 11,771.79 | **no** |
| ...AA9 | 358.34 | 10,893.54 | sí |
| ...AA6 | 346.11 | 10,521.74 | sí |
| ...AA5 | 343.00 | 10,427.20 | sí |
| ...AA8 | 331.58 | 10,080.03 | sí |

**Las dos opciones que esta decisión enumeraba quedan refutadas.** Para ...AA3: proyectar el
gravado semanal da **$11,188.72** y acumular el mes calendario da **$10,305.40** — las dos por
debajo del tope de $11,492.66, o sea que las dos predicen subsidio, y el CFDI dice que no lo
hubo. Solo `SBC × 30.4` = $12,145.41 lo explica.

Es **n = 3 contra n = 4**, con dos niveles salariales, así que no cierra la decisión: la
confirma la contadora. Pero el motor ya usa esa lectura en el test del caso real y con ella los
**28 recibos de abril cuadran al centavo**.

## D12 · Decimales del factor de integración — PROVISIONAL

El factor se redondea a **4 decimales** (`ROUND_HALF_UP`) y el SBC se calcula con **ese factor
ya redondeado**, no con el cociente completo.

Razón: el SBC que el patrón declara al IMSS tiene que ser reproducible a mano desde el factor
que el sistema le muestra. Cuatro decimales es la precisión con la que se declara el factor y
con la que están expresadas las tablas de prestaciones mínimas.

No es cosmético: con un salario diario cercano al tope (~$2,800) la diferencia entre usar el
factor redondeado y el completo vale hasta **$0.14 de SBC**.

**Pregunta para la contadora:** ¿su software (NOI / CONTPAQi) calcula el SDI con el factor
redondeado a 4 decimales o con el factor completo?

**Riesgo acotado:** por §D9 el caso real toma el `SalarioDiarioIntegrado` como dato de entrada
y no lo recomputa, así que esta decisión **no afecta el cuadre de S-04**.

## D13 · Qué es un "día hábil" para los plazos del IMSS — ABIERTA

`dias_habiles.py` usa los días de descanso obligatorio del **Art. 74 LFT**. El IMSS publica
además su propio acuerdo anual de días inhábiles, que incluye sus periodos vacacionales y **no
coincide** con el Art. 74.

Mientras ese acuerdo no esté en el repo con su fuente, toda fecha límite de aviso que calcule
el motor es una **estimación conservadora**, no una fecha legal cierta, y así lo dice el
docstring. Dos fracciones del Art. 74 quedaron fuera a propósito:

- **fr. IX, jornada electoral** — depende del calendario del INE.
- **fr. VII, transmisión del Poder Ejecutivo cada seis años** — no se incluyó sin poder citar
  el DOF de su texto vigente. No afecta ningún cálculo de 2026; la próxima ocurrencia es 2030.

En los dos casos el error tiene dirección: marcar de más un día como inhábil **corre el
vencimiento hacia adelante**, y presentar tarde un aviso afiliatorio cuesta de 20 a 350 UMA
(Art. 304-B LSS). Contar de menos es lo conservador.


## D14 · La cuota obrera del caso real no es reproducible — HALLAZGO, para la contadora

**El "Listo cuando" de F1-03 pedía cuadrar contra el caso real de S-04. No es alcanzable con
el dato timbrado, y esto explica por qué.**

La deducción de IMSS (`TipoDeduccion=001`, cuota obrera) de los 70 CFDI **no se reproduce**
desde el `SalarioBaseCotApor` del propio comprobante con las tasas de ley. Cuadran **5 de los
70 recibos**: un solo empleado, y solo desde abril.

| Empleado | SBC timbrado | Deducción observada | Motor (D2) | Recibos que cuadran |
|---|---|---|---|---|
| ...AA1 | 331.58 | 55.13 (4 recibos, solo marzo) | 55.12 | **0 de 4** |
| ...AA2 | 357.44 | 57.09 | 59.58 | 0 de 3 |
| ...AA3 | 399.52 | 68.10 (mar) · 68.09 (abr–may) | 67.75 | 0 de 9 |
| ...AA4 | 399.05 | 66.63 | 67.67 | 0 de 9 |
| ...AA5 | 343.00 | 57.28 | 57.02 | 0 de 9 |
| ...AA6 | 346.11 | 57.06 | 57.55 | 0 de 9 |
| ...AA7 | 387.23 | 64.46 | 65.36 | 0 de 9 |
| ...AA8 | 331.58 | 55.13 (mar) · 55.12 (abr–may) | 55.12 | **5 de 9** |
| ...AA9 | 358.34 | 57.21 | 59.76 | 0 de 9 |

**El conteo honesto: 5 de los 70 recibos.** Un solo empleado, y solo en sus
recibos de abril y mayo.

La tasa obrera de ley es **2.3750 %** (EyM prestaciones en dinero 0.25 + EyM gastos médicos de
pensionados 0.375 + IyV 0.625 + CEAV 1.125), más 0.40 % sobre el excedente de 3 UMA cuando
aplica.

### La prueba de que el problema es el dato de entrada, no la fórmula

Tres empleados tienen una deducción **por debajo del mínimo legal** que impone su propio SBC
timbrado:

| Empleado | SBC | Mínimo legal (incluye el excedente que causa) | Observado | Diferencia |
|---|---|---|---|---|
| ...AA2 | 357.44 | 59.58 | 57.09 | **−2.49** |
| ...AA6 | 346.11 | 57.55 | 57.06 | −0.49 |
| ...AA9 | 358.34 | 59.76 | 57.21 | **−2.55** |

**Ningún ramo omitido, ningún día faltante y ningún excedente puede hacer que un número baje.**
Si la deducción es menor que el piso que impone el SBC, entonces la base con la que el patrón
determinó la cuota **no es el `SalarioBaseCotApor` que timbró**. Es la misma naturaleza que
§D9: el caso real trae números que no se derivan de los campos visibles del CFDI.

### Preguntas concretas para la contadora

1. **¿Qué SBC se usó realmente para determinar la cuota obrera?** El timbrado no reproduce ni
   siquiera el mínimo en tres empleados.
2. **¿El software refresca la UMA el 1 de febrero para el excedente del Art. 106 fr. II, o
   arrastra la del ejercicio anterior?** Pista concreta: el empleado ...AA3 cuadra **al
   centavo** en marzo si el excedente se calcula contra 3 × UMA **2025** ($339.42) en vez de
   la de 2026: `66.42 + 1.68 = 68.10`. Con UMA 2026 da $67.75. Es n=1 y no explica su valor de
   abril, así que no se toma como explicación — pero es barato de confirmar.
3. **¿Por qué cambió el orden de redondeo entre marzo y abril?** Ver §D2.

### El corte marzo→abril lo explica casi todo lo que sí cuadra

Los dos empleados con SBC **idéntico** ($331.58) cuadran distinto, y la diferencia no está en
el trabajador sino en la fecha: `...AA8` cuadra en sus cinco recibos de abril y mayo, y
`...AA1` no cuadra en ninguno porque **causó baja el 29 de marzo** y todos sus recibos caen en
el periodo de redondeo agregado. Dos empleados con el mismo SBC y resultados opuestos según el
mes es la prueba más limpia de que lo que cambió fue el criterio del software, no el dato del
trabajador. Ver §D2.

### Qué se hizo en el código

`cuotas.py` cuadra contra **la fórmula de ley**, ramo por ramo. En
`tests/nomina/test_cuotas_caso_real.py` los tests comparan contra **el importe timbrado**, no
contra el motor, y **todos pasan**, sin skips ni `xfail`:

- el cuadre de los **5 recibos** que se reproducen, afirmado como igualdad contra el CFDI y
  como conjunto exacto sobre los 70 (si sube, alguien cambió el motor o las fixtures);
- la **caracterización** de los que no, con el importe observado **y** el calculado como
  literales, para que un cambio silencioso del motor tampoco pase.

### Lo que S-04 no cubre, para que nadie lo asuma

Las fixtures van del **8-mar-2026 al 3-may-2026**, así que **no ejercitan el transitorio de
enero** (ni el de la UMA ni el del subsidio). Todos los recibos traen `NumDiasPagados=7.000` y
no hay ni una incapacidad, así que **S-04 no puede validar §D3**. Y el subsidio para el empleo
viene con `Importe="0"` en todos, así que **tampoco va a cerrar §D11**.


## D15 · El subsidio declarado cambia de base en el corte marzo→abril

**Hallazgo de F1-04, leído del propio CFDI.** El complemento de nómina declara el subsidio en
`SubsidioAlEmpleo/@SubsidioCausado`, y ahí se ve el cambio:

| Mes | `SubsidioCausado` | Compatible con |
|---|---|---|
| marzo 2026 (35 recibos) | **$123.47** | **dos** bases distintas — ver abajo |
| abril 2026 (28 recibos) | **$123.34** | $535.65 ÷ 30.4 × 7 (la fórmula de feb–dic) |
| mayo 2026 (7 recibos) | $103.73 y $127.05 | varía por empleado — ver abajo |

### El $123.47 de marzo no permite elegir entre dos explicaciones

```
redondear(536.22 / 30.4 × 7) = 123.47    <- el peso de los CONSIDERANDOS del decreto
redondear(536.21 / 30.4 × 7) = 123.47    <- el TRANSITORIO DE ENERO (15.59% x UMA 2025)
redondear(535.65 / 30.4 × 7) = 123.34    <- la fórmula de febrero en adelante
```

Los dos primeros son **indistinguibles al centavo**, y las fixtures no traen ningún recibo de
enero ni ninguna exención que llegue a su tope, así que tampoco se puede despejar la UMA por
otra vía. Las dos lecturas posibles del marzo del caso real son:

1. el software usó el importe de los **considerandos** ($536.22), que no reconcilia con la
   fórmula del articulado (15.02 % × $3,566.22 = $535.65) y que F0-01 documentó en
   `knowledge_base/nomina/20_valores_referencia_2026.md` §4; **o**
2. el software calculó el subsidio de **enero** con el transitorio (15.59 % × UMA 2025 =
   $536.21) y **lo arrastró hasta marzo sin refrescarlo el 1 de febrero**.

**La segunda cruza directamente con la pregunta 2 de §D14**, que ya le pregunta a la contadora
si su software refresca la UMA el 1 de febrero para el excedente del Art. 106 fr. II o arrastra
la del ejercicio anterior. Si fuera eso, sería **el mismo fallo de refresco del 1-feb en dos
conceptos independientes** — una corroboración cruzada mucho más accionable que la primera
lectura.

**No hay dato que decida entre las dos.** Lo que sí es un hecho: desde abril el declarado es
$123.34, que es lo que produce la fórmula del articulado y lo que calcula el motor.

**Pregunta para la contadora:** ¿su software recalcula el subsidio el 1 de febrero, o arrastra
el de enero? ¿Y de dónde tomó el importe que usó en marzo?

### Consecuencia sobre el cuadre de F1-04

| Mes | Recibos que cuadran |
|---|---|
| marzo | 6 de 35 |
| **abril** | **28 de 28** |
| mayo | 0 de 7 |

Marzo falla por dos razones que se acumulan: la base del subsidio que declara el CFDI y que
**el tope de ingresos todavía no mordía** — en marzo el patrón dio subsidio también a los tres empleados que
en abril quedaron fuera (§D11). Mayo son 7 recibos de otra naturaleza.

### El CFDI de marzo se contradice a sí mismo

El ISR retenido de marzo **no** es `causado − SubsidioCausado` del propio comprobante: el
subsidio implícito en la retención es $123.34 o $123.35, no el $123.47 declarado. Es un dato
duro sobre la calidad del timbrado, del mismo tipo que §D14.

### Lo que queda como hipótesis, no como hallazgo

Los 7 recibos de mayo (semana-09) tienen ISR muy superior al de las demás semanas sobre el
mismo gravado, y su `SubsidioCausado` **varía por empleado** ($103.73 y $127.05), cosa que el
esquema plano de 2024 no produce. Parecen semanas de **ajuste mensual de ISR**, que es práctica
real —la retención semanal es provisional y se ajusta contra el cálculo mensual del Art. 96—
pero **no está verificado**. F1-04 no implementa el ajuste mensual: no está en su alcance.

**Pregunta para la contadora:** ¿la semana 09 lleva ajuste mensual de ISR? ¿Y por qué el
subsidio declarado varía por empleado ahí?

## D16 · El subsidio del trabajador de salario mínimo — PROVISIONAL

Al trabajador de salario mínimo **no se le retiene ISR** (Art. 96, último párrafo). ¿Qué pasa
entonces con su subsidio para el empleo?

Decisión del nocturno, la **más conservadora** de las lecturas: el subsidio **no se acredita**
—no hay ISR retenido contra el cual hacerlo— y **tampoco se entrega en efectivo**, que es el
esquema vigente desde 2024. Ni crédito para el patrón ni efectivo para el trabajador. En el
resultado del motor eso se ve como `acreditado = 0.00` y `subsidio_no_entregado = subsidio`.

Consecuencia técnica: el invariante del resultado **no es el mismo en las dos ramas**, a
propósito. `subsidio == acreditado + no_entregado` se cumple siempre, pero
`retenido == causado − acreditado` vale solo cuando hay retención: la no retención del Art. 96
**no es un acreditamiento**, el ISR se causa igual y simplemente no se retiene.

**Pregunta para la contadora:** ¿es correcto que el subsidio de ese trabajador se pierda, o su
software lo acredita/entrega de alguna forma? Afecta lo que F1-05 emita en `SubsidioCausado` y
en el importe entregado del CFDI.

### Cómo lo emite F1-05, y la pregunta que eso deja abierta

El pre-recibo emite `OtroPago` clave **002** con `Importe="0.00"` y `SubsidioCausado` con el
monto. **Hay precedente observado:** es exactamente lo que hacen los 70 CFDI del caso real.

Pero la descripción de la clave 002 en el catálogo habla del subsidio *efectivamente entregado
al trabajador*, y desde 2024 no se entrega nada — la contradicción que `knowledge_base/nomina/
24_cfdi_nomina_12.md` §3 ya había anotado. **La validación XSD no verifica esta regla**, así
que el verde de F1-05 no la responde: cómo timbrarlo sin rechazo es pregunta para la Guía de
llenado vigente y para la contadora, y se cierra hasta F3 (§D7).

---

## D17 · El séptimo día ante una falta injustificada — PROVISIONAL

Cuando un empleado de salario fijo falta sin justificar, el orquestador de D-06 calcula
`dias_pagados = dias_periodo − faltas`: **se descuenta el día y nada más**.

La otra lectura defendible descuenta además la **parte proporcional del séptimo día**. El
Art. 69 LFT concede un día de descanso con salario íntegro por cada seis días de trabajo, y
parte de los despachos entiende que una falta injustificada rompe esa proporción y arrastra
1/6 de día adicional. Con una falta en una quincena la diferencia es de ~0.17 días de salario.

**Se tomó la primera** por dos razones: es la que **favorece al trabajador** —el error, si lo
hay, no le quita dinero a la persona— y es la que se puede explicar en una demo sin abrir un
debate. Va marcada en `app/nomina_engine/periodo.py`.

**Pregunta para la contadora:** ¿el software del cliente (NOI, CONTPAQi) descuenta sólo el día
o también la proporción del séptimo?

---

## D18 · Fecha de pago contra fin de periodo — PROVISIONAL

`POST /api/v1/nomina/calcular-periodo` recibe `periodo.fecha_pago` **separada** de
`periodo.fin`, y **toda la vigencia se lee de la fecha de pago**: UMA, salario mínimo, tarifa
del Anexo 8 y el transitorio de enero del subsidio. El default, cuando no se manda, es
`periodo.fin`.

**Por qué importa y no es teórico.** Las dos magnitudes cambian en fechas distintas (la UMA el
1 de febrero, el salario mínimo el 1 de enero), así que una quincena que **cierra el 31 de
enero y se paga en febrero** se calcula con valores distintos según cuál de las dos fechas se
use. Está fijado por test: el subsidio de esa quincena es $282.22 pagada el 31-ene y $281.92
pagada el 5-feb.

**Pregunta para Ricardo o la contadora:** ¿el cliente de la demo paga el último día del periodo
o corrido unos días? Si paga corrido, el default es el equivocado para las quincenas de enero.

---

## D19 · La base del tope del subsidio usa el SBC acotado — PROVISIONAL

El orquestador compara contra el tope del subsidio un ingreso mensual de
`redondear(SBC × 30.4)`, tomando el SBC **ya acotado** por el Art. 28 (`clamp_sbc`).

La evidencia que sostiene §D11 se construyó con el SBC **timbrado**, sin acotar. Los dos
coinciden en los 9 empleados de la demo y en los 70 recibos del caso real, y **divergen sólo
para un trabajador cuyo SBC caiga por debajo del piso** —donde el clamp lo sube al salario
mínimo y por tanto sube también la base del tope, quitándole subsidio a quien menos gana.

Se dejó el acotado porque es el mismo valor con el que se calculan las cuotas, y tener dos SBC
distintos en el mismo recibo sería peor. Pero **es una decisión, no una consecuencia**.

**Nota metodológica que vale la pena:** `SBC × 30.4` es la única de las tres lecturas de §D11
que **no depende de la periodicidad**, así que trasladarla de la nómina semanal del caso real a
la quincenal de la demo no agrega un supuesto nuevo. Las otras dos (proyectar el gravado o
acumular el mes calendario) sí habrían necesitado re-justificarse.

---

## D20 · El ausentismo prolongado se advierte, no se trata — PROVISIONAL

El motor cobra **las cuotas completas de cada ramo** sin importar cuánto ausentismo haya, con
la única reducción de días que ya fija §D3. Es la dirección conservadora: cobra de más, nunca
de menos.

**Lo que NO se afirma, y por qué.** El Art. 31 LSS da un tratamiento distinto al ausentismo
prolongado, pero **este repo no tiene el texto del artículo transcrito contra el DOF** y §D3
—de donde salía la lectura— está marcada PROVISIONAL, pendiente de la contadora. Una versión
anterior de esta decisión afirmaba que el artículo "libera al patrón de todas las cuotas". Se
retiró por dos razones. Primero, no hay fuente. Segundo, **se contradice con el propio
motor**: §D3 mantiene Enfermedades y Maternidad a cargo del patrón aun con ausentismo, así que
"todas" no puede ser cierto en la lectura que el código implementa. Como la frase viajaba a la
respuesta del endpoint y al prompt del LLM, el destinatario habría sido el patrón — y tomada
al pie de la letra lo invitaba a dejar de enterar EyM.

**Pregunta para la contadora, y es la que desbloquea esto:** ¿qué dice exactamente el Art. 31
sobre las ausencias prolongadas, qué ramos subsisten en cada supuesto, y desde qué número de
días? Con la respuesta y su cita se puede implementar; sin ella, cobrar completo y advertir es
lo correcto.

**Nota de alcance.** La misma frase sin fuente sigue en §D3 ("la fr. II del Art. 31 libera al
patrón de todas las cuotas…"), donde la dejó F1-03. **No se tocó aquí**: es una nota interna,
la sección ya está marcada PROVISIONAL y pendiente de la contadora, y reescribirla sería
trabajo "de pasada" de otra tarea. Lo que sí importaba —y era lo que D-06 introducía— es que
esa lectura **no** se publique como texto legal en la respuesta de un endpoint ni en el prompt
del LLM. Cuando la contadora conteste, §D3 y §D20 se cierran juntas.

D-06 agrega una **advertencia** en la respuesta cuando un empleado supera 7 días de ausentismo
en el periodo, para que el caso no pase inadvertido.

**Lo que la advertencia NO cubre, y hay que saberlo:** el aviso mira **un periodo a la vez**.
Dos quincenas con 5 faltas cada una suman 10 días en el mes y **ninguna de las dos lo dispara**.
Si el conteo del ausentismo resultara ser **mensual** —la lectura que traía F1-03, sin fuente
verificada, ver arriba— haría falta un acumulado que hoy no existe: el almacén de asistencia es
por periodo y en memoria.

**Pregunta para la contadora:** ¿sobre qué ventana se cuenta el ausentismo, y quién lleva el
acumulado cuando la nómina es quincenal? Y **para F1-09**: si la ventana es mensual, la
persistencia tiene que permitir consultarla.

---

## D21 · Qué muestra "Calendario" en una cuenta de despacho — RESUELTA (E-07)

**Contexto (E-01).** El sidebar del contador lleva cuatro entradas, y una es **Calendario**.
La pantalla detrás es el tab de calendario de Fiscalito, que llama a
`POST /api/v1/calendario`. Ese endpoint valida `contributor_type` contra un set de cinco
(`app/routes/calendario.py:19`) y responde **400** con cualquier otro valor; `contador` no
está en el set, y el front lo mandaba tal cual. El sidebar se veía correcto y el primer clic
pintaba un banner de error.

**Decisión provisional, la conservadora:** "Calendario" muestra las **obligaciones propias del
despacho**. Un despacho, con los dos regímenes que E-01 le permite (612 y 626), es persona
física, así que sus obligaciones son las de un **independiente** con ese régimen. El mapeo
vive en el front (`tipoParaCalendario` en `services/fiscalAgentApi.ts`), con test, y **no toca
el backend ni `docs/api-contract.md`**.

**La alternativa que NO se implementó**, y por la que hay que preguntar antes de planear
E-02/E-03: que "Calendario" signifique el **calendario patronal de sus clientes** — pago
mensual del día 17, bimestral, avisos de modificación de variables. Eso es **F1-06
(`calendario_laboral.py`), que todavía no existe**. Si la respuesta es ésa, el enlace del
sidebar cambia de destino y la tarea que lo habilita es F1-06, no una de la Épica E.

**Que quede claro para quien planee E-02 y E-03:** hoy "Calendario" NO significa nada
patronal. No se puede asumir que ya cubre las obligaciones IMSS de los clientes.

### Resolución (E-07, 2026-09-02)

**Se tomó la alternativa: "Calendario" es el calendario PATRONAL de los clientes.** La tarea
habilitante era F1-06, que E-07 entregó parcialmente (`nomina_engine/calendario_laboral.py` y
`plazos_patronales.py`). El enlace del sidebar apunta ahora a `/app/calendario`, que consume
`GET /api/v1/despacho/calendario` y muestra las obligaciones de toda la cartera agrupadas por
fecha límite.

**Y con eso cae la otra mitad de la decisión, que no era opcional.** Una cuenta de despacho
**deja de tener calendario de contribuyente**: `getTabsForProfile('contador')` devuelve `[]` y
`FiscalitoServicePage` redirige a `/app/calendario`. No es un capricho de alcance — E-05 dejó de
pedirle RFC y régimen al despacho *y quitó del perfil el único lugar donde capturarlos*, y
`CalendarioTab` corta en seco sin esos dos campos. Mantener el enlace habría dejado un tab muerto
con letrero. `tipoParaCalendario` conserva su entrada `contador` sólo como guarda de
exhaustividad del `Record`, y su comentario dice que quedó inalcanzable por construcción.

**Consecuencia declarada, y es una decisión abierta para Ricardo:** *la app ya no calcula las
obligaciones fiscales propias del despacho* (su ISR e IVA como persona física con régimen 612 o
626). Si algún día se quieren, hay que volver a pedirle RFC y régimen en el onboarding y en el
perfil. **La pantalla se lo dice al contador**, no sólo este documento: el calendario patronal
lleva una línea fija que aclara que es el de sus clientes y que la app no calcula las del
despacho.

---

## D22 · La clase de riesgo de los clientes sintéticos es un supuesto — PROVISIONAL

**Contexto (E-02).** La cartera de la demo lleva dos clientes inventados —una cafetería y un
taller de reparación de vehículos— y cada uno necesita una prima de Riesgos de Trabajo para
que su nómina se pueda calcular.

**Lo que SÍ tiene fuente:** la **prima media por clase** está publicada en el Art. 73 LSS y ya
vivía en el motor (`prima_media_clase()` en `nomina_engine/tablas_imss.py`, documentada en
`knowledge_base/nomina/22_cuotas_imss_infonavit_2026.md`). E-02 la **lee de ahí**, no la
retipea: clase II (1.13065 %) para la cafetería y clase III (2.59840 %) para el taller.

**Lo que NO tiene fuente, y por eso esto es provisional:** la asignación **giro → clase**. Sale
del catálogo de actividades del RACERF, que no está en el repo. Afirmar "una cafetería es clase
II" sería declarar con fundamento algo que no se puede citar.

**Decisión:** se conservan esas primas, pero la clase viaja **declarada como supuesto**: el
código lo marca con `# DECISIÓN PROVISIONAL (nocturno):`, el campo `clase_riesgo` del contrato
lo dice, y la ficha del cliente lo imprime literalmente como *"2 (supuesta)"*. Nadie que mire la
pantalla puede confundirlo con un dato clasificado.

**Pregunta para la contadora:** ¿en qué clase clasifica el IMSS a un establecimiento de
preparación de alimentos y bebidas, y a un taller de reparación de vehículos automotores?

**Y lo que hay que recordar para un cliente de verdad:** la prima **la autodetermina el patrón
cada febrero** con su siniestralidad del ejercicio anterior (Art. 74 LSS). Es dato de entrada,
**no derivable del giro** — la clase sólo fija la prima media de una empresa nueva.


---

## D23 · La prima de RT no se corre al siguiente día hábil — PROVISIONAL

**Contexto (E-07 / F1-06).** La Declaración Anual de Prima de Riesgo de Trabajo se presenta
**durante febrero, a más tardar el último día** (Art. 74 LSS; Art. 32 RACERF). En **2026 el
último día de febrero cae en sábado 28**, o sea en un día en que el trámite no se puede
presentar.

**El planteamiento honesto, que una versión anterior de esta entrega tenía mal.** El Art. 3 del
RACERF —el que prorroga al siguiente día hábil los plazos que vencen en día inhábil o viernes—
**sí le alcanza a esta obligación**: se presenta bajo el Art. 32 del mismo reglamento y no es un
aviso afiliatorio, que es lo único que ese artículo excluye. Decir "el Art. 3 la excluye" era
citar una fuente que dice lo contrario.

**Decisión provisional, y la razón es conservadora, no legal:** `calendario_laboral.py` **no**
aplica la prórroga y reporta el **28 de febrero**. Correr la fecha al lunes 2 de marzo es la
dirección **permisiva** —le diría al patrón que tiene dos días más de los que este repo puede
sostener con cita—, y la doctrina del proyecto en materia de plazos es contar de menos, nunca de
más (misma razón que §D13 y que la omisión de la jornada electoral en `dias_habiles.py`).

Para que la fecha no engañe, la obligación viaja con `regimen_de_plazo = "imss_sin_prorroga"`
—un valor propio del enum, no `"imss"`, que promete una prórroga que aquí no ocurre— y con una
`nota` que dice que cae en sábado y que la decisión es provisional.

**Pregunta para la contadora, y es la que cierra esto:** la declaración anual de prima de riesgo
cuyo último día cae en sábado, ¿vence ese sábado o el siguiente día hábil? Y si es lo segundo,
¿es por el Art. 3 del RACERF o por otra regla?

**Qué cambia con cada respuesta.** Si vence el siguiente hábil, `fecha_limite_prima_riesgo()`
pasa a envolver su resultado en `prorroga_racerf()` y el `regimen_de_plazo` vuelve a `"imss"`;
el test que hoy fija el 28-feb-2026 se invierte. Si vence el sábado, esto deja de ser provisional
y la nota se queda como advertencia operativa.

---

## D24 · Qué obligaciones emite el calendario patronal, y cuáles no — PROVISIONAL

**Contexto (E-07).** El calendario patronal de un despacho se arma por cliente, y el modelo de
cliente de la demo (`despacho_demo.ClienteDespacho`) **no registra RFC, ni estado, ni
personalidad jurídica, ni el tipo de salario de los trabajadores**. Cada una de esas ausencias
decide si una obligación se puede afirmar, se afirma con reservas, o no se emite.

**Lo que se emite firme:** entero mensual del IMSS y bimestral de RCV/Infonavit (Art. 39 LSS),
entero del ISR retenido de salarios (LISR Art. 96), declaración anual de prima de RT (§D23) y
aguinaldo (LFT Art. 87).

**Lo que se emite CONDICIONAL, con nota.** `condicional: true` no significa "opcional": significa
"verifícalo, porque aquí no consta".

1. **Aviso bimestral de modificación de la parte variable del SBC** (Art. 34 fr. II LSS). El
   modelo no registra el tipo de salario. `None` en el motor es *no se sabe*, **no** *no tiene*:
   la cartera de la demo es toda de salario fijo, pero eso es una propiedad de los datos de
   demostración, no un hecho sobre un patrón real.
2. **PTU** (LFT Art. 122). El plazo depende de si el patrón es persona moral (30 de mayo) o
   física (29 de junio), y eso no consta, así que **se emiten las dos fechas** marcadas.

**Lo que NO se emite, y por qué:**

- **ISN (Impuesto Sobre Nóminas).** Es estatal, la tasa y la fecha varían por entidad, y
  `knowledge_base/` **no tiene ninguna fuente estatal** —ni el Código Financiero de Veracruz ni
  otro— ni el modelo registra el estado del patrón. Escribir "día 10 o 17 según la entidad" sería
  un valor legal sin cita. **Ojo:** §D8 decide no calcular su *importe* y no dice nada de la
  fecha; el argumento de aquí es la falta de fuente, no §D8. El doc 25 §4 prometía que el
  calendario sí lo mostraría como vencimiento: **se corrigió en el mismo entregable**.

**Y una que sí se emite pero con la regla acotada:** el **entero del ISR retenido** se rige por el
CFF Art. 12 (siguiente día hábil, **sin** la regla del viernes del IMSS) y **sin el ajuste por
sexto dígito del RFC**, que es una facilidad de la RMF y sólo puede correr la fecha hacia
adelante. El modelo no guarda el RFC del cliente, así que omitirla deja la fecha igual o antes de
la legal — conservador. Por eso las cuotas de marzo de 2026 vencen el **20-abr** y su ISR el
**17-abr**: dos fechas, dos reglas, y el campo `regimen_de_plazo` existe para que ninguna vista
las presente como si fueran la misma.

**Preguntas para la contadora:** (1) ¿el ISN de un patrón de Veracruz vence el día 10 o el 17, y
cuál es la fuente? (2) ¿Hay alguna obligación patronal recurrente que este calendario esté
omitiendo?

**Y para F1-09**, que es quien pone clientes reales: registrar RFC, estado, personalidad jurídica
y tipo de salario convierte casi todo lo condicional de arriba en firme, y habilita el ajuste por
sexto dígito.

## D25 · El dígito verificador del NSS — ABIERTA, para la contadora

**Contexto.** R-03 restauró el campo NSS en el alta de empleado (`ModalEmpleado`), con
validación en `apps/store/src/services/nss.ts`. El NSS son 11 dígitos: 10 de payload y uno
verificador, calculado con el **algoritmo de Luhn** (módulo 10, ISO/IEC 7812-1).

**El problema.** No se encontró **norma primaria del IMSS publicada** que especifique ese
algoritmo. Lo que hay son fuentes secundarias. No es DOF, no es un anexo, no es un acuerdo.
Y en la dirección contraria hay evidencia dura *dentro del repo*:
`apps/api/tests/xsd/nomina12.xsd` declara `NumSeguridadSocial` con `use="optional"` y patrón
`[0-9]{1,15}` — el complemento de nómina del SAT **se timbra sin exigir dígito verificador y
sin exigir once dígitos**.

**Qué se hizo mientras tanto**, y la asimetría es deliberada:

| Caso | Conducta | Razón |
|---|---|---|
| vacío | guarda | el campo es opcional, y es la salida del contador que no tiene el número |
| no numérico, o longitud ≠ 11 | **bloquea** | es lo que Ricardo pidió, es inequívoco, y no hay ninguna transformación que "haga pasar" el dato |
| 11 dígitos, verificador no casa | **advierte y guarda** | ver abajo |

**Por qué el verificador no bloquea.** Bloquearlo empujaría al contador que tiene el NSS real
en la mano a teclear uno que sí pase Luhn — un NSS **inventado** puesto junto a datos reales,
que es exactamente lo que `app/routes/despacho.py` argumenta que nunca debe pasar ("un NSS de
11 dígitos bien formado es el NSS de alguien"). Sería construir la presión que ese docstring
existe para evitar, y además con un validador más estricto que el del SAT y con la norma sin
publicar de nuestro lado. El empleado guardado así lleva insignia **"Por verificar"** en
`EmpleadosTab`: advertir no es callar.

**Lo que hace seguro bloquear por longitud es que vacío siempre guarda.** Si esa salida
desapareciera, el bloqueo por longitud tendría que caerse con ella.

**Las dos preguntas para la contadora** — son dos, no una:

1. **¿El dígito verificador del NSS es efectivamente Luhn, y el IMSS lo confirma por escrito?**
   Si hay fuente primaria, se cita aquí y en `nss.ts`, y se puede reconsiderar el bloqueo.
2. **¿Algún trabajador vigente carga hoy un NSS que no sea de 11 dígitos?** Existen
   asignaciones antiguas previas al dígito verificador. Si las hay entre los clientes del
   despacho, **el bloqueo por longitud está mal** y tiene que bajar a advertencia. Esta
   pregunta es tan de contadora como la primera y no se puede contestar desde el código.

**Hallazgo colateral: las fixtures anonimizadas del repo no pasan este validador.** De los 9
NSS distintos en `apps/api/tests/fixtures/nomina/**/*.xml`, **7 fallan el dígito
verificador** (`01010101011`, `...022`, `...033`, `...055`, `...066`, `...088`, `...099`);
sólo `01010101044` y `01010101077` cuadran. Es esperable: son sintéticos evidentes
—`scripts/anonimizar_nomina.py` los genera con un patrón `010101010XX` y **no** aplica
Luhn— y **eso es bueno para la privacidad**: ningún NSS de las fixtures puede ser el de una
persona. Pero tiene una consecuencia concreta:

> **Cuando R-07 agregue el validador de pydantic con este mismo vector, esas fixtures
> empezarán a advertir.** No a fallar —advertir no bloquea— pero ensuciará la salida de los
> tests del caso real. Las dos salidas son: regenerar las fixtures con el verificador
> correcto (`anonimizar_nomina.py` aplicando Luhn), o eximir explícitamente a las fixtures.
> **No se decide aquí**, se deja anotado para que quien haga R-07 no lo descubra con la
> suite en amarillo.

**Cómo se cambia.** Es una constante: `BLOQUEA_VERIFICADOR` en `nss.ts`. Está aislada a
propósito para que la política sea una línea y no una cacería por el formulario.

**Consecuencia declarada:** el criterio literal de R-03 ("inválido bloquea con mensaje claro")
queda **cumplido para el formato y desviado para el verificador**. Es desviación consciente,
no descuido.

---

## D26 · El periodo PARCIAL de un alta o una baja — ABIERTA, para la contadora

**Contexto.** O-03 abre la periodicidad de pago a semanal, quincenal y mensual, y para que eso
sea seguro sube al motor una guarda que **rechaza un periodo cuya duración no case con su
clave** (`nomina_engine/duracion_periodo.py`). Sin ella, `backlog.md` §G puntos 3 y 6
describen el agujero: un patrón Mensual con base de 15-16 días recibe la tarifa mensual del
Art. 96 —**ISR subestimado, con recibo creíble y sin un solo error**— y el simétrico, tarifa
quincenal sobre base mensual.

**El efecto colateral, que es esta decisión.** La guarda también bloquea un caso **legítimo**:
un alta o una baja a mitad de periodo produce un periodo corto real, que hasta O-03 sí se
calculaba. Alguien que entra el 20 de agosto tiene 12 días trabajados de una quincena de 16.

**La pregunta abierta.** ¿Cómo se retiene el ISR de un periodo parcial?

1. **Tabla del Art. 96 de la periodicidad completa, sobre la base parcial.** Es lo que hacía
   la app antes, y es lo que produce el error que la guarda viene a evitar: los límites
   inferiores de la tarifa quincenal suponen 15 días de ingreso.
2. **Prorrateo**: proyectar el ingreso a la periodicidad completa, aplicar la tarifa, y
   retener la parte proporcional. Es lo que hacen varios despachos.
3. **Tarifa diaria (clave 01) por los días trabajados.** El Anexo 8 sí la publica.

**Lo que se hizo mientras tanto — DECISIÓN PROVISIONAL (nocturno):** se **bloquea**. Es la
opción conservadora: cobrar de más o de menos en silencio es peor que no calcular. El motor
responde 422 y **su mensaje distingue las dos causas** —la clave equivocada y el periodo
parcial— porque tienen arreglos opuestos: si sólo dijera "no cuadra", el operador iría a
cambiar la periodicidad del patrón, que es el dato bueno, y lo dejaría mal configurado para
siempre.

**Es una regresión funcional declarada**, no un descuido: la app calculaba esos periodos ayer
y hoy los rechaza. Se prefiere así porque lo que calculaba era, precisamente, lo que el punto
1 describe.

**Qué desbloquea esto.** La respuesta de la contadora, o una decisión de producto de Ricardo.
Cuando llegue, el cambio es acotado: `duracion_periodo.py` deja de levantar para el caso
parcial y el motor aplica la regla elegida.

**Relación con lo ya decidido.** §D10 explica por qué catorcenal y decenal no tienen tarifa;
§D18 por qué la vigencia se lee de la fecha de pago. Ninguna de las dos cubre este caso.
`PLAN_NOMINA.md` §5 lo roza al listar las preguntas para la contadora, sin llegar a él.

---

## D27 · La quincena de 13 días de febrero: ¿se pagan 13 o 15? — ABIERTA, para la contadora

**Lo levantó el revisor de motor de O-03**, y es una pregunta que ninguna decisión previa
cubre.

**El hecho.** La guarda de `duracion_periodo` bendice el rango **13 a 16 días** para la clave
`04`, porque ésos son los extremos que produce el calendario: del 16 al 28 de febrero en año
común son 13 días. Y `dias_pagados = dias_periodo − faltas` (§D20 y `periodo.py`) hace que en
esa quincena se paguen **13 días de salario** contra una tarifa quincenal que
`tablas_isr_periodicas.py` deriva a **exactamente 15**.

**La tensión, dicha de frente.** El docstring de `duracion_periodo.py` rechaza 17 días con el
argumento de que *"tolerarlo era tolerar dos días de base sin tarifa"* — y acepta 13, que son
dos días de base **de menos** contra esa misma tarifa. El rango de calendario está bien y no se
toca: bloquear 13 rompería el periodo que la propia app propone entre el 1 y el 15 de marzo.
Lo que está sin decidir es otra cosa.

**La pregunta.** En la práctica mexicana la quincena se paga **siempre 15 días**, sea febrero o
un mes de 31. ¿Es así en esta empresa?

1. **Pagar los días naturales del periodo** (lo que hace hoy): 13 en la segunda quincena de
   febrero, 16 en la de un mes de 31.
2. **Pagar 15 siempre**, independientemente de los días naturales.

**Estado.** No se cambió nada: hoy manda la opción 1, que es lo que la app viene haciendo desde
D-06 y lo que cuadra con el caso real de S-04. **Mueve un número en cada febrero**, así que
tiene que decidirse antes de la primera nómina de febrero, no antes.

**La palanca ya existe.** `dias_pagados_override` de `calcular_periodo` implementa la opción 2
sin tocar el motor: se le pasa 15 y pisa `dias_periodo − faltas` para toda la plantilla. Lo que
falta es la decisión, no el código.

**Relación con lo demás.** §D26 cubre el periodo PARCIAL de un alta o una baja, que es otro
caso: ahí el periodo es corto porque la persona no estuvo todo el periodo. Aquí estuvo completo
y el periodo mismo es corto.

---

## D28 · Reintegrar la plantilla: ¿manda el patrón o la prestación negociada? — ABIERTA, para la contadora

**El hecho.** La ficha de cada empleado guarda sus propias `prestaciones` —días de aguinaldo,
días de vacaciones, prima vacacional— y `ModalEmpleado` las pinta **editables**: se siembran
de los parámetros del patrón al dar de alta, y el operador puede pisarlas para un caso
particular. O-03 lo dejó así a propósito.

Cuando el patrón cambia sus parámetros en Configuración de empresa, la acción **Reintegrar la
plantilla** (O-cierre) vuelve a pedirle el SBC al motor para cada empleado. Y ahí aparece la
pregunta: ¿con qué prestaciones?

**Las dos lecturas, y por qué ninguna es obviamente la buena.**

1. **Manda el patrón.** Es lo que hace útil el formulario: subir el aguinaldo de 15 a 30 y que
   la plantilla entera se reintegre. Pero **pisa en silencio** al trabajador que tiene 30 días
   negociados en una empresa que da 15: su SBC **bajaría**, y las cuotas saldrían
   subintegradas — la dirección exacta que esta app trata como la mala en todos lados. Y la
   ficha quedaría diciendo 30 mientras el SDI ya refleja 15: dos datos en desacuerdo.
2. **Manda la ficha del empleado.** No pisa a nadie, pero entonces cambiar el aguinaldo del
   patrón **no propaga a nadie**, porque cada ficha se sembró con el valor viejo el día del
   alta. El formulario de O-03 quedaría decorativo otra vez, que es justo el defecto que
   O-cierre venía a cerrar.

**Lo que se hizo, y es provisional.** Ni una ni otra: **el parámetro del patrón es un piso, no
un reemplazo.** Para cada empleado se integra con `max(patrón, ficha)` en días de aguinaldo y
prima vacacional. Así:

- Subir el aguinaldo del patrón **sí** propaga a toda la plantilla.
- Al trabajador con 30 negociados en una empresa de 15 **no se le baja nada**.
- Y como red final: si aun así el SBC nuevo resultara **menor** que el guardado, **no se
  escribe**. Se reporta aparte, para que una persona lo mire.

**El fundamento de tratarlo como piso.** La política del patrón es una prestación mínima
general; el contrato individual puede mejorarla y no empeorarla (Arts. 33 y 56 LFT, derechos
adquiridos). Bajar una prestación ya otorgada no es algo que una pantalla deba hacer sola, y
mucho menos en lote.

**Ojo: de las tres prestaciones, una no se puede honrar hoy.** Los **días de vacaciones** por
empleado son **inertes** cuando el patrón tiene tabla —y en la ruta normal siempre la tiene—:
`routes/nomina.py` resuelve los días con `dias_vacaciones_efectivos(antigüedad, tabla)` e ignora
el `dias_vacaciones` del request. Así que alguien con 25 días negociados, en una empresa cuya
tabla da 12 al año 1, integra con 12: **subintegrado respecto de lo que el patrón otorga**
(Art. 27 LSS). No lo introdujo O-cierre —es un hueco de O-03, y vale igual en `ModalEmpleado`
que al reintegrar— pero se dice aquí porque este documento formula la pregunta como si las tres
prestaciones se comportaran igual, y no lo hacen. El modal sí pinta
`dias_vacaciones_aplicados`, así que al menos se ve.

**La pregunta para la contadora.** ¿Hay en Orca gente con prestaciones negociadas **por encima**
de la política de la empresa? Si la respuesta es **no**, la opción 1 es más simple y los tres
inputs por empleado de `ModalEmpleado` sobran — habría que quitarlos o volverlos de sólo
lectura, porque la app no puede ofrecer un campo que después pisa. Si es **sí**, lo que hay hoy
se queda y conviene que la ficha muestre cuál de los dos valores se usó.

**Lo que NO se resolvió con esto.** Reintegrar cambia el SBC, y **cada cambio de SBC es un
aviso de modificación de salario ante el IMSS (movimiento 07)**. La app lo dice en pantalla y
no lo puede generar: O-04 dejó el 07 abierto por falta de dato (no hay historial de SBC en el
modelo). O sea, hoy la app te ayuda a saber **que** el aviso hace falta y no a presentarlo.
Ésa es otra decisión, y es de las caras.
