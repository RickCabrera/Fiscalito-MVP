"""
Tokens de los checadores (P0-02): emitir, listar y revocar.

Salieron de `routes/asistencia.py` en P6-05 (tope de 300 líneas) sin cambiar comportamiento:
se registran en el mismo `router` de asistencia, que es el que monta `app/main.py`.
"""

from __future__ import annotations

from fastapi import Depends, Query

from app.acceso import dispositivos
from app.despacho_demo import cliente_por_id
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente, Dispositivo
from app.routes.asistencia import ROLES_TOKENS, router
from app.schemas.acceso import (
    EmitirTokenRequest,
    TokenDispositivoSchema,
    TokenEmitidoResponse,
    TokenRevocadoResponse,
    TokensResponse,
)
from app.tenancy import Contexto, cliente_o_404, contexto_actual, exigir_rol


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
