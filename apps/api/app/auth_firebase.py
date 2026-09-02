"""
Quién está preguntando: verificación del ID token de Firebase. (R-07)

EL `uid` NUNCA VIAJA EN EL CUERPO NI EN UN QUERY PARAM
------------------------------------------------------
Es la decisión que hace que R-07 no sea un agujero. La cartera de un despacho
guarda el salario y el NSS de trabajadores de terceros; si el uid llegara como
un campo más, cualquiera con `curl` leería la cartera de cualquiera cambiando un
renglón. Llega como **ID token firmado por Firebase** en
`Authorization: Bearer …`, y `firebase-admin` verifica la firma, el emisor, la
audiencia y la expiración contra las llaves públicas de Google.

**El Admin SDK ignora las reglas de Firestore**, por diseño: son credenciales
privilegiadas. Las reglas que desplegó R-01 siguen protegiendo el acceso directo
desde el navegador. La defensa de ESTE camino es este archivo, y no hay otra.

CREDENCIALES: LO QUE FALTA PARA QUE R-07 QUEDE CERRADA
------------------------------------------------------
`firebase-admin` necesita una de estas, y **en la máquina donde se escribió esto
no había ninguna**:

1. `GOOGLE_APPLICATION_CREDENTIALS` apuntando a un JSON de service account, o
2. Application Default Credentials (`gcloud auth application-default login`), o
3. correr dentro de GCP, donde las toma del metadata server.

Por eso R-07 se entrega con el interruptor del front **apagado**
(`VITE_CARTERA_BACKEND`) y la tarea queda ABIERTA: encender el front sin
credenciales daría 503 en todo el CRUD, o sea una app rota a sabiendas. Lo que
falta es una acción de Ricardo, no código.

Mientras tanto **sí hay cobertura real**: `FIRESTORE_EMULATOR_HOST` levanta el
emulador de Firestore, que no pide autenticación, y contra él corren los mismos
casos que contra el doble en memoria (`pytest -m emulador`).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from fastapi import Header

from app.exceptions import FiscalAgentError

logger = logging.getLogger(__name__)

# Project id de respaldo para el emulador, que no valida credenciales pero sí
# necesita un proyecto al que colgar los datos.
PROYECTO_POR_DEFECTO = "fiscalito-mvp"


class CredencialesFaltantes(FiscalAgentError):
    """
    No hay con qué hablarle a Firebase.

    Es 503 y no 500 a propósito: no es un error del request, es que el servicio
    no está configurado. El mensaje dice **qué falta**, porque el modo de falla
    contrario —un 500 genérico— manda a buscar el bug en el lugar equivocado.
    """

    def __init__(self) -> None:
        super().__init__(
            "El backend no tiene credenciales de Firebase, así que no puede ser dueño de "
            "la cartera. Define GOOGLE_APPLICATION_CREDENTIALS con un service account, o "
            "corre `gcloud auth application-default login`. Para pruebas locales, levanta "
            "el emulador y exporta FIRESTORE_EMULATOR_HOST=127.0.0.1:8080.",
            status_code=503,
        )


def _credencial_anonima() -> Any:
    """
    Credencial vacía para el emulador.

    `firebase_admin` comprueba `isinstance` contra su propia `credentials.Base`,
    así que **hay que heredar de verdad**: una clase con el mismo método no
    pasa. Se construye aquí dentro y no a nivel de módulo porque su razón de ser
    es local —el emulador no autentica— y porque una credencial anónima
    paseándose por el resto del código es la clase de cosa que alguien reusa por
    accidente contra producción.
    """
    from firebase_admin import credentials as creds
    from google.auth.credentials import AnonymousCredentials

    class _Anonima(creds.Base):
        def get_credential(self) -> Any:
            return AnonymousCredentials()

    return _Anonima()


@lru_cache(maxsize=1)
def _app_firebase() -> Any:
    """
    Inicializa `firebase_admin` una sola vez, o levanta `CredencialesFaltantes`.

    Cacheado porque `initialize_app` revienta si se llama dos veces, y este
    módulo lo puede pedir desde cualquier request.
    """
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:  # noqa: SLF001 — es la API que hay para preguntarlo
        return firebase_admin.get_app()

    proyecto = os.environ.get("FIREBASE_PROJECT_ID", PROYECTO_POR_DEFECTO)

    # Con el emulador no hay credenciales que buscar, y hay que decirlo
    # explícitamente: `initialize_app(None)` **no** significa "sin
    # credenciales", significa "búscalas con ADC" — y entonces el SDK se va a
    # preguntarle al metadata server de GCE y tarda un minuto en rendirse.
    # `firebase_admin` sólo acepta una subclase de `credentials.Base`, así que
    # la anónima de `google.auth` se envuelve.
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return firebase_admin.initialize_app(_credencial_anonima(), {"projectId": proyecto})

    try:
        # **`google.auth.default()` se fuerza AQUÍ, a propósito.**
        # `credentials.ApplicationDefault()` es perezosa: `initialize_app` no
        # lanza aunque no haya credenciales, y el error salía después dentro de
        # `verify_id_token`, donde el `except` genérico lo convertía en un 401
        # —"tu sesión no es válida"— tras 12 segundos de espera al metadata
        # server. O sea que el 503 documentado NUNCA ocurría, y quien encendiera
        # el interruptor se habría pasado la tarde depurando Firebase Auth.
        # Lo midió el revisor de motor. Se resuelve al inicializar, una vez.
        import google.auth

        google.auth.default()
        return firebase_admin.initialize_app(
            credentials.ApplicationDefault(), {"projectId": proyecto}
        )
    except CredencialesFaltantes:
        raise
    except Exception as exc:  # noqa: BLE001 — el SDK lanza varios tipos distintos
        logger.warning("Sin credenciales de Firebase: %s", type(exc).__name__)
        raise CredencialesFaltantes() from exc


def cliente_firestore() -> Any:
    """El cliente de Firestore del Admin SDK. Levanta si no hay credenciales."""
    from firebase_admin import firestore

    return firestore.client(_app_firebase())


def sin_verificar_activo() -> bool:
    """
    Si el atajo que **no verifica el token** está encendido.

    EXIGE DOS VARIABLES, Y ESO ES EL PUNTO
    --------------------------------------
    La primera versión de esto sólo miraba `FIRESTORE_EMULATOR_HOST`, y un
    revisor lo marcó: si esa variable aparece por cualquier vía —un `.env` local
    copiado al servidor, un compose heredado, una plantilla de despliegue— la
    API queda **completamente abierta**. `Authorization: Bearer <uid-de-la-
    víctima>` leería y escribiría la cartera de cualquiera, y los uid de Firebase
    no son secretos. Un solo `os.environ.get` separaba "autenticado" de
    "cualquiera con curl".

    Ahora hace falta **además** `PERMITIR_TOKEN_SIN_VERIFICAR=1`, que no tiene
    ninguna otra razón de existir y que nadie copia por accidente. Y se grita al
    log: un servicio que dejó de autenticar no puede hacerlo en silencio.
    """
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return False
    if os.environ.get("PERMITIR_TOKEN_SIN_VERIFICAR") != "1":
        return False
    logger.error(
        "AUTENTICACION DESACTIVADA: PERMITIR_TOKEN_SIN_VERIFICAR=1 con emulador. "
        "Cualquiera puede leer y escribir la cartera de cualquier uid. "
        "Esto NUNCA debe estar puesto fuera de una corrida de tests."
    )
    return True


def uid_del_token(token: str) -> str:
    """
    Verifica el ID token y devuelve el uid.

    Con el atajo de pruebas encendido —**dos** variables, ver
    `sin_verificar_activo`— el token se toma como el uid literal, porque el
    emulador de Firestore no trae emulador de Auth y no hay llaves contra las
    que validar.
    """
    if sin_verificar_activo():
        return token

    from firebase_admin import auth as auth_admin

    # `_app_firebase()` FUERA del try: si levanta `CredencialesFaltantes`, tiene
    # que salir como 503 y no disfrazarse del 401 genérico de abajo.
    app = _app_firebase()
    try:
        return str(auth_admin.verify_id_token(token, app=app)["uid"])
    except Exception as exc:  # noqa: BLE001 — el SDK lanza varios tipos distintos
        # El detalle del SDK NO se propaga: distingue "token expirado" de "token
        # de otro proyecto" y eso le sirve a quien sondea, no al usuario.
        logger.info("ID token rechazado: %s", type(exc).__name__)
        raise FiscalAgentError(
            "Tu sesión no es válida o expiró. Vuelve a iniciar sesión.", status_code=401
        ) from exc


async def usuario_actual(authorization: str | None = Header(default=None)) -> str:
    """
    Dependencia de FastAPI: el uid de quien hace el request.

    Sin encabezado, o con uno mal formado, es **401 y no 403**: 403 diría "sé
    quién eres y no puedes", y aquí no se sabe quién es.
    """
    if not authorization:
        raise FiscalAgentError(
            "Falta el encabezado Authorization con tu sesión de Firebase.", status_code=401
        )
    partes = authorization.split(None, 1)
    if len(partes) != 2 or partes[0].lower() != "bearer" or not partes[1].strip():
        raise FiscalAgentError(
            "El encabezado Authorization debe ser 'Bearer <ID token>'.", status_code=401
        )
    return uid_del_token(partes[1].strip())
