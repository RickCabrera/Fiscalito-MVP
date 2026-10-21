# Despliegue de Fiscalito (P6-03)

Una imagen de la API (`apps/api/Dockerfile`) corre tres procesos con distinto comando, más el
front (`apps/store/Dockerfile`, nginx con el build de Vite) y Postgres. **No hay Redis**: la
cola de trabajos vive en Postgres (`FOR UPDATE SKIP LOCKED`, `app/modelos/trabajos.py`) y el
código no usa Redis en ningún lado; el backlog lo mencionaba como opción, no como requisito.

| Servicio | Comando | Qué hace | Salud |
|---|---|---|---|
| `api` | `arranque api` | `alembic upgrade head` y luego uvicorn. **Si la migración falla, no arranca** (exit 1). | `GET /health` |
| `worker` | `arranque worker` | Corre la cola (`python -m app.trabajos.worker --sin-programacion`). | `arranque salud worker` |
| `programador` | `arranque programador` | Encola las tareas recurrentes (respaldos, SAT, alertas, cobranza). **Una sola réplica** (dos no duplican —cada ranura se reclama una vez— pero no aportan nada). | `arranque salud programador` |
| `store` | nginx | La SPA; `/salud` responde 200. | `GET /salud` |
| `postgres` | — | Datos. | `pg_isready` |

`arranque` es `apps/api/docker/arranque.sh`. Sólo la API migra (dos procesos no corren Alembic
a la vez); worker y programador reintentan solos mientras el esquema no está listo, y cada
vuelta deja un latido que `GET /health` lee (`procesos.worker.vivo`, etc.).

## En local, igual que en producción

```bash
# 1) Secretos (un .env junto a docker-compose.yml; docker compose lo lee solo)
python -c "from cryptography.fernet import Fernet; print('FISCALITO_LLAVE_MAESTRA=' + Fernet.generate_key().decode())" >> .env
python -c "import secrets; print('FISCALITO_ENLACES_SECRETO=' + secrets.token_urlsafe(48))" >> .env
# y las VITE_FIREBASE_* del proyecto de Firebase (login)

# 2) Todo arriba
docker compose up --build

# 3) Verificar
curl -s localhost:8000/health | python -m json.tool        # status ok cuando worker y programador laten
curl -s localhost:8000/health/integraciones | python -m json.tool
open http://localhost:8080
```

El compose corre con `FISCALITO_ENTORNO=produccion` (sin atajos de desarrollo, sin
`create_all`, sin llave efímera), Postgres 16, almacenamiento en un volumen compartido por API
y worker (`FISCALITO_ALMACENAMIENTO=local`) y los demás adaptadores en `falso` **explícito**
(en producción no hay `falso` implícito). Cambiar uno es poner su variable en `.env`.

Comandos útiles:
- `docker compose run --rm api migrar` — sólo migraciones.
- `docker compose run --rm api python -m scripts.cifrar_datos_sensibles` — cifrar CLABE que
  haya quedado en claro tras configurar la llave.
- `docker compose logs -f worker` — logs JSON (`proceso`, `trabajo_id`, `despacho_id`...).

**Validación hecha en este entorno:** `docker compose config` pasa. No había demonio de
Docker ni `hadolint`, así que las imágenes **no se construyeron aquí**: los Dockerfiles se
revisaron a mano y el script de arranque se prueba con `tests/test_arranque.py` (migra antes
de servir; migración fallida = no arranca). Primer `docker compose up --build` real: pendiente
(EXT-01).

## Railway

Un proyecto con cinco servicios desde este repo:

| Servicio | Root directory | Config file | Variables mínimas |
|---|---|---|---|
| Postgres | (plugin) | — | — |
| `api` | `apps/api` | `apps/api/railway.json` | `DATABASE_URL` (referencia al plugin), `FISCALITO_ENTORNO=produccion`, `FISCALITO_LLAVE_MAESTRA`, `FISCALITO_ENLACES_SECRETO`, `FISCALITO_URL_PUBLICA_API`, `FISCALITO_URL_APP`, `CORS_ORIGINS`, `FIREBASE_PROJECT_ID`, un `FISCALITO_<SERVICIO>` por adaptador |
| `worker` | `apps/api` | `apps/api/railway.worker.json` | las mismas que `api` (comparte variables) |
| `programador` | `apps/api` | `apps/api/railway.programador.json` | las mismas que `api` |
| `store` | `/` (raíz: el lock de npm es del workspace) | `apps/store/railway.json` | `VITE_FISCAL_AGENT_URL` (dominio de `api`), `VITE_FIREBASE_*`, `VITE_RESPONSABLE_*` — **son de build**: cambiarlas exige redeploy |

- El almacenamiento en Railway es S3/R2 (`FISCALITO_ALMACENAMIENTO=s3` + `FISCALITO_S3_*`): los
  contenedores no comparten disco.
- `api` tiene `healthcheckPath: /health` (siempre 200 si la API vive; el detalle de worker y
  programador va en el cuerpo).
- La lista completa de variables está en `apps/api/.env.example` y `apps/store/.env.example`;
  `apps/api/tests/test_env_example.py` falla si el código usa una que no esté ahí.
- Qué cuenta crear y cómo probar cada servicio externo: `docs/servicios-externos.md` (y el
  runbook de P6-06).
