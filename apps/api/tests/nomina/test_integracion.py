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
from app.nomina_engine.ceav import ceav_patronal
from app.nomina_engine.integracion import (
    ConceptoIntegrable,
    clamp_sbc,
    dias_vacaciones_de_ley,
    dias_vacaciones_efectivos,
    factor_integracion,
    factor_integracion_de_ley,
    sbc_fijo,
    sbc_mixto,
    sbc_variable,
    validar_tabla_vacaciones,
)

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


class TestParametrosSalarialesEditables:
    """
    O-03: las prestaciones son del PATRON, y cambiarlas cambia el SBC.

    Es el criterio literal de la tarea —*"cambiar aguinaldo 15→30 cambia el
    factor y el SBC con test que lo demuestra"*— y se mide con el **delta
    exacto**, no con un "es mayor": un `>` pasaria con cualquier formula
    equivocada que apunte hacia arriba.
    """

    def test_aguinaldo_15_a_30_cambia_el_factor_por_15_365(self):
        """
        El delta es exactamente 15/365 = 0.0411 (a 4 decimales, D12).

        Se comprueba la RESTA y no solo el valor final: si `factor_integracion`
        dividiera entre 360 —el error clasico— los dos factores seguirian
        subiendo y un test de "el segundo es mayor" no lo notaria.
        """
        con_ley = factor_integracion(15, 12, Decimal("0.25"))
        con_30 = factor_integracion(30, 12, Decimal("0.25"))

        assert con_ley == Decimal("1.0493")
        assert con_30 == Decimal("1.0904")
        assert con_30 - con_ley == Decimal("0.0411")

    def test_y_el_SBC_sube_con_el(self):
        """El factor no es un numero decorativo: es la base de todas las cuotas."""
        salario = Decimal("500.00")
        sbc_ley = sbc_fijo(salario, factor_integracion(15, 12, Decimal("0.25")))
        sbc_30 = sbc_fijo(salario, factor_integracion(30, 12, Decimal("0.25")))

        assert sbc_ley == Decimal("524.65")
        assert sbc_30 == Decimal("545.20")
        # 500 x 0.0411 = 20.55, al centavo.
        assert sbc_30 - sbc_ley == Decimal("20.55")

    def test_la_prima_vacacional_al_50_por_ciento_tambien_lo_mueve(self):
        """La otra mitad del enunciado: prima superior a la de ley."""
        con_ley = factor_integracion(15, 12, Decimal("0.25"))
        con_50 = factor_integracion(15, 12, Decimal("0.50"))
        # 12 dias x 0.25 extra / 365 = 3/365 = 0.0082
        assert con_50 - con_ley == Decimal("0.0082")

    @pytest.mark.parametrize("aguinaldo", [0, 1, 14])
    def test_un_aguinaldo_bajo_el_minimo_de_ley_se_RECHAZA(self, aguinaldo):
        """Art. 87 LFT: 15 dias. Menos subintegra el SBC y con el las cuotas."""
        with pytest.raises(FiscalValidationError, match="Art. 87 LFT"):
            factor_integracion(aguinaldo, 12, Decimal("0.25"))

    @pytest.mark.parametrize("prima", ["0", "0.10", "0.2499"])
    def test_una_prima_bajo_el_25_por_ciento_se_RECHAZA(self, prima):
        """Art. 80 LFT: 25%. El mensaje explica que es proporcion, no porcentaje."""
        with pytest.raises(FiscalValidationError, match=r"\[0.25, 1\]"):
            factor_integracion(15, 12, Decimal(prima))


class TestTablaDeVacacionesDelPatron:
    """
    La escala de vacaciones se puede capturar, y la ley es el piso. (O-03)

    El Art. 76 fija el MINIMO; el patron puede dar mas (§D5 lo dice: el minimo
    de ley es solo el default). Lo que no puede es dar menos, y eso se rechaza
    renglon por renglon.
    """

    # La escala de ley, para tenerla a la vista: 1→12, 2→14, 3→16, 4→18, 5→20,
    # 6..10→22, 11..15→24.
    TABLA_GENEROSA = ((1, 15), (3, 20), (5, 25), (10, 30))

    def test_una_tabla_superior_a_la_ley_se_acepta(self):
        validar_tabla_vacaciones(self.TABLA_GENEROSA)  # no levanta

    def test_y_cambia_el_factor(self):
        """Capturarla sin que mueva el SBC seria un formulario decorativo."""
        anios = 3
        de_ley = dias_vacaciones_efectivos(anios)
        con_tabla = dias_vacaciones_efectivos(anios, self.TABLA_GENEROSA)
        assert (de_ley, con_tabla) == (16, 20)

        factor_ley = factor_integracion(15, de_ley, Decimal("0.25"))
        factor_tabla = factor_integracion(15, con_tabla, Decimal("0.25"))
        assert factor_tabla > factor_ley
        # 4 dias mas x 0.25 / 365 = 1/365 = 0.0027
        assert factor_tabla - factor_ley == Decimal("0.0027")

    @pytest.mark.parametrize(
        "renglon, minimo",
        [((1, 11), 12), ((3, 15), 16), ((5, 19), 20), ((10, 21), 22)],
    )
    def test_un_solo_renglon_bajo_la_ley_RECHAZA_la_tabla(self, renglon, minimo):
        """
        Renglon por renglon, no en promedio.

        Una escala generosa en el año 1 y corta en el 5 subintegraria el SBC de
        quien lleva cinco años, y un promedio la taparia.
        """
        tabla = ((1, 20), renglon, (10, 30))
        with pytest.raises(FiscalValidationError, match=f"mínimo de ley son {minimo}"):
            validar_tabla_vacaciones(tabla)

    def test_el_mensaje_dice_QUE_renglon_y_QUE_exige_la_ley(self):
        """
        El que captura la tabla tiene que poder arreglarla sin adivinar.

        "La tabla es inválida" lo dejaría probando renglones uno por uno.
        """
        with pytest.raises(FiscalValidationError) as e:
            validar_tabla_vacaciones(((5, 19),))
        mensaje = str(e.value)
        assert "19 días al año 5" in mensaje
        assert "mínimo de ley son 20" in mensaje
        assert "Art. 76 LFT" in mensaje

    def test_sin_tabla_manda_la_ley_igual_que_siempre(self):
        for anios in range(0, 21):
            assert dias_vacaciones_efectivos(anios) == dias_vacaciones_de_ley(anios)

    def test_una_antiguedad_menor_que_el_primer_renglon_cae_a_la_ley(self):
        # La tabla empieza en el año 3; alguien con 1 año no está cubierto.
        assert dias_vacaciones_efectivos(1, ((3, 20), (5, 25))) == 12

    def test_POR_ENCIMA_del_ultimo_renglon_NO_baja_los_dias(self):
        """
        EL CASO QUE VALE ESTA CLASE, y el que el revisor del plan corrigió.

        Tabla capturada hasta el año 10 con 30 días, trabajador con 11. La
        regla "por encima del último renglón se cae a la ley" le daría **24**
        (Art. 76 para 11 años) y su SBC **bajaría al cumplir un año más**.

        El Art. 27 LSS integra lo que el patrón OTORGA, no el mínimo: nadie
        pierde una prestación por ganar antigüedad. Y subintegrar es la
        dirección que este repo trata siempre como la mala.
        """
        assert dias_vacaciones_de_ley(11) == 24
        assert dias_vacaciones_efectivos(11, self.TABLA_GENEROSA) == 30
        # Y sigue sin bajar mucho más adelante.
        assert dias_vacaciones_efectivos(30, self.TABLA_GENEROSA) >= dias_vacaciones_de_ley(30)

    def test_pero_la_LEY_gana_si_supera_al_ultimo_renglon(self):
        """
        El simétrico: una tabla corta no puede dejar a nadie bajo el mínimo.

        Con 40 años de servicio la ley da 34 días, más que los 30 de la tabla.
        """
        assert dias_vacaciones_de_ley(40) == 34
        assert dias_vacaciones_efectivos(40, self.TABLA_GENEROSA) == 34

    def test_la_tabla_no_necesita_estar_ordenada(self):
        desordenada = ((10, 30), (1, 15), (5, 25))
        assert dias_vacaciones_efectivos(5, desordenada) == 25

    def test_años_negativos_se_rechazan(self):
        with pytest.raises(FiscalValidationError, match="no pueden ser negativos"):
            validar_tabla_vacaciones(((-1, 20),))
