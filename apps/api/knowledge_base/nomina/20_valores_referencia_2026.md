# 20 · Valores de referencia de nómina 2026

> **Documento de referencia, no fuente de cálculo.** El motor calcula desde
> `app/constants.py` (`uma_vigente(fecha)`, `salario_minimo_vigente(fecha, zona)`) y
> `app/nomina_engine/`. Este archivo existe para que esos valores tengan fuente y vigencia
> auditables — no es fuente de cálculo ni de tool calling.

**Alcance:** valores monetarios y topes que el motor de nómina resuelve **por fecha de
vigencia**, no como constantes globales. Cada valor lleva su vigencia y su fuente primaria.

**Regla de diseño (PLAN_NOMINA §2.1):** enero 2026 usa la **UMA 2025**; febrero en adelante,
la **UMA 2026**. El salario mínimo, en cambio, cambia el 1 de enero. Nunca hardcodear "la
UMA" ni "el SM".

---

## 1. UMA (Unidad de Medida y Actualización)

La UMA se actualiza cada año y entra en vigor el **1 de febrero**, no el 1 de enero. Esa
asimetría es la fuente de errores de cálculo más común en enero.

| Valor | Diaria | Mensual | Anual | Vigencia | Fuente primaria |
|---|---|---|---|---|---|
| **UMA 2026** | **$117.31** | $3,566.22 | $42,794.64 | 1-feb-2026 → 31-ene-2027 | INEGI, Comunicado de prensa 1/26; DOF 09-01-2026 (nota 5778072) |
| **UMA 2025** | **$113.14** | $3,439.46 | $41,273.52 | 1-feb-2025 → 31-ene-2026 | INEGI, Comunicado de prensa 1/25; DOF 09-01-2025 |

Los valores mensual y anual los publica el propio INEGI en el mismo comunicado y coinciden
con `diaria × 30.4` y `mensual × 12`. Incremento 2026 sobre 2025: 3.69 %.

**Dónde se usa la UMA en nómina:**
- Base de la cuota fija patronal de Enfermedades y Maternidad (Art. 106 fr. I LSS).
- Umbral del excedente de EyM: 3 UMA (Art. 106 fr. II LSS).
- Tope máximo del SBC: 25 UMA (Art. 28 LSS).
- Rangos de la tabla CEAV patronal (`22_cuotas_imss_infonavit_2026.md`).
- Exenciones de ISR del Art. 93 LISR (`23_isr_nomina_subsidio.md`).
- Base del subsidio para el empleo (§4).
- Multas por movimientos afiliatorios extemporáneos: 20 a 350 UMA (Art. 304-B LSS).

> **Por qué la ley dice "salario mínimo" y el motor lee "UMA".** Las leyes anteriores a 2016
> expresan topes en veces el salario mínimo. El **Decreto de desindexación (DOF 27-01-2016)**
> y el **Art. 26 apartado B constitucional** los transformaron en UMA: el SM quedó reservado
> para fines laborales y la UMA para todo lo demás. Es el eslabón que convierte "30 veces el
> SM" del Art. 93 LISR en "30 UMA". Confundirlos multiplica cada exención por ~2.69.

---

## 2. Salario mínimo general

| Zona | Diario 2026 | Incremento | Vigencia | Fuente primaria |
|---|---|---|---|---|
| **General** (resto del país) | **$315.04** | 13 % (MIR de $17.01 + 6.5 % de fijación) | 1-ene-2026 → 31-dic-2026 | Resolución CONASAMI; DOF 09-12-2025 |
| **Zona Libre de la Frontera Norte (ZLFN)** | **$440.87** | 5 % (sin MIR) | 1-ene-2026 → 31-dic-2026 | Resolución CONASAMI; DOF 09-12-2025 |

> Los incrementos son asimétricos (13 % vs 5 %) porque el **Monto Independiente de
> Recuperación** se aplica solo a la zona general; la ZLFN recibe únicamente el aumento por
> fijación. No es un error de transcripción — no lo "corrijas".

La zona la determina el domicilio del **centro de trabajo**, no el del patrón. Existen además
salarios mínimos profesionales para 61 oficios: fuera del alcance del motor por ahora, pero
son un piso superior al general cuando aplican.

> **Corregido en F0-01:** `../01_valores_referencia.md` traía los mínimos de **2025**
> ($278.80 y $419.88) etiquetados como 2026, y la UMA 2025 mensual/anual con error de
> centavos ($3,439.68 / $41,276.16 en vez de $3,439.46 / $41,273.52). Los cuatro valores
> quedaron corregidos en ese archivo, citando INEGI (Comunicado 1/25) y CONASAMI
> (DOF 09-12-2025). El resto de `01_valores_referencia.md` pertenece al dominio fiscal y no
> se tocó.

---

## 3. Piso y tope del SBC (Art. 28 LSS) — valor efectivo por fecha y zona

`SBC = clamp(SBC_calculado, piso, tope)`. El Art. 28 LSS fija el límite inferior en el salario
mínimo general **del área geográfica respectiva** — por eso el piso depende de la zona — y el
superior en 25 UMA. **Piso y tope se mueven en fechas distintas**: el piso sigue al salario
mínimo (1 de enero) y el tope sigue a la UMA (1 de febrero).

Las cuatro combinaciones, que son exactamente el contrato de `uma_vigente(fecha)` y
`salario_minimo_vigente(fecha, zona)` (tarea F0-02):

| Fecha del cálculo | Zona | Piso = 1 SM del área | Tope = 25 UMA | UMA diaria | 3 UMA (umbral EyM) |
|---|---|---|---|---|---|
| 1-ene-2026 → 31-ene-2026 | General | **$315.04** | **$2,828.50** | $113.14 | $339.42 |
| 1-ene-2026 → 31-ene-2026 | ZLFN | **$440.87** | **$2,828.50** | $113.14 | $339.42 |
| 1-feb-2026 → 31-dic-2026 | General | **$315.04** | **$2,932.75** | $117.31 | $351.93 |
| 1-feb-2026 → 31-dic-2026 | ZLFN | **$440.87** | **$2,932.75** | $117.31 | $351.93 |

Fundamento: **Art. 28 LSS** (piso y tope) y **Art. 106 fr. II LSS** (umbral de 3 UMA). Los
importes son producto de los valores de §1 y §2 con sus fuentes.

> En enero de 2027 el tope seguirá siendo el de la UMA 2026 ($2,932.75) hasta el 31 de enero,
> mientras el piso ya será el SM 2027. La regla es estructural, no una excepción de 2026.

---

## 4. Subsidio para el empleo 2026

El esquema vigente expresa el subsidio como **porcentaje de la UMA mensual**, no como la tabla
histórica por rangos de ingreso.

| Concepto | Regla del articulado | Importe que resulta | Vigencia | Fuente primaria |
|---|---|---|---|---|
| Subsidio mensual, régimen general | **15.02 % × UMA mensual vigente** | 0.1502 × $3,566.22 = **$535.65** | feb-2026 → dic-2026 | Decreto DOF 31-12-2025 (nota 5777649) |
| Subsidio mensual, transitorio de enero | **15.59 % × UMA mensual vigente** (la de 2025) | 0.1559 × $3,439.46 = **$536.21** | ene-2026 | ídem, artículo transitorio |
| Tope de ingresos gravados para tener derecho | monto fijo del decreto | **$11,492.66** mensuales | ejercicio 2026 | ídem |
| Entrada en vigor del decreto | — | 1-ene-2026 | — | ídem |

> ⚠️ **El decreto fija el porcentaje, no el peso.** El **articulado** del Decreto DOF
> 31-12-2025 establece "multiplicar el valor mensual de la UMA por 15.02 %" (15.59 % para
> enero de 2026); el importe de **$536.22** aparece únicamente en los **considerandos**, como
> referencia, y **no se reconcilia con la fórmula operativa**: 15.02 % × $3,566.22 = $535.65
> (harían falta 15.036 %, o una UMA diaria de $117.37 que nadie publicó). Por eso circulan
> fuentes secundarias con $536.22 y otras con $535.65. El transitorio de enero, en cambio,
> cuadra al centavo, lo que confirma la metodología.
>
> **Regla para el motor:** `subsidio_empleo()` **calcula** `porcentaje_vigente ×
> uma_mensual_vigente` y redondea a 2 decimales. Nunca hardcodea el peso.
>
> **Estado:** `docs/PLAN_NOMINA.md` §2.1 y §2.6 decían $536.22; **F0-01 los corrigió** citando
> el decreto, así que esa contradicción ya no existe en el repo. Lo único abierto es confirmar
> el porcentaje contra el DOF y cuadrar el importe contra el subsidio acreditado en las
> fixtures del caso real — **F1-01 y F1-04**. Si el importe real resultara $536.22, lo que
> habría que revisar es el porcentaje, no la aritmética.

Reglas de aplicación (desarrollo en `23_isr_nomina_subsidio.md`):
- Si el ingreso gravado del mes **excede** $11,492.66, el subsidio es **cero**: corte duro, no
  degradación gradual.
- Periodos menores al mes: `subsidio_mensual ÷ 30.4 × días del periodo`.
- El subsidio **solo reduce el ISR hasta cero**; el excedente ya no se entrega en efectivo.

> El transitorio de enero existe porque en enero todavía rige la UMA 2025: el porcentaje sube
> (15.59 % vs 15.02 %) para que el importe quede casi igual. Un motor que ignore el
> transitorio y aplique 15.02 % sobre la UMA 2025 da $516.61 — $19.60 de error por trabajador
> con derecho a subsidio, cada enero.

---

## 5. Prestaciones mínimas de ley (insumo del factor de integración)

| Prestación | Mínimo de ley | Fundamento | Vigencia |
|---|---|---|---|
| Aguinaldo | 15 días de salario, pagadero antes del 20 de diciembre | LFT Art. 87 | vigente |
| Vacaciones | 12 días el primer año; +2 por año hasta 20; después +2 cada 5 años | LFT Art. 76 | escala vigente desde 1-ene-2023 (reforma DOF 27-12-2022) |
| Prima vacacional | 25 % sobre el salario de los días de vacaciones | LFT Art. 80 | vigente |
| Prima dominical | 25 % adicional sobre el salario del día | LFT Art. 71 | vigente |
| PTU | 10 % de la utilidad fiscal, con el tope de la reforma laboral 2021 | LFT Arts. 117 y 127 fr. VIII | vigente desde 2021 |

El desarrollo del factor de integración está en `21_sbc_integracion.md`.

---

## 6. Índice de porcentajes (sin cifras, a propósito)

Ningún porcentaje de cuotas vive en este archivo, para que no haya dos copias que se
desincronicen. Están, con su base y su fundamento legal, en
**`22_cuotas_imss_infonavit_2026.md`**:

- Cuota fija y excedente de Enfermedades y Maternidad → §1 y §2 de ese archivo.
- Invalidez y Vida, Retiro, Guarderías, Infonavit → §1.
- CEAV patronal (tabla por rango) y CEAV obrera → §1 y §3.
- Primas de Riesgos de Trabajo por clase → §4.

Lo único que este archivo aporta a esas cuentas son los **importes con vigencia** de §1–§3:
la UMA que sirve de base a la cuota fija de EyM, el umbral de 3 UMA y el piso/tope del SBC.

**ISN (Impuesto Sobre Nómina):** estatal, no federal. Para el caso real (Veracruz) se maneja
como **3 % informativo** — no se calcula en F1 (`docs/decisiones-nomina.md` §D8). La tasa, su
artículo y su vigencia quedan **PENDIENTE VERIFICAR** contra el código financiero estatal
cuando el ISN entre al alcance; hoy no hay ningún cálculo que dependa de ese número.

---

## Fuentes primarias

- **INEGI**, Comunicado de prensa 1/26 — UMA 2026;
  `inegi.org.mx/contenidos/saladeprensa/boletines/2026/uma/uma2026.pdf`; DOF 09-01-2026
  (nota 5778072). Comunicado 1/25 para la UMA 2025.
- **CONASAMI**, Resolución de salarios mínimos generales y profesionales 2026 —
  DOF 09-12-2025.
- **Decreto que modifica el diverso que otorga el subsidio para el empleo** — DOF 31-12-2025,
  `dof.gob.mx/nota_detalle.php?codigo=5777649`.
- **Decreto de desindexación del salario mínimo** — DOF 27-01-2016; Art. 26 apartado B
  constitucional (creación de la UMA).
- Ley del Seguro Social: Arts. 28, 106, 168, 304-B.
- Ley Federal del Trabajo: Arts. 71, 76, 80, 87, 117, 127 (reforma de vacaciones,
  DOF 27-12-2022).

Las URLs completas están en `../00_fuentes_consulta.md`, sección de nómina.
