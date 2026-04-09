# DIOT — Declaración Informativa de Operaciones con Terceros 2026

**Fundamento legal:** Artículo 32, fracción VIII de la LIVA
**RMF 2026:** Regla 2.8.1.17 (exenciones), Regla 4.5.1 (formato)
**Plataforma:** Nueva plataforma digital del SAT (desde agosto 2025)

---

## Descripción

La DIOT es una **declaración informativa** (no de pago) donde el contribuyente reporta al SAT el detalle de sus operaciones con proveedores y terceros para efectos de IVA:

- IVA pagado a cada proveedor
- IVA retenido
- IVA acreditable
- Operaciones con y sin IVA

**No genera pago directo** — solo informa para cruzar información con los proveedores.

---

## Obligados a Presentar DIOT (Art. 32 fracc. VIII LIVA)

Todas las personas físicas y morales que **realicen actos o actividades gravados por IVA**, con las siguientes excepciones.

---

## Exenciones RMF 2026 (Regla 2.8.1.17)

**Personas físicas RELEVADAS de presentar DIOT en 2026:**

| Supuesto | Condición |
|----------|-----------|
| RESICO (626) | Sin importar el monto de ingresos |
| Régimen general (612) con ingresos del ejercicio anterior ≤ $4,000,000 | Verificar límite |
| Arrendamiento (606) con ingresos del ejercicio anterior ≤ $4,000,000 | Verificar límite |
| Plataformas (625) — esquema pago definitivo | Relevados |

**Importante:** Si los ingresos del ejercicio anterior superaron $4,000,000, el contribuyente SÍ está obligado a DIOT, independientemente de su régimen.

---

## Información que se Reporta en DIOT

Por cada proveedor/tercero:

| Campo | Descripción |
|-------|-------------|
| RFC del proveedor | Identificación del tercero |
| Tipo de tercero | Nacional / Extranjero / Global |
| Nombre o razón social | Del proveedor |
| Tipo de operación | 85 categorías distintas |
| Valor de actos sin IVA | Operaciones exentas o no objeto |
| Valor de actos con IVA 16% | Base gravada |
| IVA pagado no acreditable | |
| IVA retenido al proveedor | Cuando aplica |
| IVA pagado a importación | Si aplica |

---

## Periodicidad y Plazos

| Tipo | Frecuencia | Fecha Límite |
|------|-----------|-------------|
| Mensual | Por cada mes del ejercicio | Día **17 del mes siguiente** |
| Anual (ya no aplica) | Eliminada — solo mensual | — |

---

## Plataforma Nueva DIOT (desde 1 agosto 2025)

El SAT migró la DIOT a una nueva plataforma digital:
- Acceso exclusivo a través del portal del SAT con e.firma
- Solo permite presentación en línea (no hay versión offline)
- La plataforma anterior fue descontinuada

**Pasos para presentar:**
1. Ingresar al portal SAT con RFC + contraseña o e.firma
2. Seleccionar "Declaraciones" → "Informativas" → "DIOT"
3. Capturar o importar el archivo de operaciones
4. Validar y enviar
5. Descargar acuse con número de folio

---

## Estructura de Tipos de Terceros

| Tipo | Descripción |
|------|-------------|
| 04 | Proveedor nacional |
| 05 | Proveedor extranjero |
| 06 | Global (operaciones con público general) |

---

## Consecuencias de No Presentar DIOT

| Infracción | Multa (Art. 82 CFF) |
|-----------|---------------------|
| No presentar declaración informativa | $1,400 a $17,370 por declaración |
| Presentar con errores u omisiones | $1,400 a $17,370 por declaración |
| Presentar fuera de plazo | $1,400 a $17,370 por declaración |

---

## Integración con el Fiscal Agent API

El endpoint `/api/v1/diot` genera:
- Lista de proveedores con sus montos de IVA
- Clasificación por tipo de tercero
- Cálculo del IVA pagado y retenido por proveedor
- Formato listo para captura en plataforma SAT
