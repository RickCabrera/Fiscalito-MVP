# Runbook de conexión de servicios (P6-06)

Guía paso a paso para conectar Fiscalito a sus servicios reales. Está escrita para que la siga
alguien (o Claude en Chrome) **sin contexto**: cada paso dice qué cuenta abrir, qué variable
llenar, dónde pegarla y cómo comprobar que quedó.

- Detalle técnico de cada adaptador (qué hace, cómo se prueba sin red): `docs/servicios-externos.md`.
- Lista de tareas de conexión: sección **EXT** de `backlog.md` (EXT-01 a EXT-16).
- Cuando una URL no se conoce con certeza, el paso dice **"buscar en el portal del proveedor"**
  en vez de inventarla.
- `tests/test_runbook_conexion.py` (en `apps/api`) falla si una variable de `apps/api/.env.example`
  o de `apps/store/.env.example`, o la variable de un adaptador registrado, no aparece aquí.

---

## 0. Antes de empezar: dónde va cada variable y cómo se comprueba

### 0.1 Variables del backend (`apps/api`) → Railway

1. Entra a <https://railway.com> con la cuenta del despacho y abre el proyecto de Fiscalito.
2. Abre el servicio **API** → pestaña **Variables**.
3. Para pegar varias a la vez usa **Raw Editor** (formato `NOMBRE=valor`, una por renglón).
4. El **worker** (`python -m app.trabajos.worker`, que también corre la programación recurrente)
   necesita **las mismas variables** que la API: en su servicio, pestaña **Variables**, usa
   referencias a las de la API o pega el mismo bloque.
5. Railway reinicia el servicio al guardar. Espera a que el despliegue quede en verde.

### 0.2 Variables del front (`apps/store`) → build de Vite

Las `VITE_*` **se incrustan al compilar** (`npm run build`), no se leen en tiempo de ejecución:

1. En la máquina o CI que compila el front, crea `apps/store/.env.production` con las `VITE_*`.
2. Compila (`npm run build` desde `apps/store`) y publica `dist/` donde se sirva el front
   (Firebase Hosting hoy, ver EXT-02).
3. Nunca pongas una llave secreta en una `VITE_*`: todo lo que empieza con `VITE_` termina en el
   navegador (`src/sinLlavesLLM.test.ts` vigila las de LLM).

### 0.3 Cómo comprobar

- `GET https://<api>/health` → `{"status": "ok"}`.
- `GET https://<api>/health/integraciones` → por servicio: `implementacion`, `configurado` y
  `es_falso`. **Listo para producción** cuando `listo_para_produccion` es `true`: ningún
  servicio sin configurar y ninguno con la implementación `falso`.
- Cada sección de abajo trae además una prueba concreta en la app.

---

## EXT-01 · Railway (API, worker, base de datos)

1. Crea cuenta en <https://railway.com> y un proyecto nuevo "Fiscalito".
2. Agrega un servicio desde el repositorio de GitHub con raíz `apps/api` (servicio **API**).
3. Agrega una base **PostgreSQL** al proyecto (botón *New* → *Database* → *PostgreSQL*).
4. En el servicio API, pestaña **Variables**, crea `DATABASE_URL` con la referencia a la de
   Postgres (`${{Postgres.DATABASE_URL}}`; si el nombre del servicio de base es otro, usa el que
   muestre Railway). La app acepta `postgres://` y lo convierte sola.
5. Pega también:
   - `FISCALITO_ENTORNO=produccion` — sin esto, los servicios sin configurar caen al `falso` en
     silencio. Con `produccion`, un servicio sin configurar responde 503 y se ve en
     `/health/integraciones`.
   - `HOST=0.0.0.0` y `PORT` — Railway inyecta `PORT`; no lo sobrescribas salvo que el
     comando de arranque lo pida.
   - `CORS_ORIGINS` — la URL pública del front, separada por comas si hay varias
     (p. ej. `https://app.tudominio.mx`). **No dejes `*` en producción.**
   - `FISCALITO_URL_APP` — URL pública del front (se usa en los enlaces de invitación al equipo).
   - `FISCALITO_URL_PUBLICA_API` — URL pública de esta API (enlaces firmados de descarga,
     webhooks de WhatsApp y Twilio).
   - `FISCALITO_ENLACES_SECRETO` — secreto largo y aleatorio para firmar enlaces de descarga.
     Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
     Obligatorio en producción.
   - `FISCALITO_LLAVE_MAESTRA` — llave Fernet que cifra e.firmas y CSD. Generar:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
     **Guárdala también fuera de Railway**: si se pierde, todas las e.firma y CSD guardados
     quedan ilegibles. Rotación: `nueva,vieja` (ver `docs/servicios-externos.md`).
6. Crea un segundo servicio **worker** desde el mismo repo y la misma raíz, con comando de
   arranque `python -m app.trabajos.worker` y las mismas variables (paso 0.1.4).
7. Aplica las migraciones contra la base de Railway (`alembic upgrade head` desde `apps/api`,
   con `DATABASE_URL` apuntando a Postgres).
8. **Redis:** hoy la app no lo usa (el límite de peticiones vive en memoria,
   `FISCALITO_LIMITADOR=memoria`, la única implementación). No lo contrates hasta tener varias
   réplicas de la API.
9. Límites de la API (opcionales, ya tienen default):
   - `FISCALITO_RATE_LIMIT_POR_MINUTO` (default 120 por usuario).
   - `FISCALITO_RATE_LIMIT_LLM_POR_MINUTO` (default 20) y `FISCALITO_TOPE_LLM_DIARIO_LLAMADAS`
     (default 500 por despacho y día) — ver EXT-09.
   - `FISCALITO_LIMITADOR` — déjala sin poner o en `memoria`.

**Comprobar:** `GET /health` responde `ok`; `GET /health/integraciones` responde (aunque
todavía marque servicios sin configurar); el log del worker muestra que toma trabajos.

---

## EXT-02 · Firebase (login y hosting del front)

1. Entra a <https://console.firebase.google.com> y abre el proyecto (`fiscalito-mvp` hoy).
2. **Authentication** → *Sign-in method*: deja activos *Email/Password* y *Google*.
3. **Authentication** → *Settings* → *Authorized domains*: agrega el dominio del front
   (EXT-13).
4. **Configuración del proyecto** → *Tus apps* → app web: copia los valores de configuración a
   `apps/store/.env.production` (paso 0.2):
   - `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`,
     `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`,
     `VITE_FIREBASE_APP_ID`.
   - `VITE_FISCAL_AGENT_URL` — la URL pública de la API de Railway (EXT-01).
5. Restringe la llave web por dominio: en la consola de Google Cloud del mismo proyecto,
   *APIs y servicios* → *Credenciales* → la llave de navegador → restricción por referente HTTP
   con el dominio del front (la ruta exacta del menú: buscar en el portal del proveedor si
   cambió).
6. **Backend (verificación del ID token):**
   - `FIREBASE_PROJECT_ID` en Railway con el id del proyecto (default `fiscalito-mvp`).
   - `GOOGLE_APPLICATION_CREDENTIALS`: la ruta a un JSON de *service account* del proyecto
     (*Configuración del proyecto* → *Cuentas de servicio* → *Generar nueva clave privada*).
     **PENDIENTE:** esta variable es una RUTA a archivo y Railway no monta archivos secretos
     por default; buscar en la documentación de Railway cómo montar un archivo, o abrir una
     tarea para que la API acepte el JSON en una variable. Sin credenciales, todo
     `/api/v1/*` responde 503.
   - `PERMITIR_TOKEN_SIN_VERIFICAR` y `FIRESTORE_EMULATOR_HOST`: **nunca** en Railway. Son
     sólo para desarrollo con el emulador.
7. **Hosting:** desde `apps/store`, `npm run build` y luego `firebase deploy --only hosting`
   (necesita la CLI `firebase-tools` con sesión iniciada). `firebase.json` ya sirve `dist/`
   como SPA.
8. **Demostración:** `VITE_MOSTRAR_DEMO` y `VITE_CUENTAS_DEMO` **se dejan vacías en
   producción**. `VITE_MOSTRAR_DEMO=1` enseña los clientes de demostración a todos (sólo para
   un ensayo); `VITE_CUENTAS_DEMO` es una lista de correos que sí los ven.

**Comprobar:** abrir el front, iniciar sesión con Google y con correo; la pantalla de Clientes
carga sin "503". En la API, el log no muestra `CredencialesFaltantes`.

---

## EXT-03 · Descarga masiva del SAT

No se contrata: es un servicio público del SAT que se usa con la **e.firma de cada cliente**.

1. En Railway: `FISCALITO_SAT_DESCARGA=sat`.
2. Opcionales (tienen default):
   - `FISCALITO_SAT_DIAS_MAX_ESPERA` (default 7) y `FISCALITO_SAT_HORAS_AVISO` (default 24).
   - `FISCALITO_SAT_URL_AUTENTICACION`, `FISCALITO_SAT_URL_SOLICITUD`,
     `FISCALITO_SAT_URL_VERIFICACION`, `FISCALITO_SAT_URL_DESCARGA`: **no las pongas**; el
     default son las de producción del SAT. Sólo sirven para apuntar a otro ambiente.
3. En la app, en la ficha de un cliente, sube su e.firma (`.cer`, `.key` y contraseña).
4. Lanza una descarga de un mes conocido desde la pantalla del SAT de ese cliente.

**Comprobar:** `/health/integraciones` muestra `sat_descarga` con `implementacion: sat`; la
solicitud pasa de "en proceso" a "terminada" (puede tardar de minutos a días) y los XML
aparecen en la bóveda. Lo que falta confirmar con una e.firma real está en
`docs/servicios-externos.md` (Descarga masiva).

---

## EXT-04 · PAC (timbrado y cancelación)

1. Elige uno (decisión DP-4): Finkok, SW Sapien o Facturama. Pide **cuenta de pruebas
   (sandbox)** primero. Portales: Finkok <https://www.finkok.com>, Facturama
   <https://facturama.mx>; SW Sapien: buscar en el portal del proveedor.
2. En Railway: `FISCALITO_PAC=finkok` | `sw_sapien` | `facturama`.
3. Variables según el PAC:
   - Finkok: `FISCALITO_FINKOK_USUARIO`, `FISCALITO_FINKOK_PASSWORD`, `FISCALITO_FINKOK_URL`
     (default `https://demo-facturacion.finkok.com`; producción
     `https://facturacion.finkok.com`).
   - SW Sapien: `FISCALITO_SW_TOKEN` (o `FISCALITO_SW_USUARIO` + `FISCALITO_SW_PASSWORD`) y
     `FISCALITO_SW_URL` (default `https://services.test.sw.com.mx`; la de producción: buscar en
     el portal del proveedor).
   - Facturama: `FISCALITO_FACTURAMA_USUARIO`, `FISCALITO_FACTURAMA_PASSWORD`,
     `FISCALITO_FACTURAMA_URL` (default `https://apisandbox.facturama.mx`; la de producción:
     buscar en el portal del proveedor). Facturama exige subir el CSD de cada cliente a su
     cuenta Multiemisor y hoy sólo timbra retenciones (ingreso y nómina responden 501).
4. En la app, sube el **CSD** de cada cliente en su ficha.
5. Con sandbox: timbra un CFDI de retenciones o un recibo de nómina de prueba.
6. Ya validado, cambia usuario/contraseña/URL por los de producción.

**Comprobar:** `/health/integraciones` → `pac` con la implementación elegida; el PDF del
documento timbrado **ya no** dice "NO FISCAL" en rojo; el UUID aparece en la verificación de
CFDI del SAT (<https://verificacfdi.facturaelectronica.sat.gob.mx>).

---

## EXT-05 · Estatus de CFDI y listas 69-B / 69

Servicios públicos del SAT, sin contrato.

1. En Railway: `FISCALITO_SAT_ESTATUS=sat` y `FISCALITO_SAT_LISTAS=sat`.
2. Estatus (opcionales, con default): `FISCALITO_SAT_ESTATUS_URL` (no la pongas: default
   producción), `FISCALITO_SAT_ESTATUS_CONCURRENCIA` (4), `FISCALITO_SAT_ESTATUS_POR_SEGUNDO`
   (5), `FISCALITO_SAT_ESTATUS_LOTE` (1000).
3. Listas: `FISCALITO_SAT_LISTAS_ACTIVAS` (default `69b`). Las URL de cada lista se pueden
   corregir con `FISCALITO_SAT_LISTA_<LISTA>_URL` (p. ej. `FISCALITO_SAT_LISTA_69B_URL`).
   Antes de activar las del art. 69, confirma sus URL vigentes en el portal de datos abiertos
   del SAT (buscar en el portal del proveedor).

**Comprobar:** en la bóveda, "Verificar estatus" de un cliente con un UUID conocido cambia su
estatus; `GET /api/v1/sat/listas/estado` muestra la última carga sin error. Si el SAT responde
con errores de ritmo, baja `FISCALITO_SAT_ESTATUS_POR_SEGUNDO`.

---

## EXT-06 · Opinión de cumplimiento y constancia

1. Decide la vía (DP-2) y ponla en `FISCALITO_OPINION_CUMPLIMIENTO`:
   - `manual` — el despacho sube el PDF; no hay que contratar nada.
   - `portal_sat` — usa la e.firma del cliente (EXT-03, paso 3). Sin contrato.
   - `proveedor` — un tercero por API. Llena las `FISCALITO_OPINION_PROVEEDOR_*`:
     `FISCALITO_OPINION_PROVEEDOR_URL` (con `{rfc}` y `{tipo}`),
     `FISCALITO_OPINION_PROVEEDOR_API_KEY`, `FISCALITO_OPINION_PROVEEDOR_ENCABEZADO`
     (default `Authorization`), `FISCALITO_OPINION_PROVEEDOR_METODO` (default `GET`),
     `FISCALITO_OPINION_PROVEEDOR_CAMPOS` y `FISCALITO_OPINION_PROVEEDOR_RESULTADOS` (JSON,
     ver `docs/servicios-externos.md`).
2. Opcional: `FISCALITO_OPINION_DIAS_VIGENCIA` (default 30).

**Comprobar:** en la ficha de un cliente, "Obtener ahora" (o subir el PDF con `manual`) deja la
opinión con su semáforo y el PDF descargable.

---

## EXT-07 · WhatsApp Business

1. Elige: **Meta** directo (<https://developers.facebook.com>, app de tipo negocio con el
   producto WhatsApp) o **Twilio** (<https://console.twilio.com>). 360dialog no tiene
   adaptador todavía.
2. En Railway: `FISCALITO_WHATSAPP=meta` o `twilio`.
3. Meta:
   - `FISCALITO_WHATSAPP_TOKEN` (token permanente de usuario del sistema),
     `FISCALITO_WHATSAPP_PHONE_ID` (id del número), `FISCALITO_WHATSAPP_APP_SECRET` (secreto
     de la app; firma `X-Hub-Signature-256`), `FISCALITO_WHATSAPP_VERSION` (default `v20.0`).
   - En la consola de Meta, webhook: URL `https://<api>/api/v1/whatsapp/webhook` y como
     *Verify token* el mismo valor que pongas en `FISCALITO_WHATSAPP_VERIFY_TOKEN`.
4. Twilio: `FISCALITO_TWILIO_ACCOUNT_SID`, `FISCALITO_TWILIO_AUTH_TOKEN`,
   `FISCALITO_TWILIO_WHATSAPP_FROM` (número con `+`). Webhook entrante a
   `https://<api>/api/v1/whatsapp/webhook`; Twilio firma sobre `FISCALITO_URL_PUBLICA_API`,
   así que esa variable debe ser exactamente la URL pública.
5. Plantillas aprobadas (fuera de la ventana de 24 h sólo se puede mandar plantilla):
   recibos de nómina (encabezado DOCUMENT + 3 variables) y documentos al cliente
   (`FISCALITO_WHATSAPP_PLANTILLA_DOCUMENTOS`, default `documento_cliente`, encabezado DOCUMENT
   + 2 variables). En Twilio la plantilla es un Content SID `HX...`.
6. Opcional: `FISCALITO_WHATSAPP_BOT_POR_MINUTO` (default 6 mensajes por minuto por número).
7. Requisitos que ya deben existir: `FISCALITO_URL_PUBLICA_API` y `FISCALITO_ENLACES_SECRETO`
   (EXT-01).

**Comprobar:** la verificación del webhook en Meta pasa (sin el verify token responde 403);
enviar un documento a un contacto con consentimiento de WhatsApp desde la app llega al
teléfono; escribirle al número responde el bot.

---

## EXT-08 · Correo transaccional

1. Elige: **Resend** (<https://resend.com>), **SendGrid** (<https://sendgrid.com>) o cualquier
   **SMTP** (SES incluido).
2. Verifica el dominio de envío con SPF y DKIM en el DNS (EXT-13), siguiendo los registros que
   te muestre el proveedor.
3. En Railway: `FISCALITO_CORREO=resend` | `sendgrid` | `smtp` y
   `FISCALITO_CORREO_REMITENTE` (p. ej. `Fiscalito <avisos@tudominio.mx>`).
4. Según el proveedor:
   - Resend: `FISCALITO_RESEND_API_KEY`.
   - SendGrid: `FISCALITO_SENDGRID_API_KEY`.
   - SMTP: `FISCALITO_SMTP_HOST`, `FISCALITO_SMTP_PUERTO` (587 STARTTLS o 465 SSL),
     `FISCALITO_SMTP_USUARIO`, `FISCALITO_SMTP_PASSWORD`.

**Comprobar:** invitar a un usuario al equipo (Perfil → Equipo) manda el correo con el enlace a
`FISCALITO_URL_APP`.

---

## EXT-09 · LLM (y voz del asistente)

1. Crea la llave en OpenAI (<https://platform.openai.com>) o Anthropic
   (<https://console.anthropic.com>). **Pon tope de gasto mensual en la consola del proveedor.**
2. En Railway (nunca en el front):
   - `FISCALITO_LLM=openai` o `anthropic` (el adaptador del asistente y del bot).
   - `LLM_PROVIDER=openai` o `anthropic` (las explicaciones de las declaraciones).
   - OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`).
   - Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-haiku-4-5-20251001`).
3. Voz del asistente: `FISCALITO_VOZ=openai` (usa `OPENAI_API_KEY`; Whisper y TTS). Sin
   llave de OpenAI, déjala sin poner y la voz responde 503.
4. Topes propios (EXT-01, paso 9): `FISCALITO_RATE_LIMIT_LLM_POR_MINUTO`,
   `FISCALITO_TOPE_LLM_DIARIO_LLAMADAS`.

**Comprobar:** abrir el asistente en la app y preguntar algo; la respuesta no empieza con
`[falso]`. Una pre-declaración trae explicación. El LLM nunca calcula impuestos: las cifras
siguen saliendo del motor.

---

## EXT-10 · Almacenamiento de archivos (XML y PDF)

1. Recomendado **Cloudflare R2** (<https://dash.cloudflare.com>, sección R2): crea un bucket
   **privado** y un token de API con lectura y escritura sólo sobre ese bucket. Alternativa:
   AWS S3 con un usuario IAM limitado al bucket.
2. En Railway:
   - `FISCALITO_ALMACENAMIENTO=s3`
   - `FISCALITO_S3_BUCKET` (obligatoria), `FISCALITO_S3_ENDPOINT` (R2:
     `https://<cuenta>.r2.cloudflarestorage.com`; vacío en AWS),
     `FISCALITO_S3_REGION` (`auto` en R2), `FISCALITO_S3_ACCESS_KEY`,
     `FISCALITO_S3_SECRET_KEY`, `FISCALITO_S3_PREFIJO` (opcional, p. ej. `prod`).
3. `FISCALITO_ALMACEN_DIR` sólo aplica a `local`/`falso` (disco); **no uses disco en
   Railway**: se pierde en cada despliegue.

**Comprobar:** subir un XML a la bóveda de un cliente y descargarlo de vuelta; el objeto aparece
en el bucket bajo `cfdi/...`.

---

## EXT-11 · Pagos de suscripción

1. Elige **Stripe** (<https://dashboard.stripe.com>) o **Mercado Pago**
   (<https://www.mercadopago.com.mx/developers>). Conekta no tiene adaptador todavía.
2. En Railway: `FISCALITO_PAGOS=stripe` o `mercadopago`.
   - Stripe: `FISCALITO_STRIPE_API_KEY` (`sk_...`), `FISCALITO_STRIPE_WEBHOOK_SECRET`
     (`whsec_...`).
   - Mercado Pago: `FISCALITO_MERCADOPAGO_ACCESS_TOKEN`,
     `FISCALITO_MERCADOPAGO_WEBHOOK_SECRET`. Ojo: hoy sus eventos se registran y se ignoran
     (pendiente en `docs/servicios-externos.md`).
3. Crea en el proveedor un precio (Price de Stripe / plan de Mercado Pago) por cada plan y pon:
   - `FISCALITO_PAGOS_PRECIO_<ID>` (p. ej. `FISCALITO_PAGOS_PRECIO_CONTADOR=price_...`).
   - `FISCALITO_PLAN_<ID>_PRECIO` (precio mensual que se MUESTRA, p. ej. `499.00`) y
     `FISCALITO_PLAN_MONEDA` (default `MXN`).
   - Opcionales: `FISCALITO_PLANES_MODULOS` (JSON), `FISCALITO_SUSCRIPCION_DIAS_PRUEBA`
     (default 14), `FISCALITO_SUSCRIPCION_DIAS_GRACIA` (default 3).
4. En el panel del proveedor, webhook a `https://<api>/api/v1/pagos/webhook`.
5. `FISCALITO_PAGOS_FALSO_SECRETO` sólo aplica al proveedor `falso`: no la pongas en producción.

**Comprobar:** en Perfil → Planes, suscribirse con una tarjeta de prueba del proveedor; el
webhook llega (en el panel del proveedor sale 200) y el estado de la suscripción cambia en la
app.

---

## EXT-12 · Monitoreo

1. Crea un proyecto Python en Sentry (<https://sentry.io>).
2. `sentry-sdk` **no es dependencia todavía**: hace falta agregarlo a `apps/api/pyproject.toml`
   (tarea de código) antes de encender `sentry`. Mientras tanto usa `FISCALITO_MONITOREO=log`
   (los errores salen en el log de Railway).
3. Con el paquete instalado: `FISCALITO_MONITOREO=sentry` y `FISCALITO_SENTRY_DSN`.

**Comprobar:** `/health/integraciones` → `monitoreo` sin `es_falso`; un error provocado aparece
en Sentry (o en el log con `log`).

---

## EXT-13 · Dominio y DNS

1. Compra el dominio en el registrador que prefieras.
2. Registros:
   - `app.<dominio>` → el front (Firebase Hosting: *Hosting* → *Agregar dominio personalizado*;
     sigue los registros que indique).
   - `api.<dominio>` → el servicio API de Railway (*Settings* → *Networking* → *Custom
     Domain*; sigue el CNAME que indique).
   - SPF y DKIM del proveedor de correo (EXT-08).
3. Actualiza con los dominios definitivos: `CORS_ORIGINS`, `FISCALITO_URL_APP`,
   `FISCALITO_URL_PUBLICA_API` (Railway), `VITE_FISCAL_AGENT_URL` (build del front, y vuelve a
   compilar), los dominios autorizados de Firebase (EXT-02, paso 3) y las URL de webhook de
   WhatsApp y pagos.

**Comprobar:** `https://api.<dominio>/health` responde `ok` con certificado válido y el front en
`https://app.<dominio>` inicia sesión.

---

## EXT-14 · IDSE y SUA

No tienen API: no se configura nada en Fiscalito.

1. En la app, Nómina del cliente → exportador IMSS, genera el archivo TXT de movimientos.
2. El despacho lo sube en el portal IDSE con **su propio certificado del IMSS** (buscar en el
   portal del proveedor el acceso vigente) o lo importa en SUA.

**Comprobar:** IDSE acepta el lote y devuelve su acuse.

---

## EXT-15 · Checador Hikvision

1. En la app, en Dispositivos del cliente, da de alta el checador y **emite su token**
   (`POST /api/v1/asistencia/tokens`, sólo dueño o contador). El token se ve una sola vez.
2. En el aparato (menú de red / *HTTP listening* o equivalente, según el modelo: buscar en el
   manual del proveedor), configura el envío de eventos a
   `https://<api>/api/v1/asistencia/eventos?token=<token>`.
3. Para probar desde una computadora sin aparato: `scripts/simular_checador.py` con
   `FISCALITO_TOKEN_DISPOSITIVO` (el token del paso 1) o `FISCALITO_ID_TOKEN` (un ID token de
   Firebase). `scripts/levantar_demo.py` usa `FISCALITO_DESPACHO_DEMO` (uid del despacho dueño
   de las checadas sembradas). **Ninguna de estas tres va en Railway.**

**Comprobar:** una checada en el aparato aparece en el panel del checador de la nómina del
cliente en menos de un minuto.

---

## EXT-16 · Bancos (opcional, después)

Sin adaptador todavía: la v1 concilia con archivos de estado de cuenta que se suben a mano. No
hay variables que llenar. Cuando se elija un agregador bancario, se agrega su adaptador y su
sección aquí.

---

## Otros adaptadores registrados

- **Buzón SAT** (`FISCALITO_BUZON_SAT`): déjala en `falso` o sin poner. `portal_sat` responde
  501 hasta confirmar el flujo con una e.firma real; el despacho sube el ZIP del Anexo 24 en el
  portal del SAT.

---

## Índice de variables → paso

| Variable | Dónde va | Paso |
|---|---|---|
| `DATABASE_URL` | Railway | EXT-01.4 |
| `FISCALITO_ENTORNO`, `HOST`, `PORT`, `CORS_ORIGINS` | Railway | EXT-01.5 |
| `FISCALITO_URL_APP`, `FISCALITO_URL_PUBLICA_API`, `FISCALITO_ENLACES_SECRETO` | Railway | EXT-01.5 |
| `FISCALITO_LLAVE_MAESTRA` | Railway | EXT-01.5 |
| `FISCALITO_RATE_LIMIT_POR_MINUTO`, `FISCALITO_LIMITADOR` | Railway | EXT-01.9 |
| `FISCALITO_RATE_LIMIT_LLM_POR_MINUTO`, `FISCALITO_TOPE_LLM_DIARIO_LLAMADAS` | Railway | EXT-01.9 / EXT-09.4 |
| `VITE_FIREBASE_*`, `VITE_FISCAL_AGENT_URL` | build del front | EXT-02.4 |
| `VITE_MOSTRAR_DEMO`, `VITE_CUENTAS_DEMO` | build del front (vacías) | EXT-02.8 |
| `FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | Railway | EXT-02.6 |
| `PERMITIR_TOKEN_SIN_VERIFICAR`, `FIRESTORE_EMULATOR_HOST` | nunca en producción | EXT-02.6 |
| `FISCALITO_SAT_DESCARGA`, `FISCALITO_SAT_*` de descarga | Railway | EXT-03 |
| `FISCALITO_PAC`, `FISCALITO_FINKOK_*`, `FISCALITO_SW_*`, `FISCALITO_FACTURAMA_*` | Railway | EXT-04 |
| `FISCALITO_SAT_ESTATUS*`, `FISCALITO_SAT_LISTAS*` | Railway | EXT-05 |
| `FISCALITO_OPINION_*` | Railway | EXT-06 |
| `FISCALITO_WHATSAPP*`, `FISCALITO_TWILIO_*` | Railway | EXT-07 |
| `FISCALITO_CORREO*`, `FISCALITO_RESEND_API_KEY`, `FISCALITO_SENDGRID_API_KEY`, `FISCALITO_SMTP_*` | Railway | EXT-08 |
| `FISCALITO_LLM`, `LLM_PROVIDER`, `OPENAI_*`, `ANTHROPIC_*`, `FISCALITO_VOZ` | Railway | EXT-09 |
| `FISCALITO_ALMACENAMIENTO`, `FISCALITO_S3_*`, `FISCALITO_ALMACEN_DIR` | Railway | EXT-10 |
| `FISCALITO_PAGOS*`, `FISCALITO_STRIPE_*`, `FISCALITO_MERCADOPAGO_*`, `FISCALITO_PLAN*`, `FISCALITO_SUSCRIPCION_*` | Railway | EXT-11 |
| `FISCALITO_MONITOREO`, `FISCALITO_SENTRY_DSN` | Railway | EXT-12 |
| `FISCALITO_TOKEN_DISPOSITIVO`, `FISCALITO_ID_TOKEN`, `FISCALITO_DESPACHO_DEMO` | sólo scripts locales | EXT-15.3 |
| `FISCALITO_BUZON_SAT` | Railway (`falso`) | Otros adaptadores |
