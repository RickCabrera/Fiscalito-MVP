# 23 · ISR de sueldos y salarios y subsidio para el empleo

> **Documento de referencia, no fuente de cálculo.** El motor calcula desde
> `app/fiscal_engine/tablas_isr.py` y `app/nomina_engine/isr_nomina.py` /
> `tablas_isr_periodicas.py`. Este archivo no es fuente de cálculo ni de tool calling.

> ⚠️ **Este documento NO contiene las tarifas del Anexo 8 de la RMF.** Las tablas por
> periodicidad (semanal, decenal, catorcenal, quincenal) se versionan en código, con su
> fuente, en `nomina_engine/tablas_isr_periodicas.py` — tarea **F1-01**. **No calcular ISR
> desde aquí.** Lo que este archivo fija es *qué* tarifa aplica, *por qué*, y cómo se
> combinan exención, tarifa y subsidio.

**Alcance:** lo que se retiene al trabajador en el recibo. Los importes de UMA y del subsidio,
con sus vigencias, están en `20_valores_referencia_2026.md`.

**Régimen:** Título IV, Capítulo I de la LISR — ingresos por salarios y en general por la
prestación de un servicio personal subordinado (régimen SAT **605**).

---

## 1. Orden de cálculo

```
1. base_gravable = Σ percepciones gravadas del periodo   (total − exento del Art. 93)
2. isr_causado   = tarifa Art. 96 LISR aplicable a la periodicidad
3. subsidio      = subsidio_empleo(fecha, ingreso_gravado_mensual, dias_del_periodo)
4. isr_retenido  = max(isr_causado − subsidio, 0)
```

El paso 4 es donde el esquema vigente desde 2024 difiere del histórico: el subsidio **solo
reduce el ISR hasta cero**; el remanente ya **no** se entrega en efectivo al trabajador.

Las tres entradas con fecha —UMA para las exenciones, tarifa por periodicidad, porcentaje del
subsidio— se resuelven **a la fecha de pago**, no a la de cálculo.

---

## 2. Exenciones del Art. 93 LISR (expresadas en UMA)

Los topes se expresan en **veces la UMA diaria vigente a la fecha del pago** — de nuevo, enero
usa la UMA 2025.

> **Por qué UMA y no salario mínimo.** El Art. 93 dice literalmente *salario mínimo*. El
> **Decreto de desindexación (DOF 27-01-2016)** y el Art. 26 apartado B constitucional
> convirtieron esas referencias en UMA. Sin ese eslabón, "30 veces el SM" daría $9,451.20 de
> aguinaldo exento en vez de $3,519.30 (importes **derivados** de los valores del doc 20 §1 y
> §2): un factor de 2.69 de diferencia en cada exención.

| Percepción | Exento hasta | Fundamento |
|---|---|---|
| Aguinaldo | **30 UMA** | Art. 93 fr. XIV |
| Prima vacacional | **15 UMA** | Art. 93 fr. XIV |
| PTU | **15 UMA** | Art. 93 fr. XIV |
| Prima dominical | **1 UMA por domingo trabajado** | Art. 93 fr. XIV |
| Tiempo extra, **trabajador de salario mínimo** | **100 %**, dentro de los límites de la LFT | Art. 93 fr. I |
| Tiempo extra, **los demás trabajadores** | **50 %**, sin exceder **5 UMA por semana** y dentro de los límites de la LFT | Art. 93 fr. I |
| Previsión social (vales, fondo de ahorro, ayudas) | topes propios de la fracción, con el límite conjunto de 7 UMA | Art. 93 fr. VIII y IX y penúltimo párrafo |
| Indemnizaciones por riesgo de trabajo o enfermedad | conforme a la ley o al contrato | Art. 93 fr. III |

**El excedente de cualquiera de estas exenciones es gravado** (Art. 93 fr. II) y entra a la
base. La misma percepción se parte en `ImporteGravado` / `ImporteExento` en el CFDI (ver
`24_cfdi_nomina_12.md`).

**Los límites de la LFT para el tiempo extra** (Art. 66: máximo 3 horas diarias y 3 veces por
semana) acotan la exención: las horas extra que exceden esos límites se pagan al triple y son
**100 % gravadas**.

> **El trabajador de salario mínimo aparece tres veces, con reglas independientes.** No
> retención de ISR (Art. 96, último párrafo); tiempo extra 100 % exento (Art. 93 fr. I); y el
> patrón absorbe su cuota obrera del IMSS (Art. 36 LSS). Son tres normas distintas que
> coinciden en el mismo empleado — F1-04 debe aplicarlas por separado, no como una sola.

## 3. Tarifa del Art. 96 LISR

La tarifa **mensual** del Art. 96 ya existe en el motor fiscal:
`app/fiscal_engine/tablas_isr.py` → `TABLA_ISR_MENSUAL`. El recibo de nómina la **reutiliza**;
no se duplica.

Para periodicidades menores al mes (semanal, decenal, catorcenal, quincenal) hay dos caminos:

1. **Tablas periódicas del Anexo 8 de la RMF** — una tarifa publicada por periodicidad.
2. **Prorrateo** de la tarifa mensual (`÷ 30.4 × días`).

**Decisión adoptada (`docs/decisiones-nomina.md` §D1):** usar las **tablas del Anexo 8** según
la periodicidad del CFDI y validar contra el ISR retenido de las fixtures del caso real
(S-04, periodicidad semanal). Si no cuadra, se prueba el prorrateo y se documenta cuál cuadró.

> **Por qué este archivo no transcribe las tablas periódicas.** Los valores numéricos del
> Anexo 8 son código, no prosa: viven versionados en `nomina_engine/tablas_isr_periodicas.py`
> con su fuente en el docstring, y esa es exactamente la tarea **F1-01**. Transcribirlos aquí
> a mano crearía una segunda copia sin tests que se desincronizaría en la primera
> actualización. Lo que sí fija este archivo es **qué tabla aplica y por qué**.

---

## 4. Subsidio para el empleo

**Los importes, porcentajes, vigencias y fuentes viven en `20_valores_referencia_2026.md`
§4.** Aquí solo la mecánica; duplicar los números es exactamente cómo se desincronizan.

```
si ingreso_gravado_mensual > tope_subsidio(fecha)  ->  subsidio = 0
si periodo == mes completo                         ->  subsidio = subsidio_mensual(fecha)
si periodo < mes                                   ->  subsidio = subsidio_mensual(fecha) / 30.4 * dias
isr_retenido = max(isr_causado - subsidio, 0)
```

Puntos que el motor no puede equivocar:

- `subsidio_mensual(fecha)` se **calcula** como `porcentaje_vigente(fecha) x uma_mensual_vigente(fecha)`.
  El Decreto fija el porcentaje, no el peso (ver la advertencia del doc 20 §4).
- **Enero tiene porcentaje propio** (artículo transitorio) *y* UMA propia (la del año
  anterior). Son dos vigencias distintas que coinciden en el mismo mes.
- El tope de ingresos es un **corte duro**: un peso por encima deja al trabajador sin
  subsidio, no con subsidio reducido.
- El subsidio **solo reduce el ISR hasta cero**. Desde 2024 el remanente no se entrega en
  efectivo, así que nunca produce un neto mayor al bruto.
- En el CFDI el subsidio va en **OtrosPagos** (clave 002), con el nodo `SubsidioAlEmpleo` y su
  `SubsidioCausado` — no es una percepción. Ver `24_cfdi_nomina_12.md`.

## 5. A dónde va el ISR retenido

El patrón **entera** el ISR retenido en su declaración mensual (día 17 del mes siguiente, con
el ajuste por sexto dígito del RFC). Ese es el puente con el módulo fiscal ya existente:

- Output de nómina (ISR retenido por empleado y por periodo)
  → input de `app/fiscal_engine/retenciones.py` y de la pre-declaración mensual del patrón.
- Los CFDI de nómina timbrados son, para el patrón, **egresos deducibles** que entran a
  `calculadora.py` (requisito de deducibilidad: estar efectivamente pagados y timbrados,
  Art. 27 LISR).

---

## 6. Casos que el motor debe manejar sin sorpresas

- **Trabajador con 1 salario mínimo**: las tres reglas del recuadro de §2 aplican a la vez y
  ninguna implica a las otras.
- **Aguinaldo y finiquito**: percepciones no ordinarias que pueden calcularse con el
  procedimiento del **Art. 174 RLISR** (opcional) en vez de acumularse sin más al mes.
  Fuera del alcance de F1-04 salvo que el caso real lo exija.
- **Enero**: UMA 2025 para las exenciones **y** subsidio con el porcentaje transitorio. Es el
  mes donde más motores fallan.

---

## Fuentes

- LISR: Arts. 27, 93 (fr. I, II, III, VIII, IX, XIV), 96, 152. RLISR Art. 174.
- Decreto de desindexación del salario mínimo — DOF 27-01-2016; Art. 26 apartado B
  constitucional (lectura en UMA de los topes del Art. 93).
- LFT Art. 66 (límites del tiempo extraordinario).
- Decreto que modifica el subsidio para el empleo — DOF 31-12-2025.
- Anexo 8 de la RMF 2026 — tarifas por periodicidad (los valores se versionan en F1-01).
- `docs/PLAN_NOMINA.md` §2.6; `docs/decisiones-nomina.md` §D1, §D2.
