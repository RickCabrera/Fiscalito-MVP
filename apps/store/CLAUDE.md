# ORCA ORDORICA — NÓMINA · Contexto para Claude Code

> **Pivote (corrida O, 2026-09-03).** El producto dejó de ser un marketplace
> multi-cliente y es la **nómina interna de Orca Ordorica Cristal Templado**. El
> modo despacho no se borra: se apaga con `VITE_MODO_EMPRESA_UNICA=0` y sigue
> entero y probado. La marca visible vive en `src/services/marca.ts` — un solo
> archivo, para que el próximo rebrand sea un cambio y no cuarenta cadenas. Los
> **nombres internos no se tocan**: rutas (`/app/store/fiscalito/use`), ids de
> servicio, tipos (`TabFiscalito`), nombres de archivo y llaves de
> `localStorage` (`fiscalito_*`) siguen igual, porque renombrarlos rompe enlaces
> y sesiones a cambio de nada. Lo vigila `src/services/marca.test.ts`.

## INFORMACION CRITICA

**Autor principal**: Ricardo Cabrera
**Tipo**: Proyecto para hackaton Genius Arena 2026 (Track: Capital One — Finanzas para un Futuro Sostenible)
**Deadline**: Dias, no semanas
**Restriccion de costo**: Servicios gratuitos o free tier. LLM (OpenAI/Anthropic) es el unico gasto.

## PROPOSITO

**Antes del pivote** (y lo que sigue vivo tras el flag): un **marketplace web de servicios inteligentes para PYMEs y personas fisicas mexicanas**. Cada servicio del marketplace resuelve una obligacion legal o financiera (fiscal, laboral, contable).

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

/* Amber — acento del tema vanilla (definido en los 3 temas, protagonista solo en vanilla) */
--amber: #b86b2a
--amber-soft: #c89060
--amber-ink: #7c4520

/* Tambien definidos: --border, --radius, --shadow, --accent-active, --accent-active-rail (ver global.css) */
```

Gradiente principal: `linear-gradient(135deg, #492153, #355654)`
Tipografia: **Outfit** (UI) + **JetBrains Mono** (codigo/datos)

La app soporta **tres temas**: dark (default), light y vanilla. Los tres comparten la misma paleta de purple/teal en acentos.

**Temas:**
- **dark** — fondos casi negros, acentos teal/purple. Modo por defecto.
- **light** — fondos blancos fríos con tinte morado sutil.
- **vanilla** — fondos cream cálidos tipo papel manila, trim ámbar puntual en sidebar y símbolos `$`.

Reglas:
- SIEMPRE usar variables CSS de global.css. NUNCA hex o rgba hardcodeados en componentes.
- El gradiente principal (--accent-gradient) y los ramps de purple/teal son IDÉNTICOS en los tres temas.
- Cualquier variable nueva debe definirse en los tres bloques: `:root`, `[data-theme="light"]` y `[data-theme="vanilla"]`.
- Al agregar componentes, probar visualmente en los tres temas antes de hacer merge.

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
│   ├── main.tsx                # Entry point: createRoot + providers + BrowserRouter
│   ├── AppRoutes.tsx           # Arbol de <Routes>. Separado de main.tsx para que sea montable en jsdom
│   ├── vite-env.d.ts
│   ├── styles/
│   │   └── global.css          # Variables CSS, utility classes, tema global
│   ├── context/
│   │   ├── AuthContext.tsx      # Firebase Auth provider + hooks (signIn, signUp, signInWithGoogle, signOut)
│   │   ├── ProfileContext.tsx   # Perfil de contribuyente + sync con Firestore
│   │   ├── ClienteActivoContext.tsx # Provider del cliente activo del despacho (E-02)
│   │   └── clienteActivoStore.ts    # Contexto + hook useClienteActivo (separado por fast refresh)
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
│   │   ├── ClientesPage.tsx         # Cartera del despacho (E-02)
│   │   ├── ClienteDetallePage.tsx   # Ficha del cliente con su plantilla (E-02)
│   │   ├── NominaClientePage.tsx    # Nomina del cliente: checador, cierre, calculo, PDF (E-03)
│   │   ├── NominaDelClienteActivo.tsx # /app/nomina -> nomina del cliente activo (E-03)
│   │   ├── CalendarioPatronalPage.tsx # Obligaciones patronales de la cartera (E-07)
│   │   ├── ProfilePage.tsx          # Datos del contribuyente (RFC, regimen, tipo)
│   │   ├── PlanesPage.tsx           # Planes y limite de clientes, sin cobro (T8)
│   │   └── AdminPage.tsx            # Panel de admin (gestion servicios/usuarios)
│   ├── services/
│   │   ├── firebase.ts              # Config Firebase (initializeApp, auth, db)
│   │   ├── storeServices.ts         # Catalogo de servicios del marketplace
│   │   ├── contributorProfiles.ts   # Definiciones de perfiles de contribuyente (incl. contador)
│   │   ├── navigation.ts            # Sidebar, tabs por perfil y alcance de cliente (modulo puro)
│   │   ├── planes.ts                # Planes, limites y uso de clientes — sin billing (T8)
│   │   ├── despachoApi.ts           # Cliente REST de la cartera y del calendario patronal (E-02, E-07)
│   │   ├── calendarioPatronal.ts    # Logica pura del calendario patronal: agrupacion y estados (E-07)
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
/app/clientes                  → ClientesPage (protegida, cartera del despacho — solo contador)
/app/clientes/:id              → ClienteDetallePage (protegida, ficha con la plantilla del cliente)
/app/clientes/:id/nomina       → NominaClientePage (protegida, checador + cierre + calculo + PDF)
/app/nomina                    → NominaDelClienteActivo (redirige a la nomina del cliente activo)
/app/calendario                → CalendarioPatronalPage (obligaciones patronales de la cartera — solo contador)
/app/nomina-demo               → redireccion a /app/clientes/demo/nomina (ruta vieja de D-07)
/app/store                     → MarketplacePage (protegida)
/app/store/fiscalito/use       → FiscalitoServicePage (protegida, interfaz principal del servicio)
/app/store/:serviceId          → ServiceDetailPage (protegida)
/app/profile                   → ProfilePage (protegida)
/app/planes                    → PlanesPage (protegida, planes y limite de clientes — T8; se entra desde Perfil, no del sidebar)
/app/admin                     → AdminPage (protegida)
```

## PERFILES DE CONTRIBUYENTE

Definidos en `src/services/contributorProfiles.ts`. El campo `contributorType` determina que servicios y tabs ve el usuario:

| Tipo | Regimenes | Servicios visibles | Tabs Fiscalito |
|------|-----------|-------------------|----------------|
| **contador** (Despacho / Contador) | — (E-05 no le pide regimen) | ninguno | **Ninguno** (ver E-07) |
| asalariado | 605 | Fiscalito | Deducciones personales, Calendario |
| independiente (RESICO) | 626 | Fiscalito | Declaracion, Calendario, Comparar, Estado cuenta |
| independiente (Empresarial) | 612 | Fiscalito | Declaracion, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |
| arrendamiento | 606 | Fiscalito | Declaracion, Calendario, Comparar, Multi-periodo, Estado cuenta |
| plataformas | 625 | Fiscalito | Declaracion, Calendario, Estado cuenta |
| pyme | 612, 626, 621 (RIF) | Fiscalito + IMSS Manager + Contabilito | Declaracion, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |

**Nota**: La logica de filtrado de tabs esta en `services/navigation.ts:getTabsForProfile()`
— **una sola copia**, usada por `FiscalitoServicePage` y por `DashboardPage`. Los tabs se
filtran por `contributorType` y luego por `regimen`. **La rama de `contador` va PRIMERO**: un
despacho tiene regimen 612 o 626 y si se evaluara despues caeria en la rama de contribuyente.

### Navegacion por perfil (E-01)

El sidebar NO se arma en `AppLayout`: sale de `services/navigation.ts` (`getSidebarLinks`),
modulo puro sin JSX. `AppLayout` solo le pone iconos por `id`.

| Perfil | Sidebar |
|--------|---------|
| contador | Clientes · Nomina · Calendario (**patronal**, E-07) · Perfil |
| cualquier otro (incluido perfil sin tipo) | Dashboard · Fiscalito · Historial · Nomina (demo) · Perfil |

Los tabs y pantallas de contribuyente **no se borraron**: dejan de mostrarse. Un contador que
teclee `/app` es redirigido a `/app/clientes` (`rutaInicial`).

**Fuera de alcance de E-01, conocido:** `/app/historial`, `/app/store`, `/app/store/:serviceId`
y `/app/admin` siguen alcanzables por URL para un contador.

### Cliente activo del despacho (E-02)

`ClienteActivoProvider` carga `GET /despacho/clientes` **solo si el perfil es contador** y
mantiene el cliente en foco, persistido en `localStorage`. Un id guardado que ya no exista en la
cartera **cae al primero** y se corrige lo guardado: si no, la ficha pediría un cliente fantasma
y el backend respondería 404.

El **selector de cliente** vive en una barra sobre el `<Outlet />` de `AppLayout` y se muestra
solo en las rutas con alcance de cliente (`rutaTieneAlcanceDeCliente` en `navigation.ts`): todo
lo que cuelga de `/app/clientes`, incluida la nomina. **NO** en Calendario ni Perfil. Perfil es
del DESPACHO; y Calendario, desde E-07, si es patronal pero es el de **toda la cartera**, asi que
un selector de "cliente activo" encima afirmaria un alcance que esa pantalla no tiene.

**REGLA PARA AGREGAR UNA RUTA A ESA LISTA:** no basta con que la pantalla HABLE de clientes;
tiene que LEER el cliente activo y pedirle los datos a ese cliente. Si no, el selector afirma un
cliente y la pantalla ensena otro.

### El despacho y el calendario (E-07)

`Calendario` del sidebar apunta a `/app/calendario` (`CalendarioPatronalPage`), que consume
`GET /api/v1/despacho/calendario`: las obligaciones **patronales** de toda la cartera —entero
mensual IMSS, bimestral RCV/Infonavit, avisos de variables, prima de RT, PTU, aguinaldo y entero
del ISR retenido—, agrupadas por fecha limite.

**Un despacho NO tiene tabs de Fiscalito**: `getTabsForProfile('contador')` devuelve `[]` y
`FiscalitoServicePage` redirige a `/app/calendario`. E-05 dejo de pedirle RFC y regimen y quito
del perfil el unico lugar donde capturarlos, asi que el tab de calendario de contribuyente
quedaba muerto. Consecuencia declarada en §D21: **la app ya no calcula las obligaciones fiscales
propias del despacho**, y la pantalla se lo dice al contador.

**`regimen_de_plazo` no se pinta igual para todos.** Cinco valores (`imss`, `imss_sin_prorroga`,
`imss_aviso`, `sat`, `lft`) porque el viernes es inhabil para el IMSS y habil para el SAT: las
cuotas de marzo de 2026 vencen el 20-abr y su ISR el 17-abr. Fundirlos en la vista es lo que
`knowledge_base/nomina/25_calendario_laboral_2026.md` §4 llama "un bug esperando".

**`condicional` no significa opcional**: significa *verificalo, porque aqui no consta*. Ver §D24.

### La ruta es la fuente de verdad del cliente (E-03)

`NominaClientePage` toma el cliente de `useParams` y **sincroniza el contexto a la ruta**, nunca
al reves. Al reves, entrar por `/app/clientes/demo/nomina` con `taller` guardado en
`localStorage` dejaria el header diciendo Taller y la pantalla calculando demo.

La pantalla manda **siempre** `empleados` en `POST /nomina/calcular-periodo`, tomados de la
ficha: omitirlos solo es valido para el cliente `demo`. Por eso `origen_plantilla` vale
`"request"` para todos y **la banda "DATOS DE DEMOSTRACION" del PDF cuelga del cliente**, no de
ese campo.

### Frontera de tipos front → API

El front tiene un tipo que el backend no conoce: `contador`.
`PerfilContribuyente.contributor_type` (en `fiscalAgentApi.ts`) espeja a mano el enum de
`app/schemas/fiscal.py:49` y **no se ensancha a `string`** — si se ensanchara, agregar un tipo
nuevo dejaria de romper el build y pasaria a romperse en vivo con un 422. Todo paso de
`ContributorType` a un request va por una de estas dos:

- `tipoParaApi(tipo)` — para los endpoints de calculo. `contador` → `null` (un despacho no es
  el sujeto del calculo, sus clientes lo son).
- `tipoParaCalendario(tipo)` — para `POST /calendario`, que exige un tipo concreto y responde
  400 si no lo reconoce. **Su entrada `contador` quedo inalcanzable por construccion en E-07**:
  un despacho ya no llega a esa pantalla. Se conserva solo como guarda de exhaustividad del
  `Record`. Ver `docs/decisiones-nomina.md` D21.

Los dos mapas son `Record<ContributorType, ...>` exhaustivos a proposito: un tipo nuevo rompe
el build y obliga a decidir que se le manda al backend.

### Wizard de onboarding (post-registro)

Los pasos **dependen del tipo** (E-05). Un contribuyente recorre cuatro:
1. **Tipo de cuenta** — card selector visual con iconos (incluye Despacho / Contador)
2. **Datos fiscales** — RFC + regimen (filtrado por tipo) + campos PYME (nombre negocio, num empleados)
3. **Datos personales** — nombre completo, telefono, actividad economica, codigo postal
4. **Confirmacion** — resumen con boton "Comenzar"

Un **despacho** recorre tres, y se le piden SOLO tres campos: **Tipo → Datos del despacho
(nombre del contador, nombre del despacho, telefono) → Confirmacion**. Nada de RFC, regimen,
actividad ni codigo postal: no declara por si mismo en esta app, el sujeto del calculo es su
cliente (§D21).

**TODO se decide contra la lista de ids de paso, nunca contra el indice** —el render, `canNext`,
"Atras" y cual es el ultimo paso—. Con `step < 3` cableado, un wizard de tres pasos dejaba al
contador en "Confirmar" viendo "Siguiente" y `handleFinish` no corria nunca: no se creaba la
cuenta y nada fallaba visiblemente.

En `ProfilePage`, un despacho **no ve el selector de los otros cinco tipos** ni los campos
fiscales. La condicion cuelga de `profile.contributorType` (el GUARDADO), no del estado local:
si colgara del local, un contribuyente que clickeara "Despacho / Contador" por curiosidad veria
desaparecer el selector en ese mismo render y quedaria encerrado sin haber guardado nada.
`handleSave` sigue mandando los campos que ya no se pintan, para no repetir la perdida
silenciosa que cazo la mutacion de E-01.

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
- `features`: lista de funcionalidades **que ya operan**
- `features_proximamente?`: lo que todavia NO hace (T8). Se pinta atenuado en el detalle del
  servicio. Un `beta` con una sola lista a palomita afirma que todo funciona.
- `category`: 'fiscal' | 'laboral' | 'contable'
- `apiEndpoint?`: URL del backend del servicio
- `externalUrl?`: URL externa del servicio
- `appliesTo`: lista de tipos de contribuyente

### Servicios actuales:
1. **Fiscalito** (activo) — Asistente fiscal con Fiscal Agent API. Aplica a todos los tipos.
2. **IMSS Manager** (**beta**, T8) — SDI, cuotas por ramo, altas y archivo de movimientos
   afiliatorios. PYMEs y contador. Bajas y modificaciones de salario NO: falta el dato, no el
   layout (ver `exportadores/registro.ts`).
3. **Contabilito** (proximamente) — Contabilidad electronica automatizada. Solo PYMEs.

**`beta` cuenta como usable.** `servicioDisponible()` y `etiquetaDeEstado()` viven en
`storeServices.ts` y las consultan **las CUATRO pantallas que pintan `status`**: Landing (publica),
Marketplace, detalle del servicio y Admin. Hasta T8 las cuatro preguntaban `status === 'active'`
por su cuenta, asi que el estado `beta` existia en el tipo y **no significaba nada**: un servicio
en beta se veia igual que uno que no existe. **Si agregas una quinta, pregunta aqui** — el primer
intento de T8 arreglo dos y dejo la Landing diciendo "Proximamente" de un servicio que el
marketplace ya llamaba "Beta".

**IMSS Manager no tiene pantalla propia.** Lo que hace vive en Empleados (altas y plantilla) y
en Nomina (SDI, cuotas por ramo, exportador IMSS), y los botones del detalle llevan ahi. Crear
una pantalla `/app/store/imss-manager/use` anunciaria un modulo que no existe.

### Planes de la cuenta (T8)

`services/planes.ts` define tres —contador (1 usuario / 25 clientes), despacho (10 / 200) y
empresa (1 / 1)—, con `precio: 'Consultar'` en los tres. **No hay billing**: ni pasarela, ni
suscripcion, ni fecha de corte. El plan elegido se guarda en `users/{uid}.plan` via
`ProfileContext` y se elige en `/app/planes`.

- **`maxClientes` SI se hace cumplir**: bloquea "Nuevo cliente" en `ClientesPage` con el motivo
  escrito (no solo en un `title`: un boton deshabilitado no recibe hover en tactil).
- **`maxUsuarios` NO**: la app no tiene cuentas de equipo, un `users/{uid}` es una persona. El
  numero describe el plan, no algo que el codigo vigile.
- **El campo es opcional**: `undefined` = nunca eligio, y `planDelPerfil()` resuelve el default
  (`empresa` en modo empresa unica, `contador` si no) **sin escribirlo**. Guardar un default en
  silencio convierte una suposicion del codigo en un dato del usuario.
- Elegir un plan mas chico que la cartera **no borra clientes**: solo impide dar de alta otro.
- El uso ("3 / 25 clientes") se pinta en Perfil (`components/perfil/TarjetaPlan.tsx`), en
  `SelectorCliente` —que lo recibe **como prop desde `AppLayout`**, no del contexto— y junto al
  boton de alta en `ClientesPage`.

### Constancias de retencion y DIOT .txt (T5)

Dos entregables por RFC que salen de lo que el backend ya calcula. **Ninguno toca el API.**

- **`pdfExportRetenciones.ts` → `exportConstanciaRetencion(tercero, retenedor, periodo)`**: un
  PDF por tercero, `constancia-{RFC}-{Periodo}.pdf`, con boton "Constancia" por fila en
  `RetencionesTab` y "Descargar todas" (N archivos, no un PDF de N paginas: una constancia se le
  entrega a UN proveedor). **No es un CFDI de Retenciones timbrado por un PAC** y el PDF lo dice
  en una banda, arriba, antes de los importes — el timbrado esta fuera de alcance por
  `CLAUDE.md` raiz.
- **`services/exportadores/diot.ts` → `generarDIOTBatch(respuesta)`**: el `.txt` de carga batch,
  delimitado por `|`, **una linea por proveedor y sin encabezados**. El archivo lleva
  `PORVALIDAR` en el nombre y `DIOT_BATCH_POR_VALIDAR` se pinta **encima** del boton: el orden de
  los campos (`CAMPOS`) NO esta contrastado contra el instructivo vigente del SAT.
- **El corte por tasa se DEDUCE.** `POST /api/v1/diot` devuelve subtotal e IVA por proveedor y
  nada mas (`app/fiscal_engine/diot.py`), asi que `derivarPorTasa` saca la base del 16% de
  `iva_pagado / 0.16` y manda el resto **entero a tasa 0%** — el desglose no permite separar
  "tasa 0%" de "exentos". Tipo de tercero `04` y tipo de operacion `85` van fijos. Las tres son
  DECISION PROVISIONAL (nocturno) y estan marcadas en el codigo.
- **`exportadores/descargar.ts`** (`descargarBytes`) salio de `SelectorExportacion.tsx` para que
  la DIOT no duplicara el `Blob` + `createObjectURL`. Nada se loguea ni se guarda.

## FIREBASE

Proyecto: `fiscalito-mvp`
Auth: Email/password + Google habilitados
DB: Firestore

### Variables de entorno (`.env`):
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, etc. — Config Firebase
- `VITE_FISCAL_AGENT_URL` — URL del Fiscal Agent API (default: `http://localhost:8000`)
- `VITE_OPENAI_API_KEY` — API key de OpenAI para voice chat (Whisper + GPT-4o-mini + TTS). **NOTA**: esta key se expone en el bundle del cliente; aceptable para demo/hackathon, no para produccion.

#### Flags (los dos vienen APAGADOS; ver `.env.example`)

Los dos se leen con la misma regla (`services/flagEncendido.ts`): encienden `1`,
`true`, `on`, `yes`, `si` y `sí`; **cualquier otra cosa, y la variable ausente,
dejan el flag apagado**. Un valor que no se entiende no enciende nada y tampoco
avisa, así que escribe uno de esos seis.

- `VITE_CARTERA_BACKEND` (R-07, T2) — **quién es el dueño de la cartera**
  (clientes y empleados), y se decide una vez al cargar la app, en
  `services/cartera.ts`. Apagado (**default**): todo el CRUD va por
  `services/carteraFirestore.ts`, o sea Firestore desde el navegador.
  Encendido: va por `services/carteraBackend.ts` contra `/api/v1/cartera/*`.
  **El backend existe y está probado, pero exige credenciales de GCP**
  (`GOOGLE_APPLICATION_CREDENTIALS` o ADC) en `apps/api`; sin ellas responde
  **503 a todo el CRUD**, que no se ve como un problema de configuración sino
  como una app que dejó de guardar clientes. Enciéndelo sólo después de
  comprobar que `GET /api/v1/cartera/clientes` responde 200. **No hay migración
  de datos**: las rutas de Firestore (`users/{uid}/clientes/{id}/empleados/{id}`)
  son las mismas de los dos lados, así que apagarlo tampoco mueve nada. El
  contrato vive en `docs/api-contract.md`, y R-07 sigue ABIERTA en `backlog.md`.
- `VITE_MODO_EMPRESA_UNICA` (O-01, default invertido en T1) — apagado
  (**default**) es la app del DESPACHO: cartera, selector de cliente activo y el
  Fiscalito de cada cliente. Encendido es la nómina de UNA empresa implícita,
  sin cartera ni lista de clientes. Ninguno de los dos modos se borra; se
  apagan. Ojo con tu `.env` local: gana sobre el default.

### Estructura Firestore:

**Perfil de usuario** — `users/{uid}`:
```
contributorType: 'contador' | 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme' | null
rfc: string
regimen: string (codigo SAT: '626', '612', '605', '606', '625')
nombre: string
actividad: string
cp: string
telefono: string
nombreNegocio: string (solo PYME)
numEmpleados: string (solo PYME)
nombreDespacho: string (solo contador)
plan?: 'contador' | 'despacho' | 'empresa'   (T8; ausente = nunca eligio, ver services/planes.ts)
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
npm test             # Suite de vitest (red bloqueada por default)
```
