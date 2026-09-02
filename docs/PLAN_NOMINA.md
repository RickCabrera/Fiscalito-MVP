# PLAN_NOMINA.md — Fiscalito Nómina / IMSS Manager

> **Propósito de este documento.** Spec de dominio + arquitectura para extender el ecosistema Fiscalito hacia nómina (SBC/SDI, cuotas IMSS-Infonavit, recibo con ISR, timbrado) con un modelo *contador → N clientes → N empleados*. Está pensado para alimentar un `CLAUDE.md` / `backlog.md` y bucles de desarrollo. Todo valor legal está verificado a **agosto 2026** con fuentes oficiales (DOF, INEGI, IMSS, CONASAMI) o secundarias de alta confianza; las fuentes están al final.
>
> **Regla de oro heredada de Fiscalito:** el motor calcula con reglas duras (Python determinístico, tablas versionadas por año, tests contra caso real). El LLM **solo explica y decide flujo** vía tool calling. Nunca calcula.

---

## 0. TL;DR de decisiones

| Decisión | Resolución | Por qué |
|---|---|---|
| ¿Repo nuevo o mismo? | **Mismo monorepo** | Comparte tablas ISR Art. 96, constantes UMA/SM, patrón schemas/routes/engine/tests, LLM service, Dockerfile Cloud Run, knowledge_base |
| ¿API nueva o misma? | **Misma API, nuevo módulo** `app/nomina_engine/` + `app/routes/nomina/` | La API es stateless; agregar dominio = agregar routers. El agente puede cruzar fiscal + nómina en un solo tool loop |
| ¿Frontend nuevo o adaptar `apps/store`? | **Frontend nuevo** `apps/despacho/` | El modelo de usuario cambia radicalmente (contador multi-cliente). Adaptar `ProfileContext`/`OnboardingWizard`/`getTabsForProfile` sería pelear con cada pieza. Se reutiliza `global.css`, `components/voice/`, patrón `fiscalAgentApi.ts` |
| ¿MCP? | **No por ahora** | El agente ya hace tool calling interno contra REST. MCP = canal de distribución futuro (contador conecta su Claude a Fiscalito). Los endpoints mapean 1:1 a tools; envolverlos después es trivial |
| ¿Timbrado real en MVP? | **No**. Generar XML complemento nómina 1.2 sin timbrar ("pre-recibo") | PAC (Finkok / SW Sapien / Facturama) se integra en Fase 3 con sandbox |
| ¿Dependencia nómina → fiscal? | **No obligatoria** | Cuotas IMSS son autocontenidas. Lo que se comparte: tabla ISR Art. 96 (recibo), constantes, y el *flujo de datos* (ISR retenido de nómina → declaración mensual del patrón; recibos timbrados → egresos deducibles) |

---

## 1. Estado actual de Fiscalito (lo que ya existe y se hereda)

**Monorepo** `fiscalito-mvp/` con `apps/api` (FastAPI, Pydantic v2, pytest, Cloud Run) y `apps/store` (React 19 + Vite + TS + Firebase Auth/Firestore).

**Backend `apps/api`** — 11 endpoints, stateless. Estructura relevante para reutilizar:

```
app/
├── constants.py            # NOMBRES_MESES, TOPE_RESICO_ANUAL, UMA…  ← agregar SM, UMA por vigencia
├── exceptions.py           # FiscalAgentError / FiscalValidationError(422) / FiscalCalculationError(500)
├── routes/                 # un archivo por dominio; se agrega routes/nomina/
├── schemas/                # Pydantic request/response; se agrega schemas/nomina/
├── fiscal_engine/
│   ├── tablas_isr.py       # TABLA_ISR_MENSUAL (Art. 96) ← el recibo de nómina la REUTILIZA
│   └── …
├── services/
│   ├── agent_tools.py      # TOOLS_ANTHROPIC/OPENAI + RequestContext + ejecutar_tool ← extender con tools nómina
│   └── llm_service.py      # explicaciones OpenAI/Anthropic con fallback estático
knowledge_base/             # 00–14 *.md de referencia fiscal ← agregar nomina/
tests/                      # un archivo por módulo del engine + caso real CADG620317EE0
```

**Frontend `apps/store`** — servicio `imss-manager` ya declarado en `src/services/storeServices.ts` como `coming_soon`, categoría `laboral`, `appliesTo: ['pyme']`. Lo que se construye aquí **es** ese servicio, reenfocado a contadores.

**Pautas de calidad vigentes (aplican al módulo nuevo):** archivos ≤ 300 líneas; type hints + docstring; cambios al motor citan artículo de ley; nuevos endpoints con schema Pydantic completo; fallback LLM funciona sin API key; sin `print()`; tests por módulo.

---

## 2. Dominio: cómo funciona la nómina en México (lo que el motor calcula)

### 2.1 Valores de referencia 2026

| Concepto | Valor | Vigencia | Fuente |
|---|---|---|---|
| **UMA diaria 2026** | **$117.31** | 1-feb-2026 → 31-ene-2027 | INEGI / DOF 09-01-2026 |
| UMA mensual 2026 | $3,566.22 (= diaria × 30.4) | ídem | INEGI |
| UMA anual 2026 | $42,794.64 | ídem | INEGI |
| UMA diaria 2025 (aplica en **enero 2026**) | $113.14 | 1-feb-2025 → 31-ene-2026 | INEGI |
| **Salario mínimo general 2026** | **$315.04** diarios | 1-ene-2026 | CONASAMI / DOF 09-12-2025 |
| Salario mínimo Zona Libre Frontera Norte 2026 | $440.87 diarios | 1-ene-2026 | CONASAMI |
| Tope SBC | 25 UMA = $2,932.75 diarios (feb–dic 2026) | Art. 28 LSS | — |
| Piso SBC | 1 SM general ($315.04) | Art. 28 LSS | — |
| **Subsidio al empleo 2026** | 15.02 % de UMA mensual = **$535.65/mes** (feb–dic); enero transitorio 15.59 % × UMA 2025 mensual ($3,439.46) = **$536.21** | Decreto DOF 31-12-2025 | DOF 31-12-2025 (articulado) |
| Tope ingresos para subsidio | $11,492.66 mensuales | ídem | ídem |

> ⚠️ **Regla de diseño:** `constants.py` debe exponer `uma_vigente(fecha)` y `salario_minimo_vigente(fecha, zona)` — no constantes sueltas. Enero 2026 usa UMA 2025; febrero en adelante UMA 2026. Esto se repite cada año.

> ⚠️ **Quirk 2026 a validar con contadora:** desde 2024 el SM general ($315.04) supera ~2.69 UMA. La tabla CEAV tiene renglones "1.01 SM a 1.50 UMA", "1.51–2.00 UMA", "2.01–2.50 UMA" que quedan **por debajo del salario mínimo** y en la práctica son inalcanzables en zona general. Un trabajador con salario mínimo cae en 3.150 %; el siguiente escalón real es 2.51–3.00 UMA (6.026 %). Hay que confirmar cómo lo aplica el SUA para no divergir de la emisión del IMSS.

### 2.2 Salario diario, SBC/SDI y factor de integración

**Salario Base de Cotización (SBC)** — también llamado Salario Diario Integrado (SDI). Es la base sobre la que se aplican las cuotas IMSS/Infonavit (Art. 27 LSS: integra cuota diaria + gratificaciones, percepciones, alimentación, habitación, primas, comisiones, prestaciones en especie y cualquier otra cantidad entregada por el trabajo, con las exclusiones del propio Art. 27).

```
SBC = salario_diario × factor_integracion   (+ percepciones variables promediadas, si aplica)
SBC = clamp(SBC, 1 SM, 25 UMA)
```

**Factor de integración con prestaciones mínimas de ley** (aguinaldo 15 días LFT Art. 87; vacaciones LFT Art. 76 reformado 2023 "vacaciones dignas"; prima vacacional 25 % LFT Art. 80):

```
factor = 1 + (dias_aguinaldo / 365) + (dias_vacaciones × prima_vacacional / 365)
```

| Años de servicio | Aguinaldo | Vacaciones | Prima vac. | **Factor** |
|---|---|---|---|---|
| 1 | 15 | 12 | 25 % | **1.0493** |
| 2 | 15 | 14 | 25 % | 1.0507 |
| 3 | 15 | 16 | 25 % | 1.0521 |
| 4 | 15 | 18 | 25 % | 1.0534 |
| 5 | 15 | 20 | 25 % | 1.0548 |
| 6–10 | 15 | 22 | 25 % | 1.0562 |
| 11–15 | 15 | 24 | 25 % | 1.0575 |
| 16–20 | 15 | 26 | 25 % | 1.0589 |
| 21–25 | 15 | 28 | 25 % | 1.0603 |
| 26–30 | 15 | 30 | 25 % | 1.0616 |
| 31–35 | 15 | 32 | 25 % | 1.0630 |

> El motor **no debe hardcodear la tabla**: la calcula desde `(dias_aguinaldo, dias_vacaciones, prima)` porque muchas empresas dan prestaciones superiores a la ley (30 días de aguinaldo, 50 % de prima, vales, fondo de ahorro). La tabla es solo el caso "mínimo de ley" y sirve de test. Percepciones adicionales integrables (vales de despensa > 40 % UMA, fondo de ahorro fuera de límites, bonos fijos) deben modelarse como `ConceptoIntegrable{monto_diario, integra: bool}`.

### 2.3 Tipos de salario (Art. 30 LSS)

| Tipo | Cómo se determina el SBC | Aviso al IMSS |
|---|---|---|
| **Fijo** | Conocido por adelantado: salario diario × factor + percepciones fijas integrables | Modificación dentro de **5 días hábiles** siguientes al cambio (Art. 34 fr. I) |
| **Variable** (comisiones, destajo, horas extra habituales) | Promedio: `Σ percepciones variables del bimestre anterior ÷ días de salario devengado en ese bimestre`. Si es alta nueva, se estima | Modificación en los **primeros 5 días hábiles de enero, marzo, mayo, julio, septiembre y noviembre** (Art. 34 fr. II) — bimestral |
| **Mixto** | `parte fija × factor + promedio variable del bimestre anterior` | Mismas reglas: la parte fija se avisa al cambiar; la variable bimestral (Art. 34 fr. III) |

> Esta obligación bimestral de variables es **chamba recurrente automatizable**: el sistema debe generar por cliente, en cada bimestre par, la lista de empleados variables/mixtos con su nuevo SBC y el archivo de movimientos listo para IDSE.

**Movimientos afiliatorios y plazos (Art. 15 LSS):** alta, baja, reingreso y modificación de salario se presentan en **≤ 5 días hábiles**. Multas por extemporaneidad: 20 a 350 UMA.

> ⚠️ **Cambio regulatorio julio 2026:** Acuerdo del Consejo Técnico del IMSS (DOF 16-jul-2026, vigente 17-jul-2026) **deroga el NPIE** y el certificado digital propio del IMSS; la **e.firma del SAT es el único certificado válido** para movimientos afiliatorios y vinculación de representantes legales vía Escritorio Virtual. Periodo de transición de 90 días naturales (vence ~14-oct-2026). Implicación para el producto: cualquier feature de "presentar movimientos" asume e.firma del patrón; el contador opera como representante legal vinculado.

### 2.4 Cuotas obrero-patronales IMSS 2026 (por ramo)

Base: SBC, excepto la cuota fija de EyM que es sobre UMA. Fundamento LSS.

| Ramo | Concepto | Patrón | Obrero | Base | LSS |
|---|---|---|---|---|---|
| **Riesgos de Trabajo** | Prima de riesgo de la empresa | prima % | 0 | SBC | Art. 71–74 |
| **Enfermedades y Maternidad** | Cuota fija (por trabajador) | 20.40 % | 0 | **UMA** | Art. 106 fr. I |
| | Excedente (solo si SBC > 3 UMA) | 1.10 % | 0.40 % | SBC − 3 UMA | Art. 106 fr. II |
| | Prestaciones en dinero | 0.70 % | 0.25 % | SBC | Art. 107 |
| | Gastos médicos pensionados | 1.05 % | 0.375 % | SBC | Art. 25 |
| **Invalidez y Vida** | | 1.75 % | 0.625 % | SBC | Art. 147 |
| **Retiro** | | 2.00 % | 0 | SBC | Art. 168 fr. I |
| **Cesantía en Edad Avanzada y Vejez (CEAV)** | | **tabla 2026** | 1.125 % | SBC | Art. 168 fr. II + reforma DOF 16-dic-2020 |
| **Guarderías y Prestaciones Sociales** | | 1.00 % | 0 | SBC | Art. 211 |
| **Infonavit** | | 5.00 % | 0 | SBC | Ley Infonavit Art. 29 |

**Reglas especiales:**
- Trabajador con SBC = 1 SM: el patrón **absorbe la cuota obrera** (Art. 36 LSS).
- Días cotizados del periodo se reducen por **ausentismos** (hasta 7 por mes: no se cotizan EyM ni IyV, pero sí RT… validar) e **incapacidades** (no se cotiza salvo RT/EyM en algunos ramos). Modelar `dias_cotizados` como input, no asumir 30/31.
- Prima de Riesgo de Trabajo: se declara **anualmente en febrero** (Declaración Anual de Prima de RT, Art. 74 LSS) con base en siniestralidad; para empresas nuevas aplica la prima media de su clase.

**Tabla CEAV patronal 2026** (cuarto año de la transición 2023–2030; en 2030 llega a 11.875 %):

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

> Tabla **versionada por año** (`tablas_imss.py` → `CEAV_PATRONAL[2026]`, `[2027]`…). Se actualiza cada enero.

**Clases de riesgo de trabajo (prima media, Art. 73 LSS):**

| Clase | Prima media |
|---|---|
| I | 0.54355 % |
| II | 1.13065 % |
| III | 2.59840 % |
| IV | 4.65325 % |
| V | 7.58875 % |

### 2.5 Periodicidad y calendario de pago 2026

- **Mensual** (día 17 del mes siguiente): RT, EyM, IyV, Guarderías.
- **Bimestral** (día 17 del mes siguiente al bimestre): Retiro, CEAV, Infonavit (+ amortizaciones de crédito Infonavit).
- Si el 17 cae en viernes o inhábil → siguiente día hábil.
- Pago vía **SUA** (Sistema Único de Autodeterminación) generando línea de captura **SIPARE**.

| Cuotas de | Fecha límite 2026 | Tipo |
|---|---|---|
| Enero | 17-feb | Mensual |
| Febrero | 17-mar | Mensual + bimestral |
| Marzo | 20-abr | Mensual |
| Abril | 18-may | Mensual + bimestral |
| Mayo | 17-jun | Mensual |
| Junio | 20-jul | Mensual + bimestral |
| Julio | 17-ago | Mensual |
| Agosto | 17-sep | Mensual + bimestral |
| Septiembre | 19-oct | Mensual |
| Octubre | 17-nov | Mensual + bimestral |
| Noviembre | 17-dic | Mensual |
| Diciembre | 18-ene-2027 | Mensual + bimestral |

Otras fechas laborales fijas: **febrero** → Declaración Anual de Prima de RT; **mayo** → PTU (personas morales) / **junio** → PTU (personas físicas); **diciembre (antes del 20)** → aguinaldo; **bimestres pares** → aviso de variables.

### 2.6 ISR de sueldos y salarios (lo que se retiene en el recibo)

1. **Base gravable** = percepciones gravadas del periodo. Exenciones principales (Art. 93 LISR, en UMA): aguinaldo hasta 30 UMA diarias; prima vacacional hasta 15 UMA; PTU hasta 15 UMA; tiempo extra 50 % exento hasta 5 UMA semanales (dentro de límites LFT); previsión social (vales, fondo de ahorro) con topes propios.
2. **ISR** = tarifa **Art. 96 LISR** (mensual; para periodos menores se usan las tablas semanal/decenal/quincenal del Anexo 8 RMF, o se prorratea la mensual ÷ 30.4 × días — validar cuál usa el despacho). **La tabla mensual ya está en `fiscal_engine/tablas_isr.py`.** Falta agregar las periódicas.
3. **Subsidio al empleo 2026**: si ingresos mensuales ≤ $11,492.66 → subsidio = $535.65 (feb–dic) / $536.21 (ene). Periodos < mes: `subsidio_mensual ÷ 30.4 × días`. El motor **calcula** el importe como `% vigente × UMA mensual vigente`; no lo hardcodea. Se acredita contra el ISR causado; si el subsidio > ISR ya **no** se entrega en efectivo (esquema vigente desde 2024: solo reduce ISR hasta cero).
4. **ISR a retener** = max(ISR − subsidio, 0).
5. Ese ISR retenido lo **entera el patrón** en su declaración mensual (día 17) → aquí conecta con `retenciones.py` / `pre-declaracion` del Fiscalito actual.

**ISN (Impuesto Sobre Nómina)** — estatal, sobre remuneraciones, lo paga el patrón. Varía por estado (≈ 2–4 %; Veracruz 3 %, CDMX 4 %). Modelar como tabla `ISN_POR_ESTADO[año]` y calcularlo por cliente según entidad del registro patronal. Fuera del MVP del motor, dentro del calendario.

### 2.7 Recibo de nómina y timbrado (CFDI 4.0 + complemento Nómina 1.2)

Estructura mínima del recibo que el motor produce:

```
Percepciones (c_TipoPercepcion): sueldo 001, aguinaldo 002, PTU 003, horas extra 019, prima vacacional 021, vales 029, …
  cada una con ImporteGravado / ImporteExento
Deducciones (c_TipoDeduccion): ISR 002, IMSS 001 (cuota obrera), Infonavit 010, fondo de ahorro 004, …
OtrosPagos (c_TipoOtroPago): subsidio al empleo 002 (con SubsidioCausado)
Nodo Nomina: TipoNomina O/E, FechaPago, FechaInicialPago, FechaFinalPago, NumDiasPagados
Emisor: RegistroPatronal, RfcPatronOrigen
Receptor: Curp, NumSeguridadSocial, FechaInicioRelLaboral, Antigüedad (P#W/P#D), TipoContrato, TipoRegimen (02 sueldos), NumEmpleado, Departamento, Puesto, RiesgoPuesto (clase), PeriodicidadPago, SalarioBaseCotApor (SBC), SalarioDiarioIntegrado, ClaveEntFed
```

- **Timbrado**: obligatorio vía PAC autorizado. Candidatos con sandbox: Finkok, SW Sapien, Facturama. Fase 3.
- **MVP**: el motor devuelve el recibo calculado + genera el XML sin timbrar (validable contra XSD de nómina 1.2). El PDF del recibo se exporta con el patrón `pdfExport*.ts` existente.
- Periodicidades a soportar: semanal (07 días), catorcenal (14), quincenal (15), mensual (30/30.4). `NumDiasPagados` fraccionable por faltas/incapacidades.

### 2.8 El flujo real de un despacho (por qué esto vale dinero)

Este es el ciclo que el producto reemplaza; cada paso es un candidato a feature/tool del agente:

1. **Alta patronal** del cliente (registro patronal, clase/prima RT, entidad, e.firma vinculada en Escritorio Virtual IMSS).
2. **Altas / bajas / reingresos / modificaciones** de trabajadores → IDSE (≤ 5 días hábiles). Hoy: captura manual o archivo .txt/.xlsx de movimientos.
3. **Correr nómina** (semanal/quincenal): percepciones → SBC → ISR + subsidio → cuota obrera IMSS → neto. **Timbrar** cada recibo.
4. **Precálculo de cuotas** obrero-patronales del mes y del bimestre por empleado y consolidado por cliente. *("IMSS precálculo")*
5. **Conciliar** el precálculo contra la **EMA** (Emisión Mensual Anticipada) y **EBA** (Emisión Bimestral Anticipada) que el IMSS publica en IDSE. Diferencias típicas: movimientos no reconocidos, SBC distinto, días de incapacidad, ausentismos. Aquí el contador detecta errores **antes de pagar**. Es el feature más valioso: hoy se hace con Excel o herramientas tipo "Confronta SUA vs IDSE".
6. **Pagar** vía SUA → SIPARE (día 17). El ISR retenido se entera en la declaración mensual del patrón (SAT).
7. **Bimestres pares**: recalcular variables y presentar modificaciones.
8. **Febrero**: Declaración Anual de Prima de RT. **Mayo/junio**: PTU. **Diciembre**: aguinaldo.

> Métrica de éxito del producto: que un contador solo lleve N clientes con el tiempo que hoy le toma uno. Todo lo repetitivo (pasos 3–5, 7) debe ser un botón o una frase a Fiscalito.

---

## 3. Arquitectura

### 3.1 Backend — `apps/api` (extensión)

```
app/
├── constants.py                      # + uma_vigente(fecha), salario_minimo_vigente(fecha, zona)
├── routes/nomina/
│   ├── __init__.py
│   ├── sbc.py                        # POST /api/v1/nomina/sbc
│   ├── cuotas.py                     # POST /api/v1/nomina/cuotas-imss
│   ├── recibo.py                     # POST /api/v1/nomina/recibo
│   ├── calendario.py                 # POST /api/v1/nomina/calendario-laboral
│   ├── conciliacion.py               # POST /api/v1/nomina/conciliacion-ema   (Fase 2)
│   └── agente.py                     # POST /api/v1/agente/nomina
├── schemas/nomina/
│   ├── base.py                       # Empleado, Cliente(Patron), PercepcionVariable, ConceptoIntegrable, enums
│   ├── sbc.py                        # SBCRequest/Response
│   ├── cuotas.py                     # CuotasRequest/Response, DesgloseCuotasEmpleado, ConsolidadoCliente
│   ├── recibo.py                     # ReciboRequest/Response, Percepcion, Deduccion, OtroPago
│   ├── calendario.py
│   ├── conciliacion.py
│   └── agente.py
├── nomina_engine/
│   ├── __init__.py
│   ├── tablas_imss.py                # CUOTAS_RAMOS[año], CEAV_PATRONAL[año], PRIMA_MEDIA_CLASE, factor tabla test
│   ├── tablas_isr_periodicas.py      # Art. 96 diaria/semanal/quincenal (Anexo 8) + isr_periodo()
│   ├── subsidio.py                   # subsidio_empleo() con el transitorio de enero
│   ├── integracion.py                # factor_integracion(), sbc_fijo(), sbc_variable(), sbc_mixto(), clamp
│   ├── cuotas.py                     # cuotas_empleado(), cuotas_cliente() mensual/bimestral por ramo
│   ├── isr_nomina.py                 # base_gravable(), exenciones Art. 93, aplica_subsidio()
│   ├── recibo.py                     # recibo() orquesta percepciones→ISR→IMSS obrero→neto
│   ├── cfdi_nomina_xml.py            # genera XML complemento 1.2 (sin timbrar)
│   ├── calendario_laboral.py         # vencimientos IMSS/SUA, variables, prima RT, PTU, aguinaldo, ISN
│   └── conciliacion.py               # parser EMA/EBA + diff contra precálculo (Fase 2)
knowledge_base/nomina/
│   ├── 20_valores_referencia_2026.md
│   ├── 21_sbc_integracion.md
│   ├── 22_cuotas_imss_infonavit_2026.md
│   ├── 23_isr_nomina_subsidio.md
│   ├── 24_cfdi_nomina_12.md
│   ├── 25_calendario_laboral_2026.md
│   └── 26_flujo_despacho_idse_sua_ema.md
tests/nomina/
│   ├── test_integracion.py           # factor vs tabla oficial; clamp SM/25 UMA; variable bimestral
│   ├── test_cuotas.py                # cada ramo aislado; EyM cuota fija sobre UMA; excedente > 3 UMA; SM absorbe obrera
│   ├── test_isr_nomina.py            # Art. 96 + subsidio enero vs feb 2026; tope $11,492.66
│   ├── test_recibo.py
│   ├── test_cfdi_nomina_xml.py       # valida contra XSD
│   └── test_caso_real_<cliente>.py   # ← CONSEGUIR con contadora: 1 cliente real, 1 bimestre, EMA/EBA + SUA
```

**Principios del motor:**
- Todo cálculo recibe `fecha` y resuelve UMA/SM/tablas por vigencia. Nunca constantes globales sin fecha.
- `Decimal` con redondeo explícito (`ROUND_HALF_UP`, 2 decimales) — el SUA redondea por concepto, no al final. Validar contra caso real.
- Cada función documenta el artículo (LSS / LISR / LFT / Ley Infonavit).
- Stateless: el frontend manda `empleados[]` + `cliente` + `periodo`; la API devuelve desgloses. Igual que hoy manda `facturas[]`.

### 3.2 Contratos de los endpoints (bosquejo)

```python
# schemas/nomina/base.py
class TipoSalario(str, Enum): FIJO = "fijo"; VARIABLE = "variable"; MIXTO = "mixto"
class Periodicidad(str, Enum): SEMANAL = "02"; CATORCENAL = "03"; QUINCENAL = "04"; MENSUAL = "05"  # claves c_PeriodicidadPago, NO dias (corregido en F0-01)

class Cliente(BaseModel):            # = patrón
    rfc: str; razon_social: str; registro_patronal: str
    clase_riesgo: int                # 1–5
    prima_riesgo: Decimal            # % vigente (si None → prima media de la clase)
    entidad: str                     # clave estado (ISN, ClaveEntFed)
    zona_salarial: Literal["general", "frontera_norte"] = "general"

class Empleado(BaseModel):
    id: str; nombre: str; curp: str; nss: str; rfc: str
    fecha_alta: date; fecha_baja: date | None
    tipo_salario: TipoSalario
    salario_diario: Decimal                          # cuota diaria fija
    dias_aguinaldo: int = 15; dias_vacaciones: int | None = None; prima_vacacional: Decimal = Decimal("0.25")
    conceptos_integrables: list[ConceptoIntegrable] = []
    percepciones_variables_bimestre_anterior: list[PercepcionVariable] = []
    periodicidad: Periodicidad
    sbc_registrado_imss: Decimal | None              # lo que dice IDSE hoy (para detectar diff)

# POST /api/v1/nomina/sbc
SBCRequest{ cliente, empleados[], fecha_calculo }
SBCResponse{ resultados: [ {empleado_id, factor, sbc_fijo, sbc_variable, sbc_total, tope_aplicado, requiere_aviso: bool, tipo_aviso, fecha_limite_aviso} ], advertencias[], explicacion? }

# POST /api/v1/nomina/cuotas-imss
CuotasRequest{ cliente, empleados[] (con sbc + dias_cotizados + incapacidades + ausentismos), periodo_year, periodo_month, incluir_bimestral: bool, incluir_explicacion }
CuotasResponse{ por_empleado: [ {empleado_id, sbc, dias, ramos: {rt, eym_fija, eym_exc, eym_dinero, gmp, iv, guarderias, retiro, ceav, infonavit}: {patron, obrero}} ],
                consolidado: {total_patron_mensual, total_obrero_mensual, total_bimestral, total_infonavit, gran_total},
                fecha_limite_pago, advertencias[], explicacion? }

# POST /api/v1/nomina/recibo
ReciboRequest{ cliente, empleado, periodo {inicio, fin, fecha_pago, dias_pagados}, percepciones[], deducciones_extra[], incluir_xml: bool }
ReciboResponse{ percepciones (gravado/exento), isr_causado, subsidio, isr_retenido, imss_obrero, infonavit_amortizacion, otras_deducciones, neto, xml_nomina12?: str, explicacion? }

# POST /api/v1/nomina/calendario-laboral
{ cliente, empleados[] (solo tipos de salario y altas), year } → obligaciones[] {fecha, tipo, descripcion, empleados_afectados[]}

# POST /api/v1/nomina/conciliacion-ema   (Fase 2)
{ cliente, precalculo: CuotasResponse, ema_archivo: str (contenido .txt/.csv exportado de IDSE) } → diferencias[] {empleado, campo, valor_imss, valor_calculado, causa_probable}

# POST /api/v1/agente/nomina
{ mensaje, contador, cliente, empleados[], historial[], periodo } → { respuesta, resultado?: SBC|Cuotas|Recibo, herramientas_usadas[] }
```

**Tools del agente** (extienden `agent_tools.py`): `leer_cliente`, `listar_empleados`, `calcular_sbc`, `calcular_cuotas_imss`, `calcular_recibo`, `consultar_calendario_laboral`, `consultar_historial_cuotas`. El agente decide flujo; los tools llaman al engine. Mismo patrón que `/agente/predeclaracion`.

### 3.3 Frontend — `apps/despacho` (nuevo)

**Modelo de usuario:** contador (auth) → clientes (patrones) → empleados. El contador puede tener rol `owner`; preparar `miembros/` para despachos con varios contadores (Fase 4).

**Firestore:**

> **CORREGIDO EN G-03 (2026-09-02): el árbol real es `users/{uid}`, no `contadores/{uid}`.**
> `ProfileContext` ya guarda el perfil del contador en `users/{uid}` y
> `declaracionesHistory` cuelga `declaraciones` de ahí. Partir la cartera a otro árbol
> obligaría a dos reglas de seguridad para el mismo dueño y a migrar el perfil, que no era
> de esa tarea. El esquema de abajo se lee con `users/` en lugar de `contadores/`. Las reglas
> propuestas viven en `firestore.rules`, en la raíz del repo, **sin desplegar**.

```
users/{uid}                          # antes decía `contadores/{uid}`
  perfil: {nombre, cedula?, despacho?, rfc?, telefono, onboardingComplete, plan}
  clientes/{clienteId}
    datos: Cliente (ver schema) + {activo, numEmpleados, updatedAt}
    empleados/{empleadoId}
      datos: Empleado + {sbc_vigente, sbc_vigencia_desde, activo}
      movimientos/{movId}         # {tipo: alta|baja|reingreso|modificacion, fecha, sbc_anterior, sbc_nuevo, presentado_idse: bool, acuse?}
    nominas/{periodoId}           # {periodicidad, inicio, fin, fecha_pago, recibos: [ReciboResponse resumido], timbrado: pendiente|timbrado|error, totales}
    cuotas/{periodoId}            # {tipo: mensual|bimestral, CuotasResponse, conciliacion?: {fecha, diferencias[]}, pagado: bool}
    historial/{docId}             # equivalente a users/{uid}/declaraciones actual (categoría: sbc|cuotas|recibo|calendario)
```

**Security rules:** `request.auth.uid == uid` en toda la subcolección (ver `firestore.rules`). Futuro: `miembros/{uid}` con roles.

**Rutas:**

```
/                                   Landing (reutiliza hero de store, mensaje: "lleva 10 clientes con el tiempo de 1")
/login
/app/onboarding                     Wizard contador (2 pasos: datos + primer cliente opcional)
/app                                Dashboard: próximos vencimientos (todos los clientes), alertas variables, cuotas pendientes
/app/clientes                       Lista + alta de cliente
/app/clientes/:id                   Ficha: empleados, nóminas, cuotas, calendario del cliente
/app/clientes/:id/empleados         CRUD + importar CSV/XLSX + movimientos
/app/clientes/:id/nomina            Correr nómina del periodo → recibos → PDF/XML
/app/clientes/:id/cuotas            Precálculo mensual/bimestral → conciliación EMA → marcar pagado
/app/calendario                     Calendario global multi-cliente
/app/fiscal                         PREVIEW — servicios fiscales existentes (ver "Inversión de roles" abajo)
/app/perfil
```

**Inversión de roles nómina ↔ fiscal.** En `apps/store` el fiscal era lo principal e `imss-manager` salía como `coming_soon`. En `apps/despacho` se invierte: **nómina es el producto principal** y los servicios fiscales ya construidos (pre-declaración, DIOT, retenciones, multi-periodo, estado de cuenta, calendario SAT) aparecen en landing y dashboard como **"Próximamente" con preview abrible** — no una card muerta: al entrar a `/app/fiscal`, se cargan las pantallas ya programadas (tabs de `FiscalitoServicePage`, `XMLUploader`, `ResultadoDeclaracion`, etc.) portadas desde `apps/store`, funcionando en modo demo/preview contra los endpoints existentes de la API. Costo bajo porque la API ya los sirve; el trabajo es solo portar componentes y adaptarlos al contexto cliente-seleccionado. La promoción de "preview" a "módulo fiscal por cliente" completo es Fase 4.

**Reutilización desde `apps/store`:** `styles/global.css` (temas dark/light/vanilla), `components/voice/*` (useVoiceChat + VoiceChatUI), `components/common/*`, `services/firebase.ts`, `services/pdfUtils.ts`, `utils/format.ts`, patrón `fiscalAgentApi.ts` → `nominaApi.ts`, `agent/agentLoop.ts` con tools nuevos (`navegar`, `seleccionar_cliente`, `calcular_cuotas`, `correr_nomina`, `exportar_pdf`).

**Fiscalito (la IA/mascota):** mismo loop de voz/texto. Ejemplos de intents: "¿cuánto le toca pagar de IMSS a Tortillería López este mes?", "dame los variables que tengo que avisar en septiembre", "corre la quincena de Ferretería Ruiz".

### 3.4 Qué comparten fiscal y nómina (explícito)

| Pieza | Tipo | Detalle |
|---|---|---|
| `tablas_isr.py` TABLA_ISR_MENSUAL | código | ISR del recibo (Art. 96) |
| `constants.py` UMA / SM | código | ambas partes; refactor a funciones por vigencia |
| `llm_service.py`, `agent_tools.py` | código | explicaciones y tool loop |
| ISR retenido de nómina → declaración mensual del patrón | **datos** | output nómina = input `retenciones`/`pre-declaracion` |
| Recibos timbrados → egresos deducibles del patrón | **datos** | CFDIs de nómina entran como egreso en `calculadora.py` |
| Calendario | datos | fusionar obligaciones SAT + IMSS en una sola vista por cliente |

---

## 4. Fases → semilla de backlog

### Fase 0 — Fundamentos (sin código de producto)
- [ ] `knowledge_base/nomina/20–26` con los valores de la sección 2 y fuentes.
- [ ] Refactor `constants.py`: `uma_vigente(fecha)`, `salario_minimo_vigente(fecha, zona)`; migrar usos existentes; tests.
- [ ] **Conseguir caso real con la contadora**: 1 cliente, 1 bimestre completo → lista de empleados con SBC, EMA + EBA, archivo SUA pagado, recibos timbrados. Anonimizar. Es el `test_caso_real_*` que hace defendible el motor (equivalente al CADG620317EE0).
- [ ] Decidir con la contadora: tablas ISR periódicas vs prorrateo; tratamiento de ausentismos/incapacidades por ramo; resolución del quirk CEAV vs SM.

### Fase 1 — Motor (`nomina_engine`)
- [ ] `tablas_imss.py` 2026 + `tablas_isr_periodicas.py` + `subsidio_empleo()`.
- [ ] `integracion.py`: factor, SBC fijo/variable/mixto, clamp, `requiere_aviso` con fecha límite.
- [ ] `cuotas.py`: por ramo, por empleado, consolidado, mensual/bimestral, SM absorbe obrera, EyM excedente.
- [ ] `isr_nomina.py`: exenciones Art. 93, Art. 96, subsidio con vigencia enero/febrero.
- [ ] `recibo.py` + `cfdi_nomina_xml.py` (validación XSD).
- [ ] `calendario_laboral.py`.
- [ ] Routes + schemas + tests (unitarios + caso real). Explicación LLM con fallback.
- [ ] Tools de agente + `POST /agente/nomina`.

### Fase 2 — Frontend `apps/despacho`
- [ ] Scaffold Vite + reutilización de store; AuthContext; `ContadorContext` + `ClienteContext`.
- [ ] Onboarding contador; CRUD clientes; CRUD empleados + import CSV.
- [ ] Pantalla cuotas: precálculo → tabla por empleado/ramo → PDF → guardar historial.
- [ ] Pantalla nómina: periodo → recibos → PDF/XML.
- [ ] Dashboard multi-cliente con vencimientos y alertas de variables.
- [ ] Fiscalito voz/texto con tools nuevos.
- [ ] Cards "Próximamente" de servicios fiscales en landing/dashboard + `/app/fiscal` como **preview abrible**: portar tabs existentes de `apps/store` (`FiscalitoServicePage`, `XMLUploader`, `ResultadoDeclaracion`, etc.) contra los endpoints ya existentes de la API.
- [ ] Security rules + deploy Firebase Hosting.

### Fase 3 — Integraciones
- [ ] Conciliación EMA/EBA (parser + diff + explicación).
- [ ] PAC sandbox (Finkok/SW) → timbrado real; cancelación; almacenamiento de XML timbrado.
- [ ] Exportar archivo de movimientos para IDSE (formato .txt IMSS) y archivo para SUA.
- [ ] Alertas (email/n8n) antes de cada vencimiento.

### Fase 4 — Escala
- [ ] **Integrar servicios fiscales existentes (pre-declaración, DIOT, retenciones, multi-periodo, estado de cuenta) como módulo secundario por cliente**, consumiendo los endpoints ya existentes de la API: promover el preview de `/app/fiscal` a módulo completo, con datos ligados al cliente seleccionado (`clientes/{id}/historial`) y cruce nómina→fiscal (ISR retenido de nómina precargado en retenciones/pre-declaración del patrón).
- [ ] Despachos multi-usuario (roles), facturación del servicio, ISN por estado, PTU, finiquitos/liquidaciones, MCP server sobre la API.

---

## 5. Preguntas abiertas (validar con contadora antes de Fase 1)

1. ¿Tablas ISR semanal/quincenal del Anexo 8 o prorrateo de la mensual? ¿Qué hace su software actual (NOI/CONTPAQi)?
2. Redondeo: ¿por concepto por empleado (como SUA) o al consolidar?
3. Ausentismos e incapacidades: confirmar qué ramos se siguen cotizando en cada caso.
4. Quirk CEAV 2026: rango real para trabajadores entre 1 SM y 3 UMA.
5. Prestaciones superiores a la ley en sus clientes típicos (¿cuáles integran?).
6. ¿Cómo exportan hoy la EMA/EBA? (formato exacto para el parser de conciliación).
7. ¿Qué PAC usan? (para elegir sandbox).
8. ¿Sus clientes están en Veracruz? → ISN 3 % y ClaveEntFed en CFDI.

---

## 6. Fuentes

- INEGI, Comunicado 1/26 UMA 2026 — `inegi.org.mx/contenidos/saladeprensa/boletines/2026/uma/uma2026.pdf`; DOF 09-01-2026.
- CONASAMI / DOF 09-12-2025 — salarios mínimos 2026 ($315.04 general / $440.87 ZLFN).
- DOF 31-12-2025 — Decreto que modifica el subsidio para el empleo (15.02 %, transitorio
  15.59 % enero, tope $11,492.66). **Corrección F0-01:** este documento decía $536.22/mes para
  feb–dic; el articulado del decreto fija solo el **porcentaje**, y 15.02 % × $3,566.22 =
  **$535.65**. El $536.22 aparece únicamente en los considerandos y no se reconcilia con la
  fórmula. Detalle en `apps/api/knowledge_base/nomina/20_valores_referencia_2026.md` §4.
- DOF 16-12-2020 — Reforma LSS/SAR (transición CEAV 2023–2030). Tabla 2026 confirmada por IMSS y reproducida por IDC, ContadorMx, El Contribuyente.
- DOF 16-07-2026 — Acuerdo Consejo Técnico IMSS: e.firma único certificado, derogación NPIE (comunicado IMSS 380/2026).
- Ley del Seguro Social: Arts. 15, 25, 27, 28, 30, 34, 36, 71–74, 106, 107, 147, 168, 211.
- Ley del Infonavit Art. 29. LFT Arts. 76, 80, 87. LISR Arts. 93, 96. Anexo 8 RMF 2026.
- Guía de llenado del complemento de nómina 1.2 (SAT).
- ContadorMx, "Cuotas IMSS 2026: tablas, porcentajes y fechas" (tabla de ramos, factores, clases, calendario) — verificado contra LSS.
