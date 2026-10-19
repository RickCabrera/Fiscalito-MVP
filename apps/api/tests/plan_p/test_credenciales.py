"""P0-05: bóveda de credenciales (e.firma y CSD) con certificados de prueba tipo SAT."""

import pickle

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate

from app.config import settings
from app.credenciales import certificados, cifrado, servicio
from app.credenciales.certificados import CredencialInvalida
from app.exceptions import FiscalAgentError
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente
from app.tenancy import asegurar_usuario
from tests.plan_p import certs_sat

RFC = "XAXX010101AB1"
LLAVE_A = Fernet.generate_key().decode()
LLAVE_B = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def llave_maestra(monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", LLAVE_A)
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    cifrado.olvidar_llave_efimera()
    yield
    cifrado.olvidar_llave_efimera()


@pytest.fixture
def cliente(db_sesion) -> Cliente:
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC)
    db_sesion.add(c)
    db_sesion.flush()
    return c


# ── Validación ──


def test_lee_rfc_numero_y_tipo_como_el_sat():
    par = certs_sat.generar(rfc="AAA010101AAA", rfc_representante="XAXX010101AB1")
    datos = certificados.datos_certificado(load_der_x509_certificate(par.cer))
    assert datos.rfc == "AAA010101AAA"  # persona moral: antes de la diagonal
    assert datos.numero_certificado == par.numero
    assert datos.tipo_detectado == "efirma"
    csd = certs_sat.generar(tipo="csd")
    datos_csd = certificados.datos_certificado(load_der_x509_certificate(csd.cer))
    assert datos_csd.tipo_detectado == "csd"


def test_valida_un_par_correcto():
    par = certs_sat.generar()
    datos = certificados.validar(par.cer, par.key, par.password, "efirma", rfc_cliente=RFC)
    assert datos.rfc == RFC


def test_contrasena_mala():
    par = certs_sat.generar()
    with pytest.raises(CredencialInvalida, match="contraseña no abre"):
        certificados.validar(par.cer, par.key, "otra", "efirma", RFC)


def test_llave_que_no_corresponde():
    par = certs_sat.generar(semilla=1)
    otro = certs_sat.generar(semilla=2)
    with pytest.raises(CredencialInvalida, match="no corresponde"):
        certificados.validar(par.cer, otro.key, otro.password, "efirma", RFC)


def test_rfc_distinto_al_del_cliente():
    par = certs_sat.generar(rfc="BBB010101BB1")
    with pytest.raises(CredencialInvalida, match="RFC BBB010101BB1"):
        certificados.validar(par.cer, par.key, par.password, "efirma", RFC)


def test_cliente_sin_rfc_acepta_cualquiera():
    par = certs_sat.generar(rfc="BBB010101BB1")
    assert certificados.validar(par.cer, par.key, par.password, "efirma", "").rfc == "BBB010101BB1"


def test_csd_subido_como_efirma_se_rechaza():
    par = certs_sat.generar(tipo="csd")
    with pytest.raises(CredencialInvalida, match="Sello Digital"):
        certificados.validar(par.cer, par.key, par.password, "efirma", RFC)


def test_certificado_vencido():
    par = certs_sat.generar(dias_desde=-800, dias_hasta=-1)
    with pytest.raises(CredencialInvalida, match="venció"):
        certificados.validar(par.cer, par.key, par.password, "efirma", RFC)


def test_cer_basura():
    par = certs_sat.generar()
    with pytest.raises(CredencialInvalida, match="no es un certificado"):
        certificados.validar(b"no soy un cer", par.key, par.password, "efirma", RFC)


# ── Cifrado y firmante ──


def test_guarda_cifrado_y_firma(db_sesion, cliente):
    par = certs_sat.generar()
    cred = servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    assert par.key not in cred.key_cifrada and par.password.encode() not in cred.password_cifrada
    firmante = servicio.obtener_firmante(db_sesion, cliente, "efirma")
    firma = firmante.firmar(b"hola SAT")
    load_der_x509_certificate(par.cer).public_key().verify(
        firma, b"hola SAT", padding.PKCS1v15(), hashes.SHA256()
    )
    assert firmante.certificado_base64 and firmante.numero_certificado == par.numero
    assert "BEGIN" not in repr(firmante) and par.password not in repr(firmante)
    with pytest.raises(TypeError):
        pickle.dumps(firmante)


def test_sin_la_llave_maestra_no_se_puede_leer(db_sesion, cliente, monkeypatch):
    par = certs_sat.generar()
    servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    # Producción sin llave: 503 al usar la bóveda.
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", "")
    monkeypatch.setattr(settings, "ENTORNO", "produccion")
    with pytest.raises(FiscalAgentError) as e:
        servicio.obtener_firmante(db_sesion, cliente, "efirma")
    assert e.value.status_code == 503
    # Desarrollo sin llave: la efímera no descifra lo que cifró la llave real.
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    with pytest.raises(FiscalAgentError) as e:
        servicio.obtener_firmante(db_sesion, cliente, "efirma")
    assert e.value.status_code == 503
    # Otra llave cualquiera tampoco.
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", LLAVE_B)
    with pytest.raises(FiscalAgentError):
        servicio.obtener_firmante(db_sesion, cliente, "efirma")


def test_produccion_sin_llave_no_guarda(db_sesion, cliente, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", "")
    monkeypatch.setattr(settings, "ENTORNO", "produccion")
    par = certs_sat.generar()
    with pytest.raises(FiscalAgentError) as e:
        servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    assert e.value.status_code == 503


def test_rotacion_de_llave(db_sesion, cliente, monkeypatch):
    par = certs_sat.generar()
    servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", f"{LLAVE_B},{LLAVE_A}")
    assert servicio.obtener_firmante(db_sesion, cliente, "efirma")  # la vieja aún descifra
    assert servicio.recifrar_todo(db_sesion) == 1
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", LLAVE_B)  # ya sin la vieja
    assert servicio.obtener_firmante(db_sesion, cliente, "efirma").rfc == RFC


def test_llave_maestra_invalida_da_503(monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", "no-es-fernet")
    with pytest.raises(FiscalAgentError) as e:
        cifrado.cifrar(b"x")
    assert e.value.status_code == 503


def test_subir_otra_del_mismo_tipo_desactiva_la_anterior(db_sesion, cliente):
    par = certs_sat.generar()
    servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "uid-a")
    assert len(servicio.activas(db_sesion, cliente)) == 1
    assert db_sesion.query(CredencialCliente).count() == 2


def test_sin_credencial_firmante_404(db_sesion, cliente):
    with pytest.raises(FiscalAgentError) as e:
        servicio.obtener_firmante(db_sesion, cliente, "csd")
    assert e.value.status_code == 404


# ── API ──


def _alta_cliente(sesionador, uid: str, clave: str, rfc: str = RFC) -> None:
    s = sesionador()
    asegurar_usuario(s, uid)
    s.add(Cliente(despacho_id=uid, clave=clave, nombre=clave, rfc=rfc))
    s.commit()
    s.close()


def _subir(cliente_http, clave: str, par, tipo: str = "efirma"):
    return cliente_http.post(
        f"/api/v1/clientes/{clave}/credenciales",
        data={"tipo": tipo, "password": par.password},
        files={"cer": ("a.cer", par.cer), "key": ("a.key", par.key)},
    )


def test_api_sube_lista_y_borra(api, sesionador):
    _alta_cliente(sesionador, "uid-a", "taller")
    par = certs_sat.generar(dias_hasta=20)
    r = _subir(api("uid-a"), "taller", par)
    assert r.status_code == 200, r.text
    meta = r.json()["credencial"]
    assert meta["rfc"] == RFC and meta["por_vencer"] is True
    assert set(meta) >= {"tipo", "numero_certificado", "valido_hasta", "dias_para_vencer"}
    texto = r.text
    assert "key" not in meta and "password" not in texto and par.password not in texto

    r = api("uid-a").get("/api/v1/clientes/taller/credenciales")
    assert [c["tipo"] for c in r.json()["credenciales"]] == ["efirma"]

    r = api("uid-a").delete(f"/api/v1/clientes/taller/credenciales/{meta['id']}")
    assert r.status_code == 200
    assert api("uid-a").get("/api/v1/clientes/taller/credenciales").json()["credenciales"] == []


def test_api_errores_claros(api, sesionador):
    _alta_cliente(sesionador, "uid-a", "taller")
    par = certs_sat.generar()
    r = api("uid-a").post(
        "/api/v1/clientes/taller/credenciales",
        data={"tipo": "efirma", "password": "mala"},
        files={"cer": ("a.cer", par.cer), "key": ("a.key", par.key)},
    )
    assert r.status_code == 422 and "contraseña" in r.json()["error"]


def test_api_multi_tenant(api, sesionador):
    _alta_cliente(sesionador, "uid-a", "taller")
    par = certs_sat.generar()
    cred_id = _subir(api("uid-a"), "taller", par).json()["credencial"]["id"]
    assert api("uid-b").get("/api/v1/clientes/taller/credenciales").status_code == 404
    assert _subir(api("uid-b"), "taller", par).status_code == 404
    r = api("uid-b").delete(f"/api/v1/clientes/taller/credenciales/{cred_id}")
    assert r.status_code == 404
    # Aunque B tenga un cliente con la misma clave, no toca la credencial de A.
    _alta_cliente(sesionador, "uid-b", "otro")
    r = api("uid-b").delete(f"/api/v1/clientes/otro/credenciales/{cred_id}")
    assert r.status_code == 404


def test_api_auxiliar_no_puede(api, sesionador):
    from app.modelos.nucleo import AsignacionCliente, Usuario

    _alta_cliente(sesionador, "uid-a", "taller")
    s = sesionador()
    s.add(Usuario(uid="aux", despacho_id="uid-a", rol="auxiliar"))
    s.flush()
    cliente_id = s.query(Cliente).filter_by(clave="taller").one().id
    s.add(AsignacionCliente(usuario_uid="aux", cliente_id=cliente_id))
    s.commit()
    s.close()
    assert api("aux").get("/api/v1/clientes/taller/credenciales").status_code == 403
    assert _subir(api("aux"), "taller", certs_sat.generar()).status_code == 403


def test_api_sin_token_401(api):
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/v1/clientes/taller/credenciales").status_code == 401
