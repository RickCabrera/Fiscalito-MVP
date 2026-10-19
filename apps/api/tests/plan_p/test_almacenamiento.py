"""P0-03: adaptador de almacenamiento (local, memoria y S3 con boto3 stubbeado, sin red)."""

import io

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.almacenamiento import (
    AlmacenamientoLocal,
    AlmacenamientoMemoria,
    AlmacenamientoS3,
    normalizar_ruta,
)

BYTES = b'<?xml version="1.0"?>\r\n<a>\xc3\xb1 \x00 crudo</a>\n'


@pytest.mark.parametrize("fabrica", [AlmacenamientoMemoria, "local"])
def test_guarda_lee_borra_byte_por_byte(fabrica, tmp_path):
    almacen = AlmacenamientoLocal(tmp_path) if fabrica == "local" else fabrica()
    assert not almacen.existe("cfdi/a/1/x.xml")
    assert almacen.guardar(BYTES, "cfdi/a/1/x.xml") == "cfdi/a/1/x.xml"
    assert almacen.existe("cfdi/a/1/x.xml")
    assert almacen.leer("cfdi/a/1/x.xml") == BYTES
    almacen.borrar("cfdi/a/1/x.xml")
    almacen.borrar("cfdi/a/1/x.xml")  # idempotente
    assert not almacen.existe("cfdi/a/1/x.xml")
    with pytest.raises(FiscalAgentError) as e:
        almacen.leer("cfdi/a/1/x.xml")
    assert e.value.status_code == 404


@pytest.mark.parametrize("ruta", ["", "/etc/passwd", "../fuera.xml", "a/../../b", "a/./b",
                                  "C:/x.xml", "a//b"])
def test_rechaza_rutas_que_escapan(ruta, tmp_path):
    with pytest.raises(FiscalAgentError):
        normalizar_ruta(ruta)
    with pytest.raises(FiscalAgentError):
        AlmacenamientoLocal(tmp_path).guardar(b"x", ruta)


def test_local_usa_la_variable_de_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "bodega"))
    AlmacenamientoLocal().guardar(b"hola", "a/b.xml")
    assert (tmp_path / "bodega" / "a" / "b.xml").read_bytes() == b"hola"


def test_registro_elige_por_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path))
    registro.limpiar_cache()
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    assert isinstance(registro.obtener("almacenamiento"), AlmacenamientoLocal)
    monkeypatch.setenv("FISCALITO_ALMACENAMIENTO", "local")
    assert isinstance(registro.obtener("almacenamiento"), AlmacenamientoLocal)
    monkeypatch.setenv("FISCALITO_ALMACENAMIENTO", "s3")
    monkeypatch.delenv("FISCALITO_S3_BUCKET", raising=False)
    with pytest.raises(FiscalAgentError) as e:  # s3 sin bucket: 503 claro, no un crash
        registro.obtener("almacenamiento")
    assert e.value.status_code == 503
    registro.limpiar_cache()


# ── S3 / R2 con botocore Stubber: se verifica la llamada exacta, sin red ──


def _s3():
    cliente = boto3.client(
        "s3", region_name="auto", endpoint_url="https://cuenta.r2.cloudflarestorage.com",
        aws_access_key_id="x", aws_secret_access_key="y",
    )
    return cliente, Stubber(cliente)


def test_s3_guardar_leer_existe_borrar():
    cliente, stub = _s3()
    almacen = AlmacenamientoS3(cliente=cliente, bucket="boveda", prefijo="prod")
    llave = "prod/cfdi/d/1/U.xml"
    stub.add_response("put_object", {}, {"Bucket": "boveda", "Key": llave, "Body": BYTES})
    stub.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(BYTES), len(BYTES))},
        {"Bucket": "boveda", "Key": llave},
    )
    stub.add_response("head_object", {}, {"Bucket": "boveda", "Key": llave})
    stub.add_response("delete_object", {}, {"Bucket": "boveda", "Key": llave})
    stub.add_client_error("head_object", service_error_code="404", http_status_code=404,
                          expected_params={"Bucket": "boveda", "Key": llave})
    stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404,
                          expected_params={"Bucket": "boveda", "Key": llave})
    with stub:
        assert almacen.guardar(BYTES, "cfdi/d/1/U.xml") == "cfdi/d/1/U.xml"
        assert almacen.leer("cfdi/d/1/U.xml") == BYTES
        assert almacen.existe("cfdi/d/1/U.xml") is True
        almacen.borrar("cfdi/d/1/U.xml")
        assert almacen.existe("cfdi/d/1/U.xml") is False
        with pytest.raises(FiscalAgentError) as e:
            almacen.leer("cfdi/d/1/U.xml")
        assert e.value.status_code == 404
    stub.assert_no_pending_responses()


def test_s3_otros_errores_no_se_disfrazan_de_404():
    cliente, stub = _s3()
    almacen = AlmacenamientoS3(cliente=cliente, bucket="boveda", prefijo="")
    stub.add_client_error("head_object", service_error_code="AccessDenied", http_status_code=403)
    with stub, pytest.raises(Exception) as e:
        almacen.existe("a.xml")
    assert not isinstance(e.value, FiscalAgentError)


def test_s3_construye_cliente_desde_variables(monkeypatch):
    monkeypatch.setenv("FISCALITO_S3_BUCKET", "b")
    monkeypatch.setenv("FISCALITO_S3_ENDPOINT", "https://cuenta.r2.cloudflarestorage.com")
    monkeypatch.setenv("FISCALITO_S3_ACCESS_KEY", "llave")
    monkeypatch.setenv("FISCALITO_S3_SECRET_KEY", "secreto")
    almacen = AlmacenamientoS3()
    assert almacen.bucket == "b"
    assert almacen.cliente.meta.endpoint_url == "https://cuenta.r2.cloudflarestorage.com"
