"""
SQLite aguanta escrituras concurrentes sin `database is locked` (P6-04).

Las pruebas de punta a punta lo pegaron en el primer clic: al entrar una cuenta nueva, el
front dispara varias peticiones a la vez y cada una intenta crear el despacho
(`asegurar_usuario`). Con `BEGIN` diferido, dos transacciones que leen y luego escriben se
interbloquean y SQLite falla al instante. `preparar_sqlite` ahora abre con
`BEGIN IMMEDIATE`; aquí se reproduce la carrera con hilos sobre un archivo real.
"""

import threading

from sqlalchemy.orm import sessionmaker

import app.modelos  # noqa: F401 — registra todas las tablas
from app.db.base import Base
from app.db.session import crear_motor
from app.modelos.nucleo import Despacho, Usuario
from app.tenancy import asegurar_usuario


def test_primeros_requests_simultaneos_no_chocan(tmp_path):
    motor = crear_motor(f"sqlite:///{tmp_path / 'carrera.db'}")
    Base.metadata.create_all(motor)
    hacer = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    errores: list[BaseException] = []
    salida = threading.Barrier(8)

    def un_request() -> None:
        db = hacer()
        try:
            salida.wait()
            asegurar_usuario(db, "uid-nuevo")
            db.commit()
        except BaseException as exc:  # noqa: BLE001 — se reporta abajo
            errores.append(exc)
            db.rollback()
        finally:
            db.close()

    hilos = [threading.Thread(target=un_request) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert errores == []
    with hacer() as db:
        assert db.get(Despacho, "uid-nuevo") is not None
        assert db.get(Usuario, "uid-nuevo").rol == "dueno"
    motor.dispose()
