"""P6-03: el arranque del contenedor migra antes de servir y falla cerrado si la migración falla."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

ARRANQUE = Path(__file__).resolve().parents[1] / "docker" / "arranque.sh"


def _falso(bin_dir: Path, nombre: str, salida: int, rastro: Path) -> None:
    script = bin_dir / nombre
    script.write_text(f'#!/bin/sh\necho "{nombre} $*" >> "{rastro}"\nexit {salida}\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)


def _correr(tmp_path: Path, alembic_sale: int, *args: str) -> tuple[int, list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    rastro = tmp_path / "rastro.txt"
    _falso(bin_dir, "alembic", alembic_sale, rastro)
    _falso(bin_dir, "uvicorn", 0, rastro)
    _falso(bin_dir, "python", 0, rastro)
    entorno = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    r = subprocess.run(["sh", str(ARRANQUE), *args], env=entorno, capture_output=True,
                       text=True, timeout=30)
    lineas = rastro.read_text().splitlines() if rastro.exists() else []
    return r.returncode, lineas


@pytest.mark.parametrize("args", [(), ("api",)])
def test_api_migra_y_luego_sirve(tmp_path, args):
    codigo, rastro = _correr(tmp_path, 0, *args)
    assert codigo == 0
    assert rastro[0] == "alembic upgrade head"
    assert rastro[1].startswith("uvicorn app.main:app") and "--no-access-log" in rastro[1]


def test_migracion_fallida_no_arranca_la_api(tmp_path):
    codigo, rastro = _correr(tmp_path, 1, "api")
    assert codigo == 1
    assert rastro == ["alembic upgrade head"]  # uvicorn nunca corrió


def test_worker_y_programador_no_migran(tmp_path):
    codigo, rastro = _correr(tmp_path, 1, "worker")
    assert codigo == 0 and rastro == ["python -m app.trabajos.worker --sin-programacion"]
    otro = tmp_path / "p"
    otro.mkdir()
    codigo, rastro = _correr(otro, 1, "programador")
    assert codigo == 0 and rastro == ["python -m app.trabajos.programador"]
