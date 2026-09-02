"""
CRUD de la cartera del despacho, con el backend como dueño del dato. (R-07)

QUÉ RESUELVE, QUE NO ES "MOVER EL CRUD DE LADO"
-----------------------------------------------
Hasta aquí había **dos dueños del mismo dato**: el front escribía Firestore
directo y el backend calculaba sobre la plantilla que el front le mandaba en el
body de `POST /nomina/calcular-periodo`. Con la plantilla viajando por el
cliente, "afirmar un cliente y calcular otro" cabe en un JSON — y el guard del
backend no puede atraparlo, porque `cliente` y `empleados` vendrían coherentes
entre sí y ser de otro. Es el bloqueante que E-03 dejó anotado.

Este módulo construye **la mitad** de eso: el CRUD y su dueño.

**LA OTRA MITAD NO ESTÁ CONSTRUIDA, Y HAY QUE DECIRLO AQUÍ.** El tercer criterio
de R-07 —"el cálculo de nómina lee la misma fuente"— **no se cumple**, ni con el
interruptor apagado ni encendido. `routes/nomina.py` no se tocó:
`POST /nomina/calcular-periodo` sigue recibiendo `empleados` en el cuerpo y el
front sigue armándolo con `plantillaDeNomina`. Encender `VITE_CARTERA_BACKEND`
sólo cambia de dónde saca el navegador esa plantilla; **el agujero que este
docstring describe sigue abierto igual que antes.**

Una versión anterior de este comentario afirmaba lo contrario. Era falso, y lo
encontró el revisor de motor. Que el cálculo lea `listar_empleados` en vez de
creerle al cuerpo es tarea propia, anotada en el backlog.

QUÉ **NO** ESTÁ AQUÍ
--------------------
**Dispositivos.** R-04 los dejó viviendo en Firestore escritos por el front, y
meterlos aquí en la misma corrida haría nacer la colección con dos dueños dentro
del mismo día — el problema que R-07 viene a cerrar, reintroducido de lado.
Migrarlos es tarea propia, cuando el interruptor de esta se encienda.

EL `uid` VIENE DEL TOKEN, SIEMPRE
---------------------------------
Ninguna ruta de este archivo acepta un uid por parámetro. Ver `auth_firebase.py`.

DEMO — no: esto es el primer endpoint del repo pensado para producción, y por eso
es también el primero que exige autenticación. El resto de `/api/v1` sigue
abierto (S-00b), y eso **no cambia** aquí.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.auth_firebase import cliente_firestore, usuario_actual
from app.exceptions import FiscalAgentError
from app.repositorio_cartera import (
    CarteraEnMemoria,
    FirestoreCartera,
    RepositorioCartera,
)
from app.schemas.cartera import (
    ClienteCarteraSchema,
    ClientesCarteraResponse,
    EmpleadosCarteraResponse,
    OperacionResponse,
)
from app.schemas.declaraciones import ErrorResponse
from app.schemas.empleado import EmpleadoCarteraSchema

router = APIRouter(tags=["Cartera del despacho"])

# Sustituible por `app.dependency_overrides` en los tests. En producción se
# construye por request —el cliente de Firestore es barato y `firebase_admin`
# cachea la app— y así un despliegue sin credenciales falla con el 503 que
# explica qué falta, en vez de reventar al importar el módulo.
_REPO_DE_PRUEBA: CarteraEnMemoria | None = None


def repositorio() -> RepositorioCartera:
    if _REPO_DE_PRUEBA is not None:
        return _REPO_DE_PRUEBA
    return FirestoreCartera(cliente_firestore())


def _sin_id(datos: dict) -> dict:
    """
    El `id` no se escribe DENTRO del documento: ya es el nombre del documento.

    Guardarlo dos veces deja dos verdades que se pueden separar — y la que
    ganaría al leer es la del nombre, así que la del cuerpo sería la mentira
    silenciosa.
    """
    return {k: v for k, v in datos.items() if k != "id"}


@router.get(
    "/cartera/clientes",
    response_model=ClientesCarteraResponse,
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="Los clientes del despacho autenticado",
    description="Los clientes de **quien hace el request**, resueltos desde el ID token de "
    "Firebase. No hay parámetro de uid: pasarlo por el cuerpo o por la URL haría que "
    "cualquiera leyera la cartera de cualquiera cambiando un renglón.",
)
def listar_clientes(
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> ClientesCarteraResponse:
    clientes = repo.listar_clientes(uid)
    return ClientesCarteraResponse(total=len(clientes), clientes=tuple(clientes))


@router.put(
    "/cartera/clientes/{cliente_id}",
    response_model=OperacionResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Alta o edición de un cliente",
    description="Idempotente: el mismo `cliente_id` sobrescribe. El cuerpo se valida "
    "contra `ClienteCarteraSchema`, así que una prima de riesgo fuera del Art. 72 o una "
    "periodicidad desconocida se rechazan aquí y no tres pantallas después.",
)
def guardar_cliente(
    cliente_id: str,
    cliente: ClienteCarteraSchema,
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> OperacionResponse:
    if cliente.id != cliente_id:
        # No se "arregla" en silencio: un id que no cuadra entre la URL y el
        # cuerpo significa que alguien construyó el request mal, y adivinar cuál
        # de los dos vale escribiría el cliente equivocado.
        raise FiscalAgentError(
            f"El id de la URL ({cliente_id!r}) no coincide con el del cuerpo "
            f"({cliente.id!r}).",
            status_code=422,
        )
    repo.guardar_cliente(uid, cliente_id, _sin_id(cliente.model_dump(mode="json")))
    return OperacionResponse(mensaje=f"Cliente {cliente_id} guardado.")


@router.delete(
    "/cartera/clientes/{cliente_id}",
    response_model=OperacionResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Baja de un cliente, con sus empleados",
    description="**Borra en cascada.** Firestore no lo hace solo: sin esto los empleados "
    "quedarían huérfanos —con su salario y su NSS— y reaparecerían al recrear un cliente "
    "con el mismo id.",
)
def borrar_cliente(
    cliente_id: str,
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> OperacionResponse:
    repo.borrar_cliente(uid, cliente_id)
    return OperacionResponse(mensaje=f"Cliente {cliente_id} dado de baja.")


@router.get(
    "/cartera/clientes/{cliente_id}/empleados",
    response_model=EmpleadosCarteraResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="La plantilla de un cliente del despacho",
    description="La plantilla del cliente, leída de la cartera que este mismo CRUD "
    "escribe. Distinta de `/despacho/clientes/{id}/empleados`, que es la SEMILLA de "
    "demostración y no la cartera de nadie. "
    "**Todavía NADIE la consume para calcular.** `POST /nomina/calcular-periodo` sigue "
    "recibiendo la plantilla en el cuerpo, así que el tercer criterio de R-07 —*el "
    "cálculo lee la misma fuente*— **no se cumple**. Es tarea propia, y está anotada.",
)
def listar_empleados(
    cliente_id: str,
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> EmpleadosCarteraResponse:
    if repo.obtener_cliente(uid, cliente_id) is None:
        raise FiscalAgentError(
            f"El cliente {cliente_id!r} no está en tu cartera.", status_code=404
        )
    # **La lectura NO es estricta, y esto costó un bloqueo.** La primera versión
    # hacía `EmpleadoCarteraSchema(**e)` a secas: un documento guardado por una
    # versión anterior de la app —un NSS de 9 dígitos, un campo que faltaba—
    # producía un **500**, y como el front pide los empleados de todos los
    # clientes dentro de un `Promise.all`, un solo documento legado dejaba la
    # cartera COMPLETA en cero. El endpoint de clientes ya era laxo por esta
    # razón exacta; éste no lo era, y es el que más duele.
    #
    # Los que no pasan se **reportan en la respuesta**, no se esconden. Y esa
    # frase termina ahí a propósito: **el front todavía no los pinta**, así que
    # desde donde está sentado el contador ese empleado sigue quedando fuera del
    # cálculo sin verlo. Compárese con `sin_vincular`, que sí llega a la ficha, a
    # la pantalla de nómina y al PDF — eso es "no en silencio"; esto es la mitad
    # de arriba. Pintarlos es tarea pendiente y está anotada.
    #
    # `total` EXCLUYE a los ilegibles: un cliente con 4 documentos y 1 que no
    # valida reporta 3.
    empleados: list[EmpleadoCarteraSchema] = []
    ilegibles: list[str] = []
    for crudo in repo.listar_empleados(uid, cliente_id):
        try:
            empleados.append(EmpleadoCarteraSchema(**crudo))
        except ValidationError:
            ilegibles.append(str(crudo.get("empleado_no", "?")))

    return EmpleadosCarteraResponse(
        cliente_id=cliente_id,
        total=len(empleados),
        # Se cuenta aquí y no en la UI, igual que en la semilla: un aviso que
        # depende de que alguien se acuerde de filtrar es un aviso que un día no
        # sale.
        sin_vincular=sum(1 for e in empleados if not e.vinculado_al_checador),
        ilegibles=tuple(ilegibles),
        empleados=tuple(empleados),
    )


@router.put(
    "/cartera/clientes/{cliente_id}/empleados/{empleado_no}",
    response_model=OperacionResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Alta o edición de un empleado",
    description="El `empleado_no` de la URL es la llave del CÁLCULO. `employee_no`, en el "
    "cuerpo, es la del CHECADOR y puede ser nula — son distintas y fundirlas es el defecto "
    "que G-02 vino a arreglar. El NSS se valida aquí igual que en el front: 11 dígitos o "
    "vacío, sin exigir el verificador (§D25).",
)
def guardar_empleado(
    cliente_id: str,
    empleado_no: str,
    empleado: EmpleadoCarteraSchema,
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> OperacionResponse:
    if empleado.empleado_no != empleado_no:
        raise FiscalAgentError(
            f"El número de la URL ({empleado_no!r}) no coincide con el del cuerpo "
            f"({empleado.empleado_no!r}).",
            status_code=422,
        )
    repo.guardar_empleado(uid, cliente_id, empleado_no, empleado.model_dump(mode="json"))
    return OperacionResponse(mensaje=f"Empleado {empleado_no} guardado.")


@router.delete(
    "/cartera/clientes/{cliente_id}/empleados/{empleado_no}",
    response_model=OperacionResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Baja de un empleado",
)
def borrar_empleado(
    cliente_id: str,
    empleado_no: str,
    uid: str = Depends(usuario_actual),
    repo: RepositorioCartera = Depends(repositorio),
) -> OperacionResponse:
    repo.borrar_empleado(uid, cliente_id, empleado_no)
    return OperacionResponse(mensaje=f"Empleado {empleado_no} dado de baja.")
