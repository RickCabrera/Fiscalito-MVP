# 20 · Valores de referencia de nómina 2026

**Alcance:** valores monetarios y topes que el motor de nómina resuelve **por fecha de
vigencia**, no como constantes globales. Todo valor de este archivo lleva vigencia y fuente.

**Regla de diseño (PLAN_NOMINA §2.1):** `constants.py` expone `uma_vigente(fecha)` y
`salario_minimo_vigente(fecha, zona)`. Enero 2026 usa la **UMA 2025**; febrero en adelante
usa la **UMA 2026**. Este corte se repite cada año — nunca hardcodear "la UMA".

---

## 1. UMA (Unidad de Medida y Actualización)

La UMA se actualiza cada año y entra en vigor el **1 de febrero**, no el 1 de enero. Esa
asimetría es la fuente de errores de cálculo más común en enero.

| Valor | Diaria | Mensual (× 30.4) | Anual | Vigencia | Fuente |
|---|---|---|---|---|---|
| **UMA 2026** | **$117.31** | $3,566.22 | $42,794.64 | 1-feb-2026 → 31-ene-2027 | INEGI, Comunicado 1/26; DOF 09-01-2026 |
| **UMA 2025** | **$113.14** | $3,439.46 | $41,273.52 | 1-feb-2025 → 31-ene-2026 | INEGI; DOF 09-01-2025 |

Los valores mensual y anual son **derivados**, no publicados aparte: `mensual = diaria × 30.4`
y `anual = mensual × 12`. El motor los calcula, no los hardcodea.

**Consecuencia operativa:** un cálculo de nómina o de cuotas con fecha de **enero de 2026**
usa $113.14. Uno con fecha de **febrero de 2026 en adelante** usa $117.31. Lo mismo aplica a
todo tope expresado en UMA (tope SBC, exenciones del Art. 93 LISR, multas).

**Dónde se usa la UMA en nómina:**
- Base de la cuota fija patronal de Enfermedades y Maternidad (Art. 106 fr. I LSS).
- Umbral del excedente de EyM: 3 UMA (Art. 106 fr. II LSS).
- Tope máximo del SBC: 25 UMA (Art. 28 LSS).
- Rangos de la tabla CEAV patronal (ver `22_cuotas_imss_infonavit_2026.md`).
- Exenciones de ISR del Art. 93 LISR (ver `23_isr_nomina_subsidio.md`).
- Multas por movimientos afiliatorios extemporáneos: 20 a 350 UMA (Art. 304-B LSS).

---

## 2. Salario mínimo general

| Zona | Diario 2026 | Vigencia | Fuente |
|---|---|---|---|
| **General** (resto del país) | **$315.04** | 1-ene-2026 → 31-dic-2026 | CONASAMI; DOF 09-12-2025 |
| **Zona Libre de la Frontera Norte (ZLFN)** | **$440.87** | 1-ene-2026 → 31-dic-2026 | CONASAMI; DOF 09-12-2025 |

A diferencia de la UMA, el salario mínimo **sí** entra en vigor el 1 de enero. La zona la
determina el domicilio del centro de trabajo, no el del patrón.

> ⚠️ **Discrepancia con `../01_valores_referencia.md`.** Ese archivo (dominio fiscal,
> anterior a este módulo) declara SM general **$278.80** y ZLFN **$419.88**: son los valores
> **de 2025**, no de 2026. También declara la UMA mensual 2025 como $3,439.68 y la anual como
> $41,276.16, cuando `113.14 × 30.4` da $3,439.46 y `× 12` da $41,273.52.
> Para todo cálculo de nómina manda **este** archivo, con las fuentes citadas arriba. La
> corrección de `01_valores_referencia.md` toca el dominio fiscal (deducciones personales usan
> esa UMA) y **no** se hace en F0-01: queda anotada en `docs/nocturno-log.md`.

---

## 3. Piso y tope del SBC (Art. 28 LSS)

| Límite | Valor | Cómo se calcula | Vigencia | Fuente |
|---|---|---|---|---|
| **Piso** | $315.04 diarios | 1 salario mínimo **general** | 1-ene-2026 → 31-dic-2026 | Art. 28 LSS + CONASAMI |
| **Tope** | **$2,932.75** diarios | 25 × UMA diaria ($117.31) | 1-feb-2026 → 31-ene-2027 | Art. 28 LSS + INEGI |
| Tope (enero 2026) | $2,828.50 diarios | 25 × UMA 2025 ($113.14) | 1-ene-2026 → 31-ene-2026 | ídem |

El SBC se acota siempre: `SBC = clamp(SBC_calculado, piso, tope)`. Nótese que **piso y tope se
mueven en fechas distintas**: el piso cambia el 1 de enero y el tope el 1 de febrero.

---

## 4. Subsidio para el empleo 2026

El esquema vigente desde 2024 expresa el subsidio como un **porcentaje de la UMA mensual**, no
como la tabla histórica por rangos de ingreso.

| Concepto | Regla del Decreto | Importe derivado | Vigencia | Fuente |
|---|---|---|---|---|
| Subsidio mensual (régimen general) | **15.02 % × UMA mensual 2026** | 0.1502 × $3,566.22 = **$535.65** | feb-2026 → dic-2026 | Decreto DOF 31-12-2025 |
| Subsidio mensual (transitorio de enero) | **15.59 % × UMA mensual 2025** | 0.1559 × $3,439.46 = **$536.21** | ene-2026 | Decreto DOF 31-12-2025, artículo transitorio |
| Tope de ingresos para tener derecho | — | **$11,492.66** mensuales | ejercicio 2026 | ídem |

> ⚠️ **Discrepancia abierta con `docs/PLAN_NOMINA.md` §2.1.** El plan enuncia la misma regla
> (15.02 % de la UMA mensual) pero anota el importe de feb–dic como **$536.22**. Ese número no
> se reconcilia con su propia fórmula: 15.02 % × $3,566.22 = **$535.65** (harían falta
> 15.036 % para llegar a $536.22). El importe de enero del plan, en cambio, sí cuadra al
> centavo: 15.59 % × $3,439.46 = $536.21. `knowledge_base/01_valores_referencia.md` también
> declara $535.65.
> **Decisión (conservadora, nocturno):** lo verificable es la **regla del Decreto**, no el
> importe transcrito. El motor debe **calcular** el subsidio como `porcentaje × UMA mensual
> vigente` y nunca hardcodear el peso. F1-01, que es la tarea que versiona
> `subsidio_empleo()`, debe confirmar el porcentaje contra el Decreto publicado y cuadrar el
> resultado contra el subsidio acreditado en las fixtures del caso real (S-04). Si el importe
> real fuera $536.22, lo que está mal es el porcentaje, no la aritmética.

Detalles que el motor debe respetar (desarrollo en `23_isr_nomina_subsidio.md`):
- Si el ingreso gravado del mes **excede** $11,492.66, el subsidio es **cero** (no se prorratea
  ni se degrada: es un corte duro).
- Para periodos menores al mes: `subsidio_mensual ÷ 30.4 × días del periodo`.
- El subsidio **solo reduce el ISR hasta cero**. Desde 2024 el excedente ya **no** se entrega
  en efectivo al trabajador.

> El transitorio de enero existe precisamente porque en enero todavía rige la UMA 2025: el
> porcentaje sube (15.59 % vs 15.02 %) para que el importe mensual quede prácticamente igual.
> Un motor que ignore el transitorio y aplique 15.02 % sobre la UMA 2025 da $516.61 — un error
> de ~$19.60 por trabajador en enero, en todos los trabajadores con derecho a subsidio.

---

## 5. Percepciones y prestaciones mínimas de ley (base del factor de integración)

| Prestación | Mínimo de ley | Fundamento |
|---|---|---|
| Aguinaldo | 15 días de salario | LFT Art. 87 |
| Vacaciones | 12 días el primer año, +2 por año hasta 20; luego +2 cada 5 años | LFT Art. 76 (reforma "vacaciones dignas", DOF 27-12-2022, vigente 1-ene-2023) |
| Prima vacacional | 25 % sobre los días de vacaciones | LFT Art. 80 |
| Prima dominical | 25 % adicional sobre el salario del día | LFT Art. 71 |
| PTU | 10 % de la utilidad fiscal, con el tope de la reforma 2021 | LFT Art. 117 y 127 fr. VIII |

El desarrollo del factor de integración está en `21_sbc_integracion.md`.

---

## 6. Tasas y porcentajes de referencia rápida

| Concepto | Valor 2026 | Fuente |
|---|---|---|
| Cuota fija patronal EyM | 20.40 % de la UMA por trabajador/día | Art. 106 fr. I LSS |
| Umbral del excedente EyM | SBC > 3 UMA ($351.93 diarios con UMA 2026) | Art. 106 fr. II LSS |
| Aportación Infonavit | 5.00 % del SBC (100 % patronal) | Ley Infonavit Art. 29 fr. II |
| CEAV patronal | tabla por rango de SBC, 3.150 % – 7.513 % | Art. 168 fr. II LSS + reforma DOF 16-12-2020 |
| CEAV obrera | 1.125 % del SBC | ídem |
| Retiro | 2.00 % del SBC (100 % patronal) | Art. 168 fr. I LSS |
| ISN Veracruz | 3 % sobre remuneraciones (informativo, ver §D8) | Código Financiero del Estado de Veracruz |

El desglose completo por ramo está en `22_cuotas_imss_infonavit_2026.md`.

---

## Fuentes

- INEGI, Comunicado 1/26 — valor de la UMA 2026; publicación en DOF 09-01-2026.
- CONASAMI — Resolución de salarios mínimos 2026; DOF 09-12-2025.
- Decreto que modifica el subsidio para el empleo — DOF 31-12-2025.
- Ley del Seguro Social: Arts. 28, 106, 168, 304-B.
- Ley del Infonavit: Art. 29.
- Ley Federal del Trabajo: Arts. 71, 76, 80, 87, 117, 127.
