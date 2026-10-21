"""
Rutas de nómina (F1-07, hecho en P0-08): un paquete en vez de un archivo de 550 líneas.

- `periodo.py` — `GET /nomina/periodo-sugerido`, `GET /nomina/demo/plantilla`,
  `POST /nomina/sbc`.
  `POST /nomina/calcular-periodo` vive en `routes/nomina_periodo.py` (P4-01: plantilla
  de la cartera).
- `cfdi.py` — `POST /nomina/cfdi` (pre-recibo sin timbrar).

Mismas URLs, mismo orden de registro y mismo comportamiento que `routes/nomina.py`: el
OpenAPI exportado (`docs/openapi.json`) no cambió con la mudanza, y eso lo verifica
`tests/test_contrato_openapi.py`. `app/main.py` sigue montando `nomina.router`.

El calendario patronal (`GET /despacho/calendario`) se queda en `routes/despacho.py`: moverlo
cambiaría su tag en el OpenAPI y el backlog pide no crear un segundo endpoint de calendario.
"""

# El orden de import es el orden de registro de las rutas: periodo antes que cfdi.
from app.routes.nomina import periodo  # noqa: F401, I001
from app.routes.nomina import cfdi  # noqa: F401, I001
from app.routes.nomina._comun import router

__all__ = ["router", "periodo", "cfdi"]
