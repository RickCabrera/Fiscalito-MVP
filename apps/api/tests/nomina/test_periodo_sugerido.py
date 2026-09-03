"""
El periodo que la app propone, por periodicidad. (O-03)

EL CALLEJON QUE ESTO CIERRA
---------------------------
`conPeriodoAlDia` copiaba la quincena del cliente de demostracion a **todos**
los clientes, sin mirar su `clave_periodicidad` — su propio docstring lo
advertia: *"el dia que se abran las otras claves esta es la puerta que queda
abierta"*.

O-03 abre esas claves y agrega la guarda de `duracion_periodo`. Sin este
modulo, elegir **Mensual** dejaba a la empresa con una quincena propuesta y el
motor rechazando el calculo: **el selector rompia la app en dos de sus tres
opciones**, y la culpa parecia del motor.

LA INVARIANTE QUE MAS IMPORTA
-----------------------------
`test_lo_que_propone_SIEMPRE_lo_acepta_el_motor` recorre el año completo, dia
por dia, para las cuatro claves. Es la unica forma de afirmar que la app nunca
se propone a si misma un periodo que despues no puede calcular — y es la clase
de defecto que duerme: con el rango quincenal equivocado (14, 17) solo fallaba
en 15 dias de marzo.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.demo_nomina import quincena
from app.exceptions import FiscalValidationError
from app.main import app
from app.nomina_engine.duracion_periodo import validar_duracion_periodo
from app.nomina_engine.periodo_sugerido import CLAVES_CON_PERIODO, periodo_sugerido

RUTA = "/api/v1/nomina/periodo-sugerido"


def dias(periodo) -> int:
    return (periodo.fin - periodo.inicio).days + 1


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


class TestLaInvarianteQueSostieneElSelector:
    @pytest.mark.parametrize("clave", CLAVES_CON_PERIODO)
    def test_lo_que_propone_SIEMPRE_lo_acepta_el_motor(self, clave):
        """
        EL CASO QUE VALE EL ARCHIVO.

        Un año entero, dia por dia, para cada clave. Si esto fallara, la app
        estaría proponiendo un periodo que su propio motor rechaza al calcular
        — el callejón sin salida que O-03 viene a cerrar.
        """
        dia = date(2026, 1, 1)
        while dia <= date(2026, 12, 31):
            propuesto = periodo_sugerido(clave, dia)
            validar_duracion_periodo(clave, dias(propuesto))
            dia += timedelta(days=1)

    @pytest.mark.parametrize("clave", CLAVES_CON_PERIODO)
    def test_y_tambien_en_año_bisiesto(self, clave):
        """2028 tiene 29 de febrero, que es el borde de la quincena y del mes."""
        dia = date(2028, 2, 1)
        while dia <= date(2028, 3, 31):
            propuesto = periodo_sugerido(clave, dia)
            validar_duracion_periodo(clave, dias(propuesto))
            dia += timedelta(days=1)

    @pytest.mark.parametrize("clave", CLAVES_CON_PERIODO)
    def test_siempre_es_un_periodo_YA_TERMINADO(self, clave):
        """
        Nunca el que está en curso. `cerrar_periodo` marca falta **todo día
        laborable sin checada**, incluidos los que aún no llegan: cerrar el mes
        en curso el día 2 daría faltas por los 28 días que faltan.
        """
        hoy = date(2026, 9, 3)
        propuesto = periodo_sugerido(clave, hoy)
        assert propuesto.fin < hoy
        assert propuesto.inicio <= propuesto.fin


class TestCadaPeriodicidadPropoLoSuyo:
    def test_mensual_es_el_mes_natural_anterior(self):
        p = periodo_sugerido("05", date(2026, 9, 3))
        assert (p.inicio, p.fin) == (date(2026, 8, 1), date(2026, 8, 31))

    def test_mensual_en_marzo_devuelve_febrero_completo(self):
        p = periodo_sugerido("05", date(2026, 3, 10))
        assert (p.inicio, p.fin) == (date(2026, 2, 1), date(2026, 2, 28))
        assert dias(p) == 28

    def test_semanal_es_lunes_a_domingo_ya_cerrado(self):
        # El 3-sep-2026 es jueves; la semana cerrada es 24-ago (lun) a 30 (dom).
        p = periodo_sugerido("02", date(2026, 9, 3))
        assert (p.inicio, p.fin) == (date(2026, 8, 24), date(2026, 8, 30))
        assert p.inicio.weekday() == 0 and p.fin.weekday() == 6
        assert dias(p) == 7

    def test_semanal_un_lunes_devuelve_la_semana_anterior_completa(self):
        """El borde: un lunes, la semana en curso acaba de empezar."""
        lunes = date(2026, 8, 31)
        assert lunes.weekday() == 0
        p = periodo_sugerido("02", lunes)
        assert (p.inicio, p.fin) == (date(2026, 8, 24), date(2026, 8, 30))

    def test_diaria_es_ayer(self):
        p = periodo_sugerido("01", date(2026, 9, 3))
        assert (p.inicio, p.fin) == (date(2026, 9, 2), date(2026, 9, 2))

    def test_quincenal_es_LA_MISMA_funcion_que_ya_usaba_la_demo(self):
        """
        `demo_nomina.quincena` delega aquí. Si divergieran, sembrar el checador
        y calcular la nómina usarían periodos distintos y el panel saldría
        vacío — que es lo que su propio docstring lleva advirtiendo desde D-05.
        """
        for dia in (date(2026, 3, 1), date(2026, 3, 20), date(2026, 1, 5)):
            assert periodo_sugerido("04", dia) == quincena(dia)


class TestLasClavesSinTarifa:
    @pytest.mark.parametrize("clave", ["03", "10", "06", "07", "08", "09", "99"])
    def test_no_se_les_propone_periodo(self, clave):
        """
        Proponer un periodo para una clave sin tarifa sería ofrecer un cálculo
        que después no se puede hacer.
        """
        with pytest.raises(FiscalValidationError, match="No hay periodo que proponer"):
            periodo_sugerido(clave, date(2026, 9, 3))

    def test_el_mensaje_dice_cuales_SI_se_pueden(self):
        with pytest.raises(FiscalValidationError) as e:
            periodo_sugerido("03", date(2026, 9, 3))
        assert "diaria, semanal, quincenal y mensual" in str(e.value)
        assert "§D10" in str(e.value)


class TestElEndpoint:
    def test_responde_el_periodo_y_sus_dias(self, cliente_http):
        r = cliente_http.get(
            RUTA, params={"clave_periodicidad": "05", "fecha": "2026-09-03"}
        )
        assert r.status_code == 200, r.text
        cuerpo = r.json()
        assert cuerpo["periodo"]["inicio"] == "2026-08-01"
        assert cuerpo["periodo"]["fin"] == "2026-08-31"
        assert cuerpo["dias_naturales"] == 31

    def test_la_fecha_de_pago_viaja_EXPLICITA(self, cliente_http):
        """
        No `None`. La pantalla tiene que poder decir con qué fecha se va a
        calcular sin replicar el default (§D18): de ella dependen la UMA, el
        salario mínimo y la tarifa vigentes.
        """
        r = cliente_http.get(
            RUTA, params={"clave_periodicidad": "04", "fecha": "2026-09-03"}
        )
        assert r.json()["periodo"]["fecha_pago"] is not None

    def test_los_dias_los_calcula_el_BACKEND(self, cliente_http):
        """
        Y no el cliente. Restar fechas en JavaScript con zonas horarias es de
        las cosas que dan 15 donde hay 16 — y ese día de menos entra a
        `DiasDelPeriodo`, o sea a las cuotas del IMSS y al ISR.
        """
        r = cliente_http.get(
            RUTA, params={"clave_periodicidad": "04", "fecha": "2026-03-05"}
        )
        cuerpo = r.json()
        # Del 16 al 28 de febrero de 2026: la quincena más corta del año.
        assert cuerpo["periodo"]["inicio"] == "2026-02-16"
        assert cuerpo["dias_naturales"] == 13

    def test_una_clave_sin_tarifa_devuelve_422_con_el_sobre_del_proyecto(
        self, cliente_http
    ):
        r = cliente_http.get(
            RUTA, params={"clave_periodicidad": "03", "fecha": "2026-09-03"}
        )
        assert r.status_code == 422
        assert r.json()["exito"] is False

    def test_sin_fecha_usa_hoy(self, cliente_http):
        r = cliente_http.get(RUTA, params={"clave_periodicidad": "04"})
        assert r.status_code == 200
        assert r.json()["periodo"]["fin"] < date.today().isoformat()
