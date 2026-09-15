# Instalación del Sistema B en fiscalito-mvp

Este kit se descomprime **en la raíz del repo** y sobreescribe/crea:

```
CLAUDE.md                                  ← nuevo (orquestación, raíz)
backlog.md                                 ← nuevo
.gitignore                                 ← REEMPLAZA el actual
.claude/settings.json                      ← nuevo (config de equipo, se versiona)
.claude/hooks/auto-approve-readonly.py     ← nuevo
.claude/agents/revisor.md                  ← nuevo
.github/workflows/ci.yml                   ← nuevo (en la RAÍZ, donde Actions sí lo lee)
```

## Pasos manuales (5 minutos, en orden)

1. **Copiar PLAN_NOMINA.md a `docs/PLAN_NOMINA.md`** (el CLAUDE.md y el backlog lo
   referencian ahí).
2. Descomprimir este kit en la raíz. Aceptar el reemplazo de `.gitignore`.
3. **Borrar el CI muerto:** `git rm -r apps/api/.github` (Actions nunca lo leyó y ya
   quedó reemplazado por el de la raíz).
4. Borrar la carpeta basura `apps/api/{routes,schemas,services,fiscal_engine}/`
   (artefacto vacío del mkdir fallido).
5. **Verificar qué va a entrar a git ANTES de commitear:**
   `git status` — NO deben aparecer `03. CFDI DE NOMINA/`, `VERIFICACION_NOMINAS.md`,
   ningún `.env` ni `settings.local.json`. Con el `.gitignore` nuevo quedan cubiertos.
   Sí deben aparecer: CLAUDE.md, backlog.md, .claude/ (settings, hook, agente),
   .github/, .gitignore, y los `.env.example` (que el gitignore viejo ignoraba por error).
6. Commitear en una rama y abrir el **primer PR del nuevo flujo**:
   `git checkout -b chore/sistema-b && git add -A && git status` (revisar de nuevo)
   → commit → push → `gh pr create`. El CI debe correr por primera vez y salir verde
   (backend: 93 tests; frontend: build). Merge y a trabajar.
7. Opcional pero recomendado: en GitHub, Settings → Branches → proteger `main`
   (requerir PR + CI en verde). Con eso el "push directo a main" deja de ser posible
   ni por accidente.

## Notas de diseño (por qué así)

- El CI arranca **solo con lo que hoy está verde** (pytest + build). Los pasos de
  `ruff`, `lint` y `npm test` están comentados en `ci.yml` y se descomentan al cerrar
  S-01, S-02 y S-05 del backlog. Así el CI nace verde y se endurece por etapas, en vez
  de nacer en rojo y acostumbrarte a ignorarlo.
- `defaultMode: acceptEdits` + hook = casi cero interrupciones: solo pregunta
  `git push` (deliberado) y comandos raros. Las paradas de plan/resultado son del
  CLAUDE.md, no de permisos.
- Los dos CLAUDE.md de apps se quedan como contexto técnico. La orquestación vive
  solo en el de la raíz (Claude Code lo carga siempre; los de apps se cargan al
  trabajar en cada una). Cuando cierres S-03, recorta de ambos las secciones de
  contrato duplicadas.
- Los `settings.local.json` viejos pueden quedarse (son locales); las rutas obsoletas
  que tienen no estorban, solo son permisos que ya no matchean.

## Primer prompt para Claude Code (después del merge del PR de instalación)

> Lee CLAUDE.md y backlog.md. Empezamos con la tarea S-01 (lint backend a cero y
> cablearlo al CI). Propón el plan y pásalo por el revisor antes de mostrármelo.

## Hook `pre-push` (la copia viva NO se versiona — instalarla en cada clon)

`.git/hooks/` vive fuera del control de versiones, así que el hook **no viaja con el repo**:
en un clon nuevo hay que instalarlo o no habrá guardia. La copia buena está versionada en
**`scripts/git-hooks/pre-push`**; instalarla es copiarla y darle permiso de ejecución:

```sh
cp scripts/git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

`.gitattributes` fija esa copia con finales **LF** (`scripts/git-hooks/pre-push text eol=lf`).
No es cosmético: este repo convierte a CRLF por defecto, y un `#!/bin/sh` con un `\r` pegado
instala un hook que se ve bien y **no corre**.

Qué hace: al empujar a `main`, rechaza el push si el rango toca cualquier archivo que no sea
`backlog.md` o `docs/nocturno-log.md`. Todo lo demás pasa por PR. Es la guardia real del
**modo autónomo**, porque `main` no puede protegerse en GitHub: el repo es privado en plan
gratuito y la API de branch protection responde 403 pidiendo GitHub Pro.

### Es fail-closed, y no siempre lo fue

Dos agujeros, los dos del mismo tipo — la guardia cayéndose sola justo en el caso raro:

1. **Rango que no resuelve** (un SHA remoto que ya no existe en local, historia reescrita).
   `git diff` truena, y en la versión original el `for` simplemente no iteraba sobre nada:
   **el push pasaba**. Ahora el `|| { ...; exit 1; }` lo bloquea con mensaje propio.
2. **`remote_sha` en ceros** (main no existe en el remoto, o se borró y se recrea). Ahí no
   hay rango, y `git diff --name-only <sha>` compara ese commit contra el **árbol de
   trabajo**, no contra el árbol vacío: con el árbol limpio la lista sale vacía y pasaba
   cualquier contenido. Medido en este repo: `exit 0` empujando un commit que tocaba
   `apps/api/tests/...`. Ahora esa rama usa `git diff-tree --root`.

**Límite conocido, anotado a propósito:** en la rama de ceros el hook mira sólo el commit de
la punta. Si se crea `main` en un commit cuya punta toca sólo `backlog.md` pero cuyos
ancestros tocan otra cosa, pasa. Cerrarlo pide `git log --format= --name-only "$local_sha"`,
que recorre todo lo alcanzable. Está sin hacer por decisión, no por descuido. Y `git diff
A..B` es el diff **neto**: un archivo agregado en un commit y borrado en otro dentro del
mismo push no aparece aquí.

**Lo que ninguna versión de este hook puede:** `git push --no-verify` lo brinca entero. Por
eso está prohibido en `CLAUDE.md` (sección *Modo autónomo*, bullet de prohibiciones) — contra
eso no hay mecanismo, sólo protocolo.

### Comprobarlo sin empujar nada

El hook lee las refs de stdin, así que se le pueden dar a mano. Con SHAs reales del repo:

```sh
# 1. Rango que sólo toca backlog.md            -> exit 0
echo "refs/heads/main <nuevo> refs/heads/main <viejo>" | sh .git/hooks/pre-push; echo $?

# 2. Rango que toca cualquier otro archivo     -> exit 1, y dice cuál
echo "refs/heads/main <nuevo> refs/heads/main <viejo-lejano>" | sh .git/hooks/pre-push; echo $?

# 3. SHA remoto inventado                      -> exit 1 (antes del fix: exit 0)
echo "refs/heads/main <nuevo> refs/heads/main 0123456789abcdef0123456789abcdef01234567" | sh .git/hooks/pre-push; echo $?

# 4. Rama de ceros con un commit que toca otra cosa -> exit 1 (antes del fix: exit 0)
echo "refs/heads/main <sha> refs/heads/main 0000000000000000000000000000000000000000" | sh .git/hooks/pre-push; echo $?
```

## Orquestador nocturno

`scripts/nocturno-v2.ps1` es el que se usa. Abre el panel interactivo de Claude Code por
tarea y un vigilante mira el repo cada minuto; la sesión avisa cómo terminó dejando un
centinela vacío en la raíz (`TAREA_CERRADA.txt`, `TAREA_SALTADA.txt`, `COLA_VACIA.txt`), que
está gitignorado y que el loop borra al empezar cada vuelta. El protocolo que la sesión debe
seguir está en `CLAUDE.md`, sección *Modo autónomo*.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\nocturno-v2.ps1 -MaxTareas 6
```

`scripts/nocturno.ps1` (v1) está **SUPERADO**: corre en modo `-p` y busca el resultado en la
salida de texto, que ya nadie imprime. Se conserva como referencia.
