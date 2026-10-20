"""
P1-03: verificación de estatus de CFDI.

"Listo cuando": un CFDI cancelado aparece marcado en la bóveda y queda excluido por
`comprobantes_vigentes`. El adaptador real se prueba contra respuestas grabadas del
ConsultaCFDIService (sin red).
"""

import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.boveda_cfdi import servicio
from app.integraciones import registro
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.comun import ErrorServicioExterno
from app.integraciones.sat_estatus import (
    SOAP_ACTION,
    URL_SAT,
    ExpresionCfdi,
    SatEstatusFalso,
    SatEstatusSoap,
    formatear_total,
    leer_respuesta,
)
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import VerificacionCfdi
from app.modelos.trabajos import Trabajo
from app.sat_verificacion import estatus
from app.sat_verificacion import trabajos as sat_trabajos
from app.tenancy import asegurar_usuario
from app.trabajos.cola import procesar_siguiente
from app.trabajos.programacion import TAREAS, revisar_programacion
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, cfdi, uuid_n

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "sat_estatus"


def grabada(nombre: str) -> bytes:
    return (FIX / nombre).read_bytes()


class SinEspera(estatus.Ritmo):
    """Ritmo que no duerme (cuenta las esperas)."""

    def __init__(self) -> None:
        super().__init__(1000, dormir=lambda s: None)


# ── adaptador real con respuestas grabadas ──


def test_expresion_impresa_y_total_como_el_sat():
    assert formatear_total(Decimal("1160.00")) == "1160.0"
    assert formatear_total(Decimal("1160.50")) == "1160.5"
    assert formatear_total(Decimal("0.123456")) == "0.123456"
    assert formatear_total(Decimal("12")) == "12.0"
    e = ExpresionCfdi("AAAA-1", "AAA010101AAA", "BBB010101BBB", Decimal("1160.00"))
    assert e.texto() == "?re=AAA010101AAA&rr=BBB010101BBB&tt=1160.0&id=AAAA-1"


def test_soap_real_manda_sobre_y_soapaction_y_lee_vigente():
    peticiones: list[httpx.Request] = []

    def transporte(p: httpx.Request) -> httpx.Response:
        peticiones.append(p)
        return httpx.Response(200, content=grabada("vigente.xml"),
                              headers={"content-type": "text/xml; charset=utf-8"})

    real = SatEstatusSoap(http=httpx.Client(transport=httpx.MockTransport(transporte)))
    expr = ExpresionCfdi("AAAA-1", "EKU9003173C9", "XAXX010101000", Decimal("100.00"))
    r = real.consultar(expr)
    assert (r.resumen, r.encontrado, r.emisor_en_efos) == ("vigente", True, False)
    p = peticiones[0]
    assert str(p.url) == URL_SAT
    assert p.headers["SOAPAction"] == SOAP_ACTION
    assert p.headers["Content-Type"].startswith("text/xml")
    cuerpo = p.content.decode()
    assert "<c:Consulta xmlns:c=\"http://tempuri.org/\">" in cuerpo
    # El & va escapado dentro del XML, como en phpcfdi soap-request-foobar.xml.
    assert "?re=EKU9003173C9&amp;rr=XAXX010101000&amp;tt=100.0&amp;id=AAAA-1" in cuerpo


@pytest.mark.parametrize("archivo,resumen,proceso,efos", [
    ("cancelado.xml", "cancelado", False, False),
    ("no_encontrado.xml", "desconocido", False, False),
    ("en_proceso.xml", "vigente", True, True),
])
def test_respuestas_grabadas(archivo, resumen, proceso, efos):
    r = leer_respuesta(grabada(archivo))
    assert r.resumen == resumen
    assert r.en_proceso_de_cancelacion is proceso
    assert r.emisor_en_efos is efos


def test_fault_y_basura_dan_502_legible():
    with pytest.raises(ErrorServicioExterno, match="expresión impresa"):
        leer_respuesta(grabada("fault.xml"))
    with pytest.raises(ErrorServicioExterno, match="no es XML"):
        leer_respuesta(b"<html>mantenimiento")


def test_url_configurable(monkeypatch):
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_URL", "https://pruebas.example/Consulta.svc")
    vistos = []
    transporte = httpx.MockTransport(
        lambda p: vistos.append(str(p.url)) or httpx.Response(200, content=grabada(
            "vigente.xml")))
    SatEstatusSoap(http=httpx.Client(transport=transporte)).consultar(
        ExpresionCfdi("A", "B", "C", Decimal(1)))
    assert vistos == ["https://pruebas.example/Consulta.svc"]


def test_registro_falso_y_sat(monkeypatch):
    registro.limpiar_cache()
    monkeypatch.delenv("FISCALITO_SAT_ESTATUS", raising=False)
    assert isinstance(registro.obtener("sat_estatus"), SatEstatusFalso)
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS", "sat")
    assert isinstance(registro.obtener("sat_estatus"), SatEstatusSoap)
    registro.limpiar_cache()


# ── dominio ──


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    xmls = [(f"{n}.xml", io.BytesIO(cfdi(uuid_n(n), fecha=f"2026-03-{n + 1:02d}T10:00:00")))
            for n in range(6)]
    xmls.append(("r.xml", io.BytesIO(cfdi(uuid_n(9), emisor=RFC_PROVEEDOR,
                                          receptor=RFC_CLIENTE,
                                          fecha="2026-03-20T10:00:00"))))
    servicio.importar(db_sesion, c, xmls, AlmacenamientoMemoria())
    return c


def test_cancelado_queda_marcado_y_fuera_de_comprobantes_vigentes(db_sesion, cliente):
    """El "Listo cuando" de P1-03."""
    falso = SatEstatusFalso(cancelados={uuid_n(2)}, no_encontrados={uuid_n(4)})
    corte = datetime.now(UTC)
    r = estatus.verificar_cliente(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31),
                                  corte, falso, hilos=3, ritmo=SinEspera())
    assert (r.consultados, r.cancelados, r.nuevos_cancelados, r.no_encontrados) == (7, 1, 1, 1)
    assert r.vigentes == 5 and r.pendientes == 0

    cancelado = servicio.obtener(db_sesion, cliente, uuid_n(2))
    assert cancelado.estatus_sat == "cancelado" and cancelado.fecha_estatus is not None
    assert servicio.obtener(db_sesion, cliente, uuid_n(4)).estatus_sat == "desconocido"
    v = db_sesion.get(VerificacionCfdi, cancelado.id)
    assert v.estado == "Cancelado" and v.estatus_cancelacion == "Cancelado con aceptación"

    todos = select(Comprobante).where(Comprobante.cliente_id == cliente.id)
    vigentes = list(db_sesion.scalars(servicio.comprobantes_vigentes(todos)))
    assert len(vigentes) == 6 and uuid_n(2) not in {c.uuid for c in vigentes}
    # El no encontrado (desconocido) sigue contando: no verificar no es motivo para excluir.
    assert uuid_n(4) in {c.uuid for c in vigentes}
    total = db_sesion.scalar(servicio.comprobantes_vigentes(
        select(func.sum(Comprobante.total)).where(Comprobante.cliente_id == cliente.id)))
    assert total == Decimal("1160.00") * 6


def test_idempotente_y_un_cancelado_no_se_vuelve_a_consultar(db_sesion, cliente):
    falso = SatEstatusFalso(cancelados={uuid_n(2)})
    corte = datetime.now(UTC)
    args = (db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31), corte, falso)
    estatus.verificar_cliente(*args, ritmo=SinEspera())
    n = len(falso.consultas)
    otra = estatus.verificar_cliente(*args, ritmo=SinEspera())
    assert otra.consultados == 0 and len(falso.consultas) == n  # mismo corte: nada nuevo
    # Corte posterior: se re-verifican los vigentes, nunca el cancelado.
    falso.consultas.clear()
    estatus.verificar_cliente(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31),
                              corte + timedelta(seconds=5), falso, ritmo=SinEspera())
    assert uuid_n(2) not in {e.uuid for e in falso.consultas}
    assert len(falso.consultas) == 6


def test_error_por_cfdi_no_tumba_el_lote(db_sesion, cliente):
    class Fallon(SatEstatusFalso):
        def consultar(self, expresion):
            if expresion.uuid == uuid_n(1):
                raise ErrorServicioExterno("timeout")
            return super().consultar(expresion)

    r = estatus.verificar_cliente(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31),
                                  datetime.now(UTC), Fallon(), ritmo=SinEspera())
    assert r.errores == 1 and r.consultados == 6
    assert servicio.obtener(db_sesion, cliente, uuid_n(1)).fecha_estatus is None


def test_ritmo_espacia_las_llamadas():
    reloj = [0.0]
    esperas: list[float] = []
    ritmo = estatus.Ritmo(4, reloj=lambda: reloj[0], dormir=esperas.append)
    for _ in range(5):
        ritmo.esperar()
    assert esperas == pytest.approx([0.25, 0.5, 0.75, 1.0])


def test_limites_por_variable(monkeypatch):
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_CONCURRENCIA", "2")
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_POR_SEGUNDO", "1.5")
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_LOTE", "3")
    assert (estatus.concurrencia(), estatus.por_segundo(), estatus.tamano_lote()) == (2, 1.5, 3)


# ── trabajos y programación ──


def test_trabajo_por_lotes_encola_su_continuacion(sesionador, monkeypatch):
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_LOTE", "3")
    monkeypatch.setenv("FISCALITO_SAT_ESTATUS_POR_SEGUNDO", "1000")
    registro.limpiar_cache()
    falso = registro.obtener("sat_estatus")
    falso.cancelados = {uuid_n(0)}
    with sesionador() as db:
        asegurar_usuario(db, "uid-a")
        c = Cliente(despacho_id="uid-a", clave="t", nombre="T", rfc=RFC_CLIENTE)
        db.add(c)
        db.flush()
        servicio.importar(db, c, [(f"{n}.xml", io.BytesIO(cfdi(uuid_n(n)))) for n in range(7)],
                          AlmacenamientoMemoria())
        sat_trabajos.encolar_verificacion(db, c, date(2026, 1, 1), date(2026, 12, 31))
        # La misma petición viva no se duplica.
        sat_trabajos.encolar_verificacion(db, c, date(2026, 1, 1), date(2026, 12, 31))
        db.commit()
        cid = c.id
    hechos = []
    while (t := procesar_siguiente(sesionador)) is not None:
        hechos.append(t)
    assert [t.estado for t in hechos] == ["hecho"] * 3
    assert [t.resultado["pendientes"] for t in hechos] == [4, 1, 0]
    with sesionador() as db:
        estados = dict(db.execute(select(Comprobante.uuid, Comprobante.estatus_sat)
                                  .where(Comprobante.cliente_id == cid)).all())
    assert estados[uuid_n(0)] == "cancelado"
    assert sum(1 for e in estados.values() if e == "vigente") == 6
    registro.limpiar_cache()


def test_programacion_diaria_del_mes_y_semanal_del_anio(sesionador):
    nombres = {t.nombre: t for t in TAREAS}
    assert nombres["sat_estatus_mes"].hora is not None
    assert nombres["sat_estatus_anio"].cada == timedelta(days=7)
    tareas = [nombres["sat_estatus_mes"], nombres["sat_estatus_anio"]]
    hoy = datetime.now(UTC)
    with sesionador() as db:
        asegurar_usuario(db, "uid-a")
        c = Cliente(despacho_id="uid-a", clave="t", nombre="T", rfc=RFC_CLIENTE)
        db.add(c)
        db.flush()
        reciente = (hoy - timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
        servicio.importar(db, c, [("a.xml", io.BytesIO(cfdi(uuid_n(1), fecha=reciente)))],
                          AlmacenamientoMemoria())
        db.commit()
    assert set(revisar_programacion(sesionador, tareas=tareas)) == {
        "sat_estatus_mes", "sat_estatus_anio"}
    for _ in range(2):
        assert procesar_siguiente(sesionador).estado == "hecho"
    with sesionador() as db:
        hijos = list(db.scalars(select(Trabajo).where(Trabajo.tipo == "sat.verificar_estatus")))
    assert len(hijos) == 2 and {t.carga["origen"] for t in hijos} == {
        "programado:mes", "programado:anio"}


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
    db.close()


def test_api_verificar_estatus_y_boveda_muestra_cancelado(api, con_clientes, sesionador):
    a = api("uid-a")
    archivos = [("archivos", (f"{n}.xml", cfdi(uuid_n(n)), "text/xml")) for n in range(3)]
    assert a.post("/api/v1/boveda/clientes/taller/cfdi", files=archivos).status_code == 200
    falso = registro.obtener("sat_estatus")
    falso.cancelados = {uuid_n(1)}

    r = a.post("/api/v1/sat/clientes/taller/verificar-estatus",
               json={"desde": "2026-03-01", "hasta": "2026-03-31"})
    assert r.status_code == 200, r.text
    assert r.json()["comprobantes"] == 3 and r.json()["trabajo"]["tipo"] == "sat.verificar_estatus"
    assert procesar_siguiente(sesionador).estado == "hecho"

    filas = a.get("/api/v1/boveda/clientes/taller/cfdi").json()["comprobantes"]
    por_uuid = {f["uuid"]: f for f in filas}
    assert por_uuid[uuid_n(1)]["estatus_sat"] == "cancelado"
    assert por_uuid[uuid_n(1)]["fecha_estatus"]
    assert por_uuid[uuid_n(1)]["estatus_cancelacion"] == "Cancelado con aceptación"
    assert por_uuid[uuid_n(0)]["estatus_sat"] == "vigente"
    canceladas = a.get("/api/v1/boveda/clientes/taller/cfdi",
                       params={"estatus": "cancelado"}).json()
    assert canceladas["total"] == 1


def test_api_multitenant_y_validacion(api, con_clientes):
    b = api("uid-b")
    r = b.post("/api/v1/sat/clientes/taller/verificar-estatus",
               json={"desde": "2026-03-01", "hasta": "2026-03-31"})
    assert r.status_code == 404
    a = api("uid-a")
    r = a.post("/api/v1/sat/clientes/taller/verificar-estatus",
               json={"desde": "2026-04-01", "hasta": "2026-03-01"})
    assert r.status_code == 422
