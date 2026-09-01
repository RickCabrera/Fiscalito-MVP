# BACKLOG — Fiscalito (prioridad: Nómina)

Reglas: una tarea = una rama = un PR. `[x]` solo tras merge a main confirmado por
Ricardo. Cada tarea tiene su "Listo cuando" — el plan y el revisor se miden contra eso.
El detalle de dominio (valores 2026, fórmulas, fuentes) está en `docs/PLAN_NOMINA.md`.

## Cola nocturna

Orden exacto que toma el **modo autonomo** (ver `CLAUDE.md`): la primera que no este
`[x]` ni marcada SALTADA en `docs/nocturno-log.md`. Una tarea por sesion. El detalle de
cada una vive en su seccion de abajo. **S-00 no esta aqui a proposito:** su criterio de
cierre exige probar el chat de voz con microfono, asi que es diurna.

1. F0-01
2. F0-02
3. F1-01
4. F1-02
5. F1-03
6. F1-04
7. F1-05
8. F1-06
9. S-03
10. F1-07
11. F1-08
12. S-02
13. S-01b

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
- [ ] **S-04 · Caso real de nómina anonimizado** — tomar 1 bimestre de
  `03. CFDI DE NOMINA/` (p. ej. marzo–abril: 9→7 empleados, con INFONAVIT, prima
  dominical y subsidio), generar fixtures XML con RFC/nombres/CURP sintéticos y montos
  reales, en `apps/api/tests/fixtures/nomina/`. *Listo cuando:* fixtures versionadas
  sin ningún dato identificable real (verificación explícita del revisor) y un
  `conftest` que las cargue. Es el equivalente nómina del CADG620317EE0.
## F0 — Fundamentos de nómina (sin código de producto)

- [ ] **F0-01 · `knowledge_base/nomina/`** — docs 20–26 con los valores de
  PLAN_NOMINA §2 (UMA por vigencia, SM, tope/piso SBC, subsidio 2026, factor de
  integración, ramos IMSS, CEAV) y sus fuentes. *Listo cuando:* cada valor tiene fuente
  y fecha de vigencia.
- [ ] **F0-02 · Refactor `constants.py` a vigencias** — `uma_vigente(fecha)` y
  `salario_minimo_vigente(fecha, zona)`; migrar usos existentes; tests que cubran el
  corte enero/febrero 2026 (UMA 2025 en enero). *Listo cuando:* 93 tests previos
  siguen verdes + tests nuevos de vigencia.
- [x] **F0-03 · Checklist contadora** — documentar en `docs/decisiones-nomina.md` las 8
  preguntas abiertas de PLAN_NOMINA §5 con las respuestas obtenidas (tablas ISR
  periódicas vs prorrateo, redondeo, ausentismos por ramo, quirk CEAV, EMA/EBA, PAC,
  ISN Veracruz). *Listo cuando:* las que bloquean F1 tienen respuesta o decisión
  provisional explícita.

## F1 — Motor `nomina_engine`

- [ ] **F1-01 · `tablas_imss.py` + `tablas_isr_periodicas.py` + `subsidio_empleo()`** —
  tablas 2026 versionadas con fuente; subsidio con transitorio de enero. *Listo cuando:*
  tests unitarios por tabla contra valores publicados.
- [ ] **F1-02 · `integracion.py`** — factor de integración calculado desde
  (aguinaldo, vacaciones, prima), SBC fijo/variable/mixto, clamp 1 SM–25 UMA,
  `ConceptoIntegrable`, `requiere_aviso` con fecha límite (Art. 34). *Listo cuando:*
  la tabla de factores mínimos de ley de PLAN_NOMINA §2.2 pasa como test.
- [ ] **F1-03 · `cuotas.py`** — cuotas por ramo, por empleado, consolidado
  mensual/bimestral; SM absorbe cuota obrera; EyM excedente 3 UMA. *Listo cuando:*
  tests unitarios por ramo + cuadre contra el caso real S-04.
- [ ] **F1-04 · `isr_nomina.py`** — exenciones Art. 93, ISR Art. 96 periódico, subsidio
  con vigencia. *Listo cuando:* el ISR retenido de las fixtures S-04 cuadra al centavo
  (o con la regla de redondeo decidida en F0-03).
- [ ] **F1-05 · `recibo.py` + `cfdi_nomina_xml.py`** — recibo completo
  (percepciones/deducciones/otros pagos) y XML complemento nómina 1.2 **sin timbrar**,
  validado contra XSD. Las fixtures de S-04 son estructuralmente correctas pero
  **criptográficamente inverificables** (sellos sintéticos): la validación XSD es de
  estructura, no de sello. *Listo cuando:* los XSD de complemento nómina 1.2 y CFDI 4.0
  están **versionados offline en `apps/api/tests/xsd/`** para validar en CI sin red, el
  XML generado del caso real valida contra ellos, y sus totales cuadran con el timbrado
  original.
- [ ] **F1-06 · `calendario_laboral.py`** — obligaciones patronales (pago mensual día
  17, bimestral, avisos de variables) fusionables con el calendario SAT existente.
- [ ] **F1-07 · Routes + schemas nómina** — `app/routes/nomina/` y
  `app/schemas/nomina/` (sbc, cuotas, recibo, calendario), errores con
  `FiscalAgentError`, explicación LLM con fallback. *Listo cuando:* `docs/api-contract.md`
  actualizado en el mismo PR.
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
