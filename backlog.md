# BACKLOG — Fiscalito (prioridad: Nómina)

Reglas: una tarea = una rama = un PR. `[x]` solo tras merge a main confirmado por
Ricardo. Cada tarea tiene su "Listo cuando" — el plan y el revisor se miden contra eso.
El detalle de dominio (valores 2026, fórmulas, fuentes) está en `docs/PLAN_NOMINA.md`.

## Cola nocturna

Orden exacto que toma el **modo autonomo** (ver `CLAUDE.md`): la primera que no este
`[x]` ni marcada SALTADA en `docs/nocturno-log.md`. Una tarea por sesion. El detalle de
cada una vive en su seccion de abajo. **S-00 no esta aqui a proposito:** su criterio de
cierre exige probar el chat de voz con microfono, asi que es diurna.

**CAMBIO DE PRIORIDAD (2026-09-01, demo del 2026-09-02): la Épica E va al frente.**
D-04…D-07 ya están cerradas; S-03 y lo que sigue quedan en pausa hasta que E-04 cierre.

1. E-01
2. E-02
3. E-03
4. E-04
5. S-03
6. F1-07
7. F1-08
8. F1-06
9. S-02
10. S-01b

**D-08 no está en la cola**, igual que S-00: necesita el checador físico enfrente, así que es
diurna. F0-01, F0-02, F1-01…F1-05 y D-04…D-07 ya están cerradas.

## E — Épica de despacho (para la demo del 2026-09-02)

**El porqué.** Nómina quedó como una pestaña dentro de la app del CONTRIBUYENTE, pero el
producto es para un CONTADOR que lleva la nómina de varios clientes. **No se crea
`apps/despacho`** (PLAN_NOMINA §0 lo proponía; no cabe antes de la demo): se adapta
`apps/store`, que ya tiene auth, tema, PDF y componentes. Prioridad sobre todo lo demás.

- [x] **E-01 · Perfil de contador** — tipo "Despacho / Contador" en `OnboardingWizard` y
  `ProfileContext`, con sus campos (nombre del despacho, RFC). `getTabsForProfile`: si es
  contador, el sidebar muestra **Clientes / Nómina / Calendario / Perfil** y OCULTA los tabs
  de contribuyente — **no se borran, solo no se muestran**. *Listo cuando:* creo cuenta como
  contador y veo el sidebar correcto.
- [x] **E-02 · Clientes** — Backend: `GET /api/v1/despacho/clientes` y `/clientes/{id}` con 3
  clientes demo — uno es el de las fixtures S-04 con sus 9 empleados, dos sintéticos con
  distinto giro y número de empleados. Front: pantalla de lista + selector de cliente activo
  en el header, y ficha `/clientes/:id` con sus empleados (SBC, salario diario, alta, factor).
  *Listo cuando:* cambio de cliente y todo lo demás cambia con él.
- [x] **E-03 · Nómina dentro del cliente** — mover el flujo de `/app/nomina-demo` al contexto
  del cliente seleccionado: checador en vivo, cerrar quincena, calcular nómina, cuotas por
  ramo, PDF. **Mismo motor, misma API.** *Listo cuando:* el flujo completo corre para el
  cliente de fixtures y para uno sintético.
- [x] **E-04 · Pulido visual** — los inputs de fecha y los botones de la pantalla actual se ven
  crudos: jerarquía tipográfica, espaciado, estados de carga y vacío, tabla de recibos
  legible. *Listo cuando:* se proyecta en pantalla grande sin verse a medio hacer.

**Segunda tanda (2026-09-02, MODO RÁPIDO autorizado por Ricardo):** E-06 → E-07 → E-05, las tres
en una rama, un plan, un revisor de plan, un revisor de entregable y un PR. El motor de E-07
llevó **revisor aparte**, que es la excepción que Ricardo dejó en pie.

- [x] **E-05 · Onboarding y perfil del despacho** — cuando el tipo es "Despacho / Contador", el
  wizard pide SOLO: nombre del contador, nombre del despacho y teléfono. Nada de RFC, régimen
  fiscal, actividad económica ni código postal — esos son del contribuyente y a un despacho no le
  calculamos su declaración. En Perfil, si el tipo es despacho, no mostrar el selector de los
  otros 5 tipos de cuenta. *Listo cuando:* creo cuenta de despacho y sólo me piden esos tres
  datos, y en Perfil no hay dónde cambiarme de tipo.
- [x] **E-06 · La pantalla de nómina se explica sola** — convertir el flujo en 4 pasos numerados y
  visibles ("1. Checadas recibidas · 2. Cerrar quincena · 3. Calcular nómina · 4. Exportar"), cada
  uno con una línea de qué hace. Los pasos 2-4 se habilitan en orden. Además: en la nómina de un
  cliente, el sidebar y el título dejan claro en qué cliente estoy, y **"Nómina" queda resaltado,
  no "Clientes"**. *Listo cuando:* se proyecta y se entiende el orden sin que nadie lo explique.
- [x] **E-07 · Calendario patronal** — "Calendario" mostraba declaraciones ISR+IVA del
  contribuyente, que no aplican a un despacho de nómina. Se conecta al calendario laboral de
  F1-06: obligaciones patronales por cliente (entero mensual IMSS día 17, bimestral
  RCV/Infonavit, avisos de variables), agrupadas por fecha con el nombre del cliente, con
  endpoint nuevo. *Listo cuando:* el contador abre Calendario y ve vencimientos patronales de sus
  clientes, no sus propias declaraciones.

## S — Saneamiento (deuda que estorba al bucle)

- [x] **S-01 · Lint backend a cero y al CI** — `ruff check --fix` (43 auto) + limpiar el
  resto (111 total: E501, I001, F401, F541). Descomentar el paso `ruff check .` en
  `ci.yml`. *Listo cuando:* `ruff check .` sale limpio en local y corre en CI.
- [ ] **S-00 · Sacar la API key de OpenAI del frontend (SEGURIDAD — bloquea todo lo demas)**
  — `VITE_OPENAI_API_KEY` se inyecta en el bundle de Vite y viaja al navegador. Verificado
  el 2026-08-31: la key (prefijo `sk-proj-`) esta en texto plano en el bundle **en vivo**
  de `https://fiscalito-mvp.web.app/assets/index-DQ99Y4ao.js`, deployado el 2026-04-09 y
  servido con `Cache-Control: immutable`. El historial de git esta limpio (nunca se
  commiteo una key real): la fuga es solo por bundle y runtime.
  **Qué se mueve del front al back:** las 4 llamadas de
  `apps/store/src/services/voiceChatService.ts` a `api.openai.com` — `transcribeAudio`
  (Whisper), `sendMessage` (legacy, se elimina), `sendMessageWithTools` (gpt-4o-mini con
  tools) y `speakText` (tts-1 "nova"). El loop agentico (`src/agent/agentLoop.ts` +
  `tools.ts`) SE QUEDA en el cliente: sus tools operan el router y el estado de React.
  Solo se mueve la llamada al proveedor.
  **Endpoints nuevos** (bajo `/api/v1`, contrato en `docs/api-contract.md`):
  (1) `POST /voz/transcribir` — multipart `file` (webm/ogg, tope de tamaño y duracion) →
  `{"texto": str}`; (2) `POST /voz/hablar` — `{"texto": str}` (tope de caracteres) →
  `audio/mpeg` en streaming; (3) `POST /agente/turno` — `{mensaje, historial, perfil}` →
  `{"type":"text"|"tool_calls", ...}` con la MISMA forma que hoy devuelve
  `sendMessageWithTools`, para no reescribir `agentLoop.ts`. El schema de tools y el
  system prompt viven en el SERVIDOR (whitelist: `navegar`, `cargar_xmls_demo`,
  `calcular_predeclaracion`); el cliente no manda schemas.
  **Auth y CORS** (dentro del alcance: sin esto solo se traslada el agujero): dependencia
  `verify_firebase_token` sobre los 3 endpoints nuevos (valida el ID token de Firebase del
  header `Authorization: Bearer`; el front ya lo tiene en `useAuth()`) y `CORS_ORIGINS`
  explicito en produccion, nunca `*`. El **rate limit sale a S-00b**.
  **Qué se elimina de apps/store:** `VITE_OPENAI_API_KEY` de `.env` y `.env.example`; la
  constante `OPENAI_API_KEY` y los 4 `fetch` a `api.openai.com` de `voiceChatService.ts`
  (pasan por `fiscalAgentApi.ts` con el ID token); `sendMessage()` (muerta desde
  `agentLoop`); la nota de `apps/store/CLAUDE.md` que declara la key de cliente como
  "aceptable para demo"; y `apps/store/dist/` se borra y se reconstruye (el artefacto
  actual esta contaminado).
  **Rotacion (la hace Ricardo):** revocar la key `sk-proj-...` en OpenAI, emitir una nueva
  solo en `apps/api/.env`, y restringir la key de Firebase (`AIzaSy...`) por HTTP referrer.
  *Listo cuando:* (a) cero variables secretas en `apps/store/.env` y `.env.example` — solo
  quedan las de Firebase y la URL del agente; (b) `grep -rn "api.openai.com" apps/store/src`
  → cero resultados; (c) build nuevo y `grep -roE "sk-[A-Za-z0-9_-]{8,}" apps/store/dist/`
  → cero resultados; (d) la key vieja esta REVOCADA en OpenAI y la nueva vive solo en
  `apps/api/.env` — **confirmado por Ricardo el 2026-09-01**; falta la restriccion
  por HTTP referrer de la key de Firebase; (e) los 3 endpoints nuevos responden 401 sin ID token
  valido de Firebase; (f) `pytest -q` verde incluyendo tests nuevos de los 3 endpoints (401
  sin token + happy path con el cliente OpenAI mockeado; los tests nunca pegan a la API
  real); (g) `ruff check .` limpio, `npm run build` y `npm run lint` sin errores nuevos;
  (h) el chat de voz funciona end-to-end (grabar → transcribir → tool call → responder →
  TTS) sin ninguna key en el cliente; (i) `docs/api-contract.md` actualizado con los 3
  endpoints y el esquema de auth.
- [x] **S-05 · Runner de tests en el frontend** — instalar Vitest + Testing Library,
  script `test`, red cerrada por default en setup, pruebas semilla de `cfdiParser` (con
  los demo-xmls) **y de la lógica pura de `agentLoop.ts` y `tools.ts`**. Descomentar
  `npm test` en `ci.yml`. Va **antes de S-02**: sin esta red, tocar `AgentContext` para
  limpiar eslint es a ciegas. *Listo cuando:* `npm test` verde en local y en CI, y las
  semillas cubren cfdiParser + la lógica pura de agentLoop y tools.
- [ ] **S-02 · Lint frontend a cero y al CI** — corregir 20 errores + 8 warnings de
  eslint (concentrados en voiceChatService, AgentContext, tools). Descomentar `npm run
  lint` en `ci.yml`. *Listo cuando:* `npm run lint` exit 0 en local y corre en CI.
- [ ] **S-01b · Alinear `target-version` de ruff con el Python del CI** —
  `pyproject.toml` declara `target-version = "py311"` pero el job backend de `ci.yml` corre
  en Python 3.12: ruff aplica reglas de una version que no es la que ejecuta los tests.
  *Listo cuando:* las dos versiones coinciden (o la discrepancia queda justificada por
  escrito en `pyproject.toml`) y `ruff check .` sigue limpio.
- [ ] **S-03 · `docs/api-contract.md` como fuente única** — exportar el OpenAPI de
  FastAPI a un contrato versionado (endpoints, request/response). Los dos CLAUDE.md de
  apps dejan de duplicarlo y lo referencian. *Listo cuando:* el archivo existe, cubre
  los 11 endpoints, y las secciones duplicadas de los CLAUDE.md se reemplazan por la
  referencia.
- [x] **S-04 · Caso real de nómina anonimizado** — tomar 1 bimestre de
  `03. CFDI DE NOMINA/` (p. ej. marzo–abril: 9→7 empleados, con INFONAVIT, prima
  dominical y subsidio), generar fixtures XML con RFC/nombres/CURP sintéticos y montos
  reales, en `apps/api/tests/fixtures/nomina/`. *Listo cuando:* fixtures versionadas
  sin ningún dato identificable real (verificación explícita del revisor) y un
  `conftest` que las cargue. Es el equivalente nómina del CADG620317EE0.
## D — Demo 2026-09-02: nómina + checador Hikvision

Rama **vertical de demo**, no sustituye a F0/F1: cuando la demo pase, lo demo-only se borra y
el motor se queda. El detalle completo —alcance, referencia ISAPI del Hikvision, configuración
del dispositivo— vive en `docs/D-DEMO-CHECADOR.md`. Reglas del día: salario **fijo**, **1
cliente**, **quincenal**, sin IDSE, sin `apps/despacho`.

- [x] **D-01 · Tablas + constantes mínimas** — cubierta por F1-01…F1-05.
- [x] **D-02 · `integracion.py` + `cuotas.py`** — cubierta por F1-02 y F1-03.
- [x] **D-03 · `isr_nomina.py` + `recibo.py`** — cubierta por F1-04 y F1-05.
- [x] **D-04 · Módulo `asistencia/` + endpoints** — `schemas/asistencia.py` con
  `EventoChecada{empleado_no, timestamp, tipo, fuente, raw?}`; `asistencia/hikvision.py`
  con `parse_acs_event()` (lee `InfoList[].employeeNoString`, `time`, `attendanceStatus`;
  filtra `major==5 and minor==75`); `asistencia/incidencias.py` con `cerrar_periodo()`
  → días trabajados, faltas, retardos, `dias_cotizados`. Endpoints
  `POST /asistencia/eventos`, `GET /asistencia/eventos`, `POST /asistencia/cerrar-periodo`;
  almacenamiento **en memoria del proceso**, solo para la demo. *Listo cuando:* un payload
  `AcsEvent` real de la doc Hikvision produce las incidencias esperadas.
- [x] **D-05 · Simulador de checador** — `scripts/simular_checador.py` genera la quincena
  completa de los empleados de S-04 (con 2 faltas y 3 retardos sembrados) y la POSTea con el
  **mismo JSON que el dispositivo**. Modo `--en-vivo`, una checada cada 5 s. *Listo cuando:*
  corriéndolo, el panel se llena solo.
  **Criterio cumplido a medias, a propósito (PR #17):** el panel es D-07 y no existía al cerrar
  esta tarea. Lo verificado end-to-end contra los tres endpoints es que el simulador alimenta
  `POST /asistencia/eventos`, que `GET /asistencia/eventos` devuelve lo que el panel va a
  consumir —194 checadas en orden, cada una con el nombre que le toca— y que `cerrar-periodo`
  da las 2 faltas y los 3 retardos. **"El panel se llena solo" lo cierra D-07.** La lógica pura
  vive en `scripts/checador_sintetico.py`.
- [x] **D-06 · `POST /api/v1/nomina/calcular-periodo` + tool de agente** — recibe
  `{cliente, empleados[], incidencias, periodo}` → `{recibos[], cuotas_consolidadas,
  explicacion?}`. **Orquestador, no motor: llama directo a `recibo.py` y `cuotas.py` y no
  reimplementa nada.** Tool `calcular_nomina_periodo` en `agent_tools.py`. *Listo cuando:*
  `docs/api-contract.md` lo lista y el agente lo invoca desde el chat de texto.
  **Cerrada con PR #18, con dos precisiones que hay que leer antes de la demo:**
  (1) `cuotas_consolidadas` se llama `porcion_mensual` / `porcion_bimestral` porque **no es
  el entero del Art. 39 LSS**: es lo devengado en el periodo, y una quincena trae media
  mensualidad de EyM/IyV. La respuesta lo advierte. (2) Del "el agente lo invoca" está
  probado el registro, el despacho y que **los system prompts lo enumeran** —que era el
  hueco real—, pero **que un LLM decida llamarlo no se verifica en CI**: no hay key y
  ningún test pega a un proveedor. Decisiones nuevas en §D17–§D20.
- [x] **D-07 · Pantalla demo en `apps/store`** — ruta `/app/nomina-demo`, sin tocar los tabs
  existentes: panel de checador con polling cada 3 s, botón "Cerrar quincena" → tabla de
  incidencias, botón "Calcular nómina" → recibos + cuotas patronales por ramo, export PDF con
  `pdfExport*.ts`. *Listo cuando:* el flujo completo se recorre sin tocar consola.
  **Criterio cumplido a medias (PR #19).** *Verificado:* la secuencia completa de llamadas
  contra la API viva —plantilla → 194 checadas → cierre con 2 faltas y 3 retardos → 9 recibos
  con E-05 y E-08 en 15 días pagados— y los tests de jsdom con `fetch` stubbeado.
  *No verificado:* que la pantalla se pinte y los botones respondan **en un navegador** contra
  la API real; la ruta está detrás de Firebase Auth y del gate de onboarding. Para eso está el
  **runbook en `docs/D-DEMO-CHECADOR.md`**, que además lista los tres modos de falla que no son
  bugs: sembrar y demostrar el mismo día, no reiniciar la API, y la cuenta con onboarding
  completo. Endpoint nuevo `GET /nomina/demo/plantilla` para que el front no hardcodee ninguna
  constante fiscal.
- [ ] **D-08 · (Solo con el dispositivo enfrente) Conectar el Hikvision real** — push por
  HTTP listening o poll con Digest; alta de 2–3 rostros con `employeeNo` = id de fixture.
  **Fuera de la cola nocturna**: necesita hardware. *Listo cuando:* una checada real aparece
  en el panel.

> **El motor no lleva tolerancias**: es exacto. Lo que **no** hace es reproducir los recibos
> históricos del caso real, y la diferencia es del CFDI timbrado, no del motor — ver el
> recuadro "Qué significa *el motor cuadra al centavo*" en `docs/D-DEMO-CHECADOR.md` antes de
> decir nada de esto en la demo.

## F0 — Fundamentos de nómina (sin código de producto)

- [x] **F0-01 · `knowledge_base/nomina/`** — docs 20–26 con los valores de
  PLAN_NOMINA §2 (UMA por vigencia, SM, tope/piso SBC, subsidio 2026, factor de
  integración, ramos IMSS, CEAV) y sus fuentes. *Listo cuando:* cada valor tiene fuente
  y fecha de vigencia.
- [x] **F0-02 · Refactor `constants.py` a vigencias** — `uma_vigente(fecha)` y
  `salario_minimo_vigente(fecha, zona)`; migrar usos existentes; tests que cubran el
  corte enero/febrero 2026 (UMA 2025 en enero). *Listo cuando:* 93 tests previos
  siguen verdes + tests nuevos de vigencia.
- [x] **F0-03 · Checklist contadora** — documentar en `docs/decisiones-nomina.md` las 8
  preguntas abiertas de PLAN_NOMINA §5 con las respuestas obtenidas (tablas ISR
  periódicas vs prorrateo, redondeo, ausentismos por ramo, quirk CEAV, EMA/EBA, PAC,
  ISN Veracruz). *Listo cuando:* las que bloquean F1 tienen respuesta o decisión
  provisional explícita.

## F1 — Motor `nomina_engine`

- [x] **F1-01 · `tablas_imss.py` + `tablas_isr_periodicas.py` + `subsidio_empleo()`** —
  tablas 2026 versionadas con fuente; subsidio con transitorio de enero. *Listo cuando:*
  tests unitarios por tabla contra valores publicados.
- [x] **F1-02 · `integracion.py`** — factor de integración calculado desde
  (aguinaldo, vacaciones, prima), SBC fijo/variable/mixto, clamp 1 SM–25 UMA,
  `ConceptoIntegrable`, `requiere_aviso` con fecha límite (Art. 34). *Listo cuando:*
  la tabla de factores mínimos de ley de PLAN_NOMINA §2.2 pasa como test.
- [x] **F1-03 · `cuotas.py`** — cuotas por ramo, por empleado, consolidado
  mensual/bimestral; SM absorbe cuota obrera; EyM excedente 3 UMA. *Listo cuando:*
  tests unitarios por ramo + cuadre contra el caso real S-04.
  **Criterio ajustado en F1-03 (ver `docs/decisiones-nomina.md` §D14):** el cuadre contra el
  caso real **no es alcanzable con el dato timbrado**. Solo **5 de los 70 recibos** se
  reproducen: un empleado, y solo desde abril, porque el software del patrón cambió de orden de
  redondeo en el corte marzo→abril. De los demás, tres tienen una deducción **menor que el
  mínimo legal** que impone su propio `SalarioBaseCotApor`, cosa que ninguna fórmula puede
  producir. Se entregó el cuadre de esos 5 recibos contra el importe timbrado y la
  caracterización ejecutable del resto. **El cuadre completo queda pendiente de la contadora**,
  no del código.
- [x] **F1-04 · `isr_nomina.py`** — exenciones Art. 93, ISR Art. 96 periódico, subsidio
  con vigencia. *Listo cuando:* el ISR retenido de las fixtures S-04 cuadra al centavo
  (o con la regla de redondeo decidida en F0-03).
  **Resultado (ver `docs/decisiones-nomina.md` §D15):** el motor reproduce **al centavo los 28
  recibos de abril, completos**, y la exención cuadra en el 100 % de los recibos que la
  ejercitan. Marzo cuadra 6 de 35 porque el subsidio que declara el CFDI ahí es **$123.47**
  —compatible con dos bases distintas que no se pueden distinguir al centavo, ver §D15— y
  porque el tope de ingresos todavía no mordía; **desde abril el declarado es $123.34, que es
  lo que calcula el motor**. Los
  7 recibos de mayo llevan lo que parece un ajuste mensual de ISR, fuera del alcance de esta
  tarea.
  **Huecos que le deja F1-01:** `tarifa_por_periodicidad()` levanta error para la
  **catorcenal** (nadie la publica) y para la **decenal** (el Anexo 8 sí la publica, pero sus
  11 renglones no se pudieron verificar contra fuente publicada — agregarla es transcribir sus
  22 celdas con su cita). Ver `docs/decisiones-nomina.md` D10. Y **D11 sigue abierta**: el tope
  del subsidio es mensual y el caso real es semanal; `subsidio_empleo()` recibe el ingreso
  mensual ya resuelto y no decide si se proyecta o se acumula.
- [x] **F1-05 · `recibo.py` + `cfdi_nomina_xml.py`** — recibo completo
  (percepciones/deducciones/otros pagos) y XML complemento nómina 1.2 **sin timbrar**,
  validado contra XSD. Las fixtures de S-04 son estructuralmente correctas pero
  **criptográficamente inverificables** (sellos sintéticos): la validación XSD es de
  estructura, no de sello. *Listo cuando:* los XSD de complemento nómina 1.2 y CFDI 4.0
  están **versionados offline en `apps/api/tests/xsd/`** para validar en CI sin red, el
  XML generado del caso real valida contra ellos, y sus totales cuadran con el timbrado
  original.
  **Resultado:** los 6 XSD quedan versionados **byte-idénticos** a lo publicado por el SAT
  (6.1 MB, de los cuales `catCFDI.xsd` son 5.98 MB) y la resolución offline la hace un resolver
  de lxml, no una reescritura — así el SHA-256 de cada uno sigue verificando contra la fuente
  oficial, y un test lo recalcula. **Los 70 recibos del caso real se vuelven a emitir con el generador** y los
  totales que escribe en el XML cuadran contra el timbrado en los 70, **los 70 emitidos validan
  sin red**, y un test de ida y vuelta compara atributo por atributo todo lo que el generador
  emite contra el original, excluyendo los de sello. Se lee del documento emitido, no del objeto de dominio: comparar propiedades del recibo
  contra el fixture deja pasar un generador que escriba el atributo equivocado. El
  camino de **cálculo** (ISR y cuota obrera) sigue midiéndose donde lo dejaron §D14 y §D15;
  F1-05 no lo re-litiga.
- [ ] **F1-06 · `calendario_laboral.py`** — obligaciones patronales (pago mensual día
  17, bimestral, avisos de variables) fusionables con el calendario SAT existente.
  **PARCIALMENTE ENTREGADA POR E-07, y por eso NO se marca.** Ya existen
  `app/nomina_engine/calendario_laboral.py` (catálogo de obligaciones) y `plazos_patronales.py`
  (las cinco reglas de plazo), con las 12 fechas de 2026 contrastadas contra la tabla publicada
  del doc 25 §3. **Lo que falta y por qué:** la parte de "fusionables con el calendario SAT"
  choca de frente con la advertencia de `dias_habiles.py:8-14` —el del SAT corre por sexto dígito
  del RFC y el del IMSS por viernes o inhábil, y el doc 25 §4 dice que juntarlos sin distinguir
  "es un bug esperando"—. E-07 los mantuvo separados y etiquetó cada obligación con su
  `regimen_de_plazo`. **Decisión para Ricardo:** si "fusionable" significaba una sola vista, ya
  está; si significaba un solo generador, hay que reabrir la advertencia. Faltan además: ISN
  (sin fuente estatal en el repo, §D24) y el ajuste por sexto dígito (el modelo de cliente no
  guarda RFC).
  **Defecto preexistente detectado y NO arreglado aquí:** `fiscal_engine/calendario.py`
  `_fecha_limite_dia_17()` con `dias_extra=0` devuelve el día 17 crudo, domingos incluidos,
  porque sólo suma días hábiles hacia adelante y nunca corrige el día de partida. Afecta al
  calendario del CONTRIBUYENTE. Fuera del alcance de E-07; que lo recoja F1-07 o S-03.
- [ ] **F1-07 · Routes + schemas nómina** — `app/routes/nomina/` y
  `app/schemas/nomina/` (sbc, cuotas, recibo, calendario), errores con
  `FiscalAgentError`, explicación LLM con fallback. *Listo cuando:* `docs/api-contract.md`
  actualizado en el mismo PR.
  **OJO — E-07 se comió su parte de "calendario":** ya existen `GET /api/v1/despacho/calendario`
  y `app/schemas/calendario_laboral.py`, documentados en el contrato. **F1-07 no debe crear un
  segundo endpoint de calendario**; si acaso, mover el existente a `routes/nomina/` cuando esa
  carpeta exista. La cola decía S-03 → F1-07 → F1-08 → F1-06 y esta corrida se saltó ese orden
  por instrucción directa de Ricardo (demo del 2026-09-02), no por la regla de la cola.
- [ ] **F1-08 · Tools de agente + `POST /agente/nomina`** — extender `agent_tools.py`
  (calcular_sbc, calcular_cuotas, generar_recibo) con RequestContext.

## F2+ — Épicas (se desglosan al llegar)

- [ ] **F2 · Frontend `apps/despacho`** (scaffold, contador→clientes→empleados, pantallas
  cuotas/nómina, dashboard, Fiscalito voz, preview fiscal) — ver PLAN_NOMINA §3.3/§4.
- [ ] **F3 · Integraciones** (conciliación EMA/EBA, PAC sandbox, IDSE/SUA, alertas).
- [ ] **F4 · Escala** (módulo fiscal por cliente, multi-usuario, ISN, PTU, MCP).

## Diferido (despues de nomina)

Nada de esto entra a la cola nocturna. Se retoma cuando nomina este cerrada.

- [ ] **S-00b · Auth en todo `/api/v1` + rate limit por uid + tope de gasto** — va
  inmediatamente despues de S-00. S-00 pone auth solo en los 3 endpoints nuevos porque el
  backend de produccion esta caido y la ventana de exposicion es cero; S-00b cierra el
  resto.
  (1) **Auth en todos los endpoints `/api/v1`** (`/health` queda publico) — la forma barata
  es `include_router(..., dependencies=[Depends(verify_firebase_token)])` en `main.py`, una
  linea por router. Importa porque los 7 endpoints de calculo aceptan
  `incluir_explicacion: true` y **tambien queman tokens de LLM**: el front lo manda en 8
  lugares.
  (2) **Rate limit por uid de Firebase** sobre todo lo que gasta LLM (`/voz/transcribir`,
  `/voz/hablar`, `/agente/turno`, `/agente/predeclaracion` y los 7 de calculo con
  explicacion), con 429 y `Retry-After`.
  (3) **Tope de gasto**: limite duro en el dashboard de OpenAI + corte propio por ventana.
  Nota: la auth identifica, no frena — el alta de usuarios es abierta
  (`createUserWithEmailAndPassword`), asi que cualquiera obtiene un token valido en 10
  segundos. El uid sirve para rate-limitar, y ese es el control real.
  **El backend no se despliega publico hasta cerrar S-00b.**
  *Listo cuando:* tests que prueban 401 sin token en los endpoints de calculo, 429 al
  exceder el limite y 200 dentro del limite; el limite es configurable por env;
  `docs/api-contract.md` documenta la auth generica y el 429; y el tope duro esta puesto en
  el dashboard de OpenAI (confirmado por Ricardo).
- [ ] **S-06 · (Opcional, prioridad baja) Reescribir historial para purgar
  `apps/api/pfebrero/`** — 12 XML de CFDI con RFC de terceros identificables
  (CADG620317EE0, NIGE780321TK2, MCP2404207Q2, BMS170308GT7...) siguen alcanzables en los
  commits `29245f6` y `29313de` aunque ya no existan en el arbol. **Prioridad baja a
  proposito:** el repo es privado y el historial no tiene ninguna API key (verificado el
  2026-08-31 blob por blob). Reescribir historial rompe clones y forks, asi que solo vale
  la pena si el repo se hace publico. *Listo cuando:* si se decide hacerlo, `git filter-repo`
  purga la ruta, se fuerza el push y se avisa de la reescritura; si no, esta tarea se cierra
  con una nota de decision explicita.
- [ ] **S-08 · Deploy backend a Cloud Run + front apuntando a el** (cuando haya razon para
  produccion) — hoy produccion esta APAGADA por decision de Ricardo (2026-09-01): el sitio
  no tiene usuarios y la prioridad es nomina. El bundle publicado en
  `fiscalito-mvp.web.app` apunta a `fiscal-agent-api-production.up.railway.app`, que
  responde 404 (Railway lo dio de baja), asi que ningun calculo fiscal funciona en vivo.
  Mientras tanto `VITE_FISCAL_AGENT_URL` apunta a localhost en dev y punto. No redesplegar
  Railway. *Listo cuando:* haya una razon de producto para tener produccion; entonces se
  desglosa (Cloud Run, CORS_ORIGINS explicito, build del front con la URL real, redeploy de
  Hosting). Bloqueada por S-00b.
- [ ] **S-07 · Anonimizar las demo-xmls y el caso real CADG620317EE0** — las tres
  fixtures de `apps/store/public/demo-xmls/2026/01/` llevan RFC y nombre reales, y
  `vite build` las copia tal cual a `dist/`, asi que viajan al bundle desplegado. Mismo
  tratamiento para el caso real del backend. RFC/nombre sinteticos, montos reales.
  **Ojo:** desde S-05 la suite depende de esas fixtures, asi que este cambio toca tambien
  `apps/store/src/services/cfdiParser.test.ts` y `apps/store/src/agent/tools.test.ts`.
  *Listo cuando:* ningun dato identificable real queda en `public/` ni en `dist/`, y
  `npm test` sigue verde con las fixtures nuevas.
- [ ] **B-01 · (Bug, prioridad baja) La demo siempre reporta "0 egreso(s)"** —
  `ejecutarCargarXmlsDemo` cuenta `f.tipo === 'E'` para su resumen, pero las tres
  demo-xmls son `TipoDeComprobante="I"` (una factura de compra lo es). El conteo nunca
  es distinto de cero. Es un bug de datos demo, no del parser. *Listo cuando:* el resumen
  refleja la realidad (o distingue emitidas de recibidas por RFC en vez de por tipo).
