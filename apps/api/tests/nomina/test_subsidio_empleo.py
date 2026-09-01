"""
Tests del subsidio para el empleo.

Los importes esperados NO se copian de ninguna fuente secundaria: se derivan de
la regla del articulado del Decreto DOF 31-12-2025 (porcentaje x UMA mensual
vigente), que es lo unico que el decreto fija. Ver
knowledge_base/nomina/20_valores_referencia_2026.md §4 para por que el $536.22
que circula en secundarias no se usa.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine.subsidio import (
    porcentaje_subsidio_vigente,
    subsidio_empleo,
    subsidio_mensual,
    tope_ingreso_subsidio,
)

INGRESO_BAJO = Decimal("8000")


class TestSubsidioMensual:
    def test_febrero_a_diciembre(self):
        """15.02% x UMA mensual 2026 ($3,566.22) = $535.65."""
        assert subsidio_mensual(date(2026, 6, 15)) == Decimal("535.65")

    def test_enero_usa_el_transitorio_y_la_uma_2025(self):
        """15.59% x UMA mensual 2025 ($3,439.46) = $536.21."""
        assert subsidio_mensual(date(2026, 1, 15)) == Decimal("536.21")

    def test_enero_y_el_resto_del_año_no_son_iguales(self):
        assert subsidio_mensual(date(2026, 1, 15)) != subsidio_mensual(date(2026, 2, 1))

    def test_no_es_el_536_22_de_los_considerandos(self):
        """
        El articulado fija el porcentaje, no el peso. $536.22 aparece solo en
        los considerandos del decreto y no reconcilia con 15.02% x $3,566.22.
        """
        assert subsidio_mensual(date(2026, 6, 15)) != Decimal("536.22")

    def test_porcentaje_de_enero(self):
        assert porcentaje_subsidio_vigente(date(2026, 1, 31)) == Decimal("0.1559")

    def test_porcentaje_del_resto(self):
        assert porcentaje_subsidio_vigente(date(2026, 2, 1)) == Decimal("0.1502")

    def test_ejercicio_sin_decreto_cargado(self):
        with pytest.raises(FiscalValidationError):
            subsidio_mensual(date(2027, 6, 1))


class TestTopeDeIngresos:
    def test_valor_del_tope(self):
        assert tope_ingreso_subsidio(date(2026, 6, 1)) == Decimal("11492.66")

    def test_en_el_tope_exacto_si_hay_subsidio(self):
        assert subsidio_empleo(date(2026, 6, 1), Decimal("11492.66")) == Decimal("535.65")

    def test_un_centavo_arriba_no_hay_subsidio(self):
        """Corte duro: no se degrada, se apaga."""
        assert subsidio_empleo(date(2026, 6, 1), Decimal("11492.67")) == Decimal("0.00")

    def test_ingreso_negativo(self):
        with pytest.raises(FiscalValidationError):
            subsidio_empleo(date(2026, 6, 1), Decimal("-1"))


class TestProrrateo:
    def test_mes_completo(self):
        assert subsidio_empleo(date(2026, 6, 1), INGRESO_BAJO, 30) == Decimal("535.65")

    def test_semanal_febrero_a_diciembre(self):
        """535.65 / 30.4 x 7."""
        assert subsidio_empleo(date(2026, 6, 1), INGRESO_BAJO, 7) == Decimal("123.34")

    def test_semanal_enero(self):
        """536.21 / 30.4 x 7. Enero difiere del resto del año también aquí."""
        assert subsidio_empleo(date(2026, 1, 12), INGRESO_BAJO, 7) == Decimal("123.47")

    def test_quincenal(self):
        assert subsidio_empleo(date(2026, 6, 1), INGRESO_BAJO, 15) == Decimal("264.30")

    def test_un_periodo_mas_largo_que_el_mes_no_infla_el_subsidio(self):
        assert subsidio_empleo(date(2026, 6, 1), INGRESO_BAJO, 31) == Decimal("535.65")

    def test_dias_no_positivos(self):
        with pytest.raises(FiscalValidationError):
            subsidio_empleo(date(2026, 6, 1), INGRESO_BAJO, 0)
