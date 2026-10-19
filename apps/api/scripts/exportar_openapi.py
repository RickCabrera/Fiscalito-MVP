"""
Contrato único de la API (P0-08): `docs/openapi.json` + tipos TypeScript para el front.

    cd apps/api && PYTHONPATH=. python scripts/exportar_openapi.py

Escribe dos archivos, los dos derivados de `app.main:app.openapi()`:

- `docs/openapi.json` — el esquema OpenAPI completo, versionado. Es la fuente de verdad
  máquina-legible; `docs/api-contract.md` sigue siendo la explicación para humanos.
- `apps/store/src/services/tiposApi.generados.ts` — una interfaz TS por cada esquema de
  componentes, más `OperacionesApi` (cuerpo y respuesta de cada ruta).

`tests/test_contrato_openapi.py` falla si cualquiera de los dos quedó viejo y dice este
comando. No se regenera solo, por la misma razón que `exportar_rutas.py`: un test que
arregla lo que encuentra no encuentra nada.

POR QUÉ UN GENERADOR PROPIO Y NO `openapi-typescript`
-----------------------------------------------------
No está en `node_modules` y la máquina de trabajo no tiene red. Los esquemas que produce
Pydantic v2 usan un subconjunto pequeño de JSON Schema (`type`, `$ref`, `anyOf`, `items`,
`prefixItems`, `enum`, `const`, `additionalProperties`, `allOf`), y traducir eso son ~150
líneas sin dependencias. Lo que no reconoce sale como `unknown`, nunca como `any`.

`PYTHONPATH=.` HACE FALTA
-------------------------
El `.venv` compartido instala `app` en modo editable apuntando a OTRO árbol; sin
`PYTHONPATH=.` el script exportaría la API de ese árbol y no la de éste.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[3]
DESTINO_OPENAPI = RAIZ / "docs" / "openapi.json"
DESTINO_TS = RAIZ / "apps" / "store" / "src" / "services" / "tiposApi.generados.ts"
COMANDO = "cd apps/api && PYTHONPATH=. python scripts/exportar_openapi.py"

_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def documento() -> dict[str, Any]:
    """El OpenAPI de la app real, normalizado para versionarse."""
    from app.main import app

    esquema = app.openapi()
    if not esquema.get("paths") or not esquema.get("components", {}).get("schemas"):
        raise RuntimeError("El OpenAPI salió vacío: el exportador está roto, no la API.")
    return esquema


def serializar_openapi(esquema: dict[str, Any]) -> str:
    return json.dumps(esquema, ensure_ascii=False, indent=2) + "\n"


# ── JSON Schema → TypeScript ────────────────────────────────────────────────


def nombre_ts(nombre: str) -> str:
    """`PartidaSchema-Input` → `PartidaSchemaInput` (identificador TS válido)."""
    limpio = re.sub(r"[^A-Za-z0-9_$]", "", nombre)
    return limpio if _IDENT.match(limpio) else f"T{limpio}"


def _literal(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _propiedad(nombre: str) -> str:
    return nombre if _IDENT.match(nombre) else _literal(nombre)


def _union(partes: list[str]) -> str:
    vistas: list[str] = []
    for p in partes:
        if p not in vistas:
            vistas.append(p)
    if "unknown" in vistas:
        return "unknown"
    return " | ".join(vistas) if vistas else "never"


def _envolver(tipo: str) -> str:
    """Paréntesis para que `A | B` se pueda volver arreglo: `(A | B)[]`."""
    return f"({tipo})" if (" | " in tipo or " & " in tipo) else tipo


def tipo_ts(esquema: Any, sangria: int = 0) -> str:
    """Traduce un JSON Schema (el subconjunto que emite Pydantic v2) a un tipo TS."""
    if esquema is True or esquema == {} or esquema is None:
        return "unknown"
    if not isinstance(esquema, dict):
        return "unknown"
    if "$ref" in esquema:
        return nombre_ts(esquema["$ref"].rsplit("/", 1)[-1])
    if "const" in esquema:
        return _literal(esquema["const"])
    if "enum" in esquema:
        return _union([_literal(v) for v in esquema["enum"]])
    for clave in ("anyOf", "oneOf"):
        if clave in esquema:
            return _union([tipo_ts(s, sangria) for s in esquema[clave]])
    if "allOf" in esquema:
        partes = [tipo_ts(s, sangria) for s in esquema["allOf"]]
        return partes[0] if len(partes) == 1 else " & ".join(_envolver(p) for p in partes)
    tipo = esquema.get("type")
    if isinstance(tipo, list):
        return _union([tipo_ts({**esquema, "type": t}, sangria) for t in tipo])
    if tipo == "string":
        return "string"
    if tipo in ("integer", "number"):
        return "number"
    if tipo == "boolean":
        return "boolean"
    if tipo == "null":
        return "null"
    if tipo == "array":
        if "prefixItems" in esquema:
            elementos = [tipo_ts(s, sangria) for s in esquema["prefixItems"]]
            return f"[{', '.join(elementos)}]"
        return f"{_envolver(tipo_ts(esquema.get('items', {}), sangria))}[]"
    if tipo == "object" or "properties" in esquema:
        return _objeto(esquema, sangria)
    return "unknown"


def _objeto(esquema: dict[str, Any], sangria: int) -> str:
    propiedades: dict[str, Any] = esquema.get("properties", {})
    adicionales = esquema.get("additionalProperties")
    if not propiedades:
        if isinstance(adicionales, dict) and adicionales:
            return f"Record<string, {tipo_ts(adicionales, sangria)}>"
        return "Record<string, unknown>"
    requeridos = set(esquema.get("required", []))
    pad = "  " * (sangria + 1)
    lineas = ["{"]
    for nombre, sub in propiedades.items():
        opcional = "" if nombre in requeridos else "?"
        lineas.append(f"{pad}{_propiedad(nombre)}{opcional}: {tipo_ts(sub, sangria + 1)};")
    if isinstance(adicionales, dict) and adicionales:
        lineas.append(f"{pad}[clave: string]: unknown;")
    lineas.append("  " * sangria + "}")
    return "\n".join(lineas)


def _comentario(esquema: dict[str, Any]) -> str:
    descripcion = (esquema.get("description") or "").strip().splitlines()
    if not descripcion:
        return ""
    primera = descripcion[0].replace("*/", "* /").strip()
    return f"/** {primera} */\n" if primera else ""


def _contenido(cuerpo: dict[str, Any] | None) -> str:
    if not cuerpo:
        return "never"
    contenido = cuerpo.get("content", {})
    for tipo in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
        if tipo in contenido:
            return tipo_ts(contenido[tipo].get("schema", {}), 2)
    return "unknown"


def _respuesta(operacion: dict[str, Any]) -> str:
    respuestas = operacion.get("responses", {})
    for codigo in ("200", "201", "202", "204"):
        if codigo in respuestas:
            if codigo == "204":
                return "null"
            if not respuestas[codigo].get("content"):
                return "unknown"
            return _contenido(respuestas[codigo])
    return "unknown"


def generar_ts(esquema: dict[str, Any]) -> str:
    """El archivo de tipos completo. Determinístico: mismo esquema, mismos bytes."""
    componentes: dict[str, Any] = esquema["components"]["schemas"]
    salida = [
        "/**",
        " * TIPOS GENERADOS — NO EDITAR A MANO (P0-08).",
        " *",
        " * Salen de `app.main:app.openapi()` por `apps/api/scripts/exportar_openapi.py`:",
        f" *   {COMANDO}",
        " * `apps/api/tests/test_contrato_openapi.py` falla si este archivo quedó viejo.",
        " */",
        "",
    ]
    for nombre in sorted(componentes):
        sub = componentes[nombre]
        ts = nombre_ts(nombre)
        cuerpo = tipo_ts(sub)
        comentario = _comentario(sub)
        if comentario:
            salida.append(comentario.rstrip("\n"))
        if cuerpo.startswith("{"):
            salida.append(f"export interface {ts} {cuerpo}")
        else:
            salida.append(f"export type {ts} = {cuerpo};")
        salida.append("")

    rutas = sorted(esquema["paths"])
    salida.append("/** Toda ruta que publica la API. */")
    salida.append("export type RutaApi =")
    salida.extend(f"  | {_literal(r)}" for r in rutas)
    salida[-1] += ";"
    salida.append("")
    salida.append("/** Cuerpo y respuesta (2xx) de cada operación, por `MÉTODO /ruta`. */")
    salida.append("export interface OperacionesApi {")
    for ruta in rutas:
        for metodo, operacion in sorted(esquema["paths"][ruta].items()):
            if not isinstance(operacion, dict) or "responses" not in operacion:
                continue
            llave = _literal(f"{metodo.upper()} {ruta}")
            salida.append(f"  {llave}: {{")
            salida.append(f"    cuerpo: {_contenido(operacion.get('requestBody'))};")
            salida.append(f"    respuesta: {_respuesta(operacion)};")
            salida.append("  };")
    salida.append("}")
    return "\n".join(salida) + "\n"


def main() -> int:
    esquema = documento()
    DESTINO_OPENAPI.write_text(serializar_openapi(esquema), encoding="utf-8")
    DESTINO_TS.write_text(generar_ts(esquema), encoding="utf-8")
    print(f"{len(esquema['paths'])} rutas, {len(esquema['components']['schemas'])} esquemas")
    print(f"-> {DESTINO_OPENAPI}")
    print(f"-> {DESTINO_TS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
