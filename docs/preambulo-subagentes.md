# Preámbulo para cada tarea del plan P (léelo completo antes de empezar)

Trabajas en el repo Fiscalito (monorepo: `apps/api` FastAPI/Python, `apps/store` React/Vite/TS).
Producto: suite contable-fiscal-nómina SOLO para despachos contables mexicanos que llevan varias
empresas (clientes). Objetivo del plan: paridad con Contadigital. La tarea que te toca viene en tu
prompt con su "Listo cuando" — es lo que se mide.

## Lee primero
- `docs/arquitectura-p.md` (convenciones OBLIGATORIAS: tenencia, adaptadores, trabajos, tests).
- `backlog.md` sección "P — Plan de paridad" (tu tarea y su contexto).
- `apps/api/CLAUDE.md` y/o `apps/store/CLAUDE.md` según lo que toques (el recuadro K de arriba manda).
- El código existente que vas a tocar. Reusa lo que hay (motor `app/fiscal_engine`, `app/nomina_engine`,
  `app/tenancy.py`, `app/integraciones/registro.py`, `src/services/api.ts`).

## Entorno
- Backend: desde `apps/api`, usa `/home/claude/fiscalito-mvp/apps/api/.venv/bin/python -m pytest -q -p no:cacheprovider`
  y `/home/claude/fiscalito-mvp/apps/api/.venv/bin/ruff check <archivos>`. Ejecútalo SIEMPRE con
  `python -m pytest` desde el `apps/api` de TU árbol de trabajo (así se importa tu `app/`, no el de otro
  árbol). Si necesitas una dependencia nueva, agrégala a `pyproject.toml` y avísalo en tu reporte; instálala
  con `/home/claude/fiscalito-mvp/apps/api/.venv/bin/pip install <pkg>`.
- Frontend: si tu árbol no tiene `apps/store/node_modules`, crea un symlink:
  `ln -s /home/claude/fiscalito-mvp/apps/store/node_modules apps/store/node_modules`. Checks:
  `npx tsc --noEmit`, `npx vitest run <tus tests>`, `npx eslint <tus archivos>`.
- Sin red hacia servicios externos. Ningún test toca la red.

## Reglas
- Toda ruta de negocio usa `contexto_actual` + `cliente_o_404`. Prueba multi-tenant (despacho B no ve A).
- Servicios externos SOLO por adaptador con implementación `falso` + real; documenta variables en
  `docs/servicios-externos.md` (créalo si no existe; una sección por servicio: qué es, variables,
  cómo se prueba, a quién contratar).
- El LLM nunca calcula impuestos. Tablas fiscales con fuente oficial citada en docstring. Si no tienes la
  fuente exacta, deja el valor como parámetro configurable con comentario `# FUENTE POR CONFIRMAR:` y
  repórtalo — nunca inventes una cifra legal en silencio.
- Criterios que dependen del despacho/contadora: configurables por cliente con default documentado.
- No borres ni debilites tests existentes salvo que el comportamiento que prueban se haya retirado.
- Archivos front ≤ 300 líneas; CSS solo con variables de `global.css`; textos en español.
- Endpoints nuevos: agrégalos a `docs/api-contract.md` (sección por módulo, breve).
- Monta tus routers en `app/main.py` (`app.include_router(x.router, prefix="/api/v1")`) y tus modelos en
  `app/modelos/__init__.py`. Si tocas navegación del front, `src/services/navigation.ts` + `AppRoutes.tsx`.
- NO hagas git push, NO hagas merge, NO toques otras ramas. Al terminar: `git add -A && git commit` en tu
  árbol con mensaje `P<x>-<yy>: <resumen>` y autor ya configurado. No configures otro autor.

## Reporte final (corto, en español)
Rama/commit, qué quedó, tests (conteo), dependencias nuevas, variables nuevas, y lo que NO quedó o
quedó con `FUENTE POR CONFIRMAR`.
