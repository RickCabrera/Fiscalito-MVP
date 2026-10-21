"""
P6-03: toda variable de entorno que lee el código está en un `.env.example`.

Backend: cada nombre que se lee con `os.getenv`/`os.environ`/`env(...)` y cada literal
`"FISCALITO_*"` de `app/`, `scripts/` y `migrations/`, más la variable `FISCALITO_<SERVICIO>`
de cada adaptador registrado, tiene que aparecer en `apps/api/.env.example` (puesta o
comentada). Frontend: cada `import.meta.env.VITE_*` de `apps/store/src` (sin tests) en
`apps/store/.env.example`. Una variable nueva sin documentar pone este test en rojo.

Los nombres armados en tiempo de ejecución (`FISCALITO_PLAN_<ID>_PRECIO`, ...) no se pueden
leer del código: se documentan a mano en el `.env.example` con su patrón.
"""

from __future__ import annotations

import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
STORE = API.parents[0] / "store"

_LECTURA = re.compile(
    r"""(?:getenv|environ\.get|environ\[|\benv)\(?\s*["']([A-Z][A-Z0-9_]*[A-Z0-9])["']"""
)
_FISCALITO = re.compile(r"""["'](FISCALITO_[A-Z0-9_]*[A-Z0-9])["']""")
_VITE = re.compile(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)")
_DECLARADA = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)
# Sólo existen para los tests o para el emulador local; no son configuración del servicio.
NO_SON_CONFIGURACION = {"FIRESTORE_EMULATOR_HOST"}


def _declaradas(archivo: Path) -> set[str]:
    assert archivo.is_file(), f"Falta {archivo}"
    return set(_DECLARADA.findall(archivo.read_text(encoding="utf-8")))


def variables_backend() -> set[str]:
    nombres: set[str] = set()
    for carpeta in ("app", "scripts", "migrations"):
        for py in (API / carpeta).rglob("*.py"):
            texto = py.read_text(encoding="utf-8")
            nombres |= set(_LECTURA.findall(texto)) | set(_FISCALITO.findall(texto))
    from app.integraciones.registro import verificar_configuracion

    nombres |= {s["variable"] for s in verificar_configuracion()}
    return nombres - NO_SON_CONFIGURACION


def variables_front() -> set[str]:
    nombres: set[str] = set()
    for ts in (STORE / "src").rglob("*.ts*"):
        if ".test." in ts.name:
            continue
        nombres |= set(_VITE.findall(ts.read_text(encoding="utf-8")))
    return nombres


def test_el_escaner_encuentra_variables():
    """Guarda contra un regex roto que dé verde por no encontrar nada."""
    back, front = variables_backend(), variables_front()
    assert {"DATABASE_URL", "FISCALITO_LLAVE_MAESTRA", "FISCALITO_PAC"} <= back
    assert len(back) > 60
    assert "VITE_FISCAL_AGENT_URL" in front


def test_toda_variable_del_backend_esta_en_env_example():
    faltan = sorted(variables_backend() - _declaradas(API / ".env.example"))
    assert not faltan, f"Agrega a apps/api/.env.example (con su comentario): {faltan}"


def test_toda_variable_del_front_esta_en_env_example():
    faltan = sorted(variables_front() - _declaradas(STORE / ".env.example"))
    assert not faltan, f"Agrega a apps/store/.env.example: {faltan}"
