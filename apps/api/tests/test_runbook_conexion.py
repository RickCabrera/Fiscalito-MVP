"""
P6-06: cada variable de entorno documentada tiene su paso en `docs/conexion-servicios.md`.

Se comparan las variables de `apps/api/.env.example` y `apps/store/.env.example` (incluidas
las que vienen comentadas como opcionales, `# NOMBRE=valor`) y la variable que elige cada
adaptador registrado (`FISCALITO_<SERVICIO>`) contra las que menciona el runbook. Si alguien
agrega una variable y no dice dónde se configura, esto falla.
"""

import re
from pathlib import Path

from app.integraciones.registro import verificar_configuracion

RAIZ = Path(__file__).resolve().parents[3]
RUNBOOK = RAIZ / "docs/conexion-servicios.md"
ENV_EXAMPLES = [RAIZ / "apps/api/.env.example", RAIZ / "apps/store/.env.example"]

# `NOMBRE=valor` o `# NOMBRE=valor` (opcional comentada) al inicio de renglón.
_VARIABLE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", re.M)


def _variables_de(archivo: Path) -> set[str]:
    return set(_VARIABLE.findall(archivo.read_text(encoding="utf-8")))


def _mencionadas() -> set[str]:
    return set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", RUNBOOK.read_text(encoding="utf-8")))


def test_los_env_example_tienen_variables():
    for archivo in ENV_EXAMPLES:
        assert _variables_de(archivo), f"{archivo} no trae variables: ¿cambió el formato?"


def test_cada_variable_de_env_example_tiene_su_paso_en_el_runbook():
    mencionadas = _mencionadas()
    faltan = {
        f"{archivo.relative_to(RAIZ)}: {v}"
        for archivo in ENV_EXAMPLES
        for v in _variables_de(archivo)
        if v not in mencionadas
    }
    assert not faltan, (
        "Variables sin paso en docs/conexion-servicios.md:\n  " + "\n  ".join(sorted(faltan))
    )


def test_cada_adaptador_registrado_tiene_su_paso_en_el_runbook():
    mencionadas = _mencionadas()
    faltan = sorted(s["variable"] for s in verificar_configuracion()
                    if s["variable"] not in mencionadas)
    assert not faltan, f"Adaptadores sin paso en el runbook: {faltan}"


def test_el_runbook_cubre_las_dieciseis_conexiones_ext():
    texto = RUNBOOK.read_text(encoding="utf-8")
    faltan = [f"EXT-{n:02d}" for n in range(1, 17) if f"## EXT-{n:02d}" not in texto]
    assert not faltan, f"Secciones EXT sin paso en el runbook: {faltan}"
