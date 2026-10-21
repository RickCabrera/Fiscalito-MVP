#!/usr/bin/env bash
# Levanta la API de Fiscalito para las pruebas de punta a punta (P6-04).
#
# Lo arranca `playwright.config.ts` (webServer); también sirve a mano para depurar:
#   PYTHON=apps/api/.venv/bin/python apps/store/e2e/levantar.sh
#
# Qué levanta: uvicorn + worker de la cola, contra una SQLite TEMPORAL nueva en cada
# corrida, con TODOS los adaptadores en `falso` (SAT, PAC, correo, WhatsApp, almacenamiento
# local) y `FISCALITO_ENTORNO=desarrollo`.
#
# Autenticación: el front e2e manda el uid como token (`src/e2e/firebaseAuthFalso.ts`) y
# la API lo acepta SÓLO con su atajo de pruebas, que exige dos variables a la vez y está
# vetado en producción (`app/auth_firebase.sin_verificar_activo`). `FIRESTORE_EMULATOR_HOST`
# apunta a un puerto donde no escucha nadie: el backend ya no lee Firestore (R-11), la
# variable sólo es la segunda llave del atajo.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$AQUI/../../api" && pwd)"
PYTHON="${PYTHON:-python}"
PUERTO="${E2E_PUERTO_API:-8765}"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fiscalito-e2e.XXXXXX")"
export DATABASE_URL="sqlite:///$TMP/e2e.db"
export FISCALITO_ENTORNO=desarrollo
export FISCALITO_ALMACEN_DIR="$TMP/almacen"
export FIRESTORE_EMULATOR_HOST=127.0.0.1:9
export PERMITIR_TOKEN_SIN_VERIFICAR=1
export CORS_ORIGINS="*"
export FISCALITO_URL_PUBLICA_API="http://127.0.0.1:$PUERTO"
export FISCALITO_ENLACES_SECRETO="secreto-solo-e2e"
# Un recorrido hace cientos de peticiones con el mismo uid; el límite de producción no
# es lo que se prueba aquí.
export FISCALITO_RATE_LIMIT_POR_MINUTO=5000
# Sin llaves de LLM: las explicaciones caen al texto estático (el LLM nunca calcula).
export LLM_PROVIDER=openai
export OPENAI_API_KEY=""
export ANTHROPIC_API_KEY=""
# Llave fija de la corrida: API y worker son dos procesos y los dos tienen que poder
# descifrar la e.firma (la efímera de desarrollo es una por proceso).
FISCALITO_LLAVE_MAESTRA="$("$PYTHON" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export FISCALITO_LLAVE_MAESTRA

# SAT falso CON datos: los CFDI sintéticos del mes anterior del cliente del recorrido
# (`e2e/cfdis.py`), y la primera verificación al segundo en vez de a los dos minutos.
RFC_E2E="${E2E_RFC:-SIN010101AB1}"
MES_E2E="$("$PYTHON" -c 'from datetime import date, timedelta; print((date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m"))')"
"$PYTHON" "$AQUI/cfdis.py" "$TMP/sat" "$RFC_E2E" "$MES_E2E"
export FISCALITO_SAT_FALSO_DIR="$TMP/sat"
export FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION=1

# Los logs de API y worker van a un archivo (CI lo sube si el recorrido falla); en la
# consola de Playwright sólo estorban.
LOG="${E2E_LOG:-$AQUI/../e2e-logs/api.log}"
mkdir -p "$(dirname "$LOG")"
: > "$LOG"

cd "$API_DIR"
"$PYTHON" -c 'from app.db.session import crear_tablas; crear_tablas()' >> "$LOG" 2>&1

"$PYTHON" -m app.trabajos.worker --pausa 0.5 >> "$LOG" 2>&1 &
WORKER=$!
trap 'kill "$WORKER" 2>/dev/null || true; rm -rf "$TMP"' EXIT INT TERM

"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PUERTO" --log-level warning >> "$LOG" 2>&1
