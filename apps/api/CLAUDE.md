# FISCAL AGENT API - Contexto para Claude Code

## INFORMACIÓN DEL PROYECTO

**Tipo**: Microservicio backend — motor de inteligencia fiscal
**Parte de**: Ecosistema Fiscalito Store (hackaton Genius Arena 2026 - Track Capital One)
**Autor principal**: Ricardo Cabrera
**Estado**: MVP funcional con 78 tests pasando, 9 endpoints operativos

## PROPÓSITO

El Fiscal Agent API es el "cerebro contable" del ecosistema Fiscalito. Es un microservicio independiente que recibe datos fiscales del usuario (perfil + facturas CFDI) y devuelve cálculos de ISR/IVA, clasificaciones, explicaciones en lenguaje natural, advertencias y recomendaciones.

**NO ES**: Un chatbot ni un frontend
**ES**: Un motor de cálculo fiscal determinístico + LLM para explicaciones

### Principios de diseño:
- **Stateless**: No guarda datos del usuario. Todo viene en el request, se procesa, se responde.
- **Determinístico primero**: Los cálculos fiscales usan tablas ISR codificadas, NO el LLM. El LLM solo explica.
- **Dual LLM**: Configurable entre OpenAI y Anthropic vía .env. Si ninguno está disponible, fallback estático.
- **Reutilizable**: Cualquier app (Fiscalito Store, Fiscalito Flutter) puede consumirlo.

## TECH STACK

- **Framework**: FastAPI (Python)
- **Validación**: Pydantic v2
- **LLM**: OpenAI y/o Anthropic (configurable vía LLM_PROVIDER en .env)
- **Tests**: pytest
- **Server**: uvicorn
- **Deploy target**: Google Cloud Run (containerized, serverless)

## ARQUITECTURA DEL CÓDIGO

```
fiscal-agent-api/
├── .env                        # API keys (NO subir a git)
├── .env.example                # Template
├── pyproject.toml              # Dependencias y metadata
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + CORS + 8 routers registrados
│   ├── config.py               # Settings desde .env
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py           # GET /health
│   │   ├── declaraciones.py    # POST pre-declaracion, pre-declaracion-anual, deducciones-personales
│   │   ├── calendario.py       # POST calendario
│   │   ├── comparador.py       # POST comparar-regimenes
│   │   ├── diot.py             # POST diot
│   │   ├── retenciones.py      # POST retenciones-terceros
│   │   ├── multi_periodo.py    # POST multi-periodo
│   │   └── estado_cuenta.py    # POST estado-cuenta
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── fiscal.py           # PerfilContribuyente, CFDI, enums, ContributorType
│   │   ├── declaraciones.py    # PreDeclaracionRequest/Response, DesgloseFiscal
│   │   ├── deducciones.py      # DeduccionesPersonalesRequest/Response
│   │   ├── calendario.py       # CalendarioRequest/Response, ObligacionFiscalSchema
│   │   ├── comparador.py       # CompararRegimenRequest/Response
│   │   ├── diot.py             # DIOTRequest/Response, ProveedorDIOT
│   │   ├── retenciones.py      # RetencionesRequest/Response, TerceroRetencion
│   │   ├── estado_cuenta.py    # EstadoCuentaRequest/Response
│   │   └── multi_periodo.py    # MultiPeriodoRequest/Response, AcumuladoMultiPeriodo
│   ├── fiscal_engine/
│   │   ├── __init__.py
│   │   ├── tablas_isr.py       # Tablas ISR México 2026 (RESICO + Art. 96 + Art. 152)
│   │   ├── clasificador_gastos.py  # Clasificador deducibilidad por ClaveProdServ (Art. 105)
│   │   ├── calculadora.py      # Motor de cálculo: clasificar facturas, calcular ISR/IVA
│   │   ├── deducciones_personales.py  # Cálculo de deducciones personales (Art. 151 LISR)
│   │   ├── calendario.py       # Generador de calendario fiscal personalizado
│   │   ├── comparador.py       # Comparador RESICO vs Act. Empresarial
│   │   ├── diot.py             # Generador de DIOT (agrupación por proveedor)
│   │   ├── retenciones.py      # Resumen de retenciones a terceros
│   │   ├── estado_cuenta.py    # Estado de cuenta fiscal acumulado
│   │   └── multi_periodo.py    # Cálculo de múltiples periodos con acumulado
│   └── services/
│       ├── __init__.py
│       └── llm_service.py      # Explicaciones LLM (OpenAI / Anthropic / fallback)
├── knowledge_base/             # Referencia fiscal: tablas ISR, regímenes, DIOT, calendario 2026, RMF
│   ├── 00_fuentes_consulta.md
│   ├── 01_valores_referencia.md
│   ├── 02_isr_tablas_tarifas.md
│   ├── 03_resico_626.md
│   ├── 04_actividad_empresarial_612.md
│   ├── 05_asalariados_605.md
│   ├── 06_arrendamiento_606.md
│   ├── 07_plataformas_625.md
│   ├── 08_iva.md
│   ├── 09_diot.md
│   ├── 10_retenciones.md
│   ├── 11_deducciones_personales.md
│   ├── 12_calendario_fiscal_2026.md
│   ├── 13_rmf_2026_cambios.md
│   └── 14_cfdi_clasificacion.md
└── tests/
    ├── __init__.py
    ├── test_calculadora.py         # 59 tests en 20 clases (motor principal)
    ├── test_caso_real_enero2026.py  # 9 tests — caso real CADG enero 2026
    └── test_clasificador_gastos.py  # 10 tests — clasificador de gastos
```

## ENDPOINTS ACTUALES (9 endpoints)

### GET /health
Retorna estado del servicio (`status`, `service`, `version`).

### POST /api/v1/pre-declaracion
Pre-declaración mensual.
- Recibe: PerfilContribuyente + facturas[] + periodo_year + periodo_month (o periodo_bimestre)
- Calcula: ISR + IVA según régimen
- Retorna: DesgloseFiscal + explicación LLM + advertencias + recomendaciones

### POST /api/v1/pre-declaracion-anual
Pre-declaración anual.
- Recibe: PerfilContribuyente + TODAS las facturas del ejercicio + periodo_year
- Calcula: ISR anual + IVA anual
- Retorna: DesgloseFiscal + explicación + advertencias + recomendaciones

### POST /api/v1/deducciones-personales
Cálculo de deducciones personales para declaración anual.
- Recibe: ingresos_anuales + montos por concepto (médicos, colegiaturas, hipotecarios, etc.)
- Calcula: topes individuales + tope global (5 UMAs o 15%) + saldo a favor estimado
- Retorna: desglose por concepto + total deducible + saldo a favor estimado + explicación LLM

### POST /api/v1/calendario
Calendario fiscal personalizado.
- Recibe: contributor_type + regimen + rfc + year
- Genera: lista de obligaciones fiscales con fechas límite ajustadas por 6to dígito del RFC

### POST /api/v1/comparar-regimenes
Comparador RESICO vs Actividad Empresarial.
- Recibe: ingresos_mensuales_estimados + gastos_mensuales_estimados
- Simula: ISR anual en ambos regímenes
- Retorna: ISR por régimen + diferencia + recomendación + explicación LLM

### POST /api/v1/diot
Generador de DIOT (Declaración Informativa de Operaciones con Terceros).
- Recibe: PerfilContribuyente + facturas[] + periodo_year + periodo_month
- Genera: egresos agrupados por proveedor (RFC, total operaciones, IVA pagado)

### POST /api/v1/retenciones-terceros
Resumen de retenciones a terceros.
- Recibe: PerfilContribuyente + facturas[] + periodo
- Genera: retenciones ISR/IVA agrupadas por tercero

### POST /api/v1/multi-periodo
Cálculo de múltiples periodos a la vez.
- Recibe: PerfilContribuyente + facturas[] + periodo_year + periodos[]
- Calcula: declaración por cada periodo + acumulado + tendencia

### POST /api/v1/estado-cuenta
Estado de cuenta fiscal acumulado del ejercicio.
- Recibe: PerfilContribuyente + facturas[] + periodo_year
- Calcula: totales acumulados, ISR anual estimado, proyección anual, advertencias

## SCHEMAS ACTUALES (CONTRATO)

### PerfilContribuyente (schemas/fiscal.py)
```python
rfc: str                    # RFC del contribuyente
regimen: str                # Código SAT (ej: "626")
nombre: str = ""
tipo_persona: str = "fisica"
actividad_economica: str = ""
periodicidad: PeriodicidadDeclaracion = MENSUAL
tiene_empleados: bool = False
retenedor_iva: bool = False
fecha_inicio_actividades: date | None = None
contributor_type: ContributorType | None = None  # asalariado, independiente, arrendamiento, plataformas, pyme
```

### CFDI (schemas/fiscal.py)
```python
uuid: str
fecha: date
tipo: TipoFactura           # I=Ingreso, E=Egreso, T=Traslado, P=Pago
rfc_emisor: str
rfc_receptor: str
subtotal: float
total: float
iva_trasladado: float = 0
iva_retenido: float = 0
isr_retenido: float = 0
descuento: float = 0
uso_cfdi: str = "G03"
descripcion: str = ""
clave_prod_serv: str = ""          # ClaveProdServ SAT (8 dígitos)
metodo_pago: str = "PUE"          # PUE o PPD
uuid_relacionado: str | None = None  # Para complementos de pago tipo P
monto_pago: float | None = None     # Monto pagado (solo tipo P)
```

### Enums (schemas/fiscal.py)
- `RegimenFiscal`: RESICO (626), ACTIVIDAD_EMPRESARIAL (612), HONORARIOS (612, alias), SUELDOS_SALARIOS (605), ARRENDAMIENTO (606), PLATAFORMAS_TECNOLOGICAS (625), RIF (621)
- `TipoFactura`: INGRESO (I), EGRESO (E), TRASLADO (T), PAGO (P)
- `PeriodicidadDeclaracion`: MENSUAL, BIMESTRAL (legacy, no usado por RESICO), ANUAL
- `ContributorType`: ASALARIADO, INDEPENDIENTE, ARRENDAMIENTO, PLATAFORMAS, PYME

## MOTOR DE CÁLCULO (fiscal_engine/)

### calculadora.py — Motor principal
1. `clasificar_facturas()` — separa ingresos y egresos según RFC, respetando flujo de efectivo (Art. 102):
   - **PUE**: se acumula en el mes de emisión
   - **PPD**: se ignora hasta que llegue complemento de pago (tipo P)
   - **Tipo P**: acumula proporcionalmente con fecha del pago, buscando la factura PPD original por `uuid_relacionado`
2. `calcular_isr_resico()` — tasa fija (1%-2.5%) sobre ingresos brutos
3. `calcular_isr_general()` — tabla progresiva Art. 96 (mensual) o Art. 152 (anual). Soporta `meses_acumulados` para pagos provisionales Art. 106
4. `calcular_declaracion()` — orquesta todo: clasifica, calcula ISR según régimen, calcula IVA. Acepta `periodo_month` para pagos provisionales acumulativos (612)

### deducciones_personales.py — Deducciones Art. 151 LISR
- `calcular_deducciones_personales()` — aplica topes individuales por concepto + tope global
- Conceptos: gastos médicos, colegiaturas (con tope por nivel), intereses hipotecarios, donativos (7%), aportaciones retiro (10%), seguros médicos, transporte escolar, funerarios (1 UMA)
- Tope global: menor entre 5 UMAs anuales ($213,926.50) y 15% de ingresos

### calendario.py — Calendario fiscal
- `generar_calendario()` — genera obligaciones según contributor_type y régimen
- Ajusta fechas límite según 6to dígito del RFC (días hábiles extra después del día 17)

### clasificador_gastos.py — Clasificador de deducibilidad (Art. 105 LISR)
- `es_gasto_deducible()` — clasifica por ClaveProdServ (3 niveles: personal, deducible, gris)
- `clasificar_egresos()` — filtra egresos en deducibles vs personales
- `inferir_actividad_contribuyente()` — deduce giro del contribuyente de sus facturas emitidas
- 16 divisiones personales (alimentos, medicinas, muebles hogar, colchones, etc.)
- 11 divisiones siempre deducibles (combustible, TI, oficina, contabilidad, transporte, etc.)
- Excepciones por actividad: restaurantero puede deducir alimentos, etc.
- Aplica solo a regímenes 612 y 606

### comparador.py — Comparador de regímenes
- `comparar_regimenes()` — simula ISR anual en RESICO vs Act. Empresarial
- Verifica tope RESICO ($3.5M anuales)

### diot.py — DIOT
- `generar_diot()` — agrupa egresos por proveedor con totales de operaciones e IVA

### retenciones.py — Retenciones
- `generar_resumen_retenciones()` — agrupa retenciones ISR/IVA por tercero

### estado_cuenta.py — Estado de cuenta
- `generar_estado_cuenta()` — acumulados del ejercicio, proyección anual, advertencias RESICO

### multi_periodo.py — Multi-periodo
- `calcular_multi_periodo()` — calcula declaraciones para múltiples meses/bimestres + acumulado + tendencia

### Regímenes soportados en calculadora:
- **626 (RESICO)**: ISR tasa fija sobre ingresos brutos. SIN deducciones operativas. Pagos MENSUALES (Art. 113-E).
- **612 (Act. Empresarial)**: ISR tabla progresiva. CON deducciones (ingresos - gastos).
- **605 (Sueldos/Salarios)**: ISR tabla progresiva. Solo en anual con deducciones personales.
- **606 (Arrendamiento)**: ISR tabla progresiva acumulativa (Art. 116/106). Comparación automática deducción ciega (35%) vs gastos reales.
- **625 (Plataformas)**: Si ingresos anualizados <= $300k, retenciones como pago definitivo. Si no, declaración normal.
- **Genérico**: Cualquier otro régimen usa tabla general con deducciones.

## TABLAS ISR (fiscal_engine/tablas_isr.py)

- `RESICO_TASAS_MENSUALES`: 5 rangos, 1.00% a 2.50%
- RESICO PF es MENSUAL (Art. 113-E). Los bimestrales eran del RIF (eliminado 2022)
- `TABLA_ISR_MENSUAL`: Art. 96 LISR 2026, 11 rangos (1.92% a 35%)
- `TABLA_ISR_ANUAL`: Art. 152 LISR 2026, 11 rangos
- `TASA_IVA`: 0.16 (16%)
- `TASA_IVA_FRONTERA`: 0.08 (8%)
- `TASA_RETENCION_IVA`: 2/3
- `UMA_DIARIA_2026`: 117.22
- `LIMITE_DEDUCCIONES_PERSONALES`: 5 UMAs anuales ($213,926.50)

## SERVICIO LLM (services/llm_service.py)

- `generar_explicacion()` — explicación de pre-declaraciones (mensual/anual)
- `generar_explicacion_deducciones()` — explicación de deducciones personales
- `generar_explicacion_comparacion()` — explicación de comparación de regímenes
- `generar_explicacion_diot()` — explicación de DIOT
- `generar_explicacion_retenciones()` — explicación de retenciones a terceros
- `generar_explicacion_multi_periodo()` — explicación de análisis multi-periodo
- `generar_explicacion_estado_cuenta()` — explicación de estado de cuenta fiscal
- `_fallback_explicacion()` — resumen estático cuando el LLM no está disponible
- Providers: OpenAI (`gpt-4o-mini` default) o Anthropic (`claude-haiku-4-5-20251001` default)

## TESTS (78/78 pasando)

### test_calculadora.py (59 tests, 20 clases)
- `TestClasificarFacturas` (2): clasificación por RFC, case insensitive
- `TestISRResico` (4): rangos 1%, 1.1%, 2.5%, cero ingresos
- `TestISRGeneral` (2): cálculo básico mensual, anual
- `TestDeclaracionCompleta` (4): RESICO mensual, empresarial mensual, IVA, sin facturas
- `TestDeduccionesPersonales` (4): bajo tope, tope 5 UMAs, tope 15%, tope colegiaturas
- `TestDeduccionCiega` (3): ciega conviene con pocos gastos, real conviene con muchos, ciega incluye predial
- `TestPlataformas` (5): ingresos bajos retenciones definitivas, ingresos altos declaración normal, filtra gastos personales, pago definitivo no calcula IVA, no definitivo sí calcula IVA
- `TestCalendario` (3): asalariado solo anual, independiente RESICO 13 obligaciones (12 mensuales + 1 anual), ajuste fecha por RFC
- `TestArrendamientoRecomendaciones` (1): régimen 606 nunca recibe recomendación RESICO
- `TestArrendamientoISR` (3): tasa efectiva arrendamiento, tasa cero con base cero, tabla acumulativa Art. 116/106
- `TestComparador` (3): RESICO conviene, empresarial conviene, tope RESICO excedido
- `TestDIOT` (2): agrupa por proveedor, solo incluye egresos
- `TestRetenciones` (2): agrupa retenciones por tercero, sin retenciones lista vacía
- `TestMultiPeriodo` (2): separa y calcula por mes, acumulado suma correctamente
- `TestEstadoCuenta` (3): acumulados suman correctamente, RESICO cerca del tope genera advertencia, excluye PPD sin complemento
- `TestTablaAcumulada` (2): tabla acumulada meses=1 equivale a base, meses=2 duplica límites/cuotas
- `TestPagosProvisionalesArt106` (4): ISR mensual base $8,825.80, ISR acumulado 2 meses, resta pagos anteriores, no genera ISR negativo
- `TestFlujoEfectivo` (5): PUE se acumula, PPD no se acumula, PPD+complemento se acumula, pago parcial proporcional, gasto PPD sin complemento no deducible
- `TestCasoRealCADG` (1): caso real CADG620317EE0 enero 2026 — PUE/PPD mixto, base $17,120.80, ISR $1,782.87
- `TestIVAAcreditable` (4): IVA usa valor XML con descuento (no recalcula), PPD sin complemento no acreditable, RESICO IVA no acredita gastos personales, RESICO ISR no cambia con clasificador

### test_caso_real_enero2026.py (9 tests, 1 clase)
- `TestCasoRealEnero2026` (9): validación completa caso CADG620317EE0 — ingresos, deducciones efectivas, base ISR, ISR causado, IVA cobrado, IVA acreditable, IVA retenido, IVA saldo a favor, total a pagar

### test_clasificador_gastos.py (10 tests, 1 clase)
- `TestClasificadorGastos` (10): alimentos no deducible/sí para restaurantero, contador deducible, medicinas/colchón no deducible, estacionamiento/energía deducible, sin clave beneficio duda, división gris, caso real comisionista

## PERFILES DE CONTRIBUYENTE

El sistema soporta 5 tipos de contribuyente (enum `ContributorType`). El tipo afecta la lógica de cálculo y el calendario:

### asalariado (régimen 605)
- NO declara mensualmente (su patrón retiene ISR)
- Solo usa declaración anual para recuperar saldo a favor
- Endpoint de deducciones personales para gastos médicos, colegiaturas, seguros, etc.
- Tope de deducciones: 5 UMAs anuales o 15% de ingresos

### independiente (régimen 626 o 612)
- Declaración mensual (612 y 626 RESICO)
- Si RESICO: tasa fija, sin deducciones operativas
- Si Act. Empresarial: tabla progresiva, con deducciones

### arrendamiento (régimen 606)
- Declaración mensual ISR/IVA
- Comparación automática deducción ciega del 35% vs gastos reales (elige la que resulte en menor ISR)

### plataformas (régimen 625)
- Las plataformas (Uber, Rappi, etc.) ya retienen ISR/IVA
- Si ingresos < $300,000 anuales: retenciones como pago definitivo
- Si ingresos > $300,000: declaración normal con acreditamiento de retenciones

### pyme (régimen 612 o 626)
- Todo lo de independiente + retenciones de nómina a empleados
- Obligaciones adicionales: DIOT mensual

## CONTEXTO FISCAL MEXICANO

### Términos:
- **ISR**: Impuesto Sobre la Renta
- **IVA**: Impuesto al Valor Agregado (16%)
- **CFDI**: Factura electrónica XML
- **RFC**: Registro Federal de Contribuyentes
- **RESICO**: Régimen Simplificado de Confianza (tasas fijas 1%-2.5%)
- **UMA**: Unidad de Medida y Actualización ($117.22/día en 2026)
- **Deducción ciega**: Deducir 35% de ingresos sin comprobar gastos (solo arrendamiento)
- **DIOT**: Declaración Informativa de Operaciones con Terceros

### Calendario:
- Día 17: declaración mensual (varía por 6to dígito RFC)
- Día 17: declaración mensual RESICO (Art. 113-E)
- Abril: anual personas físicas
- Marzo: anual personas morales

## REGLAS DE CÓDIGO

### SIEMPRE:
- Type hints en todas las funciones
- Docstrings en español en clases y funciones públicas
- Tests para toda lógica de cálculo nueva
- Correr `pytest tests/ -v` después de cada cambio
- Mantener el motor determinístico (tablas codificadas, no LLM para cálculos)

### NUNCA:
- Usar el LLM para calcular ISR/IVA (solo para explicaciones)
- Hardcodear API keys
- Guardar datos del usuario (stateless)
- Romper los 78 tests existentes
- Cambiar las tablas ISR sin fuente oficial
