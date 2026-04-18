# FISCALITO STORE — Contexto para Claude Code

## INFORMACION CRITICA

**Autor principal**: Ricardo Cabrera
**Tipo**: Proyecto para hackaton Genius Arena 2026 (Track: Capital One — Finanzas para un Futuro Sostenible)
**Deadline**: Dias, no semanas
**Restriccion de costo**: Servicios gratuitos o free tier. LLM (OpenAI/Anthropic) es el unico gasto.

## PROPOSITO

Fiscalito Store es un **marketplace web de servicios inteligentes para PYMEs y personas fisicas mexicanas**. Cada servicio del marketplace resuelve una obligacion legal o financiera (fiscal, laboral, contable).

El primer servicio es **Fiscalito**: un asistente fiscal cuyo backend es el **Fiscal Agent API** (FastAPI/Python, proyecto separado, funcional con 12 tests en su propio repo). Calcula pre-declaraciones ISR/IVA, clasifica CFDIs, detecta saldos a favor, y explica cada calculo con LLM. Incluye un **chat de voz con IA** (Whisper STT + GPT-4o-mini + TTS) integrado como boton flotante en toda la app.

**NO ES**: Un chatbot generico ni un curso de finanzas.
**ES**: Una tienda de microservicios donde cada uno calcula como contador y explica como maestro.

## TECH STACK

- **Frontend**: React 19 + Vite 6 + TypeScript 5.6
- **Auth**: Firebase Auth (email + Google) — proyecto Firebase `fiscalito-mvp`
- **DB**: Firestore (plan gratuito) para perfiles de usuario y historial de declaraciones
- **Backend fiscal**: Fiscal Agent API (FastAPI/Python) corriendo en localhost:8000 o Cloud Run
- **LLM (backend)**: OpenAI / Anthropic (configurable via env, usado por el Fiscal Agent API)
- **LLM (frontend)**: OpenAI API directa desde el cliente — Whisper STT, GPT-4o-mini (chat de voz), TTS-1 voz "nova"
- **Styling**: CSS custom con variables (NO Tailwind, NO component libraries)
- **Icons**: lucide-react ^0.468.0
- **Router**: react-router-dom v7
- **PDF**: jspdf ^4.2.1 + jspdf-autotable ^5.0.7

## PALETA DE COLORES — OBLIGATORIA

```
/* Backgrounds */
--bg-dark: #080409          (fondo principal, casi negro)
--bg-surface: #0f0a12       (fondo sidebar)
--bg-card: #130e17          (fondo cards)
--bg-card-hover: #1a1320    (hover en cards)
--bg-input: #1a1520         (fondo de inputs)

/* Purple ramp */
--purple-deep: #2d1436      (purple oscuro)
--purple: #492153           (acento principal, botones, badges)
--purple-light: #6b3580     (hover states, gradient end)
--purple-muted: rgba(73, 33, 83, 0.4)

/* Teal ramp */
--teal-deep: #1a2527        (superficies secundarias)
--teal: #355654             (bordes activos, elementos interactivos)
--teal-light: #6e9fa0       (texto accent, stats, highlights)
--teal-muted: rgba(110, 159, 160, 0.3)

/* Text */
--text-primary: #e8e4ec     (texto principal, blanco calido)
--text-secondary: #9a8fa3   (texto secundario, labels)
--text-muted: #5c5264       (texto deshabilitado, hints)
--text-on-accent: #ffffff   (texto sobre fondos de acento)

/* Accents */
--success: #2ecc71          (valores positivos, saldo a favor)
--warning: #e0a060          (advertencias)
--danger: #e74c3c           (errores, montos negativos)

/* Tambien definidos: --border, --radius, --shadow (ver global.css) */
```

Gradiente principal: `linear-gradient(135deg, #492153, #355654)`
Tipografia: **Outfit** (UI) + **JetBrains Mono** (codigo/datos)

NUNCA usar colores fuera de esta paleta. NUNCA usar fondos blancos o claros. Es SIEMPRE dark theme.

## ESTRUCTURA DEL PROYECTO

```
fiscalito-store-app/
├── .env                        # Firebase keys + Fiscal Agent URL (NO subir a git)
├── .env.example                # Template sin valores reales
├── firebase.json               # Hosting config (public: dist, SPA rewrites, headers de cache)
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx                # Entry point + Router + AuthProvider + ProfileProvider
│   ├── vite-env.d.ts
│   ├── styles/
│   │   └── global.css          # Variables CSS, utility classes, tema global
│   ├── context/
│   │   ├── AuthContext.tsx      # Firebase Auth provider + hooks (signIn, signUp, signInWithGoogle, signOut)
│   │   └── ProfileContext.tsx   # Perfil de contribuyente + sync con Firestore
│   ├── components/
│   │   ├── AppLayout.tsx        # Sidebar + layout + guards (authLoading, user, onboarding)
│   │   ├── ProtectedRoute.tsx   # Guard de autenticacion
│   │   ├── FiscalitoVoiceChat.tsx # Wrapper delgado — boton flotante + panel (usa voice/)
│   │   ├── common/              # ErrorAlert, SuccessNotice
│   │   ├── historial/           # HistorialCard, HistorialFilters, ExpandedDetail
│   │   ├── onboarding/          # Step{Tipo,DatosFiscales,DatosPersonales,Confirmar} + WizardProgress + styles.ts
│   │   ├── voice/               # useVoiceChat (hook: STT/Chat/TTS + VAD) + VoiceChatUI
│   │   └── fiscalito/           # Tabs del servicio Fiscalito
│   │       ├── PreDeclaracionTab.tsx      # Upload XML + calculo pre-declaracion
│   │       ├── XMLUploader.tsx            # Drag & drop de archivos XML CFDI
│   │       ├── PeriodSelector.tsx         # Selector de año + mes/bimestre
│   │       ├── ResultadoDeclaracion.tsx   # Resultado con desglose + explicacion IA + export PDF
│   │       ├── DeduccionesResult.tsx      # Resultado de deducciones personales
│   │       ├── FacturaTable.tsx           # Tabla de facturas compartida entre tabs
│   │       ├── CalendarioTab.tsx          # Calendario de obligaciones fiscales
│   │       ├── CompararRegimenTab.tsx     # Comparador RESICO vs Empresarial
│   │       ├── DIOTTab.tsx                # Generacion de DIOT
│   │       ├── RetencionesTab.tsx         # Retenciones a terceros
│   │       ├── MultiPeriodoTab.tsx        # Analisis multi-periodo
│   │       ├── EstadoCuentaTab.tsx        # Estado de cuenta y proyeccion anual
│   │       └── DeduccionesPersonalesTab.tsx # Deducciones personales (asalariados)
│   ├── pages/
│   │   ├── LandingPage.tsx          # Pagina publica (hero, stats, preview servicios)
│   │   ├── LoginPage.tsx            # Login/Register con Firebase (email + Google)
│   │   ├── OnboardingWizard.tsx     # Wizard 4 pasos post-registro
│   │   ├── DashboardPage.tsx        # Vista general: stats, servicios activos, declaraciones recientes
│   │   ├── MarketplacePage.tsx      # Catalogo de servicios con filtros por categoria
│   │   ├── ServiceDetailPage.tsx    # Detalle de servicio + docs API + ejemplo request/response
│   │   ├── FiscalitoServicePage.tsx # Interfaz principal de Fiscalito con tabs
│   │   ├── HistorialPage.tsx        # Historial de declaraciones con filtros y export PDF
│   │   ├── ProfilePage.tsx          # Datos del contribuyente (RFC, regimen, tipo)
│   │   └── AdminPage.tsx            # Panel de admin (gestion servicios/usuarios)
│   ├── services/
│   │   ├── firebase.ts              # Config Firebase (initializeApp, auth, db)
│   │   ├── storeServices.ts         # Catalogo de servicios del marketplace
│   │   ├── contributorProfiles.ts   # Definiciones de perfiles de contribuyente
│   │   ├── fiscalAgentApi.ts        # Cliente REST para Fiscal Agent API (todos los endpoints)
│   │   ├── cfdiParser.ts            # Parser de XML CFDI v3/v4 (DOMParser, sin deps externas)
│   │   ├── declaracionesHistory.ts  # CRUD Firestore para historial de declaraciones
│   │   ├── pdfExport.ts             # PDF de pre-declaracion
│   │   ├── pdfExportDIOT.ts         # PDF de DIOT
│   │   ├── pdfExportRetenciones.ts  # PDF de retenciones
│   │   ├── pdfExportMulti.ts        # PDF multi-periodo
│   │   ├── pdfExportEstado.ts       # PDF estado de cuenta
│   │   ├── pdfUtils.ts              # Helpers compartidos para exports PDF (colores, tablas)
│   │   └── voiceChatService.ts      # OpenAI Whisper STT + GPT-4o-mini chat + TTS-1 (voz nova) + VAD
│   └── utils/
│       ├── format.ts                # fmtMoney y helpers de formateo
│       └── styles.ts                # Objetos de estilo inline compartidos (tablas, badges)
```

## RUTAS

```
/                              → LandingPage (publica)
/login                         → LoginPage (publica)
/app/onboarding                → OnboardingWizard (protegida, sin sidebar)
/app                           → DashboardPage (protegida, con sidebar)
/app/historial                 → HistorialPage (protegida)
/app/store                     → MarketplacePage (protegida)
/app/store/fiscalito/use       → FiscalitoServicePage (protegida, interfaz principal del servicio)
/app/store/:serviceId          → ServiceDetailPage (protegida)
/app/profile                   → ProfilePage (protegida)
/app/admin                     → AdminPage (protegida)
```

## PERFILES DE CONTRIBUYENTE

Definidos en `src/services/contributorProfiles.ts`. El campo `contributorType` determina que servicios y tabs ve el usuario:

| Tipo | Regimenes | Servicios visibles | Tabs Fiscalito |
|------|-----------|-------------------|----------------|
| asalariado | 605 | Fiscalito | Deducciones personales, Calendario |
| independiente (RESICO) | 626 | Fiscalito | Declaracion, Calendario, Comparar, Estado cuenta |
| independiente (Empresarial) | 612 | Fiscalito | Declaracion, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |
| arrendamiento | 606 | Fiscalito | Declaracion, Calendario, Comparar, Multi-periodo, Estado cuenta |
| plataformas | 625 | Fiscalito | Declaracion, Calendario, Estado cuenta |
| pyme | 612, 626, 621 (RIF) | Fiscalito + IMSS Manager + Contabilito | Declaracion, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |

**Nota**: La logica de filtrado de tabs esta en `FiscalitoServicePage.tsx:getTabsForProfile()`. Los tabs se filtran por `contributorType` y luego por `regimen`.

### Wizard de onboarding (post-registro)
Despues de registrarse, el usuario pasa por un wizard de 4 pasos en `OnboardingWizard.tsx`:
1. **Tipo de contribuyente** — card selector visual con iconos
2. **Datos fiscales** — RFC + regimen (filtrado por tipo) + campos PYME (nombre negocio, num empleados)
3. **Datos personales** — nombre completo, telefono, actividad economica, codigo postal
4. **Confirmacion** — resumen de todo lo configurado con boton "Comenzar"

El wizard guarda en Firestore y se puede editar despues en ProfilePage.

## INVARIANTES DE CONTEXTOS Y GUARDS

- **ProfileContext espera a AuthContext**: mientras `useAuth().loading === true`, `ProfileContext` mantiene `loading=true` y no dispara la carga de Firestore. Nunca devolver `DEFAULT_PROFILE` con `loading=false` antes de que auth resuelva — provoca navegaciones erróneas al onboarding.
- **Orden de guards en `AppLayout`**: (1) `authLoading || profileLoading` → Loader; (2) `!user` → `<Navigate to="/login" replace />`; (3) `!isOnboardingComplete()` → `<Navigate to="/app/onboarding" replace />`; (4) render normal.
- **Guards en `OnboardingWizard`**: Loader durante cualquier loading → `/login` si `!user` → `/app` si `isOnboardingComplete()`. El wizard se auto-redirige; no asume que fue alcanzable solo post-registro.
- **Tab activo de `FiscalitoServicePage` derivado de URL**: el tab es `useMemo` sobre `?tab=` de `searchParams`, NO `useState`. Los clicks usan `setSearchParams({ tab: id }, { replace: true })`. No existe `setActiveTab`.
- **Checklist para agregar un tab nuevo a Fiscalito**: (1) el tipo `Tab`, (2) `ALL_TABS`, (3) `getTabsForProfile` si aplica a algún perfil, (4) `TAB_PARAM_MAP` si el slug externo difiere del id interno.

## FISCAL AGENT API (backend, proyecto separado)

URL: `http://localhost:8000` (dev) o variable `VITE_FISCAL_AGENT_URL`
Docs: `http://localhost:8000/docs` (Swagger)

### Endpoints consumidos desde el frontend (`src/services/fiscalAgentApi.ts`):

| Metodo | Endpoint | Proposito |
|--------|----------|-----------|
| GET | `/health` | Healthcheck |
| POST | `/api/v1/pre-declaracion` | Declaracion mensual o bimestral ISR/IVA |
| POST | `/api/v1/pre-declaracion-anual` | Declaracion anual |
| POST | `/api/v1/deducciones-personales` | Deducciones personales (asalariados) |
| POST | `/api/v1/calendario` | Calendario de obligaciones fiscales |
| POST | `/api/v1/comparar-regimenes` | Comparacion RESICO vs Empresarial |
| POST | `/api/v1/diot` | Generacion de DIOT (reporte proveedores) |
| POST | `/api/v1/retenciones-terceros` | Retenciones a terceros |
| POST | `/api/v1/multi-periodo` | Analisis multi-mes/periodo |
| POST | `/api/v1/estado-cuenta` | Estado de cuenta y proyeccion anual |
| POST | `/api/v1/agente/predeclaracion` | Agente conversacional (tool use) — lee perfil, historial y calcula |

### Esquema de request (pre-declaracion):
```json
{
  "contribuyente": { "rfc": "XAXX010101000", "regimen": "626", "nombre": "...", "tipo_persona": "...", "actividad_economica": "..." },
  "facturas": [{ "uuid": "...", "fecha": "2025-01-10", "tipo": "I", "rfc_emisor": "...", "rfc_receptor": "...", "subtotal": 15000, "total": 17400, "iva_trasladado": 2400, "isr_retenido": 1500 }],
  "periodo_year": 2025,
  "periodo_month": 1,
  "incluir_explicacion": true
}
```

### Respuesta (DesgloseFiscal):
```json
{
  "total_ingresos_facturados", "total_ingresos_gravados", "cantidad_facturas_ingreso",
  "total_egresos", "total_deducciones_autorizadas", "base_isr", "tasa_isr",
  "isr_causado", "isr_retenido", "isr_a_pagar",
  "iva_trasladado_cobrado", "iva_trasladado_pagado", "iva_retenido", "iva_a_pagar",
  "total_a_pagar"
}
```

El Fiscal Agent es **stateless**: no guarda datos del usuario. Todo viene en el request.

## REGLAS DE CODIGO

### SIEMPRE:
- Usar TypeScript estricto (no `any` sin justificacion)
- Usar CSS variables de global.css para TODOS los colores
- Componentes funcionales con hooks
- Manejar estados de loading y error en toda llamada async
- Comentar componentes con su proposito
- Archivos en PascalCase para componentes, camelCase para servicios/utils

### NUNCA:
- Usar Tailwind, Bootstrap, Material UI ni ningun framework CSS
- Usar colores hardcodeados fuera de la paleta
- Dejar console.log en produccion
- Usar `any` como tipo sin razon
- Hacer fetch sin try/catch
- Crear archivos de mas de 300 lineas (extraer a componentes)

## SERVICIOS DEL MARKETPLACE

Definidos en `src/services/storeServices.ts`. Cada servicio tiene:
- `id`, `name`, `tagline`, `description`, `icon` (emoji)
- `status`: 'active' | 'coming_soon' | 'beta'
- `features`: lista de funcionalidades
- `category`: 'fiscal' | 'laboral' | 'contable'
- `apiEndpoint?`: URL del backend del servicio
- `externalUrl?`: URL externa del servicio
- `appliesTo`: lista de tipos de contribuyente

### Servicios actuales:
1. **Fiscalito** (activo) — Asistente fiscal con Fiscal Agent API. Aplica a todos los tipos.
2. **IMSS Manager** (proximamente) — Gestion de empleados ante el IMSS. Solo PYMEs.
3. **Contabilito** (proximamente) — Contabilidad electronica automatizada. Solo PYMEs.

## FIREBASE

Proyecto: `fiscalito-mvp`
Auth: Email/password + Google habilitados
DB: Firestore

### Variables de entorno (`.env`):
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, etc. — Config Firebase
- `VITE_FISCAL_AGENT_URL` — URL del Fiscal Agent API (default: `http://localhost:8000`)
- `VITE_OPENAI_API_KEY` — API key de OpenAI para voice chat (Whisper + GPT-4o-mini + TTS). **NOTA**: esta key se expone en el bundle del cliente; aceptable para demo/hackathon, no para produccion.

### Estructura Firestore:

**Perfil de usuario** — `users/{uid}`:
```
contributorType: 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme' | null
rfc: string
regimen: string (codigo SAT: '626', '612', '605', '606', '625')
nombre: string
actividad: string
cp: string
telefono: string
nombreNegocio: string (solo PYME)
numEmpleados: string (solo PYME)
onboardingComplete: boolean
updatedAt: serverTimestamp
```

**Historial de declaraciones** — `users/{uid}/declaraciones/{docId}`:
```
categoria: 'predeclaracion' | 'diot' | 'retenciones' | 'multiperiodo' | 'estado_cuenta' | 'deducciones'
tipo: string (monthly, bimonthly, annual)
periodo: string (ej: "Enero 2025", "Bimestre 1 2025")
regimen: string
fecha_calculo: serverTimestamp
facturas_count: number
desglose: object (para pre-declaraciones)
explicacion: string | null (explicacion IA)
advertencias: string[]
recomendaciones: string[]
proveedores: array (para DIOT)
terceros: array (para retenciones)
resultados: array (para multiperiodo)
acumulado: object (stats multiperiodo)
estado_cuenta: object (para estado de cuenta)
```

## ESTADO ACTUAL

**Completado:**
- ✅ Proyecto React + Vite + TypeScript configurado
- ✅ Firebase Auth funcionando (email + Google)
- ✅ Paleta de colores implementada con variables CSS
- ✅ Landing page publica
- ✅ Login/Register
- ✅ Wizard de onboarding post-registro (4 pasos)
- ✅ ProfileContext con sync a Firestore
- ✅ Dashboard con stats, servicios activos y declaraciones recientes
- ✅ Marketplace con cards y filtros por categoria
- ✅ Detalle de servicio con docs API y ejemplo request/response
- ✅ FiscalitoServicePage con tabs (pre-declaracion, calendario, comparar, DIOT, retenciones, multi-periodo, estado cuenta, deducciones)
- ✅ Upload y parsing de XML CFDI (v3/v4)
- ✅ Conexion real con todos los endpoints del Fiscal Agent API
- ✅ Vista de resultado de pre-declaracion con desglose + explicacion IA
- ✅ Historial de declaraciones en Firestore (todas las categorias)
- ✅ Pagina de historial con filtros y vista expandible
- ✅ Export a PDF (pre-declaracion, DIOT, retenciones, multi-periodo, estado cuenta)
- ✅ Perfil del contribuyente con tipo, RFC, regimen, datos personales
- ✅ Filtro de regimenes por tipo de contribuyente
- ✅ Tabs adaptados al perfil (asalariados solo ven deducciones, no DIOT)
- ✅ Panel admin
- ✅ Sidebar con navegacion
- ✅ Rutas protegidas
- ✅ Repo en GitHub
- ✅ Dashboard adaptado al perfil (filtra servicios y stats por contributorType)
- ✅ Chat de voz con IA (Whisper STT → GPT-4o-mini → TTS-1) — boton flotante en toda la app via AppLayout

**Pendiente:**
- ⏳ Deploy inicial a producción. Firebase Hosting configurado (`firebase.json` con `public: dist`, SPA rewrites y headers de caché inmutable); falta correr `firebase deploy`.

## COMANDOS

```bash
npm install          # Instalar dependencias
npm run dev          # Dev server en localhost:3000
npm run build        # Build para produccion (tsc + vite build)
npm run preview      # Preview del build de produccion
```
