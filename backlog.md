# BACKLOG — Fiscalito (prioridad: Nómina)

Reglas: una tarea = una rama = un PR. `[x]` solo tras merge a main confirmado por
Ricardo. Cada tarea tiene su "Listo cuando" — el plan y el revisor se miden contra eso.
El detalle de dominio (valores 2026, fórmulas, fuentes) está en `docs/PLAN_NOMINA.md`.

## S — Saneamiento (deuda que estorba al bucle)

- [x] **S-01 · Lint backend a cero y al CI** — `ruff check --fix` (43 auto) + limpiar el
  resto (111 total: E501, I001, F401, F541). Descomentar el paso `ruff check .` en
  `ci.yml`. *Listo cuando:* `ruff check .` sale limpio en local y corre en CI.
- [ ] **S-02 · Lint frontend a cero y al CI** — corregir 20 errores + 8 warnings de
  eslint (concentrados en voiceChatService, AgentContext, tools). Descomentar `npm run
  lint` en `ci.yml`. *Listo cuando:* `npm run lint` exit 0 en local y corre en CI.
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
- [ ] **S-05 · Runner de tests en el frontend** — instalar Vitest + Testing Library,
  script `test`, red cerrada por default en setup, 3–5 pruebas semilla (cfdiParser con
  los demo-xmls). Descomentar `npm test` en `ci.yml`. *Listo cuando:* `npm test` verde
  en local y en CI.

## F0 — Fundamentos de nómina (sin código de producto)

- [ ] **F0-01 · `knowledge_base/nomina/`** — docs 20–26 con los valores de
  PLAN_NOMINA §2 (UMA por vigencia, SM, tope/piso SBC, subsidio 2026, factor de
  integración, ramos IMSS, CEAV) y sus fuentes. *Listo cuando:* cada valor tiene fuente
  y fecha de vigencia.
- [ ] **F0-02 · Refactor `constants.py` a vigencias** — `uma_vigente(fecha)` y
  `salario_minimo_vigente(fecha, zona)`; migrar usos existentes; tests que cubran el
  corte enero/febrero 2026 (UMA 2025 en enero). *Listo cuando:* 93 tests previos
  siguen verdes + tests nuevos de vigencia.
- [ ] **F0-03 · Checklist contadora** — documentar en `docs/decisiones-nomina.md` las 8
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
  validado contra XSD. *Listo cuando:* el XML generado del caso real valida y sus
  totales cuadran con el timbrado original.
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
