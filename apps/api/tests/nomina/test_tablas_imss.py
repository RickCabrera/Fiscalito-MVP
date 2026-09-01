"""
Tests de las tablas de cuotas IMSS e Infonavit.

Los porcentajes esperados son los de
knowledge_base/nomina/22_cuotas_imss_infonavit_2026.md, con su artículo de la
LSS. Lo que estos tests protegen, además de los números, son dos cosas
estructurales: que ningún ramo se pierda en silencio, y que la base de cada
ramo sea la correcta (la cuota fija de EyM va sobre UMA, no sobre SBC).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import ZonaSalarioMinimo
from app.exceptions import FiscalValidationError
from app.nomina_engine.tablas_imss import (
    CEAV_OBRERO,
    PRIMA_RT_MAXIMA,
    PRIMA_RT_MINIMA,
    BaseCuota,
    PeriodicidadCuota,
    ceav_patronal,
    cuotas_ramos_vigentes,
    prima_media_clase,
    ramo_ceav_patronal,
    ramo_riesgos_trabajo,
)

FEBRERO = date(2026, 2, 15)
ENERO = date(2026, 1, 15)
SM_GENERAL_2026 = Decimal("315.04")
SM_ZLFN_2026 = Decimal("440.87")

ESPERADOS = {
    "eym_cuota_fija": ("0.2040", "0", BaseCuota.UMA, PeriodicidadCuota.MENSUAL),
    "eym_excedente": ("0.0110", "0.0040", BaseCuota.EXCEDENTE_3_UMA, PeriodicidadCuota.MENSUAL),
    "eym_prestaciones_dinero": ("0.0070", "0.0025", BaseCuota.SBC, PeriodicidadCuota.MENSUAL),
    "eym_gastos_medicos_pensionados": (
        "0.0105", "0.00375", BaseCuota.SBC, PeriodicidadCuota.MENSUAL,
    ),
    "invalidez_vida": ("0.0175", "0.00625", BaseCuota.SBC, PeriodicidadCuota.MENSUAL),
    "guarderias": ("0.0100", "0", BaseCuota.SBC, PeriodicidadCuota.MENSUAL),
    "retiro": ("0.0200", "0", BaseCuota.SBC, PeriodicidadCuota.BIMESTRAL),
    "infonavit": ("0.0500", "0", BaseCuota.SBC, PeriodicidadCuota.BIMESTRAL),
}


class TestTablaDeRamos:
    def test_cubre_exactamente_los_ramos_de_tasa_de_ley(self):
        """
        Sin este test, un ramo omitido no rompe nada: solo desaparece de la
        cuota. RT y CEAV no están aquí a propósito — su tasa no es escalar.
        """
        claves = {r.clave for r in cuotas_ramos_vigentes(FEBRERO)}
        assert claves == set(ESPERADOS)

    @pytest.mark.parametrize("clave", sorted(ESPERADOS))
    def test_porcentaje_base_y_periodicidad_de_cada_ramo(self, clave):
        ramo = next(r for r in cuotas_ramos_vigentes(FEBRERO) if r.clave == clave)
        patron, obrero, base, periodicidad = ESPERADOS[clave]
        assert ramo.patron == Decimal(patron)
        assert ramo.obrero == Decimal(obrero)
        assert ramo.base is base
        assert ramo.periodicidad is periodicidad
        assert ramo.fundamento

    def test_ningun_ramo_tiene_tasa_nula(self):
        """Lo que impide que F1-03 multiplique por None o se salte un ramo."""
        for ramo in cuotas_ramos_vigentes(FEBRERO):
            assert isinstance(ramo.patron, Decimal)
            assert isinstance(ramo.obrero, Decimal)

    def test_la_cuota_fija_de_eym_va_sobre_uma(self):
        """El error clásico: calcularla sobre el SBC da un número plausible y mal."""
        ramo = next(r for r in cuotas_ramos_vigentes(FEBRERO) if r.clave == "eym_cuota_fija")
        assert ramo.base is BaseCuota.UMA

    def test_periodicidad_de_entero(self):
        """Art. 39 LSS: los ramos de seguro son mensuales; RCV e Infonavit, bimestrales."""
        por_periodicidad: dict[PeriodicidadCuota, set[str]] = {
            PeriodicidadCuota.MENSUAL: set(),
            PeriodicidadCuota.BIMESTRAL: set(),
        }
        for ramo in cuotas_ramos_vigentes(FEBRERO):
            por_periodicidad[ramo.periodicidad].add(ramo.clave)
        assert por_periodicidad[PeriodicidadCuota.BIMESTRAL] == {"retiro", "infonavit"}
        assert "guarderias" in por_periodicidad[PeriodicidadCuota.MENSUAL]

    def test_anio_sin_tabla(self):
        with pytest.raises(FiscalValidationError):
            cuotas_ramos_vigentes(date(2027, 6, 1))


class TestRiesgosDeTrabajo:
    def test_prima_valida(self):
        ramo = ramo_riesgos_trabajo(Decimal("0.025"), FEBRERO)
        assert ramo.patron == Decimal("0.025")
        assert ramo.obrero == Decimal("0")
        assert ramo.base is BaseCuota.SBC

    @pytest.mark.parametrize("prima", ["0.004", "0.1501"])
    def test_prima_fuera_del_rango_legal(self, prima):
        """Art. 72 LSS: 0.50000% a 15.00000%."""
        with pytest.raises(FiscalValidationError):
            ramo_riesgos_trabajo(Decimal(prima), FEBRERO)

    @pytest.mark.parametrize("prima", [PRIMA_RT_MINIMA, PRIMA_RT_MAXIMA])
    def test_los_extremos_del_rango_son_validos(self, prima):
        assert ramo_riesgos_trabajo(prima, FEBRERO).patron == prima

    def test_primas_medias_por_clase(self):
        """Art. 73 LSS, clases I a V."""
        assert prima_media_clase(1, FEBRERO) == Decimal("0.0054355")
        assert prima_media_clase(3, FEBRERO) == Decimal("0.0259840")
        assert prima_media_clase(5, FEBRERO) == Decimal("0.0758875")

    def test_clase_invalida(self):
        with pytest.raises(FiscalValidationError):
            prima_media_clase(6, FEBRERO)

    def test_toda_prima_media_cae_dentro_del_rango_legal(self):
        for clase in range(1, 6):
            assert PRIMA_RT_MINIMA <= prima_media_clase(clase, FEBRERO) <= PRIMA_RT_MAXIMA


class TestCEAVPatronal:
    def test_salario_minimo_exacto(self):
        assert ceav_patronal(SM_GENERAL_2026, FEBRERO, ZonaSalarioMinimo.GENERAL) == Decimal(
            "0.03150"
        )

    def test_la_discontinuidad_de_un_centavo(self):
        """
        Un centavo por encima del salario mínimo salta de 3.150% a 6.026%:
        $315.05 son 2.686 UMA, que caen en el tramo 2.51–3.00.

        Es el quirk aceptado en docs/decisiones-nomina.md D4 (PROVISIONAL), no
        un bug: los tramos "1.01 SM a 1.50 UMA", "1.51–2.00" y "2.01–2.50"
        quedan por debajo del salario mínimo y son inalcanzables en zona
        general. NO suavizar esto sin que la contadora confirme qué hace el SUA.
        """
        un_centavo_arriba = SM_GENERAL_2026 + Decimal("0.01")
        assert ceav_patronal(
            un_centavo_arriba, FEBRERO, ZonaSalarioMinimo.GENERAL
        ) == Decimal("0.06026")

    def test_tramo_intermedio(self):
        """SBC $400 en febrero: 3.41 UMA -> tramo 3.01-3.50 -> 6.361%."""
        assert ceav_patronal(Decimal("400"), FEBRERO, ZonaSalarioMinimo.GENERAL) == Decimal(
            "0.06361"
        )

    def test_tramo_superior_abierto(self):
        assert ceav_patronal(Decimal("2000"), FEBRERO, ZonaSalarioMinimo.GENERAL) == Decimal(
            "0.07513"
        )

    def test_el_mismo_sbc_cambia_de_tramo_el_primero_de_febrero(self):
        """
        Los tramos se miden en UMA, y en enero rige la UMA del año anterior.
        $400 son 3.54 UMA en enero (UMA 2025) y 3.41 UMA en febrero (UMA 2026):
        dos tramos distintos sin que el salario haya cambiado.
        """
        en_enero = ceav_patronal(Decimal("400"), ENERO, ZonaSalarioMinimo.GENERAL)
        en_febrero = ceav_patronal(Decimal("400"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert en_enero == Decimal("0.06613")
        assert en_febrero == Decimal("0.06361")

    def test_la_zona_cambia_el_resultado(self):
        """
        En ZLFN 1 SM son $440.87 (3.76 UMA). Con SBC exacto de $440.87 el
        trabajador es de salario mínimo y paga 3.150%; trece centavos arriba
        cae en el tramo 3.51-4.00 y paga 6.613%.
        """
        assert ceav_patronal(SM_ZLFN_2026, FEBRERO, ZonaSalarioMinimo.ZLFN) == Decimal(
            "0.03150"
        )
        assert ceav_patronal(Decimal("441.00"), FEBRERO, ZonaSalarioMinimo.ZLFN) == Decimal(
            "0.06613"
        )

    def test_el_mismo_sbc_da_distinta_tasa_segun_la_zona(self):
        """$440.87 es salario mínimo en ZLFN pero un SBC alto en zona general."""
        general = ceav_patronal(SM_ZLFN_2026, FEBRERO, ZonaSalarioMinimo.GENERAL)
        zlfn = ceav_patronal(SM_ZLFN_2026, FEBRERO, ZonaSalarioMinimo.ZLFN)
        assert general == Decimal("0.06613")
        assert zlfn == Decimal("0.03150")

    def test_sbc_por_debajo_del_salario_minimo_es_error(self):
        """El clamp del Art. 28 LSS es de F1-02: aquí no se corrige en silencio."""
        with pytest.raises(FiscalValidationError):
            ceav_patronal(Decimal("300"), FEBRERO, ZonaSalarioMinimo.GENERAL)

    def test_anio_sin_tabla(self):
        with pytest.raises(FiscalValidationError):
            ceav_patronal(Decimal("500"), date(2027, 6, 1), ZonaSalarioMinimo.GENERAL)

    def test_ramo_ceav_completo(self):
        ramo = ramo_ceav_patronal(Decimal("400"), FEBRERO, ZonaSalarioMinimo.GENERAL)
        assert ramo.patron == Decimal("0.06361")
        assert ramo.obrero == CEAV_OBRERO[2026] == Decimal("0.01125")
        assert ramo.base is BaseCuota.SBC
        assert ramo.periodicidad is PeriodicidadCuota.BIMESTRAL
