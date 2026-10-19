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
| Almacenamiento | `FISCALITO_ALMACENAMIENTO` | — | otra tarea |
| Descarga masiva SAT | `FISCALITO_SAT_DESCARGA` | — | P1 |
| Estatus de CFDI | `FISCALITO_SAT_ESTATUS` | — | P1 |
| Listas 69-B | `FISCALITO_LISTAS_69B` | — | P1 |
| Opinión de cumplimiento | `FISCALITO_OPINION` | — | P1-05 |
| PAC | `FISCALITO_PAC` | — | P4 |

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

*Pendiente (P1-01).* Servicio público del SAT; no hay contrato. Se firma con la e.firma del
cliente vía `app.credenciales.obtener_firmante(db, cliente, "efirma")`. Variable prevista:
`FISCALITO_SAT_DESCARGA`.

## Estatus de CFDI

*Pendiente (P1).* Web service público del SAT (consulta de estatus y cancelabilidad). Variable
prevista: `FISCALITO_SAT_ESTATUS`.

## Listas 69-B (EFOS/EDOS)

*Pendiente (P1).* Archivos públicos del SAT. Variable prevista: `FISCALITO_LISTAS_69B`.

## Opinión de cumplimiento

*Pendiente (P1-05, DP-2).* Sin API oficial: proveedor de terceros, portal con e.firma o PDF que
sube el despacho. Variable prevista: `FISCALITO_OPINION`.

## PAC (timbrado y cancelación)

*Pendiente (P4).* Timbra con el CSD del cliente (`obtener_firmante(db, cliente, "csd")`).
Variable prevista: `FISCALITO_PAC`. Se elige proveedor en EXT-04 (DP-4).
