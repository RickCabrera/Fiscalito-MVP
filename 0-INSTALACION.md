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
