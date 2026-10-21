"""P6-02: logs con contexto, errores al monitoreo (falso) y salud de worker/programador."""

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.integraciones import registro
from app.logging_config import JSONFormatter, anotar, con_contexto
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.observabilidad import latir, salud_procesos
from app.tenancy import asegurar_usuario
from app.trabajos import encolar, manejador, procesar_siguiente
from app.trabajos.cola import olvidar_manejador
from app.trabajos.programacion import TareaRecurrente, revisar_programacion
from app.trabajos.worker import una_vuelta

T0 = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)


@pytest.fixture
def monitoreo(monkeypatch):
    monkeypatch.setenv("FISCALITO_MONITOREO", "falso")
    registro.limpiar_cache()
    falso = registro.obtener("monitoreo")
    falso.eventos.clear()
    yield falso
    registro.limpiar_cache()


@pytest.fixture
def trabajo_que_falla():
    @manejador("prueba.revienta")
    def _revienta(db, trabajo):
        logging.getLogger("prueba").error("adentro del manejador")
        raise ValueError("se rompió el cálculo")

    yield
    olvidar_manejador("prueba.revienta")


def _linea(record_msg: str, nivel=logging.INFO) -> dict:
    record = logging.LogRecord("x", nivel, __file__, 1, record_msg, None, None)
    return json.loads(JSONFormatter().format(record))


def test_el_log_lleva_el_contexto_vigente():
    with con_contexto(trabajo_id=7, despacho_id="d1"):
        anotar(intento=2)
        linea = _linea("hola")
    assert linea["trabajo_id"] == 7 and linea["despacho_id"] == "d1" and linea["intento"] == 2
    assert linea["proceso"] in ("api", "worker", "programador")
    assert "trabajo_id" not in _linea("fuera")


def test_error_en_trabajo_de_fondo_llega_al_monitoreo_con_contexto(
    sesionador, monitoreo, trabajo_que_falla
):
    with sesionador() as db:
        asegurar_usuario(db, "uid-a")
        c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller")
        db.add(c)
        db.flush()
        t = encolar(db, "prueba.revienta", {}, despacho_id="uid-a", cliente_id=c.id,
                    ejecutar_en=T0, max_intentos=2)
        db.commit()
        trabajo_id, cliente_id = t.id, c.id

    resultado = procesar_siguiente(sesionador, ahora=T0)
    assert resultado.estado == "pendiente"  # se reintentará
    errores = [e for e in monitoreo.eventos if e["tipo"] == "error"]
    assert len(errores) == 1
    evento = errores[0]
    assert isinstance(evento["error"], ValueError)
    ctx = evento["contexto"]
    assert ctx["origen"] == "trabajo"
    assert ctx["trabajo_id"] == trabajo_id and ctx["trabajo_tipo"] == "prueba.revienta"
    assert ctx["despacho_id"] == "uid-a" and ctx["cliente_id"] == cliente_id
    assert ctx["intento"] == 1 and ctx["max_intentos"] == 2 and ctx["ultimo_intento"] is False
    assert "se rompió el cálculo" in ctx["traza"] and "ValueError" in ctx["traza"]

    procesar_siguiente(sesionador, ahora=T0 + timedelta(hours=1))
    ultimo = [e for e in monitoreo.eventos if e["tipo"] == "error"][-1]["contexto"]
    assert ultimo["intento"] == 2 and ultimo["ultimo_intento"] is True


def test_un_monitoreo_roto_no_tumba_al_worker(sesionador, monkeypatch, trabajo_que_falla):
    class Roto:
        def capturar_error(self, *a, **k):
            raise RuntimeError("sentry caído")

    monkeypatch.setattr("app.observabilidad._monitoreo", lambda: Roto())
    with sesionador() as db:
        encolar(db, "prueba.revienta", {}, ejecutar_en=T0, max_intentos=1)
        db.commit()
    assert procesar_siguiente(sesionador, ahora=T0).estado == "fallido"


def test_tarea_programada_rota_llega_al_monitoreo(sesionador, monitoreo):
    def _revienta(db, ranura):
        raise KeyError("config")

    tarea = TareaRecurrente("rota", _revienta, cada=timedelta(hours=1))
    assert revisar_programacion(sesionador, ahora=T0, tareas=[tarea]) == []
    ctx = monitoreo.eventos[-1]["contexto"]
    assert ctx["origen"] == "programador" and ctx["tarea"] == "rota"


def test_error_inesperado_en_ruta_llega_con_request_id_y_despacho(api, monitoreo, monkeypatch):
    # Una ruta real que revienta por dentro (no se monta una ruta de prueba: cambiaría el
    # OpenAPI cacheado de la app y los contratos versionados).
    def _revienta(ctx):
        raise ZeroDivisionError("división")

    monkeypatch.setattr("app.routes.cartera.clientes_visibles", _revienta)
    cliente = api("uid-r")
    with pytest.raises(ZeroDivisionError):
        cliente.get("/api/v1/cartera/clientes", headers={"X-Request-ID": "req-123"})
    ctx = monitoreo.eventos[-1]["contexto"]
    assert ctx["origen"] == "ruta" and ctx["ruta"] == "/api/v1/cartera/clientes"
    assert ctx["request_id"] == "req-123" and ctx["despacho_id"] == "uid-r"
    assert len([e for e in monitoreo.eventos if e["tipo"] == "error"]) == 1  # sin duplicar


def test_respuesta_lleva_x_request_id(api):
    r = api("uid-x").get("/health")
    assert r.status_code == 200 and len(r.headers["x-request-id"]) >= 16
    r = api("uid-x").get("/health", headers={"X-Request-ID": "abc"})
    assert r.headers["x-request-id"] == "abc"


def test_salud_de_worker_y_programador(sesionador):
    with sesionador() as db:
        estado = salud_procesos(db, ahora=T0)
    assert estado["worker"]["vivo"] is False and estado["sano"] is False

    una_vuelta(sesionador, ahora=T0, tareas=[])
    with sesionador() as db:
        estado = salud_procesos(db, ahora=T0 + timedelta(minutes=1))
        assert estado["worker"]["vivo"] and estado["programador"]["vivo"]
        assert estado["sano"] is True
        assert salud_procesos(db, ahora=T0 + timedelta(minutes=30))["worker"]["vivo"] is False

    # Un pendiente vencido que nadie toma = atorado.
    with sesionador() as db:
        encolar(db, "x", {}, ejecutar_en=T0 - timedelta(hours=1))
        db.commit()
        estado = salud_procesos(db, ahora=T0 + timedelta(minutes=1))
    assert estado["trabajos"]["pendientes_sin_tomar"] == 1 and estado["sano"] is False


def test_worker_sin_programacion_solo_late_el_worker(sesionador):
    una_vuelta(sesionador, ahora=T0, tareas=[], con_programacion=False)
    with sesionador() as db:
        estado = salud_procesos(db, ahora=T0)
    assert estado["worker"]["vivo"] and not estado["programador"]["vivo"]
    latir(sesionador, "programador", ahora=T0)
    with sesionador() as db:
        assert salud_procesos(db, ahora=T0)["sano"] is True


def test_health_reporta_procesos(api, sesionador):
    cuerpo = api("uid-h").get("/health").json()
    assert cuerpo["status"] == "degradado"  # nadie ha latido en el SQLite del test
    assert cuerpo["base_datos"] == "ok" and "worker" in cuerpo["procesos"]
    latir(sesionador, "worker")
    latir(sesionador, "programador")
    cuerpo = api("uid-h").get("/health").json()
    assert cuerpo["status"] == "ok" and cuerpo["procesos"]["sano"] is True
    with sesionador() as db:
        assert db.query(Trabajo).count() == 0
