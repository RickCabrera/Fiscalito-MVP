"""
Endpoints de la cartera de clientes del despacho (E-02).

**Traductor, no motor.** Toma el catálogo estático de `app/despacho_demo.py` y
lo serializa. La única derivación que hace es `periodo_sugerido`, y la delega a
`demo_nomina.quincena()` —la misma función que usan el simulador del checador y
`GET /nomina/demo/plantilla`—: dos reglas de quincena distintas darían periodos
distintos según el cliente.

DEMO — ver `docs/D-DEMO-CHECADOR.md`: sin autenticación (la del resto de
`/api/v1` está en S-00b), datos estáticos, y no se despliega.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.demo_nomina import quincena
from app.despacho_demo import (
    CLIENTES,
    FECHA_REFERENCIA_DEMO,
    ClienteDespacho,
    EmpleadoCliente,
    cliente_por_id,
)
from app.exceptions import FiscalAgentError
from app.schemas.declaraciones import ErrorResponse
from app.schemas.despacho import (
    ClienteDetalle,
    ClienteResumen,
    ClientesResponse,
    EmpleadoClienteSchema,
)
from app.schemas.nomina import PeriodoNomina

router = APIRouter(tags=["Despacho (demo)"])

_AVISO = "DEMO — sin autenticación, datos estáticos, no desplegar. "


def _resumen(cliente: ClienteDespacho) -> ClienteResumen:
    return ClienteResumen(
        id=cliente.id,
        nombre=cliente.nombre,
        giro=cliente.giro,
        origen=cliente.origen,
        num_empleados=cliente.num_empleados,
        prima_riesgo=cliente.prima_riesgo,
        clase_riesgo=cliente.clase_riesgo,
        clave_periodicidad=cliente.clave_periodicidad,
        zona=cliente.zona,
    )


def _empleado(empleado: EmpleadoCliente) -> EmpleadoClienteSchema:
    return EmpleadoClienteSchema(
        empleado_no=empleado.empleado_no,
        nombre=empleado.nombre,
        puesto=empleado.puesto,
        salario_diario=empleado.salario_diario,
        salario_diario_integrado=empleado.salario_diario_integrado,
        zona=empleado.zona,
        fecha_alta=empleado.fecha_alta,
        antiguedad_anios=empleado.antiguedad_anios,
        factor=empleado.factor,
        factor_implicito=empleado.factor_implicito,
    )


@router.get(
    "/despacho/clientes",
    response_model=ClientesResponse,
    summary=_AVISO + "Cartera de clientes del despacho",
    description=_AVISO
    + "Los clientes que lleva el despacho, con su giro, número de empleados y prima de "
    "Riesgos de Trabajo. Es un catálogo estático de demostración, no una base de datos "
    "de clientes: el alta y la persistencia son F1-09.",
)
async def listar_clientes() -> ClientesResponse:
    return ClientesResponse(clientes=tuple(_resumen(c) for c in CLIENTES))


@router.get(
    "/despacho/clientes/{cliente_id}",
    response_model=ClienteDetalle,
    responses={404: {"model": ErrorResponse}},
    summary=_AVISO + "Ficha de un cliente",
    description=_AVISO
    + "La ficha con sus empleados (salario diario, SBC, alta y factor) y el periodo "
    "sugerido. Los campos de empleado son un superconjunto compatible de "
    "`EmpleadoNominaSchema`, para que la pantalla pueda mandarlos tal cual a "
    "`POST /nomina/calcular-periodo` sin remapear. Un id desconocido responde 404, no "
    "un cliente vacío.",
)
async def ficha_cliente(cliente_id: str) -> ClienteDetalle:
    cliente = cliente_por_id(cliente_id)
    if cliente is None:
        # 404 de dominio, no `HTTPException`: así viaja por el handler global de
        # `main.py` y sale con el mismo sobre `{"exito": false, "error": ...}`
        # que todo el resto de la API, en vez de `{"detail": ...}`.
        conocidos = ", ".join(c.id for c in CLIENTES)
        raise FiscalAgentError(
            f"El cliente {cliente_id!r} no está en la cartera de la demo. "
            f"Clientes disponibles: {conocidos}.",
            status_code=404,
        )

    sugerido = quincena(date.today())
    return ClienteDetalle(
        **_resumen(cliente).model_dump(),
        empleados=tuple(_empleado(e) for e in cliente.empleados),
        # `fecha_pago` explícita, no None: la pantalla tiene que poder mostrar
        # con qué fecha se va a calcular sin replicar el default (§D18).
        periodo_sugerido=PeriodoNomina(
            inicio=sugerido.inicio, fin=sugerido.fin, fecha_pago=sugerido.fin
        ),
        fecha_referencia=FECHA_REFERENCIA_DEMO,
    )
