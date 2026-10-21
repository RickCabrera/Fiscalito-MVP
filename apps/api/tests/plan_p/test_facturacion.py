"""
P5-04 · Facturación CFDI 4.0: ingreso, egreso y pago (Pagos 2.0) con el PAC falso.

"Listo cuando": sale una factura válida contra el XSD, sellada con el CSD del cliente,
timbrada con el PAC falso, guardada en la bóveda, con PDF con QR, y se cancela (01 con
sustituta, 02, 03, 04). Más: motor de importes (redondeo Anexo 20), catálogos contra
catCFDI.xsd, enlace con cobranza (P5-03) y multi-tenant.
"""

from __future__ import annotations

import base64
import hashlib
import io
from datetime import date
from decimal import Decimal as D

import pytest
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree
from pypdf import PdfReader

from app import almacen_cartera
from app.config import settings
from app.credenciales import servicio as cred_servicio
from app.exceptions import FiscalAgentError
from app.facturacion import calculo, catalogos, esquemas
from app.integraciones import registro
from app.modelos.cobranza import CargoCobranza
from app.modelos.nucleo import AsignacionCliente, Cliente, Despacho, Usuario
from app.nomina_cfdi import esquemas as esq_nomina
from app.tenancy import asegurar_usuario
from tests.plan_p import certs_sat

A, B = "uid-fact-a", "uid-fact-b"
RFC_EMISOR = "EKU9003173C9"
RFC_RECEPTOR = "XIA190128J61"
NS = {"c": esquemas.NS_CFDI, "p": esquemas.NS_PAGOS, "t": esquemas.NS_TFD}
IVA16 = calculo.ImpuestoEntrada("traslado", "002", "Tasa", D("0.160000"))


def _c(valor: str, cantidad: str = "1", impuestos=(IVA16,), descuento: str = "0",
       objeto: str = "02") -> calculo.ConceptoEntrada:
    return calculo.ConceptoEntrada("84111500", D(cantidad), "E48", "Servicio", D(valor),
                                   objeto, D(descuento), tuple(impuestos))


# ── motor ──


class TestMotor:
    def test_honorarios_con_retenciones(self):
        c = calculo.comprobante([_c("5000", impuestos=(
            IVA16, calculo.ImpuestoEntrada("retencion", "002", "Tasa", D("0.106667")),
            calculo.ImpuestoEntrada("retencion", "001", "Tasa", D("0.100000"))))])
        assert c.subtotal == D("5000.00") and c.total_traslados == D("800.00")
        # 5000 × 0.106667 = 533.335 → 533.34 (ROUND_HALF_UP, dentro de los límites del Anexo 20)
        assert {r.impuesto: r.importe for r in c.retenciones} == {"002": D("533.34"),
                                                                 "001": D("500.00")}
        assert c.total_retenciones == D("1033.34") and c.total == D("4766.66")

    def test_redondeo_por_concepto_y_agrupacion(self):
        # 3 × 33.335 = 100.005 → 100.01; IVA 16.0016 → 16.00 ; descuento resta a la base.
        c = calculo.comprobante([_c("33.335", "3"), _c("10.03", descuento="0.03"),
                                 _c("100", impuestos=(calculo.ImpuestoEntrada(
                                     "traslado", "002", "Exento"),))])
        assert [k.importe for k in c.conceptos] == [D("100.01"), D("10.03"), D("100.00")]
        assert c.descuento == D("0.03") and c.subtotal == D("210.04")
        t16 = next(t for t in c.traslados if t.tipo_factor == "Tasa")
        exento = next(t for t in c.traslados if t.tipo_factor == "Exento")
        assert (t16.base, t16.importe) == (D("110.01"), D("16.00") + D("1.60"))
        assert exento.base == D("100.00") and exento.importe is None
        assert c.total == D("210.04") - D("0.03") + D("17.60")

    def test_solo_exento_no_lleva_total_trasladados(self):
        c = calculo.comprobante([_c("100", impuestos=(calculo.ImpuestoEntrada(
            "traslado", "002", "Exento"),))])
        assert c.total_traslados is None and c.total == D("100.00")

    @pytest.mark.parametrize("concepto, error", [
        (_c("100", impuestos=()), "al menos un impuesto"),
        (_c("100", objeto="01"), "no se desglosan"),
        (_c("100", descuento="101"), "descuento"),
        (_c("100", impuestos=(calculo.ImpuestoEntrada("traslado", "002", "Tasa",
                                                      D("0.5")),)), "fuera de rango"),
        (_c("100", impuestos=(IVA16, IVA16)), "repetido"),
    ])
    def test_errores(self, concepto, error):
        with pytest.raises(FiscalAgentError, match=error):
            calculo.comprobante([concepto])

    def test_pago_proporcional_y_totales(self):
        c = calculo.comprobante([_c("1000")])
        d = calculo.DocumentoPagado("u", "F", "1", c.total, c.total, 1, D("580.00"),
                                    tuple(c.traslados))
        p = calculo.pago([d])
        dr = p.documentos[0]
        assert dr.saldo_insoluto == D("580.00")
        assert dr.traslados[0].base == D("500.000000") and dr.traslados[0].importe == D(
            "80.000000")
        assert p.totales == {"MontoTotalPagos": D("580.00"),
                             "TotalTrasladosBaseIVA16": D("500.00"),
                             "TotalTrasladosImpuestoIVA16": D("80.00")}
        with pytest.raises(FiscalAgentError, match="excede"):
            calculo.pago([calculo.DocumentoPagado("u", "F", "1", c.total, D("10"), 2,
                                                  D("11.00"))])


# ── catálogos y esquemas ──


def _enumeracion(nombre: str) -> set[str]:
    raiz = etree.parse(str(esq_nomina.XSD / "catCFDI.xsd")).getroot()
    xs = "{http://www.w3.org/2001/XMLSchema}"
    tipo = raiz.find(f"{xs}simpleType[@name='{nombre}']")
    assert tipo is not None, nombre
    return {e.get("value") for e in tipo.iter(f"{xs}enumeration")}


@pytest.mark.parametrize("catalogo, nombre", [
    (catalogos.FORMA_PAGO, "c_FormaPago"), (catalogos.METODO_PAGO, "c_MetodoPago"),
    (catalogos.USO_CFDI, "c_UsoCFDI"), (catalogos.REGIMEN_FISCAL, "c_RegimenFiscal"),
    (catalogos.OBJETO_IMP, "c_ObjetoImp"), (catalogos.TIPO_RELACION, "c_TipoRelacion"),
    (catalogos.EXPORTACION, "c_Exportacion"), (catalogos.IMPUESTO, "c_Impuesto"),
    (catalogos.CLAVE_UNIDAD, "c_ClaveUnidad"), (catalogos.CLAVE_PROD_SERV, "c_ClaveProdServ"),
])
def test_catalogos_existen_en_cat_cfdi(catalogo, nombre):
    assert set(catalogo) <= _enumeracion(nombre)


def test_hashes_de_los_xsd_de_pagos():
    for nombre, sha in esquemas.HASHES.items():
        assert hashlib.sha256((esquemas.AQUI / nombre).read_bytes()).hexdigest() == sha


# ── API ──


@pytest.fixture
def entorno(api, sesionador, tmp_path, monkeypatch):
    yield from preparar_entorno(api, sesionador, tmp_path, monkeypatch)


def preparar_entorno(api, sesionador, tmp_path, monkeypatch):
    """Despacho A con dos clientes: `despacho` (emisor, con CSD) y `taller` (receptor)."""
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    monkeypatch.delenv("FISCALITO_PAC", raising=False)
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    registro.limpiar_cache()
    with sesionador() as db:
        asegurar_usuario(db, A)
        db.get(Despacho, A).nombre = "Despacho Pérez"
        almacen_cartera.crear_cliente(db, A, "despacho", {
            "nombre": "Escuela Kemper Urgate", "rfc": RFC_EMISOR, "regimen": "601",
            "codigo_postal": "42501"}, con_tope=False)
        almacen_cartera.crear_cliente(db, A, "taller", {
            "nombre": "Xenon Industrial Articles", "rfc": RFC_RECEPTOR, "regimen": "601",
            "codigo_postal": "76343"}, con_tope=False)
        db.flush()
        emisor = db.query(Cliente).filter_by(despacho_id=A, clave="despacho").one()
        par = certs_sat.generar(rfc=RFC_EMISOR, tipo="csd")
        cred_servicio.guardar(db, emisor, "csd", par.cer, par.key, par.password, A)
        db.commit()
    yield api(A)
    registro.limpiar_cache()


def _factura(**extra):
    return {"tipo": "I", "forma_pago": "03", "metodo_pago": "PUE",
            "receptor": {"clave_cliente": "taller", "uso_cfdi": "G03"},
            "conceptos": [{"clave_prod_serv": "84111500", "cantidad": "1", "clave_unidad": "E48",
                           "descripcion": "Honorarios", "valor_unitario": "5000",
                           "impuestos": [{"tipo": "traslado", "impuesto": "002",
                                          "tasa": "0.16"}]}], **extra}


URL = "/api/v1/clientes/despacho/facturas"


def _xml(http, fid) -> bytes:
    r = http.get(f"{URL}/{fid}/xml")
    assert r.status_code == 200
    return r.content


def test_ingreso_valido_sellado_timbrado_boveda_pdf_y_cancelacion(entorno):
    http = entorno
    r = http.post(URL, json=_factura())
    assert r.status_code == 200, r.text
    f = r.json()["factura"]
    assert f["total"] == "5800.00" and f["es_prueba"] and f["folio"] == "1" and f["serie"] == "F"
    xml = _xml(http, f["id"])
    doc = etree.fromstring(xml)
    assert esquemas.validar(doc) == []
    # el sello verifica con el CSD sobre la cadena original del XSLT oficial
    cadena = esquemas.cadena_original(doc)
    cert = x509.load_der_x509_certificate(base64.b64decode(doc.get("Certificado")))
    cert.public_key().verify(base64.b64decode(doc.get("Sello")), cadena.encode(),
                             padding.PKCS1v15(), hashes.SHA256())
    assert doc.find("c:Complemento/t:TimbreFiscalDigital", NS).get("UUID") == f["uuid"]
    # bóveda del emisor (emitido) y del receptor (recibido)
    emitidos = http.get("/api/v1/boveda/clientes/despacho/cfdi").json()["comprobantes"]
    recibidos = http.get("/api/v1/boveda/clientes/taller/cfdi").json()["comprobantes"]
    assert {c["uuid"] for c in emitidos} == {f["uuid"]} == {c["uuid"] for c in recibidos}
    texto = PdfReader(io.BytesIO(http.get(f"{URL}/{f['id']}/pdf").content)).pages[0] \
        .extract_text()
    assert f["uuid"] in texto and "NO FISCAL" in texto and "5,800.00" in texto
    # cancelación 02
    r = http.post(f"{URL}/{f['id']}/cancelar", json={"motivo": "02"})
    assert r.status_code == 200, r.text
    assert r.json()["factura"]["estado"] == "cancelado"
    assert http.post(f"{URL}/{f['id']}/cancelar", json={"motivo": "02"}).status_code == 409
    for clave in ("despacho", "taller"):
        bov = http.get(f"/api/v1/boveda/clientes/{clave}/cfdi").json()["comprobantes"]
        assert [(c["uuid"], c["estatus_sat"], c["origen"]) for c in bov] == [
            (f["uuid"], "cancelado", "emision")]


@pytest.mark.parametrize("motivo", ["03", "04"])
def test_cancelacion_motivos_03_y_04(entorno, motivo):
    f = entorno.post(URL, json=_factura()).json()["factura"]
    r = entorno.post(f"{URL}/{f['id']}/cancelar", json={"motivo": motivo})
    assert r.status_code == 200 and r.json()["factura"]["motivo_cancelacion"] == motivo


def test_cancelacion_01_exige_sustituta_que_la_relacione(entorno):
    http = entorno
    vieja = http.post(URL, json=_factura()).json()["factura"]
    assert http.post(f"{URL}/{vieja['id']}/cancelar", json={"motivo": "01"}).status_code == 422
    otra = http.post(URL, json=_factura()).json()["factura"]
    assert http.post(f"{URL}/{vieja['id']}/cancelar", json={
        "motivo": "01", "folio_sustitucion": otra["uuid"]}).status_code == 422
    nueva = http.post(URL, json=_factura(relacionados=[
        {"tipo_relacion": "04", "uuids": [vieja["uuid"]]}])).json()["factura"]
    xml = _xml(http, nueva["id"])
    assert etree.fromstring(xml).find("c:CfdiRelacionados", NS).get("TipoRelacion") == "04"
    r = http.post(f"{URL}/{vieja['id']}/cancelar", json={
        "motivo": "01", "folio_sustitucion": nueva["uuid"]})
    assert r.status_code == 200, r.text
    assert r.json()["factura"]["folio_sustitucion"] == nueva["uuid"]


def test_egreso_y_pago_ppd_con_parcialidades(entorno):
    http = entorno
    ppd = http.post(URL, json=_factura(metodo_pago="PPD", forma_pago="99")).json()["factura"]
    assert ppd["saldo"] == "5800.00"
    assert http.post(URL, json=_factura(metodo_pago="PPD")).status_code == 422  # forma ≠ 99
    # nota de crédito sin relacionar → 422; relacionada → válida
    assert http.post(URL, json=_factura(tipo="E")).status_code == 422
    nc = http.post(URL, json=_factura(tipo="E", relacionados=[
        {"tipo_relacion": "01", "uuids": [ppd["uuid"]]}])).json()["factura"]
    assert nc["serie"] == "NC" and esquemas.validar(etree.fromstring(_xml(http, nc["id"]))) == []
    # dos parcialidades
    pago = {"fecha_pago": "2026-10-10T12:00:00", "forma_pago": "03",
            "documentos": [{"factura_id": ppd["id"], "importe_pagado": "2900.00"}]}
    p1 = http.post(f"{URL}/pagos", json=pago)
    assert p1.status_code == 200, p1.text
    p1 = p1.json()["factura"]
    doc = etree.fromstring(_xml(http, p1["id"]))
    assert esquemas.validar(doc) == []
    assert doc.get("TipoDeComprobante") == "P" and doc.get("Total") == "0"
    dr = doc.find("c:Complemento/p:Pagos/p:Pago/p:DoctoRelacionado", NS)
    assert (dr.get("NumParcialidad"), dr.get("ImpSaldoAnt"), dr.get("ImpSaldoInsoluto")) == (
        "1", "5800.00", "2900.00")
    totales = doc.find("c:Complemento/p:Pagos/p:Totales", NS)
    assert totales.get("TotalTrasladosBaseIVA16") == "2500.00"
    assert totales.get("TotalTrasladosImpuestoIVA16") == "400.00"
    assert http.get(f"{URL}/{ppd['id']}").json()["factura"]["saldo"] == "2900.00"
    # la factura con pagos vigentes no se cancela
    assert http.post(f"{URL}/{ppd['id']}/cancelar", json={"motivo": "02"}).status_code == 409
    p2 = http.post(f"{URL}/pagos", json={**pago, "documentos": [
        {"factura_id": ppd["id"], "importe_pagado": "3000.00"}]})
    assert p2.status_code == 422  # excede el saldo
    p2 = http.post(f"{URL}/pagos", json=pago).json()["factura"]
    dr2 = etree.fromstring(_xml(http, p2["id"])).find(
        "c:Complemento/p:Pagos/p:Pago/p:DoctoRelacionado", NS)
    assert (dr2.get("NumParcialidad"), dr2.get("ImpSaldoInsoluto")) == ("2", "0.00")
    # cancelar el segundo pago regresa el saldo
    assert http.post(f"{URL}/{p2['id']}/cancelar", json={"motivo": "02"}).status_code == 200
    assert http.get(f"{URL}/{ppd['id']}").json()["factura"]["saldo"] == "2900.00"
    texto = PdfReader(io.BytesIO(http.get(f"{URL}/{p1['id']}/pdf").content)).pages[0] \
        .extract_text()
    assert "pagos 2.0" in texto and p1["uuid"] in texto
    tipos = [x["tipo"] for x in http.get(URL).json()["facturas"]]
    assert sorted(tipos) == ["E", "I", "P", "P"]


def test_honorarios_del_despacho_ligados_al_cargo(entorno, sesionador, api):
    http = entorno
    with sesionador() as db:
        taller = db.query(Cliente).filter_by(despacho_id=A, clave="taller").one()
        cargo = CargoCobranza(despacho_id=A, cliente_id=taller.id, tipo="servicio",
                              concepto="Honorarios octubre", fecha=date(2026, 10, 5),
                              vencimiento=date(2026, 10, 15), importe=D("5000.00"))
        db.add(cargo)
        db.commit()
        cargo_id = cargo.id
    assert http.get(f"/api/v1/facturacion/cargos/{cargo_id}/borrador").status_code == 409
    r = http.put("/api/v1/facturacion/config", json={"cliente_propio": "despacho"})
    assert r.status_code == 200 and r.json()["cliente_propio"] == "despacho"
    b = http.get(f"/api/v1/facturacion/cargos/{cargo_id}/borrador").json()["borrador"]
    assert b["emisor"] == "despacho" and b["metodo_pago"] == "PPD"
    assert b["conceptos"][0]["valor_unitario"] == "5000.00"
    cuerpo = {k: v for k, v in b.items() if k != "emisor"}
    f = http.post(URL, json=cuerpo)
    assert f.status_code == 200, f.text
    f = f.json()["factura"]
    assert f["cargo_id"] == cargo_id
    cargos = http.get("/api/v1/cobranza/clientes/taller").json()["cargos"]
    assert cargos[0]["uuid_cfdi"] == f["uuid"]
    # facturarlo otra vez sin sustitución → 409
    assert http.post(URL, json=cuerpo).status_code == 409
    # el auxiliar, aunque tenga asignado al cliente propio, no factura a nombre del despacho
    with sesionador() as db:
        db.add(Usuario(uid="uid-fact-aux", despacho_id=A, rol="auxiliar"))
        propio = db.query(Cliente).filter_by(despacho_id=A, clave="despacho").one()
        db.flush()
        db.add(AsignacionCliente(usuario_uid="uid-fact-aux", cliente_id=propio.id))
        db.commit()
    aux = api("uid-fact-aux")
    assert aux.get(URL).status_code == 200
    assert aux.post(URL, json=_factura()).status_code == 403
    # cancelar libera el cargo
    assert http.post(f"{URL}/{f['id']}/cancelar", json={"motivo": "03"}).status_code == 200
    assert http.get("/api/v1/cobranza/clientes/taller").json()["cargos"][0]["uuid_cfdi"] is None


def test_faltantes_y_xsd_antes_del_pac(entorno):
    http = entorno
    r = http.post("/api/v1/clientes/taller/facturas", json=_factura(
        receptor={"rfc": RFC_EMISOR, "nombre": "X", "regimen": "601", "codigo_postal": "42501"}))
    assert r.status_code in (404, 409, 422)  # taller no tiene CSD
    r = http.post(URL, json=_factura(receptor={"rfc": "XAXX010101000", "nombre": "PUBLICO",
                                               "regimen": "616", "codigo_postal": "42501",
                                               "uso_cfdi": "S01"},
                                     conceptos=[{"clave_prod_serv": "99999999",
                                                 "cantidad": "1", "clave_unidad": "E48",
                                                 "descripcion": "x", "valor_unitario": "1",
                                                 "impuestos": [{"tipo": "traslado",
                                                                "impuesto": "002",
                                                                "tasa": "0.16"}]}]))
    assert r.status_code == 422 and "XSD" in r.json()["error"]


def test_multi_tenant(entorno, api):
    f = entorno.post(URL, json=_factura()).json()["factura"]
    b = api(B)
    assert b.get(URL).status_code == 404
    assert b.get(f"{URL}/{f['id']}/xml").status_code == 404
    assert b.post(f"{URL}/{f['id']}/cancelar", json={"motivo": "02"}).status_code == 404
    assert b.get("/api/v1/facturacion/config").json()["cliente_propio"] is None
    assert b.put("/api/v1/facturacion/config",
                 json={"cliente_propio": "despacho"}).status_code == 404


@pytest.mark.parametrize("regimen, isr", [("626", "0.012500"), ("612", "0.100000")])
def test_borrador_pf_a_moral_retiene_iva_dos_tercios_tambien_en_resico(
        entorno, sesionador, regimen, isr):
    # Revisor P5 B1: RESICO cambia la retención de ISR (Art. 113-J LISR), no quita la de IVA
    # de 2/3 (Art. 1o.-A fr. II inciso a LIVA; Art. 3o. fr. I RLIVA).
    http = entorno
    with sesionador() as db:
        propio = db.query(Cliente).filter_by(despacho_id=A, clave="despacho").one()
        # RFC sintético de persona física (13 caracteres); sólo se usa para el borrador.
        propio.rfc = "XAXX010101AB1"
        propio.datos = {**(propio.datos or {}), "rfc": "XAXX010101AB1", "regimen": regimen}
        taller = db.query(Cliente).filter_by(despacho_id=A, clave="taller").one()
        cargo = CargoCobranza(despacho_id=A, cliente_id=taller.id, tipo="servicio",
                              concepto="Honorarios", fecha=date(2026, 10, 5),
                              vencimiento=date(2026, 10, 15), importe=D("1000.00"))
        db.add(cargo)
        db.commit()
        cargo_id = cargo.id
    http.put("/api/v1/facturacion/config", json={"cliente_propio": "despacho"})
    b = http.get(f"/api/v1/facturacion/cargos/{cargo_id}/borrador").json()["borrador"]
    ret = {(i["impuesto"], i["tasa"]) for i in b["conceptos"][0]["impuestos"]
           if i["tipo"] == "retencion"}
    assert ret == {("002", "0.106667"), ("001", isr)}


def test_iva_trasladado_fuera_de_catalogo_se_rechaza():
    with pytest.raises(FiscalAgentError, match="c_TasaOCuota"):
        calculo.comprobante([_c("100", impuestos=(calculo.ImpuestoEntrada(
            "traslado", "002", "Tasa", D("0.050000")),))])


def test_falso_de_pagos_y_whatsapp_vetado_en_produccion(monkeypatch):
    monkeypatch.setattr(settings, "ENTORNO", "produccion")
    for servicio in ("pagos", "whatsapp"):
        monkeypatch.setenv(registro.variable(servicio), "falso")
        with pytest.raises(FiscalAgentError, match="falsa en producción"):
            registro.obtener(servicio)
