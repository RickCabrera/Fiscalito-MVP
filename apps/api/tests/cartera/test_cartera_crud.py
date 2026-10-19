"""
El CRUD de la cartera con el backend como único dueño, sobre SQL. (R-07 → P0-01)

QUÉ CAMBIÓ RESPECTO DE R-07
---------------------------
Estos casos corrían contra `CarteraEnMemoria` (un diccionario) en CI y contra el
emulador de Firestore en local (`pytest -m emulador`). Con P0-01 la cartera vive en
SQL, así que corren contra **la base de verdad** (SQLite en memoria, el mismo ORM que
Postgres en producción) y en CI, sin marcador ni emulador. Los criterios que sólo el
emulador medía —"sobrevive reinicio", borrado en cascada, merge, topes, que la lectura
no trunque— se miden aquí contra SQL, y el de reinicio contra un archivo en disco con
un motor nuevo, como un proceso recién arrancado.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import almacen_cartera
from app.modelos.nucleo import Cliente, Empleado
from app.schemas.datos_fiscales_cliente import ENTIDADES_C_ESTADO

UID_A = "uid-despacho-a"
UID_B = "uid-despacho-b"

CLIENTE = {
    "id": "mio",
    "nombre": "Cliente Propio",
    "giro": "Servicios",
    "origen": "propio",
    "prima_riesgo": "0.0054355",
    "clase_riesgo": None,
    "clave_periodicidad": "04",
    "zona": "general",
    "periodo_sugerido": {"inicio": "2026-08-16", "fin": "2026-08-31", "fecha_pago": "2026-08-31"},
}

EMPLEADO = {
    "empleado_no": "E-01",
    "nombre": "PERSONA UNA",
    "puesto": "Cajera",
    "salario_diario": "520.00",
    "salario_diario_integrado": "548.50",
    "zona": "general",
    "fecha_alta": None,
    "tipo_contrato": "indeterminado",
    "prestaciones": {"dias_aguinaldo": 15, "dias_vacaciones": 0, "prima_vacacional": "0.25"},
    "nss": "",
    "employee_no": "7",
    "enrolamiento": "enrolado",
}

CLIENTES = "/api/v1/cartera/clientes"


@pytest.fixture
def a(api) -> TestClient:
    return api(UID_A)


@pytest.fixture
def b(api) -> TestClient:
    return api(UID_B)


def _alta(http: TestClient, cliente: dict | None = None) -> None:
    datos = cliente or CLIENTE
    r = http.put(f"{CLIENTES}/{datos['id']}", json=datos)
    assert r.status_code == 200, r.text


def _empleado_directo(sesionador, despacho: str, clave: str, datos: dict) -> None:
    """Escribe un empleado saltándose la validación de la ruta, como un documento legado."""
    db = sesionador()
    cliente = almacen_cartera.buscar_cliente(db, despacho, clave)
    db.add(Empleado(cliente_id=cliente.id, empleado_no=datos["empleado_no"], datos=datos))
    db.commit()
    db.close()


# ─────────────────────────────────────────────────────────────
# Autenticación: el despacho sale del token, no del request
# ─────────────────────────────────────────────────────────────

class TestAutenticacion:
    def test_sin_encabezado_es_401(self, api):
        r = api("x").get(CLIENTES, headers={"Authorization": ""})
        assert r.status_code == 401
        assert "Authorization" in r.json()["error"]

    @pytest.mark.parametrize("valor", ["Bearer", "Bearer   ", "Basic abc", "token-suelto"])
    def test_un_encabezado_mal_formado_es_401(self, api, valor: str):
        r = api("x").get(CLIENTES, headers={"Authorization": valor})
        assert r.status_code == 401

    def test_el_uid_NO_se_acepta_por_query_param(self, a, b):
        _alta(b)
        r = a.get(f"{CLIENTES}?uid={UID_B}")
        assert r.status_code == 200
        assert r.json()["clientes"] == [], "el query param movió de quién es la cartera"


# ─────────────────────────────────────────────────────────────
# Multi-tenant: el despacho B no ve ni toca lo del A
# ─────────────────────────────────────────────────────────────

class TestAislamiento:
    def test_dos_despachos_ven_carteras_distintas(self, a, b):
        _alta(a)
        assert [c["id"] for c in a.get(CLIENTES).json()["clientes"]] == ["mio"]
        assert b.get(CLIENTES).json()["clientes"] == []

    def test_B_no_puede_leer_los_empleados_de_A(self, a, b):
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        r = b.get(f"{CLIENTES}/mio/empleados")
        assert r.status_code == 404

    def test_B_no_puede_borrar_el_cliente_de_A(self, a, b):
        _alta(a)
        assert b.delete(f"{CLIENTES}/mio").status_code == 404
        assert [c["id"] for c in a.get(CLIENTES).json()["clientes"]] == ["mio"]

    def test_B_no_puede_colgar_empleados_del_cliente_de_A(self, a, b):
        _alta(a)
        r = b.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        assert r.status_code == 404
        assert a.get(f"{CLIENTES}/mio/empleados").json()["empleados"] == []

    def test_B_no_puede_borrar_empleados_de_A(self, a, b):
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        assert b.delete(f"{CLIENTES}/mio/empleados/E-01").status_code == 404
        assert a.get(f"{CLIENTES}/mio/empleados").json()["total"] == 1

    def test_la_misma_clave_en_dos_despachos_son_dos_clientes(self, a, b):
        _alta(a)
        _alta(b, {**CLIENTE, "nombre": "El de B"})
        a.put(f"{CLIENTES}/mio", json={**CLIENTE, "nombre": "Editado por A"})
        assert b.get(CLIENTES).json()["clientes"][0]["nombre"] == "El de B"
        assert a.get(CLIENTES).json()["clientes"][0]["nombre"] == "Editado por A"


# ─────────────────────────────────────────────────────────────
# El CRUD
# ─────────────────────────────────────────────────────────────

class TestCRUD:
    def test_alta_edicion_y_baja_de_cliente(self, a):
        _alta(a)
        a.put(f"{CLIENTES}/mio", json={**CLIENTE, "nombre": "Cliente Renombrado"})
        lista = a.get(CLIENTES).json()
        assert lista["clientes"][0]["nombre"] == "Cliente Renombrado"
        assert lista["total"] == 1

        assert a.delete(f"{CLIENTES}/mio").status_code == 200
        assert a.get(CLIENTES).json()["total"] == 0

    def test_borrar_un_cliente_que_no_existe_es_404(self, a):
        assert a.delete(f"{CLIENTES}/fantasma").status_code == 404

    def test_el_id_de_la_url_y_el_del_cuerpo_tienen_que_coincidir(self, a):
        r = a.put(f"{CLIENTES}/otro", json=CLIENTE)
        assert r.status_code == 422
        assert "no coincide" in r.json()["error"]

    def test_el_id_NO_se_guarda_dentro_del_documento(self, a, db_sesion):
        _alta(a)
        cliente = almacen_cartera.buscar_cliente(db_sesion, UID_A, "mio")
        assert "id" not in cliente.datos
        assert cliente.nombre == "Cliente Propio"

    def test_un_empleado_no_puede_colgar_de_un_cliente_que_no_existe(self, a):
        r = a.put(f"{CLIENTES}/fantasma/empleados/E-01", json=EMPLEADO)
        assert r.status_code == 404

    def test_alta_edicion_y_baja_de_empleado(self, a):
        _alta(a)
        assert a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO).status_code == 200
        a.put(f"{CLIENTES}/mio/empleados/E-01", json={**EMPLEADO, "puesto": "Gerente"})
        cuerpo = a.get(f"{CLIENTES}/mio/empleados").json()
        assert cuerpo["total"] == 1
        assert cuerpo["empleados"][0]["puesto"] == "Gerente"

        assert a.delete(f"{CLIENTES}/mio/empleados/E-01").status_code == 200
        assert a.get(f"{CLIENTES}/mio/empleados").json()["total"] == 0

    def test_el_numero_de_la_url_y_el_del_cuerpo_tienen_que_coincidir(self, a):
        _alta(a)
        r = a.put(f"{CLIENTES}/mio/empleados/E-99", json=EMPLEADO)
        assert r.status_code == 422

    def test_borrar_un_cliente_se_lleva_a_sus_empleados_y_dispositivos(self, a, db_sesion):
        """Sin cascada, los empleados reaparecerían —con su salario y su NSS— al recrear."""
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        a.post(f"{CLIENTES}/mio/dispositivos", json={"nombre": "Entrada"})

        a.delete(f"{CLIENTES}/mio")
        _alta(a)

        assert a.get(f"{CLIENTES}/mio/empleados").json()["empleados"] == []
        assert a.get(f"{CLIENTES}/mio/dispositivos").json()["dispositivos"] == []
        assert db_sesion.query(Empleado).count() == 0

    def test_cuenta_los_no_vinculados_al_checador(self, a):
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        a.put(
            f"{CLIENTES}/mio/empleados/E-02",
            json={**EMPLEADO, "empleado_no": "E-02", "employee_no": None},
        )
        r = a.get(f"{CLIENTES}/mio/empleados").json()
        assert r["total"] == 2
        assert r["sin_vincular"] == 1

    def test_guardar_es_MERGE_y_no_reemplazo(self, a, sesionador):
        """Un campo que esta versión no conoce (p. ej. traído por la migración) sobrevive."""
        _alta(a)
        db = sesionador()
        cliente = almacen_cartera.buscar_cliente(db, UID_A, "mio")
        almacen_cartera.actualizar_cliente(cliente, {"campo_futuro": "x"})
        db.commit()
        db.close()

        a.put(f"{CLIENTES}/mio", json={**CLIENTE, "nombre": "Editado"})

        guardado = a.get(CLIENTES).json()["clientes"][0]
        assert guardado["nombre"] == "Editado"
        assert guardado["campo_futuro"] == "x", "el guardado borró un campo desconocido"

    def test_la_lista_va_ordenada_por_nombre(self, a):
        _alta(a, {**CLIENTE, "id": "z", "nombre": "Zapateria"})
        _alta(a, {**CLIENTE, "id": "b", "nombre": "Abarrotes"})
        assert [c["id"] for c in a.get(CLIENTES).json()["clientes"]] == ["b", "z"]


# ─────────────────────────────────────────────────────────────
# Sobrevive reinicio: otro motor, otro proceso, mismo archivo
# ─────────────────────────────────────────────────────────────

def test_sobrevive_a_reiniciar_la_api(tmp_path, monkeypatch):
    """
    EL CRITERIO LITERAL de P0-01. Se escribe por la API con un motor sobre un archivo,
    se **descarta ese motor** y se lee con uno nuevo, como un proceso recién arrancado.
    """
    from app.auth_firebase import token_del_encabezado, usuario_actual
    from app.db.base import Base
    from app.db.session import crear_motor, obtener_db
    from app.main import app

    url = f"sqlite:///{tmp_path / 'fiscalito.db'}"

    def montar() -> tuple:
        motor = crear_motor(url)
        Base.metadata.create_all(motor)
        hacer = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)

        def _db():
            s = hacer()
            try:
                yield s
                s.commit()
            finally:
                s.close()

        app.dependency_overrides[obtener_db] = _db
        def _uid(authorization: str | None = Header(default=None)) -> str:
            return token_del_encabezado(authorization)

        app.dependency_overrides[usuario_actual] = _uid
        return motor

    try:
        motor = montar()
        http = TestClient(app, headers={"Authorization": f"Bearer {UID_A}"})
        _alta(http)
        http.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        http.post(f"{CLIENTES}/mio/dispositivos", json={"nombre": "Entrada"})
        motor.dispose()

        montar()
        http = TestClient(app, headers={"Authorization": f"Bearer {UID_A}"})
        assert [c["id"] for c in http.get(CLIENTES).json()["clientes"]] == ["mio"]
        empleados = http.get(f"{CLIENTES}/mio/empleados").json()["empleados"]
        assert [e["salario_diario"] for e in empleados] == ["520.00"]
        assert http.get(f"{CLIENTES}/mio/dispositivos").json()["total"] == 1
    finally:
        app.dependency_overrides.pop(obtener_db, None)
        app.dependency_overrides.pop(usuario_actual, None)


def test_el_motor_por_default_es_un_archivo_y_no_memoria():
    """Si el default fuera `sqlite://` (memoria), "sobrevive reinicio" sería falso."""
    from app.config import settings

    assert settings.DATABASE_URL != "sqlite://"
    assert ":memory:" not in settings.DATABASE_URL
    create_engine(settings.DATABASE_URL).dispose()


# ─────────────────────────────────────────────────────────────
# Validación: lo que el contrato rechaza
# ─────────────────────────────────────────────────────────────

class TestValidacion:
    def test_una_prima_de_riesgo_fuera_del_Art_72_se_rechaza(self, a):
        """5.4355 en vez de 0.0054355 multiplica Riesgos de Trabajo por mil."""
        r = a.put(f"{CLIENTES}/mio", json={**CLIENTE, "prima_riesgo": "5.4355"})
        assert r.status_code == 422

    @pytest.mark.parametrize("nss", ["1234567890", "123456789034", "abcdefghijk"])
    def test_un_NSS_mal_formado_se_rechaza(self, a, nss: str):
        """MISMO VECTOR QUE `apps/store/src/services/nss.test.ts`."""
        _alta(a)
        r = a.put(f"{CLIENTES}/mio/empleados/E-01", json={**EMPLEADO, "nss": nss})
        assert r.status_code == 422

    @pytest.mark.parametrize("nss", ["", "12345678903", "12345678900"])
    def test_vacio_y_11_digitos_se_aceptan_incluido_el_verificador_que_no_casa(
        self, a, nss: str
    ):
        """`12345678900` tiene el verificador equivocado y se acepta (§D25)."""
        _alta(a)
        r = a.put(f"{CLIENTES}/mio/empleados/E-01", json={**EMPLEADO, "nss": nss})
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# C-01: RFC, código postal y entidad federativa del cliente
# ─────────────────────────────────────────────────────────────

XSD_CAT_CFDI = Path(__file__).resolve().parents[1] / "xsd" / "catCFDI.xsd"


class TestDatosFiscalesDelCliente:
    """MISMO VECTOR QUE `apps/store/src/components/cartera/datosFiscalesCliente.test.ts`."""

    def test_se_guardan_y_se_devuelven(self, a):
        datos = {
            **CLIENTE,
            "regimen": "612",
            "rfc": "abcd010101ab1",
            "codigo_postal": "91000",
            "clave_entidad": "VER",
        }
        assert a.put(f"{CLIENTES}/mio", json=datos).status_code == 200
        cliente = a.get(CLIENTES).json()["clientes"][0]
        assert cliente["rfc"] == "ABCD010101AB1"
        assert cliente["codigo_postal"] == "91000"
        assert cliente["clave_entidad"] == "VER"

    def test_el_rfc_se_copia_a_la_columna_indexada(self, a, db_sesion):
        a.put(f"{CLIENTES}/mio", json={**CLIENTE, "regimen": "612", "rfc": "ABCD010101AB1"})
        assert db_sesion.query(Cliente).one().rfc == "ABCD010101AB1"

    def test_un_cliente_sin_los_campos_nuevos_se_sigue_guardando(self, a):
        assert a.put(f"{CLIENTES}/mio", json=CLIENTE).status_code == 200

    @pytest.mark.parametrize(
        ("regimen", "rfc"),
        [
            ("612", "ABCD010101AB1"),
            ("601", "ABC010101AB1"),
            ("626", "ABC010101AB1"),
            ("626", "ABCD010101AB1"),
            ("", "ABC010101AB1"),
            ("612", "ÑAND010101AB1"),
        ],
    )
    def test_rfc_valido_para_su_regimen(self, a, regimen: str, rfc: str):
        r = a.put(f"{CLIENTES}/mio", json={**CLIENTE, "regimen": regimen, "rfc": rfc})
        assert r.status_code == 200

    @pytest.mark.parametrize(
        ("regimen", "rfc"),
        [
            ("612", "ABC010101AB1"),
            ("601", "ABCD010101AB1"),
            ("612", "ABCD01"),
            ("612", "ABCD0101X1AB1"),
            ("", "1234010101AB1"),
        ],
    )
    def test_rfc_mal_formado_o_de_otra_persona_se_rechaza(self, a, regimen: str, rfc: str):
        r = a.put(f"{CLIENTES}/mio", json={**CLIENTE, "regimen": regimen, "rfc": rfc})
        assert r.status_code == 422

    def test_rfc_y_regimen_que_no_casan_bloquean_TODO_guardado(self, a):
        r = a.put(
            f"{CLIENTES}/mio",
            json={**CLIENTE, "regimen": "612", "rfc": "ABC010101AB1", "giro": "Otro giro"},
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("cp", ["9100", "910000", "9100A"])
    def test_codigo_postal_de_5_digitos(self, a, cp: str):
        assert a.put(f"{CLIENTES}/mio", json={**CLIENTE, "codigo_postal": cp}).status_code == 422

    @pytest.mark.parametrize("clave", ["XXX", "ver", "TX"])
    def test_entidad_fuera_del_catalogo_se_rechaza(self, a, clave: str):
        r = a.put(f"{CLIENTES}/mio", json={**CLIENTE, "clave_entidad": clave})
        assert r.status_code == 422

    def test_el_catalogo_es_el_c_Estado_versionado_del_SAT(self):
        ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
        arbol = ET.parse(XSD_CAT_CFDI)
        tipo = arbol.getroot().find("xs:simpleType[@name='c_Estado']", ns)
        assert tipo is not None
        claves = {e.get("value") for e in tipo.iter(f"{{{ns['xs']}}}enumeration")}
        de_mexico = {c for c in claves if c is not None and len(c) == 3}
        assert de_mexico == set(ENTIDADES_C_ESTADO)
        assert len(ENTIDADES_C_ESTADO) == 33


# ─────────────────────────────────────────────────────────────
# CORS: el preflight que el navegador hace antes de un PUT
# ─────────────────────────────────────────────────────────────

def test_el_preflight_de_PUT_esta_permitido(a):
    """Sin PUT/DELETE en `allow_methods` el navegador falla en el preflight."""
    r = a.options(
        f"{CLIENTES}/mio",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "PUT"},
    )
    assert r.status_code == 200
    assert "PUT" in r.headers.get("access-control-allow-methods", "")


# ─────────────────────────────────────────────────────────────
# Documentos legados: no tumban la lista y se reportan con su razón (R-10)
# ─────────────────────────────────────────────────────────────

class TestDocumentosLegados:
    def test_un_empleado_ilegible_no_tumba_la_lista(self, a, sesionador):
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        _empleado_directo(
            sesionador, UID_A, "mio", {**EMPLEADO, "empleado_no": "E-99", "nss": "123456789"}
        )

        r = a.get(f"{CLIENTES}/mio/empleados")

        assert r.status_code == 200, "un documento legado tumbó la respuesta entera"
        assert [e["empleado_no"] for e in r.json()["empleados"]] == ["E-01"]
        assert r.json()["total"] == 1

    def test_y_los_ilegibles_se_REPORTAN_con_su_razon(self, a, sesionador):
        _alta(a)
        _empleado_directo(
            sesionador, UID_A, "mio", {**EMPLEADO, "empleado_no": "E-99", "nss": "123456789"}
        )

        cuerpo = a.get(f"{CLIENTES}/mio/empleados").json()
        assert cuerpo["ilegibles"] == ["E-99"]
        [detalle] = cuerpo["ilegibles_detalle"]
        assert detalle["empleado_no"] == "E-99"
        assert detalle["nombre"] == "PERSONA UNA"
        assert detalle["razon"].startswith("nss")

    def test_sin_ilegibles_las_listas_van_vacias(self, a):
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        cuerpo = a.get(f"{CLIENTES}/mio/empleados").json()
        assert cuerpo["ilegibles"] == []
        assert cuerpo["ilegibles_detalle"] == []


# ─────────────────────────────────────────────────────────────
# Topes: sólo en altas, nunca en ediciones, nunca truncando la lectura
# ─────────────────────────────────────────────────────────────

class TestTopes:
    def test_rechaza_al_pasarse_del_tope_de_clientes(self, a, monkeypatch):
        monkeypatch.setattr(almacen_cartera, "MAX_CLIENTES_POR_DESPACHO", 1)
        _alta(a)
        r = a.put(f"{CLIENTES}/dos", json={**CLIENTE, "id": "dos"})
        assert r.status_code == 409

    def test_editar_uno_existente_NO_rebota_por_el_tope(self, a, monkeypatch):
        """Si rebotara, llegar al tope dejaría la cartera de sólo lectura."""
        monkeypatch.setattr(almacen_cartera, "MAX_CLIENTES_POR_DESPACHO", 1)
        _alta(a)
        assert a.put(f"{CLIENTES}/mio", json={**CLIENTE, "nombre": "Editado"}).status_code == 200

    def test_el_tope_es_por_despacho(self, a, b, monkeypatch):
        monkeypatch.setattr(almacen_cartera, "MAX_CLIENTES_POR_DESPACHO", 1)
        _alta(a)
        _alta(b)

    def test_rechaza_al_pasarse_del_tope_de_empleados(self, a, monkeypatch):
        monkeypatch.setattr(almacen_cartera, "MAX_EMPLEADOS_POR_CLIENTE", 1)
        _alta(a)
        a.put(f"{CLIENTES}/mio/empleados/E-01", json=EMPLEADO)
        r = a.put(f"{CLIENTES}/mio/empleados/E-02", json={**EMPLEADO, "empleado_no": "E-02"})
        assert r.status_code == 409

    def test_la_LECTURA_no_trunca(self, a, sesionador, monkeypatch):
        """El cliente 501 no puede desaparecer de la lista sin aviso."""
        monkeypatch.setattr(almacen_cartera, "MAX_CLIENTES_POR_DESPACHO", 1)
        _alta(a)
        db = sesionador()
        almacen_cartera.crear_cliente(db, UID_A, "otro", {"nombre": "Otro"}, con_tope=False)
        db.commit()
        db.close()
        assert a.get(CLIENTES).json()["total"] == 2
