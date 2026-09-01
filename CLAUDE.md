# FISCALITO-MVP — Protocolo de trabajo (Sistema B)

Este archivo define CÓMO se trabaja en este monorepo. El QUÉ (arquitectura, endpoints,
reglas de código) vive en `apps/api/CLAUDE.md` y `apps/store/CLAUDE.md` — léelos según
la app que toque la tarea. El plan de dominio de nómina vive en `docs/PLAN_NOMINA.md`.

**Desarrollador único: Ricardo.** No hay carriles separados; el mismo bucle sirve para
backend y frontend. La prioridad absoluta actual es **nómina** (ver `backlog.md`).

## El bucle (innegociable)

1. Ricardo pide una tarea del `backlog.md` (o te dice cuál sigue).
2. **Plan primero.** Lee el backlog, el CLAUDE.md de la app afectada y el código
   relevante. Escribe un plan concreto (archivos a tocar, tests a agregar, criterio de
   "Listo cuando" de la tarea). **Pásalo por el subagente `revisor`** antes de mostrarlo.
3. Muestra el plan (ya revisado, con las observaciones del revisor resueltas o
   señaladas como decisión abierta) y **espera autorización explícita de Ricardo**.
4. Construye en una **rama nueva desde main actualizado**
   (`git checkout main && git pull && git checkout -b feat/<id-tarea>`).
5. Al terminar: corre los checks locales de la app (ver abajo), **pasa el resultado por
   el `revisor`**, corrige lo que marque, y muestra a Ricardo un resumen honesto de lo
   implementado + salida de tests. **Espera autorización.**
6. Con el OK: push a la rama y `gh pr create`. Ricardo espera el CI en verde y hace el
   merge él mismo.
7. Cuando Ricardo confirme el merge: marca `[x]` la tarea en `backlog.md`, **commitea el
   backlog en ese mismo movimiento**, y ofrece la siguiente tarea. Vuelve a esperar.

> Si el ejecutor no invoca al revisor por su cuenta, Ricardo lo dispara con `@revisor`.

## Checks locales antes de cantar victoria

- **apps/api**: `pytest -q` (93+ verdes, cero skips) · `ruff check .` limpio en lo que toques.
- **apps/store**: `npm run build` limpio (tsc sin errores) · `npm run lint` sin errores
  nuevos · cuando exista runner de tests (tarea S-05), `npm test` verde.

## Reglas de cierre (gate)

- `[x]` = **mergeado a main por Ricardo y confirmado**. No "CI verde", no "ya pusheé".
- Nunca aflojes un test, un tipo o una validación para forzar el verde.
- Rama nueva siempre desde main actualizado. Nunca rama-sobre-rama ni reusar ramas viejas.
- Una tarea por corrida. Nada "de pasada".
- Si la tarea expone o cambia un endpoint: `docs/api-contract.md` se actualiza **en el
  mismo entregable** (es la fuente única del contrato; los CLAUDE.md de las apps solo
  lo referencian).
- El commit que marca `[x]` en `backlog.md` (y solo ese, sin tocar otro archivo) va
  directo a main con push; no requiere rama ni PR.

## Diagnóstico antes de modificar

Si la tarea es arreglar algo existente: primero diagnostica (lee, reproduce, explica la
causa) y espera OK antes de editar. No reescribas a ciegas.

## Nunca

- Nunca avances de tarea sin autorización explícita de Ricardo.
- Nunca marques `[x]` sin merge confirmado.
- Nunca uses `--dangerously-skip-permissions`.
- **Nunca commitees ni copies al repo datos personales reales.** La carpeta
  `03. CFDI DE NOMINA/` y `VERIFICACION_NOMINAS.md` contienen nóminas de personas
  identificables (nombre, RFC, salario): están gitignoreadas y así se quedan. Para
  tests se usan **fixtures anonimizadas** (tarea S-04) — RFC, nombres y CURP sintéticos,
  montos reales.
- Nunca uses el LLM para calcular ISR/IVA/cuotas — el motor es determinístico, el LLM
  solo explica (regla de oro heredada, ver `apps/api/CLAUDE.md` y `docs/PLAN_NOMINA.md`).
- Nunca cambies tablas ISR/IMSS/UMA/SM sin citar fuente oficial (DOF/INEGI/IMSS/CONASAMI)
  en el docstring o en `knowledge_base/`.
- Fuera de alcance salvo tarea explícita: timbrado real con PAC, facturación CFDI de
  ingresos, MCP server.

## Modo autónomo (nocturno)

Se activa SOLO cuando Ricardo lanza una sesión con la instrucción literal "MODO AUTÓNOMO".
En ese modo el bucle cambia así, y NADA MÁS cambia:

- No hay paradas humanas: no esperes autorización del plan ni del resultado. El revisor
  SIGUE siendo obligatorio en ambos puntos (plan y entregable).
- Toma la PRIMERA tarea de la sección "Cola nocturna" de `backlog.md` que no esté `[x]` ni
  aparezca como SALTADA en `docs/nocturno-log.md`. Haz UNA sola tarea por sesión y termina.
- Rama `feat/<id>` desde main actualizado. Construye. Checks locales. Revisor. Si el revisor
  BLOQUEA, corrige y vuelve a pasar; si bloquea dos veces, la tarea se SALTA: escribes la
  razón en `docs/nocturno-log.md`, borras la rama, y terminas la sesión sin marcar nada.
- Con revisor aprobado: push, `gh pr create`, luego `gh pr merge --auto --squash
  --delete-branch`, y espera el CI con `gh pr checks --watch`. Si el CI falla: máximo 2
  intentos de arreglo; si sigue rojo, SALTA la tarea (log + cierra el PR + borra rama).
- Merge confirmado (`gh pr view --json state` dice MERGED): `git checkout main && git pull`,
  marca `[x]` en `backlog.md`, commit directo a main con push, y anota en
  `docs/nocturno-log.md`: tarea, PR, hora, y cualquier decisión que hayas tomado sin Ricardo.
- Decisiones que dependen del mundo (contadora, norma ambigua): usa
  `docs/decisiones-nomina.md`. Si no está cubierta ahí, toma la opción MÁS CONSERVADORA,
  déjala señalada con un comentario `# DECISIÓN PROVISIONAL (nocturno):` en el código y en
  el log, y continúa. Nunca te detengas a preguntar.
- Prohibido en modo autónomo, sin excepción: deploy (firebase, gcloud, railway), tocar
  producción o keys, force push, filter-repo, borrar ramas que no sean tuyas ya mergeadas,
  editar cualquier cosa bajo `03. CFDI DE NOMINA/`, cambiar este CLAUDE.md o
  `settings.json`, y aflojar tests/CI para lograr el verde.
