"""
Exporta las rutas que la API publica a `apps/store/src/services/rutasBackend.json`.

POR QUÉ EXISTE
--------------
El 2026-09-02 el calendario patronal dio 404 en el navegador. No era un bug de
path —la ruta existía y respondía 200—, pero el episodio dejó ver un agujero
real: **nada compara lo que el front pide contra lo que el backend publica**. El
test de backend de E-07 pega al router montado pero *hardcodea* la ruta, y los
tests de front stubbean `fetch`. Las dos mitades pueden estar verdes con paths
distintos cada una.

Este archivo es la mitad del puente. La otra mitad son dos tests:

- `apps/api/tests/test_rutas_publicadas.py` — que el JSON no se quede viejo
  respecto de `app.main:app`.
- `apps/store/src/services/contratoRutas.test.ts` — que cada función del front
  arme una URL que esté en el JSON.

Ninguno de los dos parsea el lenguaje del otro, y cada uno falla en el job de
CI donde está el culpable.

USO
---
    cd apps/api && python scripts/exportar_rutas.py

No se corre en CI: el test de arriba **falla** si el JSON quedó desactualizado y
dice este comando. Regenerarlo automáticamente convertiría una divergencia real
en un archivo que se arregla solo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.main import app

# Verbos que FastAPI agrega solo y que nadie llama desde el front.
METODOS_IGNORADOS = frozenset({"HEAD", "OPTIONS"})

DESTINO = Path(__file__).resolve().parents[3] / "apps/store/src/services/rutasBackend.json"


def rutas_publicadas() -> list[dict[str, Any]]:
    """
    Las rutas de la app real, ordenadas y estables.

    SE LEE DEL OPENAPI, NO DE `app.routes`
    --------------------------------------
    La primera versión recorría `app.routes` y leía `route.methods`. Pasaba en
    local (starlette 1.0) y devolvía **cero rutas** en CI (starlette 1.6), donde
    ese atributo dejó de ser legible como se esperaba: el filtro `if not metodos`
    descartaba las 18 en silencio y el test acusaba "contrato desactualizado"
    cuando lo que estaba roto era el exportador. Un exportador que se cae hacia
    la lista vacía es la peor forma de fallar, porque parece un diff.

    `app.openapi()` es contrato público de FastAPI, estable entre versiones, y
    además es **exactamente lo que el front consume**. De paso resuelve solo lo
    que antes era una lista negra: `/docs`, `/openapi.json` y `/redoc` no
    aparecen en el esquema.

    Los métodos se agrupan **por path**, una entrada por ruta. Emitir una
    entrada por combinación (path, método) hacía que
    `/api/v1/asistencia/eventos` apareciera dos veces (GET y POST), y el lado
    del front busca por path y se queda con la primera: un POST legítimo a esa
    ruta habría fallado acusando un método que el backend sí acepta.

    Raises:
        RuntimeError: si el esquema sale vacío. Es el modo de falla de arriba, y
            reventar es lo correcto: escribir `{"rutas": []}` dejaría el contrato
            en un estado que se lee como "la API no publica nada".
    """
    esquema = app.openapi()
    por_path: dict[str, set[str]] = {}
    for path, operaciones in esquema.get("paths", {}).items():
        visibles = {
            metodo.upper()
            for metodo in operaciones
            if metodo.upper() not in METODOS_IGNORADOS
        }
        if visibles:
            por_path[path] = visibles

    if not por_path:
        raise RuntimeError(
            "El OpenAPI de app.main:app salió sin rutas. No es que la API no "
            "publique nada: es que este exportador dejó de entender el esquema. "
            "Arréglalo aquí en vez de regenerar el contrato en vacío."
        )

    return [
        {"path": path, "metodos": sorted(por_path[path])} for path in sorted(por_path)
    ]


def contenido() -> str:
    documento = {
        "_generado_por": "apps/api/scripts/exportar_rutas.py",
        "_no_editar_a_mano": (
            "Regenera con `cd apps/api && python scripts/exportar_rutas.py`. "
            "Lo verifica tests/test_rutas_publicadas.py."
        ),
        "_para_que_sirve": (
            "Contrato de rutas entre apps/api y apps/store. "
            "apps/store/src/services/contratoRutas.test.ts afirma que cada URL "
            "que el front construye está aquí."
        ),
        "rutas": rutas_publicadas(),
    }
    return json.dumps(documento, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    DESTINO.write_text(contenido(), encoding="utf-8")
    # Sin flechas ni acentos: la consola de Windows es cp1252 y reventaria.
    print(f"{len(rutas_publicadas())} rutas -> {DESTINO}")
