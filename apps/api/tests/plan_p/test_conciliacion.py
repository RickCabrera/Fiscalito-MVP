"""
P2-06 · Conciliación bancaria.

"Listo cuando": un estado de cuenta de prueba concilia SÓLO los movimientos que coinciden y
deja los demás como pendientes. Además: uno a varios, ambiguos, deshacer, manual, póliza
desde el banco, reporte que cuadra, CSV/XLSX/OFX/PDF sintéticos y multi-tenant.

Los PDF son SINTÉTICOS: imitan el texto de un estado de cuenta; los diseños de los bancos
están POR CONFIRMAR CON PDF REAL (`app/contabilidad/conciliacion/pdf_bancos.py`).
"""

from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.contabilidad import catalogo, polizas
from app.contabilidad.conciliacion import emparejador, lectores, pdf_bancos, reporte, servicio
from app.contabilidad.conciliacion.emparejador import Partida
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.sat_verificacion.pdf import pdf_texto
from app.tenancy import asegurar_usuario
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE

D = Decimal


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-banco")
    c = Cliente(despacho_id="uid-banco", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    catalogo.sembrar_base(db_sesion, c)
    return c


def cta(db, cliente, numero):
    return catalogo.por_numero(db, cliente)[numero]


@pytest.fixture
def banco(db_sesion, cliente):
    return servicio.crear_cuenta(db_sesion, cliente, {
        "banco": "012", "nombre": "BBVA", "numero": "0123456789", "clabe": "",
        "cuenta_contable_id": cta(db_sesion, cliente, "102.01.01").id})


def poliza(db, cliente, fecha, importe, concepto, entra=True, contra="105.01"):
    bancos = cta(db, cliente, "102.01.01").id
    otra = cta(db, cliente, contra).id
    imp = D(importe)
    movs = [polizas.MovimientoEntrada(bancos, imp if entra else D(0), D(0) if entra else imp,
                                      concepto),
            polizas.MovimientoEntrada(otra, D(0) if entra else imp, imp if entra else D(0),
                                      concepto)]
    return polizas.crear_manual(db, cliente, tipo="ingreso" if entra else "egreso",
                                fecha=fecha, concepto=concepto, movimientos=movs, uid="u")


CSV = """Fecha,Descripción,Referencia,Retiros,Depósitos,Saldo
Saldo inicial,,,,,"10,000.00"
02/03/2026,SPEI RECIBIDO CLIENTE UNO,REF1001,,"1,160.00","11,160.00"
05/03/2026,PAGO PROVEEDOR ACME,CH-77,580.00,,"10,580.00"
10/03/2026,DEPOSITO VARIOS,REF2002,,"3,000.00","13,580.00"
15/03/2026,COMISION POR MANEJO DE CUENTA,,116.00,,"13,464.00"
20/03/2026,DEPOSITO SIN IDENTIFICAR,,,500.00,"13,964.00"
"""


def importar_csv(db, cliente, banco, texto=CSV):
    return servicio.importar(db, cliente, banco, nombre="marzo.csv", datos=texto.encode())


# ── lectores ──


def test_csv_detecta_columnas_saldos_y_signos():
    lec = lectores.leer_csv(CSV.encode())
    assert lec.saldo_inicial == D("10000.00") and lec.saldo_final == D("13964.00")
    assert len(lec.movimientos) == 5
    m = lec.movimientos[1]
    assert (m.fecha, m.cargo, m.abono, m.referencia) == (date(2026, 3, 5), D("580.00"), D(0),
                                                        "CH-77")


def test_csv_con_plantilla_importe_con_signo_y_letras():
    texto = "x;y\nDia;Movimiento;Monto\n01-mar-2026;Cobro;1500.50\n03-mar-2026;Pago;-200\n"
    mapeo = {"fecha": "A", "concepto": "B", "importe": "C", "fila_encabezado": 2,
             "separador": ";"}
    lec = lectores.leer_csv(texto.encode(), mapeo)
    assert [(m.fecha.day, m.cargo, m.abono) for m in lec.movimientos] == [
        (1, D(0), D("1500.50")), (3, D("200.00"), D(0))]


def test_xlsx_con_mapeo():
    libro = Workbook()
    h = libro.active
    h.append(["Estado de cuenta"])
    h.append(["F. Operación", "Concepto", "Cargo", "Abono", "Saldo"])
    h.append([date(2026, 3, 2), "SPEI", None, 1160, 11160])
    h.append(["05/03/2026", "Pago", "580.00", None, 10580])
    buf = io.BytesIO()
    libro.save(buf)
    lec = lectores.leer_xlsx(buf.getvalue(), {"fecha": "F. Operación", "concepto": "Concepto",
                                              "cargo": "Cargo", "abono": "Abono",
                                              "saldo": "Saldo", "fila_encabezado": 2})
    assert [(m.cargo, m.abono) for m in lec.movimientos] == [(D(0), D("1160.00")),
                                                             (D("580.00"), D(0))]
    assert lec.saldo_final == D("10580.00")


def test_ofx_sgml():
    ofx = (b"OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>"
           b"<BANKTRANLIST><STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260302<TRNAMT>1160.00"
           b"<FITID>A1<NAME>SPEI RECIBIDO<MEMO>REF1001</STMTTRN>"
           b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260305120000<TRNAMT>-580.00<FITID>A2"
           b"<CHECKNUM>77<NAME>CHEQUE</STMTTRN></BANKTRANLIST>"
           b"<LEDGERBAL><BALAMT>10580.00<DTASOF>20260331</LEDGERBAL></STMTRS></STMTTRNRS>"
           b"</BANKMSGSRSV1></OFX>")
    lec = lectores.leer_ofx(ofx)
    assert [(m.cargo, m.abono, m.referencia) for m in lec.movimientos] == [
        (D(0), D("1160.00"), "A1"), (D("580.00"), D(0), "77")]
    assert (lec.saldo_inicial, lec.saldo_final) == (D("10000.00"), D("10580.00"))


def _pdf_banco(encabezado: str, renglones: list[str]) -> bytes:
    return pdf_texto([encabezado, "ESTADO DE CUENTA", "PERIODO DEL 01/03/2026 AL 31/03/2026",
                      "SALDO ANTERIOR 10,000.00", *renglones, "SALDO FINAL 10,580.00"])


@pytest.mark.parametrize("diseno", pdf_bancos.DISENOS, ids=lambda d: d.clave)
def test_pdf_sintetico_de_cada_banco(diseno):
    """POR CONFIRMAR CON PDF REAL: el diseño sintético de cada banco se lee y el signo sale
    del saldo corrido."""
    datos = _pdf_banco(f"{diseno.nombre.upper()} S.A.", [
        "02/MAR SPEI RECIBIDO CLIENTE UNO REF 1001 1,160.00 11,160.00",
        "05/MAR PAGO PROVEEDOR ACME 580.00 10,580.00",
    ])
    lec, d = pdf_bancos.leer_pdf(datos)
    assert d.clave == diseno.clave
    assert [(m.fecha, m.cargo, m.abono) for m in lec.movimientos] == [
        (date(2026, 3, 2), D(0), D("1160.00")), (date(2026, 3, 5), D("580.00"), D(0))]
    assert lec.movimientos[0].referencia == "1001"
    assert (lec.saldo_inicial, lec.saldo_final) == (D("10000.00"), D("10580.00"))


def test_pdf_desconocido_y_no_pdf():
    with pytest.raises(FiscalAgentError, match="No se reconoció el banco"):
        pdf_bancos.leer_pdf(_pdf_banco("BANCO INVENTADO", ["02/MAR X 1.00 1.00"]))
    with pytest.raises(FiscalAgentError, match="no es un PDF"):
        pdf_bancos.leer_pdf(b"hola")


# ── emparejador puro ──


def test_emparejador_ambiguo_no_adivina():
    b = [Partida("b:1", date(2026, 3, 2), D("100"))]
    lib = [Partida("p:1", date(2026, 3, 1), D("100")), Partida("p:2", date(2026, 3, 3), D("100"))]
    r = emparejador.emparejar(b, lib, ventana=3, umbral=60)
    assert r.emparejados == [] and r.ambiguos == ["b:1"]


def test_emparejador_referencia_desempata():
    b = [Partida("b:1", date(2026, 3, 2), D("100"), "spei ref1001", "REF1001")]
    lib = [Partida("p:1", date(2026, 3, 1), D("100"), "cobro ref1001"),
           Partida("p:2", date(2026, 3, 3), D("100"), "otro")]
    r = emparejador.emparejar(b, lib)
    assert [(e.banco, e.libros) for e in r.emparejados] == [(["b:1"], ["p:1"])]


# ── conciliación de punta a punta ──


def test_concilia_solo_lo_que_coincide_y_deja_pendientes(db_sesion, cliente, banco):
    """LISTO CUANDO de P2-06."""
    p1 = poliza(db_sesion, cliente, date(2026, 3, 1), "1160.00", "Cobro F-1 ref REF1001")
    poliza(db_sesion, cliente, date(2026, 3, 6), "580.00", "Pago ACME", entra=False,
           contra="201.01")
    poliza(db_sesion, cliente, date(2026, 3, 25), "999.00", "Cheque en tránsito",
           entra=False, contra="201.01")
    poliza(db_sesion, cliente, date(2026, 2, 10), "1160.00", "Fuera de ventana")
    importar_csv(db_sesion, cliente, banco)

    r = servicio.conciliar_automatico(db_sesion, cliente, banco, None, None)
    assert r["conciliados"] == 2
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    conciliados = {x["concepto"] for x in v["banco"] if x["conciliacion_id"]}
    assert conciliados == {"SPEI RECIBIDO CLIENTE UNO", "PAGO PROVEEDOR ACME"}
    assert v["pendientes_banco"] == 3
    pend_libros = {x["concepto"] for x in v["libros"] if not x["conciliacion_id"]}
    assert pend_libros == {"Cheque en tránsito", "Fuera de ventana"}
    assert any(x["poliza_id"] == p1.id and x["conciliacion_id"] for x in v["libros"])
    # Volver a conciliar no duplica nada.
    assert servicio.conciliar_automatico(db_sesion, cliente, banco, None, None)[
        "conciliados"] == 0
    # Reimportar el mismo estado no duplica renglones.
    imp = importar_csv(db_sesion, cliente, banco)
    assert (imp.estado.nuevos, imp.estado.duplicados) == (0, 5)


def test_uno_a_varios(db_sesion, cliente, banco):
    poliza(db_sesion, cliente, date(2026, 3, 9), "1000.00", "Cobro F-2")
    poliza(db_sesion, cliente, date(2026, 3, 10), "1500.00", "Cobro F-3")
    poliza(db_sesion, cliente, date(2026, 3, 11), "500.00", "Cobro F-4")
    importar_csv(db_sesion, cliente, banco)
    r = servicio.conciliar_automatico(db_sesion, cliente, banco, None, None)
    assert r["uno_a_varios"] == 1
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    dep = next(x for x in v["banco"] if x["concepto"] == "DEPOSITO VARIOS")
    assert dep["conciliacion_id"]
    juntos = [x for x in v["libros"] if x["conciliacion_id"] == dep["conciliacion_id"]]
    assert len(juntos) == 3


def test_manual_deshacer_y_validaciones(db_sesion, cliente, banco):
    importar_csv(db_sesion, cliente, banco)
    p = poliza(db_sesion, cliente, date(2026, 3, 22), "500.00", "Depósito de socio",
               contra="301.01")
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    sin_ident = next(x for x in v["banco"] if x["concepto"] == "DEPOSITO SIN IDENTIFICAR")
    lib = next(x for x in v["libros"] if x["poliza_id"] == p.id)
    comision = next(x for x in v["banco"] if x["concepto"].startswith("COMISION"))
    with pytest.raises(FiscalAgentError, match="No cuadra"):
        servicio.conciliar_manual(db_sesion, cliente, banco, [comision["clave"]],
                                  [lib["clave"]], "", "u")
    c = servicio.conciliar_manual(db_sesion, cliente, banco, [sin_ident["clave"]],
                                  [lib["clave"]], "aportación", "u")
    with pytest.raises(FiscalAgentError, match="Ya están conciliadas"):
        servicio.conciliar_manual(db_sesion, cliente, banco, [sin_ident["clave"]],
                                  [lib["clave"]], "", "u")
    servicio.deshacer(db_sesion, cliente, banco, c.id)
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    assert all(x["conciliacion_id"] is None for x in v["banco"] + v["libros"])
    with pytest.raises(FiscalAgentError):
        servicio.deshacer(db_sesion, cliente, banco, c.id)


def test_poliza_desde_movimiento_bancario(db_sesion, cliente, banco):
    importar_csv(db_sesion, cliente, banco)
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    com = next(x for x in v["banco"] if x["concepto"].startswith("COMISION"))
    from app.modelos.conciliacion import MovimientoBancario

    sug = servicio.sugerir_cuenta(db_sesion, cliente, db_sesion.get(MovimientoBancario,
                                                                    com["id"]))
    assert sug and sug["numero"] == "701.10"
    iva = cta(db_sesion, cliente, "118.01").id
    with pytest.raises(FiscalAgentError, match="sumar 116.00"):
        servicio.crear_poliza(db_sesion, cliente, banco, com["id"],
                              [(sug["cuenta_id"], D("100.00"))], "", "u")
    p, _c = servicio.crear_poliza(db_sesion, cliente, banco, com["id"],
                                  [(sug["cuenta_id"], D("100.00")), (iva, D("16.00"))],
                                  "Comisión marzo", "u")
    assert p.tipo == "egreso"
    v = servicio.vista(db_sesion, cliente, banco, None, None)
    assert next(x for x in v["banco"] if x["id"] == com["id"])["conciliacion_id"]


def test_reporte_cuadra(db_sesion, cliente, banco):
    """Saldo banco ± partidas en tránsito = saldo libros ± partidas del banco."""
    from app.contabilidad import balanza

    balanza.guardar_saldos_iniciales(db_sesion, cliente, [
        (cta(db_sesion, cliente, "102.01.01").id, D("10000.00"), D(0)),
        (cta(db_sesion, cliente, "301.01").id, D(0), D("10000.00"))])
    poliza(db_sesion, cliente, date(2026, 3, 1), "1160.00", "Cobro ref REF1001")
    poliza(db_sesion, cliente, date(2026, 3, 6), "580.00", "Pago ACME", entra=False,
           contra="201.01")
    poliza(db_sesion, cliente, date(2026, 3, 30), "999.00", "Cheque 88", entra=False,
           contra="201.01")
    poliza(db_sesion, cliente, date(2026, 3, 31), "250.00", "Depósito en tránsito")
    importar_csv(db_sesion, cliente, banco)
    servicio.conciliar_automatico(db_sesion, cliente, banco, None, None)
    r = reporte.reporte(db_sesion, cliente, banco, date(2026, 3, 31))
    assert r["saldo_banco"] == "13964.00"
    assert r["saldo_libros"] == "9831.00"
    assert r["totales"] == {"depositos_en_transito": "250.00", "retiros_en_transito": "999.00",
                            "abonos_banco_no_registrados": "3500.00",
                            "cargos_banco_no_registrados": "116.00"}
    assert r["cuadra"] is True and r["diferencia"] == "0.00"
    assert reporte.a_excel(r, "Taller")[:2] == b"PK"


def test_cuenta_bancaria_exige_cuenta_afectable(db_sesion, cliente):
    with pytest.raises(FiscalAgentError, match="subcuentas"):
        servicio.crear_cuenta(db_sesion, cliente, {
            "banco": "012", "cuenta_contable_id": cta(db_sesion, cliente, "102.01").id})


# ── API y multi-tenant ──


def test_api_de_punta_a_punta_y_multitenant(api, sesionador):
    s = sesionador()
    asegurar_usuario(s, "uid-a")
    cli = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    s.add(cli)
    s.flush()
    catalogo.sembrar_base(s, cli)
    poliza(s, cli, date(2026, 3, 1), "1160.00", "Cobro F-1")
    bancos_id = cta(s, cli, "102.01.01").id
    s.commit()
    s.close()

    a = api("uid-a")
    base = "/api/v1/conciliacion/clientes/taller"
    r = a.post(f"{base}/cuentas", json={"banco": "012", "nombre": "BBVA",
                                        "cuenta_contable_id": bancos_id})
    assert r.status_code == 201, r.text
    cid = r.json()["cuenta"]["id"]
    r = a.put(f"{base}/plantillas", json={"nombre": "BBVA CSV", "banco": "012",
                                          "formato": "csv", "mapeo": {
                                              "fecha": "Fecha", "concepto": "Descripción",
                                              "cargo": "Retiros", "abono": "Depósitos",
                                              "saldo": "Saldo"}})
    pid = r.json()["plantilla"]["id"]
    r = a.post(f"{base}/cuentas/{cid}/estados", files={"archivo": ("m.csv", CSV.encode())},
               data={"plantilla_id": str(pid), "mapeo": json.dumps({"referencia": "Referencia"})})
    assert r.status_code == 200, r.text
    assert r.json()["estado"]["nuevos"] == 5
    r = a.post(f"{base}/cuentas/{cid}/conciliar", json={})
    assert r.json()["resultado"]["conciliados"] == 1
    v = a.get(f"{base}/cuentas/{cid}/movimientos").json()
    assert v["pendientes_banco"] == 4
    conc = next(x["conciliacion_id"] for x in v["banco"] if x["conciliacion_id"])
    rep = a.get(f"{base}/cuentas/{cid}/reporte", params={"corte": "2026-03-31",
                                                          "formato": "xlsx"})
    assert rep.status_code == 200 and rep.content[:2] == b"PK"
    assert a.delete(f"{base}/cuentas/{cid}/conciliaciones/{conc}").status_code == 200

    b = api("uid-b")
    assert b.get(f"{base}/cuentas").status_code == 404
    assert b.get(f"{base}/cuentas/{cid}/movimientos").status_code == 404
    assert b.post(f"{base}/cuentas/{cid}/conciliar", json={}).status_code == 404
