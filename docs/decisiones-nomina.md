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

## D3 · Ausentismos e incapacidades — PROVISIONAL

Aplicar el **Art. 31 LSS** literal: las ausencias de hasta 7 días al mes descuentan días en
todos los ramos **excepto Enfermedades y Maternidad**; durante una incapacidad solo se cotiza
EyM. Confirmar con la contadora.

## D4 · Quirk CEAV 2026 — PROVISIONAL

Aplicar la tabla literal por rango de UMA. El salario mínimo exacto cae en **3.150%**. Los
renglones inalcanzables se dejan en la tabla, sin lógica especial que los excluya.

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
