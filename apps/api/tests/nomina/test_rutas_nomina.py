"""
Tests del endpoint `POST /api/v1/nomina/calcular-periodo` y del tool del agente.

El endpoint es una traducción: lo que se prueba aquí es el contrato —defaults,
errores, forma de la respuesta— y **no** la aritmética, que ya mide
`test_calculo_periodo.py` contra los literales de F1.
"""

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.asistencia.almacen import almacen
from app.constants import CLIENTE_DEMO
from app.demo_nomina import PLANTILLA_DEMO
from app.main import app
from app.routes.agente import (
    SYSTEM_PROMPT_ANTHROPIC,
    SYSTEM_PROMPT_OPENAI,
)
from app.services.agent_tools import TOOLS_ANTHROPIC, TOOLS_OPENAI, ejecutar_tool
from app.services.agent_tools_nomina import calcular_nomina_periodo

CALCULAR = "/api/v1/nomina/calcular-periodo"
EVENTOS = "/api/v1/asistencia/eventos"

PERIODO = {"inicio": "2026-08-16", "fin": "2026-08-31"}
PARAMETROS = {"prima_riesgo": "0.0054355", "clave_periodicidad": "04"}


@pytest.fixture(autouse=True)
def _almacen_limpio():
    almacen.reset()
    yield
    almacen.reset()


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


def _incidencias(faltas_de=(), dias=16):
    return [
        {
            "empleado_no": e.empleado_no,
            "dias_periodo": dias,
            "faltas": faltas_de.count(e.empleado_no),
            "dias_ausentismo": faltas_de.count(e.empleado_no),
        }
        for e in PLANTILLA_DEMO
    ]


def _cuerpo(**extra):
    return {
        "cliente": CLIENTE_DEMO,
        "periodo": PERIODO,
        "incidencias": _incidencias(),
        "parametros": PARAMETROS,
        **extra,
    }


class TestContrato:
    def test_calcula_la_quincena_de_los_nueve_empleados(self, cliente_http):
        cuerpo = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        assert cuerpo["exito"] is True
        assert len(cuerpo["recibos"]) == 9
        assert {r["empleado_no"] for r in cuerpo["recibos"]} == {
            e.empleado_no for e in PLANTILLA_DEMO
        }
        assert cuerpo["porcion_mensual"]["empleados"] == 9

    def test_omitir_empleados_usa_la_plantilla_de_la_demo(self, cliente_http):
        cuerpo = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        assert cuerpo["origen_plantilla"] == "demo"
        nombres = {r["nombre"] for r in cuerpo["recibos"]}
        assert nombres == {e.nombre for e in PLANTILLA_DEMO}

    def test_un_cliente_que_no_es_el_de_la_demo_no_hereda_la_plantilla(
        self, cliente_http
    ):
        """
        Calcularle a un cliente real la nómina de otras nueve personas —y
        dejar que la exporte en PDF— es peor que responder un error.
        """
        respuesta = cliente_http.post(CALCULAR, json=_cuerpo(cliente="acme"))
        assert respuesta.status_code == 422
        assert "su propia plantilla" in respuesta.json()["error"]

    def test_con_empleados_en_el_cuerpo_el_origen_lo_dice(self, cliente_http):
        empleados = [
            {
                "empleado_no": "X-01",
                "nombre": "PERSONA DE PRUEBA",
                "salario_diario": "400.00",
                "salario_diario_integrado": "420.00",
            }
        ]
        cuerpo = cliente_http.post(
            CALCULAR,
            json={
                "cliente": "acme",
                "periodo": PERIODO,
                "incidencias": [
                    {
                        "empleado_no": "X-01",
                        "dias_periodo": 16,
                        "faltas": 0,
                        "dias_ausentismo": 0,
                    }
                ],
                "parametros": PARAMETROS,
                "empleados": empleados,
            },
        ).json()
        assert cuerpo["origen_plantilla"] == "request"
        assert len(cuerpo["recibos"]) == 1

    def test_la_respuesta_advierte_que_las_cuotas_son_del_periodo(self, cliente_http):
        """
        Es la diferencia entre informar y engañar: una quincena trae media
        mensualidad de EyM/IyV, no el entero del Art. 39.
        """
        cuerpo = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        assert any("no el entero mensual" in a.lower() for a in cuerpo["advertencias"])
        assert "porcion_mensual" in cuerpo and "porcion_bimestral" in cuerpo

    def test_los_ramos_traen_su_fundamento(self, cliente_http):
        """Sin el fundamento por ramo no se puede conciliar contra la EMA."""
        cuerpo = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        ramos = cuerpo["recibos"][0]["ramos"]
        assert ramos and all(r["fundamento"] for r in ramos)


class TestErrores:
    def test_la_periodicidad_catorcenal_responde_422_con_el_motivo_de_d10(
        self, cliente_http
    ):
        respuesta = cliente_http.post(
            CALCULAR,
            json=_cuerpo(parametros={**PARAMETROS, "clave_periodicidad": "03"}),
        )
        assert respuesta.status_code == 422
        mensaje = respuesta.json()["error"]
        assert "catorcenal" in mensaje and "D10" in mensaje

    def test_una_prima_de_riesgo_fuera_de_ley_se_rechaza_en_el_schema(
        self, cliente_http
    ):
        """
        `5.4355` en vez de `0.0054355` multiplicaría RT por mil.

        El motor también lo caza, así que **el código 422 no distingue** si el
        tope del schema está o no: lo que distingue es la FORMA. Sin el tope,
        el error llega como error de dominio (`{"exito": false, "error": ...}`)
        desde el fondo del motor; con el tope, como error de validación de
        FastAPI (`detail`), que es donde el cliente lo espera y donde dice qué
        campo está mal.
        """
        respuesta = cliente_http.post(
            CALCULAR, json=_cuerpo(parametros={**PARAMETROS, "prima_riesgo": "5.4355"})
        )
        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert "detail" in cuerpo, "debería frenarse en el schema, no en el motor"
        assert any("prima_riesgo" in str(d.get("loc", "")) for d in cuerpo["detail"])

    def test_una_prima_por_debajo_del_minimo_tambien_se_rechaza(self, cliente_http):
        """El Art. 72 acota por los dos lados; el tope de abajo también es ley."""
        respuesta = cliente_http.post(
            CALCULAR, json=_cuerpo(parametros={**PARAMETROS, "prima_riesgo": "0.0001"})
        )
        assert respuesta.status_code == 422
        assert "detail" in respuesta.json()

    def test_un_periodo_invertido_se_rechaza(self, cliente_http):
        """
        Con `fin` antes de `inicio` los días salen negativos y las cuotas dejan
        de significar nada. Se frena en el schema, junto al campo.
        """
        respuesta = cliente_http.post(
            CALCULAR,
            json=_cuerpo(periodo={"inicio": "2026-08-31", "fin": "2026-08-16"}),
        )
        assert respuesta.status_code == 422
        assert "termina antes de empezar" in str(respuesta.json())

    def test_sin_incidencias_no_se_calcula(self, cliente_http):
        respuesta = cliente_http.post(CALCULAR, json=_cuerpo(incidencias=[]))
        assert respuesta.status_code == 422

    def test_una_incidencia_de_alguien_que_no_esta_en_plantilla_responde_422(
        self, cliente_http
    ):
        cuerpo = _cuerpo()
        cuerpo["incidencias"].append(
            {"empleado_no": "E-77", "dias_periodo": 16, "faltas": 0, "dias_ausentismo": 0}
        )
        respuesta = cliente_http.post(CALCULAR, json=cuerpo)
        assert respuesta.status_code == 422
        assert "E-77" in respuesta.json()["error"]


class TestFechaDePago:
    def test_la_fecha_de_pago_cambia_el_resultado(self, cliente_http):
        """
        Una quincena que cierra el 31-ene y se paga el 5-feb se calcula con los
        valores de **febrero**. Sin `fecha_pago` separada, la vigencia de enero
        se aplicaría a nóminas pagadas en febrero: la UMA cambia el día 1 y con
        ella el subsidio y las exenciones.

        Se mide sobre E-01, que sí causa subsidio. Ojo: E-03, E-04 y E-07 no
        traen nodo de subsidio en ninguna de las dos fechas, porque su
        `SBC × 30.4` rebasa el tope de $11,492.66 — que es exactamente lo que
        documenta §D11.
        """
        enero = {"inicio": "2026-01-16", "fin": "2026-01-31"}
        cerrada_en_enero = cliente_http.post(
            CALCULAR, json=_cuerpo(periodo=enero)
        ).json()
        pagada_en_febrero = cliente_http.post(
            CALCULAR, json=_cuerpo(periodo={**enero, "fecha_pago": "2026-02-05"})
        ).json()

        def _subsidio(cuerpo, empleado="E-01"):
            recibo = next(r for r in cuerpo["recibos"] if r["empleado_no"] == empleado)
            return recibo["otros_pagos"][0]["subsidio_causado"]

        assert _subsidio(cerrada_en_enero) == "282.22"
        assert _subsidio(pagada_en_febrero) == "281.92"
        assert cerrada_en_enero["recibos"] != pagada_en_febrero["recibos"]

    def test_a_quien_rebasa_el_tope_del_subsidio_no_se_le_emite_el_nodo(
        self, cliente_http
    ):
        """§D11: con `SBC × 30.4` sobre $11,492.66 no hay subsidio que causar."""
        cuerpo = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        por_empleado = {r["empleado_no"]: r["otros_pagos"] for r in cuerpo["recibos"]}
        assert por_empleado["E-03"] == []
        assert por_empleado["E-04"] == []
        assert por_empleado["E-07"] == []
        assert por_empleado["E-01"] != []

    def test_sin_fecha_de_pago_se_usa_el_fin_del_periodo(self, cliente_http):
        con = cliente_http.post(
            CALCULAR, json=_cuerpo(periodo={**PERIODO, "fecha_pago": "2026-08-31"})
        ).json()
        sin = cliente_http.post(CALCULAR, json=_cuerpo()).json()
        assert con["recibos"] == sin["recibos"]


class TestExplicacion:
    def test_sin_pedirla_no_hay_explicacion(self, cliente_http):
        assert cliente_http.post(CALCULAR, json=_cuerpo()).json()["explicacion"] is None

    def test_con_el_llm_caido_cae_al_fallback_estatico(self, cliente_http, monkeypatch):
        """
        Los tests NUNCA pegan al proveedor real. Con el LLM inalcanzable la
        respuesta sigue siendo útil: el fallback lleva los mismos números.
        """

        async def _revienta(_prompt):
            raise RuntimeError("sin red en tests")

        monkeypatch.setattr("app.services.llm_nomina._call_openai", _revienta)
        monkeypatch.setattr("app.services.llm_nomina._call_anthropic", _revienta)
        cuerpo = cliente_http.post(
            CALCULAR, json=_cuerpo(incluir_explicacion=True)
        ).json()
        assert "9 empleados" in cuerpo["explicacion"]
        assert "Nómina del periodo" in cuerpo["explicacion"]


class TestOpenAPI:
    def test_el_endpoint_se_anuncia_como_demo(self, cliente_http):
        esquema = cliente_http.get("/openapi.json").json()
        operacion = esquema["paths"]["/api/v1/nomina/calcular-periodo"]["post"]
        assert operacion["summary"].startswith("DEMO")


class TestToolDelAgente:
    """
    El criterio de cierre de D-06 dice que el agente lo invoque desde el chat.
    """

    def _sembrar(self, cliente_http, dias, empleados=None):
        lista = empleados or [e.empleado_no for e in PLANTILLA_DEMO]
        info = [
            {
                "major": 5,
                "minor": 75,
                "time": f"{dia.isoformat()}T08:05:00-06:00",
                "employeeNoString": numero,
                "attendanceStatus": "checkIn",
                "serialNo": indice,
            }
            for indice, (dia, numero) in enumerate(
                ((d, n) for d in dias for n in lista), start=1
            )
        ]
        cliente_http.post(EVENTOS, json={"AcsEvent": {"InfoList": info}})

    def test_la_tool_esta_registrada_en_los_dos_proveedores(self):
        assert "calcular_nomina_periodo" in {t["name"] for t in TOOLS_ANTHROPIC}
        assert "calcular_nomina_periodo" in {
            t["function"]["name"] for t in TOOLS_OPENAI
        }

    def test_el_prompt_de_openai_enumera_todas_las_tools(self):
        """
        Registrar la tool en el array NO basta: **el prompt es lo que gobierna
        la selección**. El de OpenAI enumera las herramientas una por una y
        prescribe el orden, así que una tool ausente del texto es una tool que
        el modelo no va a llamar — y el criterio de D-06 es justamente que la
        llame desde el chat.

        Se comprueba contra `TOOLS_ANTHROPIC` entero (que es de donde sale
        `TOOLS_OPENAI`), no sólo contra la de nómina: así la próxima tool que
        alguien agregue sin tocar el prompt también rompe esto.

        Se exige el **renglón de la enumeración** (`"4. nombre_de_la_tool"`) y
        no que el nombre aparezca en cualquier parte: mencionarla de pasada en
        el "proceso recomendado" y dejarla fuera de la lista le quita al modelo
        la descripción de para qué sirve, que es lo que gobierna la selección.
        """
        for numero, tool in enumerate(TOOLS_ANTHROPIC, start=1):
            assert f"{numero}. {tool['name']}" in SYSTEM_PROMPT_OPENAI, tool["name"]

    def test_el_prompt_de_anthropic_nombra_la_tool_de_nomina(self):
        """
        Ese prompt es deliberadamente escueto y **no enumera** las tools de
        ISR/IVA: describe el trabajo y deja que el modelo elija. La de nómina sí
        se nombra, porque sin eso el prompt acotaba el trabajo a
        "pre-declaraciones de ISR e IVA" y empujaba activamente a no llamarla.
        """
        assert "calcular_nomina_periodo" in SYSTEM_PROMPT_ANTHROPIC
        assert "NÓMINA" in SYSTEM_PROMPT_ANTHROPIC

    def test_el_prompt_no_exige_leer_el_perfil_antes_de_la_nomina(self):
        """
        `calcular_nomina_periodo` no usa `RequestContext`: obligar a leer el
        perfil primero manda al modelo por un rodeo que no aporta nada.
        """
        assert "Sáltate este paso si la pregunta es de nómina" in SYSTEM_PROMPT_OPENAI
        assert "NO usa el perfil del contribuyente" in SYSTEM_PROMPT_ANTHROPIC

    def test_la_tool_le_dice_al_llm_que_no_recalcule(self):
        """La regla de oro: el LLM explica, no calcula."""
        tool = next(t for t in TOOLS_ANTHROPIC if t["name"] == "calcular_nomina_periodo")
        assert "NO sumes" in tool["description"]

    def test_el_despachador_la_encuentra(self, cliente_http):
        dias = [date(2026, 8, 17) + timedelta(days=n) for n in range(5)]
        self._sembrar(cliente_http, dias)
        salida, desglose = ejecutar_tool(
            "calcular_nomina_periodo",
            {"periodo_inicio": "2026-08-16", "periodo_fin": "2026-08-31"},
            ctx=None,
        )
        datos = json.loads(salida)
        assert desglose is None
        assert datos["empleados"] == 9
        assert datos["total_neto"] > 0

    def test_sin_checadas_responde_error_y_no_una_nomina_inventada(self):
        """
        Con el almacén vacío, `cerrar_periodo` marca todos los días como falta
        y el motor devuelve una nómina válida y **completamente falsa**, que el
        agente afirmaría en el chat como un hecho.
        """
        salida = json.loads(
            calcular_nomina_periodo(
                {"periodo_inicio": "2026-08-16", "periodo_fin": "2026-08-31"}
            )
        )
        assert "error" in salida
        assert "no se puede calcular" in salida["error"]
        assert "recibos" not in salida

    def test_avisa_de_las_checadas_de_empleados_desconocidos(self, cliente_http):
        """
        Un alta con el employeeNo equivocado en el checador se ve como "faltaron
        todos" si nadie lo dice.
        """
        dias = [date(2026, 8, 17) + timedelta(days=n) for n in range(5)]
        self._sembrar(cliente_http, dias)
        self._sembrar(cliente_http, [date(2026, 8, 24)], empleados=["E-99"])
        datos = json.loads(
            calcular_nomina_periodo(
                {"periodo_inicio": "2026-08-16", "periodo_fin": "2026-08-31"}
            )
        )
        assert any("E-99" in a for a in datos["advertencias"])

    def test_una_fecha_invalida_devuelve_error_y_no_revienta_el_turno(self):
        salida = json.loads(
            calcular_nomina_periodo({"periodo_inicio": "ayer", "periodo_fin": "hoy"})
        )
        assert "error" in salida
