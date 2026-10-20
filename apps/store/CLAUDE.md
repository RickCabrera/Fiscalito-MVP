# FISCALITO · Contexto para Claude Code

> **Solo despachos (K, 2026-10-19).** El sistema es SOLO para despachos y
> contadores que llevan varias empresas. Ya no hay perfiles de contribuyente en
> el onboarding, ni Dashboard/Historial propios, ni modo empresa única (Orca y el
> flag `VITE_MODO_EMPRESA_UNICA` se retiraron). Toda cuenta es `contador` y todo
> opera sobre el **cliente activo**. Una cuenta vieja de contribuyente cae al
> wizard (`cuentaLista` en `services/navigation.ts`) y sale convertida en
> despacho. Lo que diga abajo sobre contribuyentes, empresa única o Orca es
> historia: manda este recuadro. `ContributorType` conserva los seis valores
> porque son la llave guardada en Firestore de cuentas existentes.

> **Pivote (corrida O, 2026-09-03).** El producto dejó de ser un marketplace
> multi-cliente y pasó a ser la **nómina interna de Orca Ordorica Cristal
> Templado**. El modo despacho no se borra: se apaga con
> `VITE_MODO_EMPRESA_UNICA=0` y sigue entero y probado.
>
> **Rebrand a Fiscalito (2026-09-15).** La marca visible vuelve a ser
> **Fiscalito**: la suite fiscal, de nómina y de contabilidad que se le vende a
> un despacho. "Orca Ordorica Cristal Templado" sigue existiendo en la app, pero
> como **cliente** —un registro de Firestore y el `placeholder` de razón social
> en `ConfiguracionEmpresa`—, no como producto. Cambiar el nombre costó editar
> `src/services/marca.ts` y nada más, que era justo para lo que se creó ese
> archivo. La marca visible vive ahí — un solo archivo, para que el próximo
> rebrand sea un cambio y no cuarenta cadenas. Los
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
- **LLM (frontend)**: NINGUNO desde P5-07. La voz y el chat del asistente pasan por el backend (`/api/v1/asistente/*`, `services/asistenteApi.ts`); el front no tiene llaves de IA (lo vigila `src/sinLlavesLLM.test.ts`)
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
│   │   ├── contabilidad/        # Tabs de Contabilito (P2): CatalogoCuentas, ConfigPolizas,
│   │   │                        # ReglasEgreso, PolizasCliente, DetallePoliza, FormPoliza,
│   │   │                        # BalanzaCliente, AuxiliarCuenta, SaldosIniciales, BuzonTab,
│   │   │                        # ReportesContables, FiltrosReportes, TablaEstadoFinanciero (P2-05),
│   │   │                        # PeriodosContables, ValidacionPeriodo, CierreAnual (P2-08)
│   │   └── fiscalito/           # Tabs del servicio Fiscalito
│   │       ├── PreDeclaracionTab.tsx      # Upload XML + calculo pre-declaracion
│   │       ├── DeclaracionAnualTab.tsx    # T3: ejercicio completo + deducciones personales
│   │       ├── ResultadoAnual.tsx         # T3: resultado anual (desglose + deducciones + PDF)
│   │       ├── CapturaDeducciones.tsx     # Rejilla de deducciones personales, compartida
│   │       ├── XMLUploader.tsx            # Drag & drop de archivos XML CFDI
│   │       ├── ErroresDeCarga.tsx         # Archivos no cargados (no-XML o ilegibles), con su nombre (C-03)
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
│   │       ├── PagosProvisionalesPMTab.tsx # P3-01: pagos provisionales PM (motor del backend)
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
│   │   ├── ContabilitoPage.tsx      # Contabilito: catalogo, polizas, balanza y buzon (T7)
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
│   │   ├── archivosXml.ts           # Filtro de uploaders: `.xml` sin mayúsculas + rechazados con nombre (C-03). Todo uploader de CFDI pasa por `separarXml` y `ACCEPT_XML`; no filtres con `endsWith('.xml')`
│   │   ├── declaracionesHistory.ts  # CRUD Firestore para historial de declaraciones
│   │   ├── pdfExport.ts             # PDF de pre-declaracion
│   │   ├── pdfExportDIOT.ts         # PDF de DIOT
│   │   ├── pdfExportRetenciones.ts  # PDF de retenciones
│   │   ├── pdfExportMulti.ts        # PDF multi-periodo
│   │   ├── pdfExportEstado.ts       # PDF estado de cuenta
│   │   ├── contabilidadApi.ts       # Contabilito (P2): catalogo, config, polizas, balanza (API)
│   │   ├── deduccionesPersonales.ts # Campos y clasificacion por ClaveProdServ (compartido)
│   │   ├── pdfUtils.ts              # Helpers compartidos para exports PDF (colores, tablas)
│   │   ├── asistenteApi.ts          # P5-07: turno del asistente, voz a texto y texto a voz (backend)
│   │   └── voiceChatService.ts      # Grabacion, VAD y reproduccion; STT/TTS via asistenteApi (sin llaves)
│   └── utils/
│       ├── format.ts                # fmtMoney y helpers de formateo
│       └── styles.ts                # Objetos de estilo inline compartidos (tablas, badges)
```

## RUTAS

```
/                              → LandingPage (publica)
/login                         → LoginPage (publica)
/app/onboarding                → OnboardingWizard (protegida, sin sidebar)
/app                           → redirige a /app/inicio (P5-02)
/app/inicio                    → InicioPage: dashboard DEL DESPACHO, pantalla de entrada (P5-02; primera del sidebar)
/app/equipo                    → EquipoPage: usuarios, invitaciones, roles y asignaciones (P5-01; desde Perfil)
/app/cobranza                  → CobranzaPage: cuentas por cobrar del despacho (P5-03; sidebar)
/aceptar-invitacion?token=     → AceptarInvitacionPage (publica; pide sesion y une al despacho, P5-01)
/app/historial                 → redirige a /app/clientes (K)
/app/clientes                  → ClientesPage (protegida, cartera del despacho — solo contador)
/app/clientes/:id              → ClienteDetallePage (protegida, ficha con la plantilla del cliente)
/app/clientes/:id/nomina       → NominaClientePage (protegida, checador + cierre + calculo + PDF)
/app/nomina                    → NominaDelClienteActivo (redirige a la nomina del cliente activo)
/app/calendario                → CalendarioPatronalPage (obligaciones patronales de la cartera — solo contador)
/app/nomina-demo               → redireccion a /app/nomina (ruta vieja de D-07)
/app/store                     → MarketplacePage (protegida)
/app/store/fiscalito/use       → FiscalitoServicePage (protegida, interfaz principal del servicio)
/app/store/contabilito/use     → ContabilitoPage (protegida, Contabilito: catalogo/polizas/balanza/buzon — T7)
/app/store/:serviceId          → ServiceDetailPage (protegida)
/app/profile                   → ProfilePage (protegida)
/app/planes                    → PlanesPage (protegida; P5-08: planes y suscripcion DEL BACKEND — suscribirse, cambiar, cancelar, estado, bloqueos y pagos via `services/suscripcionApi.ts`; se entra desde Perfil, no del sidebar)
/app/admin                     → AdminPage (protegida)
```

## PERFILES DE CONTRIBUYENTE

Definidos en `src/services/contributorProfiles.ts`. El campo `contributorType` determina que servicios y tabs ve el usuario:

| Tipo | Regimenes | Servicios visibles | Tabs Fiscalito |
|------|-----------|-------------------|----------------|
| **contador** (Despacho / Contador) | — (E-05 no le pide regimen) | Fiscalito **del cliente activo** | Los del CLIENTE activo, por su regimen (T1). Sin cliente: ninguno |
| asalariado | 605 | Fiscalito | Deducciones personales, Calendario |
| independiente (RESICO) | 626 | Fiscalito | Declaracion, **Anual**, Calendario, Comparar, Estado cuenta |
| independiente (Empresarial) | 612 | Fiscalito | Declaracion, **Anual**, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |
| arrendamiento | 606 | Fiscalito | Declaracion, **Anual**, Calendario, Comparar, Multi-periodo, Estado cuenta |
| plataformas | 625 | Fiscalito | Declaracion, **Anual**, Calendario, Estado cuenta |
| pyme | 612, 626, 621 (RIF), **601 (PM)** | Fiscalito + IMSS Manager + Contabilito | Declaracion, **Anual**, Calendario, Comparar, DIOT, Retenciones, Multi-periodo, Estado cuenta |
| **cualquiera con regimen 601** (T6) | 601 | Fiscalito | **Pagos provisionales PM**, Calendario, Pre-declaracion (deshabilitada con mensaje) |

**T3**: el tab `anual` (Declaracion anual) lo ven TODOS menos el asalariado, cuya anual ya
**es** el tab `deducciones`. Llama a `POST /api/v1/pre-declaracion-anual` y, si el
contribuyente capturo deducciones personales, ademas a `POST /api/v1/deducciones-personales`
con la **base del ejercicio** que devolvio el primero. Los dos resultados se pintan lado a
lado y **no se restan en pantalla**: el motor no devuelve esa resta y el front no la inventa.
El filtro por año lo hace el front porque el endpoint anual **no filtra**: suma todo lo que le
llega. RESICO (626) no captura deducciones personales ahi — el estimador usa la tarifa general
del Art. 152, no la del 113-E (DECISION PROVISIONAL, pendiente con la contadora).

### Regimen 601 y RESICO PM — Personas Morales (P3-01, P3-06)

Persona moral = regimen `601`, o `626` con RFC de 12 caracteres (RESICO PM;
`getTabsForProfile(regimen, rfc)`). El motor vive en el backend (`/impuestos/clientes/{clave}/pm/*`
y `/anual`, `src/services/anualApi.ts`); la pantalla **no calcula**:

- **`PagosProvisionalesPMTab`** (`pagospm`, tab por defecto): pide los pagos de enero al mes
  (Art. 14 LISR; RESICO PM Art. 211) y pinta el mes a mes (`TablaMeses`). `DatosPMForm` captura
  lo que no sale de la boveda: coeficiente, PTU pagada, perdidas, retenciones bancarias, pagos
  presentados, fuente (contabilidad/boveda).
- **`anual`** (`AnualClienteTab`): calculo anual del backend y boton "Generar archivo" (Excel de
  papeles de trabajo, del mismo calculo). Para una PF va arriba de `DeclaracionAnualTab`.
- **Pre-declaracion**: sigue reemplazada por `AvisoMotorPM` (la de `calculadora.py` es de PF y
  el API rechaza el 601 con 400), que manda a los dos tabs anteriores.
- **Calendario**: la anual de una moral vence el 31 de marzo (corregido en P3-01).

### De quien es el RFC con que se calcula (C-02)

**Una sola costura: `context/perfilFiscal.ts` (`resolverPerfilFiscal`, puro) y su hook
`usePerfilFiscal()`.** Contador → RFC, regimen y nombre del **cliente activo**
(`ClienteResumen.rfc`, que `comoResumen` copia de la cartera); cualquier otro → su perfil,
**literal como antes**. La usan Pre-declaracion, Anual, DIOT, Retenciones, Multi-periodo, Estado de
cuenta, Calendario, el PDF de `ResultadoDeclaracion`, Contabilito y el regimen con que
`FiscalitoServicePage` escoge los tabs (`regimenParaTabs`, con el default 612 y su aviso).
**No construyas otro perfil a mano en un tab.**

- Cliente sin RFC → `FaltaDatoFiscal`: "Captura el RFC de este cliente" con **Editar cliente**
  (`ModalCliente` ahi mismo) o, si la cartera es de solo lectura, link a la ficha.
- Cliente **sin regimen → no calcula** (§D32): los tabs se ven con el 612 supuesto, el calculo no.
- **Cambiar de cliente es empezar de cero**: el contenido de los tabs lleva `key` por cliente y
  `AgentProvider` tira facturas y resultado de la pre-declaracion al cambiar de cliente activo.
- `DeduccionesPersonalesTab` **sigue leyendo el perfil** (solo aplica a 605, que el alta de
  cliente no ofrece). Pendiente declarado en `docs/nocturno-log.md`.

**Nota**: La logica de filtrado de tabs esta en `services/navigation.ts:getTabsForProfile()`
— **una sola copia**, usada por `FiscalitoServicePage` y por `DashboardPage`. Los tabs se
filtran por `contributorType` y luego por `regimen`. **La rama de `contador` va PRIMERO**: un
despacho tiene regimen 612 o 626 y si se evaluara despues caeria en la rama de contribuyente.

### Navegacion por perfil (E-01)

El sidebar NO se arma en `AppLayout`: sale de `services/navigation.ts` (`getSidebarLinks`),
modulo puro sin JSX. `AppLayout` solo le pone iconos por `id`.

| Perfil | Sidebar |
|--------|---------|
| contador (el unico desde K) | Clientes · Empleados · Dispositivos · Nomina · Calendario (**patronal**, E-07) · Fiscalito (del cliente activo, T1) · **Contabilito** (del cliente activo) · Perfil |

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
- `tipoCalendarioDeRegimen(regimen)` — el calendario del **cliente activo** de un contador
  (C-02): el tipo se deduce del regimen del cliente (601 → `pyme`, ...). PROVISIONAL, §D32.

Los dos mapas son `Record<ContributorType, ...>` exhaustivos a proposito: un tipo nuevo rompe
el build y obliga a decidir que se le manda al backend.

### Wizard de onboarding (post-registro)

**Desde K son dos pasos y nada mas: Datos del despacho → Confirmacion.** No hay paso de tipo; la cuenta se guarda como `contador` con los campos de contribuyente vacios. Lo de abajo describe el wizard anterior.

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
3. **Contabilito** (**beta**, T7) — Polizas de partida doble desde los CFDI, balanza de
   comprobacion y catalogo del codigo agrupador SAT. PYMEs y contador. El envio al buzon
   tributario NO: necesita e.firma (ver `features_proximamente`).

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

### Contabilito — contabilidad del cliente activo (P2-01 a P2-04)

> **P1-06:** Contabilito y los tabs de Fiscalito toman por defecto los CFDI del periodo de la
> **bóveda del cliente activo** (`GET /boveda/clientes/{clave}/facturas-calculo`, vía
> `components/fiscalito/useFuenteFacturas.ts` + `FuenteFacturasPanel.tsx`; sin cancelados ni
> nómina). Subir XML sigue como "Usar archivos sueltos", con "Guardar en la bóveda". Lo de
> "sin una sola llamada al API" de abajo es historia: las pólizas se arman en el front, pero
> los comprobantes ya vienen de la API.

`/app/store/contabilito/use`. **100% front y sin una sola llamada al API**, y puede serlo
porque aqui no se calcula ningun impuesto: los importes (subtotal, descuento, IVA trasladado,
retenciones) ya vienen leidos del XML por `cfdiParser.ts` y solo se acomodan en los dos lados
de una partida doble. Nada se guarda: los comprobantes viven en el estado de la pantalla.
`/app/store/contabilito/use`. **El cascaron de T7 se retiro**: ya no se suben XML ni se
arman polizas en el navegador (`services/contabilidad/*` y los tabs viejos se borraron). El
backend es dueño de todo (`/api/v1/contabilidad/clientes/{clave}/...`, ver
`docs/api-contract.md` §Contabilidad) y la pantalla opera sobre el **cliente activo**: sin
cliente, `SinClienteActivo`; al cambiar de cliente se remonta (`key`).

- Tabs: **Catalogo** (`CatalogoCuentas`, arbol editable + sembrar catalogo base), **Configuracion**
  (`ConfigPolizas` + `ReglasEgreso`, como la de Contadigital), **Polizas** (`PolizasCliente`:
  generar del periodo desde la boveda, lista, `DetallePoliza`, `FormPoliza` manual), **Balanza**
  (`BalanzaCliente` → `AuxiliarCuenta` → poliza / XML; `SaldosIniciales`) y **Buzon** (sin
  cambios hasta P2-07).
- Servicio: `services/contabilidadApi.ts` (tipos en `contabilidadTipos.ts`). Los importes viajan
  como texto; el front no decide el cuadre, lo pinta.
- **Reportes** (P2-05, `ReportesContables`): estado de resultados, balance general, balanza,
  auxiliar e impresión de pólizas, con filtros de ejercicio/periodo, cuentas, nivel,
  agrupación, moneda + tipo de cambio, idioma y comparativo. Excel lo genera el backend; PDF
  `services/pdfExportContabilidad.ts` (jspdf) transcribiendo la misma respuesta.
- **Periodos** (P2-08, `PeriodosContables`): estado por mes, cerrar con la validación del
  backend (lista de CFDI sin póliza; forzar con motivo), reabrir con motivo, cierre anual
  (`CierreAnual`) y bitácora.

### CFDI de retenciones, DIOT 2025, alertas y calendario (P3-04/05/09/10)

> Manda sobre la sección T5 de abajo, que queda como historia.

- **Retenciones** (`RetencionesCfdiPanel` en `RetencionesTab`, `services/retencionesCfdiApi.ts`):
  por tercero del mes, "Generar CFDI" → el backend arma el CFDI de Retenciones 2.0, lo sella
  con el CSD del cliente, lo valida contra el XSD y lo timbra con el PAC (`FISCALITO_PAC`).
  Descarga XML/PDF (con QR) y cancela (motivo 02, con confirmación). Con el PAC `falso` la
  pantalla dice que NO es fiscal. La constancia PDF simple sigue en la tabla ("Constancia
  simple") como alternativa.
- **DIOT** (`DiotOficialPanel` en `DIOTTab`, `services/diotApi.ts`): el `.txt` de 54 campos
  (layout 2025 del SAT) y los cortes por tasa los arma y valida el backend
  (`/clientes/{clave}/diot/{anio}/{mes}`). `services/exportadores/diot.ts` (el que salía
  `PORVALIDAR`) se borró. Tipo de tercero y de operación se corrigen por proveedor y se guardan.
- **Alertas** (P3-09): `CampanaAlertas` en la cabecera del sidebar (fuera del `<nav>`, con el
  conteo), página `/app/alertas` (`AlertasPage`, no está en el sidebar) y sección en la ficha
  del cliente (`AlertasCliente`). `services/alertasApi.ts`.
- **Calendario** (P3-10): `/app/calendario` (`CalendarioPatronalPage`, el nombre se conserva)
  ya es el calendario unificado de la cartera — fiscal (prórroga por sexto dígito y día 17
  inhábil, calculados en el backend), patronal y vencimientos de e.firma/CSD— con vistas
  semana/mes/agenda, filtros (cliente, tipo, responsable), marcar presentada y tareas del
  despacho (`components/calendario/*`, `services/agendaApi.ts`). Las funciones puras de E-07
  (`services/calendarioPatronal.ts`) siguen con sus pruebas en `calendarioPatronal.test.ts`.

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
- **No hay variables de LLM** (P5-07): la llave de OpenAI vivia aqui y Vite la incrustaba en el bundle; se retiro. El asistente (chat, voz a texto, texto a voz) va por `/api/v1/asistente/*` con la sesion de Firebase. El prompt y el catalogo de herramientas son del servidor; las herramientas de consulta (boveda, balanza, nomina, vencimientos, alertas, impuestos) corren alla sobre el cliente activo y las cifras salen del motor. `agent/tools.ts` conserva solo los ejecutores de pantalla (navegar, demo, pre-declaracion).

#### La cartera va por la API (P0-01)

Clientes, empleados y dispositivos **no se guardan en Firestore**: van SIEMPRE por
`/api/v1/cartera/*` (`services/cartera.ts`, `services/dispositivos.ts`, con `apiFetch` de
`services/api.ts`, que adjunta el ID token). El backend los guarda en SQL y filtra por
despacho; **ninguna llamada manda uid**. El flag `VITE_CARTERA_BACKEND` y los módulos
`carteraFirestore.ts` / `carteraBackend.ts` / `dispositivosFirestore.ts` se retiraron. Lo
que una cuenta tenía en Firestore se trae con `apps/api/scripts/migrar_firestore.py`. Los
empleados que el backend no puede leer llegan en `ilegibles` con su razón y se pintan en la
ficha (`EmpleadosIlegibles`, R-10). El contrato vive en `docs/api-contract.md`.

Firestore sigue guardando el **perfil** (`users/{uid}`) y el **historial de declaraciones**.

### Estructura Firestore:

**Perfil de usuario** — `users/{uid}`:
```
contributorType: 'contador' | 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme' | null
rfc: string
regimen: string (codigo SAT: '626', '612', '605', '606', '625', '601')
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
cliente_id?: string (C-02: cliente del despacho con que se calculo; ausente = el contribuyente)
```

**C-02, aditivo:** un calculo hecho para un cliente guarda `cliente_id` y su `docId` va
prefijado (`c_<cliente>__<categoria_periodo>`, `services/historialCliente.ts`), asi que dos
clientes no se pisan el mismo periodo. Uno de contribuyente se guarda **igual que siempre**. Las
lecturas (`obtenerHistorial`, `obtenerAcumuladoAnterior`) filtran por ese ambito: un cliente
solo ve lo suyo y el contribuyente nunca ve lo de un cliente.

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
- ✅ Chat de voz con IA — boton flotante en toda la app via AppLayout; desde P5-07 todo pasa por el backend (`/api/v1/asistente/*`), sin llaves en el navegador

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
