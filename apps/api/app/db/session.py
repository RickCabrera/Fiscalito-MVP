"""
Motor y sesiones de base de datos.

`DATABASE_URL` decide el motor: `postgresql+psycopg://...` en Railway, y por default un
SQLite local (`sqlite:///./fiscalito.db`) para que el proyecto arranque sin nada instalado.
Los tests usan su propio SQLite en memoria (ver `tests/conftest.py`).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def crear_motor(url: str) -> Engine:
    """Crea el engine. En SQLite activa llaves foráneas y permite uso entre hilos."""
    if url.startswith("sqlite"):
        motor = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(motor, "connect")
        def _fk(conexion, _registro):  # type: ignore[no-untyped-def]
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return motor
    return create_engine(url, pool_pre_ping=True)


motor = crear_motor(settings.DATABASE_URL)
SesionLocal = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obtener_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por request, con commit al final."""
    db = SesionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def crear_tablas() -> None:
    """Crea las tablas que falten (dev). En producción manda Alembic."""
    import app.modelos  # noqa: F401 — registra todos los modelos
    from app.db.base import Base

    Base.metadata.create_all(motor)
