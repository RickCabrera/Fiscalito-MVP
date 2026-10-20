"""Las migraciones Alembic crean exactamente el esquema de los modelos (sin diferencias)."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

RAIZ = Path(__file__).resolve().parents[2]


def test_migraciones_al_dia_con_los_modelos(tmp_path, monkeypatch):
    import app.modelos  # noqa: F401
    from app.config import settings
    from app.db.base import Base

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    command.upgrade(cfg, "head")

    motor = create_engine(url)
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    assert diferencias == [], f"Falta una migración Alembic: {diferencias[:5]}"
