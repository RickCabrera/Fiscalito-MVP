"""
La dependencia que protege `/api/v1` entero (P0-02).

Se monta al incluir cada router en `app/main.py`:

    app.include_router(x.router, prefix="/api/v1", dependencies=PROTEGIDO)

Así un router queda protegido por estar montado como los demás, y
`tests/test_acceso_rutas.py` recorre TODAS las rutas de `/api/v1` y exige 401 sin token
(salvo la lista blanca `RUTAS_PUBLICAS`): un router montado sin la dependencia se ve en rojo.

Depende de `usuario_actual` (no lo reimplementa): FastAPI resuelve una sola vez por request
cada dependencia, así que las rutas que además piden `contexto_actual` no verifican el
token dos veces, y el override de `tests/conftest.py` cubre las dos.
"""

from fastapi import Depends

from app.acceso.limitador import limite_por_minuto, obtener_limitador
from app.auth_firebase import usuario_actual
from app.exceptions import LimiteExcedido

# Rutas de /api/v1 que NO llevan el token de Firebase, con la razón. Hoy sólo el push del
# checador, que se autentica con su propio token de dispositivo (ver `acceso/dispositivos`).
# Un webhook público nuevo (pagos, WhatsApp) se declara aquí, con su verificación propia
# (firma del proveedor) dentro de la ruta, y se monta SIN `PROTEGIDO`.
RUTAS_PUBLICAS: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/asistencia/eventos"): "Push del checador: token de dispositivo.",
    ("GET", "/api/v1/recibos/descarga/{envio_id}/{archivo}"): (
        "P4-13: WhatsApp baja el recibo de aquí; enlace firmado con HMAC y vigencia."
    ),
    ("GET", "/api/v1/documentos/descarga/{envio_id}/{archivo}"): (
        "P5-05: WhatsApp baja el documento del cliente de aquí; enlace firmado con HMAC."
    ),
}


def aplicar_limite(llave: str, limite: int, que: str) -> None:
    """429 con `Retry-After` si `llave` ya gastó su cupo de la ventana."""
    espera = obtener_limitador().consumir(llave, limite)
    if espera is not None:
        raise LimiteExcedido(
            f"Demasiadas {que}: el límite es {limite} por minuto. Intenta de nuevo en unos "
            "segundos.",
            reintentar_en=espera,
        )


def usuario_autenticado(uid: str = Depends(usuario_actual)) -> str:
    """uid autenticado y dentro de su límite de peticiones por minuto."""
    aplicar_limite(f"usuario:{uid}", limite_por_minuto(), "peticiones")
    return uid


# Lo que se pasa como `dependencies=` al montar un router protegido.
PROTEGIDO = [Depends(usuario_autenticado)]
