"""
P0-08: el contrato versionado (`docs/openapi.json` + tipos TS) es el de la app real.

Falla —no regenera— cuando el código y el contrato divergen, y dice el comando. Es la
misma política que `test_rutas_publicadas.py`: regenerar es decisión de quien cambió la
ruta, porque implica revisar al front. El lado del front lo cierra
`apps/store/src/services/tiposApi.test.ts`, que importa los tipos (si no compilan, el
build se cae).
"""

from __future__ import annotations

import json

import pytest

from scripts.exportar_openapi import (
    COMANDO,
    DESTINO_OPENAPI,
    DESTINO_TS,
    documento,
    generar_ts,
    nombre_ts,
    serializar_openapi,
    tipo_ts,
)


@pytest.fixture(scope="module")
def esquema() -> dict:
    return documento()


def test_openapi_versionado_coincide_con_la_app(esquema):
    assert DESTINO_OPENAPI.exists(), f"Falta {DESTINO_OPENAPI}. Genéralo con: {COMANDO}"
    guardado = json.loads(DESTINO_OPENAPI.read_text(encoding="utf-8"))
    if guardado != esquema:
        faltan = sorted(set(esquema["paths"]) - set(guardado.get("paths", {})))
        sobran = sorted(set(guardado.get("paths", {})) - set(esquema["paths"]))
        pytest.fail(
            "docs/openapi.json quedó desactualizado respecto de app.main:app.\n"
            f"  Rutas nuevas: {faltan}\n  Rutas que ya no existen: {sobran}\n"
            f"Si el cambio es intencional: {COMANDO}\n"
            "y actualiza docs/api-contract.md en el mismo entregable."
        )


def test_openapi_esta_serializado_estable(esquema):
    """Mismo esquema, mismos bytes: un diff del JSON sólo aparece si cambió la API."""
    assert DESTINO_OPENAPI.read_text(encoding="utf-8") == serializar_openapi(esquema)


def test_los_tipos_ts_estan_al_dia(esquema):
    assert DESTINO_TS.exists(), f"Falta {DESTINO_TS}. Genéralo con: {COMANDO}"
    assert DESTINO_TS.read_text(encoding="utf-8") == generar_ts(esquema), (
        f"{DESTINO_TS.name} quedó desactualizado. Regenera con: {COMANDO}"
    )


def test_cada_esquema_de_componentes_tiene_su_tipo(esquema):
    contenido = DESTINO_TS.read_text(encoding="utf-8")
    for nombre in esquema["components"]["schemas"]:
        ts = nombre_ts(nombre)
        assert f"export interface {ts} " in contenido or f"export type {ts} =" in contenido, ts


def test_el_contrato_documenta_la_autenticacion():
    """La auth genérica, el token de dispositivo y el 429 están en el contrato humano."""
    contrato = (DESTINO_OPENAPI.parent / "api-contract.md").read_text(encoding="utf-8")
    for frase in ("Authorization: Bearer", "X-Token-Dispositivo", "429", "Retry-After"):
        assert frase in contrato, frase


class TestGenerador:
    """El traductor JSON Schema → TS sobre las formas que emite Pydantic v2."""

    @pytest.mark.parametrize(
        ("esquema", "esperado"),
        [
            ({"type": "string"}, "string"),
            ({"type": "integer"}, "number"),
            ({"type": "boolean"}, "boolean"),
            ({"anyOf": [{"type": "string"}, {"type": "null"}]}, "string | null"),
            ({"type": "array", "items": {"$ref": "#/components/schemas/X-Input"}}, "XInput[]"),
            (
                {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
                "(string | null)[]",
            ),
            ({"enum": ["a", "b"]}, '"a" | "b"'),
            ({"const": "fijo"}, '"fijo"'),
            (
                {"type": "object", "additionalProperties": {"type": "number"}},
                "Record<string, number>",
            ),
            ({"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}]},
             "[string, number]"),
            ({}, "unknown"),
            ({"type": "rarísimo"}, "unknown"),
        ],
    )
    def test_traduce(self, esquema, esperado):
        assert tipo_ts(esquema) == esperado

    def test_objeto_con_requeridos_y_opcionales(self):
        ts = tipo_ts(
            {
                "type": "object",
                "properties": {"a": {"type": "string"}, "con-guion": {"type": "integer"}},
                "required": ["a"],
            }
        )
        assert "a: string;" in ts
        assert '"con-guion"?: number;' in ts

    def test_nunca_emite_any(self, esquema):
        assert ": any" not in generar_ts(esquema)
