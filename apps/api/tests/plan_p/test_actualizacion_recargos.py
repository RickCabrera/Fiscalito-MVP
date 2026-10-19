"""
P3-02: actualización (Art. 17-A CFF) y recargos (Art. 21 CFF).

"Listo cuando": un impuesto pagado tarde calcula actualización y recargos como el ejemplo
oficial/publicado. El caso de referencia es el de sdv.com.mx/herramientas/calculadora-recargos:
$25,000 con INPC 145.169 (jul-2026) / 143.588 (ene-2026) → $25,275.27 con el cociente sin
cortar (y $25,275.00 con el factor 1.0110 cortado al diezmilésimo).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.fiscal_engine import inpc as modulo_inpc
from app.fiscal_engine.actualizacion import (
    ajustar_a_pesos,
    calcular_actualizacion_recargos,
    cortar_diezmilesimo,
    factor_actualizacion,
    fecha_limite_mensual,
    meses_de_mora,
    tasa_mensual,
)


def test_serie_inpc_cotejada_contra_boletines_inegi():
    # Valores citados textualmente de los boletines del INEGI (ver datos/inpc.csv).
    esperados = {(2024, 12): "137.949", (2025, 6): "140.405", (2025, 12): "143.042",
                 (2026, 1): "143.588", (2026, 3): "145.544", (2026, 6): "145.131",
                 (2026, 7): "145.169", (2026, 8): "145.462", (2026, 9): "146.075"}
    for (a, m), v in esperados.items():
        fila = modulo_inpc.inpc(a, m)
        assert fila.valor == D(v) and fila.verificacion == "boletin_inegi"
    serie = modulo_inpc.serie_inpc()
    assert min(serie) == (2020, 1) and len(serie) == 81  # completa de ene-2020 a sep-2026


def test_ejemplo_publicado_25000():
    f = factor_actualizacion(date(2026, 2, 17), date(2026, 8, 10), "truncar")
    assert (f.inpc_reciente, f.inpc_antiguo) == (D("145.169"), D("143.588"))
    assert (f.mes_inpc_reciente, f.mes_inpc_antiguo) == ("2026-07", "2026-01")
    assert f.factor == D("1.0110")
    sin_cortar = calcular_actualizacion_recargos(
        D("25000"), date(2026, 2, 17), date(2026, 8, 10), modo_factor="sin_redondeo")
    assert sin_cortar.monto_actualizado == D("25275.27")  # cifra del ejemplo publicado
    truncado = calcular_actualizacion_recargos(D("25000"), date(2026, 2, 17), date(2026, 8, 10))
    assert truncado.monto_actualizado == D("25275.00")
    # 6 meses o fracción (18-feb … 10-ago) a 2.07 % (LIF 2026 1.38 % × 1.5, Art. 21 CFF).
    assert truncado.meses == 6 and truncado.tasa_acumulada == D("0.1242")
    assert truncado.recargos == D("3139.16")  # 25,275.00 × 12.42 %
    assert truncado.total == D("28414.16") and truncado.total_a_pagar_ajustado == D("28414")


def test_tasa_mora_es_prorroga_mas_50_por_ciento():
    assert tasa_mensual(2026, "prorroga") == D("0.0138")
    assert tasa_mensual(2026, "mora") == D("0.0207")
    assert tasa_mensual(2025, "mora") == D("0.0147")
    assert tasa_mensual(2026, "parcialidades_mas_24") == D("0.0197")
    with pytest.raises(FiscalValidationError):
        tasa_mensual(2019, "mora")


def test_mes_o_fraccion():
    assert meses_de_mora(date(2026, 2, 17), date(2026, 2, 17)) == 0
    assert meses_de_mora(date(2026, 2, 17), date(2026, 2, 18)) == 1
    assert meses_de_mora(date(2026, 2, 17), date(2026, 3, 17)) == 1
    assert meses_de_mora(date(2026, 2, 17), date(2026, 3, 18)) == 2
    assert meses_de_mora(date(2026, 1, 31), date(2026, 2, 28)) == 1


def test_cruce_de_anio_usa_la_tasa_de_cada_anio():
    r = calcular_actualizacion_recargos(D("1000"), date(2025, 11, 17), date(2026, 1, 20))
    tasas = [m.tasa for m in r.detalle_meses]
    assert tasas == [D("0.0147"), D("0.0147"), D("0.0207")]


def test_factor_menor_a_uno_se_toma_uno():
    # INPC abr-2026 145.831 > may-2026 145.527 → pagar en jun por vencimiento de may da < 1.
    r = calcular_actualizacion_recargos(D("1000"), date(2026, 5, 17), date(2026, 6, 10))
    assert r.factor.factor_menor_a_uno and r.factor.factor == 1 and r.actualizacion == 0
    assert r.recargos == D("20.70")


def test_inpc_no_publicado_usa_el_ultimo():
    r = calcular_actualizacion_recargos(D("1000"), date(2026, 9, 17), date(2026, 12, 1))
    assert r.factor.se_uso_ultimo_publicado and r.factor.mes_inpc_reciente == "2026-09"


def test_tope_cinco_anios():
    r = calcular_actualizacion_recargos(D("100"), date(2020, 2, 17), date(2026, 9, 1))
    assert r.meses == 60 and r.meses_topados


def test_pagado_en_plazo_no_genera_accesorios():
    r = calcular_actualizacion_recargos(D("100.50"), date(2026, 3, 17), date(2026, 3, 17))
    assert (r.actualizacion, r.recargos, r.total) == (0, 0, D("100.50"))
    assert r.total_a_pagar_ajustado == D("100")


def test_redondeos():
    assert cortar_diezmilesimo(D("1.01109"), "truncar") == D("1.0110")
    assert cortar_diezmilesimo(D("1.01105"), "redondear") == D("1.0111")
    assert ajustar_a_pesos(D("10.50")) == 10 and ajustar_a_pesos(D("10.51")) == 11


def test_fecha_limite_dia_17_habil():
    assert fecha_limite_mensual(2026, 1) == date(2026, 2, 17)
    assert fecha_limite_mensual(2026, 4) == date(2026, 5, 18)  # 17-may-2026 es domingo
    assert fecha_limite_mensual(2026, 12) == date(2027, 1, 18)  # 17-ene-2027 es domingo
