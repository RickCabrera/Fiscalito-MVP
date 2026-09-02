"""
El contrato de rutas entre `apps/api` y `apps/store` no se queda viejo.

QUÉ PRUEBA ESTO Y QUÉ NO
------------------------
Prueba que `apps/store/src/services/rutasBackend.json` sea exactamente lo que
publica la app **real** (`app.main:app`), no una lista que alguien escribió a
mano y que envejeció. **No** prueba que el front pida esas rutas: eso es
`apps/store/src/services/contratoRutas.test.ts`, que corre en el job de
frontend porque es ahí donde estaría el culpable.

Las dos mitades juntas son lo que faltaba el 2026-09-02, cuando el calendario
patronal dio 404 en el navegador: el test de backend de E-07 pega al router
montado pero **hardcodea** la ruta, y los tests de front stubbean `fetch`. Las
dos mitades pueden estar verdes con paths distintos cada una, y nadie se entera
hasta que se abre el navegador.

POR QUÉ FALLA EN VEZ DE REGENERAR
---------------------------------
Un test que arregla lo que encuentra no encuentra nada. Si el JSON quedó viejo,
este test falla y dice el comando; regenerarlo es una decisión de quien cambió
la ruta, porque implica revisar si el front todavía la llama.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts.exportar_rutas import DESTINO, rutas_publicadas

COMANDO = "cd apps/api && python scripts/exportar_rutas.py"


@pytest.fixture(scope="module")
def documento() -> dict:
    """
    El JSON versionado.

    **Falla si no existe, no skipea.** Un skip aquí es el mismo agujero con otra
    cara: la suite quedaría verde declarando que el contrato está verificado
    justo cuando el archivo que lo define desapareció.
    """
    assert DESTINO.exists(), (
        f"No existe {DESTINO}. Es el contrato de rutas con apps/store. "
        f"Genéralo con: {COMANDO}"
    )
    return json.loads(DESTINO.read_text(encoding="utf-8"))


def test_el_json_versionado_coincide_con_la_app_real(documento):
    publicadas = rutas_publicadas()
    guardadas = documento["rutas"]

    faltan = [r for r in publicadas if r not in guardadas]
    sobran = [r for r in guardadas if r not in publicadas]

    assert not faltan and not sobran, (
        "El contrato de rutas quedó desactualizado.\n"
        f"  En la app pero NO en el JSON: {faltan}\n"
        f"  En el JSON pero NO en la app: {sobran}\n"
        f"Si el cambio es intencional, regenera con: {COMANDO}\n"
        "y revisa si apps/store todavía llama las rutas que se fueron."
    )


def test_el_json_no_esta_vacio(documento):
    """
    Guarda contra el fallo silencioso.

    Un exportador roto que escriba `{"rutas": []}` haría pasar el test de arriba
    —cero contra cero cuadra— y el del front no tendría contra qué comparar.
    """
    assert len(documento["rutas"]) >= 15, (
        f"Sólo {len(documento['rutas'])} rutas en el contrato. La API publica "
        "bastantes más; esto huele a exportador roto, no a limpieza."
    )


def test_el_calendario_patronal_esta_publicado(documento):
    """
    El caso concreto del 2026-09-02, anclado.

    Vale la pena aparte del test genérico: si algún día esta ruta desaparece o
    cambia de path, el mensaje de error debe nombrar el episodio en vez de
    aparecer como un renglón más de un diff.
    """
    paths = {r["path"] for r in documento["rutas"]}
    assert "/api/v1/despacho/calendario" in paths, (
        "Se fue /api/v1/despacho/calendario, que es la ruta que "
        "CalendarioPatronalPage consume. Si el cambio es a propósito, mueve "
        "también obtenerCalendarioPatronal en apps/store/src/services/despachoApi.ts."
    )


def test_ningun_404_del_backend_viaja_con_detail_string():
    """
    El invariante del que cuelga `apps/store/src/services/errorApi.ts`.

    El front distingue dos 404: el de dominio, que sale con sobre propio
    (`{exito, error}`) por el handler global, y el pelón de FastAPI
    (`{"detail": "Not Found"}`), que significa *el backend que respondió no
    conoce esta ruta*. Esa discriminación sólo es válida mientras el dominio no
    levante `HTTPException(404)`: el día que alguien lo haga, la pantalla dirá
    "el backend no reconoce esta llamada" para un recurso que simplemente no
    existe, y mandará a reiniciar un servidor sano.

    Hoy es cierto por convención (`apps/api/CLAUDE.md`: el dominio levanta
    `FiscalAgentError`, nunca `HTTPException`). Este test lo vuelve mecánico.

    Se busca con AST y no con `grep`: el patrón CORRECTO es
    `FiscalAgentError(..., status_code=404)`, así que buscar el texto
    "status_code=404" acusa justo lo que se quiere. Lo que importa es de qué
    clase es la excepción.
    """
    infractores = []
    for ruta in (Path(__file__).resolve().parents[1] / "app").rglob("*.py"):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = nodo.func.id if isinstance(nodo.func, ast.Name) else None
            if nombre != "HTTPException":
                continue
            codigos = [
                a.value for a in nodo.args if isinstance(a, ast.Constant)
            ] + [
                k.value.value
                for k in nodo.keywords
                if k.arg == "status_code" and isinstance(k.value, ast.Constant)
            ]
            if 404 in codigos:
                infractores.append(f"{ruta.name}:{nodo.lineno}")

    assert not infractores, (
        f"Hay un 404 levantado como HTTPException en {infractores}. "
        "El front lo leería como 'ruta inexistente' (ver errorApi.ts) y "
        "mandaría a reiniciar un servidor sano. Usa FiscalAgentError, que sale "
        "con el sobre {exito, error}."
    )


def test_el_generador_escribe_donde_el_front_lo_lee():
    """
    `DESTINO` es la única cosa que amarra los dos lados. Si alguien la mueve sin
    mover el import del test de vitest, los dos tests siguen verdes y dejan de
    hablar del mismo archivo.
    """
    esperado = Path("apps") / "store" / "src" / "services" / "rutasBackend.json"
    assert DESTINO.as_posix().endswith(esperado.as_posix())
