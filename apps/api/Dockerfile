# Fiscal Agent API — una imagen para los tres procesos (P6-03):
#   api (default) · worker · programador   →  ver docker/arranque.sh
# Railway: un servicio por proceso con la misma imagen y distinto comando
# (apps/api/railway*.json). Local: docker-compose.yml en la raíz. Guía: docs/despliegue.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    FISCALITO_ALMACEN_DIR=/app/almacen

WORKDIR /app

# Usuario sin privilegios; el almacén local (si se usa en vez de S3/R2) le pertenece.
RUN useradd --create-home --uid 10001 fiscalito \
    && mkdir -p /app/almacen \
    && chown fiscalito:fiscalito /app/almacen

# Dependencias primero (capa cacheable): sin `app/` todavía, `pip install .` sólo instala
# las dependencias de pyproject.toml.
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY migrations/ migrations/
COPY app/ app/
COPY scripts/ scripts/
COPY --chmod=755 docker/arranque.sh /usr/local/bin/arranque

USER fiscalito
EXPOSE 8000

# El healthcheck vive en cada servicio (compose / railway.json): la misma imagen corre el
# worker, que no escucha HTTP.
ENTRYPOINT ["/usr/local/bin/arranque"]
CMD ["api"]
