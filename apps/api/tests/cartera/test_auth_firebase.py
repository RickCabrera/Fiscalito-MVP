"""
La verificacion del ID token. (R-07)

POR QUE EXISTE ESTE ARCHIVO
---------------------------
Un revisor aplico la mutacion mas destructiva posible del entregable —hacer que
`uid_del_token` devuelva el token sin verificar, SIEMPRE— y **sobrevivio a las
dos suites completas**: 1193 verdes mas 5 del emulador. La unica defensa de este
camino, la que el propio `auth_firebase.py` declara como la unica que hay, no
tenia una sola prueba.

Es la misma forma del defecto que esta corrida lleva encontrando todo el dia:
una proteccion afirmada por escrito y sostenida por nada.

LO QUE SE MIDE AQUI
-------------------
1. Que el atajo que no verifica exige **dos** variables, no una.
2. Que sin credenciales sale un **503 que dice que falta**, y no el 401
   generico que manda a depurar sesiones de Firebase Auth durante una tarde.
3. Que un token invalido es 401 y **no filtra** el detalle del SDK.
"""

from __future__ import annotations

import os

import pytest

from app import auth_firebase
from app.auth_firebase import CredencialesFaltantes


@pytest.fixture(autouse=True)
def _entorno_limpio():
    """Cada test decide su entorno; ninguno hereda el del anterior."""
    previos = {
        k: os.environ.get(k)
        for k in ("FIRESTORE_EMULATOR_HOST", "PERMITIR_TOKEN_SIN_VERIFICAR")
    }
    for k in previos:
        os.environ.pop(k, None)
    auth_firebase._app_firebase.cache_clear()  # noqa: SLF001
    yield
    for k, v in previos.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    auth_firebase._app_firebase.cache_clear()  # noqa: SLF001


class TestElAtajoQueNoVerifica:
    """
    Exige DOS variables. Con una sola, la API quedaba completamente abierta:
    `Authorization: Bearer <uid-de-la-victima>` leeria y escribiria la cartera de
    cualquiera, y los uid de Firebase no son secretos.
    """

    def test_apagado_por_defecto(self):
        assert auth_firebase.sin_verificar_activo() is False

    def test_el_emulador_SOLO_no_lo_enciende(self):
        # El caso que importa: la variable llega por un `.env` copiado al
        # servidor, un compose heredado o una plantilla de despliegue.
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
        assert auth_firebase.sin_verificar_activo() is False

    def test_la_variable_explicita_SOLA_tampoco(self):
        os.environ["PERMITIR_TOKEN_SIN_VERIFICAR"] = "1"
        assert auth_firebase.sin_verificar_activo() is False

    def test_hacen_falta_LAS_DOS(self):
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
        os.environ["PERMITIR_TOKEN_SIN_VERIFICAR"] = "1"
        assert auth_firebase.sin_verificar_activo() is True

    def test_un_valor_distinto_de_1_no_cuenta(self):
        # `=true`, `=yes` o `=0` no encienden nada: la comparacion es exacta
        # para que un valor heredado no abra la puerta.
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
        for valor in ("0", "true", "yes", ""):
            os.environ["PERMITIR_TOKEN_SIN_VERIFICAR"] = valor
            assert auth_firebase.sin_verificar_activo() is False, valor

    def test_encendido_grita_al_log(self, caplog):
        # Un servicio que dejo de autenticar no puede hacerlo en silencio.
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
        os.environ["PERMITIR_TOKEN_SIN_VERIFICAR"] = "1"
        with caplog.at_level("ERROR"):
            auth_firebase.sin_verificar_activo()
        assert "AUTENTICACION DESACTIVADA" in caplog.text


class TestSinCredenciales:
    """
    El 503 que el contrato promete. Antes de esto **nunca ocurria**: el error
    salia como un 401 "tu sesion no es valida" tras 12 segundos de espera al
    metadata server, y quien encendiera el interruptor se habria pasado la tarde
    depurando Firebase Auth.
    """

    def test_es_503_y_dice_que_falta(self, monkeypatch):
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        def sin_adc():
            raise DefaultCredentialsError("no hay credenciales")

        monkeypatch.setattr(google.auth, "default", sin_adc)

        with pytest.raises(CredencialesFaltantes) as exc:
            auth_firebase.uid_del_token("un-token")

        assert exc.value.status_code == 503
        # El mensaje tiene que decir QUE falta, no "algo salio mal".
        assert "GOOGLE_APPLICATION_CREDENTIALS" in exc.value.message

    def test_NO_se_disfraza_de_401(self, monkeypatch):
        # La regresion concreta: `_app_firebase()` dentro del `try` hacia que el
        # `except Exception` generico lo convirtiera en el 401 de sesion
        # invalida, mandando a buscar el bug al lugar equivocado.
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        monkeypatch.setattr(
            google.auth, "default", lambda: (_ for _ in ()).throw(DefaultCredentialsError("x"))
        )

        with pytest.raises(CredencialesFaltantes) as exc:
            auth_firebase.uid_del_token("un-token")
        assert exc.value.status_code != 401


class TestTokenInvalido:
    def test_es_401_y_no_filtra_el_detalle_del_SDK(self, monkeypatch):
        """
        El detalle distingue "token expirado" de "token de otro proyecto", y eso
        le sirve a quien sondea, no al usuario. Se queda en el log.
        """
        monkeypatch.setattr(auth_firebase, "_app_firebase", lambda: object())

        import firebase_admin.auth as auth_admin

        def rechaza(*_a, **_k):
            raise ValueError("Token issued by project 999 not 111")

        monkeypatch.setattr(auth_admin, "verify_id_token", rechaza)

        from app.exceptions import FiscalAgentError

        with pytest.raises(FiscalAgentError) as exc:
            auth_firebase.uid_del_token("token-de-otro-proyecto")

        assert exc.value.status_code == 401
        assert "999" not in exc.value.message
        assert "project" not in exc.value.message.lower()

    def test_un_token_valido_devuelve_su_uid(self, monkeypatch):
        # La mitad simetrica: sin ella, una verificacion que rechazara SIEMPRE
        # pasaria los tests de arriba y dejaria la app inservible.
        monkeypatch.setattr(auth_firebase, "_app_firebase", lambda: object())

        import firebase_admin.auth as auth_admin

        monkeypatch.setattr(
            auth_admin, "verify_id_token", lambda *_a, **_k: {"uid": "uid-real"}
        )

        assert auth_firebase.uid_del_token("token-bueno") == "uid-real"
