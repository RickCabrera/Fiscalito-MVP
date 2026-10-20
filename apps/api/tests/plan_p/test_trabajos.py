"""P0-04: cola de trabajos, reintentos con backoff, huérfanos, programación y rutas."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.modelos.nucleo import Cliente, Despacho
from app.modelos.trabajos import EjecucionProgramada, Trabajo
from app.trabajos import backoff, encolar, manejador, procesar_siguiente
from app.trabajos.cola import olvidar_manejador
from app.trabajos.programacion import TareaRecurrente, revisar_programacion
from app.trabajos.worker import correr, una_vuelta

T0 = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)
MX = ZoneInfo("America/Mexico_City")


@pytest.fixture
def tipo_prueba():
    """Registra manejadores de prueba y los quita al final."""
    tipos: list[str] = []

    def _registrar(tipo: str, funcion):
        manejador(tipo)(funcion)
        tipos.append(tipo)
        return funcion

    yield _registrar
    for t in tipos:
        olvidar_manejador(t)


def _leer(sesionador, trabajo_id: int) -> Trabajo:
    with sesionador() as db:
        return db.get(Trabajo, trabajo_id)


# ── encolar / clave_unica ──


def test_clave_unica_no_duplica_mientras_esta_viva(db_sesion):
    a = encolar(db_sesion, "x", {"n": 1}, clave_unica="k")
    b = encolar(db_sesion, "x", {"n": 2}, clave_unica="k")
    assert a.id == b.id
    assert db_sesion.scalar(select(Trabajo.carga).where(Trabajo.id == a.id)) == {"n": 1}
    assert len(list(db_sesion.scalars(select(Trabajo)))) == 1


def test_clave_unica_libre_cuando_el_anterior_termino(db_sesion):
    a = encolar(db_sesion, "x", clave_unica="k")
    a.estado = "hecho"
    db_sesion.flush()
    b = encolar(db_sesion, "x", clave_unica="k")
    assert b.id != a.id


def test_sin_clave_si_duplica(db_sesion):
    assert encolar(db_sesion, "x").id != encolar(db_sesion, "x").id


def test_el_indice_parcial_sostiene_la_regla_en_la_base(db_sesion):
    """Aunque alguien inserte por fuera de `encolar`, la base rechaza el duplicado vivo."""
    db_sesion.add(Trabajo(tipo="x", clave_unica="k", estado="pendiente", ejecutar_en=T0))
    db_sesion.flush()
    db_sesion.add(Trabajo(tipo="x", clave_unica="k", estado="corriendo", ejecutar_en=T0))
    with pytest.raises(IntegrityError):
        db_sesion.flush()


def test_encolar_respeta_la_transaccion_de_afuera(sesionador):
    """El savepoint de la carrera no compromete lo que el request lleva hecho."""
    with sesionador() as db:
        db.add(Despacho(id="d1"))
        encolar(db, "x", clave_unica="k", despacho_id="d1")
        db.rollback()
    with sesionador() as db:
        assert db.scalar(select(Trabajo)) is None
        assert db.get(Despacho, "d1") is None


def test_fecha_con_zona_se_compara_en_utc(sesionador, tipo_prueba):
    """12:00 en CDMX son 18:00 UTC: a las 15:00 UTC todavía no toca."""
    tipo_prueba("x", lambda db, t: {"ok": True})
    with sesionador() as db:
        t = encolar(db, "x", ejecutar_en=datetime(2026, 10, 19, 12, 0, tzinfo=MX))
        db.commit()
    assert procesar_siguiente(sesionador, ahora=T0) is None
    hecho = procesar_siguiente(sesionador, ahora=datetime(2026, 10, 19, 18, 0, tzinfo=UTC))
    assert hecho is not None and hecho.id == t.id and hecho.estado == "hecho"


# ── procesar_siguiente: éxito, reintento con backoff, fallido ──


def test_corre_y_guarda_resultado(sesionador, tipo_prueba):
    tipo_prueba("suma", lambda db, t: {"total": t.carga["a"] + t.carga["b"]})
    with sesionador() as db:
        encolar(db, "suma", {"a": 2, "b": 3}, ejecutar_en=T0)
        db.commit()
    t = procesar_siguiente(sesionador, ahora=T0)
    assert t.estado == "hecho" and t.resultado == {"total": 5} and t.intentos == 1
    assert t.terminado_en is not None and t.error is None
    assert procesar_siguiente(sesionador, ahora=T0) is None


def test_reintenta_con_backoff_exponencial_y_luego_falla(sesionador, tipo_prueba):
    def _falla(db, t):
        raise RuntimeError("boom")

    tipo_prueba("falla", _falla)
    with sesionador() as db:
        tid = encolar(db, "falla", max_intentos=3, ejecutar_en=T0).id
        db.commit()

    momento = T0
    t = procesar_siguiente(sesionador, ahora=momento)
    assert t.estado == "pendiente" and t.intentos == 1 and "boom" in t.error
    assert t.ejecutar_en == momento + timedelta(seconds=30)
    # Antes del backoff no se toma.
    assert procesar_siguiente(sesionador, ahora=momento + timedelta(seconds=29)) is None

    momento = t.ejecutar_en
    t = procesar_siguiente(sesionador, ahora=momento)
    assert t.intentos == 2 and t.ejecutar_en == momento + timedelta(seconds=60)

    t = procesar_siguiente(sesionador, ahora=t.ejecutar_en)
    assert t.estado == "fallido" and t.intentos == 3 and t.terminado_en is not None
    assert _leer(sesionador, tid).estado == "fallido"


def test_backoff_tiene_techo():
    assert backoff(1) == timedelta(seconds=30)
    assert backoff(4) == timedelta(seconds=240)
    assert backoff(50) == timedelta(hours=1)


def test_fallo_descarta_lo_que_escribio_el_manejador(sesionador, tipo_prueba):
    def _escribe_y_falla(db, t):
        db.add(Despacho(id="basura"))
        db.flush()
        raise RuntimeError("a medias")

    tipo_prueba("medias", _escribe_y_falla)
    with sesionador() as db:
        encolar(db, "medias", max_intentos=1, ejecutar_en=T0)
        db.commit()
    assert procesar_siguiente(sesionador, ahora=T0).estado == "fallido"
    with sesionador() as db:
        assert db.get(Despacho, "basura") is None


def test_tipo_sin_manejador_falla_sin_reintentar(sesionador):
    with sesionador() as db:
        encolar(db, "nadie.lo.conoce", max_intentos=5, ejecutar_en=T0)
        db.commit()
    t = procesar_siguiente(sesionador, ahora=T0)
    assert t.estado == "fallido" and "manejador" in t.error


# ── huérfanos ──


def test_corriendo_huerfano_vuelve_a_pendiente_y_corre(sesionador, tipo_prueba):
    tipo_prueba("lento", lambda db, t: {"intento": t.intentos})
    with sesionador() as db:
        t = encolar(db, "lento")
        t.estado, t.iniciado_en, t.intentos = "corriendo", T0 - timedelta(minutes=16), 1
        db.commit()
        tid = t.id
    hecho = procesar_siguiente(sesionador, ahora=T0)
    assert hecho.id == tid and hecho.estado == "hecho" and hecho.resultado == {"intento": 2}


def test_corriendo_reciente_no_se_toca(sesionador, tipo_prueba):
    tipo_prueba("lento", lambda db, t: {})
    with sesionador() as db:
        t = encolar(db, "lento")
        t.estado, t.iniciado_en = "corriendo", T0 - timedelta(minutes=5)
        db.commit()
        tid = t.id
    assert procesar_siguiente(sesionador, ahora=T0) is None
    assert _leer(sesionador, tid).estado == "corriendo"


def test_huerfano_sin_intentos_restantes_queda_fallido(sesionador):
    with sesionador() as db:
        t = encolar(db, "x", max_intentos=2)
        t.estado, t.iniciado_en, t.intentos = "corriendo", T0 - timedelta(hours=1), 2
        db.commit()
        tid = t.id
    procesar_siguiente(sesionador, ahora=T0)
    t = _leer(sesionador, tid)
    assert t.estado == "fallido" and "Huérfano" in t.error


def test_huerfano_recuperado_conserva_la_clave_unica(sesionador):
    """Vuelve a pendiente con su clave: un nuevo `encolar` no lo duplica."""
    with sesionador() as db:
        t = encolar(db, "x", clave_unica="k")
        t.estado, t.iniciado_en, t.intentos = "corriendo", T0 - timedelta(hours=1), 1
        db.commit()
        tid = t.id
    from app.trabajos import recuperar_huerfanos

    assert recuperar_huerfanos(sesionador, ahora=T0) == 1
    with sesionador() as db:
        assert encolar(db, "x", clave_unica="k").id == tid


# ── programación recurrente ──


def test_tarea_diaria_corre_a_la_hora_en_cdmx_y_no_repite(sesionador, tipo_prueba):
    """Diaria a las 09:00 CDMX (15:00 UTC en octubre): antes no, a la hora sí, una vez."""
    tipo_prueba("reporte", lambda db, t: {"ranura": t.carga["ranura"]})

    def _encolar(db, ranura):
        encolar(db, "reporte", {"ranura": ranura.isoformat()}, ejecutar_en=ranura,
                clave_unica=f"prog:reporte:{ranura.isoformat()}")

    tareas = [TareaRecurrente("reporte", _encolar, hora=time(9, 0))]
    # La primera vez reclama la ranura de AYER (el worker acaba de arrancar).
    antes = datetime(2026, 10, 19, 14, 59, tzinfo=UTC)
    assert revisar_programacion(sesionador, ahora=antes, tareas=tareas) == ["reporte"]
    assert revisar_programacion(sesionador, ahora=antes, tareas=tareas) == []

    a_la_hora = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)
    assert una_vuelta(sesionador, ahora=a_la_hora, tareas=tareas) == 2
    with sesionador() as db:
        ranuras = sorted(t.resultado["ranura"] for t in db.scalars(select(Trabajo)))
        assert ranuras[-1] == "2026-10-19T15:00:00+00:00"
        assert all(t.estado == "hecho" for t in db.scalars(select(Trabajo)))
    # Más tarde ese mismo día no se repite.
    assert una_vuelta(sesionador, ahora=a_la_hora + timedelta(hours=5), tareas=tareas) == 0


def test_reiniciar_el_worker_no_duplica(sesionador):
    """La última ejecución vive en la base: otra 'instancia' no vuelve a encolar."""
    llamadas: list[datetime] = []
    tareas = [
        TareaRecurrente("cada10", lambda db, r: llamadas.append(r), cada=timedelta(minutes=10))
    ]
    revisar_programacion(sesionador, ahora=T0, tareas=tareas)
    revisar_programacion(sesionador, ahora=T0 + timedelta(minutes=3), tareas=tareas)
    assert len(llamadas) == 1
    revisar_programacion(sesionador, ahora=T0 + timedelta(minutes=10), tareas=tareas)
    assert len(llamadas) == 2
    with sesionador() as db:
        assert db.get(EjecucionProgramada, "cada10").ultima_ejecucion == T0 + timedelta(minutes=10)


def test_tarea_que_falla_al_encolar_no_reclama_la_ranura(sesionador):
    intentos: list[int] = []

    def _rompe(db, ranura):
        intentos.append(1)
        raise RuntimeError("sin base")

    tareas = [TareaRecurrente("rota", _rompe, cada=timedelta(hours=1))]
    assert revisar_programacion(sesionador, ahora=T0, tareas=tareas) == []
    assert revisar_programacion(sesionador, ahora=T0, tareas=tareas) == []
    assert len(intentos) == 2


def test_tarea_recurrente_exige_cada_o_hora():
    with pytest.raises(ValueError):
        TareaRecurrente("mal", lambda db, r: None)
    with pytest.raises(ValueError):
        TareaRecurrente("mal", lambda db, r: None, cada=timedelta(hours=1), hora=time(3))


def test_worker_una_vez_corre_lo_pendiente(sesionador, tipo_prueba):
    tipo_prueba("eco", lambda db, t: {"eco": t.carga})
    with sesionador() as db:
        encolar(db, "eco", {"v": 1}, ejecutar_en=datetime(2020, 1, 1, tzinfo=UTC))
        db.commit()
    correr(sesionador, una_vez=True)
    with sesionador() as db:
        t = db.scalar(select(Trabajo).where(Trabajo.tipo == "eco"))
        assert t.estado == "hecho"


def test_purga_borra_terminados_viejos_y_conserva_fallidos(sesionador):
    import app.trabajos.manejadores  # noqa: F401 — registra los de sistema

    viejo = datetime(2020, 1, 1, tzinfo=UTC)
    with sesionador() as db:
        for estado in ("hecho", "cancelado", "fallido"):
            db.add(Trabajo(tipo="x", estado=estado, ejecutar_en=viejo, terminado_en=viejo))
        encolar(db, "mantenimiento.purgar_trabajos")
        db.commit()
    t = procesar_siguiente(sesionador)
    assert t.estado == "hecho" and t.resultado["borrados"] == 2
    with sesionador() as db:
        assert {x.estado for x in db.scalars(select(Trabajo))} == {"fallido", "hecho"}


# ── rutas /api/v1/trabajos ──


def _cliente(sesionador, despacho: str, clave: str) -> int:
    with sesionador() as db:
        if db.get(Despacho, despacho) is None:
            db.add(Despacho(id=despacho))
            db.flush()
        c = Cliente(despacho_id=despacho, clave=clave, nombre=clave.title())
        db.add(c)
        db.commit()
        return c.id


def test_ruta_encola_corre_y_muestra_resultado(api, sesionador):
    import app.trabajos.manejadores  # noqa: F401

    a = api("uid-a")
    a.get("/api/v1/trabajos")  # crea el despacho
    _cliente(sesionador, "uid-a", "taller")
    r = a.post("/api/v1/trabajos/clientes/taller/diagnostico", json={"fallar_intentos": 1})
    assert r.status_code == 201, r.text
    tid = r.json()["trabajo"]["id"]
    # La clave única: un segundo clic devuelve el mismo trabajo.
    assert a.post("/api/v1/trabajos/clientes/taller/diagnostico").json()["trabajo"]["id"] == tid

    primero = procesar_siguiente(sesionador)
    assert primero.estado == "pendiente" and "Falla de prueba" in primero.error
    procesar_siguiente(sesionador, ahora=primero.ejecutar_en)

    lista = a.get("/api/v1/trabajos", params={"cliente": "taller"}).json()["trabajos"]
    assert lista[0]["id"] == tid and lista[0]["estado"] == "hecho"
    assert lista[0]["resultado"] == {"empleados": 0, "intentos": 2}
    assert lista[0]["cliente"] == "taller"


def test_ruta_reintentar_y_cancelar(api, sesionador):
    a = api("uid-a")
    a.get("/api/v1/trabajos")
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        fallido = Trabajo(tipo="x", estado="fallido", despacho_id="uid-a", cliente_id=cid,
                          intentos=5, ejecutar_en=T0, error="boom")
        pendiente = Trabajo(tipo="x", estado="pendiente", despacho_id="uid-a", ejecutar_en=T0)
        db.add_all([fallido, pendiente])
        db.commit()
    r = a.post(f"/api/v1/trabajos/{fallido.id}/reintentar")
    assert r.status_code == 200 and r.json()["trabajo"]["estado"] == "pendiente"
    assert r.json()["trabajo"]["intentos"] == 0
    assert a.post(f"/api/v1/trabajos/{fallido.id}/reintentar").status_code == 409

    cancelado = a.post(f"/api/v1/trabajos/{pendiente.id}/cancelar").json()["trabajo"]
    assert cancelado["estado"] == "cancelado"
    assert a.post(f"/api/v1/trabajos/{pendiente.id}/cancelar").status_code == 409
    filtrados = a.get("/api/v1/trabajos", params={"estado": "cancelado"}).json()["trabajos"]
    assert [t["id"] for t in filtrados] == [pendiente.id]
    assert a.get("/api/v1/trabajos", params={"estado": "raro"}).status_code == 422


def test_ruta_multi_tenant(api, sesionador):
    a, b = api("uid-a"), api("uid-b")
    a.get("/api/v1/trabajos")
    b.get("/api/v1/trabajos")
    cid = _cliente(sesionador, "uid-a", "taller")
    with sesionador() as db:
        del_a = Trabajo(tipo="x", estado="fallido", despacho_id="uid-a", cliente_id=cid,
                        ejecutar_en=T0)
        sistema = Trabajo(tipo="x", estado="fallido", despacho_id=None, ejecutar_en=T0)
        db.add_all([del_a, sistema])
        db.commit()
    assert b.get("/api/v1/trabajos").json()["trabajos"] == []
    assert b.get(f"/api/v1/trabajos/{del_a.id}").status_code == 404
    assert b.post(f"/api/v1/trabajos/{del_a.id}/reintentar").status_code == 404
    assert b.post(f"/api/v1/trabajos/{del_a.id}/cancelar").status_code == 404
    assert b.get("/api/v1/trabajos", params={"cliente": "taller"}).status_code == 404
    assert b.post("/api/v1/trabajos/clientes/taller/diagnostico").status_code == 404
    # Ni el dueño ve los de sistema.
    assert [t["id"] for t in a.get("/api/v1/trabajos").json()["trabajos"]] == [del_a.id]
    assert a.get(f"/api/v1/trabajos/{sistema.id}").status_code == 404


def test_auxiliar_solo_ve_trabajos_de_sus_clientes(api, sesionador):
    from app.modelos.nucleo import AsignacionCliente, Usuario

    api("uid-a").get("/api/v1/trabajos")
    uno = _cliente(sesionador, "uid-a", "uno")
    dos = _cliente(sesionador, "uid-a", "dos")
    with sesionador() as db:
        db.add(Usuario(uid="aux", despacho_id="uid-a", rol="auxiliar"))
        db.flush()
        db.add(AsignacionCliente(usuario_uid="aux", cliente_id=uno))
        t1 = Trabajo(tipo="x", despacho_id="uid-a", cliente_id=uno, ejecutar_en=T0)
        t2 = Trabajo(tipo="x", despacho_id="uid-a", cliente_id=dos, ejecutar_en=T0)
        t3 = Trabajo(tipo="x", despacho_id="uid-a", cliente_id=None, ejecutar_en=T0)
        db.add_all([t1, t2, t3])
        db.commit()
    aux = api("aux")
    assert [t["id"] for t in aux.get("/api/v1/trabajos").json()["trabajos"]] == [t1.id]
    assert aux.get(f"/api/v1/trabajos/{t2.id}").status_code == 404
    assert aux.get(f"/api/v1/trabajos/{t3.id}").status_code == 404


def test_rutas_exigen_token(api):
    from fastapi.testclient import TestClient

    from app.main import app

    api()  # instala los overrides
    assert TestClient(app).get("/api/v1/trabajos").status_code == 401
