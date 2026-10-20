# Servicios externos de Fiscalito

Cada servicio externo vive detrás de un **adaptador** en `apps/api/app/integraciones/<servicio>.py`:
un `Protocol`, una implementación **falsa** (determinística, sin red) y las reales. La variable
`FISCALITO_<SERVICIO>` elige cuál se usa; sin ella se usa `falso` fuera de producción y, en
producción, la app responde 503 en ese servicio y `GET /health/integraciones` lo marca.

**Cambiar de proveedor es cambiar una variable**, no código. Ningún test toca la red: las reales
se prueban con `httpx.MockTransport` y respuestas grabadas en `apps/api/tests/fixtures/<servicio>/`
(ver `apps/api/tests/plan_p/test_integraciones.py`).

Para ver qué está configurado: `GET /health/integraciones`.

| Servicio | Variable | Implementaciones | Estado |
|---|---|---|---|
| Bóveda de credenciales | `FISCALITO_LLAVE_MAESTRA` | (no es adaptador) | P0-05 hecho |
| Correo | `FISCALITO_CORREO` | falso, smtp, resend, sendgrid | P0-06 hecho |
| WhatsApp | `FISCALITO_WHATSAPP` | falso, meta, twilio | P0-06 hecho |
| Pagos | `FISCALITO_PAGOS` | falso, stripe, mercadopago | P0-06 hecho |
| Monitoreo | `FISCALITO_MONITOREO` | falso, log, sentry | P0-06 hecho |
| LLM | `FISCALITO_LLM` | falso, openai, anthropic | P0-06 hecho |
| Voz del asistente | `FISCALITO_VOZ` | falso, openai | P5-07 hecho |
| Almacenamiento | `FISCALITO_ALMACENAMIENTO` | falso, local, s3 | P0-03 hecho |
| Descarga masiva SAT | `FISCALITO_SAT_DESCARGA` | falso, sat | P1-01 hecho |
| Estatus de CFDI | `FISCALITO_SAT_ESTATUS` | falso, sat | P1-03 hecho |
| Listas 69-B / 69 | `FISCALITO_SAT_LISTAS` | falso, sat | P1-04 hecho |
| Opinión de cumplimiento | `FISCALITO_OPINION_CUMPLIMIENTO` | falso, portal_sat, proveedor, manual | P1-05 hecho |
| Buzón SAT (contabilidad electrónica) | `FISCALITO_BUZON_SAT` | falso, portal_sat (POR CONFIRMAR) | P2-07 hecho (falso) |
| PAC | `FISCALITO_PAC` | falso, finkok, sw_sapien, facturama | P3-04 hecho (reales POR CONFIRMAR con sandbox) |

---

## Bóveda de credenciales (llave maestra)

**Qué es.** La e.firma y el CSD de cada cliente se guardan cifrados (Fernet) con una llave
maestra que sólo existe en el entorno del servidor. Ver `apps/api/app/credenciales/`.

**Variables.**
- `FISCALITO_LLAVE_MAESTRA` — una o varias llaves Fernet separadas por coma. **La primera
  cifra**; todas descifran. Generar:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `FISCALITO_ENTORNO` — `produccion` hace que falte la llave = 503. En `desarrollo` se usa una
  llave efímera con aviso fuerte en el log (lo guardado no sobrevive al reinicio).

**Rotación.** Pon la nueva primero (`nueva,vieja`), reinicia, corre
`app.credenciales.servicio.recifrar_todo(db)` y quita la vieja.

**Cómo probar.** `pytest tests/plan_p/test_credenciales.py` (genera una CA y certificados de
prueba con formato SAT; ninguno es real).

**A quién contratar.** Nadie. Guarda la llave en el gestor de secretos de Railway. **Si se
pierde, todas las e.firma y CSD guardados son ilegibles** y hay que volver a subirlos.

---

## Correo transaccional

**Qué es.** Avisos de vencimiento, recibos de nómina, papeles de trabajo.
`enviar(destinatarios, asunto, html, adjuntos) -> id`.

**Variables.** `FISCALITO_CORREO` = `falso` | `smtp` | `resend` | `sendgrid`.
- Comunes: `FISCALITO_CORREO_REMITENTE` (p. ej. `Fiscalito <avisos@tudominio.mx>`).
- smtp: `FISCALITO_SMTP_HOST`, `FISCALITO_SMTP_PUERTO` (587 STARTTLS / 465 SSL),
  `FISCALITO_SMTP_USUARIO`, `FISCALITO_SMTP_PASSWORD`.
- resend: `FISCALITO_RESEND_API_KEY`.
- sendgrid: `FISCALITO_SENDGRID_API_KEY`.

**Cómo probar.** El falso guarda en `.enviados`. Las reales: `test_correo_*`.

**A quién contratar.** Resend (el más simple) o SendGrid; SES si ya hay AWS. Hay que verificar
el dominio con SPF y DKIM (EXT-08, EXT-13).

**Invitaciones al equipo (P5-01).** El enlace del correo de invitación se arma con
`FISCALITO_URL_APP` (la URL pública del front, p. ej. `https://app.fiscalito.mx`; default
`http://localhost:5173`). Los recordatorios de cobro (P5-03) usan este mismo adaptador.

---

## WhatsApp

**Qué es.** Envío de documentos y avisos al cliente del despacho, y webhook para el bot.
`enviar_texto`, `enviar_documento`, `enviar_plantilla`, `verificar_firma_webhook`,
`parsear_webhook`.

**Variables.** `FISCALITO_WHATSAPP` = `falso` | `meta` | `twilio`.
- meta (WhatsApp Cloud API): `FISCALITO_WHATSAPP_TOKEN`, `FISCALITO_WHATSAPP_PHONE_ID`,
  `FISCALITO_WHATSAPP_APP_SECRET` (firma `X-Hub-Signature-256`),
  `FISCALITO_WHATSAPP_VERSION` (default `v20.0`).
- twilio: `FISCALITO_TWILIO_ACCOUNT_SID`, `FISCALITO_TWILIO_AUTH_TOKEN`,
  `FISCALITO_TWILIO_WHATSAPP_FROM` (`+1415...`). En Twilio, la "plantilla" es un Content SID
  (`HX...`).

**Cómo probar.** El falso guarda en `.enviados` y firma con HMAC como Meta. Reales:
`test_whatsapp_*` (incluye verificación de firma de ambos).

**A quién contratar.** Meta directo (cuenta de negocio verificada, número y plantillas
aprobadas) o Twilio/360dialog como intermediario (EXT-07). Mensajes fuera de la ventana de
24 h sólo con plantilla aprobada.

**Bot del despacho (P5-06).** Webhook público `POST /api/v1/whatsapp/webhook` (firma del
proveedor) y `GET` del mismo path para la verificación de Meta con
`FISCALITO_WHATSAPP_VERIFY_TOKEN` (el "Verify token" que se pega en la consola de Meta; sin
él, la verificación responde 403). `FISCALITO_WHATSAPP_BOT_POR_MINUTO` (default 6): mensajes
por minuto por número. Los documentos se bajan de un enlace firmado con
`FISCALITO_ENLACES_SECRETO` y `FISCALITO_URL_PUBLICA_API` (las mismas de P4-13). Twilio firma
sobre la URL pública: con `FISCALITO_URL_PUBLICA_API` puesta, el webhook la usa para verificar.
Respuestas dentro de la ventana de 24 h que abre el cliente: texto y documento libres, sin
plantilla.

**Recibos de nómina (P4-13).** `enviar_plantilla(..., documento=DocumentoPlantilla(url,
nombre))`: en Meta el documento va como `header` de tipo `document` (la plantilla aprobada debe
tener encabezado DOCUMENT y tres variables de cuerpo: nombre, periodo, neto). En Twilio la URL
va como la variable siguiente de `ContentVariables` (POR CONFIRMAR contra la plantilla de
Content API). Meta baja el PDF de una URL pública firmada:
- `FISCALITO_URL_PUBLICA_API` — URL con la que Meta/Twilio llegan a esta API (default
  `http://localhost:8000`, que no sirve fuera de desarrollo).
- `FISCALITO_ENLACES_SECRETO` — secreto HMAC de los enlaces de descarga. **Obligatorio en
  producción** (sin él, 503); en desarrollo hay uno fijo.

---

## Pagos de suscripción

**Qué es.** Cobro mensual al despacho. `crear_cliente`, `crear_suscripcion`, `cancelar`,
`portal_url`, `parsear_webhook` (verifica firma; 400 si no cuadra).

**Variables.** `FISCALITO_PAGOS` = `falso` | `stripe` | `mercadopago`.
- stripe: `FISCALITO_STRIPE_API_KEY` (`sk_...`), `FISCALITO_STRIPE_WEBHOOK_SECRET`
  (`whsec_...`). El `plan` es el id del Price.
- mercadopago: `FISCALITO_MERCADOPAGO_ACCESS_TOKEN`, `FISCALITO_MERCADOPAGO_WEBHOOK_SECRET`.
  El `plan` es el `preapproval_plan_id` y el `cliente_id` de `crear_suscripcion` es el correo
  del pagador. Mercado Pago no tiene portal de cliente: `portal_url` manda a su página de
  suscripciones.

**Cómo probar.** Falso en memoria. Reales: `test_pagos_*` (incluye firma vencida de Stripe).

**A quién contratar.** Stripe (México soportado) o Mercado Pago; Conekta sería un tercer
adaptador (EXT-11).

---

## Monitoreo

**Qué es.** Errores de producción. `capturar_error(error, contexto)`,
`capturar_mensaje(mensaje, nivel, contexto)`.

**Variables.** `FISCALITO_MONITOREO` = `falso` | `log` | `sentry`.
- sentry: `FISCALITO_SENTRY_DSN`. **`sentry-sdk` no es dependencia del proyecto**: para usarlo,
  `pip install sentry-sdk` y agrégalo a `apps/api/pyproject.toml`. Sin el paquete, la app
  responde 503 explicando eso. Se inicializa con `send_default_pii=False`.
- log: no necesita nada; usa el logger `fiscalito.monitoreo` (lo recogen Railway/Cloud Run).

**Cómo probar.** `test_monitoreo_*` (Sentry con un SDK inyectado, sin red).

**A quién contratar.** Sentry (plan gratuito alcanza al inicio) — EXT-12.

---

## LLM

**Qué es.** Explicaciones y bot de WhatsApp. **Nunca calcula impuestos.**
`completar(mensajes, herramientas=None) -> RespuestaLLM(texto, llamadas, modelo, tokens_*)`.

**Variables.** `FISCALITO_LLM` = `falso` | `openai` | `anthropic`. Reusa las de
`app/services/llm_service.py`: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`),
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-haiku-4-5-20251001`).
`llm_service.py` (explicaciones de declaraciones) sigue funcionando igual con `LLM_PROVIDER`.

**Cómo probar.** El falso responde `[falso] <mensaje>` o pide la primera herramienta. Reales:
`test_llm_*` con respuestas grabadas (hablan REST con httpx, no con los SDK).

**A quién contratar.** OpenAI o Anthropic; la llave sólo en el servidor, con tope de gasto en la
consola del proveedor (EXT-09).

**Herramientas (P5-07).** El adaptador habla también el loop de herramientas en forma neutral
(`{"role": "assistant", "llamadas": [...]}` y `{"role": "herramienta", "id", "nombre",
"content"}`), que cada real traduce: OpenAI a `tool_calls` / `role: tool`; Anthropic a
`tool_use` / `tool_result` (los resultados consecutivos en UN mensaje `user`). Los nombres de
propiedad de los esquemas van sin `ñ` (Anthropic los rechaza): `anio`, no `año`.

**Límites propios (P0-02).** Además del tope del proveedor, la API corta antes:
`FISCALITO_RATE_LIMIT_LLM_POR_MINUTO` (default 20, por usuario) y
`FISCALITO_TOPE_LLM_DIARIO_LLAMADAS` (default 500, por despacho y día de la CDMX, contado en la
tabla `consumo_llm`). Los dos responden 429 con `Retry-After`. Ver `docs/api-contract.md`,
"Autenticación, límites y tope de LLM".

---

## Voz del asistente (`voz`) — P5-07

**Qué es.** Voz a texto (`transcribir(audio, mime) -> str`, Whisper `whisper-1`, español) y
texto a voz (`sintetizar(texto) -> bytes`, `tts-1` voz `nova`, MP3) del asistente del despacho.
Sustituye las llamadas que el navegador hacía con una llave en el bundle (S-00): **el front ya
no tiene ninguna llave de LLM** (`apps/store/src/sinLlavesLLM.test.ts`).

**Variables.** `FISCALITO_VOZ` = `falso` | `openai`. La real usa `OPENAI_API_KEY` (la misma
del LLM, sólo en el servidor). Sin llave → 503.

**Cómo probar.** El falso devuelve `[falso] audio de N bytes` y un MP3 mínimo; guarda lo
recibido. Real: `test_voz_openai_whisper_y_tts` con `httpx.MockTransport`.

**A quién contratar.** OpenAI (EXT-09, la misma cuenta del LLM). Cada transcripción y cada
síntesis cuenta contra el tope diario de LLM del despacho.

---

## Almacenamiento de archivos (`almacenamiento`) — P0-03

**Qué es.** Donde viven los XML originales de la bóveda de CFDI (y, más adelante, PDF y papeles
de trabajo). La app guarda, lee, borra y pregunta si existe por **ruta relativa**
(`cfdi/<despacho>/<cliente_id>/<UUID>.xml`); la base de datos sólo guarda la ruta y el SHA-256.
Ninguna implementación acepta rutas absolutas ni con `..`.

| Variable | Valores | Default | Para qué |
|---|---|---|---|
| `FISCALITO_ALMACENAMIENTO` | `falso`, `local`, `s3` | `falso` (dev) | Elige la implementación |
| `FISCALITO_ALMACEN_DIR` | ruta | `./almacen` | Carpeta raíz de `falso`/`local` |
| `FISCALITO_S3_BUCKET` | nombre | — (**obligatoria** con `s3`) | Bucket |
| `FISCALITO_S3_ENDPOINT` | URL | — (AWS) | Endpoint S3 compatible. R2: `https://<cuenta>.r2.cloudflarestorage.com` |
| `FISCALITO_S3_REGION` | texto | `auto` | Región (`auto` en R2) |
| `FISCALITO_S3_ACCESS_KEY` | llave | — | Access key ID |
| `FISCALITO_S3_SECRET_KEY` | secreto | — | Secret access key |
| `FISCALITO_S3_PREFIJO` | texto | vacío | Prefijo dentro del bucket (p. ej. `prod`) |

- **`falso` y `local` son la misma clase (disco).** `falso` no es memoria a propósito: el
  SQLite de desarrollo sobrevive reinicios y el almacén también tiene que hacerlo, o la base
  diría que un XML existe que ya se perdió. `almacen/` está en `.gitignore`.
- **`s3`** usa boto3 y sirve para AWS S3, Cloudflare R2 o MinIO. Sin `FISCALITO_S3_BUCKET`
  responde 503 con el nombre de la variable que falta.

**Cómo se prueba.** `apps/api/tests/plan_p/test_almacenamiento.py`: disco en `tmp_path`, una
implementación en memoria para pruebas de dominio, y S3 con un cliente boto3 real envuelto en
`botocore.stub.Stubber` que verifica cada llamada (`put_object`, `get_object`, `head_object`,
`delete_object`, errores 404/403) **sin red**.

**A quién contratar.** Recomendado: **Cloudflare R2** (sin costo de egreso, 10 GB gratis al
mes). Crear un bucket privado, un token de API con permiso de lectura y escritura sólo sobre
ese bucket, y pegar las cinco variables `FISCALITO_S3_*` en Railway. Alternativa: AWS S3 con un
usuario IAM limitado al bucket.

## Descarga masiva del SAT

**Qué es.** El *Servicio Web de Descarga Masiva de CFDI y Retenciones* del SAT (versión 1.5,
2025-05-30): baja los XML y la metadata emitidos y recibidos de un RFC autenticándose con SU
e.firma. Implementación propia (sin librería externa) en `apps/api/app/integraciones/`:
`sat_soap.py` (arma y lee los mensajes SOAP y firma XMLDSig) y `sat_descarga.py` (transporte,
token). La lógica de reintentos, espera y bóveda vive en `apps/api/app/sat_descarga/`.

Cuatro operaciones: **Autentica** (WS-Security con el Timestamp firmado → token, ≈5 min) →
**SolicitaDescargaEmitidos/Recibidos** (→ IdSolicitud) → **VerificaSolicitudDescarga** (cada
2, 4, 8… min con techo de 2 h; el SAT tarda de minutos a días) → **Descargar** (cada paquete,
un ZIP en base64 de hasta 200,000 XML, que se decodifica a disco en trozos y entra a la bóveda
por streaming). Se firma con `app.credenciales.obtener_firmante(db, cliente, "efirma")`.

| Variable | Valores | Default | Para qué |
|---|---|---|---|
| `FISCALITO_SAT_DESCARGA` | `falso`, `sat` | `falso` fuera de producción | Elige la implementación |
| `FISCALITO_SAT_DIAS_MAX_ESPERA` | entero | `7` | Días que se espera una solicitud "en proceso" antes de darla por fallida |
| `FISCALITO_SAT_HORAS_AVISO` | entero | `24` | Horas en proceso a partir de las cuales queda una alerta "atorada" |
| `FISCALITO_SAT_URL_AUTENTICACION` | URL | producción del SAT | Sólo para apuntar a otro ambiente |
| `FISCALITO_SAT_URL_SOLICITUD` | URL | producción del SAT | ídem |
| `FISCALITO_SAT_URL_VERIFICACION` | URL | producción del SAT | ídem |
| `FISCALITO_SAT_URL_DESCARGA` | URL | producción del SAT | ídem |

URLs de producción por default (`*.clouda.sat.gob.mx`, las del servicio 1.5):
`cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc`,
`…/SolicitaDescargaService.svc`, `…/VerificaSolicitudDescargaService.svc` y
`cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc`.

**Reglas del SAT que el código respeta** (y dónde): el SAT permite **dos solicitudes de por
vida con los mismos parámetros** (5002) → cada solicitud tiene una huella única y no se repite;
sólo se re-solicita si el SAT la perdió (5004 en verificación, vencida) y nunca más de dos
veces. 5005 (ya hay una igual vigente) → espera con backoff de horas. 5003 (tope) → el rango se
parte en dos y así sucesivamente. 404/5006 → reintento con backoff. 300–305/5001 → falla con
mensaje en español (e.firma revocada, de otro RFC, etc.). Paquetes: viven 72 h y se bajan a lo
más dos veces (5007/5008) → cada paquete importado queda registrado y no se vuelve a pedir.
Desde la 1.5: la fecha inicial debe ser menor que la final, no más de seis años atrás, y los
**XML recibidos sólo vigentes** (los cancelados recibidos se ven en la metadata).

**Cómo se prueba.** Sin red: `tests/plan_p/test_sat_soap.py` verifica la firma de cada sobre
con lxml (exc-c14n) y la llave PÚBLICA del certificado de prueba, y compara los `DigestValue`
contra los que phpcfdi/sat-ws-descarga-masiva obtuvo para los mismos parámetros.
`tests/plan_p/test_sat_descarga.py` corre el ciclo completo contra un SAT simulado
(`httpx.MockTransport` + respuestas grabadas en `tests/fixtures/sat_descarga/`): mes completo
a la bóveda, solicitud atorada ~30 h, token vencido y rechazado, duplicados, códigos de error,
tope 5003, worker que muere a media descarga. `test_sat_sincronizacion.py` cubre la diaria, la
bitácora y las rutas.

**Por confirmar con una e.firma real** (no se puede sin red ni credencial de verdad): que el
SAT acepte la firma (los sobres son byte por byte los de phpcfdi, que sí opera en producción,
pero no se ha mandado uno desde aquí); la duración real del token; el texto exacto del Fault
con token vencido (se detecta por HTTP 401/403 o "security"/"token" en el Fault); y si
`Descargar` responde 200 con `CodEstatus` de error o un HTTP de error.

**A quién contratar.** Nadie: el servicio es gratuito. Requisito: la e.firma vigente de cada
cliente cargada en su ficha (P0-05). Sin ella la descarga diaria de ese cliente se pausa y deja
una alerta `sin_efirma`.

## Estatus de CFDI (`sat_estatus`) — P1-03

**Qué es.** El web service **público** del SAT `ConsultaCFDIService` (el de "Verificación de
CFDI"): dice si un CFDI está Vigente, Cancelado o No encontrado, si es cancelable, si hay una
cancelación "En proceso" y si el emisor está en la lista de EFOS. No pide e.firma ni contrato.
Código: `apps/api/app/integraciones/sat_estatus.py` (adaptador) y
`apps/api/app/sat_verificacion/estatus.py` (lotes y escritura en la bóveda).

- SOAP 1.1, `POST https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc`,
  `SOAPAction: http://tempuri.org/IConsultaCFDIService/Consulta`, cuerpo
  `<Consulta xmlns="http://tempuri.org/"><expresionImpresa>?re=…&rr=…&tt=…&id=…`.
- `tt` (CFDI 3.3/4.0): seis decimales sin ceros sobrantes (`1160.00` → `1160.0`).
- Respuesta `ConsultaResult`: `CodigoEstatus` ("S - …" encontrado / "N - 60x …"), `Estado`,
  `EsCancelable`, `EstatusCancelacion`, `ValidacionEFOS` (200/201 = el emisor NO es EFOS).

| Variable | Valores | Default | Para qué |
|---|---|---|---|
| `FISCALITO_SAT_ESTATUS` | `falso`, `sat` | `falso` (dev) | Elige la implementación |
| `FISCALITO_SAT_ESTATUS_URL` | URL | la de producción del SAT | Otro endpoint (p. ej. el de pruebas `https://pruebacfdiconsultaqr.cloudapp.net/ConsultaCFDIService.svc`) |
| `FISCALITO_SAT_ESTATUS_CONCURRENCIA` | entero | 4 | Consultas simultáneas por trabajo |
| `FISCALITO_SAT_ESTATUS_POR_SEGUNDO` | número | 5 | Ritmo máximo (el SAT bloquea ráfagas; no publica límite) |
| `FISCALITO_SAT_ESTATUS_LOTE` | entero | 1000 | CFDI por trabajo antes de encolar la continuación |

**Qué hace la app.** `POST /sat/clientes/{clave}/verificar-estatus` y la programación (diaria
los del mes, semanal los del último año, sólo no cancelados) encolan `sat.verificar_estatus`.
Un CFDI cancelado se marca `estatus_sat = cancelado` y deja de contar:
`app.boveda_cfdi.servicio.comprobantes_vigentes(consulta)` es el filtro para Fiscalito,
Contabilito y la anual (P1-06). "No encontrado" NO cambia el estatus.

**Fuentes verificadas (2026-10-19).** README y código de
[phpcfdi/sat-estado-cfdi](https://github.com/phpcfdi/sat-estado-cfdi) (URL, SOAPAction,
namespaces, sobre, respuesta grabada y tabla de estados; enlaza el documento del SAT v1.4 de
nov-2022) y `pacs/sat.py::status` de
[SAT-CFDI/python-satcfdi](https://github.com/SAT-CFDI/python-satcfdi) (mismo contrato); formato
de `tt` de [phpcfdi/cfdi-expresiones](https://github.com/phpcfdi/cfdi-expresiones).

**Por confirmar con el servicio real.** El sandbox de desarrollo no resuelve `sat.gob.mx`:
nunca se mandó una consulta real. Al encender `sat` en Railway, verificar un UUID conocido y
ajustar `FISCALITO_SAT_ESTATUS_POR_SEGUNDO` si el SAT responde con errores de ritmo.

**Cómo se prueba.** `apps/api/tests/plan_p/test_sat_estatus.py` con `httpx.MockTransport` y
respuestas grabadas en `apps/api/tests/fixtures/sat_estatus/` (vigente, cancelado, no
encontrado, en proceso, Fault).

**A quién contratar.** Nadie: es público y gratuito.

## Listas 69-B (EFOS/EDOS) y 69 (`sat_listas`) — P1-04

**Qué es.** Los listados públicos del SAT en "Datos abiertos": el **69-B** (operaciones
inexistentes: presuntos, definitivos, desvirtuados, sentencias favorables, en un solo CSV) y
los del **69** (no localizados, créditos firmes, exigibles, cancelados, sentencias). Se
descargan a diario (`sat.listas_actualizar`, 6:30 Ciudad de México), se guardan en
`contribuyentes_lista_sat` y se cruzan con las contrapartes de cada cliente: emisores de sus
CFDI recibidos (riesgo EDOS: rojo si definitivo o presunto), receptores de sus emitidos
(informativo) y su propio RFC. Cada hallazgo nuevo es una `AlertaRiesgo`.

| Variable | Valores | Default | Para qué |
|---|---|---|---|
| `FISCALITO_SAT_LISTAS` | `falso`, `sat` | `falso` (dev) | Elige la implementación |
| `FISCALITO_SAT_LISTAS_ACTIVAS` | lista separada por comas | `69b` | Qué listas descargar (`69b`, `69_no_localizados`, `69_firmes`, `69_exigibles`, `69_cancelados`, `69_sentencias`) |
| `FISCALITO_SAT_LISTA_<LISTA>_URL` | URL | ver abajo | URL vigente de cada lista (p. ej. `FISCALITO_SAT_LISTA_69B_URL`) |

URL por default del 69-B: `http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv`
(es la que citan los scrapers públicos, p. ej. Apify `scrapers_lat/sat-69b-scraper`). **Las URL
del art. 69 son POR CONFIRMAR** (nombres de archivo no verificados): por eso no están activas
por default. Si el SAT responde HTML en vez de CSV, la carga falla diciendo qué variable
corregir.

**Parseo robusto.** UTF-8 con o sin BOM, si no cp1252/latin-1; renglones de título antes del
encabezado; delimitador `,`, `;`, `|` o tabulador deducido del encabezado; columnas reconocidas
por palabra clave sin acentos; RFC normalizado y renglones sin RFC válido descartados. Un
archivo con menos del 50 % de los renglones de la carga anterior **no reemplaza** (parece
truncado) y queda el error en `GET /sat/listas/estado`.

**Cómo se prueba.** `apps/api/tests/plan_p/test_sat_listas.py` con un CSV sintético latin-1 en
`apps/api/tests/fixtures/sat_listas/` (RFC inventados).

**A quién contratar.** Nadie: son datos públicos. Antes de producción, abrir el portal de datos
abiertos del SAT y confirmar las URL vigentes.

## Opinión de cumplimiento y constancia (`opinion_cumplimiento`) — P1-05 (DP-2)

**Qué es.** La opinión del cumplimiento de obligaciones fiscales (32-D) y la constancia de
situación fiscal de cada cliente, con historial, PDF en el almacenamiento y semáforo para la
cartera. **El SAT no tiene API oficial**; hay cuatro vías y la elección es de Ricardo (DP-2).
En TODAS se puede subir el PDF a mano (`POST /sat/clientes/{clave}/opinion/pdf`).

| Vía (`FISCALITO_OPINION_CUMPLIMIENTO`) | Qué hace | Riesgo |
|---|---|---|
| `falso` (dev) | PDF sintético positivo; pasa por el mismo lector que uno real | — |
| `portal_sat` | Entra al portal del SAT con la **e.firma del cliente** (`obtener_firmante`) y descarga el PDF | Zona gris; frágil ante cambios del portal |
| `proveedor` | Cliente HTTP genérico contra un proveedor externo | Costo por consulta |
| `manual` | No consulta nada; "Obtener ahora" responde 409 | Trabajo manual del despacho |

**`portal_sat`.** Flujo tomado de `satcfdi/portal/__init__.py` de
[python-satcfdi](https://github.com/SAT-CFDI/python-satcfdi) (MIT): login FIEL en
`loginda.siat.sat.gob.mx` con el formulario `certform` y un token
`base64(base64("guid|rfc|serie") + "#" + base64(base64(firma SHA1withRSA)))`; 32-D en
`ptsc32d.clouda.sat.gob.mx` (`RespuestaCompleta/ObtenerRespuestaCompletaPdf`, JSON con
`ContenidoBase64`); constancia en `rfcampc.siat.sat.gob.mx` (`IdcGeneraConstancia.jsf`).
**Cada paso lleva `# POR CONFIRMAR CON E.FIRMA REAL:`** en el código: se probó contra páginas
simuladas, nunca contra el SAT. Si el portal cambia, el error dice en qué paso
("El portal del SAT cambió en el paso 'login e.firma'…") y sugiere subir el PDF.

**`proveedor`.** Todas `FISCALITO_OPINION_PROVEEDOR_*`:

| Variable | Default | Para qué |
|---|---|---|
| `URL` | — (obligatoria) | Con `{rfc}` y `{tipo}` (`opinion`/`constancia`) |
| `API_KEY` | — (obligatoria) | Credencial |
| `ENCABEZADO` | `Authorization` | Con `Authorization` va `Bearer <key>`; con otro, la key sola |
| `METODO` | `GET` | `POST` manda `{"rfc","tipo"}` en JSON |
| `CAMPOS` | `{"pdf_base64":"pdf","resultado":"resultado","folio":"folio","fecha":"fecha"}` | JSON: ruta con puntos de cada dato en la respuesta |
| `RESULTADOS` | `{}` | JSON: valor del proveedor → `positiva`/`negativa`/`sin_obligaciones` |

Si el proveedor responde `application/pdf`, el cuerpo es el PDF y el sentido se lee del texto.

**Otras variables.** `FISCALITO_OPINION_DIAS_VIGENCIA` (default 30): días tras los cuales una
opinión positiva pasa a amarillo. **FUENTE POR CONFIRMAR**: regla 2.1.37 de la RMF (vigencia
de 30 días naturales), no contrastada con la RMF 2026.

**Lectura del PDF.** `pypdf` (dependencia nueva) extrae el texto y se buscan las frases "sentido
POSITIVO/NEGATIVO" e "INSCRITO SIN OBLIGACIONES", el folio y la fecha de revisión. **Por
confirmar con un PDF real**; si una opinión real sale "desconocido", el despacho puede indicar
el resultado al subirla y hay que agregar la frase a `app/sat_verificacion/pdf.py`.

**Programación.** Diario a las 7:00 se revisa qué clientes toca: por default cada cliente con
RFC pide su opinión (y constancia) el día 1 de cada mes; se cambia por cliente con
`PUT /sat/clientes/{clave}/opinion/config`.

**Cómo se prueba.** `apps/api/tests/plan_p/test_opinion_cumplimiento.py`: falso, proveedor con
`MockTransport`, portal con páginas simuladas y una e.firma de prueba, manual y rutas.

**A quién contratar.** Depende de DP-2. Si es `proveedor`, alguien que entregue la 32-D por API
con la autorización del contribuyente; con `portal_sat`, nadie, pero cada cliente necesita su
e.firma vigente cargada.

## Buzón SAT — envío de contabilidad electrónica (`buzon_sat`) — P2-07

**Qué es.** El envío de los XML del Anexo 24 (catálogo, balanza, pólizas, auxiliares) al SAT.
**El SAT no publica una API para esto**: se sube en el portal (Contabilidad electrónica →
Envío de archivos) firmando con la e.firma del contribuyente. Hoy Fiscalito genera, valida
contra el XSD oficial, sella (opcional) y empaqueta el ZIP con el nombre que pide el SAT; la
pantalla muestra cómo subirlo. Ver `apps/api/app/integraciones/buzon_sat.py`.

**Variables.** `FISCALITO_BUZON_SAT` = `falso` (default fuera de producción) | `portal_sat`.

- `falso`: sin red; valida el nombre del ZIP y devuelve un acuse sintético `FALSO-…` que dice
  que no se envió nada.
- `portal_sat`: **POR CONFIRMAR CON E.FIRMA REAL.** Preparado para automatizar el portal con
  la e.firma del cliente (`obtener_firmante`), como `opinion_cumplimiento.portal_sat`. El
  flujo de carga no está documentado; hoy responde 501 y no sale ningún request.

**Cómo se prueba.** `tests/plan_p/test_anexo24.py` (falso determinístico, portal 501, ruta
`/enviar`).

**A quién contratar.** A nadie hoy. Si se automatiza: validar el flujo con una e.firma real
de un cliente que lo autorice.

## PAC — timbrado y cancelación (`pac`) — P3-04

**Qué es.** Proveedor Autorizado de Certificación. `app/integraciones/pac.py`, contrato
genérico que reusarán nómina (P4) y facturación:
`timbrar(xml_sellado, tipo="cfdi"|"retenciones") -> Timbre(xml_timbrado, uuid, fecha)`,
`cancelar(uuid, rfc, motivo, folio_sustitucion, *, tipo, firmante)` y
`consultar_estatus(uuid, rfc, *, tipo)`. **Fiscalito sella** con el CSD del cliente
(`obtener_firmante(db, cliente, "csd")`, SHA256withRSA sobre la cadena original del XSLT
oficial) y valida contra el XSD antes de mandar nada; el PAC sólo certifica.

**Variables.** `FISCALITO_PAC` = `falso` | `finkok` | `sw_sapien` | `facturama`.
- falso: sin variables. Inserta un `TimbreFiscalDigital` 1.1 **sintético** (UUID aleatorio,
  `NoCertificadoSAT` en ceros, `Leyenda` "NO FISCAL") que valida contra su XSD. **Sin validez
  ante el SAT**: el PDF lo dice en rojo y el registro guarda `es_prueba=true`.
- finkok (SOAP): `FISCALITO_FINKOK_USUARIO`, `FISCALITO_FINKOK_PASSWORD`,
  `FISCALITO_FINKOK_URL` (default `https://demo-facturacion.finkok.com`; producción
  `https://facturacion.finkok.com`). Cancela con `cancel_signature` (solicitud firmada con el
  CSD del cliente).
- sw_sapien (REST): `FISCALITO_SW_TOKEN` (token de larga duración) o `FISCALITO_SW_USUARIO` +
  `FISCALITO_SW_PASSWORD`; `FISCALITO_SW_URL` (default `https://services.test.sw.com.mx`).
  Cancela por UUID con el CSD cargado en la cuenta de SW.
- facturama (REST): `FISCALITO_FACTURAMA_USUARIO`, `FISCALITO_FACTURAMA_PASSWORD`,
  `FISCALITO_FACTURAMA_URL` (default `https://apisandbox.facturama.mx`). Facturama **no recibe
  XML sellado**: sella con el CSD que el despacho sube a su cuenta Multiemisor; el adaptador
  traduce el XML de retenciones al JSON de `POST /2/retenciones`. Para CFDI de ingreso/nómina
  responde 501 hasta que exista el mapeo completo.

**Cómo probar.** `pytest tests/plan_p/test_retenciones_cfdi.py`. Las reales se prueban con
`httpx.MockTransport` y respuestas en `apps/api/tests/fixtures/pac/` **construidas desde la
documentación pública** (wiki.finkok.com, developers.sw.com.mx, facturama.mx/api/cfdi-retenciones
y la implementación MIT de `satcfdi` 26.10.1), no capturadas de un sandbox. Lo que no se pudo
verificar sin cuenta de pruebas está marcado `POR CONFIRMAR CON CUENTA DE PRUEBAS` en el código:
servicio y namespace de retenciones de Finkok (`retentions.wsdl`), rutas de retenciones de SW
(`retencion/stamp/v3`, `retencion/cancel`) y de Facturama (descarga y cancelación por Id),
algoritmo de firma de la solicitud de cancelación (exc-c14n/rsa-sha1) y namespace de la
cancelación de retenciones.

**A quién contratar.** Cualquiera de los tres con sandbox (EXT-04, DP-4). Finkok y SW timbran
XML presellado (encaja con el diseño); Facturama obliga a subirle el CSD de cada cliente.

## Límite de peticiones (`limitador`) — P0-02

**Qué es.** Ventana deslizante de 60 s por usuario (y por token de checador) delante de todo
`/api/v1`. No es un servicio externo HOY: vive en la memoria del proceso. Se documenta aquí
porque el día que haya más de una réplica pasa a serlo (Redis o la base).

**Variables.** `FISCALITO_RATE_LIMIT_POR_MINUTO` (default 120). `FISCALITO_LIMITADOR` =
`memoria` (única implementación; elegir otra cosa revienta al arrancar el primer request).

**Cómo probar.** `apps/api/tests/plan_p/test_acceso.py` (`TestLimites`, `TestVentanaDeslizante`).

**A quién contratar.** Nadie mientras haya un solo proceso. Con varias réplicas: Redis administrado
(Railway, Upstash) e implementar `Limitador` en `app/acceso/limitador.py`.
