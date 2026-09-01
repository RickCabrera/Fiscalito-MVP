"""
Tests del cálculo de cuotas obrero-patronales.

Ninguna tasa se teclea aquí: las esperadas se derivan de `tablas_imss`, que es
la única fuente con fundamento. Lo que sí se fija con literales es la
aritmética completa de casos concretos y el orden del redondeo.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import ZonaSalarioMinimo, uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.ceav import CEAV_OBRERO
from app.nomina_engine.cuotas import (
    DiasDelPeriodo,
    consolidado_bimestral,
    consolidado_mensual,
    cuotas_empleado,
)
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.tablas_imss import (
    BaseCuota,
    PeriodicidadCuota,
    cuotas_ramos_vigentes,
)
from app.redondeo import redondear

MARZO = date(2026, 3, 8)
ENERO = date(2026, 1, 15)
GENERAL = ZonaSalarioMinimo.GENERAL
PRIMA_RT = Decimal("0.0054355")  # prima media clase I
SBC_TIPICO = Decimal("331.58")  # del caso real, por debajo de 3 UMA


def _cuotas(sbc_valor, dias=None, fecha=MARZO, zona=GENERAL, prima=PRIMA_RT):
    sbc = clamp_sbc(Decimal(sbc_valor), fecha, zona)
    return cuotas_empleado(sbc, dias or DiasDelPeriodo(7), fecha, zona, prima)


def _ramo(resultado, clave):
    return next(r for r in resultado.ramos if r.clave == clave)


def _tasa_obrera_de_ley(fecha=MARZO) -> Decimal:
    """Suma de las tasas obreras sobre SBC. Derivada de la tabla, no tecleada."""
    return sum(
        (r.obrero for r in cuotas_ramos_vigentes(fecha) if r.base is BaseCuota.SBC),
        start=Decimal("0"),
    ) + CEAV_OBRERO[fecha.year]  # CEAV obrera, que vive fuera de la tabla escalar


class TestBasesPorRamo:
    def test_la_cuota_fija_de_eym_va_sobre_uma_no_sobre_sbc(self):
        """Art. 106 fr. I. El error clásico da un número plausible y mal."""
        resultado = _cuotas(SBC_TIPICO)
        cuota_fija = _ramo(resultado, "eym_cuota_fija")
        assert cuota_fija.base_diaria == uma_vigente(MARZO)
        assert cuota_fija.base_diaria != SBC_TIPICO

    def test_el_excedente_de_eym_no_existe_bajo_3_uma(self):
        """3 UMA = $351.93 en marzo de 2026."""
        excedente = _ramo(_cuotas("340.00"), "eym_excedente")
        assert excedente.base_diaria == Decimal("0")
        assert excedente.patron == Decimal("0.00")
        assert excedente.obrero == Decimal("0.00")

    def test_el_excedente_se_calcula_solo_sobre_la_porcion(self):
        """SBC $400: la base es 400 − 3×117.31 = $48.07, no $400."""
        excedente = _ramo(_cuotas("400.00"), "eym_excedente")
        assert excedente.base_diaria == Decimal("400.00") - 3 * uma_vigente(MARZO)
        assert excedente.base_diaria == Decimal("48.07")

    def test_el_umbral_del_excedente_se_mueve_con_la_uma(self):
        """
        En enero rige la UMA 2025, así que 3 UMA son $339.42 y un SBC de $345
        sí paga excedente; en marzo, con 3 UMA = $351.93, no paga.
        """
        assert _ramo(_cuotas("345.00", fecha=ENERO), "eym_excedente").base_diaria > 0
        assert _ramo(_cuotas("345.00", fecha=MARZO), "eym_excedente").base_diaria == 0

    def test_la_cuota_fija_de_enero_usa_la_uma_2025(self):
        assert _ramo(_cuotas("400.00", fecha=ENERO), "eym_cuota_fija").base_diaria == Decimal(
            "113.14"
        )

    @pytest.mark.parametrize(
        "clave", ["eym_prestaciones_dinero", "invalidez_vida", "retiro", "infonavit"]
    )
    def test_los_demas_ramos_van_sobre_el_sbc(self, clave):
        assert _ramo(_cuotas(SBC_TIPICO), clave).base_diaria == SBC_TIPICO


class TestAritmeticaPorRamo:
    def test_infonavit_5_por_ciento(self):
        """Art. 29 fr. II Ley del Infonavit: $331.58 × 5% × 7 = $116.05."""
        infonavit = _ramo(_cuotas(SBC_TIPICO), "infonavit")
        assert infonavit.patron == Decimal("116.05")
        assert infonavit.obrero == Decimal("0.00")

    def test_retiro_2_por_ciento(self):
        assert _ramo(_cuotas(SBC_TIPICO), "retiro").patron == Decimal("46.42")

    def test_cuota_fija_eym(self):
        """20.40% × UMA × 7 = 0.2040 × 117.31 × 7 = $167.52."""
        assert _ramo(_cuotas(SBC_TIPICO), "eym_cuota_fija").patron == Decimal("167.52")

    def test_invalidez_y_vida_reparte_entre_patron_y_obrero(self):
        iyv = _ramo(_cuotas(SBC_TIPICO), "invalidez_vida")
        assert iyv.patron == Decimal("40.62")
        assert iyv.obrero == Decimal("14.51")

    def test_riesgos_de_trabajo_usa_la_prima_inyectada(self):
        rt = _ramo(_cuotas(SBC_TIPICO, prima=Decimal("0.025")), "riesgos_trabajo")
        assert rt.tasa_patron == Decimal("0.025")
        assert rt.patron == redondear(SBC_TIPICO * Decimal("0.025") * 7)
        assert rt.obrero == Decimal("0.00")

    def test_ceav_trae_la_tasa_de_su_tramo(self):
        """Sin la tasa del tramo, el renglón no es conciliable contra la EMA."""
        ceav = _ramo(_cuotas("400.00"), "ceav")
        assert ceav.tasa_patron == Decimal("0.06361")  # tramo 3.01–3.50 UMA
        assert ceav.tasa_obrero == Decimal("0.01125")


class TestDiasYAusentismo:
    def test_los_dias_reducen_las_cuotas(self):
        siete = _cuotas(SBC_TIPICO, DiasDelPeriodo(7))
        catorce = _cuotas(SBC_TIPICO, DiasDelPeriodo(14))
        assert catorce.total_patron > siete.total_patron

    def test_el_ausentismo_no_reduce_enfermedades_y_maternidad(self):
        """
        Art. 31 LSS, decisión D3 (PROVISIONAL): con 3 días de ausencia el
        trabajador cotiza 27 días en los demás ramos y 30 en EyM. Un motor con
        un solo contador de días subcobra EyM en silencio.
        """
        resultado = _cuotas(SBC_TIPICO, DiasDelPeriodo(30, dias_ausentismo=3))
        assert _ramo(resultado, "eym_cuota_fija").dias == 30
        assert _ramo(resultado, "eym_prestaciones_dinero").dias == 30
        assert _ramo(resultado, "invalidez_vida").dias == 27
        assert _ramo(resultado, "retiro").dias == 27
        assert _ramo(resultado, "riesgos_trabajo").dias == 27

    def test_la_incapacidad_tambien_deja_eym_completo(self):
        resultado = _cuotas(SBC_TIPICO, DiasDelPeriodo(30, dias_incapacidad=5))
        assert _ramo(resultado, "eym_cuota_fija").dias == 30
        assert _ramo(resultado, "ceav").dias == 25

    def test_una_ausencia_mayor_a_siete_dias_sigue_cobrando_eym(self):
        """
        LÍMITE CONOCIDO. D3 habla de ausencias **de hasta 7 días**; la fr. II
        del Art. 31 libera al patrón de todas las cuotas cuando la ausencia
        excede ese plazo (con la baja del Art. 37). Eso NO está implementado:
        con 20 días de ausencia el motor sigue cobrando 30 días de EyM.

        La dirección del error es la conservadora —cobra de más, no de menos—
        así que se deja fijada aquí en vez de adivinar. Ver `docs/decisiones-
        nomina.md` §D3.
        """
        resultado = _cuotas(SBC_TIPICO, DiasDelPeriodo(30, dias_ausentismo=20))
        assert _ramo(resultado, "eym_cuota_fija").dias == 30
        assert _ramo(resultado, "invalidez_vida").dias == 10

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"dias_periodo": 0},
            {"dias_periodo": 32},
            {"dias_periodo": 30, "dias_ausentismo": -1},
            {"dias_periodo": 7, "dias_ausentismo": 5, "dias_incapacidad": 5},
        ],
    )
    def test_dias_invalidos(self, kwargs):
        with pytest.raises(FiscalValidationError):
            DiasDelPeriodo(**kwargs)


class TestArticulo36:
    """El patrón absorbe la cuota obrera del trabajador de salario mínimo."""

    def test_el_salario_minimo_dispara_la_absorcion(self):
        resultado = _cuotas("315.04")  # SM general 2026 exacto
        assert resultado.absorbio_cuota_obrera is True
        assert resultado.total_obrero == Decimal("0.00")

    def test_un_sbc_acotado_al_piso_tambien_absorbe(self):
        """El clamp del Art. 28 es el camino práctico a este supuesto."""
        assert _cuotas("200.00").absorbio_cuota_obrera is True

    def test_no_es_una_exencion_la_cuota_se_sigue_calculando(self):
        """
        Solo cambia quién paga: el desglose conserva el importe obrero de cada
        ramo, que es lo que permite conciliar contra la EMA renglón por renglón.
        """
        resultado = _cuotas("315.04")
        iyv = _ramo(resultado, "invalidez_vida")
        assert iyv.obrero > Decimal("0")
        assert resultado.total_patron >= sum(r.obrero for r in resultado.ramos)

    def test_el_total_no_cambia_solo_el_reparto(self):
        absorbido = _cuotas("315.04")
        suma_desglose = sum(r.patron + r.obrero for r in absorbido.ramos)
        assert absorbido.total == suma_desglose

    def test_absorbe_tambien_la_obrera_del_excedente_de_eym(self):
        """
        El 0.40% del Art. 106 fr. II es la línea que se olvida al absorber.

        El caso NO es hipotético: en la Zona Libre de la Frontera Norte el
        salario mínimo ($440.87) está **por encima** de 3 UMA ($351.93), así
        que un trabajador de salario mínimo de frontera causa excedente de EyM
        y absorción del Art. 36 al mismo tiempo. Es población real.
        """
        resultado = _cuotas(
            "440.87", fecha=MARZO, zona=ZonaSalarioMinimo.ZLFN
        )
        assert resultado.absorbio_cuota_obrera is True
        excedente = _ramo(resultado, "eym_excedente")
        assert excedente.obrero > Decimal("0")
        assert excedente.obrero == Decimal("2.49")
        assert resultado.total_obrero == Decimal("0.00")
        assert resultado.total_patron >= excedente.obrero

    @pytest.mark.parametrize("sbc", ["315.04", "331.58"])
    def test_invariante_total(self, sbc):
        resultado = _cuotas(sbc)
        assert resultado.total == resultado.total_patron + resultado.total_obrero


class TestRedondeo:
    def test_se_redondea_por_concepto_y_despues_se_suma(self):
        """
        D2. El orden es load-bearing: con SBC $331.58 y 7 días, redondear cada
        ramo y sumar da $55.12 de cuota obrera, mientras redondear la suma da
        $55.13. El caso real de S-04 muestra los dos órdenes conviviendo (D14).
        """
        resultado = _cuotas(SBC_TIPICO)
        assert resultado.total_obrero == Decimal("55.12")
        agregado = redondear(SBC_TIPICO * 7 * _tasa_obrera_de_ley())
        assert agregado == Decimal("55.13")

    def test_el_consolidado_no_re_redondea(self):
        """D2: el redondeo ya ocurrió por concepto; volver a redondear cambiaría el pago."""
        empleados = (_cuotas(SBC_TIPICO), _cuotas("399.52"))
        mensual = consolidado_mensual(empleados)
        esperado = sum(
            r.patron + r.obrero
            for e in empleados
            for r in e.ramos
            if r.periodicidad is PeriodicidadCuota.MENSUAL
        )
        assert mensual.total == esperado


class TestConsolidados:
    def test_cada_ramo_cae_en_exactamente_un_consolidado(self):
        """Lo que atrapa un ramo nuevo en 2027 que nadie clasificó."""
        resultado = _cuotas(SBC_TIPICO)
        mensuales = {r.clave for r in resultado.ramos
                     if r.periodicidad is PeriodicidadCuota.MENSUAL}
        bimestrales = {r.clave for r in resultado.ramos
                       if r.periodicidad is PeriodicidadCuota.BIMESTRAL}
        assert mensuales & bimestrales == set()
        assert mensuales | bimestrales == {r.clave for r in resultado.ramos}

    def test_el_bimestral_es_rcv_mas_infonavit(self):
        """Art. 39 LSS."""
        bimestral = consolidado_bimestral((_cuotas(SBC_TIPICO),))
        assert set(bimestral.por_ramo) == {"retiro", "ceav", "infonavit"}

    def test_infonavit_queda_en_su_propia_clave(self):
        """No es una cuota del IMSS: la emisión llega separada y así se concilia."""
        bimestral = consolidado_bimestral((_cuotas(SBC_TIPICO),))
        assert bimestral.por_ramo["infonavit"] == Decimal("116.05")

    def test_el_mensual_no_incluye_rcv_ni_infonavit(self):
        mensual = consolidado_mensual((_cuotas(SBC_TIPICO),))
        assert "retiro" not in mensual.por_ramo
        assert "infonavit" not in mensual.por_ramo
        assert "riesgos_trabajo" in mensual.por_ramo

    def test_suma_varios_empleados(self):
        uno = _cuotas(SBC_TIPICO)
        consolidado = consolidado_mensual((uno, uno, uno))
        assert consolidado.empleados == 3
        assert consolidado.total == 3 * consolidado_mensual((uno,)).total


class TestGuardaDeCoherencia:
    def test_un_sbc_acotado_con_otra_fecha_no_se_acepta(self):
        """
        Un `SBCAcotado` de enero tiene el tope de la UMA 2025. Usarlo para
        cotizar marzo produciría un número plausible y equivocado.
        """
        sbc_de_enero = clamp_sbc(Decimal("400"), ENERO, GENERAL)
        with pytest.raises(FiscalValidationError) as exc:
            cuotas_empleado(sbc_de_enero, DiasDelPeriodo(7), MARZO, GENERAL, PRIMA_RT)
        assert "clamp_sbc" in str(exc.value)

    def test_un_sbc_acotado_con_otra_zona_no_se_acepta(self):
        sbc_zlfn = clamp_sbc(Decimal("600"), MARZO, ZonaSalarioMinimo.ZLFN)
        with pytest.raises(FiscalValidationError):
            cuotas_empleado(sbc_zlfn, DiasDelPeriodo(7), MARZO, GENERAL, PRIMA_RT)
