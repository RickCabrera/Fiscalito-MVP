"""
Tests del redondeo monetario.

Estos son los tests de la decision **D2** (`docs/decisiones-nomina.md`): por
concepto y por empleado, 2 decimales, al estilo SUA. El modo de redondeo solo
se distingue en los EMPATES exactos, asi que una suite sin empates pasa igual
con `ROUND_HALF_UP` que con el `ROUND_HALF_EVEN` que Python usa por defecto — y
el cuadre contra el caso real depende de cual sea.
"""

from decimal import ROUND_HALF_EVEN, Decimal

from app.redondeo import redondear


class TestRoundHalfUp:
    def test_empate_hacia_arriba_con_digito_par(self):
        """0.125: HALF_UP da 0.13; HALF_EVEN daria 0.12."""
        assert redondear(Decimal("0.125")) == Decimal("0.13")

    def test_empate_hacia_arriba_con_digito_impar(self):
        """0.135: los dos modos coinciden aqui, por eso no basta un solo caso."""
        assert redondear(Decimal("0.135")) == Decimal("0.14")

    def test_difiere_del_redondeo_por_defecto_de_python(self):
        """
        Deja fijado que el modo NO es el default. Si alguien quita el
        `rounding=` de `redondear()`, este test falla.
        """
        por_defecto = Decimal("0.125").quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        assert por_defecto == Decimal("0.12")
        assert redondear(Decimal("0.125")) != por_defecto

    def test_empate_en_montos_realistas(self):
        assert redondear(Decimal("1234.565")) == Decimal("1234.57")
        assert redondear(Decimal("1234.575")) == Decimal("1234.58")

    def test_sin_empate_no_hay_ambiguedad(self):
        assert redondear(Decimal("0.124")) == Decimal("0.12")
        assert redondear(Decimal("0.126")) == Decimal("0.13")

    def test_negativos(self):
        """HALF_UP redondea alejandose del cero."""
        assert redondear(Decimal("-0.125")) == Decimal("-0.13")

    def test_no_altera_lo_que_ya_tiene_dos_decimales(self):
        assert redondear(Decimal("535.65")) == Decimal("535.65")
