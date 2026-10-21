"""
Correcciones del revisor de motor sobre P4 (B2, B5, O2, O3, O5, O8, O9). Esperados a mano.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine.ajuste_anual import DatosAnuales, ajuste_anual
from app.nomina_engine.jornada import tope_horas_extra_semanal
from app.nomina_engine.ptu import TrabajadorPTU, repartir_ptu
from tests.nomina.cartera_sembrada import sembrar_cliente

CALC = "/api/v1/nomina/calcular-periodo"
QUINCENA = {"inicio": "2026-08-16", "fin": "2026-08-31"}


def _emp(no, diario="500.00", sdi="525.00", **extra):
    return {
        "empleado_no": no,
        "nombre": f"PERSONA {no}",
        "salario_diario": diario,
        "salario_diario_integrado": sdi,
        **extra,
    }


def _inc(no, dias=16):
    return {"empleado_no": no, "dias_periodo": dias, "faltas": 0, "dias_ausentismo": 0}


class TestB2TopeDeHorasExtra:
    """Art. 66 LFT y Transitorio Cuarto del Decreto DOF 01-05-2026."""

    @pytest.mark.parametrize(
        "fecha, horas",
        [
            (date(2026, 8, 31), D("9")),
            (date(2027, 12, 31), D("9")),
            (date(2028, 1, 1), D("10")),
            (date(2029, 6, 1), D("11")),
            (date(2030, 1, 1), D("12")),
            (date(2035, 1, 1), D("12")),
        ],
    )
    def test_vigencia_por_fecha(self, fecha, horas):
        assert tope_horas_extra_semanal(fecha) == horas

    def test_lo_que_pasa_del_tope_se_paga_triple_y_gravado(self, api):
        """
        2026, quincena de 16 días: tope 9 × 16/7 = 20.57 horas. De 30 dobles a $60/h, 20.57
        quedan dobles ($2,468.40) y 9.43 pasan a triples ($1,697.40), 100 % gravadas.
        """
        c = api("uid-b2")
        sembrar_cliente(c, "p4", [_emp("A-1", "480.00", "504.00")])
        r = c.post(
            CALC,
            json={
                "cliente": "p4",
                "periodo": QUINCENA,
                "incidencias": [_inc("A-1")],
                "variables": [{"empleado_no": "A-1", "horas_dobles": "30"}],
            },
        ).json()
        he = {p["clave"]: p for p in r["recibos"][0]["percepciones"] if p["tipo"] == "019"}
        assert D(he["P019D"]["importe"]) == D("2468.40")
        assert (D(he["P019T"]["importe"]), D(he["P019T"]["exento"])) == (D("1697.40"), D("0"))
        assert any("Art. 68" in a for a in r["advertencias"])


class TestB5FiniquitoConIngresoDelMes:
    def test_la_ruta_apila_lo_ordinario_sobre_salario_por_30_4(self, api):
        """ISR(5,654.67 + 15,200) − ISR(15,200) = 2,566.21 − 1,438.66 = 1,127.55."""
        c = api("uid-b5")
        sembrar_cliente(c, "p4", [_emp("A-1", fecha_alta="2020-01-01")])
        r = c.post(
            "/api/v1/nomina/clientes/p4/finiquito",
            json={
                "empleado_no": "A-1",
                "fecha_baja": "2026-06-30",
                "causa": "despido_injustificado",
                "incluir_20_dias": True,
            },
        ).json()
        assert r["resultado"]["isr_ordinario"] == "1127.55"


class TestO2Consejeros:
    def test_retencion_a_la_tasa_maxima_sobre_todo_el_monto(self, api):
        """
        15,000 de honorarios de consejero × 35 % = 5,250.00 (tarifa daría 2,272.26).
        P6-07: la ficha lo marca como consejero (antes se suponía por el régimen 07).
        """
        c = api("uid-o2")
        sembrar_cliente(
            c, "p4", [_emp("C-1", "1000.00", "1000.00", tipo_regimen="07", es_consejero=True)]
        )
        r = c.post(
            CALC,
            json={"cliente": "p4", "periodo": QUINCENA, "incidencias": [], "tipo": "asimilados"},
        ).json()
        isr = next(d for d in r["recibos"][0]["deducciones"] if d["tipo"] == "002")
        assert D(isr["importe"]) == D("5250.00")


class TestO3PrimaVacacionalAnual:
    def test_el_segundo_pago_del_anio_ya_no_tiene_exencion(self, api):
        """1,000 × 30 días × 25 % = 7,500 de prima; el tope anual es 15 UMA = 1,759.65."""
        c = api("uid-o3")
        sembrar_cliente(c, "p4", [_emp("A-1", "1000.00", "1050.00")])

        def prima(periodo, dias):
            r = c.post(
                CALC,
                json={
                    "cliente": "p4",
                    "periodo": periodo,
                    "incidencias": [_inc("A-1", dias)],
                    "variables": [{"empleado_no": "A-1", "dias_vacaciones": 30}],
                },
            ).json()
            return next(p for p in r["recibos"][0]["percepciones"] if p["tipo"] == "021")

        primera = prima(QUINCENA, 16)
        assert D(primera["exento"]) == D("1759.65")
        segunda = prima({"inicio": "2026-09-01", "fin": "2026-09-15"}, 15)
        assert D(segunda["exento"]) == D("0") and D(segunda["gravado"]) == D("7500.00")
        # Recalcular el primero no se cuenta a sí mismo; el segundo no exentó nada, así
        # que el primero conserva su exención completa.
        assert D(prima(QUINCENA, 16)["exento"]) == D("1759.65")

    def test_la_captura_previa_se_resta(self, api):
        c = api("uid-o3b")
        sembrar_cliente(c, "p4", [_emp("A-1", "1000.00", "1050.00")])
        r = c.post(
            CALC,
            json={
                "cliente": "p4",
                "periodo": QUINCENA,
                "incidencias": [_inc("A-1")],
                "variables": [
                    {
                        "empleado_no": "A-1",
                        "dias_vacaciones": 30,
                        "prima_vacacional_exenta_previa": "1000",
                    }
                ],
            },
        ).json()
        p = next(p for p in r["recibos"][0]["percepciones"] if p["tipo"] == "021")
        assert D(p["exento"]) == D("759.65")


class TestO5O8PTU:
    TRAB = (
        TrabajadorPTU("S", 365, D("400"), D("146000"), tipo="sindicalizado"),
        TrabajadorPTU("P", 365, D("600"), D("219000"), tipo="planta"),
        TrabajadorPTU("E", 365, D("900"), D("328500"), tipo="eventual"),
        TrabajadorPTU("C", 365, D("1000"), D("365000"), tipo="confianza"),
    )

    def test_el_tope_de_confianza_sale_del_sindicalizado(self):
        """400 × 1.2 = 480: los salarios de C cuentan como 365,000 × 480/1000 = 175,200."""
        r = repartir_ptu(D("1000000"), self.TRAB, date(2026, 5, 29))
        c = next(t for t in r.trabajadores if t.empleado_no == "C")
        # por salarios: 50,000 × 175,200 / (146,000 + 219,000 + 328,500 + 175,200)
        assert c.por_salarios == D("10084.03")

    def test_sin_sindicalizados_manda_el_de_planta_y_no_el_eventual(self):
        """600 × 1.2 = 720 (el eventual gana 900 y no cuenta): 365,000 × 720/1000 = 262,800."""
        r = repartir_ptu(D("1000000"), self.TRAB[1:], date(2026, 5, 29))
        c = next(t for t in r.trabajadores if t.empleado_no == "C")
        assert c.por_salarios == D("16216.22")  # 50,000 × 262,800 / 810,300

    def test_avisa_lo_no_modelado(self):
        r = repartir_ptu(D("1000000"), self.TRAB, date(2026, 5, 29))
        assert any("fr. III" in a and "fr. VII" in a and "fr. X" in a for a in r.avisos)

    def test_remanente_al_ejercicio_siguiente(self):
        trab = (TrabajadorPTU("A", 365, D("100"), D("36500")),)
        r = repartir_ptu(
            D("1000000"), trab, date(2026, 5, 29), remanente="sumar_siguiente_ejercicio"
        )
        assert r.remanente == D("91000.00")  # 100,000 − tope 90 × 100
        assert any("ejercicio siguiente" in a and "Art. 122" in a for a in r.avisos)


class TestO9ImpuestoLocal:
    BASE = dict(
        ejercicio=2026,
        fecha_alta=date(2020, 1, 1),
        fecha_baja=None,
        ingresos_gravados=D("180000"),
        ingresos_exentos=D("0"),
        isr_retenido=D("15000"),
    )

    def test_se_resta_de_la_base(self):
        """Base 180,000 − 3,000 = 177,000: 16,069.64 + 1,264.33 × 17.92 % = 16,296.21."""
        r = ajuste_anual(
            DatosAnuales(
                **self.BASE, impuesto_local_retenido=D("3000"), tasa_impuesto_local=D("0.03")
            )
        )
        assert r.impuesto_anual == D("16296.21")

    def test_con_tasa_mayor_al_5_por_ciento_no_procede(self):
        with pytest.raises(FiscalValidationError, match="5 %"):
            ajuste_anual(
                DatosAnuales(
                    **self.BASE, impuesto_local_retenido=D("3000"), tasa_impuesto_local=D("0.06")
                )
            )
