#!/bin/sh
# Arranque del contenedor de la API (P6-03). Una imagen, tres procesos:
#   arranque api          migraciones (alembic upgrade head) y luego uvicorn
#   arranque worker       la cola de trabajos (sin programación: la lleva el programador)
#   arranque programador  encola las tareas recurrentes
#   arranque migrar       sólo las migraciones
#   arranque salud <worker|programador>  exit 0 si ese proceso latió hace poco
# Cualquier otro comando se ejecuta tal cual (p. ej. `arranque python -m scripts.x`).
#
# FAIL-CLOSED: si la migración falla, la API NO arranca (sale con 1 y Railway no promueve el
# despliegue). Sólo la API migra, para que dos procesos no corran Alembic a la vez; el worker y
# el programador reintentan solos mientras el esquema no está listo.
set -eu

proceso="${1:-api}"
if [ "$#" -gt 0 ]; then
  shift
fi

migrar() {
  echo "arranque: alembic upgrade head"
  if ! alembic upgrade head; then
    echo "arranque: FALLÓ la migración; el servicio no arranca." >&2
    exit 1
  fi
}

case "$proceso" in
  api)
    if [ "${FISCALITO_MIGRAR_AL_ARRANCAR:-1}" = "1" ]; then
      migrar
    fi
    # --no-access-log: el checador manda su token en ?token= y el access log lo escribiría.
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log "$@"
    ;;
  worker)
    exec python -m app.trabajos.worker --sin-programacion "$@"
    ;;
  programador)
    exec python -m app.trabajos.programador "$@"
    ;;
  migrar)
    migrar
    ;;
  salud)
    exec python -m app.observabilidad "$@"
    ;;
  *)
    exec "$proceso" "$@"
    ;;
esac
