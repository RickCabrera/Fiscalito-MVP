"""
Dispositivos del cliente por la API, sobre SQL. (R-09 → P0-01)

R-04 los dejó en Firestore escritos por el navegador. Ahora el backend es su dueño, con
las mismas reglas que `validarDispositivo` aplica en el formulario.
"""

from __future__ import annotations

import pytest

CLIENTE = {
    "id": "taller",
    "nombre": "Taller",
    "giro": "Servicios",
    "origen": "propio",
    "prima_riesgo": "0.0054355",
    "clave_periodicidad": "04",
    "zona": "general",
}
BASE = "/api/v1/cartera/clientes/taller/dispositivos"
APARATO = {
    "nombre": "Entrada planta",
    "ip": "192.168.1.64",
    "puerto": 80,
    "marca": "Hikvision",
    "modelo": "MinMoe",
    "serial": "SER-001",
    "employee_nos": ["7", "8"],
    "notas": "",
}


@pytest.fixture
def a(api):
    http = api("uid-a")
    assert http.put("/api/v1/cartera/clientes/taller", json=CLIENTE).status_code == 200
    return http


def test_alta_edicion_y_baja(a):
    r = a.post(BASE, json=APARATO)
    assert r.status_code == 201
    ident = r.json()["id"]
    assert ident

    lista = a.get(BASE).json()
    assert lista["total"] == 1
    assert lista["dispositivos"][0] == {**APARATO, "id": ident}

    r = a.put(f"{BASE}/{ident}", json={**APARATO, "nombre": "Recepción", "employee_nos": ["7"]})
    assert r.status_code == 200
    guardado = a.get(BASE).json()["dispositivos"][0]
    assert guardado["nombre"] == "Recepción"
    assert guardado["employee_nos"] == ["7"]

    assert a.delete(f"{BASE}/{ident}").status_code == 200
    assert a.get(BASE).json()["total"] == 0


def test_el_id_lo_genera_el_backend_y_no_se_guarda_en_el_documento(a, db_sesion):
    from app.modelos.nucleo import Dispositivo

    ident = a.post(BASE, json=APARATO).json()["id"]
    fila = db_sesion.query(Dispositivo).one()
    assert fila.clave == ident
    assert "id" not in fila.datos


def test_dos_altas_con_el_mismo_nombre_son_dos_dispositivos(a):
    a.post(BASE, json={**APARATO, "serial": ""})
    a.post(BASE, json={**APARATO, "serial": ""})
    assert a.get(BASE).json()["total"] == 2


def test_editar_uno_que_no_existe_es_404(a):
    assert a.put(f"{BASE}/fantasma", json=APARATO).status_code == 404


def test_de_un_cliente_que_no_existe_es_404(a):
    r = a.get("/api/v1/cartera/clientes/fantasma/dispositivos")
    assert r.status_code == 404


@pytest.mark.parametrize(
    "cambio",
    [
        {"nombre": "   "},
        {"ip": "999.1.1.1"},
        {"ip": "192.168.1"},
        {"puerto": 0},
        {"puerto": 70000},
    ],
)
def test_lo_que_el_formulario_rechaza_el_backend_tambien(a, cambio):
    assert a.post(BASE, json={**APARATO, **cambio}).status_code == 422


def test_la_ip_es_opcional(a):
    assert a.post(BASE, json={**APARATO, "ip": ""}).status_code == 201


def test_un_serial_repetido_en_el_mismo_cliente_se_rechaza(a):
    a.post(BASE, json=APARATO)
    r = a.post(BASE, json={**APARATO, "nombre": "Otro"})
    assert r.status_code == 422
    assert "serial" in r.json()["error"]


def test_editar_conservando_su_propio_serial_no_choca_consigo_mismo(a):
    ident = a.post(BASE, json=APARATO).json()["id"]
    assert a.put(f"{BASE}/{ident}", json={**APARATO, "nombre": "Nuevo"}).status_code == 200


def test_las_llaves_del_checador_se_limpian(a):
    """Un `""` sería un enrolado fantasma permanente; un repetido, una fila doble."""
    a.post(BASE, json={**APARATO, "employee_nos": ["7", " ", "7", " 8 "]})
    assert a.get(BASE).json()["dispositivos"][0]["employee_nos"] == ["7", "8"]


class TestAislamiento:
    def test_B_no_ve_los_dispositivos_de_A(self, a, api):
        a.post(BASE, json=APARATO)
        assert api("uid-b").get(BASE).status_code == 404

    def test_B_no_puede_editar_ni_borrar_los_de_A(self, a, api):
        ident = a.post(BASE, json=APARATO).json()["id"]
        b = api("uid-b")
        assert b.put(f"{BASE}/{ident}", json={**APARATO, "nombre": "Hackeado"}).status_code == 404
        assert b.delete(f"{BASE}/{ident}").status_code == 404
        assert a.get(BASE).json()["dispositivos"][0]["nombre"] == "Entrada planta"

    def test_B_con_un_cliente_de_la_misma_clave_no_alcanza_los_de_A(self, a, api):
        ident = a.post(BASE, json=APARATO).json()["id"]
        b = api("uid-b")
        b.put("/api/v1/cartera/clientes/taller", json=CLIENTE)
        assert b.get(BASE).json()["total"] == 0
        assert b.put(f"{BASE}/{ident}", json=APARATO).status_code == 404
        assert b.delete(f"{BASE}/{ident}").status_code == 200  # idempotente, no toca a A
        assert a.get(BASE).json()["total"] == 1
