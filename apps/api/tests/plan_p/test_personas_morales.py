"""
P3-01: motor de personas morales (601) y RESICO PM — casos de resultado conocido.

Fuentes de los casos (ver `knowledge_base/16_personas_morales.md`):
- Coeficiente de utilidad y pago provisional de marzo: siemprealdia.co, "Coeficiente de
  utilidad: ¿Cómo determinarlo y aplicarlo en pagos provisionales de ISR?" (2026):
  2,700,000 / 12,150,000 = 0.2222; marzo: 3,800,000 × 0.1845 = 701,100 − 150,000 de pérdida
  = 551,100 × 30 % = 165,330 − 95,000 − 5,000 = 65,330. Y su tabla de utilidad estimada
  enero-abril (202,950 / 433,575 / 701,100 / 922,500).
- Ajuste anual por inflación con promedios dados: contadormx.com, "Cálculo del ajuste anual
  por inflación acumulable o deducible": (1,250,000 − 1,000,000) × 0.0045 = 1,125 acumulable;
  (1,250,000 − 900,000) × 0.0045 = 1,575 deducible.
- Factores con el INPC de la serie versionada (INEGI, `datos/inpc.csv`): se escriben a mano en
  cada test con los índices que usan, para que cualquiera los rehaga.
- Anual PM y RESICO PM: casos construidos con la mecánica literal de los Arts. 9, 57, 211 y
  212 LISR. FUENTE POR CONFIRMAR: no hay ejemplo oficial publicado con estas cifras.
"""

from __future__ import annotations

from decimal import Decimal

from app.fiscal_engine import personas_morales as m
from app.fiscal_engine.anual_pf import tasa_resico_anual

D = Decimal


def test_coeficiente_de_utilidad_ejemplo_publicado():
    assert m.coeficiente_utilidad(D("2700000"), D("12150000")) == D("0.2222")
    # Pérdida o sin ingresos: no hay coeficiente (Art. 14 fr. I).
    assert m.coeficiente_utilidad(D("-1"), D("100")) == D("0")
    assert m.coeficiente_utilidad(D("1"), D("0")) == D("0")
    # Anticipos a miembros de cooperativas (Art. 94 fr. II) se suman a la utilidad.
    assert m.coeficiente_utilidad(D("100"), D("1000"), D("50")) == D("0.1500")
    # Al diezmilésimo: truncar (default) vs redondear (criterio DP-3).
    assert m.coeficiente_utilidad(D("1859225"), D("10000000")) == D("0.1859")
    assert m.coeficiente_utilidad(D("18596"), D("100000"), modo="redondear") == D("0.1860")


def _marzo() -> m.EntradaProvisionales:
    return m.EntradaProvisionales(
        2026, 4, {1: D("1100000"), 2: D("1250000"), 3: D("1450000"), 4: D("1200000")},
        D("0.1845"),
        # La pérdida ya viene actualizada (a diciembre de 2025): enero-junio no se actualiza más.
        perdidas=[m.PerdidaPendiente(2024, D("150000"), (2025, 12))],
        retenciones_mes={3: D("5000")},
        pagos_efectuados={1: D("40000"), 2: D("55000")},
    )


def test_pago_provisional_marzo_ejemplo_publicado():
    pagos = m.pagos_provisionales_pm(_marzo())
    assert [p.utilidad_estimada for p in pagos] == [
        D("202950.00"), D("433575.00"), D("701100.00"), D("922500.00")]
    marzo = pagos[2]
    assert marzo.ingresos_acumulados == D("3800000.00")
    assert marzo.perdidas == D("150000.00") and marzo.base == D("551100.00")
    assert marzo.isr_causado == D("165330.00")
    assert marzo.pagos_anteriores == D("95000.00") and marzo.retenciones == D("5000.00")
    assert marzo.pago_determinado == D("65330.00") and not marzo.pago_capturado
    # Abril acredita lo efectuado en enero-marzo (40,000 + 55,000 + 65,330).
    abril = pagos[3]
    assert abril.pagos_anteriores == D("160330.00")
    assert abril.isr_causado == D("231750.00")  # (922,500 − 150,000) × 30 %
    assert abril.pago_determinado == D("66420.00")  # 231,750 − 160,330 − 5,000


def test_ptu_en_octavos_de_mayo_a_diciembre():
    assert m.ptu_disminuible_provisional(D("80000"), 4) == 0
    assert m.ptu_disminuible_provisional(D("80000"), 5) == D("10000.00")
    assert m.ptu_disminuible_provisional(D("80000"), 12) == D("80000.00")
    # Pagada en julio: junio no la disminuye; julio ya lleva tres octavos.
    assert m.ptu_disminuible_provisional(D("80000"), 6, mes_pago=7) == 0
    assert m.ptu_disminuible_provisional(D("80000"), 7, mes_pago=7) == D("30000.00")
    e = m.EntradaProvisionales(2026, 5, {1: D("100000")}, D("0.10"), ptu_pagada=D("400000"))
    mayo = m.pagos_provisionales_pm(e)[-1]
    # La disminución no excede la utilidad del pago (Art. 14 fr. II).
    assert mayo.utilidad_estimada == D("10000.00") and mayo.ptu_disminuida == D("10000.00")
    assert mayo.isr_causado == 0


def test_ajuste_anual_por_inflacion_ejemplo_publicado():
    assert m.ajuste_por_promedios(D("1000000"), D("1250000"), D("0.0045")) == (
        D("1125.00"), D("0.00"))
    assert m.ajuste_por_promedios(D("1250000"), D("900000"), D("0.0045")) == (
        D("0.00"), D("1575.00"))


def test_ajuste_anual_por_inflacion_2025_con_inpc():
    # Factor de ajuste anual 2025 = INPC dic-2025 / INPC dic-2024 − 1
    #   = 143.042 / 137.949 − 1 = 0.036920… → 0.0369 (diezmilésimo, truncado).
    r = m.ajuste_anual_inflacion(2025, [D("1000000")] * 12, [D("1250000")] * 12)
    assert r.factor is not None and r.factor.mes_reciente == "2025-12"
    assert r.factor.mes_antiguo == "2024-12"
    assert r.factor_ajuste == D("0.0369")
    assert r.promedio_creditos == D("1000000.00") and r.promedio_deudas == D("1250000.00")
    assert r.acumulable == D("9225.00") and r.deducible == 0  # 250,000 × 0.0369
    # Saldos distintos por mes: promedio = suma ÷ 12.
    cred = [D("100000"), D("50000")] + [D("150700")] * 10
    deud = [D("0"), D("0")] + [D("20000")] * 10
    r = m.ajuste_anual_inflacion(2025, cred, deud)
    assert r.promedio_creditos == D("138083.33") and r.promedio_deudas == D("16666.67")
    assert r.deducible == D("4480.27")  # 121,416.66 × 0.0369
    assert not r.notas


def test_ajuste_anual_sin_inpc_publicado_avisa_estimacion():
    r = m.ajuste_anual_inflacion(2026, [D("1")] * 12, [D("2")] * 12)
    assert r.factor is not None and r.factor.uso_ultimo_publicado
    assert "estimación" in r.notas[0]


def test_actualizacion_de_perdidas_art_57():
    # Pérdida 2023 de 100,000 aplicada en 2025:
    #   1a: INPC dic-2023 / jul-2023 = 132.373 / 128.832 = 1.02748… → 1.0274 → 102,740.00
    #   2a: INPC jun-2025 / dic-2023 = 140.405 / 132.373 = 1.06067… → 1.0606 → 108,966.04
    a = m.actualizar_perdida(m.PerdidaPendiente(2023, D("100000")), 2025, (2025, 6), "truncar")
    assert [f.factor for f in a.factores] == [D("1.0274"), D("1.0606")]
    assert a.actualizada == D("108966.04") and a.actualizada_a == "2025-06"
    # Más de diez ejercicios: ya no se disminuye.
    vieja = m.actualizar_perdida(m.PerdidaPendiente(2014, D("5")), 2025, (2025, 6), "truncar")
    assert not vieja.vigente and "diez" in vieja.nota
    # Se aplican de la más antigua a la más reciente y sólo hasta la utilidad.
    total, det = m.aplicar_perdidas(
        [m.PerdidaPendiente(2024, D("50"), (2025, 6)),
         m.PerdidaPendiente(2023, D("80"), (2025, 6))],
        2025, (2025, 6), D("100"), "truncar")
    assert total == D("100") and [(x.ejercicio, x.aplicada) for x in det] == [
        (2023, D("80")), (2024, D("20"))]
    assert det[1].remanente_final == D("30")


def test_perdidas_en_provisionales_se_actualizan_desde_julio():
    p = [m.PerdidaPendiente(2023, D("100000"), (2023, 12))]
    e = m.EntradaProvisionales(2025, 7, {1: D("10000000")}, D("0.10"), perdidas=p)
    pagos = m.pagos_provisionales_pm(e)
    assert pagos[5].perdidas == D("100000.00")  # junio: última actualización
    assert pagos[6].perdidas == D("106060.00")  # julio: × 1.0606 (jun-2025 / dic-2023)


def test_anual_pm_caso_completo():
    aai = m.ajuste_anual_inflacion(2025, [D("1000000")] * 12, [D("1250000")] * 12)
    r = m.anual_pm(m.EntradaAnual(
        2025, D("10000000"), D("8000000"), aai, ptu_pagada=D("150000"),
        perdidas=[m.PerdidaPendiente(2023, D("100000"))], pagos_provisionales=D("400000"),
        retenciones=D("2000")))
    assert r.importe("ingresos_totales") == D("10009225.00")
    assert r.importe("utilidad_antes_ptu") == D("2009225.00")
    assert r.utilidad_fiscal == D("1859225.00")
    assert r.importe("perdidas_aplicadas") == D("108966.04")
    assert r.resultado_fiscal == D("1750258.96")
    assert r.isr_ejercicio == D("525077.69")  # 30 % al centavo (ROUND_HALF_UP)
    assert r.a_cargo == D("123077.69") and r.a_favor == 0
    assert r.coeficiente_siguiente == D("0.1859")  # 1,859,225 / 10,000,000
    # PTU: renta gravable sin PTU pagada ni pérdidas (Art. 9), 10 %.
    assert r.renta_gravable_ptu == D("2009225.00") and r.ptu_a_repartir == D("200922.50")


def test_anual_pm_con_perdida_la_aumenta_con_la_ptu():
    r = m.anual_pm(m.EntradaAnual(2025, D("1000"), D("1200"), ptu_pagada=D("50"),
                                  pagos_provisionales=D("30")))
    assert r.utilidad_fiscal == 0 and r.perdida_fiscal == D("250")  # Art. 57
    assert r.isr_ejercicio == 0 and r.a_favor == D("30")
    assert r.coeficiente_siguiente == 0


def test_resico_pm_pagos_provisionales_art_211():
    e = m.EntradaProvisionales(
        2026, 5, {k: D("500000") for k in range(1, 6)}, ptu_pagada=D("60000"),
        mes_pago_ptu=5, deducciones_mes={k: D("300000") for k in range(1, 6)},
        retenciones_mes={2: D("1000")})
    pagos = m.pagos_provisionales_resico_pm(e)
    assert [p.isr_causado for p in pagos] == [
        D("60000.00"), D("120000.00"), D("180000.00"), D("240000.00"), D("282000.00")]
    # Mayo: (2.5 M − 1.5 M − 60,000 de PTU completa) × 30 % = 282,000.
    assert pagos[4].ptu_disminuida == D("60000.00")
    assert pagos[4].deducciones_acumuladas == D("1500000.00")
    assert [p.pago_determinado for p in pagos] == [
        D("60000.00"), D("59000.00"), D("60000.00"), D("60000.00"), D("42000.00")]


def test_resico_pm_anual_art_212():
    r = m.anual_pm(m.EntradaAnual(2026, D("6000000"), D("3600000"), ptu_pagada=D("60000"),
                                  pagos_provisionales=D("690000"), retenciones=D("1000")),
                   resico=True)
    assert r.utilidad_fiscal == D("2340000.00") and r.isr_ejercicio == D("702000.00")
    assert r.a_cargo == D("11000.00")
    assert r.coeficiente_siguiente == 0  # RESICO PM no usa coeficiente
    assert "Art. 207" in r.renglones[0].fundamento


def test_tasa_resico_pf_anual_art_113_f():
    assert tasa_resico_anual(D("300000")) == D("0.0100")
    assert tasa_resico_anual(D("300000.01")) == D("0.0110")
    assert tasa_resico_anual(D("3500000")) == D("0.0250")
