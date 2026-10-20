"""
Endpoints de asistencia (checador).

**DEMO** — ver `docs/D-DEMO-CHECADOR.md`: almacenamiento **en memoria del proceso**, que se
pierde al reiniciar; no desplegar. Producción está apagada por decisión de Ricardo (S-08).

AUTENTICACIÓN (P0-02)
---------------------
- `POST /asistencia/eventos` es la única ruta de `/api/v1` que acepta algo distinto del ID
  token de Firebase: el **token del dispositivo** (`?token=` o `X-Token-Dispositivo`), porque
  el Hikvision no sabe pedir un ID token. El token decide despacho y cliente; un `?cliente=`
  distinto del suyo es 403. Sin token de dispositivo, se acepta la sesión de Firebase (el
  simulador y las pantallas la usan).
- El resto (consultar, cerrar periodo, administrar tokens) exige la sesión de Firebase, que
  se monta en `app/main.py` para todo el router salvo `router_publico`.

AISLAMIENTO ENTRE DESPACHOS
---------------------------
Los clientes de la demo (`demo`, `cafeteria`, `taller`) son un catálogo compartido, así que
el almacén se indexa por `despacho::cliente` (`llave_almacen`). El despacho sale SIEMPRE del
token —de Firebase o del dispositivo—, nunca del request: un despacho no puede leer ni
cerrar las checadas de otro aunque use la misma clave de cliente.

El `cliente` viaja como **query param con default**, no en el cuerpo: la URL que se
configura en el dispositivo es fija y el cuerpo lo arma el aparato.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.acceso import dispositivos
from app.acceso.dependencias import aplicar_limite
from app.acceso.limitador import limite_por_minuto
from app.asistencia.almacen import almacen, llave_almacen
from app.asistencia.hikvision import parse_acs_event
from app.asistencia.incidencias import cerrar_periodo
from app.auth_firebase import usuario_actual
from app.constants import CLIENTE_DEMO
from app.db.session import obtener_db
from app.despacho_demo import cliente_por_id
from app.exceptions import FiscalAgentError, FiscalValidationError
from app.modelos.nucleo import Cliente, Dispositivo
from app.schemas.acceso import (
    EmitirTokenRequest,
    TokenDispositivoSchema,
    TokenEmitidoResponse,
    TokenRevocadoResponse,
    TokensResponse,
)
from app.schemas.asistencia import (
    CerrarPeriodoRequest,
    CerrarPeriodoResponse,
    EventosRecibidosResponse,
    EventosResponse,
    FuenteChecada,
)
from app.tenancy import Contexto, asegurar_usuario, cliente_o_404, contexto_actual, exigir_rol

# Montado con la sesión de Firebase obligatoria (ver `app/main.py`).
router = APIRouter(tags=["Asistencia (demo)"])
# Montado SIN la dependencia global: se autentica por dentro (dispositivo o Firebase).
router_publico = APIRouter(tags=["Asistencia (demo)"])

_AVISO = "DEMO — almacenamiento en memoria, no desplegar. "
ROLES_TOKENS = ("dueno", "contador")


@dataclass(frozen=True)
class Emisor:
    """Quién empuja checadas: su despacho y, si es un dispositivo, el cliente de su token."""

    despacho_id: str
    cliente_fijo: str | None


def _uid_de_firebase(request: Request, authorization: str) -> str:
    """
    El uid del encabezado `Authorization`, por la MISMA dependencia que el resto de la API.

    Se resuelve a mano porque aquí la sesión es opcional (puede venir un token de
    dispositivo en su lugar) y una dependencia de FastAPI no puede ser "opcional si falla".
    Se respeta `dependency_overrides` para que los tests autentiquen igual que en todas las
    demás rutas.
    """
    verificar = request.app.dependency_overrides.get(usuario_actual, usuario_actual)
    return verificar(authorization=authorization)


def emisor_de_eventos(
    request: Request,
    token: str | None = Query(
        default=None, description="Token del dispositivo (la URL que se configura en el aparato)"
    ),
    x_token_dispositivo: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(obtener_db),
) -> Emisor:
    """Dispositivo (por su token) o usuario (por su sesión de Firebase); si no, 401."""
    secreto = x_token_dispositivo or token
    if secreto:
        checador = dispositivos.resolver(db, secreto)
        aplicar_limite(f"dispositivo:{checador.token_id}", limite_por_minuto(), "peticiones")
        return Emisor(despacho_id=checador.despacho_id, cliente_fijo=checador.cliente_clave)
    if authorization:
        uid = _uid_de_firebase(request, authorization)
        aplicar_limite(f"usuario:{uid}", limite_por_minuto(), "peticiones")
        return Emisor(despacho_id=asegurar_usuario(db, uid).despacho_id, cliente_fijo=None)
    raise FiscalAgentError(
        "Falta autenticación: el checador manda su token de dispositivo (`?token=` o "
        "`X-Token-Dispositivo`) y las pantallas la sesión de Firebase (`Authorization`).",
        status_code=401,
    )


async def _cuerpo_json(request: Request) -> dict:
    """
    Lee el cuerpo como JSON, venga como `application/json` o como multipart.

    El Hikvision manda `multipart/form-data` cuando adjunta la foto del
    reconocimiento: ahi el evento va en una parte y la imagen en otra. Solo se
    lee la parte JSON; la foto **no se guarda** (es un dato biometrico y no
    hace falta para calcular nada).

    Se revisan **todas** las partes, con y sin `filename`. Starlette convierte
    una parte en `str` solo cuando su Content-Disposition NO trae filename; con
    filename llega como `UploadFile`. Varios firmwares mandan la parte del
    evento con `Content-Type: application/json` **y** filename, asi que mirar
    solo las de tipo `str` rechazaria el batch entero contra el aparato real.
    """
    tipo = request.headers.get("content-type", "")
    if tipo.startswith("multipart/form-data"):
        formulario = await request.form()
        for valor in formulario.values():
            if isinstance(valor, str):
                crudo: bytes | str = valor
            else:
                crudo = await valor.read()
            try:
                contenido = json.loads(crudo)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # la parte de la imagen no decodifica: se salta
            if isinstance(contenido, dict):
                return contenido
        raise FiscalValidationError(
            "El multipart no trae ninguna parte con un objeto JSON de evento."
        )
    try:
        contenido = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FiscalValidationError("El cuerpo no es JSON válido.") from exc
    if not isinstance(contenido, dict):
        raise FiscalValidationError("El cuerpo debe ser un objeto JSON.")
    return contenido


@router_publico.post(
    "/asistencia/eventos",
    response_model=EventosRecibidosResponse,
    summary=_AVISO + "Recibir checadas del checador",
    description=_AVISO
    + "Acepta el cuerpo `AcsEvent` tal como lo manda el Hikvision (JSON o "
    "multipart con la foto) o el simulador. Deduplica por (empleado, serialNo). "
    "Autenticación: token del dispositivo (`?token=` o `X-Token-Dispositivo`), que fija "
    "despacho y cliente, o la sesión de Firebase.",
)
async def recibir_eventos(
    request: Request,
    cliente: str | None = Query(default=None, description="Id del cliente"),
    fuente: FuenteChecada = Query(default=FuenteChecada.HIKVISION),
    emisor: Emisor = Depends(emisor_de_eventos),
) -> EventosRecibidosResponse:
    if emisor.cliente_fijo is not None:
        if cliente is not None and cliente != emisor.cliente_fijo:
            raise FiscalAgentError(
                "El token de este dispositivo es de otro cliente: no puede registrar "
                f"checadas de {cliente!r}.",
                status_code=403,
            )
        cliente = emisor.cliente_fijo
    cliente = cliente or CLIENTE_DEMO
    payload = await _cuerpo_json(request)
    eventos = parse_acs_event(payload, fuente=fuente)
    llave = llave_almacen(emisor.despacho_id, cliente)
    aceptados, duplicados = almacen.agregar(llave, eventos)
    return EventosRecibidosResponse(
        cliente=cliente,
        recibidos=aceptados,
        duplicados=duplicados,
        total_en_memoria=almacen.total(llave),
    )


def _exigir_asignado(ctx: Contexto, clave: str) -> None:
    """Un auxiliar sólo ve checadas de clientes que tiene asignados (revisor P0)."""
    if ctx.es_auxiliar:
        cliente_o_404(ctx, clave)


@router.get(
    "/asistencia/eventos",
    response_model=EventosResponse,
    summary=_AVISO + "Consultar checadas para el panel en vivo",
    description=_AVISO
    + "Devuelve los eventos en memoria del cliente EN TU DESPACHO, ordenados "
    "cronológicamente. `desde` es inclusivo. Un cliente sin eventos devuelve una lista "
    "vacía, no 404.",
)
async def consultar_eventos(
    cliente: str = Query(default=CLIENTE_DEMO),
    desde: datetime | None = Query(default=None, description="Inclusivo"),
    ctx: Contexto = Depends(contexto_actual),
) -> EventosResponse:
    _exigir_asignado(ctx, cliente)
    llave = llave_almacen(ctx.despacho_id, cliente)
    return EventosResponse(cliente=cliente, eventos=almacen.eventos(llave, desde))


@router.post(
    "/asistencia/cerrar-periodo",
    response_model=CerrarPeriodoResponse,
    summary=_AVISO + "Cerrar el periodo y calcular incidencias",
    description=_AVISO
    + "Días trabajados, faltas y retardos a partir de las checadas del periodo. "
    "`dias_cotizados` es informativo: la base de cuotas del IMSS la determina "
    "`DiasDelPeriodo` según el ramo (§D3).",
)
async def cerrar(
    req: CerrarPeriodoRequest, ctx: Contexto = Depends(contexto_actual)
) -> CerrarPeriodoResponse:
    _exigir_asignado(ctx, req.cliente)
    incidencias, desconocidos = cerrar_periodo(
        almacen.eventos(llave_almacen(ctx.despacho_id, req.cliente)),
        req.empleados,
        req.periodo,
        req.horario,
    )
    return CerrarPeriodoResponse(
        cliente=req.cliente,
        periodo=req.periodo,
        incidencias=incidencias,
        empleados_desconocidos=desconocidos,
    )


# ── Tokens de dispositivo (P0-02) ────────────────────────────────────────────


def _cliente_del_token(ctx: Contexto, clave: str) -> Cliente | None:
    """
    El cliente al que se le emite un token.

    Un cliente de `clientes` pasa por `cliente_o_404` (otro despacho = 404). Los tres de la
    demo son un catálogo estático sin renglón: se aceptan sin renglón (`None`), y sus
    checadas igual quedan aisladas por despacho en el almacén.
    """
    try:
        return cliente_o_404(ctx, clave)
    except FiscalAgentError:
        if cliente_por_id(clave) is not None:
            return None
        raise


@router.post(
    "/asistencia/tokens",
    response_model=TokenEmitidoResponse,
    status_code=201,
    summary="Emitir el token de un checador",
    description="Crea el secreto con el que un checador empuja checadas de un cliente. "
    "La respuesta es la ÚNICA vez que se ve en claro: el backend guarda su SHA-256. "
    "Se configura en el aparato como `.../api/v1/asistencia/eventos?token=<token>`. "
    "Sólo `dueno` y `contador`.",
)
def emitir_token(
    req: EmitirTokenRequest, ctx: Contexto = Depends(contexto_actual)
) -> TokenEmitidoResponse:
    exigir_rol(ctx, *ROLES_TOKENS)
    cliente = _cliente_del_token(ctx, req.cliente)
    dispositivo = None
    if req.dispositivo:
        if cliente is None:
            raise FiscalAgentError(
                f"El cliente {req.cliente!r} no tiene dispositivos dados de alta.", 404
            )
        dispositivo = ctx.db.query(Dispositivo).filter_by(
            cliente_id=cliente.id, clave=req.dispositivo
        ).one_or_none()
        if dispositivo is None:
            raise FiscalAgentError(f"No existe el dispositivo {req.dispositivo!r}.", 404)
    emitido = dispositivos.emitir(
        ctx.db, ctx.despacho_id, req.cliente, cliente, dispositivo, req.etiqueta, ctx.uid
    )
    return TokenEmitidoResponse(
        token=emitido.token,
        registro=TokenDispositivoSchema(**dispositivos.metadatos(emitido.registro)),
    )


@router.get(
    "/asistencia/tokens",
    response_model=TokensResponse,
    summary="Tokens de checador vigentes",
    description="Los tokens activos del despacho (sin el secreto), opcionalmente de un cliente.",
)
def listar_tokens(
    cliente: str | None = Query(default=None), ctx: Contexto = Depends(contexto_actual)
) -> TokensResponse:
    exigir_rol(ctx, *ROLES_TOKENS)
    return TokensResponse(
        tokens=[
            TokenDispositivoSchema(**dispositivos.metadatos(t))
            for t in dispositivos.listar(ctx.db, ctx.despacho_id, cliente)
        ]
    )


@router.delete(
    "/asistencia/tokens/{token_id}",
    response_model=TokenRevocadoResponse,
    summary="Revocar el token de un checador",
    description="El aparato deja de poder empujar checadas en el acto. Otro despacho = 404.",
)
def revocar_token(token_id: int, ctx: Contexto = Depends(contexto_actual)) -> TokenRevocadoResponse:
    exigir_rol(ctx, *ROLES_TOKENS)
    registro = dispositivos.revocar(ctx.db, ctx.despacho_id, token_id)
    return TokenRevocadoResponse(
        registro=TokenDispositivoSchema(**dispositivos.metadatos(registro))
    )
