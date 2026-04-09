# Fiscal Agent API

Motor de inteligencia fiscal independiente para el ecosistema **Fiscalito Store** .

Hackaton Genius Arena 2026 — Track Capital One.

## Que hace

Recibe datos fiscales del usuario (perfil + facturas CFDI) y devuelve:
- **Pre-declaraciones mensuales/bimestrales/anuales** — calculo automatico de ISR/IVA
- **Deducciones personales** — calcula topes individuales y globales, estima saldo a favor
- **Calendario fiscal personalizado** — obligaciones con fechas ajustadas por RFC
- **Comparacion de regimenes** — simula ISR en RESICO vs Act. Empresarial
- **Explicaciones en lenguaje natural** — cada calculo incluye explicacion generada por LLM
- **Advertencias y recomendaciones** — detecta anomalias y sugiere optimizaciones

## 5 tipos de contribuyente soportados

| Tipo | Regimen | Declaracion | Caracteristicas |
|------|---------|-------------|-----------------|
| **asalariado** | 605 | Solo anual | Patron retiene ISR. Deducciones personales para saldo a favor |
| **independiente** | 626 / 612 | Bimestral (RESICO) o mensual (612) | RESICO: tasa fija 1%-2.5%. Act. Empresarial: tabla progresiva con deducciones |
| **arrendamiento** | 606 | Mensual | Elige automaticamente entre deduccion ciega (35%) y gastos reales |
| **plataformas** | 625 | Mensual | Ingresos <= $300k anuales: retenciones como pago definitivo |
| **pyme** | 612 / 626 | Mensual | Incluye obligaciones DIOT y retenciones de nomina |

## Arquitectura

```
fiscal-agent-api/
├── app/
│   ├── main.py                         # FastAPI app + CORS + routers
│   ├── config.py                       # Settings (.env)
│   ├── routes/
│   │   ├── health.py                   # GET /health
│   │   ├── declaraciones.py            # pre-declaracion, pre-declaracion-anual, deducciones-personales
│   │   ├── calendario.py               # calendario fiscal personalizado
│   │   └── comparador.py               # comparacion de regimenes
│   ├── schemas/
│   │   ├── fiscal.py                   # PerfilContribuyente, CFDI, ContributorType (el contrato)
│   │   ├── declaraciones.py            # PreDeclaracion Request/Response, DesgloseFiscal
│   │   ├── deducciones.py              # DeduccionesPersonales Request/Response
│   │   ├── calendario.py               # Calendario Request/Response
│   │   └── comparador.py               # CompararRegimen Request/Response
│   ├── fiscal_engine/
│   │   ├── tablas_isr.py               # Tablas ISR Mexico 2025 (RESICO, Art. 96, Art. 152)
│   │   ├── calculadora.py              # Motor de calculo ISR/IVA (deduccion ciega, plataformas)
│   │   ├── deducciones_personales.py   # Topes individuales y globales (5 UMAs / 15%)
│   │   ├── calendario.py               # Generador de obligaciones fiscales
│   │   └── comparador.py               # Simulacion RESICO vs Act. Empresarial
│   └── services/
│       └── llm_service.py              # OpenAI / Anthropic / fallback estatico
└── tests/
    └── test_calculadora.py             # 26 tests
```

## Principios de diseno

- **Stateless**: no guarda datos del usuario. Todo viene en el request.
- **Determinista**: los calculos fiscales son matematicos, no dependen del LLM.
- **LLM solo para explicaciones**: el motor calcula, el LLM explica.
- **Dual LLM**: configurable entre OpenAI y Anthropic via `.env`.
- **Reutilizable**: cualquier app (Fiscalito Store, Fiscalito Flutter) puede consumirlo.

## Setup

```bash
# 1. Instalar dependencias
pip install -e ".[dev]"

# 2. Configurar
cp .env.example .env
# Editar .env con tu API key

# 3. Correr tests (26 tests)
pytest tests/ -v

# 4. Levantar servidor
uvicorn app.main:app --reload --port 8000
```

Documentacion interactiva disponible en `http://localhost:8000/docs`.

## Endpoints

### `GET /health`
Health check del servicio.

### `POST /api/v1/pre-declaracion`
Pre-declaracion mensual o bimestral. Recibe perfil del contribuyente + facturas del periodo. Calcula ISR/IVA segun regimen.

### `POST /api/v1/pre-declaracion-anual`
Pre-declaracion anual. Recibe todas las facturas del ejercicio fiscal.

### `POST /api/v1/deducciones-personales`
Calcula deducciones personales para declaracion anual: gastos medicos, colegiaturas (con topes por nivel), intereses hipotecarios, donativos, aportaciones al retiro, seguros, transporte escolar y funerarios. Aplica tope global (menor entre 5 UMAs anuales y 15% de ingresos). Estima saldo a favor de ISR.

### `POST /api/v1/calendario`
Genera calendario de obligaciones fiscales personalizado segun tipo de contribuyente, regimen y RFC. La fecha limite del dia 17 se ajusta segun el 6to digito numerico del RFC.

### `POST /api/v1/comparar-regimenes`
Simula ISR anual en RESICO (626) vs Actividad Empresarial (612). Considera el tope de $3.5M para RESICO. Recomienda el regimen mas conveniente segun ingresos y gastos.

## Ejemplo de request

```json
{
  "contribuyente": {
    "rfc": "CAUA030101ABC",
    "regimen": "626",
    "nombre": "Timmy Freelancer",
    "contributor_type": "independiente"
  },
  "facturas": [
    {
      "uuid": "AAA-111",
      "fecha": "2025-01-10",
      "tipo": "I",
      "rfc_emisor": "CAUA030101ABC",
      "rfc_receptor": "EMPRESA_RFC",
      "subtotal": 15000.00,
      "total": 17400.00,
      "iva_trasladado": 2400.00,
      "isr_retenido": 1500.00
    }
  ],
  "periodo_year": 2025,
  "periodo_month": 1,
  "incluir_explicacion": true
}
```

## Tests

26 tests pasando:

- **TestClasificarFacturas** (2) — clasificacion por RFC, case insensitive
- **TestISRResico** (4) — rangos 1%, 1.1%, 2.5%, cero ingresos
- **TestISRGeneral** (2) — calculo basico mensual y anual
- **TestDeclaracionCompleta** (4) — RESICO mensual, empresarial mensual, IVA, sin facturas
- **TestDeduccionesPersonales** (4) — bajo tope, tope 5 UMAs, tope 15%, colegiaturas por nivel
- **TestDeduccionCiega** (2) — ciega conviene vs real conviene
- **TestPlataformas** (2) — retenciones definitivas vs declaracion normal
- **TestCalendario** (3) — asalariado solo anual, RESICO 7 obligaciones, ajuste por RFC
- **TestComparador** (3) — RESICO conviene, empresarial conviene, tope excedido

## Tech stack

- **Framework**: FastAPI (Python)
- **Validacion**: Pydantic v2
- **LLM**: OpenAI y/o Anthropic (configurable via `LLM_PROVIDER` en .env)
- **Tests**: pytest
- **Server**: uvicorn
- **Deploy target**: Google Cloud Run

## Integracion con Fiscalito (Flutter)

Fiscalito necesita agregar estos campos al `CfdiModel`:
- `subtotal`, `iva_trasladado`, `iva_retenido`, `isr_retenido`, `descuento`, `uso_cfdi`

Y crear un `FiscalAgentService` en Dart que haga POST a estos endpoints
enviando el perfil del usuario + sus facturas del periodo.

## Autor

Desarrollado por **Ricardo Cabrera**.
