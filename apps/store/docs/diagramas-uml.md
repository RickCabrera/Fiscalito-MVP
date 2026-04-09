# Diagramas UML — Fiscalito Store

## 1. Diagrama de Componentes (Arquitectura General)

```mermaid
graph TB
    subgraph Cliente["🖥️ Cliente (Browser)"]
        subgraph ReactApp["React 19 + Vite + TypeScript"]
            Router["React Router v7"]
            
            subgraph Contexts["Context Providers"]
                AuthCtx["AuthContext<br/>(user, signIn, signUp,<br/>signInWithGoogle, signOut)"]
                ProfileCtx["ProfileContext<br/>(profile, setProfile,<br/>isOnboardingComplete)"]
            end

            subgraph Pages["Pages"]
                Landing["LandingPage"]
                Login["LoginPage"]
                Onboarding["OnboardingWizard"]
                Dashboard["DashboardPage"]
                Marketplace["MarketplacePage"]
                ServiceDetail["ServiceDetailPage"]
                Fiscalito["FiscalitoServicePage"]
                Historial["HistorialPage"]
                Profile["ProfilePage"]
                Admin["AdminPage"]
            end

            subgraph Services["Services Layer"]
                FiscalAPI["fiscalAgentApi.ts"]
                HistorialSvc["declaracionesHistory.ts"]
                CFDIParser["cfdiParser.ts"]
                PDFExport["pdfExport*.ts"]
                VoiceChat["voiceChatService.ts"]
                StoreSvc["storeServices.ts"]
                ContribProfiles["contributorProfiles.ts"]
            end
        end
    end

    subgraph Firebase["☁️ Firebase"]
        FireAuth["Firebase Auth<br/>(Email + Google)"]
        Firestore["Firestore<br/>users/{uid}<br/>users/{uid}/declaraciones"]
    end

    subgraph Backend["⚙️ Fiscal Agent API (FastAPI)"]
        HealthEP["/health"]
        PreDecEP["/api/v1/pre-declaracion"]
        AnualEP["/api/v1/pre-declaracion-anual"]
        DeducEP["/api/v1/deducciones-personales"]
        CalEP["/api/v1/calendario"]
        CompEP["/api/v1/comparar-regimenes"]
        DIOTEP["/api/v1/diot"]
        RetEP["/api/v1/retenciones-terceros"]
        MultiEP["/api/v1/multi-periodo"]
        EstadoEP["/api/v1/estado-cuenta"]
    end

    subgraph ExternalAPIs["🌐 APIs Externas"]
        OpenAI["OpenAI API<br/>(Whisper + GPT-4o-mini + TTS)"]
    end

    AuthCtx -->|"Auth state"| FireAuth
    ProfileCtx -->|"CRUD perfil"| Firestore
    HistorialSvc -->|"CRUD declaraciones"| Firestore
    FiscalAPI -->|"REST calls"| Backend
    VoiceChat -->|"Transcribe + Chat + TTS"| OpenAI
    Router --> Pages
    Pages --> Services
    Pages --> Contexts
```

---

## 2. Diagrama de Clases (Modelos de Datos)

```mermaid
classDiagram
    direction TB

    class PerfilContribuyente {
        +String rfc
        +String regimen
        +String nombre
        +String tipo_persona
        +String actividad_economica
        +String periodicidad
        +Boolean tiene_empleados
        +Boolean retenedor_iva
        +String fecha_inicio_actividades
        +String contributor_type
    }

    class CFDI {
        +String uuid
        +String fecha
        +String tipo: I|E|T|P
        +String rfc_emisor
        +String rfc_receptor
        +Number subtotal
        +Number total
        +Number iva_trasladado
        +Number iva_retenido
        +Number isr_retenido
        +Number descuento
        +String uso_cfdi
        +String descripcion
        +String metodo_pago
        +String uuid_relacionado
        +Number monto_pago
        +String clave_prod_serv
    }

    class DesgloseFiscal {
        +Number total_ingresos_facturados
        +Number total_ingresos_gravados
        +Number cantidad_facturas_ingreso
        +Number total_egresos
        +Number total_deducciones_autorizadas
        +Number cantidad_facturas_egreso
        +Number base_isr
        +Number tasa_isr
        +Number isr_causado
        +Number isr_retenido
        +Number isr_a_pagar
        +Number iva_trasladado_cobrado
        +Number iva_trasladado_pagado
        +Number iva_retenido
        +Number iva_a_pagar
        +Number pagos_provisionales_anteriores
        +Number total_a_pagar
    }

    class PreDeclaracionRequest {
        +PerfilContribuyente contribuyente
        +CFDI[] facturas
        +Number periodo_year
        +Number periodo_month
        +Number periodo_bimestre
        +Boolean incluir_explicacion
        +Number pagos_provisionales_anteriores
        +Number predial_pagado
    }

    class PreDeclaracionResponse {
        +Boolean exito
        +String tipo_declaracion
        +String periodo
        +String regimen
        +DesgloseFiscal desglose
        +String explicacion
        +String[] advertencias
        +String[] recomendaciones
    }

    class UserProfile {
        +ContributorType contributorType
        +String rfc
        +String regimen
        +String nombre
        +String actividad
        +String cp
        +String telefono
        +String nombreNegocio
        +String numEmpleados
        +Boolean onboardingComplete
    }

    class ContributorProfile {
        +ContributorType id
        +String label
        +String description
        +String icon
        +String[] allowedRegimens
        +String[] obligations
        +String[] applicableServices
        +String[] extraFields
    }

    class DeclaracionRecord {
        +String id
        +HistorialCategoria categoria
        +String tipo
        +String periodo
        +String regimen
        +Timestamp fecha_calculo
        +DesgloseFiscal desglose
        +String explicacion
        +String[] advertencias
        +String[] recomendaciones
        +Number facturas_count
        +DIOTProveedor[] proveedores
        +RetencionTercero[] terceros
        +PeriodoResultado[] resultados
        +AcumuladoMultiPeriodo acumulado
        +Object estado_cuenta
    }

    class DashboardStats {
        +Number totalDeclaraciones
        +Number declaracionesEsteMes
        +Number ultimoISR
        +Number ultimoIVA
        +Number ultimoTotal
        +Number saldoFavorAcumulado
        +Number promedioMensual
    }

    class StoreService {
        +String id
        +String name
        +String tagline
        +String description
        +String icon
        +String status: active|coming_soon|beta
        +String[] features
        +String category: fiscal|laboral|contable
        +ContributorType[] appliesTo
        +String apiEndpoint
    }

    class DIOTProveedor {
        +String rfc
        +String nombre
        +Number total_operaciones
        +Number iva_pagado
        +Number cantidad_facturas
    }

    class RetencionTercero {
        +String rfc
        +String nombre
        +Number total_pagado
        +Number isr_retenido
        +Number iva_retenido
        +Number cantidad_facturas
    }

    class ObligacionFiscal {
        +String nombre
        +String descripcion
        +String fecha_limite
        +String periodicidad
        +Boolean completada
    }

    class DeduccionDetalle {
        +String concepto
        +Number monto_solicitado
        +Number tope_aplicable
        +Number monto_aceptado
    }

    class PeriodoResultado {
        +String periodo
        +DesgloseFiscal desglose
    }

    class AcumuladoMultiPeriodo {
        +Number total_isr_pagado
        +Number total_iva_pagado
        +Number total_general_pagado
        +Number promedio_mensual
        +String tendencia
    }

    PreDeclaracionRequest --> PerfilContribuyente
    PreDeclaracionRequest --> CFDI
    PreDeclaracionResponse --> DesgloseFiscal
    DeclaracionRecord --> DesgloseFiscal
    DeclaracionRecord --> DIOTProveedor
    DeclaracionRecord --> RetencionTercero
    DeclaracionRecord --> PeriodoResultado
    DeclaracionRecord --> AcumuladoMultiPeriodo
    PeriodoResultado --> DesgloseFiscal
    UserProfile --> ContributorProfile : "maps to"
    StoreService --> ContributorProfile : "appliesTo"
```

---

## 3. Diagrama de Secuencia — Flujo de Pre-Declaracion

```mermaid
sequenceDiagram
    actor U as Usuario
    participant UI as FiscalitoServicePage<br/>(PreDeclaracionTab)
    participant XML as cfdiParser
    participant API as fiscalAgentApi
    participant FA as Fiscal Agent API<br/>(FastAPI)
    participant HS as declaracionesHistory
    participant FS as Firestore
    participant PDF as pdfExport

    U->>UI: Selecciona año y mes
    U->>UI: Arrastra archivos XML (CFDI)
    UI->>XML: parseMultipleCFDI(files)
    XML->>XML: readFileAsText() por cada archivo
    XML->>XML: parseCFDIFromXML() por cada XML
    XML-->>UI: { success: CFDI[], errors: [] }
    UI->>UI: Muestra facturas parseadas (ingresos/egresos)

    U->>UI: Click "Calcular Pre-Declaración"
    UI->>UI: Construye PreDeclaracionRequest<br/>(contribuyente desde ProfileContext)
    UI->>API: calcularPreDeclaracion(request)
    API->>FA: POST /api/v1/pre-declaracion
    FA->>FA: Clasifica CFDIs, calcula ISR/IVA
    FA->>FA: Genera explicación con LLM
    FA-->>API: PreDeclaracionResponse
    API-->>UI: PreDeclaracionResponse

    alt exito == true
        UI->>UI: Muestra ResultadoDeclaracion<br/>(desglose + explicación IA)
        UI->>HS: guardarDeclaracion(uid, data)
        HS->>FS: setDoc(users/{uid}/declaraciones/{id})
        FS-->>HS: OK
        HS-->>UI: docId

        opt Usuario exporta PDF
            U->>UI: Click "Exportar PDF"
            UI->>PDF: exportarDeclaracionPDF(data)
            PDF-->>U: Descarga archivo PDF
        end
    else exito == false
        UI->>UI: Muestra error/advertencias
    end
```

---

## 4. Diagrama de Secuencia — Registro y Onboarding

```mermaid
sequenceDiagram
    actor U as Usuario
    participant LP as LoginPage
    participant AC as AuthContext
    participant FA as Firebase Auth
    participant OW as OnboardingWizard
    participant PC as ProfileContext
    participant FS as Firestore

    U->>LP: Ingresa email + password
    LP->>AC: signUp(email, password)
    AC->>FA: createUserWithEmailAndPassword()
    FA-->>AC: User credential
    AC-->>LP: user !== null

    LP->>LP: Redirige a /app
    Note over LP: ProtectedRoute detecta<br/>onboarding incompleto
    LP->>OW: Redirige a /app/onboarding

    rect rgb(30, 20, 40)
        Note over OW: Paso 1: Tipo de Contribuyente
        U->>OW: Selecciona tipo (ej: independiente)
    end

    rect rgb(30, 20, 40)
        Note over OW: Paso 2: Datos Fiscales
        U->>OW: Ingresa RFC + selecciona régimen
    end

    rect rgb(30, 20, 40)
        Note over OW: Paso 3: Datos Personales
        U->>OW: Nombre, teléfono, actividad, CP
    end

    rect rgb(30, 20, 40)
        Note over OW: Paso 4: Confirmación
        U->>OW: Click "Comenzar"
    end

    OW->>PC: setProfile({ ...allData, onboardingComplete: true })
    PC->>FS: setDoc(users/{uid}, profileData, merge)
    FS-->>PC: OK
    PC-->>OW: Perfil guardado

    OW->>OW: Redirige a /app (Dashboard)
```

---

## 5. Diagrama de Casos de Uso

```mermaid
graph TB
    subgraph Actores
        Asal["👤 Asalariado<br/>(Régimen 605)"]
        Indep["👤 Independiente<br/>(RESICO 626 / Emp. 612)"]
        Arrend["👤 Arrendamiento<br/>(Régimen 606)"]
        Plat["👤 Plataformas<br/>(Régimen 625)"]
        PYME["👤 PYME<br/>(612/626/621)"]
        Admin["🔧 Admin"]
    end

    subgraph Auth["Autenticación"]
        UC1["Registrarse<br/>(Email/Google)"]
        UC2["Iniciar Sesión"]
        UC3["Completar Onboarding<br/>(4 pasos)"]
    end

    subgraph Comunes["Casos de Uso Comunes"]
        UC4["Ver Dashboard<br/>con estadísticas"]
        UC5["Ver Marketplace<br/>de servicios"]
        UC6["Editar Perfil<br/>de contribuyente"]
        UC7["Ver Historial<br/>de declaraciones"]
        UC8["Exportar PDF"]
        UC9["Chat por Voz<br/>(Fiscalito AI)"]
    end

    subgraph FiscalitoUC["Fiscalito — Servicios Fiscales"]
        UC10["Calcular<br/>Pre-Declaración<br/>ISR/IVA"]
        UC11["Ver Calendario<br/>de Obligaciones"]
        UC12["Comparar Régimenes<br/>(RESICO vs Emp.)"]
        UC13["Generar DIOT<br/>(Proveedores)"]
        UC14["Calcular Retenciones<br/>a Terceros"]
        UC15["Análisis<br/>Multi-Periodo"]
        UC16["Estado de Cuenta<br/>y Proyección Anual"]
        UC17["Calcular Deducciones<br/>Personales"]
    end

    subgraph AdminUC["Administración"]
        UC18["Gestionar Servicios"]
        UC19["Gestionar Usuarios"]
    end

    %% Todos los usuarios
    Asal --> UC1 & UC2 & UC3
    Indep --> UC1 & UC2 & UC3
    Arrend --> UC1 & UC2 & UC3
    Plat --> UC1 & UC2 & UC3
    PYME --> UC1 & UC2 & UC3

    Asal --> UC4 & UC5 & UC6 & UC7 & UC8 & UC9
    Indep --> UC4 & UC5 & UC6 & UC7 & UC8 & UC9
    Arrend --> UC4 & UC5 & UC6 & UC7 & UC8 & UC9
    Plat --> UC4 & UC5 & UC6 & UC7 & UC8 & UC9
    PYME --> UC4 & UC5 & UC6 & UC7 & UC8 & UC9

    %% Asalariado: solo deducciones y calendario
    Asal --> UC17 & UC11

    %% Independiente: declaración, calendario, comparar, estado + según régimen
    Indep --> UC10 & UC11 & UC12 & UC16
    Indep -.->|"Solo Empresarial<br/>(612)"| UC13 & UC14 & UC15

    %% Arrendamiento
    Arrend --> UC10 & UC11 & UC12 & UC15 & UC16

    %% Plataformas
    Plat --> UC10 & UC11 & UC16

    %% PYME: todos los tabs
    PYME --> UC10 & UC11 & UC12 & UC13 & UC14 & UC15 & UC16 & UC17

    %% Admin
    Admin --> UC18 & UC19

    %% Dependencias
    UC10 -.->|"include"| UC8
    UC13 -.->|"include"| UC8
    UC14 -.->|"include"| UC8
    UC15 -.->|"include"| UC8
    UC16 -.->|"include"| UC8
```

---

## 6. Diagrama de Estados — Ciclo de Vida del Usuario

```mermaid
stateDiagram-v2
    [*] --> NoRegistrado

    NoRegistrado --> Registrando: Click Registrarse
    Registrando --> Autenticado: Firebase Auth OK
    Registrando --> NoRegistrado: Error auth

    NoRegistrado --> Autenticado: Login exitoso

    Autenticado --> Onboarding: onboardingComplete == false
    Autenticado --> Activo: onboardingComplete == true

    state Onboarding {
        [*] --> Paso1_TipoContribuyente
        Paso1_TipoContribuyente --> Paso2_DatosFiscales: Selecciona tipo
        Paso2_DatosFiscales --> Paso3_DatosPersonales: RFC + Régimen
        Paso3_DatosPersonales --> Paso4_Confirmacion: Nombre + datos
        Paso4_Confirmacion --> [*]: Guardar en Firestore
    }

    Onboarding --> Activo: onboardingComplete = true

    state Activo {
        [*] --> Dashboard
        Dashboard --> Marketplace: Explorar servicios
        Dashboard --> Historial: Ver declaraciones
        Dashboard --> Perfil: Editar datos

        Marketplace --> FiscalitoService: Usar Fiscalito
        
        state FiscalitoService {
            [*] --> SeleccionTab
            SeleccionTab --> SubiendoXML: Tab con facturas
            SeleccionTab --> ConfigurandoParams: Tab sin facturas
            SubiendoXML --> Calculando: Enviar a API
            ConfigurandoParams --> Calculando: Enviar a API
            Calculando --> MostrandoResultado: Éxito
            Calculando --> MostrandoError: Fallo
            MostrandoResultado --> ExportandoPDF: Exportar
            MostrandoResultado --> GuardandoHistorial: Auto-guardado
            MostrandoResultado --> SeleccionTab: Nueva consulta
            MostrandoError --> SeleccionTab: Reintentar
        }

        FiscalitoService --> Dashboard: Volver
        Historial --> Dashboard: Volver
        Perfil --> Dashboard: Volver
    }

    Activo --> NoRegistrado: Sign Out
```

---

## 7. Diagrama de Paquetes (Estructura del Proyecto)

```mermaid
graph TB
    subgraph src["📁 src/"]
        main["main.tsx<br/>(Entry + Router + Providers)"]

        subgraph styles["📁 styles/"]
            globalCSS["global.css<br/>(Variables CSS + Tema)"]
        end

        subgraph context["📁 context/"]
            AuthContext["AuthContext.tsx<br/>(Firebase Auth)"]
            ProfileContext["ProfileContext.tsx<br/>(Perfil Firestore)"]
        end

        subgraph pages["📁 pages/"]
            p1["LandingPage.tsx"]
            p2["LoginPage.tsx"]
            p3["OnboardingWizard.tsx"]
            p4["DashboardPage.tsx"]
            p5["MarketplacePage.tsx"]
            p6["ServiceDetailPage.tsx"]
            p7["FiscalitoServicePage.tsx"]
            p8["HistorialPage.tsx"]
            p9["ProfilePage.tsx"]
            p10["AdminPage.tsx"]
        end

        subgraph components["📁 components/"]
            AppLayout["AppLayout.tsx<br/>(Sidebar + Layout)"]
            ProtectedRoute["ProtectedRoute.tsx"]
            subgraph fiscalitoComp["📁 fiscalito/"]
                f1["PreDeclaracionTab"]
                f2["XMLUploader"]
                f3["PeriodSelector"]
                f4["ResultadoDeclaracion"]
                f5["CalendarioTab"]
                f6["CompararRegimenTab"]
                f7["DIOTTab"]
                f8["RetencionesTab"]
                f9["MultiPeriodoTab"]
                f10["EstadoCuentaTab"]
                f11["DeduccionesPersonalesTab"]
            end
        end

        subgraph services["📁 services/"]
            s1["firebase.ts<br/>(Init Firebase)"]
            s2["fiscalAgentApi.ts<br/>(10 endpoints)"]
            s3["cfdiParser.ts<br/>(XML → CFDI)"]
            s4["declaracionesHistory.ts<br/>(CRUD Firestore)"]
            s5["storeServices.ts<br/>(Catálogo servicios)"]
            s6["contributorProfiles.ts<br/>(5 tipos contribuyente)"]
            s7["voiceChatService.ts<br/>(Whisper + GPT)"]
            s8["pdfExport*.ts<br/>(5 exportadores)"]
        end
    end

    main --> context
    main --> pages
    pages --> components
    pages --> services
    components --> services
    context --> services
    AuthContext --> s1
    ProfileContext --> s1
    s4 --> s1
```

---

## 8. Diagrama de Despliegue

```mermaid
graph TB
    subgraph UserDevice["🖥️ Dispositivo del Usuario"]
        Browser["Navegador Web<br/>(Chrome/Firefox/Safari)"]
    end

    subgraph Hosting["🌐 Hosting (por definir)"]
        SPA["React SPA<br/>(Build estático)<br/>Vite + TypeScript"]
    end

    subgraph FirebaseCloud["☁️ Google Cloud / Firebase"]
        FBAuth["Firebase Authentication<br/>• Email/Password<br/>• Google OAuth"]
        FBStore["Cloud Firestore<br/>• users/{uid}<br/>• users/{uid}/declaraciones"]
    end

    subgraph BackendServer["⚙️ Servidor Backend"]
        FiscalAgent["Fiscal Agent API<br/>FastAPI / Python<br/>localhost:8000 | Cloud Run"]
        LLM["LLM Engine<br/>(OpenAI / Anthropic)<br/>Explicaciones fiscales"]
    end

    subgraph OpenAICloud["🤖 OpenAI API"]
        Whisper["Whisper<br/>(Speech-to-Text)"]
        GPT["GPT-4o-mini<br/>(Chat fiscal)"]
        TTS["Text-to-Speech"]
    end

    Browser <-->|"HTTPS"| SPA
    SPA <-->|"Firebase SDK"| FBAuth
    SPA <-->|"Firebase SDK"| FBStore
    SPA <-->|"REST API<br/>JSON"| FiscalAgent
    SPA <-->|"REST API"| OpenAICloud
    FiscalAgent <-->|"API calls"| LLM

    style UserDevice fill:#080409,stroke:#492153,color:#e8e4ec
    style FirebaseCloud fill:#0f0a12,stroke:#355654,color:#e8e4ec
    style BackendServer fill:#0f0a12,stroke:#492153,color:#e8e4ec
    style OpenAICloud fill:#0f0a12,stroke:#355654,color:#e8e4ec
```

---

## 9. Diagrama Entidad-Relacion (Firestore)

```mermaid
erDiagram
    USER ||--o{ DECLARACION : "tiene"
    USER {
        string uid PK
        string contributorType "asalariado|independiente|arrendamiento|plataformas|pyme"
        string rfc
        string regimen "605|606|612|625|626|621"
        string nombre
        string actividad
        string cp
        string telefono
        string nombreNegocio "solo PYME"
        string numEmpleados "solo PYME"
        boolean onboardingComplete
        timestamp updatedAt
    }

    DECLARACION {
        string id PK
        string categoria "predeclaracion|diot|retenciones|multiperiodo|estado_cuenta|deducciones"
        string tipo "monthly|bimonthly|annual"
        string periodo "Enero 2025"
        string regimen
        timestamp fecha_calculo
        number facturas_count
        object desglose "DesgloseFiscal (pre-declaraciones)"
        string explicacion "Explicación IA"
        array advertencias
        array recomendaciones
        array proveedores "DIOTProveedor[] (solo DIOT)"
        array terceros "RetencionTercero[] (solo retenciones)"
        array resultados "PeriodoResultado[] (solo multi)"
        object acumulado "AcumuladoMultiPeriodo (solo multi)"
        object estado_cuenta "solo estado de cuenta"
    }

    CONTRIBUTOR_PROFILE {
        string id PK "tipo contribuyente"
        string label
        string description
        array allowedRegimens
        array obligations
        array applicableServices
    }

    STORE_SERVICE {
        string id PK
        string name
        string status "active|coming_soon|beta"
        string category "fiscal|laboral|contable"
        array appliesTo "ContributorType[]"
        string apiEndpoint
    }

    USER }o--|| CONTRIBUTOR_PROFILE : "es tipo"
    CONTRIBUTOR_PROFILE }o--o{ STORE_SERVICE : "tiene acceso a"
```

---

## Notas

- Los diagramas reflejan el estado actual del proyecto al 7 de abril 2026.
- Para renderizar: GitHub, GitLab, Notion, VS Code (con extensión Mermaid), o [mermaid.live](https://mermaid.live).
- El Fiscal Agent API es stateless — toda la lógica de persistencia está en Firestore desde el frontend.
