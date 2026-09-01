# Valores de Referencia 2026

**Fuente:** INEGI DOF 09/01/2026, DOF 31/12/2025

---

## UMA (Unidad de Medida y Actualización) 2026

Vigente a partir del **1 de febrero de 2026** (enero 2026 aplica UMA 2025).

| Periodo | Valor |
|---------|-------|
| Diario | $117.31 MXN |
| Mensual | $3,566.22 MXN |
| Anual | $42,794.64 MXN |

**Incremento:** 3.69% respecto a UMA 2025 ($113.14 diario).

### UMA 2025 (enero 2026 y ejercicio fiscal 2025)

| Periodo | Valor |
|---------|-------|
| Diario | $113.14 MXN |
| Mensual | $3,439.46 MXN |
| Anual | $41,273.52 MXN |

*Valores corregidos en F0-01 contra el Comunicado de prensa 1/25 del INEGI (antes decían
$3,439.68 y $41,276.16). Vigencia: 1-feb-2025 → 31-ene-2026.*

### Uso de la UMA en el sistema Fiscalito

- **Límite deducciones personales:** 5 veces el **valor anual de la UMA del ejercicio**
  (Art. 151 último párrafo LISR). El valor anual es el que publica el INEGI (Art. 4 fr. III
  de la Ley para Determinar el Valor de la UMA), **no** `diaria × 365`:
  - ejercicio **2026** → 5 × $42,794.64 = **$213,973.20**
  - ejercicio **2025** → 5 × $41,273.52 = **$206,367.60**

  *Corregido en F0-02: la línea anterior daba $213,973.20 pero lo atribuía a la UMA 2025, y
  arrastraba un $207,648.00 sin fuente. El motor lo resuelve por ejercicio con
  `app.constants.uma_anual_vigente()`.*
- **Subsidio al empleo:** basado en salario mínimo y UMA
- **Ingresos exentos:** límites expresados en UMAs

---

## Salario Mínimo 2026

| Zona | Valor Diario | Vigencia |
|------|-------------|----------|
| General (todo el país) | $315.04 MXN | 1-ene-2026 → 31-dic-2026 |
| Zona Libre Frontera Norte (ZLFN) | $440.87 MXN | 1-ene-2026 → 31-dic-2026 |

*Valores corregidos en F0-01 contra la Resolución CONASAMI publicada en el DOF el 09-12-2025
(antes decían $278.80 y $419.88, que son los mínimos de **2025**). El incremento del general
es 13 % — MIR de $17.01 más 6.5 % de fijación — y el de la ZLFN 5 % sin MIR; la asimetría es
correcta. Desglose en `nomina/20_valores_referencia_2026.md` §2.*

**Nota:** No se retiene ISR a trabajadores que perciban únicamente 1 salario mínimo mensual (Art. 96 LISR).

---

## Factor de Actualización ISR 2026 (Anexo 8 RMF 2026)

- **Factor aplicado:** 1.13213
- **Cálculo:** INPC noviembre 2025 / INPC noviembre 2022
- **Criterio:** La inflación acumulada superó el 10% en el periodo, activando la actualización obligatoria de tablas
- **Publicación:** DOF 28/12/2025 (Anexo 8 RMF 2026)

---

## Subsidio al Empleo 2026 (Decreto DOF 31/12/2025)

| Ingresos Mensuales (hasta) | Subsidio Mensual | Regla del decreto |
|---------------------------|-----------------|-------------------|
| $11,492.66 | $535.65 (feb–dic) | 15.02 % × UMA mensual 2026 ($3,566.22) |
| $11,492.66 | $536.21 (enero) | 15.59 % × UMA mensual 2025 ($3,439.46), transitorio |

*Verificado en F0-01 contra el articulado del Decreto DOF 31-12-2025, que fija el porcentaje y
no un monto en pesos. El importe se calcula, no se hardcodea; ver
`nomina/20_valores_referencia_2026.md` §4.*

**Nota:** El subsidio al empleo solo aplica a personas físicas asalariadas (régimen 605). Se acredita contra el ISR causado; si el subsidio excede el ISR, no genera saldo a favor reembolsable del patrón.

---

## Límite RESICO 2026

- **Ingresos máximos:** $3,500,000 anuales para tributar en RESICO (Art. 113-E LISR)
- Si se excede este límite, el contribuyente debe migrarse al régimen general (612) en el ejercicio siguiente
