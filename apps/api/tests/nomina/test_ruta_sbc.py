"""
`POST /api/v1/nomina/sbc` — integración de un salario fijo (G-01).

QUÉ PRUEBA ESTO Y QUÉ NO
------------------------
Que la ruta sea **traductor y no motor**. Las fórmulas están probadas en
`tests/nomina/test_integracion.py` contra la tabla de factores mínimos de ley de
PLAN_NOMINA §2.2; aquí se prueba que la ruta llame al motor y no decida nada por
su cuenta, que no se trague las validaciones, y que no acote en silencio.

POR QUÉ ESTA RUTA EXISTE
------------------------
Para que la pantalla de alta de empleado muestre SBC y factor mientras se teclea
el salario **sin reimplementar la fórmula en TypeScript**. Un factor calculado en
el front sería una segunda verdad sobre el Art. 27 sin ningún test que la cuide.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.main import app
from app.nomina_engine.integracion import (
    clamp_sbc,
    dias_vacaciones_de_ley,
    factor_integracion,
    sbc_fijo,
)

RUTA = "/api/v1/nomina/sbc"
FECHA = "2026-09-01"


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


def pedir(cliente_http: TestClient, **campos) -> dict:
    cuerpo = {"salario_diario": "500.00", "fecha": FECHA, **campos}
    r = cliente_http.post(RUTA, json=cuerpo)
    assert r.status_code == 200, r.text
    return r.json()


class TestTraductorNoMotor:
    @pytest.mark.parametrize("anios", [0, 1, 3, 5, 10, 25])
    def test_el_factor_es_exactamente_el_del_motor(self, cliente_http, anios):
        """
        Si alguna vez difieren, es que la ruta se puso a integrar por su cuenta.
        """
        del_motor = factor_integracion(15, dias_vacaciones_de_ley(anios), Decimal("0.25"))
        assert pedir(cliente_http, anios_servicio_cumplidos=anios)["factor"] == str(del_motor)

    @pytest.mark.parametrize("salario", ["316.00", "500.00", "1250.75", "5000.00"])
    def test_el_sbc_es_exactamente_el_del_motor(self, cliente_http, salario):
        factor = factor_integracion(15, dias_vacaciones_de_ley(0), Decimal("0.25"))
        esperado = clamp_sbc(
            sbc_fijo(Decimal(salario), factor), date(2026, 9, 1), ZonaSalarioMinimo.GENERAL
        )
        cuerpo = pedir(cliente_http, salario_diario=salario)
        assert cuerpo["sbc"] == str(esperado.valor)
        assert cuerpo["sbc_sin_acotar"] == str(sbc_fijo(Decimal(salario), factor))

    def test_el_piso_y_el_tope_son_los_del_motor(self, cliente_http):
        cuerpo = pedir(cliente_http)
        assert cuerpo["piso"] == str(
            salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.GENERAL)
        )
        assert Decimal(cuerpo["tope"]) == (uma_vigente(date(2026, 9, 1)) * 25).quantize(
            Decimal("0.01")
        )


class TestElClampNoEsSilencioso:
    def test_un_salario_por_debajo_del_minimo_reporta_que_se_aplico_el_piso(
        self, cliente_http
    ):
        """
        `piso_aplicado` es el ÚNICO camino por el que un SBC llega a ser
        exactamente 1 salario mínimo, que es el supuesto del Art. 36 LSS (el
        patrón absorbe la cuota obrera) y el renglón de 3.150% de CEAV. Acotar
        sin decirlo escondería las dos cosas.
        """
        cuerpo = pedir(cliente_http, salario_diario="100.00")
        assert cuerpo["piso_aplicado"] is True
        assert cuerpo["tope_aplicado"] is False
        assert cuerpo["sbc"] == cuerpo["piso"]
        assert Decimal(cuerpo["sbc_sin_acotar"]) < Decimal(cuerpo["sbc"])

    def test_un_salario_altisimo_reporta_que_se_aplico_el_tope(self, cliente_http):
        cuerpo = pedir(cliente_http, salario_diario="99999.00")
        assert cuerpo["tope_aplicado"] is True
        assert cuerpo["sbc"] == cuerpo["tope"]

    def test_un_salario_normal_no_reporta_ningun_clamp(self, cliente_http):
        cuerpo = pedir(cliente_http)
        assert cuerpo["piso_aplicado"] is False
        assert cuerpo["tope_aplicado"] is False
        assert cuerpo["sbc"] == cuerpo["sbc_sin_acotar"]


class TestNoSeTragaLasValidaciones:
    def test_una_prima_como_porcentaje_responde_422_y_no_un_sbc_inflado(
        self, cliente_http
    ):
        """
        25 en vez de 0.25 produce un factor de 1.86 y un SBC inflado 77% que
        ninguna tabla de referencia detecta. Un "mejor esfuerzo" que lo dejara
        pasar mataría el guard que `factor_integracion` documenta.
        """
        r = cliente_http.post(
            RUTA, json={"salario_diario": "500.00", "fecha": FECHA, "prima_vacacional": "25"}
        )
        assert r.status_code == 422
        assert r.json()["exito"] is False
        assert "0.25" in r.json()["error"]

    def test_un_aguinaldo_menor_al_minimo_responde_422(self, cliente_http):
        # Art. 87 LFT: subintegraría el SBC y con él todas las cuotas.
        r = cliente_http.post(
            RUTA, json={"salario_diario": "500.00", "fecha": FECHA, "dias_aguinaldo": 10}
        )
        assert r.status_code == 422
        assert "87" in r.json()["error"]

    def test_un_salario_de_cero_se_rechaza_en_el_schema(self, cliente_http):
        r = cliente_http.post(RUTA, json={"salario_diario": "0", "fecha": FECHA})
        assert r.status_code == 422


class TestLaFechaEsObligatoria:
    def test_sin_fecha_no_se_calcula(self, cliente_http):
        """
        `clamp_sbc` mueve el piso el 1-ene (salario mínimo) y el tope el 1-feb
        (UMA). Un `date.today()` implícito haría que el número del modal cambiara
        solo entre enero y febrero — la deriva contra la que está escrito todo el
        encabezado de `despacho_demo.py`.
        """
        r = cliente_http.post(RUTA, json={"salario_diario": "500.00"})
        assert r.status_code == 422

    def test_enero_y_febrero_de_2026_dan_topes_distintos(self, cliente_http):
        """
        En enero rige la UMA 2025 y en febrero la 2026. Si el tope no cambiara,
        la fecha no se estaría usando.
        """
        enero = pedir(cliente_http, fecha="2026-01-15", salario_diario="99999.00")
        febrero = pedir(cliente_http, fecha="2026-02-15", salario_diario="99999.00")
        assert Decimal(enero["tope"]) < Decimal(febrero["tope"])


class TestLoQueLaRutaNoHace:
    def test_no_acepta_conceptos_integrables(self, cliente_http):
        """
        §D5: el motor no decide qué integra, el catálogo es dato y
        `ConceptoIntegrable.monto_diario` es *la porción que integra, ya
        calculada por el llamador*. Si el front mandara una despensa completa,
        sobreintegraría. Fuera de alcance de esta corrida: se ignora, no se
        adivina.
        """
        r = cliente_http.post(
            RUTA,
            json={
                "salario_diario": "500.00",
                "fecha": FECHA,
                "conceptos": [{"clave": "029", "monto_diario": "50.00", "integra": True}],
            },
        )
        assert r.status_code == 200
        # El SBC es el del salario solo: el concepto no se integró por su cuenta.
        assert r.json()["sbc"] == pedir(cliente_http)["sbc"]

    def test_no_devuelve_explicacion_de_llm(self, cliente_http):
        # Aquí no hay nada que explicar que no sea el número, y el LLM nunca
        # entra a un cálculo (regla de oro).
        assert "explicacion" not in pedir(cliente_http)

    def test_devuelve_los_dias_de_vacaciones_con_los_que_integro(self, cliente_http):
        """
        Si el motor recibiera 0 y aplicara el de ley por dentro, la pantalla no
        podría decir con cuántos días integró — y el contador no podría
        verificarlo.
        """
        assert pedir(cliente_http, anios_servicio_cumplidos=3)[
            "dias_vacaciones_aplicados"
        ] == dias_vacaciones_de_ley(3)

    def test_unas_vacaciones_capturadas_ganan_sobre_las_de_ley(self, cliente_http):
        # Prestación superior a la de ley: la ley es piso, no techo.
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=0, dias_vacaciones=30)
        assert cuerpo["dias_vacaciones_aplicados"] == 30
        assert Decimal(cuerpo["factor"]) > factor_integracion(
            15, dias_vacaciones_de_ley(0), Decimal("0.25")
        )


class TestFundamento:
    def test_la_respuesta_cita_su_fundamento_legal(self, cliente_http):
        fundamento = pedir(cliente_http)["fundamento"]
        for articulo in ("27", "28", "30", "76", "80", "87"):
            assert articulo in fundamento
