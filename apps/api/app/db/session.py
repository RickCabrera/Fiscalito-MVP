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


def preparar_sqlite(motor: Engine) -> None:
    """
    Llaves foráneas y transacciones de verdad en SQLite.

    pysqlite no emite `BEGIN` antes de un `SAVEPOINT`, así que un `begin_nested()` al
    principio de una transacción se confirmaba solo al liberarse y el `rollback()` de
    afuera ya no lo deshacía (P0-04: la cola y el programador usan savepoints). La receta
    de SQLAlchemy: apagar el manejo propio del driver y emitir `BEGIN` nosotros.

    **`BEGIN IMMEDIATE`, no `BEGIN` a secas (P6-04).** Con `BEGIN` diferido, dos requests
    que leen y luego escriben —los primeros de una cuenta nueva crean su despacho en
    paralelo, y el worker escribe su latido cada vuelta— se bloquean entre sí al subir de
    lectura a escritura, y SQLite responde `database is locked` AL INSTANTE, sin esperar
    el `timeout`: es su forma de romper el interbloqueo. Las pruebas de punta a punta lo
    pegaban en el primer clic. Tomar el candado de escritura al empezar serializa las
    transacciones (y entonces sí espera hasta `timeout`); en SQLite —desarrollo y
    pruebas— es el precio correcto. Postgres no pasa por aquí.
    """

    @event.listens_for(motor, "connect")
    def _conectar(conexion, _registro):  # type: ignore[no-untyped-def]
        conexion.isolation_level = None
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(motor, "begin")
    def _begin(conexion):  # type: ignore[no-untyped-def]
        conexion.exec_driver_sql("BEGIN IMMEDIATE")


def crear_motor(url: str) -> Engine:
    """Crea el engine. En SQLite activa llaves foráneas y permite uso entre hilos."""
    if url.startswith("sqlite"):
        # `timeout`: cuánto espera una transacción el candado de otra (ver `preparar_sqlite`).
        motor = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        preparar_sqlite(motor)
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
