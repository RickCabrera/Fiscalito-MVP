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
responsabilidad es del llamador (F1-04), y el docstring lo dice. Hay que cerrarla antes de
cuadrar el ISR del caso real.

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
desde el `SalarioBaseCotApor` del propio comprobante con las tasas de ley. Solo 2 de 9
empleados cuadran.

| Empleado | SBC timbrado | Deducción observada | Tasa obrera implícita |
|---|---|---|---|
| ...AA1 | 331.58 | 55.13 / 55.12 | **2.3752 %** ✅ |
| ...AA2 | 357.44 | 57.09 | 2.2817 % |
| ...AA3 | 399.52 | 68.10 / 68.09 | 2.4351 % |
| ...AA4 | 399.05 | 66.63 | 2.3853 % |
| ...AA5 | 343.00 | 57.28 | 2.3857 % |
| ...AA6 | 346.11 | 57.06 | 2.3552 % |
| ...AA7 | 387.23 | 64.46 | 2.3781 % |
| ...AA8 | 331.58 | 55.13 / 55.12 | **2.3752 %** ✅ |
| ...AA9 | 358.34 | 57.21 | 2.2808 % |

La tasa obrera de ley es **2.3750 %** (EyM prestaciones en dinero 0.25 + EyM gastos médicos de
pensionados 0.375 + IyV 0.625 + CEAV 1.125), más 0.40 % sobre el excedente de 3 UMA cuando
aplica.

### La prueba de que el problema es el dato de entrada, no la fórmula

Tres empleados tienen una deducción **por debajo del mínimo legal** que impone su propio SBC
timbrado:

| Empleado | SBC | Mínimo legal (2.375 % × 7 días) | Observado | Diferencia |
|---|---|---|---|---|
| ...AA2 | 357.44 | 59.42 | 57.09 | **−2.33** |
| ...AA6 | 346.11 | 57.54 | 57.06 | −0.48 |
| ...AA9 | 358.34 | 59.57 | 57.21 | **−2.36** |

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

### Qué se hizo en el código

`cuotas.py` cuadra contra **la fórmula de ley**, ramo por ramo. En
`tests/nomina/test_cuotas_caso_real.py` hay dos clases de test y **las dos pasan**, sin skips
ni `xfail`: el cuadre estricto de los dos empleados que sí se reproducen (las nueve semanas), y
la **caracterización** de los siete que no, con sus importes observados como literales. Si
alguien "arregla" el motor y esos siete empiezan a cuadrar, el test truena y obliga a explicar
qué cambió.

### Lo que S-04 no cubre, para que nadie lo asuma

Las fixtures van del **8-mar-2026 al 3-may-2026**, así que **no ejercitan el transitorio de
enero** (ni el de la UMA ni el del subsidio). Todos los recibos traen `NumDiasPagados=7.000` y
no hay ni una incapacidad, así que **S-04 no puede validar §D3**. Y el subsidio para el empleo
viene con `Importe="0"` en todos, así que **tampoco va a cerrar §D11**.
