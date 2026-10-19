"""
Bóveda de credenciales del cliente (P0-05): `/api/v1/clientes/{clave}/credenciales`.

- POST (multipart: `cer`, `key`, `password`, `tipo`): valida y guarda cifrada.
- GET: metadatos (tipo, RFC, número de certificado, vigencia, días para vencer).
- DELETE /{id}: borra (destruye los secretos y la deja inactiva).

Sólo `dueno` y `contador`. La respuesta nunca trae la llave ni la contraseña.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.credenciales import servicio
from app.exceptions import FiscalAgentError
from app.tenancy import Contexto, cliente_o_404, contexto_actual, exigir_rol

router = APIRouter(prefix="/clientes/{clave}/credenciales", tags=["credenciales"])

ROLES = ("dueno", "contador")
# Un .cer/.key del SAT pesa ~1-2 KB. 64 KB deja holgura y corta subidas absurdas.
TAMANO_MAXIMO = 64 * 1024


async def _leer(archivo: UploadFile, nombre: str) -> bytes:
    datos = await archivo.read(TAMANO_MAXIMO + 1)
    if len(datos) > TAMANO_MAXIMO:
        raise FiscalAgentError(
            f"El archivo {nombre} es demasiado grande para ser un {nombre} del SAT.",
            status_code=422,
        )
    return datos


@router.post("")
async def subir_credencial(
    clave: str,
    tipo: str = Form(...),
    password: str = Form(...),
    cer: UploadFile = File(...),
    key: UploadFile = File(...),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Valida el par .cer/.key con su contraseña y lo guarda cifrado."""
    exigir_rol(ctx, *ROLES)
    cliente = cliente_o_404(ctx, clave)
    cer_der = await _leer(cer, ".cer")
    key_der = await _leer(key, ".key")
    cred = servicio.guardar(ctx.db, cliente, tipo, cer_der, key_der, password, ctx.uid)
    return {"exito": True, "credencial": servicio.metadatos(cred)}


@router.get("")
def listar_credenciales(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Credenciales activas del cliente (sólo metadatos)."""
    exigir_rol(ctx, *ROLES)
    cliente = cliente_o_404(ctx, clave)
    return {
        "exito": True,
        "credenciales": [servicio.metadatos(c) for c in servicio.activas(ctx.db, cliente)],
    }


@router.delete("/{credencial_id}")
def borrar_credencial(
    clave: str, credencial_id: int, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """Borra la credencial del cliente."""
    exigir_rol(ctx, *ROLES)
    cliente = cliente_o_404(ctx, clave)
    servicio.desactivar(ctx.db, cliente, credencial_id)
    return {"exito": True}
