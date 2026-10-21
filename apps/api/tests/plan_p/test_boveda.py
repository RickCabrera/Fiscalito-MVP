"""
P0-03: bóveda de CFDI — servicio de importación y rutas.

"Listo cuando": un ZIP con 500 XML se guarda una sola vez, se clasifica emitido/recibido por
el RFC del cliente y el XML vuelve a descargarse idéntico byte por byte; multi-tenant probado.
"""

import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.boveda_cfdi import servicio
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.tenancy import asegurar_usuario
from tests.plan_p.cfdi_sintetico import (
    RFC_CLIENTE,
    RFC_COMPRADOR,
    RFC_PROVEEDOR,
    cfdi,
    pago,
    uuid_n,
)

NOMINA = Path(__file__).resolve().parents[1] / "fixtures" / "nomina"


def _zip(miembros: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos)
    return buf.getvalue()


def _quinientos() -> dict[str, bytes]:
    """250 emitidos + 250 recibidos, con variaciones de formato para que no sean idénticos."""
    miembros = {}
    for n in range(500):
        emitido = n % 2 == 0
        xml = cfdi(
            uuid_n(n),
            emisor=RFC_CLIENTE if emitido else RFC_PROVEEDOR,
            receptor=RFC_COMPRADOR if emitido else RFC_CLIENTE,
            fecha=f"2026-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}T09:{n % 60:02d}:00",
        )
        if n % 3 == 0:  # fin de línea Windows y BOM: deben volver idénticos
            xml = b"\xef\xbb\xbf" + xml.replace(b"\n", b"\r\n")
        nombre = f"carpeta/{n:03d}.{'XML' if n % 5 == 0 else 'xml'}"
        miembros[nombre] = xml
    return miembros


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    return c


# ── servicio ──


def test_zip_de_500_una_sola_vez_clasificado_y_byte_por_byte(db_sesion, cliente):
    almacen = AlmacenamientoMemoria()
    miembros = _quinientos()
    contenido = _zip(miembros)

    r = servicio.importar(db_sesion, cliente, [("lote.zip", io.BytesIO(contenido))], almacen)
    assert (r.importados, r.duplicados, r.rechazados) == (500, 0, [])
    assert r.rfc_cliente == RFC_CLIENTE and not r.rfc_deducido

    # Se sube OTRA VEZ: nada se duplica.
    r2 = servicio.importar(db_sesion, cliente, [("lote.zip", io.BytesIO(contenido))], almacen)
    assert (r2.importados, r2.duplicados) == (0, 500)
    assert {d["razon"] for d in r2.duplicados_detalle} == {"ya existía"}
    assert db_sesion.scalar(select(func.count(Comprobante.id))) == 500
    assert len(almacen.archivos) == 500

    por_dir = dict(db_sesion.execute(
        select(Comprobante.direccion, func.count()).group_by(Comprobante.direccion)
    ).all())
    assert por_dir == {"emitido": 250, "recibido": 250}

    for n, (_nombre, original) in enumerate(miembros.items()):
        comp = servicio.obtener(db_sesion, cliente, uuid_n(n))
        assert servicio.leer_xml_original(comp, almacen) == original
        assert comp.sha256 == hashlib.sha256(original).hexdigest()
        assert comp.direccion == ("emitido" if n % 2 == 0 else "recibido")


def test_mezcla_de_xml_sueltos_zip_y_rechazos(db_sesion, cliente):
    almacen = AlmacenamientoMemoria()
    interno = _zip({"x.xml": cfdi(uuid_n(900))})
    zip_ = _zip({
        "a.xml": cfdi(uuid_n(1)),
        "dup.xml": cfdi(uuid_n(1)),  # mismo UUID dentro del mismo lote
        "anidado.zip": interno,
        "notas.txt": b"hola",
        "roto.xml": b"<cfdi:Comprobante",
        "ajeno.xml": cfdi(uuid_n(2), emisor=RFC_PROVEEDOR, receptor=RFC_COMPRADOR),
        "__MACOSX/._a.xml": b"basura de mac",
        "sub/": b"",
    })
    r = servicio.importar(db_sesion, cliente, [
        ("suelto.XML", io.BytesIO(cfdi(uuid_n(3), tipo="E"))),
        ("lote.zip", io.BytesIO(zip_)),
        ("foto.png", io.BytesIO(b"\x89PNG")),
        ("pago.xml", io.BytesIO(pago(uuid_n(4), [uuid_n(1)]))),
    ], almacen)
    assert r.importados == 3  # suelto, a.xml, pago
    assert r.duplicados == 1
    razones = {x["archivo"]: x["razon"] for x in r.rechazados}
    assert set(razones) == {"lote.zip/anidado.zip", "lote.zip/notas.txt", "lote.zip/roto.xml",
                            "lote.zip/ajeno.xml", "foto.png"}
    assert "ZIP dentro de otro ZIP" in razones["lote.zip/anidado.zip"]
    assert "no es emisor ni receptor" in razones["lote.zip/ajeno.xml"]
    p = servicio.obtener(db_sesion, cliente, uuid_n(4))
    assert p.tipo == "P" and p.datos["pagos"]["uuids_relacionados"] == [uuid_n(1)]


def test_zip_danado(db_sesion, cliente):
    r = servicio.importar(db_sesion, cliente, [("x.zip", io.BytesIO(b"PK\x03\x04basura"))],
                          AlmacenamientoMemoria())
    assert r.importados == 0 and "dañado" in r.rechazados[0]["razon"]


def test_xml_demasiado_grande_se_rechaza(db_sesion, cliente, monkeypatch):
    monkeypatch.setattr(servicio, "MAX_BYTES_XML", 100)
    zip_ = _zip({"grande.xml": cfdi(uuid_n(1))})
    r = servicio.importar(db_sesion, cliente, [
        ("suelto.xml", io.BytesIO(cfdi(uuid_n(2)))), ("z.zip", io.BytesIO(zip_)),
    ], AlmacenamientoMemoria())
    assert r.importados == 0 and len(r.rechazados) == 2
    assert all("10 MB" in x["razon"] for x in r.rechazados)


def test_cliente_sin_rfc_deduce_el_mas_frecuente(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="sinrfc", nombre="Sin RFC", rfc="")
    db_sesion.add(c)
    db_sesion.flush()
    archivos = sorted(NOMINA.glob("semana-01/*.xml"))
    r = servicio.importar(
        db_sesion, c, [(p.name, io.BytesIO(p.read_bytes())) for p in archivos],
        AlmacenamientoMemoria(),
    )
    assert r.rfc_deducido and r.rfc_cliente == "XAP0101011X0"  # el patrón emisor
    assert r.importados == len(archivos)
    assert {d["direccion"] for d in r.importados_detalle} == {"emitido"}
    assert c.rfc == ""  # la ficha del cliente no se toca


def test_rfc_de_la_ficha_si_la_columna_esta_vacia(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="f", nombre="F", rfc="",
                datos={"rfc": RFC_CLIENTE.lower()})
    db_sesion.add(c)
    db_sesion.flush()
    r = servicio.importar(db_sesion, c, [("a.xml", io.BytesIO(cfdi(uuid_n(1))))],
                          AlmacenamientoMemoria())
    assert r.rfc_cliente == RFC_CLIENTE and not r.rfc_deducido and r.importados == 1


def test_mismo_uuid_en_dos_clientes_si_se_permite(db_sesion, cliente):
    otro = Cliente(despacho_id="uid-a", clave="comprador", nombre="C", rfc=RFC_COMPRADOR)
    db_sesion.add(otro)
    db_sesion.flush()
    almacen = AlmacenamientoMemoria()
    xml = cfdi(uuid_n(7))
    servicio.importar(db_sesion, cliente, [("a.xml", io.BytesIO(xml))], almacen)
    r = servicio.importar(db_sesion, otro, [("a.xml", io.BytesIO(xml))], almacen)
    assert r.importados == 1
    assert servicio.obtener(db_sesion, otro, uuid_n(7)).direccion == "recibido"
    assert servicio.obtener(db_sesion, cliente, uuid_n(7)).direccion == "emitido"


def test_xml_alterado_en_el_almacen_no_se_entrega(db_sesion, cliente):
    almacen = AlmacenamientoMemoria()
    servicio.importar(db_sesion, cliente, [("a.xml", io.BytesIO(cfdi(uuid_n(1))))], almacen)
    comp = servicio.obtener(db_sesion, cliente, uuid_n(1))
    almacen.archivos[comp.ruta_xml] += b" "
    with pytest.raises(Exception) as e:
        servicio.leer_xml_original(comp, almacen)
    assert getattr(e.value, "status_code", None) == 500


# ── rutas ──


@pytest.fixture
def almacen_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    return tmp_path / "almacen"


@pytest.fixture
def con_clientes(sesionador):
    """Despacho A con `taller` y despacho B con `otro`."""
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([
        Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE),
        Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE),
    ])
    db.commit()
    db.close()


BASE = "/api/v1/boveda/clientes"


def test_api_zip_de_500_y_descarga_identica(api, con_clientes, almacen_dir):
    miembros = _quinientos()
    contenido = _zip(miembros)
    a = api("uid-a")
    lote = [("archivos", ("lote.zip", contenido, "application/zip"))]
    r = a.post(f"{BASE}/taller/cfdi", files=lote)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["exito"] and cuerpo["importados"] == 500 and cuerpo["duplicados"] == 0

    r = a.post(f"{BASE}/taller/cfdi", files=lote)
    assert r.json()["importados"] == 0 and r.json()["duplicados"] == 500
    assert len(list(almacen_dir.rglob("*.xml"))) == 500

    for n in (0, 3, 5, 499):
        original = list(miembros.values())[n]
        x = a.get(f"{BASE}/taller/cfdi/{uuid_n(n).lower()}/xml")
        assert x.status_code == 200
        assert x.content == original  # byte por byte
        assert x.headers["content-type"].startswith("application/xml")

    lista = a.get(f"{BASE}/taller/cfdi", params={"por_pagina": 200}).json()
    assert lista["total"] == 500 and len(lista["comprobantes"]) == 200
    emitidos = a.get(f"{BASE}/taller/cfdi", params={"direccion": "emitido"}).json()
    assert emitidos["total"] == 250
    resumen = a.get(f"{BASE}/taller/resumen").json()["renglones"]
    assert sum(x["cantidad"] for x in resumen) == 500
    assert {x["direccion"] for x in resumen} == {"emitido", "recibido"}


def test_api_filtros_paginado_y_borrado(api, con_clientes, almacen_dir):
    a = api("uid-a")
    archivos = [
        ("archivos", ("1.xml", cfdi(uuid_n(1), fecha="2026-01-15T10:00:00"), "text/xml")),
        ("archivos", ("2.xml", cfdi(uuid_n(2), tipo="E", fecha="2026-02-01T00:00:00"),
                      "text/xml")),
        ("archivos", ("3.xml", cfdi(uuid_n(3), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                                    fecha="2026-02-28T23:59:59"), "text/xml")),
        ("archivos", ("4.xml", pago(uuid_n(4), [uuid_n(1)]), "text/xml")),
    ]
    assert a.post(f"{BASE}/taller/cfdi", files=archivos).json()["importados"] == 4

    def total(**params):
        return a.get(f"{BASE}/taller/cfdi", params=params).json()["total"]

    assert total() == 4
    assert total(desde="2026-02-01", hasta="2026-02-28") == 2  # 'hasta' inclusivo
    assert total(tipo="E") == 1 and total(tipo="P") == 1
    assert total(direccion="recibido") == 1
    assert total(rfc=RFC_PROVEEDOR) == 1  # contraparte de lo recibido
    assert total(rfc=RFC_COMPRADOR) == 3  # contraparte de lo emitido
    assert total(estatus="desconocido") == 4 and total(estatus="vigente") == 0
    p1 = a.get(f"{BASE}/taller/cfdi", params={"por_pagina": 3, "pagina": 2}).json()
    assert len(p1["comprobantes"]) == 1
    assert p1["comprobantes"][0]["uuid"] == uuid_n(1)  # el más viejo al final
    assert p1["comprobantes"][0]["total"] == "1160.00"

    assert a.get(f"{BASE}/taller/cfdi", params={"tipo": "Z"}).status_code == 422
    assert a.get(f"{BASE}/taller/cfdi",
                 params={"desde": "2026-03-01", "hasta": "2026-01-01"}).status_code == 422

    assert a.delete(f"{BASE}/taller/cfdi/{uuid_n(2)}").json()["exito"]
    assert total() == 3
    assert a.get(f"{BASE}/taller/cfdi/{uuid_n(2)}/xml").status_code == 404
    assert a.delete(f"{BASE}/taller/cfdi/{uuid_n(2)}").status_code == 404
    assert len(list(almacen_dir.rglob("*.xml"))) == 3


def test_multi_tenant_b_no_ve_ni_toca_lo_de_a(api, con_clientes, almacen_dir):
    a, b = api("uid-a"), api("uid-b")
    xml = cfdi(uuid_n(1))
    assert a.post(f"{BASE}/taller/cfdi",
                  files=[("archivos", ("1.xml", xml, "text/xml"))]).json()["importados"] == 1

    # B pide el cliente de A: 404 en todo, igual que si no existiera.
    assert b.get(f"{BASE}/taller/cfdi").status_code == 404
    assert b.get(f"{BASE}/taller/resumen").status_code == 404
    assert b.get(f"{BASE}/taller/cfdi/{uuid_n(1)}/xml").status_code == 404
    assert b.delete(f"{BASE}/taller/cfdi/{uuid_n(1)}").status_code == 404
    assert b.post(f"{BASE}/taller/cfdi",
                  files=[("archivos", ("1.xml", xml, "text/xml"))]).status_code == 404

    # Su propio cliente, con el MISMO RFC, no ve el CFDI de A: la bóveda es por cliente.
    assert b.get(f"{BASE}/otro/cfdi").json()["total"] == 0
    assert b.get(f"{BASE}/otro/cfdi/{uuid_n(1)}/xml").status_code == 404
    # Y si lo sube, es un comprobante suyo, no "ya existía".
    r = b.post(f"{BASE}/otro/cfdi", files=[("archivos", ("1.xml", xml, "text/xml"))]).json()
    assert r["importados"] == 1 and r["duplicados"] == 0
    assert a.get(f"{BASE}/taller/cfdi").json()["total"] == 1
    # A no ve el cliente de B.
    assert a.get(f"{BASE}/otro/cfdi").status_code == 404


def test_api_sin_token_es_401(api, con_clientes, almacen_dir):
    a = api("uid-a")
    r = a.get(f"{BASE}/taller/cfdi", headers={"Authorization": ""})
    assert r.status_code == 401
