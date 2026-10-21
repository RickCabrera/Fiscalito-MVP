# Arquitectura del plan P — convenciones obligatorias

Este documento manda sobre cómo se construye cualquier tarea del plan P (`backlog.md`, sección P).
Si una tarea necesita romper una convención, se escribe aquí primero.

## Backend (`apps/api`)

**Persistencia (DP-1).** SQLAlchemy 2 (ORM tipado). `DATABASE_URL` decide el motor: Postgres en
Railway, SQLite local por default. Modelos en `app/modelos/<dominio>.py`, importados desde
`app/modelos/__init__.py`. Base y mixin de marcas de tiempo en `app/db/base.py`. Sesión por request
con `Depends(obtener_db)` (`app/db/session.py`). En desarrollo las tablas se crean al arrancar; las
migraciones Alembic se generan al cierre de cada fase (no en cada tarea).
- Usa tipos portables (`JSON`, `String`, `Numeric`, `DateTime(timezone=True)`); nada específico de
  Postgres salvo detrás de un `if dialecto`.
- Dinero: `Numeric(18, 2)` y `Decimal` en Python. Nunca `float` para importes nuevos.

**Tenencia.** Toda ruta de negocio depende de `contexto_actual` (`app/tenancy.py`) y obtiene clientes
SÓLO con `cliente_o_404(ctx, clave)` o `clientes_visibles(ctx)`. Todo modelo con datos de negocio
cuelga de `clientes.id` o lleva `despacho_id`. Cliente de otro despacho = **404**, nunca 403.

**Servicios externos.** Cada uno en `app/integraciones/<servicio>.py`: un `Protocol`, una clase
`...Falso` determinística sin red, y las reales. Se registran con
`registro.registrar("<servicio>", "<nombre>", fabrica, descripcion)` al importar el módulo y se
obtienen con `registro.obtener("<servicio>")`. La variable `FISCALITO_<SERVICIO>` elige; sin ella,
`falso` fuera de producción. Toda variable nueva se documenta en `docs/servicios-externos.md`.
**Ningún test toca la red.** Las implementaciones reales se prueban con respuestas grabadas
(fixtures en `tests/fixtures/<servicio>/`).

**Trabajos en segundo plano.** Cola en la propia base (`app/trabajos/`): `encolar(db, tipo, carga,
ejecutar_en=None, clave_unica=None)`; manejadores registrados por `tipo`; worker
`python -m app.trabajos.worker`; tareas recurrentes declaradas en `app/trabajos/programacion.py`.
Todo trabajo debe ser **idempotente** (puede correr dos veces).

**Errores.** Desde el dominio se lanza `FiscalAgentError(msg, status_code)`; el handler global la
serializa a `{"exito": false, "error": msg}`.

**Motor.** El LLM nunca calcula. Tablas fiscales con fuente oficial citada. Cálculo nuevo de motor →
revisor de motor. Parámetros que dependen del criterio del despacho (DP-3) son **configurables por
cliente** con un default documentado, nunca constantes escondidas.

**Rutas.** Routers en `app/routes/`, montados en `app/main.py` bajo `/api/v1`. Esquemas Pydantic en
`app/schemas/`. Respuestas con `exito: bool`. Todo endpoint nuevo entra a `docs/api-contract.md`.

**Tests.** pytest, sin red. Fixtures de `tests/conftest.py`:
- `db_sesion`: sesión SQLite en memoria con todas las tablas.
- `api("uid")`: `TestClient` autenticado como ese uid (cada uid nuevo = su propio despacho).
Prueba siempre el caso multi-tenant: el despacho B no ve lo del despacho A.

## Frontend (`apps/store`)

React 19 + Vite + TS estricto, CSS con variables de `global.css` (sin frameworks CSS), máx. 300
líneas por archivo, loading y error en toda llamada. Llamadas a la API con `apiFetch` de
`src/services/api.ts` (adjunta el ID token de Firebase). Pantallas nuevas en `src/pages/`,
componentes en `src/components/<modulo>/`, navegación en `src/services/navigation.ts`. Tests con
Vitest + Testing Library, red cerrada (stub de `fetch`).

## Checks antes de entregar
- `apps/api`: `pytest -q` verde, `ruff check .` limpio en lo tocado.
- `apps/store`: `npm run build` limpio, `npm test` verde, `npm run lint` sin errores nuevos.
- `apps/store`: `npm run lint` sale en 0 (P6-05, S-02) y corre en CI; quedan sólo *warnings* de
  `react-refresh/only-export-components` en los contextos (`useAuth`, `useProfile`, `useAgent`
  conviven con su provider; moverlos rompería los `vi.mock` de decenas de pruebas a cambio de
  nada en producción).

## Decisión R-11 · El emulador de Firestore NO entra al CI (P6-05)

**Decisión: no se agrega un job con `firebase-tools` al CI.** No hace falta: desde P0-01 la
cartera vive en SQL y los criterios que sólo medía el emulador —"sobrevive reinicio", borrado en
cascada, merge, topes— se prueban contra la base de verdad (`tests/cartera/test_cartera_crud.py`,
SQLite en tests, Postgres en producción). Ya no existe ningún test marcado `emulador`; el filtro
`-m "not emulador"` se retiró de `pyproject.toml`, así que **verde en CI vuelve a significar "toda
la suite corrió"**, sin skips.

Lo que sigue tocando Firebase en el backend es la verificación del ID token
(`app/auth_firebase.py`), que se prueba con tokens falsos y con la guardia de
`FIRESTORE_EMULATOR_HOST` (`tests/cartera/test_auth_firebase.py`,
`tests/plan_p/test_revision_p0.py`); ninguna de esas pruebas necesita el emulador corriendo.
Firestore en el front sólo guarda el perfil (`users/{uid}`) y el historial de declaraciones, y
sus pruebas usan mocks de `services/firebase`.

**Cuándo revisar esta decisión:** si vuelve a aparecer código del backend que lea o escriba
Firestore, o un test marcado `emulador`. En ese caso el job es `npx firebase-tools emulators:exec
--only firestore "pytest -m emulador"` y entra al gate.
