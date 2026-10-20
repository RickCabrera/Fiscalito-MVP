"""
Motor de nómina completa (P4-03 a P4-08): casos con resultado conocido.

Los esperados son LITERALES calculados a mano con la ley y la tarifa publicada, no
llamando al motor. Tarifa mensual 2026 (Anexo 8): renglón 3 = 7,168.52 / 420.95 /
10.88 %, renglón 4 = 12,598.03 / 1,011.68 / 16 %, renglón 5 = 14,644.65 / 1,339.14 /
17.92 %. UMA 2026 = 117.31. Tarifa anual Art. 152, renglón 5 = 175,735.67 /
16,069.64 / 17.92 %.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine.aguinaldo import aguinaldo_proporcional, calcular_aguinaldo
from app.nomina_engine.ajuste_anual import DatosAnuales, ajuste_anual
from app.nomina_engine.criterios import CriteriosNomina, criterios_de, prestacion_efectiva
from app.nomina_engine.finiquito import (
    DatosSeparacion,
    anios_para_exencion,
    calcular_finiquito,
    procede_prima_antiguedad,
)
from app.nomina_engine.isr_extraordinario import isr_art_96, isr_art_174, isr_separacion
from app.nomina_engine.ptu import TrabajadorPTU, repartir_ptu
from app.nomina_engine.tablas_isr_periodicas import (
    TARIFA_CATORCENAL_2026,
    TARIFA_DECENAL_2026,
    TARIFA_DIARIA_2026,
)

PAGO = date(2026, 12, 15)


class TestTarifaDecenal:
    """Anexo 8 RMF 2026, rubro B, "pagos que correspondan a un periodo de 10 días"."""

    PUBLICADA = [
        ("0.01", "277.80", "0.00", "0.0192"),
        ("277.81", "2358.10", "5.30", "0.0640"),
        ("2358.11", "4144.10", "138.50", "0.1088"),
        ("4144.11", "4817.30", "332.80", "0.16"),
        ("4817.31", "5767.60", "440.50", "0.1792"),
        ("5767.61", "11632.50", "610.80", "0.2136"),
        ("11632.51", "18334.40", "1863.50", "0.2352"),
        ("18334.41", "35003.50", "3439.80", "0.30"),
        ("35003.51", "46671.30", "8440.50", "0.32"),
        ("46671.31", "140013.80", "12174.20", "0.34"),
        ("140013.81", "Infinity", "43910.70", "0.35"),
    ]

    def test_reproduce_la_publicada_al_centavo(self):
        for renglon, (li, ls, cuota, tasa) in zip(TARIFA_DECENAL_2026, self.PUBLICADA):
            assert (renglon.limite_inferior, renglon.limite_superior) == (D(li), D(ls))
            assert (renglon.cuota_fija, renglon.tasa_excedente) == (D(cuota), D(tasa))


class TestTarifaCatorcenalDerivada:
    def test_es_la_diaria_por_14(self):
        """§D10: diaria del Anexo 8 × 14, con el límite inferior = superior anterior + 0.01."""
        for dia, cat in zip(TARIFA_DIARIA_2026[:-1], TARIFA_CATORCENAL_2026[:-1]):
            assert cat.limite_superior == dia.limite_superior * 14
            assert cat.cuota_fija == dia.cuota_fija * 14
        assert TARIFA_CATORCENAL_2026[1].limite_inferior == D("388.93")  # 27.78 × 14 + 0.01


class TestISRExtraordinario:
    def test_art_96_suma_al_mes(self):
        """Ordinario 12,160 (400 × 30.4) + gravado 2,480.70: ISR 1,338.51 − 964.02."""
        assert isr_art_96(D("2480.70"), D("12160.00"), PAGO).isr == D("374.49")

    def test_art_174_rlisr(self):
        """2,480.70 ÷ 365 × 30.4 = 206.61; ISR(12,366.61) − ISR(12,160) = 22.48; tasa × gravado."""
        r = isr_art_174(D("2480.70"), D("12160.00"), PAGO)
        assert r.isr == D("269.91")
        assert r.metodo == "art_174"

    def test_separacion_con_la_tasa_del_ultimo_sueldo(self):
        """USMO 15,000: ISR 1,402.82 → tasa 9.352 %; × 50,000 = 4,676.07 (Arts. 95 y 96)."""
        assert isr_separacion(D("50000"), D("15000"), PAGO).isr == D("4676.07")

    def test_separacion_menor_al_ultimo_sueldo_va_por_el_96(self):
        r = isr_separacion(D("5000"), D("15000"), PAGO, D("0"))
        assert r.metodo == "art_96"


class TestAguinaldo:
    def test_proporcional_por_dias(self):
        """Alta 1-jul: 184 días. 400 × 15 × 184 / 365 = 3,024.66 (Art. 87 LFT)."""
        assert aguinaldo_proporcional(D("400"), 15, 184) == D("3024.66")

    def test_exencion_de_30_uma_y_su_isr(self):
        r = calcular_aguinaldo(D("400"), 15, 365, PAGO, D("12160.00"))
        assert (r.importe, r.exento, r.gravado) == (D("6000.00"), D("3519.30"), D("2480.70"))
        assert r.isr.isr == D("374.49")
        assert r.neto == D("5625.51")

    def test_la_opcion_174_cambia_el_isr(self):
        r = calcular_aguinaldo(D("400"), 15, 365, PAGO, D("12160.00"), "art_174")
        assert r.isr.isr == D("269.91")

    def test_el_exento_ya_aplicado_reduce_la_exencion(self):
        r = calcular_aguinaldo(D("400"), 15, 365, PAGO, D("12160.00"), exento_ya_aplicado=D("3000"))
        assert r.exento == D("519.30")

    def test_menos_de_15_dias_se_rechaza(self):
        with pytest.raises(FiscalValidationError, match="Art. 87"):
            aguinaldo_proporcional(D("400"), 10, 365)


class TestFiniquito:
    """
    Alta 1-ene-2020, baja 30-jun-2026 (2,373 días = 6.5014 años), salario 500, SDI 525,
    despido injustificado, 22 días de vacaciones al año, prima 25 %, pagado en baja.
    """

    def _datos(self, causa="despido_injustificado", incluir_20_dias=True):
        return DatosSeparacion(
            fecha_alta=date(2020, 1, 1),
            fecha_baja=date(2026, 6, 30),
            salario_diario=D("500"),
            salario_diario_integrado=D("525"),
            causa=causa,
            dias_vacaciones_anio=22,
            incluir_20_dias=incluir_20_dias,
        )

    def test_los_20_dias_no_entran_por_default_y_se_avisa(self):
        """O4: proceden sólo si el patrón no reinstala (Art. 49) o el trabajador rescinde (52)."""
        d = DatosSeparacion(
            date(2020, 1, 1),
            date(2026, 6, 30),
            D("500"),
            D("525"),
            "despido_injustificado",
            dias_vacaciones_anio=22,
        )
        r = calcular_finiquito(d)
        assert not any("20 DÍAS" in c.concepto for c in r.conceptos)
        assert any("Art. 49" in n and "Art. 52" in n for n in r.notas)

    def test_lo_ordinario_se_apila_sobre_el_ingreso_del_mes(self):
        """
        B5: con ingreso ordinario 15,200 (500 × 30.4), el ISR de lo ordinario gravado
        (5,654.67) es ISR(20,854.67) − ISR(15,200) = 2,566.21 − 1,438.66.
        """
        r = calcular_finiquito(self._datos(), D("15200.00"))
        assert r.isr_ordinario == D("1127.55")

    def test_liquidacion_cuadra_al_centavo(self):
        r = calcular_finiquito(self._datos())
        por = {c.concepto: c for c in r.conceptos}
        # Ordinarios
        assert por["AGUINALDO PROPORCIONAL"].importe == D("3719.18")  # 500×15×181/365
        assert por["AGUINALDO PROPORCIONAL"].gravado == D("199.88")
        assert por["VACACIONES PROPORCIONALES"].importe == D("5454.79")  # 500×22×181/365
        assert por["PRIMA VACACIONAL PROPORCIONAL"].importe == D("1363.70")
        assert por["PRIMA VACACIONAL PROPORCIONAL"].gravado == D("0.00")  # < 15 UMA
        # Separación (Art. 162: 12 días × años; Art. 50: 90 días y 20 días por año)
        assert por["PRIMA DE ANTIGÜEDAD"].importe == D("39008.22")
        assert por["INDEMNIZACIÓN 3 MESES"].importe == D("47250.00")
        assert por["INDEMNIZACIÓN 20 DÍAS POR AÑO"].importe == D("68264.38")
        # Exención 90 UMA × 7 años (6.5 → fracción > 6 meses = 7) = 73,905.30
        assert r.anios_para_exencion == 7
        exento_sep = sum(c.exento for c in r.conceptos if c.separacion)
        assert exento_sep == D("73905.30")
        # ISR: ordinario 5,654.67 → 324.06; separación 80,617.30 × 1,402.82/15,000
        assert r.isr_ordinario == D("324.06")
        assert r.isr_separacion == D("7539.44")
        assert r.total == D("165060.27")
        assert r.neto == r.total - D("324.06") - D("7539.44")

    def test_la_renuncia_con_menos_de_15_anios_no_lleva_prima_ni_indemnizacion(self):
        r = calcular_finiquito(self._datos("renuncia"))
        assert not any(c.separacion for c in r.conceptos)
        assert any("Art. 162" in n for n in r.notas)

    def test_prima_de_antiguedad_topada_a_2_salarios_minimos(self):
        d = DatosSeparacion(
            date(2016, 1, 1), date(2026, 6, 30), D("1500"), D("1600"), "despido_justificado"
        )
        prima = next(c for c in calcular_finiquito(d).conceptos if c.clave == "022")
        anios = D((date(2026, 6, 30) - date(2016, 1, 1)).days + 1) / 365
        assert prima.importe == (D("630.08") * 12 * anios).quantize(D("0.01"))  # 2 × 315.04

    def test_casos_de_prima_de_antiguedad(self):
        assert procede_prima_antiguedad("renuncia", D("15"))
        assert not procede_prima_antiguedad("renuncia", D("14.9"))
        assert procede_prima_antiguedad("muerte", D("0.1"))
        assert not procede_prima_antiguedad("termino_contrato", D("20"))

    def test_fraccion_de_mas_de_seis_meses(self):
        assert anios_para_exencion(date(2020, 1, 1), date(2026, 6, 1)) == 6
        assert anios_para_exencion(date(2020, 1, 1), date(2026, 7, 15)) == 7


class TestPTU:
    """
    Renta gravable 1,000,000 → 100,000 repartibles. A: 365 días, cuota 300, salarios
    109,500. B: 365 / 500 / 182,500. C: 180 / 400 / 72,000. Director y eventual de 50
    días no participan (Art. 127 fr. I y VIII).
    """

    TRAB = (
        TrabajadorPTU("A", 365, D("300"), D("109500")),
        TrabajadorPTU("B", 365, D("500"), D("182500")),
        TrabajadorPTU("C", 180, D("400"), D("72000")),
        TrabajadorPTU("D", 365, D("3000"), D("1095000"), tipo="director"),
        TrabajadorPTU("E", 50, D("300"), D("15000"), tipo="eventual"),
    )

    def test_reparto_con_tope(self):
        r = repartir_ptu(D("1000000"), self.TRAB, date(2026, 5, 29))
        por = {t.empleado_no: t for t in r.trabajadores}
        assert r.utilidad_repartible == D("100000.00")
        assert (por["A"].por_dias, por["A"].por_salarios) == (D("20054.95"), D("15041.21"))
        assert por["A"].ptu == D("27000.00")  # tope 90 días × 300
        assert por["B"].ptu == D("45000.00")  # tope 90 × 500
        assert por["C"].ptu == D("19780.22")  # no topa
        assert not por["D"].participa and not por["E"].participa
        assert r.remanente == D("8219.78")
        assert r.repartido + r.remanente == D("100000.00")

    def test_exencion_de_15_uma(self):
        c = next(
            t
            for t in repartir_ptu(D("1000000"), self.TRAB, date(2026, 5, 29)).trabajadores
            if t.empleado_no == "C"
        )
        assert c.exento == D("1759.65")
        assert c.gravado == D("18020.57")

    def test_redistribuir_el_remanente_reparte_todo(self):
        r = repartir_ptu(D("1000000"), self.TRAB, date(2026, 5, 29), remanente="redistribuir")
        por = {t.empleado_no: t.ptu for t in r.trabajadores}
        assert por["C"] == D("28000.00")
        assert r.repartido == D("100000.00")

    def test_el_promedio_de_3_anios_puede_subir_el_tope(self):
        trab = (
            TrabajadorPTU("A", 365, D("300"), D("109500"), promedio_ptu_3_anios=D("40000")),
            *self.TRAB[1:3],
        )
        a = repartir_ptu(D("1000000"), trab, date(2026, 5, 29)).trabajadores[0]
        assert a.tope == D("40000") and a.ptu == D("35096.16")


class TestAjusteAnual:
    BASE = dict(
        ejercicio=2026,
        fecha_alta=date(2020, 1, 1),
        fecha_baja=None,
        ingresos_gravados=D("180000"),
        ingresos_exentos=D("10000"),
        isr_retenido=D("15000"),
    )

    def test_saldo_a_cargo_cuadra_con_el_calculo_manual(self):
        """Art. 152: 16,069.64 + (180,000 − 175,735.67) × 17.92 % = 16,833.81."""
        r = ajuste_anual(DatosAnuales(**self.BASE))
        assert r.procede and r.impuesto_anual == D("16833.81")
        assert r.saldo_a_cargo == D("1833.81") and r.saldo_a_favor == D("0.00")

    def test_saldo_a_favor(self):
        r = ajuste_anual(DatosAnuales(**{**self.BASE, "isr_retenido": D("17000")}))
        assert r.saldo_a_favor == D("166.19")

    @pytest.mark.parametrize(
        "cambio, fraccion",
        [
            ({"fecha_alta": date(2026, 3, 1)}, "fr. I"),
            ({"fecha_baja": date(2026, 11, 15)}, "fr. I"),
            ({"ingresos_gravados": D("395000"), "ingresos_exentos": D("10000")}, "fr. II"),
            ({"comunico_que_declara": True}, "fr. III"),
        ],
    )
    def test_quienes_no(self, cambio, fraccion):
        r = ajuste_anual(DatosAnuales(**{**self.BASE, **cambio}))
        assert not r.procede and fraccion in r.motivo
        assert r.saldo_a_cargo == D("0.00")


class TestCriterios:
    def test_defaults_documentados(self):
        c = CriteriosNomina()
        assert (c.parcial, c.febrero, c.prestaciones) == (
            "tarifa_proporcional",
            "quince_siempre",
            "mayor",
        )

    def test_opcion_invalida(self):
        with pytest.raises(FiscalValidationError):
            criterios_de({"febrero": "trece"})

    def test_d28_mayor_contra_ficha(self):
        assert prestacion_efectiva(15, 30, "mayor") == 30
        assert prestacion_efectiva(20, 15, "mayor") == 20
        assert prestacion_efectiva(20, 15, "ficha") == 15
