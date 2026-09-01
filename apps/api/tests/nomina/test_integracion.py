"""
Tests del factor de integracion y del SBC.

El criterio de cierre de F1-02 es la tabla de factores minimos de ley de
`docs/PLAN_NOMINA.md` §2.2, que aqui se prueba renglon por renglon. Esa tabla
NO esta en el codigo a proposito: el motor calcula el factor desde las
prestaciones, y la tabla existe solo para verificar el caso "minimo de ley".
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import ZonaSalarioMinimo
from app.exceptions import FiscalValidationError
from app.nomina_engine.integracion import (
    ConceptoIntegrable,
    clamp_sbc,
    dias_vacaciones_de_ley,
    factor_integracion,
    factor_integracion_de_ley,
    sbc_fijo,
    sbc_mixto,
    sbc_variable,
)
from app.nomina_engine.tablas_imss import ceav_patronal

FEBRERO = date(2026, 2, 15)
ENERO = date(2026, 1, 15)

# (años de servicio, días de vacaciones, factor) — PLAN_NOMINA §2.2, con
# aguinaldo de 15 días y prima vacacional del 25%.
TABLA_FACTORES_DE_LEY = [
    (1, 12, "1.0493"),
    (2, 14, "1.0507"),
    (3, 16, "1.0521"),
    (4, 18, "1.0534"),
    (5, 20, "1.0548"),
    (6, 22, "1.0562"),
    (11, 24, "1.0575"),
    (16, 26, "1.0589"),
    (21, 28, "1.0603"),
    (26, 30, "1.0616"),
    (31, 32, "1.0630"),
]


class TestTablaDeFactoresMinimosDeLey:
    """El 'Listo cuando' de F1-02, literal."""

    @pytest.mark.parametrize("anios,dias,factor", TABLA_FACTORES_DE_LEY)
    def test_factor_por_antiguedad(self, anios, dias, factor):
        assert dias_vacaciones_de_ley(anios) == dias
        assert factor_integracion_de_ley(anios) == Decimal(factor)

    @pytest.mark.parametrize("anios,dias,factor", TABLA_FACTORES_DE_LEY)
    def test_el_factor_se_calcula_desde_las_prestaciones(self, anios, dias, factor):
        assert factor_integracion(15, dias, Decimal("0.25")) == Decimal(factor)


class TestEscalaDeVacaciones:
    """Art. 76 LFT, escala vigente desde el 1-ene-2023."""

    def test_alta_nueva_con_cero_anios_cumplidos(self):
        """
        El alta nueva integra con los 12 días que va a devengar. Rechazar el 0
        haría imposible calcular el SBC de un alta — justo el caso que tiene 5
        días hábiles para presentar el aviso.
        """
        assert dias_vacaciones_de_ley(0) == 12
        assert factor_integracion_de_ley(0) == Decimal("1.0493")

    @pytest.mark.parametrize(
        "anios,dias", [(7, 22), (10, 22), (12, 24), (15, 24), (20, 26), (30, 30), (35, 32)]
    )
    def test_dentro_de_cada_quinquenio(self, anios, dias):
        assert dias_vacaciones_de_ley(anios) == dias

    @pytest.mark.parametrize("anios,dias", [(36, 34), (40, 34), (41, 36)])
    def test_la_escala_no_termina_en_35(self, anios, dias):
        """
        El Art. 76 es una regla, no una tabla cerrada: 'aumentará en dos días
        por cada cinco de servicios'. Un trabajador de 37 años existe.
        """
        assert dias_vacaciones_de_ley(anios) == dias

    def test_antiguedad_negativa(self):
        with pytest.raises(FiscalValidationError):
            dias_vacaciones_de_ley(-1)


class TestPrestacionesSuperioresALaLey:
    def test_treinta_dias_de_aguinaldo(self):
        assert factor_integracion(30, 12, Decimal("0.25")) > factor_integracion_de_ley(1)

    def test_prima_vacacional_del_cincuenta_por_ciento(self):
        assert factor_integracion(15, 12, Decimal("0.50")) > factor_integracion_de_ley(1)

    def test_valor_exacto_de_un_paquete_superior(self):
        """30 aguinaldo + 20 vacaciones + 50% prima = 1 + 30/365 + 10/365."""
        assert factor_integracion(30, 20, Decimal("0.50")) == Decimal("1.1096")


class TestValidacionesDelFactor:
    def test_prima_como_porcentaje_en_vez_de_proporcion(self):
        """
        Pasar 25 en vez de 0.25 daría un factor de 1.86 y un SBC 77% inflado
        que ninguna tabla de referencia detecta. Es el error más fácil de
        cometer en esta API.
        """
        with pytest.raises(FiscalValidationError) as exc:
            factor_integracion(15, 12, Decimal("25"))
        assert "0.25" in str(exc.value)

    def test_prima_por_debajo_del_minimo_de_ley(self):
        with pytest.raises(FiscalValidationError):
            factor_integracion(15, 12, Decimal("0.20"))

    def test_aguinaldo_por_debajo_del_minimo_de_ley(self):
        """Art. 87 LFT. Un aguinaldo menor subintegraría el SBC y las cuotas."""
        with pytest.raises(FiscalValidationError):
            factor_integracion(10, 12, Decimal("0.25"))

    def test_vacaciones_negativas(self):
        with pytest.raises(FiscalValidationError):
            factor_integracion(15, -1, Decimal("0.25"))


class TestSBCFijo:
    def test_salario_por_factor(self):
        assert sbc_fijo(Decimal("500"), Decimal("1.0493")) == Decimal("524.65")

    def test_concepto_integrable_suma(self):
        vales = ConceptoIntegrable("Excedente de despensa", Decimal("10"), True)
        assert sbc_fijo(Decimal("500"), Decimal("1.0493"), (vales,)) == Decimal("534.65")

    def test_concepto_no_integrable_no_suma(self):
        herramienta = ConceptoIntegrable("Herramientas de trabajo", Decimal("50"), False)
        assert sbc_fijo(Decimal("500"), Decimal("1.0493"), (herramienta,)) == Decimal("524.65")

    def test_solo_el_excedente_integra(self):
        """
        `monto_diario` es la porción que integra, ya calculada: la despensa
        integra solo por encima del 40% de la UMA. Pasar la despensa completa
        sobreintegra el SBC.
        """
        despensa_total = Decimal("60")
        exento = Decimal("46.92")  # 40% de la UMA 2026
        excedente = ConceptoIntegrable("Despensa", despensa_total - exento, True)
        assert sbc_fijo(Decimal("500"), Decimal("1.0493"), (excedente,)) == Decimal("537.73")

    def test_salario_negativo(self):
        with pytest.raises(FiscalValidationError):
            sbc_fijo(Decimal("-1"), Decimal("1.0493"))


class TestSBCVariableYMixto:
    def test_promedio_del_bimestre(self):
        """Art. 30 fr. II: total de variables entre días devengados."""
        assert sbc_variable(Decimal("6000"), 60) == Decimal("100.00")

    def test_sin_dias_devengados(self):
        with pytest.raises(FiscalValidationError) as exc:
            sbc_variable(Decimal("6000"), 0)
        assert "estima" in str(exc.value)

    def test_variables_negativas(self):
        with pytest.raises(FiscalValidationError):
            sbc_variable(Decimal("-1"), 60)

    def test_mixto_suma_las_dos_partes(self):
        esperado = sbc_fijo(Decimal("500"), Decimal("1.0493")) + sbc_variable(
            Decimal("6000"), 60
        )
        assert sbc_mixto(Decimal("500"), Decimal("1.0493"), Decimal("6000"), 60) == esperado


class TestClampDelArticulo28:
    def test_por_debajo_del_piso_sube_al_salario_minimo(self):
        resultado = clamp_sbc(Decimal("200"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert resultado.valor == Decimal("315.04")
        assert resultado.piso_aplicado is True
        assert resultado.tope_aplicado is False

    def test_por_encima_del_tope_baja_a_25_uma(self):
        resultado = clamp_sbc(Decimal("5000"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert resultado.valor == Decimal("2932.75")
        assert resultado.tope_aplicado is True

    def test_dentro_del_rango_no_se_toca(self):
        resultado = clamp_sbc(Decimal("800"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert resultado.valor == Decimal("800")
        assert resultado.piso_aplicado is False
        assert resultado.tope_aplicado is False

    def test_el_piso_depende_de_la_zona(self):
        """$400 está sobre el piso general y bajo el de la ZLFN."""
        general = clamp_sbc(Decimal("400"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        zlfn = clamp_sbc(Decimal("400"), FEBRERO, ZonaSalarioMinimo.ZLFN)
        assert general.piso_aplicado is False
        assert zlfn.piso_aplicado is True
        assert zlfn.valor == Decimal("440.87")

    def test_en_enero_el_tope_usa_la_uma_vieja_y_el_piso_el_minimo_nuevo(self):
        """
        Las dos vigencias cruzadas: el salario mínimo cambió el 1 de enero, la
        UMA no cambia hasta el 1 de febrero.
        """
        resultado = clamp_sbc(Decimal("800"), ENERO, ZonaSalarioMinimo.GENERAL)
        assert resultado.piso == Decimal("315.04")  # SM 2026
        assert resultado.tope == Decimal("2828.50")  # 25 x UMA 2025

    def test_sbc_negativo(self):
        with pytest.raises(FiscalValidationError):
            clamp_sbc(Decimal("-1"), FEBRERO, ZonaSalarioMinimo.GENERAL)

    @pytest.mark.parametrize(
        "sbc_crudo",
        [
            sbc_fijo(Decimal("100"), Decimal("1.0493")),
            sbc_variable(Decimal("600"), 60),
            sbc_mixto(Decimal("100"), Decimal("1.0493"), Decimal("600"), 60),
        ],
    )
    def test_el_clamp_aplica_a_los_tres_tipos(self, sbc_crudo):
        assert clamp_sbc(sbc_crudo, FEBRERO, ZonaSalarioMinimo.GENERAL).piso_aplicado is True


class TestCosturaConCuotas:
    def test_un_sbc_acotado_al_piso_es_aceptado_por_ceav(self):
        """
        `ceav_patronal` levanta si el SBC está bajo el piso, a propósito. Este
        es el camino por el que un SBC llega a ser exactamente 1 salario
        mínimo, y por tanto el único por el que el renglón de 3.150% de la
        tabla de CEAV es alcanzable (ver D4).
        """
        acotado = clamp_sbc(Decimal("200"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert acotado.piso_aplicado is True
        assert ceav_patronal(acotado.valor, FEBRERO, ZonaSalarioMinimo.GENERAL) == Decimal(
            "0.03150"
        )

    def test_un_sbc_sin_acotar_revienta_en_cuotas(self):
        """Lo que justifica que el docstring de `sbc_*` grite que no acotan."""
        crudo = sbc_fijo(Decimal("100"), Decimal("1.0493"))
        with pytest.raises(FiscalValidationError):
            ceav_patronal(crudo, FEBRERO, ZonaSalarioMinimo.GENERAL)
