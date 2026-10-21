"""
Correcciones del revisor de motor sobre el motor fiscal de P3 (B1, B3, B4, O12).

Cada caso trae su cálculo a mano y su fundamento:

- B1 — Código Financiero de Veracruz art. 103 fr. I inciso n): sólo exenta los premios de
  asistencia y puntualidad ANUALES; los del periodo gravan (3 % + 15 % adicional).
- B3 — LISR art. 9 párrafos cuarto y quinto (P6-07): la renta gravable de PTU disminuye de
  los ingresos acumulables las cantidades no deducibles del art. 28 fr. XXX (sólo ahí).
- B4 — LIVA art. 5o. fr. V inciso c) (reforma 2022) y art. 4o.-A: los actos no objeto entran
  al denominador de la proporción; el art. 5o.-C excluye conceptos (dividendos, ...).
- O12 — un INPC sin cotejar con el boletín del INEGI o una tasa de recargos de fuente
  secundaria sale en la respuesta como `por_confirmar`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.contabilidad import catalogo, polizas
from app.contabilidad.polizas import MovimientoEntrada
from app.exceptions import FiscalValidationError
from app.fiscal_engine import personas_morales as m
from app.fiscal_engine.actualizacion import calcular_actualizacion_recargos, resultado_como_dict
from app.fiscal_engine.isn import ConfigISN, PercepcionISN, calcular_isn
from app.fiscal_engine.iva import ConfigIVA, MovimientoIVA, calcular_iva_mes
from app.fiscal_engine.resumen_impuestos import ImporteSistema, armar_resumen, resumen_dict
from app.impuestos.servicio import config_iva
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.schemas.impuestos import ConfigImpuestosSchema
from tests.plan_p.test_rutas_anual import IMP, _ventas_del_ejemplo
from tests.plan_p.test_rutas_anual import despachos as clientes_pm  # noqa: F401

# `clientes_pm`: el fixture `despachos` de las rutas de la anual (moral, resico y fisica del
# despacho A, y uno del B).

D = Decimal


# ── B1: ISN de Veracruz, premios de puntualidad y asistencia ──


def test_b1_veracruz_premios_de_puntualidad_y_asistencia_gravan():
    percepciones = [PercepcionISN("001", D("10000")), PercepcionISN("010", D("1000")),
                    PercepcionISN("049", D("500"))]
    r = calcular_isn("VER", date(2026, 3, 1), percepciones)
    # 11,500 × 3 % = 345.00; 345.00 × 15 % = 51.75.
    assert r.excluido == 0 and r.base == D("11500.00")
    assert r.impuesto == D("345.00") and r.adicional == D("51.75") and r.total == D("396.75")
    # Si al despacho le consta que son ANUALES (inciso n), los excluye por cliente.
    anual = calcular_isn("VER", date(2026, 3, 1), percepciones,
                         ConfigISN(claves_excluidas_extra=frozenset({"010", "049"})))
    assert anual.base == D("10000.00") and anual.total == D("345.00")  # 300 + 45


# ── B3: renta gravable de PTU menos los no deducibles del Art. 28 fr. XXX ──


def test_b3_renta_gravable_ptu_resta_no_deducibles_art28_xxx():
    r = m.anual_pm(m.EntradaAnual(2025, D("10000000"), D("8000000"), ptu_pagada=D("100000"),
                                  no_deducibles_art28_xxx=D("150000")))
    # Utilidad antes de PTU 2,000,000; renta gravable = 2,000,000 − 150,000 = 1,850,000.
    assert r.renta_gravable_ptu == D("1850000.00") and r.ptu_a_repartir == D("185000.00")
    # Sólo toca la PTU: utilidad fiscal = 2,000,000 − 100,000 de PTU pagada; ISR 570,000.
    assert r.utilidad_fiscal == D("1900000.00") and r.isr_ejercicio == D("570000.00")
    assert r.no_deducibles_art28_xxx == D("150000.00")


def test_b3_no_deducibles_negativos_se_rechazan():
    with pytest.raises(FiscalValidationError):
        m.anual_pm(m.EntradaAnual(2025, D("1"), D("0"), no_deducibles_art28_xxx=D("-1")))


def _nomina(sesionador, gravado: str, exento: str) -> None:
    db = sesionador()
    c = db.query(Cliente).filter_by(clave="moral").one()
    db.add(Comprobante(
        cliente_id=c.id, uuid="NNNNNNNN-0000-4000-8000-000000000001", version="4.0", tipo="N",
        fecha=datetime(2026, 3, 15, 10), rfc_emisor=c.rfc, rfc_receptor="XEXX010101000",
        direccion="emitido", ruta_xml="sintetico.xml", sha256="0" * 64,
        datos={"nomina": {"FechaPago": "2026-03-15", "percepciones": {
            "TotalGravado": gravado, "TotalExento": exento}}}))
    db.commit()
    db.close()


@pytest.mark.usefixtures("clientes_pm")
def test_b3_anual_pm_desde_la_boveda_deriva_el_art28_xxx_de_la_nomina(api, sesionador):
    a = api("uid-a")
    _ventas_del_ejemplo(a)  # 3,800,000 de ingresos
    _nomina(sesionador, "20000", "10000")
    d = a.post(f"{IMP}/moral/anual", json={"anio": 2026}).json()
    ren = {x["clave"]: D(x["importe"]) for x in d["renglones"]}
    # Deducción de nómina: 20,000 + 47 % × 10,000 = 24,700; no deducible 53 % = 5,300.
    assert ren["deducciones"] == D("24700.00")
    p = d["ptu"]
    assert p["no_deducibles_art28_xxx"] == "5300.00" and p["origen_art28_xxx"] == "boveda"
    assert p["utilidad_antes_ptu"] == "3775300.00"
    assert p["renta_gravable"] == "3770000.00" and p["a_repartir"] == "377000.00"
    assert "Sexta Comisión" in p["fundamento"]

    # Capturado manda sobre lo derivado.
    a.put(f"{IMP}/moral/pm/datos/2026", json={"no_deducibles_art28_xxx": "1000"})
    p = a.post(f"{IMP}/moral/anual", json={"anio": 2026}).json()["ptu"]
    assert p["origen_art28_xxx"] == "capturado" and p["renta_gravable"] == "3774300.00"


@pytest.mark.usefixtures("clientes_pm")
def test_b3_anual_pm_desde_la_contabilidad_con_cuenta_art28_xxx(api, sesionador):
    db = sesionador()
    c = db.query(Cliente).filter_by(clave="moral").one()
    catalogo.sembrar_base(db, c)
    cs = catalogo.por_numero(db, c)
    polizas.crear_manual(db, c, tipo="diario", fecha=date(2026, 3, 10), concepto="prueba",
                         uid="u", movimientos=[
                             MovimientoEntrada(cs["102.01.01"].id, D("45000"), D("0")),
                             MovimientoEntrada(cs["501.01"].id, D("40000"), D("0")),
                             MovimientoEntrada(cs["601.84"].id, D("15000"), D("0")),
                             MovimientoEntrada(cs["401.01"].id, D("0"), D("100000"))])
    db.commit()
    db.close()
    a = api("uid-a")
    # Sin cuenta designada: no se resta nada y se avisa (no se baja la PTU sin dato).
    d = a.post(f"{IMP}/moral/anual", json={"anio": 2026}).json()
    assert d["ptu"]["origen_art28_xxx"] == "sin dato"
    assert d["ptu"]["no_deducibles_art28_xxx"] == "0.00"
    assert any("Art. 28 fr. XXX" in n for n in d["notas"])
    # Con la cuenta 601.84 como la del no deducible del 28-XXX: deja de deducirse y resta
    # en la renta gravable de PTU.
    a.put(f"{IMP}/moral/pm/datos/2026", json={"cuentas_art28_xxx": ["601.84"]})
    d = a.post(f"{IMP}/moral/anual", json={"anio": 2026}).json()
    ren = {x["clave"]: D(x["importe"]) for x in d["renglones"]}
    assert ren["deducciones"] == D("40000.00")
    p = d["ptu"]
    assert p["origen_art28_xxx"] == "contabilidad" and p["no_deducibles_art28_xxx"] == "15000.00"
    assert D(p["renta_gravable"]) == D(p["utilidad_antes_ptu"]) - D("15000")


# ── B4: actos no objeto en la proporción del IVA ──


def _movs_b4() -> list[MovimientoIVA]:
    return [
        MovimientoIVA("A", "emitido", base_16=D("80000"), iva_16=D("12800")),
        MovimientoIVA("B", "emitido", base_exento=D("10000")),
        MovimientoIVA("NOOBJ", "emitido", base_no_objeto=D("10000")),
        MovimientoIVA("D", "recibido", base_16=D("10000"), iva_16=D("1600")),
    ]


def test_b4_no_objeto_entra_al_denominador_de_la_proporcion():
    r = calcular_iva_mes(2026, 4, _movs_b4())
    # 80,000 ÷ (80,000 + 10,000 exentos + 10,000 no objeto) = 0.8000.
    assert r.proporcion == D("0.8000") and r.valor_no_objeto_en_proporcion == D("10000.00")
    assert r.iva_acreditable == D("1280.00")  # 1,600 × 0.8
    assert r.iva_a_pagar == D("11520.00")  # 12,800 − 1,280


def test_b4_no_objeto_excluido_por_el_despacho_y_no_objeto_solo():
    r = calcular_iva_mes(2026, 4, _movs_b4(),
                         config=ConfigIVA(no_objeto_excluidos=frozenset({"NOOBJ"})))
    # Art. 5o.-C (p. ej. dividendos): 80,000 ÷ 90,000 = 0.88888… → 0.8888 truncado.
    assert r.proporcion == D("0.8888") and r.iva_acreditable == D("1422.08")
    assert r.valor_no_objeto == D("10000.00")  # se sigue informando
    # Sin exentos, el no objeto basta para que haya proporción.
    sin_exentos = [x for x in _movs_b4() if x.uuid != "B"]
    assert calcular_iva_mes(2026, 4, sin_exentos).proporcion == D("0.8888")


def test_b4_configuracion_del_cliente():
    cfg = ConfigImpuestosSchema(iva_no_objeto_excluidos=[" abc-1 ", ""])
    assert cfg.iva_no_objeto_excluidos == ["ABC-1"]
    assert config_iva(cfg).no_objeto_excluidos == frozenset({"ABC-1"})


# ── O12: fuentes por confirmar en la respuesta ──


def test_o12_actualizacion_con_inpc_y_tasa_secundarios_por_confirmar():
    r = calcular_actualizacion_recargos(D("10000"), date(2025, 3, 17), date(2025, 5, 20))
    # Factor 139.620 (abr-2025) ÷ 138.726 (feb-2025) = 1.00644… → 1.0064; 3 meses de mora
    # a 1.47 % (0.98 % × 1.5) = 4.41 % sobre 10,064.00 = 443.82.
    assert r.monto_actualizado == D("10064.00") and r.recargos == D("443.82")
    assert r.por_confirmar
    assert [f.split(" (")[0].split(":")[0] for f in r.fuentes_por_confirmar] == [
        "INPC 2025-04", "INPC 2025-02", "Tasa de recargos 2025"]
    d = resultado_como_dict(r)
    assert d["por_confirmar"] is True and len(d["fuentes_por_confirmar"]) == 3


def test_o12_actualizacion_con_fuentes_verificadas_no_marca():
    r = calcular_actualizacion_recargos(D("10000"), date(2026, 2, 17), date(2026, 7, 10))
    # 145.131 (jun-2026) ÷ 143.588 (ene-2026) = 1.01074… → 1.0107; 5 meses × 2.07 % (LIF
    # 2026 art. 11) = 10.35 % sobre 10,107.00 = 1,046.07. Boletines del INEGI y LIF citada.
    assert r.monto_actualizado == D("10107.00") and r.recargos == D("1046.07")
    assert not r.por_confirmar and resultado_como_dict(r)["fuentes_por_confirmar"] == []


def test_o12_resumen_marca_el_renglon_y_junta_las_fuentes():
    r = armar_resumen(2025, 2, date(2025, 3, 17), date(2025, 5, 20),
                      [ImporteSistema("iva_a_cargo", D("10000"))])
    d = resumen_dict(r)
    filas = {f["clave"]: f for f in d["renglones"]}
    assert filas["iva_a_cargo"]["por_confirmar"] is True
    assert filas["isr_pm"]["por_confirmar"] is False  # en cero: sin factor
    assert d["por_confirmar"] is True and len(d["fuentes_por_confirmar"]) == 3
    assert any("FUENTE POR CONFIRMAR" in n for n in d["notas"])


def test_o12_personas_morales_propagan_inpc_secundario():
    # Pérdida de 2023 sin actualizar: factor dic-2023 ÷ jul-2023 (tablas secundarias).
    det = m.actualizar_perdida(m.PerdidaPendiente(2023, D("100000")), 2025, None, "truncar")
    assert len(det.fuentes_por_confirmar) == 2
    assert m.factor_dict(det.factores[0])["por_confirmar"] is True
    # AAI 2025: dic-2025 ÷ dic-2024, ambos cotejados con boletín → no marca.
    aai = m.ajuste_anual_inflacion(2025, [D("1000000")] * 12, [D("1250000")] * 12)
    assert aai.fuentes_por_confirmar == ()
    r = m.anual_pm(m.EntradaAnual(2025, D("10000000"), D("8000000"), aai,
                                  perdidas=[m.PerdidaPendiente(2023, D("100000"))]))
    assert r.fuentes_por_confirmar  # vienen de la pérdida
    pagos = m.pagos_provisionales_pm(m.EntradaProvisionales(
        2025, 1, {1: D("1000000")}, D("0.10"), perdidas=[m.PerdidaPendiente(2023, D("1000"))]))
    assert m.pago_dict(pagos[0])["por_confirmar"] is True


def test_o12_isn_estado_no_verificado():
    agu = calcular_isn("AGU", date(2026, 3, 1), [PercepcionISN("001", D("1000"))])
    ver = calcular_isn("VER", date(2026, 3, 1), [PercepcionISN("001", D("1000"))])
    assert agu.tasa.por_confirmar and not ver.tasa.por_confirmar
