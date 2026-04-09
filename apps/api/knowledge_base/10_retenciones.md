# Retenciones a Terceros — ISR e IVA 2026

**Fundamento legal:** Arts. 96, 106, 113-A, 116 LISR; Arts. 1-A, 3, 18-D LIVA

---

## Descripción

Las **retenciones** son montos de impuesto que un tercero (patrón, persona moral cliente) descuenta del pago al contribuyente y entera directamente al SAT a nombre de este.

El retenedor actúa como **agente recaudador** — el impuesto ya fue pagado antes de que el contribuyente lo reciba.

---

## Retenciones de ISR por Tipo de Ingreso

### 1. Salarios (Régimen 605)

| Concepto | Retenedor | % |
|----------|-----------|---|
| Sueldo y salarios | Patrón | Variable (tabla Art. 96 LISR) |

El patrón aplica la tabla mensual del Art. 96 LISR menos el subsidio al empleo.

### 2. Honorarios (Régimen 612) — Art. 106 LISR

| Concepto | Retenedor | % ISR Retenido |
|----------|-----------|----------------|
| Servicios profesionales a PM | Persona moral | 10% sobre monto pagado |
| Servicios a la Federación, entidades, municipios | Ente público | 10% |

**Nota:** La retención aplica cuando el pagador es persona moral. Entre personas físicas, NO hay retención.

### 3. Arrendamiento (Régimen 606) — Art. 117 LISR

| Concepto | Retenedor | % ISR Retenido |
|----------|-----------|----------------|
| Renta de bienes inmuebles pagada por PM | Persona moral | 10% sobre la renta |

### 4. Plataformas Tecnológicas (Régimen 625) — Art. 113-A LISR

| Tipo de Servicio | % ISR Retenido |
|-----------------|----------------|
| Transporte de pasajeros y entrega de bienes | 2.10% |
| Hospedaje | 4.00% |
| Enajenación de bienes y otros servicios | 1.00% |

---

## Retenciones de IVA por Tipo

### Personas morales que contratan personas físicas — Art. 1-A fracc. II LIVA

| Servicio prestado por PF | % IVA Retenido por PM |
|-------------------------|----------------------|
| Servicios independientes (honorarios) | 66.67% del IVA facturado |
| Arrendamiento de bienes inmuebles (comercial) | 66.67% del IVA facturado |

**Ejemplo práctico:**
```
Honorario: $10,000
IVA 16%: $1,600
Total factura: $11,600

PM retiene:
  ISR: $10,000 × 10% = $1,000
  IVA: $1,600 × 66.67% = $1,067

PM paga al PF: $11,600 - $1,000 - $1,067 = $9,533
PM entera al SAT: $1,000 (ISR) + $1,067 (IVA)
PF entera al SAT: $1,600 - $1,067 = $533 (IVA restante)
```

### Plataformas Digitales — Art. 18-D LIVA

| Tipo de Servicio | % IVA Retenido |
|-----------------|----------------|
| Todos los tipos | 50% del IVA causado (8% sobre el valor) |

---

## Constancias de Retención

El retenedor debe emitir **CFDI de Retenciones e Información de Pagos** (Art. 127 RISAT):
- Por cada periodo en que se efectúa retención
- Contiene: RFC del retenido, monto del pago, ISR retenido, IVA retenido

**Tipos de CFDI de retención relevantes:**
| Tipo | Descripción |
|------|-------------|
| 01 | Retenciones por arrendamiento |
| 03 | Dividendos o utilidades |
| 06 | Intereses |
| 14 | Pagos por servicios de plataformas tecnológicas |
| 17 | Retenciones efectuadas a personas físicas (honorarios) |

---

## Acreditamiento de Retenciones

El contribuyente acredita las retenciones recibidas contra su impuesto a pagar:

```
ISR a Pagar = ISR Provisional Calculado - Retenciones ISR recibidas en el periodo
IVA a Pagar = IVA Trasladado - IVA Acreditable - IVA Retenido por clientes PM
```

---

## Obligaciones del Retenedor (Art. 99 LISR / Art. 5 LIVA)

1. Efectuar la retención en el momento del pago
2. Enterar las retenciones al SAT a más tardar el día **17 del mes siguiente**
3. Emitir CFDI de retenciones
4. Presentar declaración informativa anual de retenciones (Forma 37 o equivalente)

---

## Retenciones en el Sistema Fiscalito

El endpoint `/api/v1/retenciones-terceros` calcula:
- ISR retenido por cada tercero (cliente persona moral)
- IVA retenido por cada tercero
- Total de retenciones acreditables del periodo
- Verificación de que los CFDI de retención coincidan con los CFDIs de ingreso
