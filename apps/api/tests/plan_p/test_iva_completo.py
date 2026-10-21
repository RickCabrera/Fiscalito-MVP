"""P3-03: IVA completo. "Listo cuando": un saldo a favor de un mes se acredita en el siguiente."""

from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.fiscal_engine.iva import ConfigIVA, MovimientoIVA, calcular_iva_mes, calcular_iva_periodos


def cobro(uuid, base, iva=None, **kw):
    return MovimientoIVA(uuid, "emitido", base_16=D(base),
                         iva_16=D(iva) if iva else D(base) * D("0.16"), **kw)


def gasto(uuid, base, iva=None, **kw):
    return MovimientoIVA(uuid, "recibido", base_16=D(base),
                         iva_16=D(iva) if iva else D(base) * D("0.16"), **kw)


def test_saldo_a_favor_se_acredita_el_mes_siguiente():
    movs = {
        1: [cobro("A", "10000"), gasto("B", "30000")],   # 1,600 - 4,800 → a favor 3,200
        2: [cobro("C", "20000"), gasto("D", "5000")],    # 3,200 - 800 = 2,400 → aplica 2,400
        3: [cobro("E", "10000")],                        # 1,600 - 800 restante = 800
    }
    ene, feb, mar = calcular_iva_periodos(2026, [1, 2, 3], movs)
    assert ene.iva_a_pagar == 0 and ene.saldo_favor_del_mes == D("3200.00")
    assert ene.saldo_favor_siguiente == D("3200.00")
    assert feb.saldo_favor_anterior == D("3200.00") and feb.saldo_favor_aplicado == D("2400.00")
    assert feb.iva_a_pagar == 0 and feb.saldo_favor_siguiente == D("800.00")
    assert mar.saldo_favor_aplicado == D("800.00") and mar.iva_a_pagar == D("800.00")
    assert mar.saldo_favor_siguiente == 0


def test_devolucion_es_sobre_el_total_y_ya_no_se_acredita():
    movs = {1: [cobro("A", "1000"), gasto("B", "5000")], 2: [cobro("C", "10000")]}
    ene, feb = calcular_iva_periodos(2026, [1, 2], movs, D("100"),
                                     opciones_saldo={1: "devolucion"})
    assert ene.saldo_favor_solicitado == D("740.00")  # 100 anterior + 640 del mes (Art. 6o.)
    assert ene.saldo_favor_siguiente == 0
    assert feb.saldo_favor_anterior == 0 and feb.iva_a_pagar == D("1600.00")


def test_proporcion_con_actos_exentos():
    # 60,000 gravados al 16 % + 20,000 al 0 % + 20,000 exentos → proporción 0.8000.
    movs = [
        cobro("A", "60000"), MovimientoIVA("B", "emitido", base_0=D("20000")),
        MovimientoIVA("C", "emitido", base_exento=D("20000")),
        gasto("G1", "10000"),                               # indistinto: 1,600 × 0.8
        gasto("G2", "5000"),                                # identificado gravado: 800 total
        gasto("G3", "2500"),                                # identificado exento: 0
    ]
    r = calcular_iva_mes(2026, 4, movs, asignaciones={"G2": "gravado", "G3": "exento"})
    assert r.proporcion == D("0.8000")
    assert r.iva_acreditable_proporcional == D("1280.00")
    assert r.iva_acreditable_identificado == D("800.00")
    assert r.iva_no_acreditable_exentos == D("400.00")
    assert r.iva_acreditable == D("2080.00")
    assert r.iva_a_pagar == D("9600.00") - D("2080.00")


def test_proporcion_fija_art_5c():
    movs = [cobro("A", "1000"), MovimientoIVA("B", "emitido", base_exento=D("9000")),
            gasto("G", "1000")]
    r = calcular_iva_mes(2026, 4, movs, config=ConfigIVA(proporcion_modo="fija",
                                                          proporcion_fija=D("0.5")))
    assert r.proporcion == D("0.5") and r.iva_acreditable == D("80.00")
    with pytest.raises(FiscalValidationError):
        calcular_iva_mes(2026, 4, movs, config=ConfigIVA(proporcion_modo="fija"))


def test_retenciones_y_8_por_ciento():
    movs = [
        MovimientoIVA("A", "emitido", base_8=D("1000"), iva_8=D("80"), iva_retenido=D("20")),
        MovimientoIVA("B", "recibido", base_16=D("1000"), iva_16=D("160"),
                      iva_retenido=D("106.67")),
    ]
    r = calcular_iva_mes(2026, 4, movs)
    assert r.iva_trasladado_cobrado == D("80.00") and r.iva_retenido_por_clientes == D("20.00")
    assert r.iva_retenido_a_terceros == D("106.67")
    assert any("fronteriza" in n for n in r.notas)
    sin_nota = calcular_iva_mes(2026, 4, movs, config=ConfigIVA(region_fronteriza=True))
    assert not any("fronteriza" in n for n in sin_nota.notas)


def test_notas_de_credito_y_no_deducibles():
    movs = [cobro("A", "1000"), cobro("NC", "200", signo=-1),
            gasto("P", "500", deducible=False)]
    r = calcular_iva_mes(2026, 4, movs)
    assert r.iva_trasladado_cobrado == D("128.00")
    assert r.iva_acreditable == 0 and r.iva_pagado_no_deducible == D("80.00")
