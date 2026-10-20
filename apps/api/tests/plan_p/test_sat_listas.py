"""
P1-04: listas 69-B (EFOS/EDOS) y 69.

"Listo cuando": un proveedor que está en la lista se marca en rojo y genera alerta.
CSV sintéticos con RFC inventados; ningún test descarga nada.
"""

import io
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.boveda_cfdi import servicio
from app.integraciones import registro
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.comun import ErrorServicioExterno
from app.integraciones.sat_listas import (
    CSV_69B_FALSO,
    SatListasFalso,
    SatListasPortal,
    listas_activas,
    url_de,
)
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import AlertaRiesgo, CargaListaSat, ContribuyenteListaSat
from app.sat_verificacion import listas
from app.tenancy import asegurar_usuario
from app.trabajos.cola import encolar, procesar_siguiente
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_COMPRADOR, cfdi, uuid_n

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "sat_listas"
CSV_RARO = (FIX / "69b_sintetico_latin1.csv").read_bytes()
EFOS = "EFO010101AA1"
PRESUNTO = "PRE020202BB2"
DESVIRTUADO = "DES030303CC3"


# ── parseo ──


def test_parsea_latin1_con_titulos_punto_y_coma_y_encabezados_raros():
    renglones = {r.rfc: r for r in listas.parsear_csv(CSV_RARO, "69b")}
    assert set(renglones) == {EFOS, PRESUNTO, DESVIRTUADO, "SEN040404DD4"}  # sin basura
    e = renglones[EFOS]
    assert e.nombre == "EMPRESA FACTURADORA SINTÉTICA, S.A. DE C.V."
    assert e.situacion == "definitivo" and e.situacion_texto == "Definitivo"
    # La publicación más reciente (definitivos), no la de presuntos.
    assert e.fecha_publicacion_sat == date(2026, 5, 10)
    assert e.fecha_publicacion_dof == date(2026, 5, 15)
    p = renglones[PRESUNTO]  # minúsculas y espacio al final en el CSV
    assert p.situacion == "presunto" and p.nombre == "Presunta Señora Ñandú"
    assert renglones["SEN040404DD4"].situacion == "sentencia_favorable"
    assert renglones[DESVIRTUADO].situacion == "desvirtuado"


def test_parsea_el_csv_del_falso_utf8_y_coma():
    con_bom = b"\xef\xbb\xbf" + CSV_69B_FALSO.encode("utf-8")
    for datos in (CSV_69B_FALSO.encode("latin-1"), con_bom):
        renglones = {r.rfc: r for r in listas.parsear_csv(datos, "69b")}
        assert renglones[EFOS].nombre == "EMPRESA FACTURADORA SINTETICA, S.A. DE C.V."
        assert renglones[PRESUNTO].fecha_publicacion_dof == date(2026, 8, 5)


def test_csv_sin_columna_rfc_es_error_claro():
    with pytest.raises(ValueError, match="no trae una columna RFC"):
        listas.parsear_csv(b"<html>pagina de error</html>", "69b")


# ── carga ──


def test_carga_reemplaza_es_idempotente_y_no_acepta_truncados(db_sesion):
    falso = SatListasFalso(contenidos={"69b": CSV_RARO})
    r = listas.cargar_lista(db_sesion, "69b", falso)
    assert r.registros == 4 and not r.sin_cambios
    assert listas.cargar_lista(db_sesion, "69b", falso).sin_cambios  # mismo archivo
    assert db_sesion.scalar(select(func.count(ContribuyenteListaSat.id))) == 4

    # Un archivo con 1 renglón contra 4: parece truncado, no reemplaza.
    falso.contenidos["69b"] = CSV_69B_FALSO.encode("latin-1").split(b"\r\n2,")[0] + b"\r\n"
    r = listas.cargar_lista(db_sesion, "69b", falso)
    assert r.rechazada and db_sesion.scalar(select(func.count(ContribuyenteListaSat.id))) == 4
    assert db_sesion.get(CargaListaSat, "69b").error

    # Una versión nueva válida reemplaza (el desvirtuado que salió deja de estar).
    falso.contenidos["69b"] = CSV_RARO.replace(b"DES030303CC3", b"NUE050505EE5")
    r = listas.cargar_lista(db_sesion, "69b", falso)
    rfcs = set(db_sesion.scalars(select(ContribuyenteListaSat.rfc)))
    assert DESVIRTUADO not in rfcs and "NUE050505EE5" in rfcs
    assert db_sesion.get(CargaListaSat, "69b").error is None


def test_portal_real_descarga_con_url_configurable_y_detecta_html(monkeypatch):
    monkeypatch.setenv("FISCALITO_SAT_LISTA_69B_URL", "https://datos.example/69b.csv")
    assert url_de("69b") == "https://datos.example/69b.csv"
    vistos = []

    def transporte(p: httpx.Request) -> httpx.Response:
        vistos.append(str(p.url))
        if "69b" in str(p.url):
            return httpx.Response(200, content=CSV_RARO, headers={"content-type": "text/csv"})
        return httpx.Response(200, text="<html>no</html>", headers={"content-type": "text/html"})

    portal = SatListasPortal(http=httpx.Client(transport=httpx.MockTransport(transporte)))
    datos, url = portal.descargar("69b")
    assert datos == CSV_RARO and url == "https://datos.example/69b.csv"
    with pytest.raises(ErrorServicioExterno, match="FISCALITO_SAT_LISTA_69_FIRMES_URL"):
        portal.descargar("69_firmes")


def test_listas_activas(monkeypatch):
    monkeypatch.delenv("FISCALITO_SAT_LISTAS_ACTIVAS", raising=False)
    assert listas_activas() == ["69b"]
    monkeypatch.setenv("FISCALITO_SAT_LISTAS_ACTIVAS", "69b, 69_no_localizados")
    assert listas_activas() == ["69b", "69_no_localizados"]
    monkeypatch.setenv("FISCALITO_SAT_LISTAS_ACTIVAS", "69b,inventada")
    with pytest.raises(ValueError):
        listas_activas()


def test_lista_69_no_localizados():
    csv_69 = ("RFC;RAZÓN SOCIAL;TIPO PERSONA;SUPUESTO;FECHAS DE PRIMERA PUBLICACION\r\n"
              "NOL060606FF6;NO LOCALIZADA SINTETICA;M;NO LOCALIZADOS;01/02/2026\r\n"
              ).encode("latin-1")
    r = listas.parsear_csv(csv_69, "69_no_localizados")
    assert r[0].rfc == "NOL060606FF6" and r[0].situacion == "no_localizados"
    assert listas.nivel_de("69_no_localizados", "no_localizados") == ("medio", False)


# ── cruce ──


@pytest.fixture
def cliente_con_cfdi(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    servicio.importar(db_sesion, c, [
        ("1.xml", io.BytesIO(cfdi(uuid_n(1), emisor=EFOS, receptor=RFC_CLIENTE))),
        ("2.xml", io.BytesIO(cfdi(uuid_n(2), emisor=EFOS, receptor=RFC_CLIENTE))),
        ("3.xml", io.BytesIO(cfdi(uuid_n(3), emisor=DESVIRTUADO, receptor=RFC_CLIENTE))),
        ("4.xml", io.BytesIO(cfdi(uuid_n(4), emisor=RFC_CLIENTE, receptor=PRESUNTO))),
        ("5.xml", io.BytesIO(cfdi(uuid_n(5), emisor=RFC_CLIENTE, receptor=RFC_COMPRADOR))),
    ], AlmacenamientoMemoria())
    listas.cargar_lista(db_sesion, "69b", SatListasFalso(contenidos={"69b": CSV_RARO}))
    return c


def test_proveedor_en_lista_se_marca_en_rojo_y_genera_alerta(db_sesion, cliente_con_cfdi):
    """El "Listo cuando" de P1-04."""
    riesgos = {(r.rfc, r.relacion): r for r in listas.riesgos_de(db_sesion, cliente_con_cfdi)}
    efos = riesgos[(EFOS, "proveedor")]
    assert efos.rojo and efos.nivel == "alto" and efos.comprobantes == 2
    assert efos.total == "2320.00"
    # Desvirtuado: se ve pero no en rojo. El cliente al que le facturamos: informativo.
    assert not riesgos[(DESVIRTUADO, "proveedor")].rojo
    assert riesgos[(PRESUNTO, "cliente")].nivel == "medio"
    assert not riesgos[(PRESUNTO, "cliente")].rojo
    assert (RFC_COMPRADOR, "cliente") not in riesgos

    nuevas = listas.cruzar_cliente(db_sesion, cliente_con_cfdi)
    assert {(a.rfc, a.relacion, a.nivel) for a in nuevas} == {
        (EFOS, "proveedor", "alto"), (PRESUNTO, "cliente", "medio")}
    assert listas.cruzar_cliente(db_sesion, cliente_con_cfdi) == []  # idempotente
    assert db_sesion.scalar(select(func.count(AlertaRiesgo.id))) == 2

    marcados = listas.rfcs_marcados(db_sesion, {EFOS, RFC_COMPRADOR})
    assert marcados == {EFOS: {"lista": "69b", "situacion": "definitivo", "nivel": "alto"}}


def test_rfc_propio_en_lista_alerta(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="x", nombre="X", rfc=EFOS)
    db_sesion.add(c)
    db_sesion.flush()
    listas.cargar_lista(db_sesion, "69b", SatListasFalso(contenidos={"69b": CSV_RARO}))
    assert [c.id for c in listas.clientes_con_contraparte_listada(db_sesion)] == [c.id]
    [alerta] = listas.cruzar_cliente(db_sesion, c)
    assert alerta.tipo == "propio_69b" and alerta.relacion == "propio"


def test_trabajo_diario_descarga_y_cruza(sesionador):
    registro.limpiar_cache()
    with sesionador() as db:
        asegurar_usuario(db, "uid-a")
        c = Cliente(despacho_id="uid-a", clave="t", nombre="T", rfc=RFC_CLIENTE)
        db.add(c)
        db.flush()
        servicio.importar(db, c, [("1.xml", io.BytesIO(
            cfdi(uuid_n(1), emisor=EFOS, receptor=RFC_CLIENTE)))], AlmacenamientoMemoria())
        encolar(db, "sat.listas_actualizar", {})
        db.commit()
    import app.trabajos.manejadores as m

    m.cargar_manejadores()
    t = procesar_siguiente(sesionador)
    assert t.estado == "hecho", t.error
    assert t.resultado["clientes_a_cruzar"] == 1
    assert procesar_siguiente(sesionador).resultado == {"alertas_nuevas": 1}
    with sesionador() as db:
        assert db.scalar(select(AlertaRiesgo.rfc)) == EFOS
    registro.limpiar_cache()


def test_trabajo_registra_el_error_si_la_lista_no_baja(sesionador):
    class Caido(SatListasFalso):
        def descargar(self, lista):
            raise ErrorServicioExterno("SAT caído")

    registro.limpiar_cache()
    import app.trabajos.manejadores as m

    m.cargar_manejadores()
    registro._CACHE["sat_listas:falso"] = Caido()
    with sesionador() as db:
        encolar(db, "sat.listas_actualizar", {}, max_intentos=1)
        db.commit()
    t = procesar_siguiente(sesionador)
    assert t.estado == "fallido" and "SAT caído" in t.error
    with sesionador() as db:
        assert "SAT caído" in db.get(CargaListaSat, "69b").error
    registro.limpiar_cache()


# ── rutas ──


@pytest.fixture
def con_clientes(sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([Cliente(despacho_id="uid-a", clave="taller", nombre="T", rfc=RFC_CLIENTE),
                Cliente(despacho_id="uid-b", clave="otro", nombre="O", rfc=RFC_CLIENTE)])
    db.commit()
    listas.cargar_lista(db, "69b", SatListasFalso(contenidos={"69b": CSV_RARO}))
    db.commit()
    db.close()


def test_api_riesgos_boveda_y_estado(api, con_clientes, sesionador):
    a = api("uid-a")
    archivos = [("archivos", ("1.xml", cfdi(uuid_n(1), emisor=EFOS, receptor=RFC_CLIENTE),
                              "text/xml")),
                ("archivos", ("2.xml", cfdi(uuid_n(2)), "text/xml"))]
    assert a.post("/api/v1/boveda/clientes/taller/cfdi", files=archivos).status_code == 200
    with sesionador() as db:
        listas.cruzar_cliente(db, db.scalar(select(Cliente).where(Cliente.clave == "taller")))
        db.commit()

    r = a.get("/api/v1/sat/clientes/taller/riesgos-69b").json()
    assert r["en_rojo"] == 1 and r["riesgos"][0]["rfc"] == EFOS
    assert r["alertas"][0]["nivel"] == "alto" and not r["alertas"][0]["atendida"]
    assert r["listas"][0]["lista"] == "69b" and r["listas"][0]["registros"] == 4

    filas = {f["uuid"]: f for f in a.get("/api/v1/boveda/clientes/taller/cfdi").json()[
        "comprobantes"]}
    assert filas[uuid_n(1)]["art_69b"]["situacion"] == "definitivo"
    assert filas[uuid_n(2)]["art_69b"] is None

    estado = a.get("/api/v1/sat/listas/estado").json()["listas"]
    assert {x["lista"] for x in estado} >= {"69b", "69_no_localizados"}
    assert next(x for x in estado if x["lista"] == "69b")["cargada_en"]

    semaforo = a.get("/api/v1/sat/cartera/semaforo").json()["clientes"]
    assert semaforo == [{"clave": "taller", "riesgos_69b": 1, "alertas_contables": 0,
                         "opinion": {"semaforo": "gris", "origen": None, "marca": None,
                                     "resultado": None, "fecha": None}}]

    alerta = r["alertas"][0]["id"]
    b = api("uid-b")
    assert b.get("/api/v1/sat/clientes/taller/riesgos-69b").status_code == 404
    assert b.post(f"/api/v1/sat/clientes/otro/alertas/{alerta}/atender").status_code == 404
    assert b.get("/api/v1/sat/cartera/semaforo").json()["clientes"][0]["riesgos_69b"] == 0
    assert a.post(f"/api/v1/sat/clientes/taller/alertas/{alerta}/atender").status_code == 200
    assert a.get("/api/v1/sat/cartera/semaforo").json()["clientes"][0]["riesgos_69b"] == 0
