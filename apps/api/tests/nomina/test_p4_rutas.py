"""
Rutas de nómina completa (P4-01 a P4-08): plantilla del backend, criterios, variables,
asimilados, historial y multi-tenant.

Esperados a mano. Tarifas derivadas de la mensual 2026 con la regla del Anexo 8
(diaria = mensual / 30.4 redondeada, × días).
"""

from decimal import Decimal as D

import pytest

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


def _inc(no, dias=16, faltas=0, **extra):
    return {
        "empleado_no": no,
        "dias_periodo": dias,
        "faltas": faltas,
        "dias_ausentismo": faltas,
        **extra,
    }


def _calc(http, cliente="p4", periodo=QUINCENA, incidencias=None, **extra):
    r = http.post(
        CALC,
        json={
            "cliente": cliente,
            "periodo": periodo,
            "incidencias": incidencias or [_inc("A-1")],
            **extra,
        },
    )
    return r


def _deduccion(recibo, tipo):
    return next((D(d["importe"]) for d in recibo["deducciones"] if d["tipo"] == tipo), D("0"))


@pytest.fixture
def http(api):
    c = api("uid-p4")
    sembrar_cliente(c, "p4", [_emp("A-1")])
    return c


class TestPeriodosParcialesD26:
    def _con_alta(self, api, criterio):
        c = api(f"uid-d26-{criterio}")
        sembrar_cliente(
            c, "p4", [_emp("A-1", fecha_alta="2026-08-24")], criterios={"parcial": criterio}
        )
        return _calc(c).json()["recibos"][0]

    def test_ya_no_se_bloquea_y_paga_los_dias_con_relacion(self, api):
        r = self._con_alta(api, "tarifa_proporcional")
        assert r["parcial"] is True and r["dias_en_periodo"] == 8 and r["dias_pagados"] == 8
        assert D(r["total_percepciones"]) == D("4000.00")

    def test_tarifa_proporcional_default_conservador(self, api):
        """Tarifa de 8 días: renglón 5 (3,853.85 / 352.40 / 17.92 %) → 378.59."""
        assert _deduccion(self._con_alta(api, "tarifa_proporcional"), "002") == D("378.59")

    def test_tarifa_del_periodo(self, api):
        """Quincenal: renglón 3 (3,537.16 / 207.75 / 10.88 %) → 258.11. Retiene menos."""
        assert _deduccion(self._con_alta(api, "tarifa_periodo"), "002") == D("258.11")


class TestFebreroD27:
    FEB = {"inicio": "2026-02-16", "fin": "2026-02-28"}

    @pytest.mark.parametrize(
        "criterio, dias, sueldo",
        [
            ("quince_siempre", 15, "7500.00"),
            ("dias_calendario", 13, "6500.00"),
        ],
    )
    def test_quince_o_calendario(self, api, criterio, dias, sueldo):
        c = api(f"uid-d27-{criterio}")
        sembrar_cliente(c, "p4", [_emp("A-1")], criterios={"febrero": criterio})
        r = _calc(c, periodo=self.FEB, incidencias=[_inc("A-1", 13)]).json()["recibos"][0]
        assert r["dias_pagados"] == dias and r["total_percepciones"] == sueldo


class TestCatorcenalYDecenal:
    def test_catorcenal_calcula_y_advierte_que_es_derivada(self, api):
        c = api("uid-cat")
        sembrar_cliente(c, "p4", [_emp("A-1")], periodicidad="03")
        r = _calc(
            c, periodo={"inicio": "2026-08-03", "fin": "2026-08-16"}, incidencias=[_inc("A-1", 14)]
        )
        assert r.status_code == 200, r.text
        assert any("DERIVADA" in a for a in r.json()["advertencias"])

    def test_decenal_calcula(self, api):
        c = api("uid-dec")
        sembrar_cliente(c, "p4", [_emp("A-1")], periodicidad="10")
        r = _calc(
            c, periodo={"inicio": "2026-08-01", "fin": "2026-08-10"}, incidencias=[_inc("A-1", 10)]
        )
        assert r.status_code == 200, r.text
        assert r.json()["recibos"][0]["dias_pagados"] == 10


class TestAsimilados:
    def test_isr_correcto_y_sin_cuotas_ni_subsidio(self, api):
        """
        1,000 × 15 = 15,000 (quincena). Tarifa quincenal renglón 6 (8,651.41 / 916.20 /
        21.36 %): 916.20 + 6,348.59 × 21.36 % = 2,272.26. Sin IMSS (no hay relación laboral)
        ni subsidio (Art. 94 fr. IV, régimen 09).
        """
        c = api("uid-asim")
        sembrar_cliente(
            c, "p4", [_emp("A-1"), _emp("H-1", "1000.00", "1000.00", tipo_regimen="09")]
        )
        cuerpo = _calc(c, tipo="asimilados", incidencias=[_inc("H-1")]).json()
        assert [r["empleado_no"] for r in cuerpo["recibos"]] == ["H-1"]
        r = cuerpo["recibos"][0]
        assert r["percepciones"][0]["tipo"] == "046" and r["tipo_regimen"] == "09"
        assert _deduccion(r, "002") == D("2272.26")
        assert _deduccion(r, "001") == D("0") and r["ramos"] == [] and r["otros_pagos"] == []

    def test_sin_cierre_del_checador_toma_el_periodo_completo(self, api):
        """Los asimilados no checan: sin incidencias se calcula el periodo entero."""
        c = api("uid-asim3")
        sembrar_cliente(
            c, "p4", [_emp("A-1"), _emp("H-1", "1000.00", "1000.00", tipo_regimen="09")]
        )
        r = c.post(
            CALC,
            json={"cliente": "p4", "periodo": QUINCENA, "incidencias": [], "tipo": "asimilados"},
        )
        assert r.status_code == 200, r.text
        assert _deduccion(r.json()["recibos"][0], "002") == D("2272.26")

    def test_la_ordinaria_sigue_exigiendo_incidencias(self, http):
        r = http.post(CALC, json={"cliente": "p4", "periodo": QUINCENA, "incidencias": []})
        assert r.status_code == 422

    def test_la_ordinaria_no_incluye_asimilados(self, api):
        c = api("uid-asim2")
        sembrar_cliente(c, "p4", [_emp("A-1"), _emp("H-1", tipo_regimen="09")])
        assert [r["empleado_no"] for r in _calc(c).json()["recibos"]] == ["A-1"]


class TestVariables:
    def _calc(self, api, variables, inc=None):
        c = api("uid-var")
        sembrar_cliente(c, "p4", [_emp("A-1", "480.00", "504.00")])
        return _calc(c, incidencias=[inc or _inc("A-1")], variables=[variables]).json()["recibos"][
            0
        ]

    def test_horas_extra_dobles_y_triples(self, api):
        """9 dobles a 60/h = 1,080, exento 50 % = 540 (≤ 5 UMA/semana); 2 triples = 360 gravadas."""
        r = self._calc(api, {"empleado_no": "A-1", "horas_dobles": "9", "horas_triples": "2"})
        he = [p for p in r["percepciones"] if p["tipo"] == "019"]
        assert (D(he[0]["importe"]), D(he[0]["exento"])) == (D("1080.00"), D("540.00"))
        assert (D(he[1]["importe"]), D(he[1]["gravado"])) == (D("360.00"), D("360.00"))
        assert D(r["sbc_variable_integrable"]) == D("360.00")  # Art. 27 fr. IX LSS

    def test_horas_dobles_sobre_el_limite_de_la_lft_se_advierten(self, api):
        c = api("uid-var2")
        sembrar_cliente(c, "p4", [_emp("A-1", "480.00", "504.00")])
        r = _calc(c, variables=[{"empleado_no": "A-1", "horas_dobles": "40"}]).json()
        assert any("Art. 66 LFT" in a for a in r["advertencias"])

    def test_prima_dominical_exenta_hasta_1_uma_por_domingo(self, api):
        r = self._calc(api, {"empleado_no": "A-1", "domingos_trabajados": 2})
        p = next(p for p in r["percepciones"] if p["tipo"] == "020")
        assert (D(p["importe"]), D(p["exento"])) == (D("240.00"), D("234.62"))

    def test_incapacidad_reduce_pagados_y_cotizacion_menos_eym(self, api):
        r = self._calc(api, {"empleado_no": "A-1", "incapacidades": [{"tipo": "02", "dias": 2}]})
        assert r["dias_pagados"] == 13  # 15 − 2
        dias = {x["clave"]: x["dias"] for x in r["ramos"]}
        assert dias["eym_prestaciones_dinero"] == 16 and dias["invalidez_vida"] == 14

    def test_infonavit_fonacot_y_pension(self, api):
        r = self._calc(
            api,
            {
                "empleado_no": "A-1",
                "infonavit": {"tipo": "porcentaje", "valor": "0.20"},
                "fonacot": "5000",
                "pension": {"tipo": "porcentaje", "valor": "0.10", "base": "bruto"},
            },
        )
        assert _deduccion(r, "010") == D("1612.80")  # 504 × 20 % × 16
        assert _deduccion(r, "011") == D("1440.00")  # topado a 20 % de 7,200
        assert _deduccion(r, "007") == D("720.00")  # 10 % de 7,200


class TestHistorial:
    def test_guardar_listar_abrir_identico(self, http):
        calculo = _calc(http).json()
        pid = calculo["periodo_id"]
        lista = http.get("/api/v1/nomina/clientes/p4/historial").json()["periodos"]
        assert [p["id"] for p in lista] == [pid]
        abierto = http.get(f"/api/v1/nomina/clientes/p4/periodos/{pid}").json()
        assert abierto["resultado"]["recibos"] == calculo["recibos"]
        assert abierto["parametros"]["uma_diaria"] == "117.31"
        assert abierto["criterios"]["febrero"] == "quince_siempre"

    def test_abrir_no_recalcula_aunque_cambie_el_criterio(self, http):
        pid = _calc(http).json()["periodo_id"]
        antes = http.get(f"/api/v1/nomina/clientes/p4/periodos/{pid}").json()["resultado"]
        sembrar_cliente(http, "p4", [], criterios={"febrero": "dias_calendario"})
        despues = http.get(f"/api/v1/nomina/clientes/p4/periodos/{pid}").json()["resultado"]
        assert antes == despues

    def test_recalcular_reemplaza_y_cerrar_bloquea(self, http):
        pid = _calc(http).json()["periodo_id"]
        assert _calc(http).json()["periodo_id"] == pid
        assert http.post(f"/api/v1/nomina/clientes/p4/periodos/{pid}/cerrar").status_code == 200
        r = _calc(http)
        assert r.status_code == 409 and "cerrada" in r.json()["error"]

    def test_comparar(self, http):
        a = _calc(http).json()["periodo_id"]
        b = _calc(
            http,
            periodo={"inicio": "2026-09-01", "fin": "2026-09-15"},
            incidencias=[_inc("A-1", 15, faltas=1)],
        ).json()["periodo_id"]
        cmp = http.get(f"/api/v1/nomina/clientes/p4/comparar?a={a}&b={b}").json()
        assert D(cmp["diferencia_neto"]) < 0
        assert cmp["por_empleado"][0]["empleado_no"] == "A-1"


class TestMultiTenant:
    def test_otro_despacho_no_ve_ni_calcula(self, http, api):
        pid = _calc(http).json()["periodo_id"]
        ajeno = api("uid-otro-despacho")
        assert _calc(ajeno).status_code == 404
        assert ajeno.get("/api/v1/nomina/clientes/p4/historial").status_code == 404
        assert ajeno.get(f"/api/v1/nomina/clientes/p4/periodos/{pid}").status_code == 404
        sembrar_cliente(ajeno, "p4", [_emp("A-1")])
        assert ajeno.get(f"/api/v1/nomina/clientes/p4/periodos/{pid}").status_code == 404
        assert ajeno.get("/api/v1/nomina/clientes/p4/historial").json()["periodos"] == []


class TestCalculadoras:
    def test_aguinaldo_con_alta_a_medio_anio(self, api):
        c = api("uid-agui")
        sembrar_cliente(c, "p4", [_emp("A-1", "400.00", "420.00", fecha_alta="2026-07-01")])
        r = c.post(
            "/api/v1/nomina/clientes/p4/aguinaldo",
            json={"ejercicio": 2026, "fecha_pago": "2026-12-15"},
        ).json()
        fila = r["resultado"]["recibos"][0]
        assert fila["total_percepciones"] == "3024.66" and r["periodo_id"]

    def test_finiquito_y_ptu_y_ajuste(self, api):
        c = api("uid-calc")
        sembrar_cliente(c, "p4", [_emp("A-1", "500.00", "525.00", fecha_alta="2020-01-01")])
        fin = c.post(
            "/api/v1/nomina/clientes/p4/finiquito",
            json={
                "empleado_no": "A-1",
                "fecha_baja": "2026-06-30",
                "causa": "despido_injustificado",
            },
        )
        assert fin.status_code == 200, fin.text
        assert D(fin.json()["resultado"]["isr_separacion"]) > 0
        ptu = c.post(
            "/api/v1/nomina/clientes/p4/ptu",
            json={
                "ejercicio": 2025,
                "renta_gravable": "100000",
                "fecha_pago": "2026-05-29",
                "trabajadores": [
                    {"empleado_no": "A-1", "dias_trabajados": 365, "salarios_devengados": "182500"}
                ],
            },
        )
        assert ptu.json()["resultado"]["repartido"] == "10000.00"
        aj = c.post(
            "/api/v1/nomina/clientes/p4/ajuste-anual",
            json={
                "ejercicio": 2026,
                "trabajadores": [
                    {"empleado_no": "A-1", "ingresos_gravados": "180000", "isr_retenido": "15000"}
                ],
            },
        )
        assert aj.json()["resultado"]["trabajadores"][0]["saldo_a_cargo"] == "1833.81"
        tipos = {
            p["tipo"] for p in c.get("/api/v1/nomina/clientes/p4/historial").json()["periodos"]
        }
        assert tipos == {"finiquito", "ptu"}

    def test_criterios_con_explicacion(self, http):
        r = http.get("/api/v1/nomina/criterios").json()
        assert r["defaults"]["parcial"] == "tarifa_proporcional"
        assert "conservadora" in r["opciones"]["parcial"]["tarifa_proporcional"]
