"""
Tests de los dos endpoints de la cartera del despacho (E-02).

El "Listo cuando" de E-02 vive a caballo entre esto y el front: aquí se fija que
la ficha trae **todo lo que la pantalla necesita para cambiar de cliente sin
inventar nada** —empleados con sus montos, periodo sugerido y prima—, y que un
id desconocido falla de forma legible en vez de devolver un cliente vacío.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.despacho_demo import CLIENTES, FECHA_REFERENCIA_DEMO
from app.main import app

LISTA = "/api/v1/despacho/clientes"
FICHA = "/api/v1/despacho/clientes/{}"


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


class TestListaDeClientes:
    def test_devuelve_los_tres_clientes(self, cliente_http):
        r = cliente_http.get(LISTA)
        assert r.status_code == 200

        cuerpo = r.json()
        assert cuerpo["exito"] is True
        assert [c["id"] for c in cuerpo["clientes"]] == ["demo", "cafeteria", "taller"]

    def test_el_resumen_trae_lo_que_pinta_la_lista(self, cliente_http):
        clientes = cliente_http.get(LISTA).json()["clientes"]
        por_id = {c["id"]: c for c in clientes}

        assert por_id["demo"]["num_empleados"] == 9
        assert por_id["cafeteria"]["num_empleados"] == 4
        assert por_id["taller"]["num_empleados"] == 12
        for cliente in clientes:
            assert cliente["giro"]
            assert cliente["nombre"]
            assert Decimal(cliente["prima_riesgo"]) > 0

    def test_distingue_el_caso_real_del_sintetico(self, cliente_http):
        """
        La pantalla tiene que poder decir cuál es el caso real anonimizado y
        cuáles son inventados: enseñar los tres como si fueran iguales sería
        presentar datos sintéticos con el mismo peso que los reales.
        """
        por_id = {c["id"]: c for c in cliente_http.get(LISTA).json()["clientes"]}
        assert por_id["demo"]["origen"] == "fixtures-s04"
        assert por_id["cafeteria"]["origen"] == "sintetico"
        assert por_id["taller"]["origen"] == "sintetico"


class TestFichaDelCliente:
    def test_la_ficha_del_caso_real_trae_sus_nueve_empleados(self, cliente_http):
        r = cliente_http.get(FICHA.format("demo"))
        assert r.status_code == 200

        ficha = r.json()
        assert len(ficha["empleados"]) == 9
        assert {e["empleado_no"] for e in ficha["empleados"]} == {
            f"E-0{n}" for n in range(1, 10)
        }

    def test_los_empleados_del_caso_real_no_traen_alta_inventada(self, cliente_http):
        ficha = cliente_http.get(FICHA.format("demo")).json()
        for empleado in ficha["empleados"]:
            assert empleado["fecha_alta"] is None
            assert empleado["antiguedad_anios"] is None
            # El factor viaja, pero marcado: es un cociente observado, no el de ley.
            assert empleado["factor_implicito"] is True
            assert Decimal(empleado["factor"]) > 1

    def test_los_empleados_sinteticos_traen_alta_antiguedad_y_factor_de_ley(
        self, cliente_http
    ):
        ficha = cliente_http.get(FICHA.format("cafeteria")).json()
        assert len(ficha["empleados"]) == 4
        for empleado in ficha["empleados"]:
            assert empleado["fecha_alta"] is not None
            assert empleado["antiguedad_anios"] >= 0
            assert empleado["factor_implicito"] is False
            assert empleado["puesto"]

    def test_la_ficha_dice_contra_que_fecha_midio_la_antiguedad(self, cliente_http):
        """
        No es "hoy". Si la pantalla dijera "antigüedad" a secas, el número
        cambiaría solo al cruzar un aniversario y con él el SDI.
        """
        ficha = cliente_http.get(FICHA.format("taller")).json()
        assert ficha["fecha_referencia"] == FECHA_REFERENCIA_DEMO.isoformat()

    def test_la_ficha_trae_el_periodo_sugerido_ya_resuelto(self, cliente_http):
        """
        Para que la pantalla NO derive la quincena de las fechas de las checadas
        —eso da 15 días donde la quincena tiene 16 y mueve cuotas e ISR.
        """
        ficha = cliente_http.get(FICHA.format("taller")).json()
        periodo = ficha["periodo_sugerido"]
        assert periodo["inicio"] < periodo["fin"]
        assert periodo["fecha_pago"] == periodo["fin"]

    def test_los_campos_de_empleado_sirven_tal_cual_para_calcular(self, cliente_http):
        """
        `EmpleadoClienteSchema` es superconjunto compatible de
        `EmpleadoNominaSchema`: si estos cinco campos cambiaran de nombre o de
        tipo, E-03 tendría que remapear para llamar a `calcular-periodo`.
        """
        from app.schemas.nomina import EmpleadoNominaSchema

        ficha = cliente_http.get(FICHA.format("cafeteria")).json()
        for empleado in ficha["empleados"]:
            traducido = EmpleadoNominaSchema(**{
                campo: empleado[campo]
                for campo in (
                    "empleado_no",
                    "nombre",
                    "salario_diario",
                    "salario_diario_integrado",
                    "zona",
                )
            })
            assert traducido.empleado_no == empleado["empleado_no"]
            assert traducido.salario_diario_integrado == Decimal(
                empleado["salario_diario_integrado"]
            )


class TestClienteDesconocido:
    def test_responde_404_y_no_un_cliente_vacio(self, cliente_http):
        r = cliente_http.get(FICHA.format("no-existe"))
        assert r.status_code == 404

    def test_el_404_usa_el_mismo_sobre_que_el_resto_de_la_api(self, cliente_http):
        """
        `{"exito": false, "error": ...}`, no el `{"detail": ...}` de
        `HTTPException`: el front tiene un solo camino para leer errores.
        """
        cuerpo = cliente_http.get(FICHA.format("no-existe")).json()
        assert cuerpo["exito"] is False
        assert "no-existe" in cuerpo["error"]
        # El mensaje dice cuáles sí existen, para que el operador no adivine.
        for cliente in CLIENTES:
            assert cliente.id in cuerpo["error"]
