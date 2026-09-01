"""
Tests de los valores por vigencia: UMA y salario minimo.

Lo que estos tests protegen no es "el valor de la UMA" sino la REGLA: la UMA
cambia el 1 de febrero y el salario minimo el 1 de enero. Un motor que
capture "la UMA" en una constante calcula mal todo enero.

Fuentes de los valores esperados (verificadas en F0-01, ver
knowledge_base/nomina/20_valores_referencia_2026.md):
- UMA 2025 y 2026: INEGI, Comunicados de prensa 1/25 y 1/26 (DOF 09-01-2025
  y 09-01-2026).
- Salario minimo 2025 y 2026: resoluciones CONASAMI (DOF 09-12-2024 y
  09-12-2025).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import (
    ZonaSalarioMinimo,
    salario_minimo_vigente,
    uma_anual_vigente,
    uma_mensual_vigente,
    uma_vigente,
)
from app.exceptions import FiscalValidationError


class TestCorteDeVigenciaUMA:
    """La UMA del año N rige del 1-feb-N al 31-ene-(N+1)."""

    def test_enero_2026_usa_la_uma_2025(self):
        assert uma_vigente(date(2026, 1, 15)) == Decimal("113.14")

    def test_ultimo_dia_de_enero_2026_sigue_en_uma_2025(self):
        assert uma_vigente(date(2026, 1, 31)) == Decimal("113.14")

    def test_primero_de_febrero_2026_estrena_uma_2026(self):
        assert uma_vigente(date(2026, 2, 1)) == Decimal("117.31")

    def test_diciembre_2026_sigue_en_uma_2026(self):
        assert uma_vigente(date(2026, 12, 31)) == Decimal("117.31")

    def test_enero_2027_sigue_en_uma_2026(self):
        """La vigencia se extiende al año siguiente: no es un caso de borde raro."""
        assert uma_vigente(date(2027, 1, 31)) == Decimal("117.31")

    def test_febrero_2027_ya_no_tiene_fuente_cargada(self):
        with pytest.raises(FiscalValidationError) as exc:
            uma_vigente(date(2027, 2, 1))
        assert "2025, 2026" in str(exc.value)

    def test_enero_2025_corresponde_a_la_uma_2024_no_cargada(self):
        with pytest.raises(FiscalValidationError):
            uma_vigente(date(2025, 1, 15))


class TestCorteDeVigenciaSalarioMinimo:
    """El salario minimo del año N rige del 1-ene-N al 31-dic-N."""

    def test_ultimo_dia_de_2025(self):
        valor = salario_minimo_vigente(date(2025, 12, 31), ZonaSalarioMinimo.GENERAL)
        assert valor == Decimal("278.80")

    def test_primero_de_enero_2026_ya_es_el_minimo_nuevo(self):
        valor = salario_minimo_vigente(date(2026, 1, 1), ZonaSalarioMinimo.GENERAL)
        assert valor == Decimal("315.04")

    def test_zona_libre_frontera_norte(self):
        valor = salario_minimo_vigente(date(2026, 6, 15), ZonaSalarioMinimo.ZLFN)
        assert valor == Decimal("440.87")

    def test_la_zona_cambia_el_resultado(self):
        general = salario_minimo_vigente(date(2026, 6, 15), ZonaSalarioMinimo.GENERAL)
        zlfn = salario_minimo_vigente(date(2026, 6, 15), ZonaSalarioMinimo.ZLFN)
        assert zlfn > general

    def test_anio_sin_fuente_cargada(self):
        with pytest.raises(FiscalValidationError) as exc:
            salario_minimo_vigente(date(2027, 1, 1), ZonaSalarioMinimo.GENERAL)
        assert "2025, 2026" in str(exc.value)

    def test_zona_invalida(self):
        with pytest.raises(FiscalValidationError):
            salario_minimo_vigente(date(2026, 6, 15), "frontera_sur")


class TestLasDosReglasNoCoinciden:
    """
    El corazon de F0-02: en enero de 2026 conviven la UMA 2025 y el SM 2026.

    Un motor que asuma "los valores del año en curso" para las dos magnitudes
    calcula mal el piso o el tope del SBC durante todo enero.
    """

    def test_enero_2026_mezcla_uma_vieja_con_salario_minimo_nuevo(self):
        fecha = date(2026, 1, 20)
        assert uma_vigente(fecha) == Decimal("113.14")  # UMA 2025
        assert salario_minimo_vigente(fecha, ZonaSalarioMinimo.GENERAL) == Decimal("315.04")

    def test_las_ventanas_de_validez_son_distintas(self):
        """Enero de 2027 tiene UMA pero ya no tiene salario minimo cargado."""
        assert uma_vigente(date(2027, 1, 15)) == Decimal("117.31")
        with pytest.raises(FiscalValidationError):
            salario_minimo_vigente(date(2027, 1, 15), ZonaSalarioMinimo.GENERAL)

    def test_tope_y_piso_del_sbc_en_enero_2026(self):
        """25 UMA con la UMA 2025, 1 SM con el minimo 2026 (Art. 28 LSS)."""
        fecha = date(2026, 1, 20)
        assert uma_vigente(fecha) * 25 == Decimal("2828.50")
        assert salario_minimo_vigente(fecha, ZonaSalarioMinimo.GENERAL) == Decimal("315.04")


class TestValoresDerivados:
    """
    Mensual y anual deben coincidir con lo que publica el INEGI.

    El orden del redondeo importa: la mensual se redondea a 2 decimales ANTES
    de multiplicar por 12. Redondear solo al final da $42,794.69 en 2026, que
    no es el valor publicado.
    """

    def test_uma_mensual_2026(self):
        assert uma_mensual_vigente(date(2026, 2, 1)) == Decimal("3566.22")

    def test_uma_anual_2026(self):
        assert uma_anual_vigente(date(2026, 2, 1)) == Decimal("42794.64")

    def test_uma_mensual_2025(self):
        assert uma_mensual_vigente(date(2025, 6, 1)) == Decimal("3439.46")

    def test_uma_anual_2025(self):
        assert uma_anual_vigente(date(2025, 6, 1)) == Decimal("41273.52")

    @pytest.mark.parametrize("fecha", [date(2025, 6, 1), date(2026, 6, 1)])
    def test_la_anual_es_doce_veces_la_mensual_redondeada(self, fecha):
        assert uma_anual_vigente(fecha) == uma_mensual_vigente(fecha) * 12

    def test_redondear_al_final_daria_otro_numero(self):
        """Deja documentado por que el orden del redondeo esta fijado."""
        sin_redondeo_intermedio = Decimal("117.31") * Decimal("30.4") * 12
        assert sin_redondeo_intermedio != uma_anual_vigente(date(2026, 2, 1))

    def test_enero_2026_deriva_de_la_uma_2025(self):
        assert uma_anual_vigente(date(2026, 1, 10)) == Decimal("41273.52")
