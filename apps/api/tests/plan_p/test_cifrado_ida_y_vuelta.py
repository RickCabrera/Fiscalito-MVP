"""Revisor P6 B2: lo que `cifrar_existentes` cifra, `descifrar_existentes` lo deja en claro."""

import json

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text

from app.config import settings
from app.db.cifrado_columnas import (
    PREFIJO,
    cifrar_existentes,
    descifrar_existentes,
)

CLABE = "002180700000000011"  # sintética, sin titular


def test_cifrar_y_descifrar_existentes_ida_y_vuelta(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    motor = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    with motor.begin() as c:
        c.execute(text("CREATE TABLE empleados (id INTEGER PRIMARY KEY, datos JSON)"))
        c.execute(text("CREATE TABLE cuentas_bancarias "
                       "(id INTEGER PRIMARY KEY, numero VARCHAR(400), clabe VARCHAR(400))"))
        c.execute(text("INSERT INTO empleados VALUES (1, :d)"),
                  {"d": json.dumps({"clabe": CLABE, "numero_cuenta": "1234567890", "x": 1})})
        c.execute(text("INSERT INTO cuentas_bancarias VALUES (1, '0123456789', :c)"),
                  {"c": CLABE})

        assert cifrar_existentes(c) == {"empleados": 1, "cuentas_bancarias": 1}
        datos = json.loads(c.execute(text("SELECT datos FROM empleados")).scalar_one())
        assert datos["clabe"].startswith(PREFIJO) and datos["x"] == 1
        numero, clabe = c.execute(text("SELECT numero, clabe FROM cuentas_bancarias")).one()
        assert numero.startswith(PREFIJO) and clabe.startswith(PREFIJO)

        assert descifrar_existentes(c) == {"empleados": 1, "cuentas_bancarias": 1}
        datos = json.loads(c.execute(text("SELECT datos FROM empleados")).scalar_one())
        assert datos == {"clabe": CLABE, "numero_cuenta": "1234567890", "x": 1}
        assert c.execute(text("SELECT numero, clabe FROM cuentas_bancarias")).one() == (
            "0123456789", CLABE)
        # Idempotente: lo que ya está en claro no se toca.
        assert descifrar_existentes(c) == {"empleados": 0, "cuentas_bancarias": 0}
