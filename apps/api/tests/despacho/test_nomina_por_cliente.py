"""
La nómina corre para cualquier cliente de la cartera (E-03).

TRES COSAS QUE ESTE ARCHIVO PROTEGE
-----------------------------------
1. Que el simulador sepa sembrar a un cliente sintético, y que para `demo` siga
   dando exactamente lo que el runbook de D-07 promete.
2. Que las dos fuentes de los nueve empleados del caso real —la ficha de E-02 y
   `GET /nomina/demo/plantilla`— no diverjan. Desde E-03 hay dos endpoints
   sirviendo la misma plantilla.
3. **El camino de asistencia vacía**, que hasta E-03 nadie había ejercitado y
   que resultó no ser el que se suponía. Ver `TestSinChecadas`.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.asistencia.almacen import almacen
from app.despacho_demo import cliente_por_id
from app.main import app

RAIZ = Path(__file__).resolve().parents[2]


def _generador():
    """`scripts/` no es paquete: se carga por ruta, igual que hace el CLI."""
    ruta = RAIZ / "scripts" / "checador_sintetico.py"
    spec = importlib.util.spec_from_file_location("checador_sintetico_e03", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


gen = _generador()


@pytest.fixture(autouse=True)
def _almacen_limpio():
    almacen.reset()
    yield
    almacen.reset()


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


class TestPlantillaDelSimulador:
    def test_para_demo_da_lo_mismo_que_las_fixtures(self):
        """
        No-divergencia: `despacho_demo` reusa `PLANTILLA_DEMO`, que a su vez no
        diverge de las fixtures por `test_plantilla_demo.py`. Este test cierra
        el último eslabón de esa cadena.
        """
        desde_cartera = gen.plantilla_de_cliente("demo")
        desde_fixtures = gen.plantilla_desde_fixtures()

        assert [(e.numero, e.nombre) for e in desde_cartera] == [
            (e.numero, e.nombre) for e in desde_fixtures
        ]

    @pytest.mark.parametrize(("cliente_id", "cuantos"), [("cafeteria", 4), ("taller", 12)])
    def test_sabe_generar_la_plantilla_de_un_sintetico(self, cliente_id, cuantos):
        empleados = gen.plantilla_de_cliente(cliente_id)
        assert len(empleados) == cuantos
        # Y son los del cliente, no los nueve de las fixtures: ése era el bug.
        cartera = cliente_por_id(cliente_id)
        assert cartera is not None
        assert [e.numero for e in empleados] == [e.empleado_no for e in cartera.empleados]

    def test_un_cliente_que_no_existe_levanta(self):
        from app.exceptions import FiscalValidationError

        with pytest.raises(FiscalValidationError, match="no esta en la cartera"):
            gen.plantilla_de_cliente("fantasma")


class TestSiembra:
    def test_demo_conserva_la_siembra_literal_del_runbook(self):
        """
        D-07 promete 2 faltas y 3 retardos con nombre y apellido. Si esto
        cambia, el ensayo de la demo deja de dar los números documentados.
        """
        empleados = gen.plantilla_de_cliente("demo")
        assert gen.siembra_para("demo", empleados) is gen.SIEMBRA_DEMO

    @pytest.mark.parametrize(
        ("cliente_id", "faltas", "retardos"),
        [("cafeteria", 1, 1), ("taller", 2, 3)],
    )
    def test_los_sinteticos_usan_la_regla_escalada(self, cliente_id, faltas, retardos):
        empleados = gen.plantilla_de_cliente(cliente_id)
        siembra = gen.siembra_para(cliente_id, empleados)

        assert len(siembra.faltas) == faltas
        assert len(siembra.retardos) == retardos

    def test_siembra_solo_a_empleados_del_propio_cliente(self):
        """
        Sembrarle a un `empleado_no` ajeno produciría un `empleados_desconocidos`
        en el cierre y una checada que el panel no sabe a quién atribuir.
        """
        for cliente_id in ("cafeteria", "taller"):
            empleados = gen.plantilla_de_cliente(cliente_id)
            suyos = {e.numero for e in empleados}
            siembra = gen.siembra_para(cliente_id, empleados)
            for marca in (*siembra.faltas, *siembra.retardos):
                assert marca.empleado in suyos

    def test_la_siembra_generada_es_valida_para_el_periodo(self):
        """`generar_checadas` valida la siembra; que no levante es el test."""
        from datetime import date

        from app.demo_nomina import quincena

        periodo = quincena(date(2026, 9, 1))
        for cliente_id in ("demo", "cafeteria", "taller"):
            empleados = gen.plantilla_de_cliente(cliente_id)
            eventos = gen.generar_checadas(
                empleados, periodo, None, gen.OFFSET_DEFAULT,
                gen.siembra_para(cliente_id, empleados),
            )
            assert eventos


class TestDosFuentesDeLaMismaPlantilla:
    def test_la_ficha_y_el_endpoint_de_demo_no_divergen(self, cliente_http):
        """
        Desde E-03 la pantalla toma los empleados de la ficha y ya no de
        `/nomina/demo/plantilla`. Los dos endpoints siguen vivos y sirven a los
        mismos nueve: si divergen, la nómina que se calcula deja de ser la que
        el otro endpoint promete.
        """
        ficha = cliente_http.get("/api/v1/despacho/clientes/demo").json()
        plantilla = cliente_http.get("/api/v1/nomina/demo/plantilla").json()

        de_ficha = {(e["empleado_no"], e["nombre"]) for e in ficha["empleados"]}
        de_plantilla = {(e["empleado_no"], e["nombre"]) for e in plantilla["empleados"]}
        assert de_ficha == de_plantilla

        # Y la prima y la periodicidad, que alimentan el cálculo.
        assert Decimal(ficha["prima_riesgo"]) == Decimal(plantilla["prima_riesgo"])
        assert ficha["clave_periodicidad"] == plantilla["clave_periodicidad"]


class TestSinChecadas:
    """
    QUÉ PASA CUANDO NADIE SEMBRÓ, QUE NO ES LO QUE PARECÍA.

    No sale un error ni una nómina en ceros: sale una **nómina completa y
    creíble**. `dias_pagados = dias_periodo − faltas` y `faltas` sólo cuenta
    días **laborables**, así que doce personas que no fueron un solo día cobran
    los 5 días no laborables de la quincena.

    Eso es §D17 —«se descuenta el día y nada más»— llevado a su extremo, y
    **no se toca el motor aquí**: §D17 está abierta y pendiente de la contadora,
    y cambiar la semántica de `dias_pagados` movería los números del caso real
    que hoy cuadran contra el timbrado.

    Lo que este test hace es **fijar los números observados** para que nadie los
    cambie en silencio, y comprobar que la advertencia que salva la situación
    llega y nombra a todos.
    """

    PERIODO = {"inicio": "2026-08-16", "fin": "2026-08-31", "fecha_pago": "2026-08-31"}

    def _empleados(self, cliente_id: str, cuantos: int | None = None):
        cliente = cliente_por_id(cliente_id)
        assert cliente is not None
        empleados = cliente.empleados[:cuantos] if cuantos else cliente.empleados
        return cliente, [
            {
                "empleado_no": e.empleado_no,
                "nombre": e.nombre,
                "salario_diario": str(e.salario_diario),
                "salario_diario_integrado": str(e.salario_diario_integrado),
                "zona": e.zona.value,
            }
            for e in empleados
        ]

    def test_cerrar_sin_eventos_marca_falta_todo_dia_laborable(self, cliente_http):
        r = cliente_http.post(
            "/api/v1/asistencia/cerrar-periodo",
            json={
                "cliente": "taller",
                "empleados": ["T-01", "T-02"],
                "periodo": {"inicio": "2026-08-16", "fin": "2026-08-31"},
            },
        )
        assert r.status_code == 200

        for inc in r.json()["incidencias"]:
            assert inc["dias_periodo"] == 16
            assert inc["dias_laborables"] == 11
            assert inc["dias_trabajados"] == 0
            assert inc["faltas"] == 11

    def test_calcular_sin_checadas_no_da_ceros_sino_los_dias_de_descanso(
        self, cliente_http
    ):
        """
        **5 días pagados, no 0.** Si alguien "arregla" esto, que sea a propósito
        y con §D17 cerrada, no de pasada.
        """
        cliente, empleados = self._empleados("taller", 2)
        r = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json={
                "cliente": "taller",
                "periodo": self.PERIODO,
                "incidencias": [
                    {"empleado_no": e["empleado_no"], "dias_periodo": 16, "faltas": 11,
                     "dias_ausentismo": 11}
                    for e in empleados
                ],
                "parametros": {
                    "prima_riesgo": str(cliente.prima_riesgo),
                    "clave_periodicidad": cliente.clave_periodicidad,
                },
                "empleados": empleados,
            },
        )
        assert r.status_code == 200

        cuerpo = r.json()
        for recibo in cuerpo["recibos"]:
            assert recibo["dias_pagados"] == 5
            assert Decimal(recibo["total_percepciones"]) > 0
            assert Decimal(recibo["neto"]) > 0

    def test_la_advertencia_de_ausentismo_nombra_a_todos(self, cliente_http):
        """
        Es lo único que separa esa nómina creíble de una mentira. Si se pierde,
        la pantalla enseña $30,811.33 de nómina de gente que no fue a trabajar
        sin decir nada.
        """
        cliente, empleados = self._empleados("taller")
        r = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json={
                "cliente": "taller",
                "periodo": self.PERIODO,
                "incidencias": [
                    {"empleado_no": e["empleado_no"], "dias_periodo": 16, "faltas": 11,
                     "dias_ausentismo": 11}
                    for e in empleados
                ],
                "parametros": {
                    "prima_riesgo": str(cliente.prima_riesgo),
                    "clave_periodicidad": cliente.clave_periodicidad,
                },
                "empleados": empleados,
            },
        )
        assert r.status_code == 200

        avisos = " ".join(r.json()["advertencias"])
        assert "ausentismo" in avisos
        for empleado in empleados:
            assert empleado["empleado_no"] in avisos


class TestFlujoCompletoPorCliente:
    """
    El "Listo cuando" de E-03: el flujo corre para el cliente de fixtures **y**
    para uno sintético. Sembrar → cerrar → calcular, con el mismo motor.
    """

    @pytest.mark.parametrize("cliente_id", ["demo", "cafeteria", "taller"])
    def test_sembrar_cerrar_y_calcular(self, cliente_http, cliente_id):
        from datetime import date

        from app.demo_nomina import quincena

        cliente = cliente_por_id(cliente_id)
        assert cliente is not None
        periodo = quincena(date.today())
        empleados = gen.plantilla_de_cliente(cliente_id)

        eventos = gen.generar_checadas(
            empleados, periodo, None, gen.OFFSET_DEFAULT,
            gen.siembra_para(cliente_id, empleados),
        )
        r = cliente_http.post(
            f"/api/v1/asistencia/eventos?cliente={cliente_id}&fuente=simulado",
            json=gen.envolver(eventos),
        )
        assert r.status_code == 200

        cierre = cliente_http.post(
            "/api/v1/asistencia/cerrar-periodo",
            json={
                "cliente": cliente_id,
                "empleados": [e.numero for e in empleados],
                "periodo": {"inicio": str(periodo.inicio), "fin": str(periodo.fin)},
            },
        ).json()
        assert len(cierre["incidencias"]) == len(empleados)
        # Con siembra hay faltas, pero nadie falta el periodo entero.
        assert all(i["dias_trabajados"] > 0 for i in cierre["incidencias"])

        nomina = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json={
                "cliente": cliente_id,
                "periodo": {
                    "inicio": str(periodo.inicio),
                    "fin": str(periodo.fin),
                    "fecha_pago": str(periodo.fin),
                },
                "incidencias": [
                    {
                        "empleado_no": i["empleado_no"],
                        "dias_periodo": i["dias_periodo"],
                        "faltas": i["faltas"],
                        "dias_ausentismo": i["dias_ausentismo"],
                    }
                    for i in cierre["incidencias"]
                ],
                "parametros": {
                    "prima_riesgo": str(cliente.prima_riesgo),
                    "clave_periodicidad": cliente.clave_periodicidad,
                },
                "empleados": [
                    {
                        "empleado_no": e.empleado_no,
                        "nombre": e.nombre,
                        "salario_diario": str(e.salario_diario),
                        "salario_diario_integrado": str(e.salario_diario_integrado),
                        "zona": e.zona.value,
                    }
                    for e in cliente.empleados
                ],
            },
        )
        assert nomina.status_code == 200

        cuerpo = nomina.json()
        assert len(cuerpo["recibos"]) == len(cliente.empleados)
        assert Decimal(cuerpo["porcion_mensual"]["total_patron"]) > 0
        # La plantilla viajó en el request para los tres, no sólo para `demo`.
        assert cuerpo["origen_plantilla"] == "request"
