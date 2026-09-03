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
from app.nomina_engine.tablas_imss import (
    PRIMA_RT_MAXIMA,
    PRIMA_RT_MINIMA,
    prima_media_clase,
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
    PrimasDeRiesgoResponse,
)
from app.schemas.empleado import (
    EmpleadoCarteraSchema,
    EmpleadosClienteResponse,
    EstatusEnrolamiento,
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


def _empleado_cartera(empleado: EmpleadoCliente) -> EmpleadoCarteraSchema:
    """
    Traduce un empleado de la semilla al modelo canónico de la cartera.

    **`nss` se queda vacío y `fecha_alta` puede ser `None`.** Los nueve del caso
    real salen de fixtures anonimizadas con montos reales: ponerles un NSS
    inventado lo dejaría junto a datos reales, que es justo la mezcla que
    después alguien confunde con dato verdadero. Mismo criterio que ya usa
    `despacho_demo.py` para la fecha de alta.

    **`employee_no = empleado_no`** porque estos empleados YA están enrolados en
    el checador de la demo: es lo que hace que la demo siga funcionando igual
    que antes de G-02. Un empleado capturado desde la UI empieza sin llave.
    """
    return EmpleadoCarteraSchema(
        empleado_no=empleado.empleado_no,
        nombre=empleado.nombre,
        puesto=empleado.puesto,
        salario_diario=empleado.salario_diario,
        salario_diario_integrado=empleado.salario_diario_integrado,
        zona=empleado.zona,
        fecha_alta=empleado.fecha_alta,
        employee_no=empleado.empleado_no,
        enrolamiento=EstatusEnrolamiento.ENROLADO,
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

ADVERTENCIAS_CALENDARIO_EMPRESA = (
    ADVERTENCIAS_CALENDARIO[0],
    "Las obligaciones marcadas como condicionales dependen de datos que la empresa no "
    "registra (tipo de salario, personalidad jurídica). Verifícalas antes de confiar en ellas.",
    "Ninguna de estas fechas depende todavía de los datos de la empresa: son las de "
    "cualquier patrón. El ajuste por sexto dígito del RFC no está implementado.",
)


def _obligacion_de_la_empresa(o: ObligacionPatronal) -> ObligacionPatronalSchema:
    """
    La misma obligación, sin dueño que etiquetar (O-01).

    `cliente_nombre` va **vacío a propósito**, no con un nombre inventado ni con
    el de un cliente del catálogo: en modo empresa única hay un solo patrón, el
    backend no sabe cómo se llama —ni tiene por qué, no viaja en el query
    string— y repetir la misma etiqueta en cada renglón es ruido. El front
    descarta el vacío al agrupar (`calendarioPatronal.ts`).

    `cliente_id` sí lleva `empresa`, que es el id real del cliente implícito en
    `users/{uid}/clientes/empresa`: sirve de llave y no afirma ningún nombre.
    """
    return ObligacionPatronalSchema(
        cliente_id="empresa",
        cliente_nombre="",
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
    empresa_unica: bool = Query(
        default=False,
        description="`true` = hay **un solo patrón**, no una cartera: devuelve UN juego de "
        "obligaciones en vez de repetirlo por cada cliente del catálogo. `cliente_id` vale "
        "`empresa` y `cliente_nombre` viene **vacío**, porque etiquetar cada renglón con el "
        "mismo nombre es ruido y el nombre del patrón no tiene por qué viajar en un query "
        "string. Los dos campos siguen siendo obligatorios en el schema: cambia su valor, no "
        "su presencia (O-01).",
    ),
) -> CalendarioPatronalResponse:
    # El rango lo valida el motor (levanta `FiscalValidationError`), pero se
    # comprueba aquí para no construir tres calendarios antes de rechazar.
    if not ANIO_MINIMO <= anio_de_las_cuotas <= ANIO_MAXIMO:
        raise FiscalValidationError(
            f"Año fuera de rango: {anio_de_las_cuotas}. "
            f"Debe estar entre {ANIO_MINIMO} y {ANIO_MAXIMO}."
        )

    # `tiene_salario_variable` y `personalidad` van en `None` —o sea "no
    # consta"— porque `ClienteDespacho` no registra ninguno de los dos. El
    # motor devuelve entonces esas obligaciones marcadas `condicional`, que
    # es distinto de omitirlas y distinto de afirmarlas.
    #
    # O-01: con `empresa_unica` **no se hace el fan-out**. Es la MISMA llamada a
    # `calendario_patronal()`, sin repetirla por cliente: no hay un segundo
    # generador de calendario, que es lo que `knowledge_base/nomina/
    # 25_calendario_laboral_2026.md` §4 llama "un bug esperando". Ninguna fecha
    # depende del cliente —lo dicen las propias advertencias de abajo—, así que
    # quitar el fan-out no quita información: quita triplicado.
    if empresa_unica:
        obligaciones = [
            _obligacion_de_la_empresa(o) for o in calendario_patronal(anio_de_las_cuotas)
        ]
    else:
        obligaciones = [
            _obligacion(cliente, o)
            for cliente in CLIENTES
            for o in calendario_patronal(anio_de_las_cuotas)
        ]
    # Orden global: por fecha, y dentro del día por obligación y cliente, para
    # que la pantalla pueda agrupar sin reordenar.
    obligaciones.sort(key=lambda o: (o.fecha_limite, o.clave, o.cliente_nombre))

    # Sin obligaciones no hay rango que anunciar. Hoy es inalcanzable —`CLIENTES`
    # es constante y no vacía— pero la pantalla SÍ pinta un estado vacío, y una
    # de las dos mitades sobraría: indexar aquí sería un 500 en ese camino.
    return CalendarioPatronalResponse(
        anio_de_las_cuotas=anio_de_las_cuotas,
        cubre_desde=obligaciones[0].fecha_limite if obligaciones else None,
        cubre_hasta=obligaciones[-1].fecha_limite if obligaciones else None,
        total_obligaciones=len(obligaciones),
        obligaciones=tuple(obligaciones),
        advertencias=(
            ADVERTENCIAS_CALENDARIO_EMPRESA if empresa_unica else ADVERTENCIAS_CALENDARIO
        ),
    )


@router.get(
    "/despacho/clientes/{cliente_id}/empleados",
    response_model=EmpleadosClienteResponse,
    responses={404: {"model": ErrorResponse}},
    summary=_AVISO + "Semilla de empleados de un cliente",
    description=_AVISO
    + "Los empleados del cliente en el **modelo canónico de la cartera** "
    "(`EmpleadoCarteraSchema`), que es el mismo que el despacho guarda en Firestore. "
    "Es una SEMILLA, no un CRUD: el backend está declarado stateless y no persiste "
    "altas ni bajas — el dueño del dato es `users/{uid}/clientes/{id}/empleados/{id}` "
    "(PLAN_NOMINA §3.3). Esta ruta existe para que una cuenta nueva arranque con los "
    "tres clientes de demostración sin que el front invente sus datos.\n\n"
    "**`employee_no` viene igual a `empleado_no` para todos**, porque estos empleados "
    "ya están dados de alta en el checador de la demo. Un empleado capturado desde la "
    "UI puede no tenerlo, y entonces `sin_vincular` lo cuenta.",
)
async def empleados_del_cliente(cliente_id: str) -> EmpleadosClienteResponse:
    cliente = cliente_por_id(cliente_id)
    if cliente is None:
        # Mismo 404 de dominio que la ficha: `FiscalAgentError` para que salga
        # con el sobre `{exito, error}` y no con el `detail` pelón de FastAPI,
        # que el front lee como "esta ruta no existe" (ver `errorApi.ts`).
        conocidos = ", ".join(c.id for c in CLIENTES)
        raise FiscalAgentError(
            f"El cliente {cliente_id!r} no está en la cartera de la demo. "
            f"Clientes disponibles: {conocidos}.",
            status_code=404,
        )

    empleados = tuple(_empleado_cartera(e) for e in cliente.empleados)
    return EmpleadosClienteResponse(
        cliente_id=cliente.id,
        origen=cliente.origen,
        total=len(empleados),
        # Se cuenta aquí, no en la UI: un aviso que depende de que alguien se
        # acuerde de filtrar es un aviso que un día no sale.
        sin_vincular=sum(1 for e in empleados if not e.vinculado_al_checador),
        empleados=empleados,
    )


@router.get(
    "/despacho/primas-de-riesgo",
    response_model=PrimasDeRiesgoResponse,
    responses={422: {"model": ErrorResponse}},
    summary=_AVISO + "Primas medias por clase de riesgo, con su vigencia",
    description=_AVISO
    + "Las primas **medias** por clase (Art. 73 LSS), que son las que aplican a una "
    "empresa nueva, más los límites del Art. 72. Existe para que el formulario de alta "
    "de cliente no las copie a TypeScript: ahí quedarían **sin vigencia, sin fuente y sin "
    "test**, y en el año siguiente propondrían en silencio las primas del anterior. En el "
    "motor se leen por `prima_media_clase(clase, fecha)`, con función de vigencia.\n\n"
    "**Son un punto de partida, no la prima del cliente:** la prima real la autodetermina "
    "el patrón cada febrero con su siniestralidad (Art. 74 LSS).",
)
async def primas_de_riesgo(
    fecha: date = Query(
        default_factory=date.today,
        description="Fecha de vigencia. La tabla es por año.",
    ),
) -> PrimasDeRiesgoResponse:
    return PrimasDeRiesgoResponse(
        fecha=fecha,
        minima=PRIMA_RT_MINIMA,
        maxima=PRIMA_RT_MAXIMA,
        medias_por_clase={
            str(clase): prima_media_clase(clase, fecha) for clase in (1, 2, 3, 4, 5)
        },
        fundamento="Arts. 72 y 73 LSS. La prima real se autodetermina en febrero (Art. 74).",
    )
