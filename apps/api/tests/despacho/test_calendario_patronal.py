"""
Endpoint del calendario patronal de la cartera (E-07).

QUÉ PRUEBA ESTO Y QUÉ NO
------------------------
Las **fechas** las prueba `tests/nomina/test_calendario_laboral.py` contra la
tabla publicada del doc 25. Aquí se prueba que el router sea **traductor y no
motor**: que no recalcule nada, que etiquete cada obligación con su cliente, que
el orden sea el que la pantalla espera, y que la respuesta diga qué rango cubre
y qué NO cubre.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.despacho_demo import CLIENTES
from app.main import app
from app.nomina_engine.calendario_laboral import calendario_patronal

RUTA = "/api/v1/despacho/calendario"


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


def pedir(cliente_http: TestClient, anio: int = 2026) -> dict:
    respuesta = cliente_http.get(RUTA, params={"anio_de_las_cuotas": anio})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


class TestFormaDeLaRespuesta:
    def test_trae_las_obligaciones_de_toda_la_cartera(self, cliente_http):
        cuerpo = pedir(cliente_http)
        por_cliente = calendario_patronal(2026)
        assert cuerpo["total_obligaciones"] == len(por_cliente) * len(CLIENTES)
        assert {o["cliente_id"] for o in cuerpo["obligaciones"]} == {c.id for c in CLIENTES}

    def test_cada_obligacion_dice_de_qué_cliente_es(self, cliente_http):
        nombres = {c.id: c.nombre for c in CLIENTES}
        for o in pedir(cliente_http)["obligaciones"]:
            assert o["cliente_nombre"] == nombres[o["cliente_id"]]

    def test_vienen_ordenadas_por_fecha(self, cliente_http):
        fechas = [o["fecha_limite"] for o in pedir(cliente_http)["obligaciones"]]
        assert fechas == sorted(fechas)

    def test_el_router_no_recalcula_ninguna_fecha(self, cliente_http):
        """
        **Traductor, no motor.** El conjunto de fechas que devuelve el endpoint
        para un cliente tiene que ser exactamente el del motor: si alguna vez
        difieren, es que el router se puso a decidir plazos por su cuenta.
        """
        del_motor = {o.fecha_limite.isoformat() for o in calendario_patronal(2026)}
        del_endpoint = {
            o["fecha_limite"]
            for o in pedir(cliente_http)["obligaciones"]
            if o["cliente_id"] == CLIENTES[0].id
        }
        assert del_endpoint == del_motor


class TestRangoQueCubre:
    def test_dice_desde_cuándo_y_hasta_cuándo(self, cliente_http):
        """
        Un calendario pedido por AÑO DE LAS CUOTAS empieza en febrero y termina
        en enero del año siguiente. Sin estos dos campos, la pantalla enseñaría
        un enero vacío sin poder explicar por qué.
        """
        cuerpo = pedir(cliente_http)
        assert cuerpo["cubre_desde"] == "2026-02-17"
        assert cuerpo["cubre_hasta"].startswith("2027-01")

    def test_no_incluye_nada_que_venza_antes_de_febrero(self, cliente_http):
        for o in pedir(cliente_http)["obligaciones"]:
            assert o["fecha_limite"] >= "2026-02-01"


class TestLoQueNoCubre:
    def test_las_advertencias_viajan_en_el_cuerpo(self, cliente_http):
        """
        Y no sólo en la documentación: la pantalla las imprime tal cual, así que
        no puede quedarse desincronizada de lo que el backend realmente omite.
        """
        advertencias = " ".join(pedir(cliente_http)["advertencias"]).lower()
        assert "isn" in advertencias
        assert "condicional" in advertencias

    def test_las_condicionales_traen_nota(self, cliente_http):
        condicionales = [o for o in pedir(cliente_http)["obligaciones"] if o["condicional"]]
        assert condicionales, "ninguna obligación salió condicional"
        for o in condicionales:
            assert o["nota"], o["clave"]


class TestReglasDePlazoDistinguibles:
    def test_el_isr_y_las_cuotas_de_marzo_no_se_fundieron(self, cliente_http):
        """
        El par que el doc 25 §4 pide no confundir, visto desde la API: mismo mes,
        dos fechas, y `regimen_de_plazo` diciendo cuál regla produjo cada una.
        """
        marzo = {
            o["clave"]: o
            for o in pedir(cliente_http)["obligaciones"]
            if o["cliente_id"] == CLIENTES[0].id and o["periodo_cubierto"] == "marzo 2026"
        }
        assert marzo["imss_mensual"]["fecha_limite"] == "2026-04-20"
        assert marzo["isr_retenido"]["fecha_limite"] == "2026-04-17"
        assert marzo["imss_mensual"]["regimen_de_plazo"] == "imss"
        assert marzo["isr_retenido"]["regimen_de_plazo"] == "sat"

    def test_la_prima_de_rt_no_se_etiqueta_como_prorrogable(self, cliente_http):
        prima = next(
            o for o in pedir(cliente_http)["obligaciones"] if o["clave"] == "prima_rt"
        )
        assert prima["regimen_de_plazo"] == "imss_sin_prorroga"
        assert "sábado" in prima["nota"]


class TestValidacion:
    @pytest.mark.parametrize("anio", [1999, 2101])
    def test_un_ano_fuera_de_rango_falla_con_el_sobre_del_proyecto(self, cliente_http, anio):
        respuesta = cliente_http.get(RUTA, params={"anio_de_las_cuotas": anio})
        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["exito"] is False
        assert "fuera de rango" in cuerpo["error"]

    def test_sin_parametro_usa_el_ano_en_curso(self, cliente_http):
        respuesta = cliente_http.get(RUTA)
        assert respuesta.status_code == 200
        assert respuesta.json()["anio_de_las_cuotas"] == date.today().year


class TestEmpresaUnica:
    """
    `empresa_unica=true`: un solo patrón, no una cartera. (O-01)

    El pivote convirtió el producto en la nómina interna de UNA empresa. El
    endpoint no cambia de motor —sigue siendo `calendario_patronal()`, y crear
    un segundo generador es lo que el doc 25 §4 llama "un bug esperando"—: lo
    que se quita es el fan-out sobre los tres clientes del catálogo demo.

    Sin este parámetro, la empresa vería su calendario **triplicado**, con el
    nombre de tres clientes que no son suyos, en su pantalla de Calendario.
    """

    def pedir_empresa(self, cliente_http: TestClient, anio: int = 2026) -> dict:
        respuesta = cliente_http.get(
            RUTA, params={"anio_de_las_cuotas": anio, "empresa_unica": True}
        )
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()

    def test_devuelve_un_juego_de_obligaciones_no_tres(self, cliente_http):
        cuerpo = self.pedir_empresa(cliente_http)
        assert cuerpo["total_obligaciones"] == len(calendario_patronal(2026))

    def test_es_exactamente_la_cartera_dividida_entre_el_numero_de_clientes(
        self, cliente_http
    ):
        """
        No es "menos obligaciones": es **las mismas, sin repetir**.

        Se compara contra el modo cartera para que un cambio en el catálogo
        —agregar o quitar un cliente demo— no pueda hacer pasar este test por
        casualidad.
        """
        cartera = pedir(cliente_http)
        empresa = self.pedir_empresa(cliente_http)
        assert (
            empresa["total_obligaciones"] * len(CLIENTES)
            == cartera["total_obligaciones"]
        )

    def test_las_fechas_son_las_MISMAS_que_en_modo_cartera(self, cliente_http):
        """
        El fan-out se quita; el motor no se toca.

        Si esto fallara, `empresa_unica` habría dejado de ser un filtro de
        presentación para convertirse en un segundo calendario — que es
        exactamente lo que F1-06 dejó advertido que no se hiciera.
        """
        empresa = self.pedir_empresa(cliente_http)
        cartera = pedir(cliente_http)
        del_motor = [(o.clave, str(o.fecha_limite)) for o in calendario_patronal(2026)]
        de_la_empresa = [(o["clave"], o["fecha_limite"]) for o in empresa["obligaciones"]]
        assert sorted(de_la_empresa) == sorted(del_motor)
        # Y siguen siendo un subconjunto exacto de lo que ve la cartera.
        de_la_cartera = {(o["clave"], o["fecha_limite"]) for o in cartera["obligaciones"]}
        assert set(de_la_empresa) == de_la_cartera

    def test_el_nombre_del_cliente_viene_VACIO_no_inventado(self, cliente_http):
        """
        El backend no sabe cómo se llama la empresa —no viaja en el query
        string, y no tiene por qué— así que no lo afirma.

        Un nombre por default ("Mi empresa", o peor: el de un cliente del
        catálogo) sería un dato inventado impreso al lado de cada obligación.
        El campo sigue siendo obligatorio en el schema: cambia su valor, no su
        presencia, así que ningún consumidor se rompe.
        """
        cuerpo = self.pedir_empresa(cliente_http)
        assert {o["cliente_nombre"] for o in cuerpo["obligaciones"]} == {""}
        assert {o["cliente_id"] for o in cuerpo["obligaciones"]} == {"empresa"}
        # Y ninguno trae el nombre de un cliente del catálogo de demostración.
        nombres_demo = {c.nombre for c in CLIENTES}
        assert not nombres_demo & {o["cliente_nombre"] for o in cuerpo["obligaciones"]}

    def test_las_advertencias_hablan_de_la_empresa_no_de_la_cartera(self, cliente_http):
        """
        Las advertencias viajan en el cuerpo y la pantalla las imprime tal cual
        (E-07). En modo empresa única decían "son las mismas para toda la
        cartera", que ahí no significa nada.
        """
        cuerpo = self.pedir_empresa(cliente_http)
        texto = " ".join(cuerpo["advertencias"])
        assert "cartera" not in texto.lower()
        # Lo que NO cubre se sigue diciendo: el ISN sigue fuera (§D24).
        assert "ISN" in texto

    def test_el_default_es_el_modo_cartera(self, cliente_http):
        """
        Omitir el parámetro no puede cambiar el comportamiento de nadie: el modo
        despacho sigue siendo lo que responde el endpoint sin pedir nada.
        """
        assert pedir(cliente_http)["total_obligaciones"] == len(
            calendario_patronal(2026)
        ) * len(CLIENTES)
