"""Correcciones que pidió el revisor de la fase P0."""

import io
import zipfile

import pytest

from app import auth_firebase
from app.boveda_cfdi import servicio as boveda
from app.boveda_cfdi.parser import CfdiInvalido, parsear_cfdi
from app.config import settings
from tests.plan_p.cfdi_sintetico import cfdi


def test_atajo_sin_verificar_jamas_en_produccion(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    monkeypatch.setenv("PERMITIR_TOKEN_SIN_VERIFICAR", "1")
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    assert auth_firebase.sin_verificar_activo() is True
    monkeypatch.setattr(settings, "ENTORNO", "produccion")
    assert auth_firebase.sin_verificar_activo() is False


def test_uuid_del_timbre_con_formato_invalido_se_rechaza():
    xml = cfdi("../../etc/passwd")
    xml = xml if isinstance(xml, bytes) else xml.encode()
    with pytest.raises(CfdiInvalido, match="UUID"):
        parsear_cfdi(xml)


def test_zip_con_demasiados_miembros_se_rechaza_entero(monkeypatch):
    monkeypatch.setattr(boveda, "MAX_MIEMBROS_ZIP", 3)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(4):
            zf.writestr(f"x{i}.xml", "<a/>")
    buf.seek(0)
    salida = list(boveda._iterar_zip("lote.zip", buf))
    assert len(salida) == 1 and salida[0][1] is None and "máximo" in salida[0][2]
