"""
P4-12 · Dispersión bancaria: CLABE, ficha, cada layout (longitudes, campos y total al
centavo), excluidos, cuadre contra la nómina cerrada y multi-tenant.
"""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.dispersion import registro_fijo as rf
from app.dispersion.bancos import banamex, banorte
from app.dispersion.catalogo import LAYOUTS, layout_por_id
from app.dispersion.clabe import digito_verificador, es_clabe_valida, motivo_clabe_invalida
from app.dispersion.tipos import Abono, Cargo, Opciones, Pago
from app.exceptions import FiscalAgentError
from app.schemas.empleado import EmpleadoCarteraSchema
from app.schemas.empleado_pago import normalizar_celular
from tests.plan_p.nomina_cerrada import clabe, nomina_cerrada

# ── CLABE (mismo vector que apps/store/src/services/clabe.test.ts) ──


class TestClabe:
    def test_vector_publico_valido(self):
        assert digito_verificador("03218000011835971") == 9
        assert es_clabe_valida("032180000118359719")

    @pytest.mark.parametrize("mala,texto", [
        ("032180000118359718", "verificador"),  # último dígito alterado
        ("032180000118359", "18 dígitos"),
        ("03218000011835971X", "sólo lleva dígitos"),
        ("132180000118359719", "verificador"),  # banco alterado
    ])
    def test_invalidas(self, mala, texto):
        assert texto in (motivo_clabe_invalida(mala) or "")

    def test_ficha_rechaza_clabe_mala_y_toma_el_banco_de_la_buena(self):
        base = {"empleado_no": "1", "nombre": "X", "salario_diario": "300",
                "salario_diario_integrado": "315"}
        with pytest.raises(ValidationError, match="verificador"):
            EmpleadoCarteraSchema(**base, clabe="032180000118359718")
        ficha = EmpleadoCarteraSchema(**base, clabe="032 180 000118359719")
        assert ficha.clabe == "032180000118359719" and ficha.banco == "032"
        with pytest.raises(ValidationError, match="no es el de la CLABE"):
            EmpleadoCarteraSchema(**base, clabe="032180000118359719", banco="012")

    def test_celular_e164_mexicano_y_consentimiento(self):
        assert normalizar_celular("55 1234-5678") == "+525512345678"
        assert normalizar_celular("+5215512345678") == "+525512345678"
        assert normalizar_celular("525512345678") == "+525512345678"
        with pytest.raises(ValueError, match="E.164"):
            normalizar_celular("+15551234567")
        with pytest.raises(ValidationError, match="consentimiento"):
            EmpleadoCarteraSchema(empleado_no="1", nombre="X", salario_diario="300",
                                  salario_diario_integrado="315", consentimiento_whatsapp=True)


# ── Cada layout: longitudes, campos y total al centavo ──

OP = Opciones(fecha_aplicacion=date(2026, 8, 31), concepto="NOMINA 20260816-20260831",
              razon_social="TALLER EJEMPLO SA DE CV", referencia_numerica=42,
              datos_banco={"numero_cliente": "123456789012", "emisora": "12345",
                           "convenio": "54321", "referencia_empresa": "77"})
CENTAVOS = (1234567, 89, 100000)
CARGOS = {"bbva": "0987654321", "banamex": "70001234567", "santander": "65501234567",
          "banorte": "0123456789", "hsbc": "4001234567", "scotiabank": "01234567890",
          "banbajio": "1234567890"}
CUENTAS_PROPIAS = {"bbva": "1234567890", "banamex": "12345678901", "santander": "12345678901",
                   "banorte": "1234567890", "hsbc": "1234567890", "scotiabank": "12345678901",
                   "banbajio": "1234567890"}
# (longitudes por renglón, cómo reconocer el detalle, posición 1-based del importe, ancho)
ESPERADO = {
    "bbva": ([108, 108, 108], lambda x: True, 48, 15),
    "banamex": ([84, 51, 419, 419, 419, 52], lambda x: x[0] == "3", 11, 18),
    "santander": ([39, 127, 127, 127, 29], lambda x: x[0] == "2", 110, 18),
    "banorte": ([165, 165, 165, 165], lambda x: x[0] == "D", 100, 15),
    "hsbc": ([85, 93, 93, 93], lambda x: not x.startswith("MXPRLF"), 11, 14),
    "scotiabank": ([46, 46, 136, 136, 136, 49, 49], lambda x: x.startswith("EEDA"), 9, 15),
    "banbajio": ([51, 95, 95, 95, 23], lambda x: x.startswith("02"), 31, 15),
}


def _pagos(layout_id: str) -> list[tuple[Pago, Abono]]:
    lay = layout_por_id(layout_id)
    salida = []
    for i, c in enumerate(CENTAVOS, start=1):
        p = Pago(empleado_no=f"E{i}", nombre=f"JOSÉ MUÑOZ {i}", centavos=c, banco=lay.banco or "",
                 numero_cuenta=CUENTAS_PROPIAS[layout_id], nombres="JOSÉ",
                 apellido_paterno="MUÑOZ", apellido_materno="PÉREZ", rfc="XAXX010101000")
        a = lay.abono(p)
        assert isinstance(a, Abono), a
        salida.append((p, a))
    return salida


@pytest.mark.parametrize("layout_id", sorted(ESPERADO))
def test_layout_longitudes_importe_y_total_al_centavo(layout_id):
    lay = layout_por_id(layout_id)
    pagos = _pagos(layout_id)
    contenido = lay.generar(pagos, Cargo(banco=lay.banco or "", numero=CARGOS[layout_id]), OP)
    texto = contenido.decode("ascii")
    assert texto.endswith("\r\n") and "Ñ" not in texto and "É" not in texto
    renglones = texto.split("\r\n")[:-1]
    largos, es_detalle, pos, ancho = ESPERADO[layout_id]
    assert [len(x) for x in renglones] == largos
    detalles = [x for x in renglones if es_detalle(x)]
    assert [int(x[pos - 1:pos - 1 + ancho]) for x in detalles] == list(CENTAVOS)
    assert lay.importes(contenido) == list(CENTAVOS)
    assert sum(lay.importes(contenido)) == 1334656  # $13,346.56 al centavo


def test_banamex_campos_del_layout_d():
    pagos = _pagos("banamex")
    texto = layout_por_id("banamex").generar(pagos, Cargo("002", "70001234567"), OP).decode()
    control, glob, det1, *_, tot = texto.split("\r\n")[:-1]
    assert control[0] == "1" and control[1:13] == "123456789012" and control[13:19] == "260831"
    assert control[79:84] == "15D01"
    assert glob[:5] == "21001" and glob[5:23] == "000000000001334656"
    assert glob[23:25] == "01" and glob[25:45] == "00000000070001234567" and glob[45:] == "000003"
    assert det1[:10] == "3000101001" and det1[28:30] == "01"
    assert det1[30:50] == "00000000012345678901" and det1[50:66].rstrip() == "E1"
    assert det1[66:121].rstrip() == "JOSE,MUNOZ/PEREZ".replace("MUNOZ", "MU@OZ")
    assert tot == "4001000003000000000001334656000001000000000001334656"


def test_banamex_interbancario_con_clabe():
    lay = banamex.Banamex()
    p = Pago("E9", "LUIS PEREZ", 5000, banco="012", clabe=clabe("012", "1"), nombres="LUIS",
             apellido_paterno="PEREZ", apellido_materno="DIAZ")
    a = lay.abono(p)
    assert isinstance(a, Abono) and a.interbancario and a.tipo == "clabe"
    det = rf.leer(banamex.DETALLE, lay.generar([(p, a)], Cargo("002", "70001234567"),
                                               OP).decode().split("\r\n")[2])
    assert det["metodo"] == "002" and det["tipo_cuenta"] == "40"
    assert det["cuenta"] == "00" + p.clabe and det["banco"] == "0012"
    assert det["referencia"] == "0000042         "
    sin_apellidos = Pago("E8", "X", 1, banco="012", clabe=clabe("012", "2"))
    assert "NOMBRE,PATERNO/MATERNO" in lay.abono(sin_apellidos)


def test_banorte_detalle_con_clabe_de_otro_banco():
    lay = banorte.Banorte()
    p = Pago("E2", "LUIS", 123456, banco="012", clabe=clabe("012", "1234567890"))
    a = lay.abono(p)
    det = rf.leer(banorte.DETALLE, lay.generar([(p, a)], Cargo("072", "0123456789"),
                                               OP).decode().split("\r\n")[1])
    assert (det["banco"], det["tipo_cuenta"], det["cuenta"]) == ("012", "40", p.clabe)
    assert det["importe"] == "000000000123456" and det["fecha"] == "20260831"


def test_layouts_sin_interbancario_excluyen_con_motivo():
    p = Pago("E2", "LUIS", 1, banco="012", clabe=clabe("012", "1"))
    for lid in ("santander", "hsbc", "banbajio"):
        motivo = layout_por_id(lid).abono(p)
        assert isinstance(motivo, str) and "sólo abona" in motivo


def test_generico_csv_y_xlsx_configurable():
    pagos = _pagos("bbva")
    for formato in ("csv", "xlsx"):
        lay = layout_por_id("generico", columnas=["empleado_no", "clabe", "importe"],
                            formato=formato, separador="|")
        contenido = lay.generar(pagos, Cargo(""), OP)
        assert lay.importes(contenido) == list(CENTAVOS)
    csv = layout_por_id("generico", columnas=["empleado_no", "importe"], separador="|")
    texto = csv.generar(pagos, Cargo(""), OP).decode("utf-8-sig")
    assert texto.split("\r\n")[1] == "E1|12345.67"
    with pytest.raises(FiscalAgentError, match="importe"):
        layout_por_id("generico", columnas=["empleado_no"])


def test_todos_declaran_fuente_y_estado():
    for clase in LAYOUTS.values():
        assert clase.estado in ("verificado", "por_confirmar") and clase.fuente
        if clase.estado == "por_confirmar":
            assert "POR CONFIRMAR CON MANUAL DEL BANCO" in clase.fuente
    assert {c.id for c in LAYOUTS.values() if c.estado == "verificado"} == {
        "banamex", "banorte", "generico"}


# ── De punta a punta: nómina cerrada → archivo, excluidos y cuadre ──

URL = "/api/v1/nomina/clientes/{c}/periodos/{p}/dispersion"


def test_banamex_cuadra_al_centavo_y_reporta_excluidos(api, sesionador):
    n = nomina_cerrada(api, sesionador)
    r = n["http"].post(URL.format(c=n["clave"], p=n["pid"]), json={
        "layout": "banamex", "cuenta_cargo_id": n["cuentas"]["002"],
        "datos_banco": {"numero_cliente": "123456789012"}})
    assert r.status_code == 200, r.text
    j = r.json()
    netos = {k: D(v) for k, v in n["netos"].items()}
    causas = {e["empleado_no"]: e["causa"] for e in j["excluidos"]}
    # E3 efectivo, E4 sin cuenta, E5 interbancario sin apellidos (Banamex los exige).
    assert causas == {"E3": "efectivo", "E4": "sin_cuenta", "E5": "layout"}
    assert sorted(i["empleado_no"] for i in j["incluidos"]) == ["E1", "E2"]
    assert D(j["total_archivo"]) == netos["E1"] + netos["E2"]
    assert D(j["total_archivo"]) + D(j["total_excluidos"]) == sum(netos.values())
    assert D(j["total_nomina"]) == sum(netos.values()) and j["cuadra"] is True
    contenido = base64.b64decode(j["archivo"]["base64"])
    assert layout_por_id("banamex").importes(contenido) == [
        int(netos["E1"] * 100), int(netos["E2"] * 100)]
    assert j["incluidos"][0]["cuenta"].startswith("****")


def test_generico_incluye_todos_los_transferibles(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-gen")
    j = n["http"].post(URL.format(c=n["clave"], p=n["pid"]), json={"layout": "generico"}).json()
    assert sorted(i["empleado_no"] for i in j["incluidos"]) == ["E1", "E2", "E5"]
    assert j["cuadra"] and j["archivo"]["nombre"].endswith(".csv")


def test_neto_cero_se_excluye(api, sesionador):
    from sqlalchemy import select

    from app.modelos.nomina import NominaPeriodo, ReciboNomina

    n = nomina_cerrada(api, sesionador, uid="uid-cero")
    s = sesionador()
    rec = s.scalar(select(ReciboNomina).where(ReciboNomina.periodo_id == n["pid"],
                                              ReciboNomina.empleado_no == "E1"))
    per = s.get(NominaPeriodo, n["pid"])
    per.total_neto -= rec.neto
    rec.neto = D("0.00")
    s.commit()
    s.close()
    j = n["http"].post(URL.format(c=n["clave"], p=n["pid"]), json={"layout": "generico"}).json()
    assert {e["empleado_no"]: e["causa"] for e in j["excluidos"]}["E1"] == "neto_cero"


def test_errores_de_entrada(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-err")
    url = URL.format(c=n["clave"], p=n["pid"])
    sin_cliente = n["http"].post(url, json={"layout": "banamex",
                                            "cuenta_cargo_id": n["cuentas"]["002"]})
    assert sin_cliente.status_code == 422 and "cliente" in sin_cliente.json()["error"]
    otro_banco = n["http"].post(url, json={"layout": "banorte",
                                           "cuenta_cargo_id": n["cuentas"]["002"],
                                           "datos_banco": {"emisora": "1"}})
    assert otro_banco.status_code == 422 and "cuenta de cargo" in otro_banco.json()["error"]
    assert n["http"].post(url, json={"layout": "banorte"}).status_code == 422


def test_sin_cerrar_es_409_y_multitenant(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-mt")
    ajeno = api("uid-ajeno")
    url = URL.format(c=n["clave"], p=n["pid"])
    assert ajeno.post(url, json={"layout": "generico"}).status_code == 404
    r = n["http"].post("/api/v1/nomina/calcular-periodo", json={
        "cliente": n["clave"], "periodo": {"inicio": "2026-09-01", "fin": "2026-09-15"},
        "incidencias": [{"empleado_no": "E1", "dias_periodo": 15, "faltas": 0,
                         "dias_ausentismo": 0}]})
    abierto = r.json()["periodo_id"]
    r = n["http"].post(URL.format(c=n["clave"], p=abierto), json={"layout": "generico"})
    assert r.status_code == 409


def test_catalogo_de_layouts_por_api(api):
    j = api("uid-cat").get("/api/v1/nomina/dispersion/layouts").json()
    ids = {x["id"] for x in j["layouts"]}
    assert ids == {"bbva", "banamex", "santander", "banorte", "hsbc", "scotiabank", "banbajio",
                   "generico"}
