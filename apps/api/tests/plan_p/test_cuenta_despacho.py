"""P6-01: exportar, respaldar y borrar la cuenta del despacho; cifrado de datos bancarios."""

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select, text

from app.config import settings
from app.db.base import Base
from app.db.cifrado_columnas import cifrar_existentes
from app.despacho.alcance import TABLAS_GLOBALES_CONOCIDAS, tablas_del_despacho, tablas_globales
from app.despacho.respaldos import encolar_respaldos, leer_indice, respaldar
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.modelos.cfdi import Comprobante
from app.modelos.cuenta import BajaDespacho
from app.modelos.nucleo import Cliente, Despacho, Empleado, Usuario
from app.modelos.trabajos import Trabajo
from app.tenancy import asegurar_usuario
from app.trabajos import procesar_siguiente
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, cfdi, uuid_n

CLABE = "002010077777777771"  # ejemplo público del algoritmo de Banxico (ver dispersion/clabe.py)
LLAVE = Fernet.generate_key().decode()


@pytest.fixture
def almacen_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    return tmp_path / "almacen"


@pytest.fixture
def llave(monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", LLAVE)


@pytest.fixture
def dos_despachos(sesionador, api, almacen_dir, llave):
    """A y B, cada uno con un cliente, un empleado con CLABE y un CFDI en la bóveda."""
    db = sesionador()
    for uid, clave in (("uid-a", "taller"), ("uid-b", "otro")):
        asegurar_usuario(db, uid)
        c = Cliente(despacho_id=uid, clave=clave, nombre=clave, rfc=RFC_CLIENTE)
        db.add(c)
        db.flush()
        db.add(Empleado(cliente_id=c.id, empleado_no="1",
                        datos={"nombre": "Trabajador Sintético", "clabe": CLABE}))
    db.commit()
    db.close()
    for uid, clave, n in (("uid-a", "taller", 1), ("uid-b", "otro", 2)):
        xml = cfdi(uuid_n(n), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                   fecha="2026-05-01T09:00:00")
        r = api(uid).post(f"/api/v1/boveda/clientes/{clave}/cfdi",
                          files=[("archivos", ("a.xml", xml, "application/xml"))])
        assert r.status_code == 200 and r.json()["importados"] == 1, r.text
    return sesionador


def _cuenta(sesionador, modelo, *condiciones) -> int:
    with sesionador() as db:
        return db.scalar(select(func.count()).select_from(modelo).where(*condiciones)) or 0


# ── alcance ──


def test_toda_tabla_con_dueno_entra_al_alcance():
    con_dueno = {t.name for t, _ in tablas_del_despacho("x")}
    for tabla in Base.metadata.sorted_tables:
        if "despacho_id" in tabla.c or "cliente_id" in tabla.c:
            assert tabla.name in con_dueno or tabla.name == "bajas_despacho", tabla.name
    # Lo que queda fuera es lo global conocido y la lápida: una tabla nueva sin camino
    # al despacho tiene que decidirse aquí, no quedar fuera en silencio.
    assert set(tablas_globales()) == TABLAS_GLOBALES_CONOCIDAS | {"bajas_despacho"}


# ── cifrado ──


def test_clabe_del_empleado_se_guarda_cifrada_y_se_lee_en_claro(dos_despachos):
    with dos_despachos() as db:
        crudo = db.execute(text("SELECT datos FROM empleados LIMIT 1")).scalar()
        assert CLABE not in str(crudo) and "enc:" in str(crudo)
        assert db.scalars(select(Empleado)).first().datos["clabe"] == CLABE


def test_la_api_de_cartera_guarda_cifrado_y_devuelve_en_claro(api, sesionador, llave):
    from tests.nomina.cartera_sembrada import sembrar_cliente
    from tests.plan_p.nomina_cerrada import clabe, emp

    cuenta = clabe("012", "1234567890")
    http = api("uid-c")
    sembrar_cliente(http, "fab", [emp("E9", clabe=cuenta, numero_cuenta="1234567890")])
    r = http.get("/api/v1/cartera/clientes/fab/empleados")
    assert r.status_code == 200 and cuenta in r.text and "1234567890" in r.text
    with sesionador() as db:
        crudo = str(db.execute(text("SELECT datos FROM empleados")).scalar())
    assert cuenta not in crudo and "1234567890" not in crudo


def test_migracion_cifra_lo_que_estaba_en_claro(db_sesion, llave):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="x", nombre="x")
    db_sesion.add(c)
    db_sesion.flush()
    db_sesion.execute(text(
        "INSERT INTO empleados (cliente_id, empleado_no, datos, creado_en, actualizado_en) "
        "VALUES (:c, '9', :d, '2026-01-01', '2026-01-01')"),
        {"c": c.id, "d": json.dumps({"clabe": CLABE, "nombre": "N"})})
    assert cifrar_existentes(db_sesion.connection())["empleados"] == 1
    assert cifrar_existentes(db_sesion.connection())["empleados"] == 0  # idempotente
    crudo = db_sesion.execute(text("SELECT datos FROM empleados WHERE empleado_no='9'")).scalar()
    assert CLABE not in crudo
    db_sesion.expire_all()
    assert db_sesion.scalars(select(Empleado)).first().datos["clabe"] == CLABE


def test_sin_llave_en_desarrollo_queda_en_claro_y_la_migracion_no_toca(db_sesion, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", "")
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="x", nombre="x")
    db_sesion.add(c)
    db_sesion.flush()
    db_sesion.add(Empleado(cliente_id=c.id, empleado_no="1", datos={"clabe": CLABE}))
    db_sesion.flush()
    assert CLABE in db_sesion.execute(text("SELECT datos FROM empleados")).scalar()
    assert cifrar_existentes(db_sesion.connection()) == {"empleados": 0, "cuentas_bancarias": 0}


# ── exportar ──


def test_exportar_en_segundo_plano_y_descargar_por_enlace_firmado(api, dos_despachos):
    a = api("uid-a")
    r = a.post("/api/v1/despacho/exportar")
    assert r.status_code == 200, r.text
    trabajo = r.json()["trabajo"]
    assert trabajo["estado"] == "pendiente" and trabajo["url"] is None
    assert procesar_siguiente(dos_despachos).estado == "hecho"

    estado = a.get(f"/api/v1/despacho/exportar/{trabajo['id']}").json()["trabajo"]
    assert estado["estado"] == "hecho" and estado["url"]
    partes = urlsplit(estado["url"])
    publico = api("uid-nadie")
    publico.headers.pop("Authorization")
    z = publico.get(f"{partes.path}?{partes.query}")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        nombres = zf.namelist()
        manifiesto = json.loads(zf.read("manifiesto.json"))
        clientes = json.loads(zf.read("tablas/clientes.json"))
        empleados = json.loads(zf.read("tablas/empleados.json"))
        xmls = [n for n in nombres if n.startswith("archivos/") and n.endswith(".xml")]
    assert [c["clave"] for c in clientes] == ["taller"]  # nada del despacho B
    assert empleados[0]["datos"]["clabe"] == CLABE  # el dueño recibe su dato en claro
    assert len(xmls) == 1 and manifiesto["archivos"] == 1
    assert manifiesto["tablas"]["comprobantes"] == 1

    # Firma alterada o vencida: 404 sin distinguir.
    assert publico.get(f"{partes.path}?{partes.query[:-1]}0").status_code == 404
    vencida = partes.query.replace("vence=", "vence=1")
    assert publico.get(f"{partes.path}?{vencida}").status_code == 404


def test_exportar_es_solo_del_dueno_y_de_su_despacho(api, dos_despachos, sesionador):
    with sesionador() as db:
        db.add(Usuario(uid="uid-aux", despacho_id="uid-a", rol="auxiliar"))
        db.commit()
    assert api("uid-aux").post("/api/v1/despacho/exportar").status_code == 403
    t = api("uid-a").post("/api/v1/despacho/exportar").json()["trabajo"]
    assert api("uid-b").get(f"/api/v1/despacho/exportar/{t['id']}").status_code == 404


# ── borrar ──


def test_borrar_exige_la_frase_y_el_rol(api, dos_despachos, sesionador):
    with sesionador() as db:
        db.add(Usuario(uid="uid-cont", despacho_id="uid-a", rol="contador"))
        db.commit()
    frase = {"confirmacion": "BORRAR MI DESPACHO"}
    assert api("uid-cont").post("/api/v1/despacho/borrar", json=frase).status_code == 403
    r = api("uid-a").post("/api/v1/despacho/borrar", json={"confirmacion": "borrar"})
    assert r.status_code == 422
    assert _cuenta(dos_despachos, Cliente, Cliente.despacho_id == "uid-a") == 1


def test_borrar_a_no_toca_b(api, dos_despachos, almacen_dir):
    antes_b = {
        "clientes": _cuenta(dos_despachos, Cliente, Cliente.despacho_id == "uid-b"),
        "xml": len(list((almacen_dir).rglob("*.xml"))),
    }
    assert antes_b == {"clientes": 1, "xml": 2}
    with dos_despachos() as db:
        respaldar(db, "uid-a")
        respaldar(db, "uid-b")
    r = api("uid-a").post("/api/v1/despacho/borrar",
                          json={"confirmacion": "BORRAR MI DESPACHO"})
    assert r.status_code == 200, r.text
    borrado = r.json()["borrado"]
    assert borrado["clientes"] == 1 and borrado["empleados"] == 1
    # El XML, el ZIP del respaldo y su índice.
    assert borrado["comprobantes"] == 1 and borrado["archivos"] == 3
    assert not (almacen_dir / "respaldos/uid-a").exists() or not any(
        (almacen_dir / "respaldos/uid-a").iterdir())
    assert any((almacen_dir / "respaldos/uid-b").glob("*.zip"))

    s = dos_despachos
    assert _cuenta(s, Despacho, Despacho.id == "uid-a") == 0
    assert _cuenta(s, Usuario, Usuario.despacho_id == "uid-a") == 0
    assert _cuenta(s, Cliente, Cliente.despacho_id == "uid-a") == 0
    assert _cuenta(s, Empleado) == 1 and _cuenta(s, Comprobante) == 1
    # B intacto: su cliente, su empleado, su XML (que sigue descargable).
    assert _cuenta(s, Cliente, Cliente.despacho_id == "uid-b") == 1
    assert len(list(almacen_dir.rglob("*.xml"))) == 1
    b = api("uid-b")
    assert b.get("/api/v1/boveda/clientes/otro/cfdi").json()["total"] == 1
    with s() as db:
        # Nada colgando del despacho borrado en ninguna tabla.
        for tabla, condicion in tablas_del_despacho("uid-a"):
            assert db.scalar(select(func.count()).select_from(tabla).where(condicion)) == 0
        baja = db.scalars(select(BajaDespacho)).one()
        assert baja.despacho_id == "uid-a" and baja.uid == "uid-a"


def test_tras_borrar_el_mismo_usuario_entra_a_un_despacho_vacio(api, dos_despachos):
    a = api("uid-a")
    a.post("/api/v1/despacho/borrar", json={"confirmacion": "BORRAR MI DESPACHO"})
    r = a.get("/api/v1/cartera/clientes")
    assert r.status_code == 200 and r.json()["total"] == 0


# ── respaldos ──


def test_respaldo_diario_con_indice_y_retencion(dos_despachos, monkeypatch):
    monkeypatch.setenv("FISCALITO_RESPALDOS_RETENCION_DIAS", "2")
    almacen = AlmacenamientoMemoria()
    t0 = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    with dos_despachos() as db:
        for dia in range(4):
            respaldar(db, "uid-a", momento=t0 + timedelta(days=dia), almacen=almacen)
        respaldar(db, "uid-a", momento=t0 + timedelta(days=3), almacen=almacen)  # idempotente
    indice = leer_indice(almacen, "uid-a")
    assert [e["ruta"] for e in indice] == [
        "respaldos/uid-a/2026-10-02.zip", "respaldos/uid-a/2026-10-03.zip",
        "respaldos/uid-a/2026-10-04.zip"]
    assert not almacen.existe("respaldos/uid-a/2026-10-01.zip")
    with zipfile.ZipFile(io.BytesIO(almacen.leer(indice[-1]["ruta"]))) as zf:
        assert json.loads(zf.read("manifiesto.json"))["despacho_id"] == "uid-a"
    assert not any(r.startswith("respaldos/uid-b") for r in almacen.archivos)


def test_el_programador_encola_un_respaldo_por_despacho(dos_despachos, monkeypatch):
    ranura = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    with dos_despachos() as db:
        assert len(encolar_respaldos(db, ranura)) == 2
        assert len(encolar_respaldos(db, ranura)) == 2  # misma clave: no duplica
        db.commit()
        assert db.scalar(select(func.count()).select_from(Trabajo).where(
            Trabajo.tipo == "despacho.respaldar")) == 2
    monkeypatch.setenv("FISCALITO_RESPALDOS_ACTIVOS", "0")
    with dos_despachos() as db:
        assert encolar_respaldos(db, ranura + timedelta(days=1)) == []


def test_el_trabajo_de_respaldo_escribe_al_almacen(dos_despachos, almacen_dir):
    ranura = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    with dos_despachos() as db:
        encolar_respaldos(db, ranura)
        db.commit()
    for _ in range(2):
        assert procesar_siguiente(dos_despachos, ahora=ranura).estado == "hecho"
    assert (almacen_dir / "respaldos/uid-a/2026-10-01.zip").is_file()
    assert (almacen_dir / "respaldos/uid-b/2026-10-01.zip").is_file()
