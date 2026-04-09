"""
Tests del motor fiscal con datos de ejemplo.
Ejecutar: pytest tests/ -v
"""

import pytest
from app.schemas.fiscal import PerfilContribuyente, CFDI, TipoFactura, PeriodicidadDeclaracion
from app.fiscal_engine.calculadora import (
    clasificar_facturas,
    calcular_isr_resico,
    calcular_isr_general,
    calcular_declaracion,
)
from app.fiscal_engine.deducciones_personales import (
    calcular_deducciones_personales,
    TOPE_5_UMAS_ANUALES,
)
from app.fiscal_engine.tablas_isr import TABLA_ISR_MENSUAL, generar_tabla_acumulada
from app.fiscal_engine.calendario import generar_calendario, _dias_habiles_extra
from app.fiscal_engine.comparador import calcular_todos_regimenes
from datetime import date


# ============================================================
# Fixtures — datos de ejemplo
# ============================================================

def perfil_resico() -> PerfilContribuyente:
    return PerfilContribuyente(
        rfc="CAUA030101ABC",
        regimen="626",
        nombre="Timmy Freelancer",
        periodicidad=PeriodicidadDeclaracion.MENSUAL,
    )


def perfil_actividad_empresarial() -> PerfilContribuyente:
    return PerfilContribuyente(
        rfc="GOPE900515XYZ",
        regimen="612",
        nombre="Pedro Gonzalez",
        periodicidad=PeriodicidadDeclaracion.MENSUAL,
    )


def facturas_enero_resico() -> list[CFDI]:
    """Facturas de ejemplo para un freelancer RESICO en enero."""
    return [
        # Factura emitida (ingreso) - proyecto de diseno
        CFDI(
            uuid="AAA-111", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="CAUA030101ABC", rfc_receptor="EMPRESA_SA_RFC",
            subtotal=15000.00, total=17400.00,
            iva_trasladado=2400.00, isr_retenido=1500.00, iva_retenido=1600.00,
        ),
        # Segunda factura emitida
        CFDI(
            uuid="AAA-222", fecha=date(2025, 1, 25), tipo=TipoFactura.INGRESO,
            rfc_emisor="CAUA030101ABC", rfc_receptor="OTRA_EMPRESA_RFC",
            subtotal=8000.00, total=9280.00,
            iva_trasladado=1280.00, isr_retenido=800.00,
        ),
        # Factura recibida (egreso) - licencia Adobe
        CFDI(
            uuid="BBB-333", fecha=date(2025, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="ADOBE_RFC", rfc_receptor="CAUA030101ABC",
            subtotal=1200.00, total=1392.00,
            iva_trasladado=192.00,
        ),
    ]


def facturas_enero_empresarial() -> list[CFDI]:
    """Facturas de ejemplo para actividad empresarial en enero."""
    return [
        # Ingreso: servicio de consultoria
        CFDI(
            uuid="CCC-111", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
            subtotal=50000.00, total=58000.00,
            iva_trasladado=8000.00,
        ),
        # Gasto: renta de oficina
        CFDI(
            uuid="CCC-222", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
            rfc_emisor="ARRENDADOR_RFC", rfc_receptor="GOPE900515XYZ",
            subtotal=12000.00, total=13920.00,
            iva_trasladado=1920.00,
        ),
        # Gasto: internet
        CFDI(
            uuid="CCC-333", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
            rfc_emisor="TELMEX_RFC", rfc_receptor="GOPE900515XYZ",
            subtotal=800.00, total=928.00,
            iva_trasladado=128.00,
        ),
    ]


# ============================================================
# Tests
# ============================================================

class TestClasificarFacturas:
    def test_clasifica_ingresos_y_egresos(self):
        facturas = facturas_enero_resico()
        ingresos, egresos = clasificar_facturas(facturas, "CAUA030101ABC")

        assert len(ingresos) == 2  # Las 2 facturas emitidas por el contribuyente
        assert len(egresos) == 1   # La factura de Adobe (recibida)

    def test_rfc_case_insensitive(self):
        facturas = facturas_enero_resico()
        ingresos, egresos = clasificar_facturas(facturas, "caua030101abc")
        assert len(ingresos) == 2


class TestISRResico:
    def test_rango_1_porciento(self):
        isr, tasa = calcular_isr_resico(20000)
        assert tasa == 0.01
        assert isr == 200.00

    def test_rango_1_punto_1(self):
        isr, tasa = calcular_isr_resico(30000)
        assert tasa == 0.011
        assert isr == 330.00

    def test_rango_2_punto_5(self):
        isr, tasa = calcular_isr_resico(250000)
        assert tasa == 0.025
        assert isr == 6250.00

    def test_cero_ingresos(self):
        isr, tasa = calcular_isr_resico(0)
        assert isr == 0.0


class TestISRGeneral:
    def test_calculo_basico(self):
        # $50,000 mensuales -> rango 35,362.84-55,736.68 (Anexo 8 RMF 2026)
        isr, tasa = calcular_isr_general(50000)
        assert isr > 0
        assert 0.15 < tasa < 0.25  # Tasa efectiva razonable

    def test_anual(self):
        isr, tasa = calcular_isr_general(600000, es_anual=True)
        assert isr > 0


class TestDeclaracionCompleta:
    def test_declaracion_resico_mensual(self):
        perfil = perfil_resico()
        facturas = facturas_enero_resico()
        desglose = calcular_declaracion(perfil, facturas)

        # RESICO: ISR sobre ingresos brutos (23,000), sin deducciones
        assert desglose.total_ingresos_gravados == 23000.00
        assert desglose.total_deducciones_autorizadas == 0  # RESICO no deduce
        assert desglose.isr_causado > 0
        assert desglose.isr_retenido == 2300.00  # 1500 + 800
        assert desglose.total_a_pagar >= 0

    def test_declaracion_empresarial_mensual(self):
        perfil = perfil_actividad_empresarial()
        facturas = facturas_enero_empresarial()
        desglose = calcular_declaracion(perfil, facturas)

        # Act. Empresarial: ingresos - deducciones
        assert desglose.total_ingresos_gravados == 50000.00
        assert desglose.total_deducciones_autorizadas == 12800.00  # renta + internet
        assert desglose.base_isr == 37200.00  # 50000 - 12800
        assert desglose.isr_causado > 0

    def test_iva_calculo(self):
        perfil = perfil_actividad_empresarial()
        facturas = facturas_enero_empresarial()
        desglose = calcular_declaracion(perfil, facturas)

        assert desglose.iva_trasladado_cobrado == 8000.00
        assert desglose.iva_trasladado_pagado == 2048.00  # 1920 + 128
        assert desglose.iva_a_pagar == 8000.00 - 2048.00  # 5952

    def test_sin_facturas_retorna_ceros(self):
        perfil = perfil_resico()
        desglose = calcular_declaracion(perfil, [])
        assert desglose.total_a_pagar == 0.0


# ============================================================
# Tests Deducciones Personales
# ============================================================

class TestDeduccionesPersonales:
    def test_deducciones_bajo_tope(self):
        """Gastos medicos + colegiaturas que no excedan el tope global."""
        resultado = calcular_deducciones_personales(
            ingresos_anuales=500_000.00,
            gastos_medicos=30_000.00,
            colegiaturas=10_000.00,
            nivel_educativo="primaria",
        )
        # Colegiaturas primaria tope $12,900 -> $10,000 pasa completo
        assert resultado.total_antes_tope == 40_000.00
        assert resultado.total_deducible == 40_000.00
        assert resultado.excedente_no_aprovechado == 0.0

    def test_tope_5_umas_aplicado(self):
        """Deducciones exceden 5 UMAs anuales, se aplica tope."""
        resultado = calcular_deducciones_personales(
            ingresos_anuales=2_000_000.00,  # 15% = $300,000 > 5 UMAs
            gastos_medicos=150_000.00,
            intereses_hipotecarios=100_000.00,
        )
        assert resultado.tope_tipo == "5_umas"
        assert resultado.total_deducible == round(TOPE_5_UMAS_ANUALES, 2)
        assert resultado.excedente_no_aprovechado > 0

    def test_tope_15_porciento_cuando_menor(self):
        """El 15% de ingresos es menor que 5 UMAs -> se aplica 15%."""
        ingresos = 800_000.00  # 15% = $120,000 < $213,926.50
        resultado = calcular_deducciones_personales(
            ingresos_anuales=ingresos,
            gastos_medicos=100_000.00,
            intereses_hipotecarios=50_000.00,
        )
        assert resultado.tope_tipo == "15_porciento"
        assert resultado.tope_global == ingresos * 0.15
        assert resultado.total_deducible == ingresos * 0.15

    def test_tope_colegiaturas_por_nivel(self):
        """Colegiaturas se topan segun nivel educativo."""
        resultado = calcular_deducciones_personales(
            ingresos_anuales=500_000.00,
            colegiaturas=30_000.00,
            nivel_educativo="bachillerato",  # tope $24,500
        )
        # Buscar la deduccion de colegiaturas en el desglose
        colegiatura_deduccion = [d for d in resultado.desglose if "Colegiaturas" in d.concepto][0]
        assert colegiatura_deduccion.monto_solicitado == 30_000.00
        assert colegiatura_deduccion.monto_aceptado == 24_500.00


# ============================================================
# Tests Deduccion Ciega Arrendamiento
# ============================================================

class TestDeduccionCiega:
    def test_ciega_conviene_con_pocos_gastos(self):
        """Con pocos gastos reales, la deduccion ciega del 35% conviene."""
        perfil = PerfilContribuyente(
            rfc="ARRE010101ABC",
            regimen="606",
            nombre="Arrendador Test",
        )
        facturas = [
            # Ingreso por renta: $30,000
            CFDI(
                uuid="ARR-001", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="ARRE010101ABC", rfc_receptor="INQUILINO_RFC",
                subtotal=30_000.00, total=34_800.00, iva_trasladado=4_800.00,
            ),
            # Gasto real pequeno: $2,000 (< 35% de 30k = $10,500)
            CFDI(
                uuid="ARR-002", fecha=date(2025, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="MANTENIMIENTO_RFC", rfc_receptor="ARRE010101ABC",
                subtotal=2_000.00, total=2_320.00, iva_trasladado=320.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        assert desglose.deduccion_ciega_aplicada is True
        # Deduccion ciega = 30,000 * 0.35 = 10,500
        assert desglose.total_deducciones_autorizadas == 10_500.00
        assert desglose.comparacion_deduccion is not None

    def test_real_conviene_con_muchos_gastos(self):
        """Con muchos gastos reales, la deduccion real conviene."""
        perfil = PerfilContribuyente(
            rfc="ARRE010101ABC",
            regimen="606",
            nombre="Arrendador Test",
        )
        facturas = [
            # Ingreso por renta: $30,000
            CFDI(
                uuid="ARR-001", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="ARRE010101ABC", rfc_receptor="INQUILINO_RFC",
                subtotal=30_000.00, total=34_800.00, iva_trasladado=4_800.00,
            ),
            # Gasto real grande: $15,000 (> 35% de 30k = $10,500)
            CFDI(
                uuid="ARR-003", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="REPARACIONES_RFC", rfc_receptor="ARRE010101ABC",
                subtotal=15_000.00, total=17_400.00, iva_trasladado=2_400.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        assert desglose.deduccion_ciega_aplicada is False
        assert desglose.total_deducciones_autorizadas == 15_000.00

    def test_deduccion_ciega_incluye_predial(self):
        """Deduccion ciega = 35% de ingresos + predial pagado (Art. 115)."""
        perfil = PerfilContribuyente(
            rfc="ARRN010101AB1", regimen="606", nombre="Arrendador",
        )
        factura = CFDI(
            uuid="A1", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="ARRN010101AB1", rfc_receptor="INQ123",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        # Sin predial: ciega = 35,000
        desglose_sin = calcular_declaracion(perfil, [factura], predial_pagado=0)
        # Con predial $2,000: ciega = 35,000 + 2,000 = 37,000
        desglose_con = calcular_declaracion(perfil, [factura], predial_pagado=2_000)

        assert desglose_sin.deduccion_ciega_aplicada is True
        assert desglose_sin.total_deducciones_autorizadas == 35_000.00
        assert desglose_con.deduccion_ciega_aplicada is True
        assert desglose_con.total_deducciones_autorizadas == 37_000.00


# ============================================================
# Tests Plataformas Tecnologicas
# ============================================================

class TestPlataformas:
    def test_ingresos_bajos_retenciones_definitivas(self):
        """Ingresos anualizados <= $300k -> retenciones como pago definitivo."""
        perfil = PerfilContribuyente(
            rfc="PLAT010101AB2",
            regimen="625",
            nombre="Conductor Uber",
        )
        facturas = [
            # Ingreso mensual: $20,000 -> anualizado $240,000 < $300,000
            CFDI(
                uuid="PLT-001", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="PLAT010101AB2", rfc_receptor="UBER_RFC",
                subtotal=20_000.00, total=23_200.00,
                iva_trasladado=3_200.00, isr_retenido=2_000.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        assert desglose.retenciones_definitivas is True
        assert desglose.isr_causado == 0.0
        assert desglose.ingreso_anualizado_estimado == 240_000.00

    def test_ingresos_altos_declaracion_normal(self):
        """Ingresos anualizados > $300k -> debe declarar normalmente."""
        perfil = PerfilContribuyente(
            rfc="PLAT010101AB2",
            regimen="625",
            nombre="Conductor Uber Premium",
        )
        facturas = [
            # Ingreso mensual: $30,000 -> anualizado $360,000 > $300,000
            CFDI(
                uuid="PLT-002", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="PLAT010101AB2", rfc_receptor="UBER_RFC",
                subtotal=30_000.00, total=34_800.00,
                iva_trasladado=4_800.00, isr_retenido=3_000.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        assert desglose.retenciones_definitivas is False
        assert desglose.isr_causado > 0
        assert desglose.ingreso_anualizado_estimado == 360_000.00

    def test_plataformas_filtra_gastos_personales(self):
        """Regimen 625 con ingresos >$300k debe filtrar gastos personales."""
        perfil = PerfilContribuyente(
            rfc="PLAT020101AB1", regimen="625", nombre="Conductor",
        )
        ingreso = CFDI(
            uuid="I1", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
            rfc_emisor="PLAT020101AB1", rfc_receptor="UBER123",
            subtotal=30_000, total=34_800, iva_trasladado=4_800,
            clave_prod_serv="78101800", metodo_pago="PUE",
        )
        gasto_negocio = CFDI(
            uuid="G1", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="GAS123", rfc_receptor="PLAT020101AB1",
            subtotal=2_000, total=2_320, iva_trasladado=320,
            clave_prod_serv="15101500", metodo_pago="PUE",  # Gasolina -> deducible
        )
        gasto_personal = CFDI(
            uuid="G2", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="REST123", rfc_receptor="PLAT020101AB1",
            subtotal=500, total=580, iva_trasladado=80,
            clave_prod_serv="90101600", metodo_pago="PUE",  # Restaurante -> personal
        )
        desglose = calcular_declaracion(
            perfil, [ingreso, gasto_negocio, gasto_personal],
        )
        assert desglose.gastos_personales_excluidos == 500
        assert desglose.total_deducciones_autorizadas == 2_000

    def test_plataformas_pago_definitivo_no_calcula_iva(self):
        """Pago definitivo (<=300k): IVA = 0, retenciones cubren todo."""
        perfil = PerfilContribuyente(
            rfc="PLAT020101AB1", regimen="625", nombre="Conductor",
        )
        ingreso = CFDI(
            uuid="P1", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="PLAT020101AB1", rfc_receptor="UBER123",
            subtotal=20_000, total=23_200, iva_trasladado=3_200,
            isr_retenido=420, iva_retenido=1_600,
            clave_prod_serv="78101800", metodo_pago="PUE",
        )
        gasto = CFDI(
            uuid="G1", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="GAS123", rfc_receptor="PLAT020101AB1",
            subtotal=2_000, total=2_320, iva_trasladado=320,
            clave_prod_serv="15101500", metodo_pago="PUE",
        )
        desglose = calcular_declaracion(perfil, [ingreso, gasto])
        assert desglose.retenciones_definitivas is True
        assert desglose.isr_causado == 0
        assert desglose.iva_trasladado_cobrado == 0
        assert desglose.iva_trasladado_pagado == 0
        assert desglose.iva_retenido == 0
        assert desglose.iva_a_pagar == 0

    def test_plataformas_no_definitivo_si_calcula_iva(self):
        """Ingresos >$300k: declara normal, SI calcula IVA."""
        perfil = PerfilContribuyente(
            rfc="PLAT030101AB1", regimen="625", nombre="Vendedor ML",
        )
        ingreso = CFDI(
            uuid="P2", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="PLAT030101AB1", rfc_receptor="MELI123",
            subtotal=30_000, total=34_800, iva_trasladado=4_800,
            isr_retenido=750, iva_retenido=2_400,
            clave_prod_serv="44121700", metodo_pago="PUE",
        )
        desglose = calcular_declaracion(perfil, [ingreso])
        assert desglose.retenciones_definitivas is False
        assert desglose.isr_causado > 0
        assert desglose.iva_trasladado_cobrado == 4_800
        assert desglose.iva_a_pagar != 0


# ============================================================
# Tests Calendario Fiscal
# ============================================================

class TestCalendario:
    def test_asalariado_solo_anual(self):
        """Asalariado solo tiene 1 obligacion: declaracion anual."""
        obligaciones = generar_calendario("asalariado", "605", "XAXX010101000")
        assert len(obligaciones) == 1
        assert obligaciones[0].periodicidad == "anual"
        assert "anual" in obligaciones[0].nombre.lower()

    def test_independiente_resico_13_obligaciones(self):
        """Independiente RESICO tiene 12 mensuales + 1 anual = 13."""
        obligaciones = generar_calendario("independiente", "626", "XAXX010101000")
        assert len(obligaciones) == 13
        mensuales = [o for o in obligaciones if o.periodicidad == "mensual"]
        anuales = [o for o in obligaciones if o.periodicidad == "anual"]
        assert len(mensuales) == 12
        assert len(anuales) == 1

    def test_sexto_digito_ajusta_fecha(self):
        """El 6to digito del RFC ajusta la fecha limite del dia 17."""
        # RFC con 6to digito = 1 -> +1 dia habil
        obligaciones_1 = generar_calendario("arrendamiento", "606", "ABCD210101XY1")
        # RFC con 6to digito = 9 -> +5 dias habiles
        obligaciones_9 = generar_calendario("arrendamiento", "606", "ABCD210199XY1")

        # Las fechas deben ser diferentes
        fecha_1 = obligaciones_1[0].fecha_limite
        fecha_9 = obligaciones_9[0].fecha_limite
        assert fecha_1 != fecha_9

        # Verificar logica de dias habiles extra
        assert _dias_habiles_extra(1) == 1
        assert _dias_habiles_extra(9) == 5
        assert _dias_habiles_extra(0) == 5


# ============================================================
# Tests Arrendamiento (606) — Bugs corregidos
# ============================================================

class TestArrendamientoRecomendaciones:
    def test_regimen_606_nunca_recibe_recomendacion_resico(self):
        """El regimen 606 (Arrendamiento) esta excluido de RESICO por ley."""
        from app.routes.declaraciones import _generar_recomendaciones
        from app.schemas.declaraciones import PreDeclaracionRequest

        perfil = PerfilContribuyente(
            rfc="ARRE010101ABC",
            regimen="606",
            nombre="Arrendador Test",
        )
        facturas = [
            CFDI(
                uuid="ARR-REC-001", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="ARRE010101ABC", rfc_receptor="INQUILINO_RFC",
                subtotal=20_000.00, total=23_200.00, iva_trasladado=3_200.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        req = PreDeclaracionRequest(
            contribuyente=perfil,
            facturas=facturas,
            periodo_year=2025,
            periodo_month=1,
        )
        recomendaciones = _generar_recomendaciones(req, desglose)
        for r in recomendaciones:
            assert "resico" not in r.lower(), (
                f"Regimen 606 no debe recibir recomendacion de RESICO, pero recibio: {r}"
            )


class TestArrendamientoISR:
    def test_tasa_efectiva_arrendamiento_19500(self):
        """Arrendamiento usa tarifa progresiva Art. 96, no tasa plana.
        Para base gravable de $19,500 la tasa efectiva debe estar entre 10% y 15%.
        """
        perfil = PerfilContribuyente(
            rfc="ARRE010101ABC",
            regimen="606",
            nombre="Arrendador Test",
        )
        # Ingreso de $30,000, gastos reales de $10,500 -> base = $19,500
        facturas = [
            CFDI(
                uuid="ARR-ISR-001", fecha=date(2025, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="ARRE010101ABC", rfc_receptor="INQUILINO_RFC",
                subtotal=30_000.00, total=34_800.00, iva_trasladado=4_800.00,
            ),
            CFDI(
                uuid="ARR-ISR-002", fecha=date(2025, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GASTOS_RFC", rfc_receptor="ARRE010101ABC",
                subtotal=10_500.00, total=12_180.00, iva_trasladado=1_680.00,
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas)
        # Deduccion ciega = 30000 * 0.35 = 10,500 = gastos reales -> ciega gana (empate)
        # Base = 30000 - 10500 = 19,500
        assert desglose.base_isr == 19_500.00
        # Tasa efectiva progresiva para $19,500 debe estar entre 10% y 15%
        assert 0.10 <= desglose.tasa_isr <= 0.15, (
            f"Tasa efectiva {desglose.tasa_isr} fuera del rango esperado 10%-15%"
        )
        assert desglose.isr_causado > 0

    def test_tasa_efectiva_cero_cuando_base_cero(self):
        """Si base gravable es 0, la tasa efectiva debe ser 0.0."""
        isr, tasa = calcular_isr_general(0.0, es_anual=False)
        assert isr == 0.0
        assert tasa == 0.0

    def test_arrendamiento_usa_tabla_acumulativa(self):
        """Arrendamiento en mes 6 debe usar tabla x6 (Art. 116/106)."""
        perfil = PerfilContribuyente(
            rfc="ARRN010101AB1", regimen="606", nombre="Arrendador",
        )
        # Factura registrada en enero del ejercicio (Art. 106: la tabla
        # acumulada solo aplica si las facturas cubren desde enero).
        factura_ingreso = CFDI(
            uuid="A1", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="ARRN010101AB1", rfc_receptor="INQU010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        # Sin gastos -> deduccion ciega 35%
        desglose = calcular_declaracion(perfil, [factura_ingreso], periodo_month=6)

        # Deduccion ciega: 100000 * 0.35 = 35000 -> base = 65000
        assert desglose.base_isr == 65_000
        assert desglose.deduccion_ciega_aplicada is True
        # Con tabla x6 (Anexo 8 RMF 2026): ISR = $4,918.09 (rango 3 acumulado)
        # Con tabla x1 seria mucho mayor
        assert desglose.isr_causado == 4_918.09


# ============================================================
# Tests Comparador de Regimenes
# ============================================================

class TestComparador:
    def _get(self, resultados, regimen):
        return next(r for r in resultados if r.regimen == regimen)

    def test_devuelve_cinco_regimenes(self):
        """Siempre se calculan los 5 regimenes de PF."""
        resultados, _, _, _ = calcular_todos_regimenes(30_000, 5_000)
        assert len(resultados) == 5
        codigos = {r.regimen for r in resultados}
        assert codigos == {"626", "612", "606", "625", "605"}

    def test_ordenados_menor_isr_primero(self):
        """Los resultados vienen ordenados de menor a mayor ISR anual (disponibles primero)."""
        resultados, _, _, _ = calcular_todos_regimenes(30_000, 5_000)
        disponibles = [r for r in resultados if r.disponible]
        isrs = [r.isr_anual for r in disponibles]
        assert isrs == sorted(isrs)

    def test_resico_conviene_ingresos_bajos_pocos_gastos(self):
        """Con ingresos bajos y pocos gastos, RESICO tiene menor ISR que 612."""
        resultados, recomendado, _, _ = calcular_todos_regimenes(20_000, 3_000)
        r626 = self._get(resultados, "626")
        r612 = self._get(resultados, "612")
        assert r626.disponible is True
        assert r626.isr_anual < r612.isr_anual

    def test_empresarial_conviene_muchos_gastos(self):
        """Con muchos gastos deducibles, 612 tiene menor ISR que RESICO."""
        resultados, _, _, _ = calcular_todos_regimenes(250_000, 240_000)
        r626 = self._get(resultados, "626")
        r612 = self._get(resultados, "612")
        assert r612.isr_anual < r626.isr_anual

    def test_tope_resico_excedido(self):
        """Ingresos > $3.5M anuales -> RESICO no disponible."""
        resultados, _, _, recomendacion = calcular_todos_regimenes(300_000, 100_000)
        r626 = self._get(resultados, "626")
        assert r626.disponible is False
        assert any("no disponible" in n.lower() for n in r626.notas)

    def test_606_aplica_deduccion_ciega(self):
        """606 con pocos gastos aplica la deduccion ciega del 35%."""
        resultados, _, _, _ = calcular_todos_regimenes(50_000, 2_000)
        r606 = self._get(resultados, "606")
        assert r606.disponible is True
        assert any("ciega" in n.lower() for n in r606.notas)

    def test_606_predial_incluido(self):
        """606 con predial reduce la base gravable."""
        res_sin, _, _, _ = calcular_todos_regimenes(50_000, 5_000, predial_mensual=0)
        res_con, _, _, _ = calcular_todos_regimenes(50_000, 5_000, predial_mensual=1_000)
        r606_sin = self._get(res_sin, "606")
        r606_con = self._get(res_con, "606")
        assert r606_con.isr_anual <= r606_sin.isr_anual

    def test_625_pago_definitivo_bajo_umbral(self):
        """625 con ingresos <= $300k anuales es pago definitivo."""
        resultados, _, _, _ = calcular_todos_regimenes(20_000, 0)  # $240k anual
        r625 = self._get(resultados, "625")
        assert r625.disponible is True
        assert any("definitivo" in n.lower() for n in r625.notas)

    def test_recomendado_es_el_menor_isr_disponible(self):
        """El regimen recomendado es el disponible con menor ISR."""
        resultados, recomendado, _, _ = calcular_todos_regimenes(30_000, 5_000)
        disponibles = [r for r in resultados if r.disponible]
        mejor = min(disponibles, key=lambda r: r.isr_anual)
        assert recomendado == mejor.regimen


# ============================================================
# Tests DIOT
# ============================================================

class TestDIOT:
    def test_agrupa_por_proveedor(self):
        """3 facturas de egreso de 2 proveedores distintos se agrupan correctamente."""
        from app.fiscal_engine.diot import generar_diot

        facturas = [
            CFDI(
                uuid="DIOT-001", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_A_RFC", rfc_receptor="PYME123456ABC",
                subtotal=10_000.00, total=11_600.00, iva_trasladado=1_600.00,
            ),
            CFDI(
                uuid="DIOT-002", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_B_RFC", rfc_receptor="PYME123456ABC",
                subtotal=5_000.00, total=5_800.00, iva_trasladado=800.00,
            ),
            CFDI(
                uuid="DIOT-003", fecha=date(2025, 1, 20), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_A_RFC", rfc_receptor="PYME123456ABC",
                subtotal=8_000.00, total=9_280.00, iva_trasladado=1_280.00,
            ),
        ]
        proveedores = generar_diot("PYME123456ABC", facturas)
        assert len(proveedores) == 2

        prov_a = [p for p in proveedores if p.rfc == "PROVEEDOR_A_RFC"][0]
        assert prov_a.total_operaciones == 18_000.00
        assert prov_a.iva_pagado == 2_880.00
        assert prov_a.cantidad_facturas == 2

        prov_b = [p for p in proveedores if p.rfc == "PROVEEDOR_B_RFC"][0]
        assert prov_b.total_operaciones == 5_000.00
        assert prov_b.cantidad_facturas == 1

    def test_solo_incluye_egresos(self):
        """Facturas de ingreso del contribuyente no aparecen en DIOT."""
        from app.fiscal_engine.diot import generar_diot

        facturas = [
            # Ingreso del contribuyente (emite factura)
            CFDI(
                uuid="DIOT-ING", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="PYME123456ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=50_000.00, total=58_000.00, iva_trasladado=8_000.00,
            ),
            # Egreso del contribuyente (recibe factura)
            CFDI(
                uuid="DIOT-EGR", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="PYME123456ABC",
                subtotal=3_000.00, total=3_480.00, iva_trasladado=480.00,
            ),
        ]
        proveedores = generar_diot("PYME123456ABC", facturas)
        assert len(proveedores) == 1
        assert proveedores[0].rfc == "PROVEEDOR_RFC"


# ============================================================
# Tests Retenciones a Terceros
# ============================================================

class TestRetenciones:
    def test_agrupa_retenciones_por_tercero(self):
        """2 facturas con retenciones de proveedores distintos se agrupan."""
        from app.fiscal_engine.retenciones import generar_resumen_retenciones

        facturas = [
            CFDI(
                uuid="RET-001", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="TERCERO_A_RFC", rfc_receptor="PYME123456ABC",
                subtotal=20_000.00, total=23_200.00,
                iva_trasladado=3_200.00, isr_retenido=2_000.00, iva_retenido=1_600.00,
            ),
            CFDI(
                uuid="RET-002", fecha=date(2025, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="TERCERO_B_RFC", rfc_receptor="PYME123456ABC",
                subtotal=10_000.00, total=11_600.00,
                iva_trasladado=1_600.00, isr_retenido=1_000.00, iva_retenido=0.00,
            ),
        ]
        terceros = generar_resumen_retenciones("PYME123456ABC", facturas)
        assert len(terceros) == 2

        t_a = [t for t in terceros if t.rfc == "TERCERO_A_RFC"][0]
        assert t_a.isr_retenido == 2_000.00
        assert t_a.iva_retenido == 1_600.00

        t_b = [t for t in terceros if t.rfc == "TERCERO_B_RFC"][0]
        assert t_b.isr_retenido == 1_000.00
        assert t_b.iva_retenido == 0.00

    def test_sin_retenciones_lista_vacia(self):
        """Facturas sin retenciones producen lista vacia."""
        from app.fiscal_engine.retenciones import generar_resumen_retenciones

        facturas = [
            CFDI(
                uuid="RET-003", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="PYME123456ABC",
                subtotal=5_000.00, total=5_800.00,
                iva_trasladado=800.00, isr_retenido=0.00, iva_retenido=0.00,
            ),
        ]
        terceros = generar_resumen_retenciones("PYME123456ABC", facturas)
        assert len(terceros) == 0


# ============================================================
# Tests Multi-Periodo
# ============================================================

class TestMultiPeriodo:
    def test_separa_y_calcula_por_mes(self):
        """RESICO (no acumulativo): cada mes se calcula con sus facturas aisladas."""
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_resico()
        facturas = [
            CFDI(
                uuid="MP-ENE", fecha=date(2025, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="CAUA030101ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=30_000.00, total=34_800.00, iva_trasladado=4_800.00,
            ),
            CFDI(
                uuid="MP-FEB", fecha=date(2025, 2, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="CAUA030101ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=40_000.00, total=46_400.00, iva_trasladado=6_400.00,
            ),
            CFDI(
                uuid="MP-MAR", fecha=date(2025, 3, 20), tipo=TipoFactura.INGRESO,
                rfc_emisor="CAUA030101ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=50_000.00, total=58_000.00, iva_trasladado=8_000.00,
            ),
        ]
        resultados, acumulado = calcular_multi_periodo(perfil, facturas, 2025, [1, 2, 3])
        assert len(resultados) == 3
        assert "Enero" in resultados[0].periodo
        assert "Febrero" in resultados[1].periodo
        assert "Marzo" in resultados[2].periodo
        # RESICO: cada mes solo cuenta sus propias facturas (no acumula)
        assert resultados[0].desglose.total_ingresos_gravados == 30_000.00
        assert resultados[1].desglose.total_ingresos_gravados == 40_000.00
        assert resultados[2].desglose.total_ingresos_gravados == 50_000.00

    def test_acumulado_suma_correctamente(self):
        """El acumulado debe sumar ISR e IVA de todos los periodos."""
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_actividad_empresarial()
        facturas = [
            CFDI(
                uuid="MP-AC-1", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=20_000.00, total=23_200.00, iva_trasladado=3_200.00,
            ),
            CFDI(
                uuid="MP-AC-2", fecha=date(2025, 2, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=20_000.00, total=23_200.00, iva_trasladado=3_200.00,
            ),
        ]
        resultados, acumulado = calcular_multi_periodo(perfil, facturas, 2025, [1, 2])
        total_isr_manual = sum(r.desglose.isr_a_pagar for r in resultados)
        total_iva_manual = sum(max(r.desglose.iva_a_pagar, 0) for r in resultados)
        assert acumulado.total_isr_pagado == round(total_isr_manual, 2)
        assert acumulado.total_iva_pagado == round(total_iva_manual, 2)
        assert acumulado.total_general_pagado == round(total_isr_manual + total_iva_manual, 2)

    def test_612_acumulativo_art106(self):
        """Regimen 612: febrero acumula ingresos de enero (Art. 106 LISR)."""
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_actividad_empresarial()
        facturas = [
            CFDI(
                uuid="ACU-ENE", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=30_000.00, total=34_800.00, iva_trasladado=4_800.00,
                metodo_pago="PUE",
            ),
            CFDI(
                uuid="ACU-FEB", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=40_000.00, total=46_400.00, iva_trasladado=6_400.00,
                metodo_pago="PUE",
            ),
        ]
        resultados, _ = calcular_multi_periodo(perfil, facturas, 2026, [1, 2])
        # Enero aislado: solo $30,000
        assert resultados[0].desglose.total_ingresos_gravados == 30_000.00
        # Febrero (mes-only): $40,000. El acumulado se reporta en el nuevo
        # campo ingresos_acumulados (Art. 106 LISR).
        assert resultados[1].desglose.total_ingresos_gravados == 40_000.00
        assert resultados[1].desglose.ingresos_acumulados == 70_000.00
        # La base ISR es la base acumulada de ambos meses (Art. 106)
        assert resultados[1].desglose.base_isr == 70_000.00

    def test_626_no_acumulativo(self):
        """RESICO (626): cada mes aislado, sin acumulado (Art. 113-E)."""
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_resico()
        facturas = [
            CFDI(
                uuid="RES-ENE", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="CAUA030101ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=15_000.00, total=17_400.00, iva_trasladado=2_400.00,
                metodo_pago="PUE",
            ),
            CFDI(
                uuid="RES-FEB", fecha=date(2026, 2, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="CAUA030101ABC", rfc_receptor="CLIENTE_RFC",
                subtotal=20_000.00, total=23_200.00, iva_trasladado=3_200.00,
                metodo_pago="PUE",
            ),
        ]
        resultados, _ = calcular_multi_periodo(perfil, facturas, 2026, [1, 2])
        # RESICO: cada mes con sus propias facturas, sin acumular
        assert resultados[0].desglose.total_ingresos_gravados == 15_000.00
        assert resultados[1].desglose.total_ingresos_gravados == 20_000.00
        # Pagos provisionales anteriores deben ser 0 en ambos meses (RESICO no acumula)
        assert resultados[0].desglose.pagos_provisionales_anteriores == 0.0
        assert resultados[1].desglose.pagos_provisionales_anteriores == 0.0

    def test_pagos_provisionales_se_restan(self):
        """En 612 acumulativo: febrero resta el ISR causado en enero."""
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_actividad_empresarial()
        facturas = [
            CFDI(
                uuid="PROV-ENE", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=50_000.00, total=58_000.00, iva_trasladado=8_000.00,
                metodo_pago="PUE",
            ),
            CFDI(
                uuid="PROV-FEB", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=50_000.00, total=58_000.00, iva_trasladado=8_000.00,
                metodo_pago="PUE",
            ),
        ]
        resultados, _ = calcular_multi_periodo(perfil, facturas, 2026, [1, 2])
        isr_enero = resultados[0].desglose.isr_causado
        pagos_ant_feb = resultados[1].desglose.pagos_provisionales_anteriores

        # Febrero debe haber restado el ISR causado en enero como pago anterior
        assert pagos_ant_feb == round(isr_enero, 2)
        # Febrero mes-only: $50k. El acumulado se reporta aparte (Art. 106).
        assert resultados[1].desglose.total_ingresos_gravados == 50_000.00
        assert resultados[1].desglose.ingresos_acumulados == 100_000.00
        # ISR de enero debe ser positivo (con $50k esta en rango progresivo)
        assert isr_enero > 0

    def test_multi_periodo_consistente_acumulado_total(self):
        """
        Multi-periodo 612: el ISR pagado total acumulado debe igualar
        la suma de los ISR a pagar de cada mes (no debe haber doble conteo
        ni perdida por la mecanica acumulativa Art. 106).
        """
        from app.fiscal_engine.multi_periodo import calcular_multi_periodo

        perfil = perfil_actividad_empresarial()
        facturas = [
            CFDI(
                uuid="CONS-ENE", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=40_000.00, total=46_400.00, iva_trasladado=6_400.00,
                metodo_pago="PUE",
            ),
            CFDI(
                uuid="CONS-FEB", fecha=date(2026, 2, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=60_000.00, total=69_600.00, iva_trasladado=9_600.00,
                metodo_pago="PUE",
            ),
        ]
        resultados, acumulado = calcular_multi_periodo(perfil, facturas, 2026, [1, 2])
        # El ISR causado total despues de febrero (con acumulados Jan+Feb)
        # debe igualar la suma de los ISR causados mes a mes.
        suma_causados = sum(r.desglose.isr_causado for r in resultados)
        # Calculo de referencia: tabla x2 sobre $100k base
        isr_total_esperado, _ = calcular_isr_general(100_000, meses_acumulados=2)
        assert round(suma_causados, 2) == round(isr_total_esperado, 2)
        # Los ingresos acumulados de febrero deben coincidir con la suma mes-only
        ene = resultados[0].desglose.total_ingresos_gravados
        feb = resultados[1].desglose.total_ingresos_gravados
        assert resultados[1].desglose.ingresos_acumulados == ene + feb


# ============================================================
# Tests Estado de Cuenta
# ============================================================

class TestEstadoCuenta:
    def test_acumulados_suman_correctamente(self):
        """Los acumulados deben sumar ingresos y egresos de varios meses."""
        from app.fiscal_engine.estado_cuenta import generar_estado_cuenta

        perfil = perfil_actividad_empresarial()
        facturas = [
            # Ingreso enero
            CFDI(
                uuid="EC-001", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=40_000.00, total=46_400.00,
                iva_trasladado=6_400.00, isr_retenido=4_000.00,
            ),
            # Ingreso febrero
            CFDI(
                uuid="EC-002", fecha=date(2025, 2, 15), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=60_000.00, total=69_600.00,
                iva_trasladado=9_600.00, isr_retenido=6_000.00,
            ),
            # Gasto enero
            CFDI(
                uuid="EC-003", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="GOPE900515XYZ",
                subtotal=10_000.00, total=11_600.00, iva_trasladado=1_600.00,
            ),
        ]
        resultado = generar_estado_cuenta(perfil, facturas, 2025)
        assert resultado["ingresos_acumulados"] == 100_000.00
        assert resultado["egresos_acumulados"] == 10_000.00
        assert resultado["isr_retenido_acumulado"] == 10_000.00
        assert resultado["iva_cobrado_acumulado"] == 16_000.00
        assert resultado["mes_mayor_ingreso"] == "Febrero"

    def test_resico_cerca_del_tope_genera_advertencia(self):
        """RESICO con ingresos proyectados cerca del tope genera advertencia."""
        from app.fiscal_engine.estado_cuenta import generar_estado_cuenta

        perfil = PerfilContribuyente(
            rfc="RESI010101AB3",
            regimen="626",
            nombre="Freelancer RESICO",
        )
        # Un solo mes con $300,000 -> proyeccion anual $3.6M > tope $3.5M
        facturas = [
            CFDI(
                uuid="EC-TOPE", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="RESI010101AB3", rfc_receptor="CLIENTE_RFC",
                subtotal=300_000.00, total=348_000.00, iva_trasladado=48_000.00,
            ),
        ]
        resultado = generar_estado_cuenta(perfil, facturas, 2025)
        assert resultado["proyeccion_ingresos_anuales"] == 3_600_000.00
        assert any("tope" in a.lower() or "exceden" in a.lower() for a in resultado["advertencias"])

    def test_estado_cuenta_excluye_ppd_sin_complemento(self):
        """Estado de cuenta respeta flujo de efectivo: PPD sin complemento no suma."""
        from app.fiscal_engine.estado_cuenta import generar_estado_cuenta

        perfil = perfil_actividad_empresarial()
        facturas = [
            # Ingreso PUE
            CFDI(
                uuid="EC-PUE", fecha=date(2025, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="GOPE900515XYZ", rfc_receptor="CLIENTE_RFC",
                subtotal=50_000.00, total=58_000.00, iva_trasladado=8_000.00,
                metodo_pago="PUE",
            ),
            # Gasto PUE
            CFDI(
                uuid="EC-EGR-PUE", fecha=date(2025, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="GOPE900515XYZ",
                subtotal=10_000.00, total=11_600.00, iva_trasladado=1_600.00,
                metodo_pago="PUE",
            ),
            # Gasto PPD sin complemento (NO debe sumar)
            CFDI(
                uuid="EC-EGR-PPD", fecha=date(2025, 1, 8), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR2_RFC", rfc_receptor="GOPE900515XYZ",
                subtotal=20_000.00, total=23_200.00, iva_trasladado=3_200.00,
                metodo_pago="PPD",
            ),
        ]
        resultado = generar_estado_cuenta(perfil, facturas, 2025)
        # Solo PUE cuenta
        assert resultado["ingresos_acumulados"] == 50_000.00
        assert resultado["egresos_acumulados"] == 10_000.00  # PPD excluido


# ============================================================
# Tests Pagos Provisionales Acumulativos (Art. 106)
# ============================================================

class TestTablaAcumulada:
    def test_meses_1_equivale_a_tabla_base(self):
        """generar_tabla_acumulada(1) debe ser igual a TABLA_ISR_MENSUAL."""
        tabla_1 = generar_tabla_acumulada(1)
        for fila_gen, fila_base in zip(tabla_1, TABLA_ISR_MENSUAL):
            assert fila_gen[0] == fila_base[0]  # limite_inferior
            assert fila_gen[1] == fila_base[1]  # limite_superior
            assert fila_gen[2] == fila_base[2]  # cuota_fija
            assert fila_gen[3] == fila_base[3]  # tasa

    def test_meses_2_duplica_limites_y_cuotas(self):
        """generar_tabla_acumulada(2) duplica limites y cuotas, mantiene tasas."""
        tabla_2 = generar_tabla_acumulada(2)
        for fila_gen, fila_base in zip(tabla_2, TABLA_ISR_MENSUAL):
            if fila_base[0] > 0.01:
                assert fila_gen[0] == round(fila_base[0] * 2, 2)
            else:
                assert fila_gen[0] == 0.01
            if fila_base[1] != float("inf"):
                assert fila_gen[1] == round(fila_base[1] * 2, 2)
            else:
                assert fila_gen[1] == float("inf")
            assert fila_gen[2] == round(fila_base[2] * 2, 2)
            assert fila_gen[3] == fila_base[3]  # tasa no cambia


class TestPagosProvisionalesArt106:
    def test_isr_mensual_base_8825_80(self):
        """Base $8,825.80 con meses=1 -> ISR=$601.26 (rango 3 tabla 2026)."""
        isr, tasa = calcular_isr_general(8_825.80, meses_acumulados=1)
        # Rango 3: cuota $420.95 + ($8,825.80 - $7,168.51) x 10.88%
        esperado = round(420.95 + (8_825.80 - 7_168.51) * 0.1088, 2)
        assert isr == esperado

    def test_isr_acumulado_2_meses(self):
        """Base $17,651.60 con meses=2 -> ISR~$1,202.52 (tabla acumulada x2)."""
        isr, tasa = calcular_isr_general(17_651.60, meses_acumulados=2)
        # Tabla x2 (Anexo 8 RMF 2026): rango 3: cuota $841.90 + ($17,651.60 - $14,337.04) x 10.88%
        cuota_acum = round(420.95 * 2, 2)
        lim_inf_acum = round(7_168.52 * 2, 2)
        esperado = round(cuota_acum + (17_651.60 - lim_inf_acum) * 0.1088, 2)
        assert isr == esperado

    def test_pagos_provisionales_anteriores_se_restan(self):
        """En febrero, si ya pago ISR en enero, se resta del ISR acumulado."""
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        # Art. 106: la tabla acumulada x2 requiere que las facturas cubran
        # tambien enero. Se incluyen ambos meses para satisfacer el safeguard.
        factura_ene = CFDI(
            uuid="F0", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        factura_feb = CFDI(
            uuid="F1", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        facturas = [factura_ene, factura_feb]
        desglose_sin = calcular_declaracion(
            perfil, facturas, periodo_month=2, pagos_provisionales_anteriores=0,
        )
        desglose_con = calcular_declaracion(
            perfil, facturas, periodo_month=2, pagos_provisionales_anteriores=5_000,
        )
        assert desglose_con.isr_causado == desglose_sin.isr_causado - 5_000

    def test_pagos_anteriores_no_generan_negativo(self):
        """Si pagos anteriores > ISR causado, resultado es 0 (no negativo)."""
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        # Incluir factura de enero para que el safeguard Art. 106 permita
        # tabla acumulada x2 (y por tanto restar pagos anteriores).
        factura_ene = CFDI(
            uuid="F2-ENE", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PUE",
        )
        factura_feb = CFDI(
            uuid="F2", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PUE",
        )
        desglose = calcular_declaracion(
            perfil,
            [factura_ene, factura_feb],
            periodo_month=2,
            pagos_provisionales_anteriores=999_999,
        )
        assert desglose.isr_causado >= 0

    def test_612_tabla_acumulada_requiere_facturas_acumuladas(self):
        """
        Art. 106: con facturas que cubren enero Y febrero, periodo_month=2
        debe usar tabla acumulada x2 sobre la base acumulada de ambos meses.
        """
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        factura_ene = CFDI(
            uuid="ACUM-ENE", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        factura_feb = CFDI(
            uuid="ACUM-FEB", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        desglose = calcular_declaracion(
            perfil, [factura_ene, factura_feb], periodo_month=2,
        )
        # Base acumulada de ambos meses
        assert desglose.base_isr == 200_000
        # ISR debe corresponder a la tabla acumulada x2 sobre la base 200_000,
        # NO a la tabla mensual simple.
        isr_acumulado, _ = calcular_isr_general(200_000, meses_acumulados=2)
        isr_mensual, _ = calcular_isr_general(200_000, meses_acumulados=1)
        assert desglose.isr_causado == isr_acumulado
        assert isr_acumulado != isr_mensual  # las tablas deben diferir

    def test_612_solo_facturas_mes_actual_usa_tabla_simple(self):
        """
        Safeguard Art. 106: si solo hay facturas del mes actual (febrero) y
        ninguna de enero, la tabla acumulada x2 NO puede aplicarse sobre una
        base incompleta. El motor debe forzar tabla mensual simple (meses=1)
        y NO restar pagos provisionales anteriores.
        """
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        factura_feb = CFDI(
            uuid="FEB-ONLY", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        desglose = calcular_declaracion(
            perfil,
            [factura_feb],
            periodo_month=2,
            pagos_provisionales_anteriores=5_000,
        )
        # El safeguard debe forzar meses=1
        isr_mensual, _ = calcular_isr_general(100_000, meses_acumulados=1)
        assert desglose.isr_causado == isr_mensual
        # Y NO debe restar pagos provisionales anteriores (solo aplican
        # cuando se uso tabla acumulada).
        assert desglose.pagos_provisionales_anteriores == 0
        # Debe ser distinto del calculo erroneo con tabla x2
        isr_acumulado_mal, _ = calcular_isr_general(100_000, meses_acumulados=2)
        assert desglose.isr_causado != isr_acumulado_mal

    def test_612_acumulado_con_ingresos_anteriores(self):
        """
        Nuevo flujo Art. 106: el caller pasa solo facturas del mes actual
        + totales acumulados explicitos. El motor suma los acumulados a la
        base ISR pero mantiene total_ingresos_gravados como mes-only.
        """
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        factura_feb = CFDI(
            uuid="FEB-NEW", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        desglose = calcular_declaracion(
            perfil,
            [factura_feb],
            periodo_month=2,
            ingresos_acumulados_anteriores=80_000,
            deducciones_acumuladas_anteriores=20_000,
            pagos_provisionales_anteriores=2_000,
        )
        # Mes only: ingresos $100k, deducciones $0
        assert desglose.total_ingresos_gravados == 100_000
        assert desglose.total_deducciones_autorizadas == 0
        # Acumulados: $100k + $80k = $180k ingresos, $0 + $20k = $20k deducciones
        assert desglose.ingresos_acumulados == 180_000
        assert desglose.deducciones_acumuladas == 20_000
        # Base ISR acumulada: $180k - $20k = $160k
        assert desglose.base_isr == 160_000
        # ISR debe usar tabla acumulada x2 sobre la base, menos pagos anteriores
        isr_acum, _ = calcular_isr_general(160_000, meses_acumulados=2)
        assert desglose.isr_causado == max(round(isr_acum, 2) - 2_000, 0)
        assert desglose.pagos_provisionales_anteriores == 2_000

    def test_612_mes1_ignora_acumulados_anteriores(self):
        """En enero (mes 1) no se aplican acumulados aunque se manden."""
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        factura_ene = CFDI(
            uuid="ENE-NEW", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        desglose = calcular_declaracion(
            perfil,
            [factura_ene],
            periodo_month=1,
            ingresos_acumulados_anteriores=999_999,
            deducciones_acumuladas_anteriores=999_999,
        )
        # Mes 1: solo cuenta el mes actual
        assert desglose.base_isr == 100_000
        assert desglose.ingresos_acumulados == 0
        assert desglose.deducciones_acumuladas == 0

    def test_612_sin_acumulados_explicitos_backward_compat(self):
        """Con acumulados=0 el resultado debe ser identico al flujo legacy."""
        perfil = PerfilContribuyente(rfc="EMPR010101AB1", regimen="612", nombre="Empresario")
        # Facturas que cubren enero y febrero (legacy path activo)
        factura_ene = CFDI(
            uuid="BC-ENE", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        factura_feb = CFDI(
            uuid="BC-FEB", fecha=date(2026, 2, 15), tipo=TipoFactura.INGRESO,
            rfc_emisor="EMPR010101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=100_000, total=116_000, iva_trasladado=16_000,
            metodo_pago="PUE",
        )
        desglose_legacy = calcular_declaracion(
            perfil, [factura_ene, factura_feb], periodo_month=2,
        )
        desglose_explicit = calcular_declaracion(
            perfil, [factura_ene, factura_feb], periodo_month=2,
            ingresos_acumulados_anteriores=0,
            deducciones_acumuladas_anteriores=0,
        )
        assert desglose_legacy.base_isr == desglose_explicit.base_isr
        assert desglose_legacy.isr_causado == desglose_explicit.isr_causado


# ============================================================
# Tests Flujo de Efectivo PUE/PPD (Art. 102 LISR)
# ============================================================

class TestFlujoEfectivo:
    """Tests para logica PUE/PPD (Art. 102 LISR)."""

    def test_factura_pue_se_acumula(self):
        """Factura PUE se cuenta como ingreso inmediatamente."""
        factura = CFDI(
            uuid="PUE-001", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="AAA000000AA0", rfc_receptor="BBB000000BB0",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PUE",
        )
        ingresos, egresos = clasificar_facturas([factura], "AAA000000AA0")
        assert len(ingresos) == 1
        assert ingresos[0].subtotal == 10_000

    def test_factura_ppd_no_se_acumula(self):
        """Factura PPD NO se cuenta hasta que llegue complemento de pago."""
        factura = CFDI(
            uuid="PPD-100", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="AAA000000AA0", rfc_receptor="BBB000000BB0",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PPD",
        )
        ingresos, egresos = clasificar_facturas([factura], "AAA000000AA0")
        assert len(ingresos) == 0

    def test_ppd_con_complemento_se_acumula(self):
        """Factura PPD + complemento de pago -> se acumula con fecha del pago."""
        factura_ppd = CFDI(
            uuid="PPD-101", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="AAA000000AA0", rfc_receptor="BBB000000BB0",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PPD",
        )
        complemento = CFDI(
            uuid="REP-101", fecha=date(2026, 1, 15), tipo=TipoFactura.PAGO,
            rfc_emisor="BBB000000BB0", rfc_receptor="AAA000000AA0",
            subtotal=0, total=0,
            metodo_pago="PUE",
            uuid_relacionado="PPD-101",
            monto_pago=11_600,
        )
        ingresos, egresos = clasificar_facturas(
            [factura_ppd, complemento], "AAA000000AA0",
        )
        assert len(ingresos) == 1
        assert ingresos[0].subtotal == 10_000
        assert ingresos[0].fecha == date(2026, 1, 15)

    def test_ppd_pago_parcial(self):
        """Complemento de pago parcial -> solo acumula la proporcion pagada."""
        factura_ppd = CFDI(
            uuid="PPD-102", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="AAA000000AA0", rfc_receptor="BBB000000BB0",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            metodo_pago="PPD",
        )
        complemento = CFDI(
            uuid="REP-102", fecha=date(2026, 1, 20), tipo=TipoFactura.PAGO,
            rfc_emisor="BBB000000BB0", rfc_receptor="AAA000000AA0",
            subtotal=0, total=0,
            metodo_pago="PUE",
            uuid_relacionado="PPD-102",
            monto_pago=5_800,  # 50% del total
        )
        ingresos, egresos = clasificar_facturas(
            [factura_ppd, complemento], "AAA000000AA0",
        )
        assert len(ingresos) == 1
        assert ingresos[0].subtotal == 5_000  # 50% del subtotal
        assert ingresos[0].iva_trasladado == 800  # 50% del IVA

    def test_ppd_gasto_sin_complemento_no_deducible(self):
        """Gasto PPD sin complemento de pago NO es deducible."""
        factura_ppd = CFDI(
            uuid="PPD-103", fecha=date(2026, 1, 9), tipo=TipoFactura.INGRESO,
            rfc_emisor="BBB000000BB0", rfc_receptor="AAA000000AA0",
            subtotal=8_295, total=9_622.20, iva_trasladado=1_327.20,
            metodo_pago="PPD",
        )
        ingresos, egresos = clasificar_facturas([factura_ppd], "AAA000000AA0")
        assert len(egresos) == 0


# ============================================================
# Test Caso Real: CADG620317EE0 Enero 2026
# ============================================================

class TestCasoRealCADG:
    """
    Verificacion con datos del cliente CADG620317EE0, enero 2026.
    Regimen 612 (Act. Empresarial). Valida que PUE/PPD + Art. 106
    produzcan el ISR correcto de $1,782.87.
    """

    def test_declaracion_enero_2026(self):
        """
        33 facturas PUE gastos ($186,440.56) + 1 PPD sin complemento ($8,295)
        + 1 PPD con complemento ($4,542.99) + 1 PUE ingreso ($208,104.35)
        -> Base ISR $17,120.80 -> ISR $1,782.87
        """
        perfil = PerfilContribuyente(
            rfc="CADG620317EE0",
            regimen="612",
            nombre="Contribuyente Caso Real",
        )

        facturas: list[CFDI] = []

        # --- 1 factura PUE emitida (ingreso del contribuyente) ---
        facturas.append(CFDI(
            uuid="ING-PUE-001", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="CADG620317EE0", rfc_receptor="CLIENTE_RFC_001",
            subtotal=208_104.35, total=241_401.05,
            iva_trasladado=33_296.70,
            metodo_pago="PUE",
        ))

        # --- 33 facturas PUE recibidas (gastos): subtotal neto = $186,440.56 ---
        # Simplificadas en 3 facturas con el mismo total neto
        facturas.append(CFDI(
            uuid="EGR-PUE-001", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="PROVEEDOR_A_RFC", rfc_receptor="CADG620317EE0",
            subtotal=80_000.00, total=92_800.00, iva_trasladado=12_800.00,
            metodo_pago="PUE",
        ))
        facturas.append(CFDI(
            uuid="EGR-PUE-002", fecha=date(2026, 1, 12), tipo=TipoFactura.INGRESO,
            rfc_emisor="PROVEEDOR_B_RFC", rfc_receptor="CADG620317EE0",
            subtotal=70_000.00, total=81_200.00, iva_trasladado=11_200.00,
            metodo_pago="PUE",
        ))
        facturas.append(CFDI(
            uuid="EGR-PUE-003", fecha=date(2026, 1, 20), tipo=TipoFactura.INGRESO,
            rfc_emisor="PROVEEDOR_C_RFC", rfc_receptor="CADG620317EE0",
            subtotal=36_440.56, total=42_271.05, iva_trasladado=5_830.49,
            metodo_pago="PUE",
        ))

        # --- 1 factura PPD de MXGA CONTADORES sin complemento (NO deducible) ---
        facturas.append(CFDI(
            uuid="PPD-MXGA", fecha=date(2026, 1, 8), tipo=TipoFactura.INGRESO,
            rfc_emisor="MXGA_CONTADORES", rfc_receptor="CADG620317EE0",
            subtotal=8_295.00, total=9_622.20, iva_trasladado=1_327.20,
            metodo_pago="PPD",
        ))

        # --- 1 factura PPD de BRIGHT MEXICO con complemento (SI deducible) ---
        facturas.append(CFDI(
            uuid="PPD-BRIGHT", fecha=date(2026, 1, 3), tipo=TipoFactura.INGRESO,
            rfc_emisor="BRIGHT_MEXICO", rfc_receptor="CADG620317EE0",
            subtotal=4_542.99, total=5_269.87, iva_trasladado=726.88,
            metodo_pago="PPD",
        ))
        # Complemento de pago por el 100% del total de BRIGHT
        facturas.append(CFDI(
            uuid="REP-BRIGHT", fecha=date(2026, 1, 18), tipo=TipoFactura.PAGO,
            rfc_emisor="CADG620317EE0", rfc_receptor="BRIGHT_MEXICO",
            subtotal=0, total=0,
            uuid_relacionado="PPD-BRIGHT",
            monto_pago=5_269.87,
        ))

        # Calcular declaracion enero 2026, regimen 612
        desglose = calcular_declaracion(
            perfil, facturas, es_anual=False, periodo_month=1,
        )

        # Ingresos: solo la PUE emitida
        assert desglose.total_ingresos_gravados == 208_104.35

        # Deducciones: PUE gastos + BRIGHT via complemento, NO MXGA
        assert desglose.total_deducciones_autorizadas == 190_983.55

        # Base ISR
        assert desglose.base_isr == 17_120.80

        # ISR rango 5 tabla 2026 (Anexo 8): cuota $1,339.14 + ($17,120.80 - $14,644.65) x 17.92%
        assert desglose.isr_causado == 1_782.87


# ============================================================
# Tests IVA Acreditable (Art. 5 LIVA)
# ============================================================

class TestIVAAcreditable:
    """Verifica que el IVA se tome del XML (no recalculado) y respete flujo de efectivo."""

    def test_iva_usa_valor_xml_no_recalcula(self):
        """
        CFDI con descuento: subtotal=1000, descuento=400, iva_trasladado=96.
        El IVA es 16% de $600 (base neta), no de $1,000.
        Verificar que se use el valor del XML ($96), no base_gravable * 0.16.
        """
        perfil = PerfilContribuyente(
            rfc="TEST010101AB1", regimen="612", nombre="Test IVA",
        )
        facturas = [
            # Ingreso emitido
            CFDI(
                uuid="IVA-ING-001", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="TEST010101AB1", rfc_receptor="CLIENTE_RFC",
                subtotal=5_000.00, total=5_800.00, iva_trasladado=800.00,
                metodo_pago="PUE",
            ),
            # Gasto con descuento: IVA calculado sobre base neta (600), no subtotal (1000)
            CFDI(
                uuid="IVA-EGR-001", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="TEST010101AB1",
                subtotal=1_000.00, total=696.00, descuento=400.00,
                iva_trasladado=96.00,
                metodo_pago="PUE",
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas, periodo_month=1)

        # IVA cobrado = $800 (del ingreso)
        assert desglose.iva_trasladado_cobrado == 800.00
        # IVA acreditable = $96 (valor del XML, no 1000*0.16=160 ni 600*0.16=96)
        assert desglose.iva_trasladado_pagado == 96.00
        # IVA a pagar = 800 - 96 = 704
        assert desglose.iva_a_pagar == 704.00

    def test_iva_ppd_sin_complemento_no_acreditable(self):
        """IVA de factura PPD sin complemento NO es acreditable (Art. 5 LIVA)."""
        perfil = PerfilContribuyente(
            rfc="TEST010101AB1", regimen="612", nombre="Test IVA PPD",
        )
        facturas = [
            CFDI(
                uuid="IVA-ING-002", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
                rfc_emisor="TEST010101AB1", rfc_receptor="CLIENTE_RFC",
                subtotal=10_000.00, total=11_600.00, iva_trasladado=1_600.00,
                metodo_pago="PUE",
            ),
            # Gasto PPD: IVA NO acreditable sin complemento
            CFDI(
                uuid="IVA-PPD-001", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
                rfc_emisor="PROVEEDOR_RFC", rfc_receptor="TEST010101AB1",
                subtotal=5_000.00, total=5_800.00, iva_trasladado=800.00,
                metodo_pago="PPD",
            ),
        ]
        desglose = calcular_declaracion(perfil, facturas, periodo_month=1)

        # IVA cobrado = $1,600
        assert desglose.iva_trasladado_cobrado == 1_600.00
        # IVA acreditable = $0 (PPD sin complemento)
        assert desglose.iva_trasladado_pagado == 0.00
        # IVA a pagar = 1,600 - 0 = 1,600
        assert desglose.iva_a_pagar == 1_600.00

    def test_resico_iva_no_acredita_gastos_personales(self):
        """RESICO: IVA de gastos personales NO es acreditable (Art. 5-I LIVA)."""
        perfil = PerfilContribuyente(
            rfc="RESI020101AB1", regimen="626", nombre="Plomero RESICO",
        )
        ingreso = CFDI(
            uuid="R-ING", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="RESI020101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            clave_prod_serv="72151500", metodo_pago="PUE",
        )
        gasto_negocio = CFDI(
            uuid="R-NEG", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="FERR123", rfc_receptor="RESI020101AB1",
            subtotal=1_000, total=1_160, iva_trasladado=160,
            clave_prod_serv="27111700", metodo_pago="PUE",  # Herramientas -> deducible
        )
        gasto_personal = CFDI(
            uuid="R-PER", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="SUPER123", rfc_receptor="RESI020101AB1",
            subtotal=2_000, total=2_320, iva_trasladado=320,
            clave_prod_serv="50000000", metodo_pago="PUE",  # Alimentos -> personal
        )
        desglose = calcular_declaracion(
            perfil, [ingreso, gasto_negocio, gasto_personal],
        )
        # ISR: RESICO no deduce
        assert desglose.base_isr == 10_000
        assert desglose.total_deducciones_autorizadas == 0
        # IVA: solo herramienta, NO super
        assert desglose.iva_trasladado_cobrado == 1_600
        assert desglose.iva_trasladado_pagado == 160
        assert desglose.iva_a_pagar == 1_440
        # Gastos personales excluidos
        assert desglose.gastos_personales_excluidos == 2_000
        assert desglose.cantidad_gastos_personales == 1

    def test_resico_isr_no_cambia_con_clasificador(self):
        """Agregar 626 al clasificador no afecta el ISR de RESICO."""
        perfil = PerfilContribuyente(
            rfc="RESI020101AB1", regimen="626", nombre="Plomero",
        )
        ingreso = CFDI(
            uuid="R2-ING", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="RESI020101AB1", rfc_receptor="CLIE010101AB1",
            subtotal=50_000, total=58_000, iva_trasladado=8_000,
            clave_prod_serv="72151500", metodo_pago="PUE",
        )
        gasto = CFDI(
            uuid="R2-G", fecha=date(2026, 1, 10), tipo=TipoFactura.INGRESO,
            rfc_emisor="PROV123", rfc_receptor="RESI020101AB1",
            subtotal=10_000, total=11_600, iva_trasladado=1_600,
            clave_prod_serv="27111700", metodo_pago="PUE",
        )
        desglose = calcular_declaracion(perfil, [ingreso, gasto])
        # ISR RESICO: tasa 1.10% sobre $50,000 brutos (rango $25k-$50k)
        assert desglose.isr_causado == 550.0
        assert desglose.total_deducciones_autorizadas == 0
        assert desglose.base_isr == 50_000
