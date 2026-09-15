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
- Nunca uses `--dangerously-skip-permissions` en sesiones interactivas. La única excepción
  es el orquestador del Modo autónomo, `scripts/nocturno-v2.ps1`, que lo lanza con el hook
  `pre-push` como guardia. La sesión que abre v2 **es interactiva y lleva ese flag**: eso es
  el orquestador haciendo su trabajo, no una sesión tuya saltándose la regla.
- **`scripts/nocturno.ps1` (v1) está SUPERADO: no lo uses.** El Modo autónomo se señaliza
  hoy con archivos centinela (ver abajo) y v1 no sabe leerlos — corre en modo `-p` y busca
  el resultado en la salida de texto, que ya nadie imprime. Lanzado con este protocolo,
  seguiría abriendo sesiones contra una cola vacía hasta agotar `-MaxTareas`. Se conserva
  como referencia del modo `-p`; adaptarlo o borrarlo es tarea propia.
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

## Modo rápido

Se activa SOLO cuando Ricardo lo pide con la instrucción literal "MODO RÁPIDO". Es una
excepción a la cadencia del bucle, **no a sus garantías**. Se combina con Modo autónomo o
se usa solo. Lo que cambia:

- **Un plan para toda la corrida**, no uno por tarea, con **una** pasada de revisor sobre
  ese plan y **una** al cierre de la corrida. La sección del backlog dice cuántas y dónde.
- **Sin paradas de autorización entre tareas.** Sigue siendo una rama y un PR por tarea.
- **Excepción que nunca se levanta:** si la tarea toca cálculo, cuotas, ISR o cualquier
  motor, esa parte pasa por **revisor de motor aparte**, sin importar el modo.
- **Tests.** La sección del backlog puede aplazar la suite completa al cierre de la corrida
  y acotar qué se escribe durante ella. Lo que **no** puede hacer, ni en modo rápido ni en
  ninguno: borrar un test, marcarlo skip, o aflojar un tipo o una validación. Un test que
  rompe porque el comportamiento cambió **se adapta al comportamiento nuevo**; uno que rompe
  porque algo se rompió, se arregla.
- La sección del backlog es la que define el régimen concreto de su corrida. Si no lo
  define, aplica el bucle normal.

## Modo autónomo (nocturno)

Se activa SOLO cuando Ricardo lanza una sesión con la instrucción literal "MODO AUTÓNOMO".
En ese modo el bucle cambia así, y NADA MÁS cambia:

- No hay paradas humanas: no esperes autorización del plan ni del resultado. El revisor
  SIGUE siendo obligatorio en ambos puntos (plan y entregable).
- Toma la PRIMERA tarea de la sección "Cola nocturna" de `backlog.md` que no esté `[x]` ni
  aparezca como SALTADA en `docs/nocturno-log.md`. Haz UNA sola tarea por sesión y termina.
- **Una tarea = una sesión, y la sesión TERMINA al cerrarla.** No encadenes la siguiente
  aunque quede tiempo y aunque sea obvia cuál sigue: `scripts/nocturno-v2.ps1` lanza un
  proceso nuevo por tarea, y ese proceso nuevo es lo que hace que la tarea 12 arranque con
  tanto contexto útil como la 1. Encadenar dentro de la misma sesión arrastra el historial
  entero y degrada todo lo que venga después.
- **El log es el ÚNICO canal entre sesiones.** La siguiente sesión **no recuerda nada** de
  ésta: no ha visto tu razonamiento, tus dudas ni lo que descubriste a medio camino. Escribe
  en `docs/nocturno-log.md` lo que necesitaría saber alguien que llega en frío: decisiones
  que tomaste, lo que quedó abierto, las trampas que encontraste y lo que ibas a hacer
  distinto. Si algo importa y no está escrito, se perdió.
- **Y el log se escribe DENTRO DE LA RAMA, antes del push y del PR.** No después del merge.
  Su commit va en la rama de la tarea y viaja en el PR como un archivo más del entregable.
  *Por qué:* el vigilante mata la ventana en cuanto la tarea cierra, y escribir la nota
  después del merge es escribirla en el minuto en que te están apagando. En un repo hermano
  que corre este mismo protocolo, **nueve sesiones seguidas cerraron sin dejar nota** por
  exactamente eso. Tras el merge, a main sólo va el commit del `[x]` en `backlog.md`.
- Si la Cola nocturna ya no tiene tareas pendientes, **no inventes ninguna** ni te adelantes
  a las congeladas: crea el archivo vacío `COLA_VACIA.txt` en la raíz del repo y termina. El
  loop lo lee y para.
- Rama `feat/<id>` desde main actualizado. Construye. Checks locales. Revisor. Si el revisor
  BLOQUEA, corrige y vuelve a pasar; si bloquea dos veces, la tarea se SALTA (ver abajo).
- Con revisor aprobado: **escribe y commitea la entrada del log en la rama**, push,
  `gh pr create`, `gh pr checks --watch`; con CI verde:
  `gh pr merge --squash --delete-branch` (sin `--auto`). Si el CI falla: máximo 2 intentos
  de arreglo; si sigue rojo, SALTA.
- **Cierre.** Merge confirmado (`gh pr view --json state` dice MERGED):
  `git checkout main && git pull`, marca `[x]` en `backlog.md`, commit directo a main con
  push. La nota del log ya entró con el PR: no la repitas aquí. Como **último paso**, crea el
  archivo vacío `TAREA_CERRADA.txt` en la raíz del repo y termina la sesión. Ése es el aviso
  de que ya no te queda nada por escribir y la ventana se puede cerrar.
- **Salto.** Al SALTAR una tarea —revisor que bloquea dos veces, o CI que sigue rojo tras dos
  intentos—: `gh pr close` si llegaste a abrirlo, escribe la razón en `docs/nocturno-log.md`
  marcándola **SALTADA**, y **commitea y pushea esa entrada DIRECTO a main** (el `pre-push` lo
  permite). No la dejes en la rama: la vas a borrar, y entonces la siguiente sesión no ve el
  salto y vuelve a tomar la misma tarea. Después borra la rama, crea el archivo vacío
  `TAREA_SALTADA.txt` en la raíz y termina **sin marcar nada** en el backlog.
- Decisiones que dependen del mundo (contadora, norma ambigua): usa
  `docs/decisiones-nomina.md`. Si no está cubierta ahí, toma la opción MÁS CONSERVADORA,
  déjala señalada con un comentario `# DECISIÓN PROVISIONAL (nocturno):` en el código y en
  el log, y continúa. Nunca te detengas a preguntar.
- **Límite de uso.** Si la sesión muere porque se agotó el límite de tokens, no es un fallo
  de la tarea y no se anota como SALTADA: `scripts/nocturno-v2.ps1` espera y **reintenta la
  misma tarea** en una sesión nueva. Deja el árbol en un estado del que se pueda continuar
  —rama pusheada o cambios commiteados— y no marques nada. Es el único camino que NO deja
  centinela: sin ninguno de los tres archivos, el loop asume límite de uso y reintenta.
- **Los tres centinelas, juntos.** Son archivos vacíos en la raíz del repo, están
  gitignorados, y el loop los borra al empezar cada vuelta. Crea **uno solo** y siempre como
  último acto de la sesión: `TAREA_CERRADA.txt` (cerraste), `TAREA_SALTADA.txt` (saltaste),
  `COLA_VACIA.txt` (no había nada que tomar).
- Prohibido en modo autónomo, sin excepción: deploy (firebase, gcloud, railway), tocar
  producción o keys, force push, `git push --no-verify` (brinca el `pre-push`, que es la
  única guardia real de main), filter-repo, borrar ramas que no sean tuyas ya mergeadas,
  editar cualquier cosa bajo `03. CFDI DE NOMINA/`, cambiar este CLAUDE.md o
  `settings.json`, y aflojar tests/CI para lograr el verde.
