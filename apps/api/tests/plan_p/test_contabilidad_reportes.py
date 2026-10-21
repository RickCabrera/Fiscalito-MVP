"""
P2-05 (reportes contables) y P2-08 (cierre de periodo y de ejercicio).

"Listo cuando" medidos aquí:
- P2-05: los reportes cuadran con la balanza del mismo periodo; el balance cuadra; el Excel
  se abre y trae los totales.
- P2-08: un periodo cerrado no acepta pólizas nuevas, y el cierre anual deja en cero las
  cuentas de resultados y la apertura trae los saldos de balance.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.contabilidad import balanza, catalogo, cierre, excel, polizas, reportes
from app.contabilidad.polizas import MovimientoEntrada
from app.exceptions import FiscalAgentError
from app.modelos.contabilidad import CuentaContable
from app.modelos.nucleo import Cliente, Usuario
from app.tenancy import asegurar_usuario
from tests.plan_p.conta_sintetico import RFC_CLIENTE, factura, uuid_n

D = Decimal


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-rep")
    c = Cliente(despacho_id="uid-rep", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    catalogo.sembrar_base(db_sesion, c)
    return c


def cuentas(db, cliente) -> dict[str, CuentaContable]:
    return catalogo.por_numero(db, cliente)


def poliza(db, cliente, fecha: date, *movs: tuple[str, str, str]) -> None:
    """movs: (cuenta, cargo, abono)."""
    cs = cuentas(db, cliente)
    polizas.crear_manual(db, cliente, tipo="diario", fecha=fecha, concepto="prueba", uid="u",
                         movimientos=[MovimientoEntrada(cs[n].id, D(c), D(a))
                                      for n, c, a in movs])


def ejercicio_2026(db, cliente) -> None:
    """Capital, una venta, su costo, gastos, gasto financiero, ISR y una compra de activo."""
    poliza(db, cliente, date(2026, 1, 2), ("102.01.01", "100000", "0"),
           ("301.01", "0", "100000"))
    poliza(db, cliente, date(2026, 3, 10), ("105.01", "116000", "0"),
           ("401.01", "0", "100000"), ("209.01", "0", "16000"))
    poliza(db, cliente, date(2026, 3, 11), ("501.01", "40000", "0"),
           ("115.01", "0", "40000"))
    poliza(db, cliente, date(2026, 2, 1), ("115.01", "50000", "0"),
           ("102.01.01", "0", "50000"))
    poliza(db, cliente, date(2026, 3, 20), ("601.84", "15000", "0"),
           ("701.10", "500", "0"), ("704.23", "0", "200"), ("102.01.01", "0", "15300"))
    poliza(db, cliente, date(2026, 3, 25), ("156.01", "20000", "0"),
           ("201.01", "0", "20000"))
    poliza(db, cliente, date(2026, 4, 5), ("102.01.01", "58000", "0"),
           ("105.01", "0", "58000"))
    poliza(db, cliente, date(2026, 12, 31), ("613.05", "1000", "0"),
           ("171.03", "0", "1000"))


def linea(rep: dict, clave: str) -> dict:
    return next(x for x in rep["lineas"] if x["clave"] == clave)


# ── P2-05 ──


def test_clasificacion_por_codigo_agrupador(db_sesion, cliente):
    cs = cuentas(db_sesion, cliente)
    esperado = {"102.01.01": "activo_circulante", "156.01": "activo_no_circulante",
                "171.03": "activo_no_circulante", "201.01": "pasivo_corto",
                "301.01": "capital", "401.01": "ingresos", "402.01": "ingresos",
                "501.01": "costo", "601.84": "gastos", "701.10": "otros_gastos",
                "702.10": "otros_ingresos", "704.23": "otros_ingresos"}
    for numero, sec in esperado.items():
        assert reportes.seccion(cs[numero]) == sec, numero


def test_estado_de_resultados_cuadra_con_la_balanza(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    desde, hasta = date(2026, 3, 1), date(2026, 3, 31)
    er = reportes.estado_resultados(db_sesion, cliente, desde, hasta, reportes.Opciones())
    r = er["resumen"]
    assert r["ingresos"] == "100000.00" and r["costo"] == "40000.00"
    assert r["utilidad_bruta"] == "60000.00" and r["gastos"] == "15000.00"
    assert r["utilidad_operacion"] == "45000.00"
    assert r["utilidad_antes_impuestos"] == "44700.00" == r["utilidad_neta"]
    # Contra la balanza del mismo periodo: Σ (cargos − abonos) de las de resultados.
    bal = balanza.balanza(db_sesion, cliente, desde, hasta, nivel=1, solo="todas")
    mov = {x["numero"]: D(x["abonos"]) - D(x["cargos"]) for x in bal["renglones"]}
    neto = sum(v for n, v in mov.items() if n[0] in "4567")
    assert D(r["utilidad_neta"]) == neto
    assert linea(er, "c:" + str(cuentas(db_sesion, cliente)["401.01"].id))["valores"][
        "importe"] == "100000.00"
    # El acumulado del ejercicio incluye la depreciación de diciembre sólo si hasta la alcanza.
    anual = reportes.estado_resultados(db_sesion, cliente, date(2026, 1, 1), date(2026, 12, 31),
                                       reportes.Opciones())
    assert anual["resumen"]["utilidad_neta"] == "43700.00"


def test_balance_general_cuadra_y_coincide_con_la_balanza(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    hasta = date(2026, 4, 30)
    bg = reportes.balance_general(db_sesion, cliente, hasta, reportes.Opciones())
    assert bg["cuadra"] and bg["diferencia"] == "0.00"
    r = bg["resumen"]
    bal = balanza.balanza(db_sesion, cliente, date(2026, 4, 1), hasta, nivel=1)
    saldo = {x["numero"]: D(x["saldo_final"]) for x in bal["renglones"]}
    activo = sum(v for n, v in saldo.items() if n[0] == "1")
    pasivo = -sum(v for n, v in saldo.items() if n[0] == "2")
    assert D(r["activo"]) == activo == D("180700.00")
    assert D(r["pasivo"]) == pasivo == D("36000.00")
    assert r["capital"] == "100000.00" and r["resultado"] == "44700.00"
    assert D(r["activo"]) == D(r["pasivo_mas_capital"])
    assert linea(bg, "total_activo")["valores"]["importe"] == "180700.00"


def test_filtros_nivel_agrupador_moneda_idioma_y_comparativo(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    marzo = (date(2026, 3, 1), date(2026, 3, 31))
    n1 = reportes.estado_resultados(db_sesion, cliente, *marzo, reportes.Opciones(nivel=1))
    assert all(x.get("nivel", 0) <= 1 for x in n1["lineas"])
    ag = reportes.estado_resultados(db_sesion, cliente, *marzo,
                                    reportes.Opciones(agrupar="agrupador"))
    assert any(x["clave"] == "a:401.01" for x in ag["lineas"])
    usd = reportes.estado_resultados(db_sesion, cliente, *marzo, reportes.Opciones(
        moneda="usd", tipo_cambio=D("20")))
    assert usd["resumen"]["ingresos"] == "5000.00" and usd["moneda"] == "USD"
    with pytest.raises(FiscalAgentError, match="tipo de cambio"):
        reportes.estado_resultados(db_sesion, cliente, *marzo, reportes.Opciones(moneda="USD"))
    en = reportes.estado_resultados(db_sesion, cliente, *marzo, reportes.Opciones(idioma="en"))
    assert en["titulo"] == "Income statement" and linea(en, "utilidad_neta")["etiqueta"] == \
        "Net income"
    comp = reportes.estado_resultados(db_sesion, cliente, date(2026, 4, 1), date(2026, 4, 30),
                                      reportes.Opciones(comparar="periodo_anterior"))
    assert comp["comparativo"]["desde"] == "2026-03-01"
    neta = linea(comp, "utilidad_neta")["valores"]
    assert (neta["importe"], neta["comparativo"], neta["variacion"]) == (
        "0.00", "44700.00", "-44700.00")
    assert reportes.rango_comparativo(date(2026, 3, 1), date(2026, 3, 31), "anio_anterior") \
        == (date(2025, 3, 1), date(2025, 3, 31))
    assert reportes.rango_comparativo(date(2026, 1, 1), date(2026, 3, 31), "periodo_anterior") \
        == (date(2025, 10, 1), date(2025, 12, 31))
    con_mov = reportes.estado_resultados(db_sesion, cliente, *marzo,
                                         reportes.Opciones(solo="todas"))
    assert len(con_mov["lineas"]) > len(n1["lineas"])


def test_excel_se_abre_y_trae_los_totales(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    marzo = (date(2026, 3, 1), date(2026, 3, 31))
    datos_cliente = {"nombre": "Taller", "rfc": RFC_CLIENTE}
    bal = balanza.balanza(db_sesion, cliente, *marzo)
    ws = load_workbook(io.BytesIO(excel.balanza(bal, datos_cliente))).active
    filas = list(ws.iter_rows(values_only=True))
    totales = next(f for f in filas if f[0] == "Totales")
    assert totales[4] == float(bal["totales"]["cargos"]) == totales[5]
    assert ws.cell(row=6, column=3).number_format.startswith("#,##0.00")
    er = reportes.estado_resultados(db_sesion, cliente, *marzo, reportes.Opciones())
    ws = load_workbook(io.BytesIO(excel.estado_financiero(er))).active
    neta = next(f for f in ws.iter_rows(values_only=True) if f[1] == "Utilidad neta del ejercicio")
    assert neta[2] == 44700.0
    bg = reportes.balance_general(db_sesion, cliente, date(2026, 4, 30), reportes.Opciones())
    ws = load_workbook(io.BytesIO(excel.estado_financiero(bg))).active
    activo = next(f for f in ws.iter_rows(values_only=True) if f[1] == "Total activo")
    assert activo[2] == 180700.0
    cta = cuentas(db_sesion, cliente)["102.01.01"]
    aux = balanza.auxiliar(db_sesion, cliente, cta.id, *marzo)
    ws = load_workbook(io.BytesIO(excel.auxiliar(aux, datos_cliente))).active
    assert list(ws.iter_rows(values_only=True))[-1][7] == float(aux["saldo_final"])


# ── P2-08 ──


def test_periodo_cerrado_no_acepta_polizas_y_reabrir_pide_motivo_y_rol(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u")
    with pytest.raises(FiscalAgentError, match="cerrado"):
        poliza(db_sesion, cliente, date(2026, 3, 15), ("601.84", "1", "0"),
               ("101.01", "0", "1"))
    with pytest.raises(FiscalAgentError, match="ya está cerrado"):
        cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u")
    with pytest.raises(FiscalAgentError) as e:
        cierre.reabrir_mes(db_sesion, cliente, 2026, 3, "aux", "auxiliar", "corrección")
    assert e.value.status_code == 403
    with pytest.raises(FiscalAgentError, match="motivo"):
        cierre.reabrir_mes(db_sesion, cliente, 2026, 3, "u", "dueno", "")
    cierre.reabrir_mes(db_sesion, cliente, 2026, 3, "u", "contador", "Falta una factura")
    poliza(db_sesion, cliente, date(2026, 3, 15), ("601.84", "1", "0"), ("101.01", "0", "1"))
    estado = cierre.estado_ejercicio(db_sesion, cliente, 2026)
    assert estado["meses"][2]["estado"] == "abierto"
    assert [h["accion"] for h in estado["historial"]][:2] == ["reabrir", "cerrar"]
    assert estado["historial"][0]["motivo"] == "Falta una factura"


def test_no_cierra_con_cfdi_sin_poliza_salvo_forzado_con_motivo(db_sesion, cliente):
    from app.boveda_cfdi import servicio
    from app.integraciones.almacenamiento import AlmacenamientoMemoria

    servicio.importar(db_sesion, cliente, [("f.xml", io.BytesIO(factura(uuid_n(1, "C0000000"))))],
                      almacen=AlmacenamientoMemoria())
    v = cierre.validar(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31))
    assert v["total_cfdi_sin_poliza"] == 1 and not v["se_puede_cerrar"]
    assert v["cfdi_sin_poliza"][0]["uuid"] == uuid_n(1, "C0000000")
    with pytest.raises(FiscalAgentError, match="sin póliza"):
        cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u")
    with pytest.raises(FiscalAgentError, match="motivo"):
        cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u", forzar=True)
    cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u", forzar=True,
                      motivo="Se contabiliza en abril")
    hist = cierre.estado_ejercicio(db_sesion, cliente, 2026)["historial"]
    assert "1 CFDI sin póliza" in hist[0]["motivo"]


def test_no_cierra_si_la_balanza_no_cuadra(db_sesion, cliente):
    cs = cuentas(db_sesion, cliente)
    balanza.guardar_saldos_iniciales(db_sesion, cliente, [(cs["101.01"].id, D("10"), D("0"))])
    with pytest.raises(FiscalAgentError, match="no cuadra"):
        cierre.cerrar_mes(db_sesion, cliente, 2026, 3, "u", forzar=True, motivo="forzado")
    with pytest.raises(FiscalAgentError, match="no cuadra"):
        cierre.cierre_anual(db_sesion, cliente, 2026, "u")


def test_cierre_anual_salda_resultados_y_abre_el_balance(db_sesion, cliente):
    ejercicio_2026(db_sesion, cliente)
    antes = balanza.balanza(db_sesion, cliente, date(2026, 12, 1), date(2026, 12, 31))
    r = cierre.cierre_anual(db_sesion, cliente, 2026, "u")
    assert r["resultado"] == "43700.00" and r["tipo_resultado"] == "utilidad"
    assert [p["origen"] for p in r["polizas"]] == ["cierre", "cierre", "apertura"]
    assert all(p["total_cargos"] == p["total_abonos"] for p in r["polizas"])
    # Balanza de cierre: resultados en cero y la utilidad en 305.01.
    cierre_bal = balanza.balanza(db_sesion, cliente, date(2026, 12, 1), date(2026, 12, 31),
                                 incluir_cierre=True, solo="todas")
    assert cierre_bal["cuadra"]
    cs = cuentas(db_sesion, cliente)
    todo = {x["numero"]: x for x in cierre_bal["renglones"]}
    for n, x in todo.items():
        assert x["saldo_final"] == "0.00", n  # el cierre de balance deja todo en cero
    # Sin `incluir_cierre`, diciembre se ve igual que antes del cierre.
    assert balanza.balanza(db_sesion, cliente, date(2026, 12, 1),
                           date(2026, 12, 31))["renglones"] == antes["renglones"]
    # Enero 2027: resultados en cero, balance con los saldos de cierre y sin movimientos.
    enero = balanza.balanza(db_sesion, cliente, date(2027, 1, 1), date(2027, 1, 31))
    assert enero["cuadra"] and enero["totales"]["cargos"] == "0.00"
    ini = {x["numero"]: x["saldo_inicial"] for x in enero["renglones"]}
    assert all(not n.startswith(("4", "5", "6", "7")) for n in ini)
    fin_2026 = {x["numero"]: x["saldo_final"] for x in antes["renglones"]
                if not x["numero"].startswith(("4", "5", "6", "7"))}
    for n, s in fin_2026.items():
        if n.startswith("305"):
            continue
        assert ini.get(n) == s, n
    assert ini["305.01"] == "-43700.00"
    # Los doce meses quedaron cerrados y el balance de enero cuadra con resultado 0.
    assert all(m["estado"] == "cerrado" for m in
               cierre.estado_ejercicio(db_sesion, cliente, 2026)["meses"])
    bg = reportes.balance_general(db_sesion, cliente, date(2027, 1, 31), reportes.Opciones(),
                                  desde=date(2027, 1, 1))
    assert bg["cuadra"] and bg["resumen"]["resultado"] == "0.00"
    assert bg["resumen"]["capital"] == "143700.00"
    with pytest.raises(FiscalAgentError, match="ya tiene cierre"):
        cierre.cierre_anual(db_sesion, cliente, 2026, "u")
    pid = r["polizas"][0]["id"]
    with pytest.raises(FiscalAgentError, match="no se editan"):
        polizas.cancelar(db_sesion, cliente, pid, "x")
    _ = cs


def test_cierre_anual_con_traspaso_y_perdida_y_deshacer(db_sesion, cliente):
    poliza(db_sesion, cliente, date(2026, 5, 1), ("601.84", "3000", "0"),
           ("101.01", "0", "3000"))
    poliza(db_sesion, cliente, date(2026, 5, 2), ("101.01", "5000", "0"),
           ("301.01", "0", "5000"))
    r = cierre.cierre_anual(db_sesion, cliente, 2026, "u", traspasar_resultado=True)
    assert (r["resultado"], r["tipo_resultado"]) == ("-3000.00", "perdida")
    enero = {x["numero"]: x["saldo_inicial"] for x in balanza.balanza(
        db_sesion, cliente, date(2027, 1, 1), date(2027, 1, 31))["renglones"]}
    assert enero["304.02"] == "3000.00" and "305.02" not in enero
    assert enero["101.01"] == "2000.00" and enero["301.01"] == "-5000.00"
    with pytest.raises(FiscalAgentError) as e:
        cierre.deshacer_cierre_anual(db_sesion, cliente, 2026, "a", "auxiliar", "corrección")
    assert e.value.status_code == 403
    assert cierre.deshacer_cierre_anual(db_sesion, cliente, 2026, "u", "dueno",
                                        "Ajuste de auditoría") == 3
    assert balanza.balanza(db_sesion, cliente, date(2027, 1, 1),
                           date(2027, 1, 31))["renglones"][0]["numero"] != "304.02"
    poliza(db_sesion, cliente, date(2026, 12, 20), ("601.84", "100", "0"),
           ("101.01", "0", "100"))
    assert cierre.cierre_anual(db_sesion, cliente, 2026, "u")["resultado"] == "-3100.00"


# ── API y multi-tenant ──


@pytest.fixture
def con_clientes(sesionador):
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add(Usuario(uid="uid-aux", despacho_id="uid-a", rol="contador"))
    db.add_all([Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE),
                Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE)])
    db.commit()
    db.close()


def test_api_reportes_cierre_y_multitenant(api, con_clientes):
    a, b = api("uid-a"), api("uid-b")
    base = "/api/v1/contabilidad/clientes/taller"
    a.post(f"{base}/cuentas/sembrar")
    cs = {c["numero"]: c["id"] for c in a.get(f"{base}/cuentas").json()["cuentas"]}
    r = a.post(f"{base}/polizas", json={"tipo": "diario", "fecha": "2026-03-10", "movimientos": [
        {"cuenta_id": cs["105.01"], "cargo": "1160.00"},
        {"cuenta_id": cs["401.01"], "abono": "1000.00"},
        {"cuenta_id": cs["209.01"], "abono": "160.00"}]})
    assert r.status_code == 201, r.text
    q = "desde=2026-03-01&hasta=2026-03-31"
    er = a.get(f"{base}/reportes/estado-resultados?{q}&comparar=anio_anterior").json()
    assert er["resumen"]["utilidad_neta"] == "1000.00"
    bg = a.get(f"{base}/reportes/balance-general?{q}").json()
    assert bg["cuadra"] and bg["resumen"]["activo"] == "1160.00"
    assert a.get(f"{base}/reportes/balance-general?{q}&moneda=USD").status_code == 422
    imp = a.get(f"{base}/reportes/polizas?{q}").json()
    assert imp["total"] == 1 and len(imp["polizas"][0]["movimientos"]) == 3
    for reporte in ("balanza", "estado_resultados", "balance_general", "polizas"):
        x = a.get(f"{base}/reportes/excel?reporte={reporte}&{q}")
        assert x.status_code == 200, (reporte, x.text)
        assert x.headers["content-type"] == excel.MIME
        assert load_workbook(io.BytesIO(x.content)).active["A1"].value
    x = a.get(f"{base}/reportes/excel?reporte=auxiliar&cuenta_id={cs['105.01']}&{q}")
    assert x.status_code == 200
    assert a.get(f"{base}/reportes/excel?reporte=auxiliar&{q}").status_code == 422
    # Cierre mensual, póliza rechazada, reapertura con motivo y rol.
    v = a.get(f"{base}/periodos/2026/3/validacion").json()
    assert v["se_puede_cerrar"]
    assert a.post(f"{base}/periodos/2026/3/cerrar", json={}).json()["exito"]
    r = a.post(f"{base}/polizas", json={"tipo": "diario", "fecha": "2026-03-11", "movimientos": [
        {"cuenta_id": cs["601.84"], "cargo": "1.00"},
        {"cuenta_id": cs["101.01"], "abono": "1.00"}]})
    assert r.status_code == 409
    assert a.post(f"{base}/periodos/2026/3/reabrir", json={"motivo": ""}).status_code == 422
    estado = a.get(f"{base}/periodos/2026").json()
    assert estado["meses"][2]["estado"] == "cerrado" and estado["meses"][2]["polizas"] == 1
    assert api("uid-aux").post(f"{base}/periodos/2026/3/reabrir",
                               json={"motivo": "Corrección del contador"}).status_code == 200
    assert a.get(f"{base}/periodos-cerrados").json()["periodos"] == []
    # Cierre anual.
    assert a.get(f"{base}/cierre-anual/2026/validacion").json()["se_puede_cerrar"]
    r = a.post(f"{base}/cierre-anual/2026", json={}).json()
    assert r["resultado"] == "1000.00" and len(r["polizas"]) == 3
    assert a.post(f"{base}/cierre-anual/2026", json={}).status_code == 409
    assert a.post(f"{base}/cierre-anual/2026/deshacer",
                  json={"motivo": "Ajuste posterior"}).json()["canceladas"] == 3
    # El despacho B no ve nada de A.
    for metodo, ruta, cuerpo in [
        ("get", f"{base}/reportes/estado-resultados?{q}", None),
        ("get", f"{base}/reportes/balance-general?{q}", None),
        ("get", f"{base}/reportes/excel?reporte=balanza&{q}", None),
        ("get", f"{base}/reportes/polizas?{q}", None),
        ("get", f"{base}/periodos/2026", None),
        ("get", f"{base}/periodos/2026/3/validacion", None),
        ("post", f"{base}/periodos/2026/3/cerrar", {}),
        ("post", f"{base}/periodos/2026/3/reabrir", {"motivo": "intento ajeno"}),
        ("post", f"{base}/cierre-anual/2026", {}),
        ("post", f"{base}/cierre-anual/2026/deshacer", {"motivo": "intento ajeno"}),
    ]:
        kw = {"json": cuerpo} if cuerpo is not None else {}
        assert getattr(b, metodo)(ruta, **kw).status_code == 404, ruta
    otro = "/api/v1/contabilidad/clientes/otro"
    b.post(f"{otro}/cuentas/sembrar")
    x = b.get(f"{otro}/reportes/excel?reporte=auxiliar&cuenta_id={cs['105.01']}&{q}")
    assert x.status_code == 404
    assert b.get(f"{otro}/reportes/estado-resultados?{q}").json()["resumen"]["ingresos"] == \
        "0.00"
