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

from fastapi import APIRouter, Query

from app.demo_nomina import quincena
from app.despacho_demo import (
    CLIENTES,
    FECHA_REFERENCIA_DEMO,
    ClienteDespacho,
    EmpleadoCliente,
    cliente_por_id,
)
from app.exceptions import FiscalAgentError, FiscalValidationError
from app.nomina_engine.calendario_laboral import (
    ANIO_MAXIMO,
    ANIO_MINIMO,
    ObligacionPatronal,
    calendario_patronal,
)
from app.schemas.calendario_laboral import (
    CalendarioPatronalResponse,
    ObligacionPatronalSchema,
)
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


# Lo que el calendario patronal NO cubre. Viaja en el cuerpo de la respuesta y
# no sólo en la documentación: la pantalla lo imprime tal cual, sin volver a
# redactarlo por su cuenta y sin poder quedarse desincronizada.
ADVERTENCIAS_CALENDARIO = (
    "No cubre el ISN (Impuesto Sobre Nóminas): es estatal, no hay fuente estatal en la base "
    "de conocimiento y el cliente no registra su entidad. Ver docs/decisiones-nomina.md §D24.",
    "Las obligaciones marcadas como condicionales dependen de datos que el modelo de cliente "
    "no registra (tipo de salario, personalidad jurídica). Verifícalas antes de confiar en ellas.",
    "Hoy ninguna de estas fechas depende del cliente: son las mismas para toda la cartera. "
    "Cambiarán cuando el alta de clientes (F1-09) registre RFC, entidad y personalidad.",
)


def _obligacion(cliente: ClienteDespacho, o: ObligacionPatronal) -> ObligacionPatronalSchema:
    return ObligacionPatronalSchema(
        cliente_id=cliente.id,
        cliente_nombre=cliente.nombre,
        clave=o.clave,
        nombre=o.nombre,
        descripcion=o.descripcion,
        fecha_limite=o.fecha_limite,
        periodicidad=o.periodicidad,
        periodo_cubierto=o.periodo_cubierto,
        fundamento=o.fundamento,
        regimen_de_plazo=o.regimen_de_plazo,
        condicional=o.condicional,
        nota=o.nota,
    )


@router.get(
    "/despacho/calendario",
    response_model=CalendarioPatronalResponse,
    responses={422: {"model": ErrorResponse}},
    summary=_AVISO + "Calendario de obligaciones patronales de la cartera",
    description=_AVISO
    + "Las obligaciones patronales de **todos** los clientes del despacho, ordenadas por "
    "fecha límite y etiquetadas con su cliente. `anio_de_las_cuotas` es el año del periodo "
    "que se reporta, **no** el del vencimiento: las cuotas de diciembre vencen en enero del "
    "año siguiente y sí están aquí; las de diciembre del año anterior, no. Por eso la "
    "respuesta trae `cubre_desde` y `cubre_hasta`. "
    "**Traductor, no motor:** no calcula ninguna fecha. Todas salen de "
    "`nomina_engine/calendario_laboral.py`, que es donde viven los fundamentos y los tests.",
)
async def calendario_de_la_cartera(
    anio_de_las_cuotas: int = Query(
        default_factory=lambda: date.today().year,
        description="Año del periodo que se reporta. Por defecto, el año en curso.",
    ),
) -> CalendarioPatronalResponse:
    # El rango lo valida el motor (levanta `FiscalValidationError`), pero se
    # comprueba aquí para no construir tres calendarios antes de rechazar.
    if not ANIO_MINIMO <= anio_de_las_cuotas <= ANIO_MAXIMO:
        raise FiscalValidationError(
            f"Año fuera de rango: {anio_de_las_cuotas}. "
            f"Debe estar entre {ANIO_MINIMO} y {ANIO_MAXIMO}."
        )

    obligaciones = [
        _obligacion(cliente, o)
        for cliente in CLIENTES
        # `tiene_salario_variable` y `personalidad` van en `None` —o sea "no
        # consta"— porque `ClienteDespacho` no registra ninguno de los dos. El
        # motor devuelve entonces esas obligaciones marcadas `condicional`, que
        # es distinto de omitirlas y distinto de afirmarlas.
        for o in calendario_patronal(anio_de_las_cuotas)
    ]
    # Orden global: por fecha, y dentro del día por obligación y cliente, para
    # que la pantalla pueda agrupar sin reordenar.
    obligaciones.sort(key=lambda o: (o.fecha_limite, o.clave, o.cliente_nombre))

    return CalendarioPatronalResponse(
        anio_de_las_cuotas=anio_de_las_cuotas,
        cubre_desde=obligaciones[0].fecha_limite,
        cubre_hasta=obligaciones[-1].fecha_limite,
        total_obligaciones=len(obligaciones),
        obligaciones=tuple(obligaciones),
        advertencias=ADVERTENCIAS_CALENDARIO,
    )
