"""
Tests de exenciones del Art. 93 y de la retención de ISR.

Los topes se prueban con importes **por encima** del límite: una exención con
tope de 1 UMA y otra de 30 UMA se comportan igual mientras el importe sea
pequeño, así que un test con importes bajos no distingue un tope de otro.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.isr_nomina import (
    ContextoExencion,
    Percepcion,
    base_gravable,
    exentar,
    isr_retenido,
)

MARZO = date(2026, 3, 8)
ENERO = date(2026, 1, 15)
UMA_2026 = Decimal("117.31")
UMA_2025 = Decimal("113.14")


def _ctx(fecha=MARZO, **kwargs):
    return ContextoExencion(fecha=fecha, **kwargs)


def _p(clave, importe, descripcion="x"):
    return Percepcion(clave, descripcion, Decimal(importe))


class TestTopesEnUMA:
    def test_aguinaldo_exento_hasta_30_uma(self):
        """30 × $117.31 = $3,519.30."""
        resultado = exentar(_p("002", "5000.00"), _ctx())
        assert resultado.exento == Decimal("3519.30")
        assert resultado.gravado == Decimal("1480.70")
        assert "fr. XIV" in resultado.fundamento

    def test_aguinaldo_por_debajo_del_tope_va_todo_exento(self):
        resultado = exentar(_p("002", "2000.00"), _ctx())
        assert resultado.exento == Decimal("2000.00")
        assert resultado.gravado == Decimal("0.00")

    def test_prima_vacacional_exenta_hasta_15_uma(self):
        resultado = exentar(_p("021", "3000.00"), _ctx())
        assert resultado.exento == Decimal("1759.65")

    def test_ptu_exenta_hasta_15_uma(self):
        resultado = exentar(_p("003", "3000.00"), _ctx())
        assert resultado.exento == Decimal("1759.65")

    def test_los_topes_no_son_intercambiables(self):
        """
        Con un importe grande, aguinaldo (30 UMA) y prima vacacional (15 UMA)
        se separan. Con importes chicos darían lo mismo y el test no probaría
        nada.
        """
        grande = "5000.00"
        assert exentar(_p("002", grande), _ctx()).exento != exentar(
            _p("021", grande), _ctx()
        ).exento

    def test_la_uma_de_enero_es_la_del_año_anterior(self):
        """
        Vigencia: en enero rige la UMA 2025, así que la misma percepción exenta
        distinto. Las fixtures de S-04 son de marzo a mayo y no pueden probarlo.
        """
        assert exentar(_p("002", "5000.00"), _ctx(ENERO)).exento == Decimal("3394.20")
        assert Decimal("3394.20") == UMA_2025 * 30


class TestPrimaDominical:
    def test_un_domingo_exenta_hasta_una_uma(self):
        resultado = exentar(_p("020", "200.00"), _ctx(domingos_trabajados=1))
        assert resultado.exento == UMA_2026
        assert resultado.gravado == Decimal("82.69")

    def test_el_tope_escala_con_los_domingos(self):
        resultado = exentar(_p("020", "500.00"), _ctx(domingos_trabajados=4))
        assert resultado.exento == redondear_uma(4)

    def test_por_debajo_del_tope_va_todo_exento(self):
        resultado = exentar(_p("020", "79.00"), _ctx())
        assert resultado.exento == Decimal("79.00")
        assert resultado.gravado == Decimal("0.00")


def redondear_uma(veces: int) -> Decimal:
    return (UMA_2026 * veces).quantize(Decimal("0.01"))


class TestHorasExtra:
    def test_los_demas_trabajadores_exentan_la_mitad(self):
        resultado = exentar(_p("019", "400.00"), _ctx())
        assert resultado.exento == Decimal("200.00")
        assert resultado.gravado == Decimal("200.00")

    def test_con_tope_de_cinco_uma_por_semana(self):
        """5 × $117.31 = $586.55: la mitad de $2,000 excede el tope."""
        resultado = exentar(_p("019", "2000.00"), _ctx())
        assert resultado.exento == Decimal("586.55")
        assert resultado.gravado == Decimal("1413.45")

    def test_el_tope_escala_con_las_semanas_del_periodo(self):
        resultado = exentar(
            _p("019", "2000.00"), _ctx(semanas_del_periodo=Decimal("2"))
        )
        assert resultado.exento == Decimal("1000.00")  # la mitad, bajo el tope de 10 UMA

    def test_el_trabajador_de_salario_minimo_exenta_todo(self):
        """Art. 93 fr. I, primera rama: 100 % dentro de los límites de la LFT."""
        resultado = exentar(
            _p("019", "2000.00"), _ctx(es_trabajador_de_salario_minimo=True)
        )
        assert resultado.exento == Decimal("2000.00")
        assert resultado.gravado == Decimal("0.00")
        assert "salario mínimo" in resultado.fundamento


class TestPercepcionesSinExencion:
    def test_el_sueldo_va_100_por_ciento_gravado(self):
        resultado = exentar(_p("001", "2212.00"), _ctx())
        assert resultado.gravado == Decimal("2212.00")
        assert resultado.exento == Decimal("0.00")

    @pytest.mark.parametrize(
        "clave",
        [
            "005",  # fondo de ahorro — previsión social, fr. VIII y IX
            "029",  # vales de despensa — previsión social
            "023",  # pagos por separación — fr. XIII
            "014",  # subsidios por incapacidad — fr. III
            "022",  # prima de antigüedad — fr. XIII
            "015",  # becas para trabajadores y/o hijos — previsión social
            "999",  # una clave que ni siquiera existe en el catálogo
        ],
    )
    def test_toda_clave_no_clasificada_levanta_error(self, clave):
        """
        LISTA BLANCA: solo las claves que se sabe que NO tienen exención se
        gravan al 100 %. Cualquier otra levanta.

        Enumerar las exenciones no implementadas una por una dejaría fuera las
        que se olviden, y esas se gravarían en silencio. Y aquí el silencio es
        el error peligroso: gravar de más es conservador **para el fisco**, no
        para el trabajador, que es a quien se le retiene de más.
        """
        with pytest.raises(FiscalValidationError) as exc:
            exentar(_p(clave, "1000.00"), _ctx())
        assert "no está clasificada" in str(exc.value)

    @pytest.mark.parametrize("clave", ["001", "010", "038", "049"])
    def test_las_claves_de_la_lista_blanca_se_gravan(self, clave):
        assert exentar(_p(clave, "500.00"), _ctx()).gravado == Decimal("500.00")

    def test_importe_negativo(self):
        with pytest.raises(FiscalValidationError):
            exentar(_p("001", "-1"), _ctx())


class TestBaseGravable:
    def test_suma_solo_lo_gravado(self):
        percepciones = (_p("001", "2212.00"), _p("020", "79.00"))
        desglose, base = base_gravable(percepciones, _ctx())
        assert base == Decimal("2212.00")
        assert desglose[1].exento == Decimal("79.00")

    def test_una_percepcion_parcialmente_exenta_aporta_su_gravado(self):
        desglose, base = base_gravable((_p("002", "5000.00"),), _ctx())
        assert base == Decimal("1480.70")


class TestRetencion:
    def test_el_subsidio_reduce_el_isr(self):
        """Gravado $2,212 semanales: causado $158.02 − subsidio $123.34."""
        resultado = isr_retenido(
            Decimal("2212.00"), "02", MARZO, Decimal("10080.03"), 7
        )
        assert resultado.causado == Decimal("158.02")
        assert resultado.subsidio == Decimal("123.34")
        assert resultado.retenido == Decimal("34.68")

    def test_el_subsidio_no_genera_saldo_a_favor(self):
        """
        Desde 2024 el remanente no se entrega en efectivo: el retenido llega a
        cero y el sobrante se reporta aparte, no como negativo.
        """
        resultado = isr_retenido(Decimal("300.00"), "02", MARZO, Decimal("5000.00"), 7)
        assert resultado.retenido == Decimal("0.00")
        assert resultado.subsidio_no_entregado > Decimal("0")
        assert resultado.causado < resultado.subsidio

    def test_sobre_el_tope_no_hay_subsidio(self):
        resultado = isr_retenido(
            Decimal("2576.35"), "02", MARZO, Decimal("12145.41"), 7
        )
        assert resultado.subsidio == Decimal("0.00")
        assert resultado.retenido == resultado.causado

    def test_al_trabajador_de_salario_minimo_no_se_le_retiene(self):
        """
        Art. 96, último párrafo. Es una norma distinta de la exención del
        Art. 93 fr. I y de la absorción del Art. 36 LSS: las tres coinciden en
        el mismo empleado y se aplican por separado.
        """
        resultado = isr_retenido(
            Decimal("2212.00"),
            "02",
            MARZO,
            Decimal("10080.03"),
            7,
            es_trabajador_de_salario_minimo=True,
        )
        assert resultado.retenido == Decimal("0.00")
        assert resultado.sin_retencion_por_salario_minimo is True
        assert resultado.causado > Decimal("0")  # causarse, se causa

    def test_enero_usa_el_subsidio_transitorio(self):
        enero = isr_retenido(Decimal("2212.00"), "02", ENERO, Decimal("10080.03"), 7)
        marzo = isr_retenido(Decimal("2212.00"), "02", MARZO, Decimal("10080.03"), 7)
        assert enero.subsidio == Decimal("123.47")
        assert marzo.subsidio == Decimal("123.34")

    def test_base_negativa(self):
        with pytest.raises(FiscalValidationError):
            isr_retenido(Decimal("-1"), "02", MARZO, Decimal("5000.00"), 7)

    @pytest.mark.parametrize("salario_minimo", [False, True])
    @pytest.mark.parametrize(
        "base,mensual",
        [
            ("2212.00", "10080.03"),  # subsidio parcial
            ("300.00", "5000.00"),  # el subsidio supera al causado
            ("2576.35", "12145.41"),  # sobre el tope, sin subsidio
        ],
    )
    def test_el_invariante_se_cumple_en_las_dos_ramas(
        self, base, mensual, salario_minimo
    ):
        """
        Las dos reglas, que NO son la misma en las dos ramas.

        `subsidio == acreditado + no_entregado` se cumple siempre. En cambio
        `retenido == causado − acreditado` vale solo cuando hay retención: si
        el Art. 96 último párrafo la suprime, el retenido es cero **aunque el
        ISR se haya causado**, porque la no retención no es un acreditamiento.

        Sin `acreditado` explícito esto pasaba en silencio: el subsidio se
        contaba como acreditado contra un ISR que nunca se retuvo, y el
        consumidor —F1-05, que va a emitir `SubsidioCausado` y el importe
        entregado al CFDI— no podía detectarlo.
        """
        resultado = isr_retenido(
            Decimal(base),
            "02",
            MARZO,
            Decimal(mensual),
            7,
            es_trabajador_de_salario_minimo=salario_minimo,
        )
        assert resultado.invariante

    def test_sin_retencion_el_subsidio_queda_integro_sin_entregar(self):
        """
        DECISIÓN PROVISIONAL (nocturno), ver `docs/decisiones-nomina.md` §D16:
        al trabajador de salario mínimo el subsidio no se acredita (no hay ISR
        retenido contra el cual hacerlo) y tampoco se entrega en efectivo.
        """
        resultado = isr_retenido(
            Decimal("2212.00"),
            "02",
            MARZO,
            Decimal("10080.03"),
            7,
            es_trabajador_de_salario_minimo=True,
        )
        assert resultado.causado == Decimal("158.02")  # se causa
        assert resultado.retenido == Decimal("0.00")  # no se retiene
        assert resultado.acreditado == Decimal("0.00")  # no se acredita
        assert resultado.subsidio == Decimal("123.34")
        assert resultado.subsidio_no_entregado == Decimal("123.34")

    def test_sobre_el_tope_no_hay_subsidio_que_acreditar(self):
        """Ancla numérica de la rama sin subsidio."""
        resultado = isr_retenido(
            Decimal("2576.35"), "02", MARZO, Decimal("12145.41"), 7
        )
        assert resultado.causado == Decimal("197.66")
        assert resultado.subsidio == Decimal("0.00")
        assert resultado.acreditado == Decimal("0.00")
        assert resultado.retenido == Decimal("197.66")
        assert resultado.subsidio_no_entregado == Decimal("0.00")


def test_la_uma_vigente_es_la_esperada():
    """Ancla de los literales de este archivo."""
    assert uma_vigente(MARZO) == UMA_2026
    assert uma_vigente(ENERO) == UMA_2025
