"""
Tests de días hábiles y de avisos de modificación de salario.

Dos reglas opuestas conviven en el repo y estos tests las mantienen separadas:
el pago de cuotas del día 17 SÍ se corre por caer en viernes (RACERF Art. 3,
F1-06), y la presentación de avisos afiliatorios NO.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine.avisos import (
    TipoAviso,
    TipoSalario,
    avisos_requeridos,
    cambio_de_sbc,
    fecha_limite_aviso_fijo,
    fecha_limite_aviso_variable,
)
from app.nomina_engine.dias_habiles import (
    descansos_obligatorios,
    es_habil,
    n_esimo_dia_habil_del_mes,
    sumar_dias_habiles,
)


class TestDescansosObligatorios:
    """Art. 74 LFT."""

    def test_los_siete_supuestos_incluidos_en_2026(self):
        assert descansos_obligatorios(2026) == {
            date(2026, 1, 1),  # fr. I
            date(2026, 2, 2),  # fr. II, primer lunes de febrero
            date(2026, 3, 16),  # fr. III, tercer lunes de marzo
            date(2026, 5, 1),  # fr. IV
            date(2026, 9, 16),  # fr. V
            date(2026, 11, 16),  # fr. VI, tercer lunes de noviembre
            date(2026, 12, 25),  # fr. VIII
        }

    def test_los_lunes_conmemorativos_se_mueven_con_el_año(self):
        assert date(2027, 2, 1) in descansos_obligatorios(2027)
        assert date(2027, 3, 15) in descansos_obligatorios(2027)

    def test_el_primero_de_octubre_no_es_inhabil(self):
        """
        Art. 74 fr. VII queda fuera hasta poder citar el DOF de su texto
        vigente. Contar de menos es lo conservador: marcar un día de más como
        inhábil corre el vencimiento hacia adelante, y un aviso extemporáneo
        cuesta de 20 a 350 UMA (Art. 304-B LSS).
        """
        assert date(2030, 10, 1) not in descansos_obligatorios(2030)

    def test_es_habil(self):
        assert es_habil(date(2026, 6, 10)) is True  # miércoles cualquiera
        assert es_habil(date(2026, 6, 13)) is False  # sábado
        assert es_habil(date(2026, 5, 1)) is False  # descanso obligatorio


class TestConteoDeDiasHabiles:
    def test_el_dia_de_partida_no_cuenta(self):
        assert sumar_dias_habiles(date(2026, 6, 8), 1) == date(2026, 6, 9)

    def test_salta_el_fin_de_semana(self):
        """Del jueves, 2 días hábiles caen en lunes."""
        assert sumar_dias_habiles(date(2026, 6, 11), 2) == date(2026, 6, 15)

    def test_salta_un_descanso_obligatorio(self):
        """Del lunes 27-abr, 5 días hábiles saltan el 1 de mayo y el fin de semana."""
        assert sumar_dias_habiles(date(2026, 4, 27), 5) == date(2026, 5, 5)

    def test_cero_dias(self):
        assert sumar_dias_habiles(date(2026, 6, 10), 0) == date(2026, 6, 10)

    def test_dias_negativos(self):
        with pytest.raises(ValueError):
            sumar_dias_habiles(date(2026, 6, 10), -1)

    def test_n_esimo_dia_habil_del_mes(self):
        assert n_esimo_dia_habil_del_mes(2026, 3, 5) == date(2026, 3, 6)
        assert n_esimo_dia_habil_del_mes(2026, 3, 1) == date(2026, 3, 2)

    def test_n_esimo_cuando_el_primero_del_mes_es_inhabil(self):
        """Mayo de 2026 arranca en viernes 1, que es descanso obligatorio."""
        assert n_esimo_dia_habil_del_mes(2026, 5, 1) == date(2026, 5, 4)
        assert n_esimo_dia_habil_del_mes(2026, 5, 5) == date(2026, 5, 8)

    def test_n_invalido(self):
        with pytest.raises(ValueError):
            n_esimo_dia_habil_del_mes(2026, 5, 0)


class TestFechaLimiteDelAviso:
    def test_cinco_dias_habiles_siguientes(self):
        assert fecha_limite_aviso_fijo(date(2026, 6, 8)) == date(2026, 6, 15)

    def test_el_vencimiento_NO_se_corre_por_caer_en_viernes(self):
        """
        RACERF Art. 3 prorroga los plazos que vencen en viernes o día inhábil,
        pero EXCLUYE la presentación de avisos afiliatorios. La regla contraria
        —la que sí corre el viernes— es la del pago de cuotas del día 17.
        """
        limite = fecha_limite_aviso_fijo(date(2026, 6, 5))
        assert limite == date(2026, 6, 12)
        assert limite.weekday() == 4  # viernes, y ahí se queda

    def test_bimestre_impar_siguiente(self):
        """El bimestre 1 (ene-feb) se avisa en los primeros 5 días hábiles de marzo."""
        assert fecha_limite_aviso_variable(1, 2026) == date(2026, 3, 6)

    def test_bimestre_2_se_avisa_en_mayo(self):
        assert fecha_limite_aviso_variable(2, 2026) == date(2026, 5, 8)

    def test_el_bimestre_6_se_avisa_en_enero_del_año_siguiente(self):
        assert fecha_limite_aviso_variable(6, 2026) == date(2027, 1, 8)

    @pytest.mark.parametrize("bimestre", [0, 7, -1])
    def test_bimestre_invalido(self, bimestre):
        with pytest.raises(FiscalValidationError):
            fecha_limite_aviso_variable(bimestre, 2026)


class TestCambioDeSBC:
    def test_detecta_el_cambio(self):
        assert cambio_de_sbc(Decimal("500.00"), Decimal("520.00")) is True

    def test_sin_cambio(self):
        assert cambio_de_sbc(Decimal("500.00"), Decimal("500.00")) is False

    def test_una_diferencia_de_subcentavo_no_dispara_aviso(self):
        """
        Sin el redondeo previo a 2 decimales, el arrastre del promedio de
        variables dispararía un aviso fantasma.
        """
        assert cambio_de_sbc(Decimal("500.001"), Decimal("500.004")) is False


class TestAvisosRequeridos:
    def test_fijo_con_cambio(self):
        (aviso,) = avisos_requeridos(
            TipoSalario.FIJO, Decimal("500"), Decimal("520"), date(2026, 6, 8)
        )
        assert aviso.requiere is True
        assert aviso.tipo is TipoAviso.MODIFICACION_FIJA
        assert aviso.fecha_limite == date(2026, 6, 15)
        assert "fr. I" in aviso.fundamento

    def test_fijo_sin_cambio_no_requiere_aviso(self):
        (aviso,) = avisos_requeridos(
            TipoSalario.FIJO, Decimal("500"), Decimal("500"), date(2026, 6, 8)
        )
        assert aviso.requiere is False
        assert aviso.fecha_limite is None

    def test_variable_requiere_aviso_aunque_el_sbc_no_cambie(self):
        """
        La obligación bimestral no depende del cambio: lo que se presenta es la
        determinación del bimestre (Art. 34 fr. II).
        """
        (aviso,) = avisos_requeridos(
            TipoSalario.VARIABLE,
            Decimal("500"),
            Decimal("500"),
            date(2026, 3, 1),
            bimestre_reportado=1,
        )
        assert aviso.requiere is True
        assert aviso.tipo is TipoAviso.BIMESTRAL_VARIABLE
        assert aviso.fecha_limite == date(2026, 3, 6)

    def test_variable_sin_bimestre_es_error(self):
        with pytest.raises(FiscalValidationError) as exc:
            avisos_requeridos(
                TipoSalario.VARIABLE, Decimal("500"), Decimal("520"), date(2026, 6, 8)
            )
        assert "bimestre_reportado" in str(exc.value)

    def test_mixto_genera_dos_avisos_con_vencimientos_distintos(self):
        """Art. 34 fr. III: la parte fija al cambiar, la variable bimestral."""
        avisos = avisos_requeridos(
            TipoSalario.MIXTO,
            Decimal("500"),
            Decimal("520"),
            date(2026, 6, 8),
            bimestre_reportado=2,
        )
        assert len(avisos) == 2
        fija, variable = avisos
        assert fija.tipo is TipoAviso.MODIFICACION_FIJA
        assert variable.tipo is TipoAviso.BIMESTRAL_VARIABLE
        assert fija.fecha_limite != variable.fecha_limite
        assert fija.fecha_limite == date(2026, 6, 15)
        assert variable.fecha_limite == date(2026, 5, 8)
