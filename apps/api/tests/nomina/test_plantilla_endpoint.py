"""
Tests de `GET /api/v1/nomina/demo/plantilla` (D-07).

POR QUE EXISTE ESE ENDPOINT
---------------------------
Para que la pantalla de la demo **no escriba ni una constante fiscal**. Sin él,
el front tendría que hardcodear en TypeScript los nueve empleados y la
`prima_riesgo` —que tiene fundamento legal (Art. 72/74 LSS) y dueño en
`app/demo_nomina.py`— en un lugar donde ningún test verifica que no diverjan.

Y `periodo_sugerido` existe porque deducir el periodo de las fechas de las
checadas **da mal**: del 16 al 31 de agosto de 2026 son 16 días naturales, pero
la primera y la última checada son del 17 y el 31 (el 16 es domingo), o sea 15.
Ese día de menos entra a `DiasDelPeriodo` y a los días pagados: mueve las
cuotas del IMSS y el ISR, en pantalla y en el PDF.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.constants import CLIENTE_DEMO, ZonaSalarioMinimo
from app.demo_nomina import (
    CLAVE_PERIODICIDAD_DEMO,
    PLANTILLA_DEMO,
    PRIMA_RIESGO_DEMO,
    quincena,
)
from app.main import app

PLANTILLA = "/api/v1/nomina/demo/plantilla"


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


class TestPlantilla:
    def test_devuelve_los_nueve_empleados_con_su_nombre(self, cliente_http):
        cuerpo = cliente_http.get(PLANTILLA).json()
        assert cuerpo["origen"] == "demo"
        assert [(e["empleado_no"], e["nombre"]) for e in cuerpo["empleados"]] == [
            (e.empleado_no, e.nombre) for e in PLANTILLA_DEMO
        ]

    def test_no_expone_salarios(self):
        """
        El front no los necesita —los recibos ya los traen— y menos superficie
        es menos que pueda salir por donde no debe.
        """
        from app.schemas.nomina import EmpleadoDemoSchema

        assert set(EmpleadoDemoSchema.model_fields) == {"empleado_no", "nombre"}

    def test_devuelve_los_parametros_del_patron(self, cliente_http):
        """Son los que el front tendría que haber copiado a mano."""
        cuerpo = cliente_http.get(PLANTILLA).json()
        assert cuerpo["prima_riesgo"] == str(PRIMA_RIESGO_DEMO)
        assert cuerpo["clave_periodicidad"] == CLAVE_PERIODICIDAD_DEMO
        assert cuerpo["zona"] == ZonaSalarioMinimo.GENERAL.value

    def test_un_cliente_ajeno_no_recibe_la_plantilla(self, cliente_http):
        respuesta = cliente_http.get(PLANTILLA, params={"cliente": "acme"})
        assert respuesta.status_code == 422
        assert "no es la nómina de nadie más" in respuesta.json()["error"]

    def test_el_periodo_sugerido_trae_fecha_de_pago_explicita(self, cliente_http):
        """
        No `null`: la pantalla tiene que poder mostrar con qué fecha se calcula
        sin replicar el default en TypeScript. §D18 sigue abierta sobre cuál
        debería ser, y por eso el número se enseña en vez de asumirse.
        """
        sugerido = cliente_http.get(PLANTILLA).json()["periodo_sugerido"]
        assert sugerido["fecha_pago"] is not None
        assert sugerido["fecha_pago"] == sugerido["fin"]

    def test_el_periodo_sugerido_es_el_de_la_regla_de_quincena(self, cliente_http):
        esperado = quincena(date.today())
        sugerido = cliente_http.get(PLANTILLA).json()["periodo_sugerido"]
        assert sugerido["inicio"] == esperado.inicio.isoformat()
        assert sugerido["fin"] == esperado.fin.isoformat()


class TestLaQuincenaSonDieciseisDias:
    """
    El ancla contra el heurístico que D-07 estuvo a punto de meter desde el
    front. Los dos números van literales.
    """

    def test_del_16_al_31_son_16_dias_naturales_no_15(self):
        periodo = quincena(date(2026, 9, 1))
        assert (periodo.inicio, periodo.fin) == (date(2026, 8, 16), date(2026, 8, 31))
        assert (periodo.fin - periodo.inicio).days + 1 == 16

    def test_la_primera_y_la_ultima_checada_darian_15(self):
        """
        Lo que habría pasado con `min`/`max` de los eventos: el 16 de agosto de
        2026 es domingo, así que la primera checada es del 17. Un día menos de
        base para EyM, IyV, Retiro y CEAV, y un día menos pagado.
        """
        periodo = quincena(date(2026, 9, 1))
        laborables = [
            periodo.inicio + __import__("datetime").timedelta(days=n)
            for n in range((periodo.fin - periodo.inicio).days + 1)
        ]
        laborables = [d for d in laborables if d.weekday() < 5]
        assert laborables[0] == date(2026, 8, 17)
        assert (laborables[-1] - laborables[0]).days + 1 == 15


class TestFechaDePagoEfectiva:
    """
    La respuesta del cálculo dice **con qué fecha se calculó**, ya resuelto el
    default. Sin eso, el front tendría que replicar `fecha_pago ?? fin` y el PDF
    mentiría en silencio el día que el default cambie (§D18 está abierta).
    """

    def _cuerpo(self, periodo):
        return {
            "cliente": CLIENTE_DEMO,
            "periodo": periodo,
            "incidencias": [
                {
                    "empleado_no": e.empleado_no,
                    "dias_periodo": 16,
                    "faltas": 0,
                    "dias_ausentismo": 0,
                }
                for e in PLANTILLA_DEMO
            ],
            "parametros": {"prima_riesgo": "0.0054355", "clave_periodicidad": "04"},
        }

    def test_sin_fecha_de_pago_la_efectiva_es_el_fin_del_periodo(self, cliente_http):
        cuerpo = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json=self._cuerpo({"inicio": "2026-08-16", "fin": "2026-08-31"}),
        ).json()
        assert cuerpo["fecha_pago_efectiva"] == "2026-08-31"

    def test_con_fecha_de_pago_explicita_se_devuelve_esa(self, cliente_http):
        cuerpo = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json=self._cuerpo(
                {"inicio": "2026-01-16", "fin": "2026-01-31", "fecha_pago": "2026-02-05"}
            ),
        ).json()
        assert cuerpo["fecha_pago_efectiva"] == "2026-02-05"
