"""
P4-09: movimientos afiliatorios completos — historial de SBC, baja con causa, layouts IDSE
02/07/08 con longitudes y posiciones exactas, archivos de importación al SUA, estado de envío
y multi-tenant. Datos sintéticos (NSS, CURP y RFC inventados con forma válida).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine import imss_layouts as L
from tests.nomina.cartera_sembrada import sembrar_cliente

RP = "Y1234567104"
GUIA = "01234"
BASE = "/api/v1/nomina/clientes/imss"


def _emp(no="E1", **extra):
    return {
        "empleado_no": no, "nombre": "JOSÉ PEÑA ÁLVAREZ", "apellido_paterno": "PEÑA",
        "apellido_materno": "ÁLVAREZ", "nombres": "JOSÉ", "salario_diario": "400.00",
        "salario_diario_integrado": "420.00", "fecha_alta": "2026-03-02",
        "nss": "12345678901", "curp": "PEPJ800101HVZRRN09", "rfc": "PEPJ800101AB1",
        "codigo_postal": "91000", **extra,
    }


def _sembrar(http, empleados=None):
    sembrar_cliente(http, "imss", empleados or [_emp()])
    r = http.put("/api/v1/cartera/clientes/imss", json={
        "id": "imss", "nombre": "CLIENTE IMSS", "prima_riesgo": "0.0054355",
        "registro_patronal": RP, "guia_subdelegacion": GUIA, "rfc": "EKU9003173C9",
        "regimen": "601", "codigo_postal": "91000", "clave_entidad": "VER", "clase_riesgo": 1})
    assert r.status_code == 200, r.text


@pytest.fixture
def http(api):
    c = api("uid-imss")
    _sembrar(c)
    return c


def _movs(http, **params):
    return http.get(f"{BASE}/movimientos-imss", params=params).json()["movimientos"]


def _campo(linea: str, desde: int, hasta: int) -> str:
    return linea[desde - 1:hasta]


# ── layouts puros ──


class TestLayouts:
    @pytest.mark.parametrize("campos, largo", [
        (L.ALTA, 168), (L.MODIFICACION, 168), (L.BAJA, 168), (L.CIFRAS_CONTROL, 168),
        (L.SUA_TRABAJADOR, 164), (L.SUA_MOVIMIENTO, 49),
    ])
    def test_cubren_el_registro_sin_huecos(self, campos, largo):
        L.verificar_layout(campos, largo)

    def test_un_hueco_se_detecta(self):
        roto = tuple(c for c in L.ALTA if c.nombre != "umf")
        with pytest.raises(FiscalValidationError, match="hueco"):
            L.verificar_layout(roto, 168)

    def test_no_trunca(self):
        with pytest.raises(FiscalValidationError, match="no cabe"):
            L.escribir_registro(L.ALTA, {"apellido_paterno": "X" * 28}, 168)

    def test_translitera_a_ascii(self):
        linea, cambiados = L.escribir_registro(L.ALTA, {"apellido_paterno": "PEÑA"}, 168)
        assert _campo(linea, 23, 49) == "PENA".ljust(27) and cambiados == ["apellido_paterno"]
        assert linea.isascii()

    def test_salario_con_decimales_implicitos(self):
        assert L.importe_implicito(D("526.05"), 4) == "052605"
        assert L.importe_implicito(D("526.05"), 5) == "0052605"
        with pytest.raises(FiscalValidationError):
            L.importe_implicito(D("10000.00"), 4)

    def test_fecha_sin_separadores(self):
        assert L.fecha_ddmmaaaa(date(2026, 3, 2)) == "02032026"


# ── del alta al archivo, por la API ──


class TestFlujo:
    def test_el_alta_deja_un_08_pendiente_e_historial(self, http):
        (m,) = _movs(http)
        assert (m["tipo"], m["estado"], m["fecha"], m["sbc"]) == (
            "08", "pendiente", "2026-03-02", "420.00")
        h = http.get(f"{BASE}/empleados/E1/historial-sbc").json()["historial"]
        assert h == [{"fecha": "2026-03-02", "sbc": "420.00", "tipo_salario": "0",
                      "motivo": "alta", "nota": ""}]

    def test_archivo_08_con_posiciones_del_layout(self, http):
        r = http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_08"})
        assert r.status_code == 200, r.text
        lote = r.json()["lote"]
        assert lote["registros"] == 2  # un movimiento + cifras de control
        txt = http.get(f"{BASE}/movimientos-imss/lotes/{lote['id']}/archivo").content
        assert txt.endswith(b"\r\n") and all(b < 128 for b in txt)
        alta, control = txt.decode("ascii").split("\r\n")[:2]
        assert len(alta) == len(control) == 168
        assert _campo(alta, 1, 10) == RP[:10] and _campo(alta, 11, 11) == RP[10]
        assert _campo(alta, 12, 21) == "1234567890" and _campo(alta, 22, 22) == "1"
        assert _campo(alta, 23, 49).rstrip() == "PENA"
        assert _campo(alta, 50, 76).rstrip() == "ALVAREZ"
        assert _campo(alta, 77, 103).rstrip() == "JOSE"
        assert _campo(alta, 104, 109) == "042000"
        assert _campo(alta, 116, 118) == "100"  # permanente, salario fijo, jornada normal
        assert _campo(alta, 119, 126) == "02032026"
        assert _campo(alta, 127, 129) == "000"
        assert _campo(alta, 132, 133) == "08" and _campo(alta, 134, 138) == GUIA
        assert _campo(alta, 139, 148).rstrip() == "E1"
        assert _campo(alta, 150, 167) == "PEPJ800101HVZRRN09" and alta[167] == "9"
        assert _campo(control, 1, 13) == "*" * 13 and _campo(control, 57, 62) == "000001"
        assert _campo(control, 134, 138) == GUIA and control[167] == "9"
        assert r.json()["transliterados"]
        assert _movs(http)[0]["estado"] == "generado"

    def test_cambio_de_sbc_genera_07_y_baja_genera_02(self, http):
        http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_08"})
        (alta,) = _movs(http)
        assert http.post(f"{BASE}/movimientos-imss/marcar", json={
            "ids": [alta["id"]], "estado": "enviado"}).status_code == 200
        r = http.post(f"{BASE}/movimientos-imss/marcar", json={
            "ids": [alta["id"]], "estado": "acuse", "acuse": "LOTE-123"})
        assert r.json()["movimientos"][0]["estado"] == "acuse"

        r = http.post(f"{BASE}/empleados/E1/sbc", json={
            "fecha": "2026-06-01", "sbc": "455.50", "motivo": "aumento"})
        assert r.status_code == 200, r.text
        assert r.json()["movimiento"]["tipo"] == "07"
        r = http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_07"})
        mod = http.get(f"{BASE}/movimientos-imss/lotes/{r.json()['lote']['id']}/archivo") \
            .content.decode("ascii").split("\r\n")[0]
        assert len(mod) == 168
        assert _campo(mod, 104, 109) == "045550" and _campo(mod, 116, 116) == " "
        assert _campo(mod, 119, 126) == "01062026" and _campo(mod, 127, 131) == " " * 5
        assert _campo(mod, 132, 133) == "07" and _campo(mod, 150, 167) == "PEPJ800101HVZRRN09"

        r = http.put("/api/v1/cartera/clientes/imss/empleados/E1",
                     json=_emp(fecha_baja="2026-07-15", causa_baja="2",
                               salario_diario_integrado="455.50"))
        assert r.status_code == 200 and "movimiento" in r.json()["mensaje"]
        r = http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_02"})
        assert r.status_code == 200, r.text
        baja = http.get(f"{BASE}/movimientos-imss/lotes/{r.json()['lote']['id']}/archivo") \
            .content.decode("ascii").split("\r\n")[0]
        assert len(baja) == 168
        assert _campo(baja, 104, 118) == "0" * 15
        assert _campo(baja, 119, 126) == "15072026" and _campo(baja, 132, 133) == "02"
        assert _campo(baja, 149, 149) == "2" and _campo(baja, 150, 167) == " " * 18
        historial = http.get(f"{BASE}/empleados/E1/historial-sbc").json()["historial"]
        assert [h["sbc"] for h in historial] == ["420.00", "455.50"]

    def test_baja_sin_causa_no_se_exporta_y_lo_dice(self, http):
        http.put("/api/v1/cartera/clientes/imss/empleados/E1", json=_emp(fecha_baja="2026-07-15"))
        r = http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_02"})
        assert r.status_code == 422 and "causa de baja" in r.json()["error"]
        assert [m["estado"] for m in _movs(http, tipo="02")] == ["pendiente"]

    def test_corregir_el_sbc_antes_de_enviar_el_alta_no_genera_07(self, http):
        http.put("/api/v1/cartera/clientes/imss/empleados/E1",
                 json=_emp(salario_diario_integrado="430.00"))
        (m,) = _movs(http)
        assert (m["tipo"], m["sbc"]) == ("08", "430.00")

    def test_sin_nss_queda_fuera_con_su_razon(self, api):
        c = api("uid-imss-sin-nss")
        _sembrar(c, [_emp(), _emp("E2", nss="")])
        r = c.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_08"})
        assert r.status_code == 200
        assert r.json()["lote"]["registros"] == 2
        (fuera,) = r.json()["no_exportables"]
        assert fuera["empleado_no"] == "E2" and "NSS" in fuera["motivo"]

    def test_asimilado_no_genera_movimientos(self, api):
        c = api("uid-imss-asim")
        _sembrar(c, [_emp("A1", tipo_regimen="09")])
        assert _movs(c) == []

    def test_reingreso_genera_08(self, http):
        http.put("/api/v1/cartera/clientes/imss/empleados/E1",
                 json=_emp(fecha_baja="2026-04-30", causa_baja="1"))
        http.put("/api/v1/cartera/clientes/imss/empleados/E1",
                 json=_emp(fecha_alta="2026-06-01"))
        tipos = sorted((m["tipo"], m["fecha"]) for m in _movs(http))
        assert ("08", "2026-06-01") in tipos and ("02", "2026-04-30") in tipos


class TestSUA:
    def test_trabajadores_y_movimientos(self, http):
        r = http.post(f"{BASE}/movimientos-imss/archivo",
                      json={"destino": "sua_trabajadores", "al": "2026-05-01"})
        assert r.status_code == 200, r.text
        linea = http.get(f"{BASE}/movimientos-imss/lotes/{r.json()['lote']['id']}/archivo") \
            .content.decode("ascii").split("\r\n")[0]
        assert len(linea) == 164
        assert _campo(linea, 1, 11) == RP and _campo(linea, 12, 22) == "12345678901"
        assert _campo(linea, 23, 35) == "PEPJ800101AB1"
        assert _campo(linea, 54, 103).rstrip() == "PENA$ALVAREZ$JOSE"
        assert _campo(linea, 106, 113) == "02032026" and _campo(linea, 114, 120) == "0042000"
        r = http.post(f"{BASE}/movimientos-imss/archivo", json={
            "destino": "sua_movimientos", "desde": "2026-03-01", "hasta": "2026-03-31"})
        mov = http.get(f"{BASE}/movimientos-imss/lotes/{r.json()['lote']['id']}/archivo") \
            .content.decode("ascii").split("\r\n")[0]
        assert len(mov) == 49 and _campo(mov, 23, 24) == "08"
        assert _campo(mov, 25, 32) == "02032026" and _campo(mov, 43, 49) == "0042000"


class TestMultiTenant:
    def test_otro_despacho_no_ve_ni_genera(self, http, api):
        otro = api("uid-otro-imss")
        assert otro.get(f"{BASE}/movimientos-imss").status_code == 404
        assert otro.post(f"{BASE}/movimientos-imss/archivo",
                         json={"destino": "idse_08"}).status_code == 404
        lote = http.post(f"{BASE}/movimientos-imss/archivo", json={"destino": "idse_08"}) \
            .json()["lote"]
        assert otro.get(f"{BASE}/movimientos-imss/lotes/{lote['id']}/archivo").status_code == 404
