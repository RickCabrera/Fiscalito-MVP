"""
Tests de las tarifas del ISR por periodicidad.

LA AUTORIDAD DE ESTE MODULO SON LOS LITERALES DE ESTE ARCHIVO.
`tablas_isr_periodicas.py` genera las tarifas periodicas de la mensual con la
regla del Anexo 8; estos literales son los valores PUBLICADOS, y son los que
hacen legitima esa generacion. Si algun dia dejan de coincidir, lo que se
cambia es la generacion, no el literal.

Fuente de los literales: Anexo 8 de la RMF 2026, DOF 28-12-2025.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.exceptions import FiscalValidationError
from app.fiscal_engine.tablas_isr import TABLA_ISR_MENSUAL
from app.nomina_engine.tablas_isr_periodicas import (
    TARIFA_DIARIA_2026,
    TARIFA_MENSUAL_2026,
    TARIFA_QUINCENAL_2026,
    TARIFA_SEMANAL_2026,
    isr_periodo,
    tarifa_por_periodicidad,
)

# (limite_inferior, limite_superior, cuota_fija) publicados. La tasa sobre
# excedente no cambia con la periodicidad, por eso no se repite.
PUBLICADA_DIARIA = [
    ("0.01", "27.78", "0.00"),
    ("27.79", "235.81", "0.53"),
    ("235.82", "414.41", "13.85"),
    ("414.42", "481.73", "33.28"),
    ("481.74", "576.76", "44.05"),
    ("576.77", "1163.25", "61.08"),
    ("1163.26", "1833.44", "186.35"),
    ("1833.45", "3500.35", "343.98"),
    ("3500.36", "4667.13", "844.05"),
    ("4667.14", "14001.38", "1217.42"),
    ("14001.39", None, "4391.07"),
]

PUBLICADA_SEMANAL = [
    ("0.01", "194.46", "0.00"),
    ("194.47", "1650.67", "3.71"),
    ("1650.68", "2900.87", "96.95"),
    ("2900.88", "3372.11", "232.96"),
    ("3372.12", "4037.32", "308.35"),
    ("4037.33", "8142.75", "427.56"),
    ("8142.76", "12834.08", "1304.45"),
    ("12834.09", "24502.45", "2407.86"),
    ("24502.46", "32669.91", "5908.35"),
    ("32669.92", "98009.66", "8521.94"),
    ("98009.67", None, "30737.49"),
]

PUBLICADA_QUINCENAL = [
    ("0.01", "416.70", "0.00"),
    ("416.71", "3537.15", "7.95"),
    ("3537.16", "6216.15", "207.75"),
    ("6216.16", "7225.95", "499.20"),
    ("7225.96", "8651.40", "660.75"),
    ("8651.41", "17448.75", "916.20"),
    ("17448.76", "27501.60", "2795.25"),
    ("27501.61", "52505.25", "5159.70"),
    ("52505.26", "70006.95", "12660.75"),
    ("70006.96", "210020.70", "18261.30"),
    ("210020.71", None, "65866.05"),
]


def _comparar(generada, publicada):
    assert len(generada) == len(publicada)
    for i, (renglon, (li, ls, cf)) in enumerate(zip(generada, publicada)):
        assert renglon.limite_inferior == Decimal(li), f"límite inferior renglón {i + 1}"
        if ls is None:
            assert renglon.limite_superior.is_infinite(), f"último renglón {i + 1}"
        else:
            assert renglon.limite_superior == Decimal(ls), f"límite superior renglón {i + 1}"
        assert renglon.cuota_fija == Decimal(cf), f"cuota fija renglón {i + 1}"


class TestTarifasContraValoresPublicados:
    """Cada tarifa entregada se compara renglón por renglón con la publicada."""

    def test_diaria(self):
        _comparar(TARIFA_DIARIA_2026, PUBLICADA_DIARIA)

    def test_semanal(self):
        _comparar(TARIFA_SEMANAL_2026, PUBLICADA_SEMANAL)

    def test_quincenal(self):
        _comparar(TARIFA_QUINCENAL_2026, PUBLICADA_QUINCENAL)

    def test_mensual_coincide_con_la_del_motor_fiscal(self):
        """
        La mensual está en dos lugares (float en fiscal_engine, Decimal aquí).
        Este test es lo que impide que se separen sin que nadie se entere.
        """
        assert len(TARIFA_MENSUAL_2026) == len(TABLA_ISR_MENSUAL)
        for renglon, (li, ls, cf, tasa) in zip(TARIFA_MENSUAL_2026, TABLA_ISR_MENSUAL):
            assert renglon.limite_inferior == Decimal(str(li))
            if renglon.limite_superior.is_infinite():
                assert ls == float("inf")
            else:
                assert renglon.limite_superior == Decimal(str(ls))
            assert renglon.cuota_fija == Decimal(str(cf))
            assert renglon.tasa_excedente == Decimal(str(tasa))


class TestReglaDeConstruccion:
    """El orden del redondeo y el origen del límite inferior no son negociables."""

    def test_el_redondeo_va_a_la_diaria_no_al_final(self):
        """
        Segundo renglón quincenal: $3,537.15 publicado.
        `mensual x 15 / 30.4` daría $3,537.09 — 6 centavos abajo.
        """
        assert TARIFA_QUINCENAL_2026[1].limite_superior == Decimal("3537.15")
        camino_ingenuo = (Decimal("7168.51") * 15 / Decimal("30.4")).quantize(Decimal("0.01"))
        assert camino_ingenuo == Decimal("3537.09")

    def test_el_limite_inferior_sale_del_superior_anterior(self):
        """
        $416.71 publicado. Derivarlo del límite inferior mensual ($844.60)
        daría $416.70, que es el límite SUPERIOR del renglón anterior.
        """
        assert TARIFA_QUINCENAL_2026[1].limite_inferior == Decimal("416.71")
        assert TARIFA_QUINCENAL_2026[0].limite_superior == Decimal("416.70")

    @pytest.mark.parametrize(
        "tarifa",
        [TARIFA_DIARIA_2026, TARIFA_SEMANAL_2026, TARIFA_QUINCENAL_2026, TARIFA_MENSUAL_2026],
    )
    def test_continuidad_de_los_renglones(self, tarifa):
        assert tarifa[0].limite_inferior == Decimal("0.01")
        for anterior, siguiente in zip(tarifa, tarifa[1:]):
            assert siguiente.limite_inferior == anterior.limite_superior + Decimal("0.01")
        assert tarifa[-1].limite_superior.is_infinite()

    @pytest.mark.parametrize(
        "tarifa",
        [TARIFA_DIARIA_2026, TARIFA_SEMANAL_2026, TARIFA_QUINCENAL_2026],
    )
    def test_las_tasas_no_cambian_con_la_periodicidad(self, tarifa):
        for periodica, mensual in zip(tarifa, TARIFA_MENSUAL_2026):
            assert periodica.tasa_excedente == mensual.tasa_excedente


class TestSelectorDeTarifa:
    def test_claves_soportadas(self):
        for clave in ("01", "02", "04", "05"):
            assert tarifa_por_periodicidad(clave, date(2026, 6, 1))

    def test_catorcenal_no_tiene_tarifa_publicada(self):
        with pytest.raises(FiscalValidationError) as exc:
            tarifa_por_periodicidad("03", date(2026, 6, 1))
        assert "catorcenal" in str(exc.value)

    def test_decenal_no_se_entrega_sin_verificar(self):
        with pytest.raises(FiscalValidationError) as exc:
            tarifa_por_periodicidad("10", date(2026, 6, 1))
        assert "decenal" in str(exc.value)

    @pytest.mark.parametrize("clave", ["06", "07", "08", "09", "99"])
    def test_claves_que_no_son_periodos(self, clave):
        with pytest.raises(FiscalValidationError):
            tarifa_por_periodicidad(clave, date(2026, 6, 1))

    def test_clave_desconocida(self):
        with pytest.raises(FiscalValidationError):
            tarifa_por_periodicidad("77", date(2026, 6, 1))

    def test_ejercicio_sin_tarifas(self):
        with pytest.raises(FiscalValidationError) as exc:
            tarifa_por_periodicidad("02", date(2027, 6, 1))
        assert "2026" in str(exc.value)

    def test_enero_usa_la_tarifa_del_ejercicio_no_la_del_anterior(self):
        """
        La tarifa del Anexo 8 rige por ejercicio calendario, a diferencia de la
        UMA, que en enero todavía es la del año anterior.
        """
        assert tarifa_por_periodicidad("05", date(2026, 1, 5)) is TARIFA_MENSUAL_2026


class TestISRPeriodo:
    def test_base_cero(self):
        assert isr_periodo(Decimal("0"), "05", date(2026, 6, 1)) == Decimal("0.00")

    def test_primer_renglon_mensual(self):
        """
        $500 mensuales: cuota fija $0.00 + (500 - 0.01) x 1.92% = $9.60.

        Esperado literal a propósito: recalcular la fórmula en el test la
        verifica contra sí misma y no puede atrapar una fórmula equivocada.
        """
        assert isr_periodo(Decimal("500"), "05", date(2026, 6, 1)) == Decimal("9.60")

    def test_borde_superior_de_renglon(self):
        """En el límite superior exacto todavía manda ese renglón: $16.22."""
        assert isr_periodo(Decimal("844.59"), "05", date(2026, 6, 1)) == Decimal("16.22")

    def test_quincenal_literal(self):
        """$10,000 quincenales: renglón 6, $916.20 + (10000 - 8651.41) x 21.36%."""
        assert isr_periodo(Decimal("10000"), "04", date(2026, 6, 1)) == Decimal("1204.26")

    def test_primer_peso_del_renglon_siguiente(self):
        resultado = isr_periodo(Decimal("844.60"), "05", date(2026, 6, 1))
        assert resultado == Decimal("16.22")  # cuota fija, excedente cero

    def test_semanal_de_un_salario_tipico(self):
        """$2,000 semanales: renglón 3, $96.95 + (2000 - 1650.68) x 10.88% = $134.96."""
        assert isr_periodo(Decimal("2000"), "02", date(2026, 6, 1)) == Decimal("134.96")

    def test_ultimo_renglon_abierto(self):
        assert isr_periodo(Decimal("900000"), "05", date(2026, 6, 1)) > Decimal("0")

    def test_base_negativa(self):
        with pytest.raises(FiscalValidationError):
            isr_periodo(Decimal("-1"), "05", date(2026, 6, 1))
