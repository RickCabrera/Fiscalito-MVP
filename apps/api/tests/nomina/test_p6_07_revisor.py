"""
P6-07 — observaciones de la 2.ª pasada del revisor de motor. Esperados a mano.

1. Consejero que además es trabajador (Art. 96 LISR, quinto párrafo): flag por empleado.
2. Citas de párrafo: Art. 9 quinto, Art. 97 tercero, Art. 96 quinto.
3. No objeto de IVA por `ObjetoImp == "01"`; residuo sólo para CFDI 3.3, con aviso.
4. Tope diario de horas extra (Art. 66 LFT) y triples del Art. 68 segundo párrafo.
5. Finiquito: resta los exentos del año (Art. 93 fr. XIV, por año de calendario).
6. Archivos partidos a ≤ 300 líneas, con los nombres de antes todavía importables.
"""

import inspect
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.exceptions import FiscalValidationError
from app.fiscal_engine import pm_anual
from app.fiscal_engine.iva import MovimientoIVA, calcular_iva_mes
from app.impuestos.servicio import base_no_objeto, movimiento_iva
from app.nomina_engine import ajuste_anual as aa
from app.nomina_engine import periodo_completo
from app.nomina_engine.finiquito import DatosSeparacion, calcular_finiquito
from app.nomina_engine.jornada import clasificar_horas_por_dia, veces_por_semana
from app.nomina_engine.periodo_completo_tipos import EmpleadoNomina
from app.nomina_engine.variables_tipos import VariablesEmpleado
from tests.nomina.cartera_sembrada import sembrar_cliente

CALC = "/api/v1/nomina/calcular-periodo"
QUINCENA = {"inicio": "2026-08-16", "fin": "2026-08-31"}
APP = Path(__file__).resolve().parents[2] / "app"


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


# ── 1. Consejero ──


class TestConsejero:
    """15,000 de honorarios: tasa mínima 35 % = 5,250.00; tarifa = 2,272.26."""

    def _isr(self, c, **flags):
        sembrar_cliente(c, "p6", [_emp("C-1", "1000.00", "1000.00", **flags)])
        r = c.post(
            CALC,
            json={"cliente": "p6", "periodo": QUINCENA, "incidencias": [], "tipo": "asimilados"},
        ).json()
        isr = next(d for d in r["recibos"][0]["deducciones"] if d["tipo"] == "002")
        return D(isr["importe"]), r["advertencias"]

    def test_consejero_que_ademas_es_trabajador_usa_la_tarifa(self, api):
        isr, avisos = self._isr(
            api("uid-p607-1"), tipo_regimen="07", es_consejero=True, consejero_es_trabajador=True
        )
        assert isr == D("2272.26")
        assert any("además es trabajador" in a and "quinto párrafo" in a for a in avisos)

    def test_el_regimen_07_sin_marca_lleva_la_minima_por_default(self, api):
        # Decisión provisional conservadora: el 07 es "miembros de consejos".
        isr, avisos = self._isr(api("uid-p607-2"), tipo_regimen="07")
        assert isr == D("5250.00")
        assert any("régimen 07 sin marcar" in a for a in avisos)

    def test_el_regimen_07_que_ademas_es_trabajador_usa_tarifa(self, api):
        isr, avisos = self._isr(api("uid-p607-2b"), tipo_regimen="07",
                                consejero_es_trabajador=True)
        assert isr == D("2272.26")
        assert any("se retiene con la tarifa" in a for a in avisos)
        assert not any("se aplica la retención mínima" in a for a in avisos)

    def test_administrador_en_honorarios_09_marcado_lleva_la_minima(self, api):
        isr, avisos = self._isr(api("uid-p607-3"), tipo_regimen="09", es_consejero=True)
        assert isr == D("5250.00")
        assert any("Art. 96 LISR, quinto párrafo" in a for a in avisos)

    def test_un_asalariado_marcado_no_lleva_la_minima(self):
        e = EmpleadoNomina("X", "X", D("1"), D("1"), es_consejero=True)
        assert not e.aplica_retencion_minima_consejero


# ── 2. Citas de párrafo ──


class TestCitas:
    def test_art_96_quinto_parrafo(self):
        fuente = inspect.getsource(periodo_completo)
        assert "Art. 96 LISR, quinto párrafo" in fuente
        assert "penúltimo párrafo" not in fuente

    def test_art_97_tercer_parrafo_en_los_saldos(self):
        cargo = aa.ajuste_anual(
            aa.DatosAnuales(2026, date(2025, 1, 1), None, D("200000"), D("0"), D("0"))
        )
        favor = aa.ajuste_anual(
            aa.DatosAnuales(2026, date(2025, 1, 1), None, D("100000"), D("0"), D("50000"))
        )
        assert "Art. 97 LISR, tercer párrafo" in cargo.tratamiento
        assert "Art. 97 LISR, tercer párrafo" in favor.tratamiento
        assert "quinto párr. fr. II" in aa.motivo_no_procede(
            aa.DatosAnuales(2026, None, None, D("500000"), D("0"), D("0"))
        )

    def test_art_9_quinto_parrafo_para_el_28_xxx(self):
        fuente = inspect.getsource(pm_anual)
        assert "Art. 9 quinto párrafo: no deducibles por el Art. 28 fr. XXX" in fuente
        for ruta in ("impuestos/papeles.py", "impuestos/personas_morales.py"):
            texto = (APP / ruta).read_text()
            assert "Art. 9 cuarto párrafo" not in texto
        assert "(Art. 9 quinto párrafo)" in (APP / "impuestos/papeles.py").read_text()


# ── 3. IVA no objeto por ObjetoImp ──


def _comp(conceptos, subtotal="1800", descuento="0", **extra):
    return SimpleNamespace(
        uuid="U-1",
        direccion="emitido",
        tipo="I",
        subtotal=D(subtotal),
        descuento=D(descuento),
        iva_trasladado=D("160"),
        iva_retenido=D("0"),
        uso_cfdi="G03",
        datos={
            "conceptos": conceptos,
            "impuestos": {
                "traslados": [
                    {"Impuesto": "002", "TipoFactor": "Tasa", "TasaOCuota": "0.160000",
                     "Base": "1000", "Importe": "160"}
                ]
            },
        },
        **extra,
    )


CONCEPTOS_40 = [
    {"Importe": "1000", "ObjetoImp": "02"},
    {"Importe": "500", "Descuento": "50", "ObjetoImp": "01"},
    {"Importe": "300", "ObjetoImp": "03"},  # sí objeto sin desglose: NO es no objeto
]


class TestNoObjetoIVA:
    def test_cfdi_40_solo_cuenta_objeto_imp_01(self):
        # Por residuo saldría 1,800 − 1,000 = 800; por ObjetoImp, 500 − 50 = 450.
        assert base_no_objeto(_comp(CONCEPTOS_40), D("1000")) == (D("450"), False)

    def test_cfdi_33_sin_objeto_imp_cae_al_residuo(self):
        conceptos = [{"Importe": "1000"}, {"Importe": "800"}]
        assert base_no_objeto(_comp(conceptos), D("1000")) == (D("800"), True)

    def test_movimiento_y_aviso_del_motor(self):
        e = SimpleNamespace(comprobante=_comp(CONCEPTOS_40), factor_pesos=D("1"), origen="PUE")
        m = movimiento_iva(e)
        assert (m.base_no_objeto, m.no_objeto_por_residuo) == (D("450"), False)
        r = calcular_iva_mes(2026, 3, [m])
        assert r.valor_no_objeto == D("450.00")
        assert not any("ObjetoImp" in n for n in r.notas)
        r33 = calcular_iva_mes(
            2026, 3,
            [MovimientoIVA("V-33", "emitido", base_16=D("1000"), base_no_objeto=D("800"),
                           no_objeto_por_residuo=True)],
        )
        assert any("ObjetoImp" in n and "V-33" in n for n in r33.notas)


# ── 4. Tope diario de horas extra ──


class TestTopeDiario:
    FECHA = date(2026, 8, 31)

    def test_lo_que_pasa_de_3_horas_diarias_es_triple(self):
        c = clasificar_horas_por_dia([D("4"), D("4")], self.FECHA)
        assert (c.dobles, c.triples, c.exceso_diario) == (D("6"), D("2"), D("2"))

    def test_el_cuarto_dia_de_la_semana_es_triple(self):
        c = clasificar_horas_por_dia([D("2")] * 4, self.FECHA)
        assert (c.dobles, c.triples, c.exceso_veces) == (D("6"), D("2"), D("2"))

    def test_cada_semana_tiene_su_tope(self):
        semana = [D("3")] * 3 + [D("0")] * 4
        c = clasificar_horas_por_dia(semana * 2, self.FECHA)
        assert (c.dobles, c.triples) == (D("18"), D("0"))

    def test_tope_semanal_desde_2028(self):
        assert (veces_por_semana(self.FECHA), veces_por_semana(date(2028, 3, 1))) == (3, 4)
        c = clasificar_horas_por_dia([D("3")] * 4, date(2028, 3, 1))
        assert (c.dobles, c.triples, c.exceso_semanal) == (D("10"), D("2"), D("2"))

    def test_no_se_capturan_las_dos_formas(self):
        with pytest.raises(FiscalValidationError):
            VariablesEmpleado("A", horas_dobles=D("1"), horas_extra_por_dia=(D("1"),))

    def test_por_la_ruta(self, api):
        """$480 diarios → $60/h. 6 dobles = $720.00; 2 triples = $360.00, 100 % gravadas."""
        c = api("uid-p607-he")
        sembrar_cliente(c, "p6", [_emp("A-1", "480.00", "504.00")])
        r = c.post(
            CALC,
            json={
                "cliente": "p6",
                "periodo": QUINCENA,
                "incidencias": [_inc("A-1")],
                "variables": [{"empleado_no": "A-1", "horas_extra_por_dia": ["4", "4"]}],
            },
        ).json()
        he = {p["clave"]: p for p in r["recibos"][0]["percepciones"] if p["tipo"] == "019"}
        assert D(he["P019D"]["importe"]) == D("720.00")
        assert (D(he["P019T"]["importe"]), D(he["P019T"]["exento"])) == (D("360.00"), D("0"))
        assert any("pasan de 3 diarias" in a for a in r["advertencias"])

    def test_sin_desglose_diario_se_avisa(self, api):
        c = api("uid-p607-he2")
        sembrar_cliente(c, "p6", [_emp("A-1", "480.00", "504.00")])
        r = c.post(
            CALC,
            json={
                "cliente": "p6",
                "periodo": QUINCENA,
                "incidencias": [_inc("A-1")],
                "variables": [{"empleado_no": "A-1", "horas_dobles": "5"}],
            },
        ).json()
        assert any("sin desglose diario" in a for a in r["advertencias"])

    def test_mas_dias_que_el_periodo(self, api):
        c = api("uid-p607-he3")
        sembrar_cliente(c, "p6", [_emp("A-1", "480.00", "504.00")])
        r = c.post(
            CALC,
            json={
                "cliente": "p6",
                "periodo": QUINCENA,
                "incidencias": [_inc("A-1")],
                "variables": [{"empleado_no": "A-1", "horas_extra_por_dia": ["1"] * 17}],
            },
        )
        assert r.status_code == 422


# ── 5. Finiquito con los exentos del año ──


def _sep(**extra):
    return DatosSeparacion(
        fecha_alta=date(2020, 1, 1),
        fecha_baja=date(2026, 8, 31),
        salario_diario=D("1000"),
        salario_diario_integrado=D("1050"),
        causa="renuncia",
        **extra,
    )


class TestFiniquitoExentosDelAnio:
    """UMA desde el 1-feb-2026: $117.31. 30 UMA = 3,519.30; 15 UMA = 1,759.65."""

    def _por_clave(self, r):
        return {x.clave: x for x in r.conceptos if x.clave in ("002", "021")}

    def test_resta_aguinaldo_y_prima_ya_exentos(self):
        base = self._por_clave(calcular_finiquito(_sep()))
        assert base["002"].exento == D("3519.30") and base["021"].exento == D("1759.65")
        r = calcular_finiquito(
            _sep(aguinaldo_exento_previo=D("3000"), prima_vacacional_exenta_previa=D("1759.65"))
        )
        c = self._por_clave(r)
        assert c["002"].exento == D("519.30")
        assert c["002"].gravado == c["002"].importe - D("519.30")
        assert (c["021"].exento, c["021"].gravado) == (D("0"), c["021"].importe)
        assert any("Exentos ya aplicados en 2026" in n for n in r.notas)

    def test_la_ruta_toma_el_historial_del_anio_y_no_el_de_otro_despacho(self, api):
        def finiquito(c):
            r = c.post(
                "/api/v1/nomina/clientes/p6/finiquito",
                json={"empleado_no": "A-1", "fecha_baja": "2026-08-31", "causa": "renuncia",
                      "guardar": False},
            ).json()
            return {p["clave"]: p for p in r["resultado"]["conceptos"]}

        a = api("uid-p607-fa")
        sembrar_cliente(a, "p6", [_emp("A-1", "1000.00", "1050.00", fecha_alta="2020-01-01")])
        # Una quincena de agosto con 30 días de vacaciones: prima 7,500, exenta 1,759.65.
        a.post(
            CALC,
            json={
                "cliente": "p6",
                "periodo": {"inicio": "2026-08-01", "fin": "2026-08-15"},
                "incidencias": [_inc("A-1", 15)],
                "variables": [{"empleado_no": "A-1", "dias_vacaciones": 30}],
            },
        )
        assert D(finiquito(a)["021"]["exento"]) == D("0")

        b = api("uid-p607-fb")
        sembrar_cliente(b, "p6", [_emp("A-1", "1000.00", "1050.00", fecha_alta="2020-01-01")])
        assert D(finiquito(b)["021"]["exento"]) == D("1759.65")

    def test_la_captura_fuera_del_historial_se_suma(self, api):
        c = api("uid-p607-fc")
        sembrar_cliente(c, "p6", [_emp("A-1", "1000.00", "1050.00", fecha_alta="2020-01-01")])
        r = c.post(
            "/api/v1/nomina/clientes/p6/finiquito",
            json={"empleado_no": "A-1", "fecha_baja": "2026-08-31", "causa": "renuncia",
                  "guardar": False, "aguinaldo_exento_previo": "3000"},
        ).json()
        agui = next(p for p in r["resultado"]["conceptos"] if p["clave"] == "002")
        assert D(agui["exento"]) == D("519.30")


# ── 6. Archivos partidos ──


class TestArchivosPartidos:
    @pytest.mark.parametrize(
        "ruta",
        [
            "impuestos/personas_morales.py",
            "impuestos/pm_fuentes.py",
            "impuestos/servicio.py",
            "impuestos/isn_cliente.py",
            "schemas/cartera.py",
            "schemas/cartera_respuestas.py",
        ],
    )
    def test_300_lineas_o_menos(self, ruta):
        assert len((APP / ruta).read_text().splitlines()) <= 300

    def test_los_nombres_siguen_importables(self):
        from app.impuestos import personas_morales as pm
        from app.impuestos.isn_cliente import isn_del_cliente, percepciones_de_nomina
        from app.schemas.cartera_respuestas import EmpleadosCarteraResponse

        assert pm.CREDITOS_DEFAULT and pm.boveda_flujo and pm.saldos_aai
        assert callable(isn_del_cliente) and callable(percepciones_de_nomina)
        assert "empleados" in EmpleadosCarteraResponse.model_fields
