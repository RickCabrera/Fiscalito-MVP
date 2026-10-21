"""
P4-11: CFDI de nómina 4.0 + complemento 1.2 listo para timbrar.

- Cada tipo (ordinaria con subsidio, asimilados, finiquito con separación, incapacidad y horas
  extra, jubilación) valida contra los XSD oficiales versionados en `tests/xsd/`.
- El sello verifica con el CSD sobre la cadena original del XSLT oficial.
- La nómina completa se timbra en segundo plano con el PAC falso, cada recibo con su PDF con QR,
  ZIP de todos, cancelación con motivo, reintento ante caída del PAC y multi-tenant.
"""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree
from pypdf import PdfReader

from app.config import settings
from app.credenciales import certificados
from app.credenciales import servicio as cred_servicio
from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno
from app.modelos.nucleo import Cliente
from app.nomina_cfdi import esquemas, servicio
from app.nomina_engine.cfdi_nomina_xml import (
    ExtrasNomina,
    HorasExtraCfdi,
    IncapacidadCfdi,
    JubilacionCfdi,
    SeparacionCfdi,
    generar_cfdi_nomina,
)
from app.nomina_engine.recibo import (
    DatosPatron,
    DatosTrabajador,
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)
from app.trabajos.cola import procesar_siguiente
from tests.nomina.test_p4_09_movimientos_imss import _emp, _sembrar
from tests.nomina.validacion_xsd import XSD, errores_de_validacion
from tests.plan_p import certs_sat

RFC = "EKU9003173C9"
BASE = "/api/v1/nomina/clientes/imss"
PATRON = DatosPatron(RFC, "CLIENTE IMSS", "601", "Y1234567104", "91000", "VER")
TRABAJADOR = DatosTrabajador(
    rfc="PEPJ800101AB1", nombre="JOSE PENA ALVAREZ", curp="PEPJ800101HVZRRN09",
    numero_seguridad_social="12345678901", codigo_postal="91000",
    fecha_inicio_relacion_laboral=date(2026, 3, 2), antiguedad="P15W", tipo_contrato="01",
    tipo_regimen="02", numero_empleado="E1", puesto="", riesgo_puesto="1",
    periodicidad_pago="04", salario_base_cotizacion=D("420.00"),
    salario_diario_integrado=D("420.00"),
)
FECHA = datetime(2026, 6, 16, 10, 0, 0)


class _Firmante:
    def __init__(self) -> None:
        par = certs_sat.generar(rfc=RFC, tipo="csd", numero="30001000000500003416")
        self._llave = certificados.abrir_llave(par.key, par.password)
        self._cer = par.cer
        self.numero_certificado = par.numero

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str:
        firma = self._llave.sign(datos, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(firma).decode()

    @property
    def certificado_base64(self) -> str:
        return base64.b64encode(self._cer).decode()


def _xml(recibo: Recibo, trabajador=TRABAJADOR, patron=PATRON, tipo="O", extras=None) -> str:
    return generar_cfdi_nomina(recibo, patron, trabajador, FECHA, date(2026, 6, 1),
                               date(2026, 6, 15), date(2026, 6, 15), D("15"), tipo,
                               "NOM", "1", extras)


def _p(tipo, clave, gravado, exento="0.00", concepto="Concepto"):
    return PartidaPercepcion(tipo, clave, concepto, D(gravado), D(exento))


ORDINARIA = Recibo(
    percepciones=(_p("001", "P001", "6300.00"),),
    deducciones=(PartidaDeduccion("002", "D001", "ISR", D("540.12")),
                 PartidaDeduccion("001", "D002", "IMSS", D("170.00"))),
    otros_pagos=(PartidaOtroPago("002", "D100", "SUBSIDIO", D("0.00"), D("123.34")),),
)


class TestGenerador:
    def test_ordinaria_con_subsidio_valida(self):
        xml = _xml(ORDINARIA)
        assert errores_de_validacion(xml) == []
        assert 'SubsidioCausado="123.34"' in xml and 'RegistroPatronal="Y1234567104"' in xml

    def test_asimilados_sin_datos_imss(self):
        t = DatosTrabajador(**{**TRABAJADOR.__dict__, "tipo_regimen": "09", "tipo_contrato": "09",
                               "salario_base_cotizacion": None, "salario_diario_integrado": None})
        patron = DatosPatron(RFC, "CLIENTE IMSS", "601", "", "91000", "VER")
        recibo = Recibo((_p("046", "P046", "10000.00", concepto="Honorarios asimilados"),),
                        (PartidaDeduccion("002", "D001", "ISR", D("1200.00")),))
        xml = _xml(recibo, t, patron)
        assert errores_de_validacion(xml) == []
        for prohibido in ("NumSeguridadSocial", "SalarioBaseCotApor", "RiesgoPuesto",
                          "FechaInicioRelLaboral", "RegistroPatronal", "TotalOtrosPagos"):
            assert prohibido not in xml, prohibido

    def test_finiquito_con_separacion(self):
        t = DatosTrabajador(**{**TRABAJADOR.__dict__, "tipo_regimen": "13", "tipo_contrato": "99",
                               "periodicidad_pago": "99"})
        patron = DatosPatron(RFC, "CLIENTE IMSS", "601", "", "91000", "VER")
        recibo = Recibo(
            (_p("001", "P001", "800.00"), _p("022", "P022", "1000.00", "3000.00"),
             _p("025", "P025", "5000.00", "2000.00")),
            (PartidaDeduccion("002", "D001", "ISR", D("1500.00")),))
        extras = ExtrasNomina(separacion=SeparacionCfdi(D("11000.00"), 3, D("12000.00"),
                                                        D("6000.00"), D("0.00")))
        xml = _xml(recibo, t, patron, "E", extras)
        assert errores_de_validacion(xml) == []
        assert 'TotalSeparacionIndemnizacion="11000.00"' in xml and "NumAñosServicio" in xml

    def test_incapacidad_y_horas_extra(self):
        recibo = Recibo((_p("001", "P001", "6300.00"), _p("019", "P019D", "150.00", "150.00")),
                        (PartidaDeduccion("002", "D001", "ISR", D("600.00")),))
        extras = ExtrasNomina(
            horas_extra=(HorasExtraCfdi("P019D", 2, "01", 4, D("300.00")),),
            incapacidades=(IncapacidadCfdi(2, "02"),))
        xml = _xml(recibo, extras=extras)
        assert errores_de_validacion(xml) == []
        assert 'TipoHoras="01"' in xml and 'DiasIncapacidad="2"' in xml

    def test_jubilacion_una_exhibicion(self):
        recibo = Recibo((_p("039", "P039", "50000.00", "20000.00"),))
        extras = ExtrasNomina(jubilacion=JubilacionCfdi(D("12000.00"), D("38000.00"),
                                                        total_una_exhibicion=D("70000.00")))
        xml = _xml(recibo, tipo="E", extras=extras)
        assert errores_de_validacion(xml) == []
        assert 'TotalJubilacionPensionRetiro="70000.00"' in xml

    def test_sellado_verifica_con_el_csd_y_valida(self):
        firmante = _Firmante()
        sellado, cadena = servicio.sellar(_xml(ORDINARIA).encode(), firmante)
        assert cadena.startswith("||4.0|NOM|1|2026-06-16T10:00:00|") and cadena.endswith("||")
        assert "|1.2|O|2026-06-15|" in cadena  # el complemento entra a la cadena
        doc = etree.fromstring(sellado)
        cert = x509.load_der_x509_certificate(base64.b64decode(doc.get("Certificado")))
        cert.public_key().verify(base64.b64decode(doc.get("Sello")), cadena.encode(),
                                 padding.PKCS1v15(), hashes.SHA256())
        assert esquemas.validar(doc) == [] and errores_de_validacion(sellado) == []

    def test_las_copias_de_los_xsd_son_identicas(self):
        for nombre in ("cfdv40.xsd", "nomina12.xsd", "catCFDI.xsd", "catNomina.xsd",
                       "tdCFDI.xsd", "TimbreFiscalDigitalv11.xsd", "envoltorio_validacion.xsd"):
            assert hashlib.sha256((esquemas.XSD / nombre).read_bytes()).digest() == \
                hashlib.sha256((XSD / nombre).read_bytes()).digest(), nombre


# ── la nómina completa por la API ──


@pytest.fixture
def entorno(api, sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    monkeypatch.delenv("FISCALITO_PAC", raising=False)
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    registro.limpiar_cache()
    http = api("uid-timbra")
    _sembrar(http, [_emp(), _emp("E2", nss="98765432109", rfc="LOAM850505AB2",
                                 curp="LOAM850505MVZPRR03", nombre="MARIA LOPEZ",
                                 apellido_paterno="LOPEZ", nombres="MARIA")])
    db = sesionador()
    cliente = db.query(Cliente).filter_by(clave="imss", despacho_id="uid-timbra").one()
    par = certs_sat.generar(rfc=RFC, tipo="csd")
    cred_servicio.guardar(db, cliente, "csd", par.cer, par.key, par.password, "uid-timbra")
    db.commit()
    db.close()
    yield http
    registro.limpiar_cache()


def _quincena_cerrada(http) -> int:
    r = http.post("/api/v1/nomina/calcular-periodo", json={
        "cliente": "imss", "periodo": {"inicio": "2026-06-01", "fin": "2026-06-15"},
        "incidencias": [
            {"empleado_no": "E1", "dias_periodo": 15, "faltas": 0, "dias_ausentismo": 0},
            {"empleado_no": "E2", "dias_periodo": 15, "faltas": 0, "dias_ausentismo": 0}],
        "variables": [{"empleado_no": "E1", "horas_dobles": "4",
                       "incapacidades": [{"tipo": "02", "dias": 2}]}]})
    assert r.status_code == 200, r.text
    pid = r.json()["periodo_id"]
    assert http.post(f"{BASE}/periodos/{pid}/cerrar").status_code == 200
    return pid


class TestTimbradoNomina:
    def test_nomina_completa_timbrada_con_pdf_zip_y_cancelacion(self, entorno, sesionador, api):
        http = entorno
        pid = _quincena_cerrada(http)
        r = http.post(f"{BASE}/periodos/{pid}/timbrar")
        assert r.status_code == 200, r.text
        assert r.json()["por_estado"] == {"pendiente": 2}
        assert procesar_siguiente(sesionador).estado == "hecho"
        estado = http.get(f"{BASE}/periodos/{pid}/cfdi").json()
        assert estado["estado_periodo"] == "timbrada" and estado["por_estado"] == {"timbrado": 2}
        assert estado["trabajo"]["estado"] == "hecho"
        for c in estado["recibos"]:
            assert c["uuid"] and c["es_prueba"] and c["pac"] == "falso"
            xml = http.get(f"{BASE}/periodos/{pid}/cfdi/{c['id']}/xml").content
            assert errores_de_validacion(xml) == [], c["empleado_no"]
            assert b"NO FISCAL" in xml
            pdf = http.get(f"{BASE}/periodos/{pid}/cfdi/{c['id']}/pdf")
            texto = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
            assert c["uuid"] in texto and "NO FISCAL" in texto
        e1 = next(c for c in estado["recibos"] if c["empleado_no"] == "E1")
        xml = http.get(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/xml").text
        assert "<nomina12:HorasExtra " in xml and "<nomina12:Incapacidad " in xml
        # ReciboNomina.uuid_cfdi y la bóveda
        hist = http.get(f"{BASE}/periodos/{pid}").json()
        assert hist["periodo"]["estado"] == "timbrada"
        bov = http.get("/api/v1/boveda/clientes/imss/cfdi").json()
        assert {e1["uuid"]} <= {c["uuid"] for c in bov["comprobantes"]}

        z = zipfile.ZipFile(io.BytesIO(http.get(f"{BASE}/periodos/{pid}/cfdi.zip").content))
        assert len(z.namelist()) == 4

        # otro despacho no ve nada
        otro = api("uid-otro-timbra")
        assert otro.get(f"{BASE}/periodos/{pid}/cfdi").status_code == 404
        assert otro.get(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/xml").status_code == 404
        assert otro.post(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/cancelar",
                         json={"motivo": "02"}).status_code == 404

        r = http.post(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/cancelar", json={"motivo": "02"})
        assert r.status_code == 200, r.text
        assert r.json()["cfdi"]["estado"] == "cancelado" and r.json()["estado_periodo"] == "cerrada"
        assert http.post(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/cancelar",
                         json={"motivo": "02"}).status_code == 409
        assert http.post(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/cancelar",
                         json={"motivo": "01"}).status_code in (409, 422)
        # re-timbrar sólo el cancelado
        http.post(f"{BASE}/periodos/{pid}/timbrar")
        procesar_siguiente(sesionador)
        estado = http.get(f"{BASE}/periodos/{pid}/cfdi").json()
        assert estado["estado_periodo"] == "timbrada"
        assert sorted(c["estado"] for c in estado["recibos"]) == [
            "cancelado", "timbrado", "timbrado"]

    def test_horas_por_dia_con_bloque_partido_timbran_y_cuadran(self, entorno, sesionador):
        # Revisor P6-07 B1: quincena al 15-08-2026, 3 h los días 1-3, 8-10 y 15. El tope
        # proporcional deja dobles y triples; el CFDI debe declarar las mismas horas.
        http = entorno
        dias = ["3", "3", "3", "0", "0", "0", "0", "3", "3", "3", "0", "0", "0", "0", "3"]
        r = http.post("/api/v1/nomina/calcular-periodo", json={
            "cliente": "imss", "periodo": {"inicio": "2026-08-01", "fin": "2026-08-15"},
            "incidencias": [
                {"empleado_no": "E1", "dias_periodo": 15, "faltas": 0, "dias_ausentismo": 0},
                {"empleado_no": "E2", "dias_periodo": 15, "faltas": 0, "dias_ausentismo": 0}],
            "variables": [{"empleado_no": "E1", "horas_extra_por_dia": dias}]})
        assert r.status_code == 200, r.text
        pid = r.json()["periodo_id"]
        assert http.post(f"{BASE}/periodos/{pid}/cerrar").status_code == 200
        assert http.post(f"{BASE}/periodos/{pid}/timbrar").status_code == 200
        assert procesar_siguiente(sesionador).estado == "hecho"
        estado = http.get(f"{BASE}/periodos/{pid}/cfdi").json()
        assert estado["por_estado"] == {"timbrado": 2}, estado
        e1 = next(c for c in estado["recibos"] if c["empleado_no"] == "E1")
        xml = http.get(f"{BASE}/periodos/{pid}/cfdi/{e1['id']}/xml").content
        assert errores_de_validacion(xml) == []
        assert b'TipoHoras="02"' in xml and b'TipoHoras="01"' in xml
        # Revisor P6 B1: las horas declaradas suman las trabajadas y cuadran con el importe.
        nodos = etree.fromstring(xml).iter("{http://www.sat.gob.mx/nomina12}HorasExtra")
        por_tipo = {n.get("TipoHoras"): (int(n.get("HorasExtra")), D(n.get("ImportePagado")))
                    for n in nodos}
        assert por_tipo["01"][0] + por_tipo["02"][0] == 21
        hora_doble = por_tipo["01"][1] / por_tipo["01"][0]
        hora_triple = por_tipo["02"][1] / por_tipo["02"][0]
        assert abs(hora_triple - hora_doble * D("1.5")) <= D("0.01")

    def test_no_timbra_una_nomina_abierta(self, entorno):
        r = entorno.post("/api/v1/nomina/calcular-periodo", json={
            "cliente": "imss", "periodo": {"inicio": "2026-06-01", "fin": "2026-06-15"},
            "incidencias": [{"empleado_no": "E1", "dias_periodo": 15, "faltas": 0,
                             "dias_ausentismo": 0}]})
        pid = r.json()["periodo_id"]
        assert entorno.post(f"{BASE}/periodos/{pid}/timbrar").status_code == 409

    def test_dato_faltante_es_error_por_recibo_y_se_corrige(self, entorno, sesionador):
        http = entorno
        http.put("/api/v1/cartera/clientes/imss/empleados/E2", json=_emp(
            "E2", nss="98765432109", rfc="", curp="LOAM850505MVZPRR03", nombre="MARIA LOPEZ",
            apellido_paterno="LOPEZ", nombres="MARIA"))
        pid = _quincena_cerrada(http)
        http.post(f"{BASE}/periodos/{pid}/timbrar")
        procesar_siguiente(sesionador)
        estado = http.get(f"{BASE}/periodos/{pid}/cfdi").json()
        assert estado["por_estado"] == {"timbrado": 1, "error": 1}
        e2 = next(c for c in estado["recibos"] if c["empleado_no"] == "E2")
        assert "RFC del trabajador" in e2["error"]
        assert estado["estado_periodo"] == "cerrada"
        http.put("/api/v1/cartera/clientes/imss/empleados/E2", json=_emp(
            "E2", nss="98765432109", rfc="LOAM850505AB2", curp="LOAM850505MVZPRR03",
            nombre="MARIA LOPEZ", apellido_paterno="LOPEZ", nombres="MARIA"))
        http.post(f"{BASE}/periodos/{pid}/timbrar")
        procesar_siguiente(sesionador)
        assert http.get(f"{BASE}/periodos/{pid}/cfdi").json()["por_estado"] == {"timbrado": 2}

    def test_caida_del_pac_se_reintenta_sin_duplicar(self, entorno, sesionador):
        http = entorno
        pid = _quincena_cerrada(http)
        pac = registro.obtener("pac")
        original = pac.timbrar
        llamadas = []

        def falla_una_vez(xml, tipo="cfdi"):
            llamadas.append(1)
            if len(llamadas) == 2:
                raise ErrorServicioExterno("timeout")
            return original(xml, tipo)

        pac.timbrar = falla_una_vez  # type: ignore[method-assign]
        try:
            http.post(f"{BASE}/periodos/{pid}/timbrar")
            t = procesar_siguiente(sesionador)
            assert t.estado == "pendiente" and "PAC" in (t.error or "")
            assert http.get(f"{BASE}/periodos/{pid}/cfdi").json()["por_estado"] == {
                "timbrado": 1, "reintento": 1}
            despues = datetime(2030, 1, 1, tzinfo=t.ejecutar_en.tzinfo)
            t = procesar_siguiente(sesionador, ahora=despues)
            assert t.estado == "hecho"
        finally:
            pac.timbrar = original  # type: ignore[method-assign]
        assert len(llamadas) == 3
        assert http.get(f"{BASE}/periodos/{pid}/cfdi").json()["por_estado"] == {"timbrado": 2}

    def test_asimilados_y_finiquito_se_timbran(self, entorno, sesionador):
        http = entorno
        http.put("/api/v1/cartera/clientes/imss/empleados/A1", json=_emp(
            "A1", tipo_regimen="09", nss="", rfc="GOVA700101AB3", curp="GOVA700101HVZMLR05",
            nombre="ANA GOMEZ", apellido_paterno="GOMEZ", nombres="ANA"))
        r = http.post("/api/v1/nomina/calcular-periodo", json={
            "cliente": "imss", "tipo": "asimilados",
            "periodo": {"inicio": "2026-06-01", "fin": "2026-06-15"}, "incidencias": []})
        assert r.status_code == 200, r.text
        asim = r.json()["periodo_id"]
        r = http.post(f"{BASE}/finiquito", json={"empleado_no": "E1", "fecha_baja": "2026-06-30",
                                                 "causa": "despido_injustificado"})
        assert r.status_code == 200, r.text
        fin = r.json()["periodo_id"]
        for pid in (asim, fin):
            http.post(f"{BASE}/periodos/{pid}/cerrar")
            assert http.post(f"{BASE}/periodos/{pid}/timbrar").status_code == 200
            procesar_siguiente(sesionador)
            estado = http.get(f"{BASE}/periodos/{pid}/cfdi").json()
            assert set(estado["por_estado"]) == {"timbrado"}, estado
            xml = http.get(f"{BASE}/periodos/{pid}/cfdi/{estado['recibos'][0]['id']}/xml").text
            assert errores_de_validacion(xml.encode()) == []
            if pid == asim:
                assert 'TipoRegimen="09"' in xml and "NumSeguridadSocial" not in xml
            else:
                assert 'TipoNomina="E"' in xml and 'TipoRegimen="13"' in xml
                assert "SeparacionIndemnizacion" in xml and 'PeriodicidadPago="99"' in xml
