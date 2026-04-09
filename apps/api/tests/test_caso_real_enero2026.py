"""
Test caso real: cliente CADG620317EE0, enero 2026, regimen 612.

Valida el flujo completo de PUE/PPD con complementos de pago,
pagos provisionales Art. 106, e IVA a flujo de efectivo (Art. 5 LIVA).

Ejecutar: pytest tests/test_caso_real_enero2026.py -v
"""

from datetime import date
from app.schemas.fiscal import PerfilContribuyente, CFDI, TipoFactura
from app.fiscal_engine.calculadora import calcular_declaracion


def _perfil_cadg() -> PerfilContribuyente:
    return PerfilContribuyente(
        rfc="CADG620317EE0",
        regimen="612",
        nombre="CADG Caso Real",
    )


def _facturas_enero_2026() -> list[CFDI]:
    facturas: list[CFDI] = []

    # --- INGRESO: 1 factura PUE emitida ---
    facturas.append(CFDI(
        uuid="18DCD0B7", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
        rfc_emisor="CADG620317EE0", rfc_receptor="RIX150930NF1",
        subtotal=208_104.35, total=219_203.18,
        iva_trasladado=33_296.70, iva_retenido=22_197.87, isr_retenido=0,
        metodo_pago="PUE",
    ))

    # --- GASTOS PUE: 33 facturas consolidadas en 1 ---
    facturas.append(CFDI(
        uuid="PUE-CONSOLIDADO", fecha=date(2026, 1, 15), tipo=TipoFactura.INGRESO,
        rfc_emisor="PROVEEDORES_VARIOS", rfc_receptor="CADG620317EE0",
        subtotal=186_440.56, total=207_941.05, iva_trasladado=21_500.49,
        metodo_pago="PUE",
    ))

    # --- GASTO PPD: MXGA Contadores SIN complemento (NO deducible) ---
    facturas.append(CFDI(
        uuid="A4CC9220", fecha=date(2026, 1, 9), tipo=TipoFactura.INGRESO,
        rfc_emisor="MCP2404207Q2", rfc_receptor="CADG620317EE0",
        subtotal=8_295.00, total=9_622.20, iva_trasladado=1_327.20,
        metodo_pago="PPD",
    ))

    # --- GASTO PPD: Bright Mexico CON complemento (SI deducible) ---
    facturas.append(CFDI(
        uuid="4C059A14", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
        rfc_emisor="BMS170308GT7", rfc_receptor="CADG620317EE0",
        subtotal=4_542.99, total=5_269.87, iva_trasladado=726.88,
        metodo_pago="PPD",
    ))

    # --- COMPLEMENTO DE PAGO para Bright ---
    facturas.append(CFDI(
        uuid="727F3352", fecha=date(2026, 1, 1), tipo=TipoFactura.PAGO,
        rfc_emisor="BMS170308GT7", rfc_receptor="CADG620317EE0",
        subtotal=0, total=0,
        metodo_pago="PUE",
        uuid_relacionado="4C059A14",
        monto_pago=5_269.87,
    ))

    return facturas


class TestCasoRealEnero2026:
    """Verificacion completa del caso CADG620317EE0 enero 2026."""

    def test_ingresos(self):
        """Solo la factura PUE emitida cuenta como ingreso."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        assert desglose.total_ingresos_gravados == 208_104.35
        assert desglose.cantidad_facturas_ingreso == 1

    def test_deducciones_efectivas(self):
        """PUE gastos + Bright pagado. MXGA sin complemento NO se deduce."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # $186,440.56 (PUE) + $4,542.99 (Bright PPD pagado) = $190,983.55
        assert desglose.total_deducciones_autorizadas == 190_983.55
        # MXGA ($8,295) excluido
        assert desglose.total_egresos == 190_983.55
        # 1 PUE consolidado + 1 Bright via complemento = 2
        assert desglose.cantidad_facturas_egreso == 2

    def test_base_isr(self):
        """Base = ingresos - deducciones efectivas."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # $208,104.35 - $190,983.55 = $17,120.80
        assert desglose.base_isr == 17_120.80

    def test_isr_causado(self):
        """ISR tabla enero 2026 (Anexo 8 RMF), rango $14,644.65 - $17,533.64."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # Cuota $1,339.14 + ($17,120.80 - $14,644.65) x 17.92% = $1,782.87
        assert desglose.isr_causado == 1_782.87
        # Sin retenciones ISR, isr_a_pagar = isr_causado
        assert desglose.isr_retenido == 0.0
        assert desglose.isr_a_pagar == 1_782.87

    def test_iva_cobrado(self):
        """IVA trasladado cobrado = IVA de la factura de ingreso."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        assert desglose.iva_trasladado_cobrado == 33_296.70

    def test_iva_acreditable(self):
        """IVA acreditable = PUE gastos + Bright pagado. MXGA excluido."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # $21,500.49 (PUE) + $726.88 (Bright pagado) = $22,227.37
        assert desglose.iva_trasladado_pagado == 22_227.37

    def test_iva_retenido(self):
        """IVA retenido por el cliente al contribuyente."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        assert desglose.iva_retenido == 22_197.87

    def test_iva_saldo_a_favor(self):
        """IVA a pagar negativo = saldo a favor."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # $33,296.70 - $22,227.37 - $22,197.87 = -$11,128.54
        assert desglose.iva_a_pagar == -11_128.54

    def test_total_a_pagar(self):
        """Total = ISR a pagar + max(IVA, 0). IVA negativo no se suma."""
        desglose = calcular_declaracion(
            _perfil_cadg(), _facturas_enero_2026(), periodo_month=1,
        )
        # ISR $1,782.87 + IVA $0 (saldo a favor, no se suma) = $1,782.87
        assert desglose.total_a_pagar == 1_782.87
