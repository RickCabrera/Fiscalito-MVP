# 22 · Cuotas obrero-patronales IMSS e Infonavit 2026

> **Documento de referencia, no fuente de cálculo.** El motor calcula desde
> `app/nomina_engine/tablas_imss.py` (`CUOTAS_RAMOS[2026]`, `CEAV_PATRONAL[2026]`,
> `PRIMA_MEDIA_CLASE`) y `app/nomina_engine/cuotas.py`. Este archivo no es fuente de cálculo
> ni de tool calling.

**Alcance:** porcentajes por ramo, su base de cálculo y su fundamento legal. Los valores
monetarios (UMA, SM) y sus vigencias están en `20_valores_referencia_2026.md`; el SBC, en
`21_sbc_integracion.md`.

**Vigencia de este archivo:** ejercicio **2026**. La tabla CEAV cambia cada enero durante la
transición 2023–2030 (`CEAV_PATRONAL[2026]`, `[2027]`…). Todo lo demás es porcentaje fijo de
ley y solo cambia con reforma.

---

## 1. Tabla de ramos

Base = SBC, salvo donde se indique. Cuota diaria por trabajador, por día cotizado.

| Ramo | Concepto | Patrón | Obrero | Base | Fundamento |
|---|---|---|---|---|---|
| **Riesgos de Trabajo** | Prima de la empresa | prima % (0.50000–15.00000) | 0 | SBC | Art. 71–74 LSS |
| **Enfermedades y Maternidad** | Cuota fija por trabajador | 20.40 % | 0 | **UMA** | Art. 106 fr. I LSS |
| | Excedente (solo si SBC > 3 UMA) | 1.10 % | 0.40 % | **SBC − 3 UMA** | Art. 106 fr. II LSS |
| | Prestaciones en dinero | 0.70 % | 0.25 % | SBC | Art. 107 LSS |
| | Gastos médicos de pensionados | 1.05 % | 0.375 % | SBC | Art. 25 LSS |
| **Invalidez y Vida** | | 1.75 % | 0.625 % | SBC | Art. 147 LSS |
| **Retiro** | | 2.00 % | 0 | SBC | Art. 168 fr. I LSS |
| **CEAV** (Cesantía en Edad Avanzada y Vejez) | | **tabla 2026** (§3) | 1.125 % | SBC | Art. 168 fr. II LSS + reforma DOF 16-12-2020 |
| **Guarderías y Prestaciones Sociales** | | 1.00 % | 0 | SBC | Art. 211 LSS |
| **Infonavit** | Aportación patronal | 5.00 % | 0 | SBC | Ley Infonavit Art. 29 fr. II |

**Periodicidad de entero:** mensual los ramos de seguro (RT, EyM, IyV, Guarderías) y
bimestral RCV e Infonavit (Art. 39 LSS). Las **fechas límite de 2026** y la regla del día
inhábil viven en `25_calendario_laboral_2026.md` — este archivo no las duplica.

---

## 2. La única base que no es el SBC

La **cuota fija de EyM (20.40 %)** se calcula sobre la **UMA**, no sobre el SBC. Es el error
clásico al implementar el motor: da un número plausible pero equivocado en todos los
trabajadores que no ganan exactamente 1 UMA.

```
cuota_fija_eym = 0.2040 × UMA_diaria_vigente(fecha) × dias_cotizados
```

El **excedente de EyM** solo existe si `SBC > 3 UMA` ($351.93 diarios con UMA 2026) y se
aplica **únicamente sobre la porción excedente**:

```
if SBC > 3 × UMA:
    base_excedente = SBC − 3 × UMA
    patron = 0.0110 × base_excedente × dias
    obrero = 0.0040 × base_excedente × dias
```

---

## 3. Tabla CEAV patronal 2026

Cuarto año de la transición 2023–2030 (en 2030 el tope llega a 11.875 %). Rango determinado
por el SBC del trabajador.

| SBC del trabajador | Patrón 2026 |
|---|---|
| 1.00 SM | 3.150 % |
| 1.01 SM a 1.50 UMA | 3.676 % |
| 1.51 a 2.00 UMA | 4.851 % |
| 2.01 a 2.50 UMA | 5.556 % |
| 2.51 a 3.00 UMA | 6.026 % |
| 3.01 a 3.50 UMA | 6.361 % |
| 3.51 a 4.00 UMA | 6.613 % |
| 4.01 UMA en adelante | 7.513 % |

Cuota obrera de CEAV: **1.125 %** del SBC, sin tabla.

**Fuente:** artículo **transitorio** del Decreto por el que se reforman la LSS y la Ley del
SAR, **DOF 16-12-2020**, que contiene la tabla de la transición 2023–2030 (el Art. 168 fr. II
vigente remite a ella). **Vigencia del renglón 2026:** 1-ene-2026 → 31-dic-2026; es el cuarto
escalón de la rampa.

**Consumidor en código:** `CEAV_PATRONAL[2026]` en `nomina_engine/tablas_imss.py` (tarea
F1-01). Cada enero se agrega el renglón del año nuevo citando el mismo transitorio; los años
anteriores no se borran, porque un recálculo de un ejercicio pasado debe seguir cuadrando.

> Los rangos de la tabla están expresados en **UMA**, así que en **enero** se evalúan contra
> la UMA 2025 y de febrero en adelante contra la UMA 2026: un mismo trabajador puede cambiar
> de renglón el 1 de febrero sin que su salario haya cambiado.

> ⚠️ **Quirk 2026.** El salario mínimo general ($315.04) equivale a ~2.69 UMA, así que los
> renglones "1.01 SM a 1.50 UMA", "1.51–2.00 UMA" y "2.01–2.50 UMA" quedan **por debajo del
> salario mínimo** y son inalcanzables en zona general. Un trabajador con SM exacto cae en
> 3.150 %; el siguiente escalón real es 2.51–3.00 UMA (6.026 %). Decisión adoptada
> (**PROVISIONAL**, `docs/decisiones-nomina.md` §D4): aplicar la tabla literal, dejar los
> renglones inalcanzables sin lógica especial, y confirmar contra la emisión del IMSS (EMA)
> para no divergir del SUA.

---

## 4. Reglas especiales

**El patrón absorbe la cuota obrera del trabajador con SBC de 1 salario mínimo**
(Art. 36 LSS). No es una exención: la cuota se sigue calculando y enterando, solo cambia quién
la paga. En el recibo, ese trabajador no lleva deducción de IMSS.

**Días cotizados.** Los ausentismos e incapacidades reducen los días, con efecto distinto por
ramo (Art. 31 LSS). Tratamiento adoptado y su estado **PROVISIONAL**:
`docs/decisiones-nomina.md` §D3. `dias_cotizados` es input.

**Prima de Riesgos de Trabajo.** Se autodetermina y se declara **anualmente en febrero**
(Declaración Anual de Prima de RT, Art. 74 LSS) con base en la siniestralidad del ejercicio
anterior. Puede variar como máximo un punto porcentual por año, dentro del rango 0.50000 % –
15.00000 %. Empresa nueva: **prima media de su clase**.

| Clase de riesgo | Prima media | Fundamento |
|---|---|---|
| I | 0.54355 % | Art. 73 LSS |
| II | 1.13065 % | ídem |
| III | 2.59840 % | ídem |
| IV | 4.65325 % | ídem |
| V | 7.58875 % | ídem |

**Redondeo.** Por concepto y por empleado, a 2 decimales, al estilo SUA — no al consolidar
(`docs/decisiones-nomina.md` §D2). El motor usa `Decimal` con `ROUND_HALF_UP`.

---

## 5. Consolidación

El motor produce tres niveles, todos derivados del mismo cálculo por empleado/día:

1. **Por empleado y por ramo** — lo que permite conciliar contra la EMA/EBA línea por línea.
2. **Mensual por cliente** — RT + EyM + IyV + Guarderías.
3. **Bimestral por cliente** — Retiro + CEAV + Infonavit (+ amortizaciones).

---

## Fuentes

- Ley del Seguro Social: Arts. 25, 31, 36, 71–74, 106, 107, 147, 168, 211.
- Reforma LSS / Ley del SAR, DOF 16-12-2020 — transición CEAV 2023–2030.
- Ley del Infonavit: Art. 29.
- `docs/PLAN_NOMINA.md` §2.4; `docs/decisiones-nomina.md` §D2, §D3, §D4.
