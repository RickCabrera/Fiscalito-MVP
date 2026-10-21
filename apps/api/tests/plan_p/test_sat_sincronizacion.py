"""
P1-02: sincronización diaria, descarga por rango, histórica y bitácora del SAT.

"Listo cuando": el programador lanza la descarga diaria de cada cliente con e.firma y el
calendario marca cada día como completo, en proceso o fallido.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import settings
from app.credenciales import cifrado
from app.credenciales import servicio as credenciales
from app.integraciones import registro
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.sat_descarga import DescargaSatFalso
from app.modelos.nucleo import AsignacionCliente, Cliente, Usuario
from app.modelos.sat_descarga import AlertaDescargaSat, ConfigDescargaSat, SolicitudDescargaSat
from app.modelos.trabajos import Trabajo
from app.sat_descarga import servicio, sincronizacion
from app.tenancy import asegurar_usuario
from app.trabajos import procesar_siguiente
from app.trabajos.manejadores import cargar_manejadores
from app.trabajos.programacion import revisar_programacion
from tests.plan_p import certs_sat
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_COMPRADOR, cfdi, uuid_n
from tests.plan_p.sat_simulado import Reloj, zip_de

cargar_manejadores()

# 2026-10-02 02:30 en la Ciudad de México (UTC-6).
DESPUES_DE_LAS_DOS = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    cifrado.olvidar_llave_efimera()
    almacen = AlmacenamientoMemoria()
    falso = DescargaSatFalso()
    monkeypatch.setattr(servicio, "obtener_cliente_sat", lambda: falso)
    monkeypatch.setattr(servicio, "obtener_almacenamiento", lambda: almacen)
    registro.limpiar_cache()
    yield falso
    cifrado.olvidar_llave_efimera()


def _alta(sesionador, uid: str, clave: str, rfc: str = RFC_CLIENTE, efirma: bool = True,
          activa: bool = True) -> int:
    with sesionador() as db:
        asegurar_usuario(db, uid)
        c = Cliente(despacho_id=uid, clave=clave, nombre=clave.title(), rfc=rfc)
        db.add(c)
        db.flush()
        if efirma:
            par = certs_sat.generar(rfc=rfc)
            credenciales.guardar(db, c, "efirma", par.cer, par.key, par.password, uid)
        if activa:
            db.add(ConfigDescargaSat(cliente_id=c.id, activa=True, emitidos=True,
                                     recibidos=False, metadata_=False, cancelados=False,
                                     hora="02:00"))
        db.commit()
        return c.id


def _correr_cola(sesionador, momento, vueltas=30):
    for _ in range(vueltas):
        if procesar_siguiente(sesionador, ahora=momento) is None:
            return


def _xml_del_dia(dia: date, n: int, desde: int = 0) -> dict[str, bytes]:
    return {f"{uuid_n(i)}.xml": cfdi(uuid_n(i), emisor=RFC_CLIENTE, receptor=RFC_COMPRADOR,
                                     fecha=f"{dia.isoformat()}T11:00:00")
            for i in range(desde, desde + n)}


# ── diaria ──


def test_programador_lanza_la_diaria_de_cada_cliente_con_efirma(sesionador, entorno,
                                                                 monkeypatch):
    con = _alta(sesionador, "uid-a", "taller")
    sin = _alta(sesionador, "uid-b", "panaderia", efirma=False)
    apagado = _alta(sesionador, "uid-c", "farmacia", activa=False)
    reloj = Reloj(DESPUES_DE_LAS_DOS)
    monkeypatch.setattr(servicio, "reloj", reloj)
    ayer = date(2026, 10, 1)
    entorno.al_solicitar = lambda p: [zip_de(_xml_del_dia(ayer, 3))]

    # Antes de las 02:00 no se encola nada.
    revisar_programacion(sesionador, ahora=datetime(2026, 10, 2, 7, 50, tzinfo=UTC))
    with sesionador() as db:
        assert db.scalar(select(Trabajo).where(Trabajo.tipo == "sat.descarga.rango")) is None

    assert "sat_diaria" in revisar_programacion(sesionador, ahora=DESPUES_DE_LAS_DOS)
    _correr_cola(sesionador, DESPUES_DE_LAS_DOS)
    with sesionador() as db:
        rangos = list(db.scalars(select(Trabajo).where(Trabajo.tipo == "sat.descarga.rango")))
        assert [t.cliente_id for t in rangos] == [con]
        assert rangos[0].clave_unica == f"sat.diaria:{con}:2026-10-01"
        sol = db.scalar(select(SolicitudDescargaSat).where(
            SolicitudDescargaSat.cliente_id == con))
        assert (sol.fecha_inicial, sol.fecha_final) == (
            datetime(2026, 10, 1), datetime(2026, 10, 1, 23, 59, 59))
        assert sol.origen == "diaria" and sol.estado in ("solicitada", "en_proceso",
                                                          "terminada")
        # Sin e.firma: pausada con alerta consultable. Apagado: nada.
        cfg = db.scalar(select(ConfigDescargaSat).where(ConfigDescargaSat.cliente_id == sin))
        assert cfg.pausada_por == "efirma"
        alerta = db.scalar(select(AlertaDescargaSat).where(AlertaDescargaSat.cliente_id == sin))
        assert alerta.tipo == "sin_efirma" and "e.firma" in alerta.mensaje
        assert db.scalar(select(SolicitudDescargaSat).where(
            SolicitudDescargaSat.cliente_id.in_([sin, apagado]))) is None

    # La verificación se reprogramó: al pasar el tiempo la cola la corre sola y termina.
    for minutos in (5, 15, 40):
        momento = DESPUES_DE_LAS_DOS + timedelta(minutes=minutos)
        reloj.momento = momento
        _correr_cola(sesionador, momento)
    with sesionador() as db:
        sol = db.scalar(select(SolicitudDescargaSat).where(
            SolicitudDescargaSat.cliente_id == con))
        assert sol.estado == "terminada" and sol.xml_importados == 3

    # Otra vuelta el mismo día no vuelve a encolar.
    revisar_programacion(sesionador, ahora=DESPUES_DE_LAS_DOS + timedelta(minutes=20))
    _correr_cola(sesionador, DESPUES_DE_LAS_DOS + timedelta(minutes=20))
    with sesionador() as db:
        assert len(list(db.scalars(select(Trabajo).where(
            Trabajo.tipo == "sat.descarga.rango")))) == 1


def test_efirma_nueva_reanuda_la_pausa(sesionador):
    cid = _alta(sesionador, "uid-a", "taller", efirma=False)
    with sesionador() as db:
        sincronizacion.encolar_diarias(db, DESPUES_DE_LAS_DOS)
        db.commit()
        par = certs_sat.generar(rfc=RFC_CLIENTE)
        c = db.get(Cliente, cid)
        credenciales.guardar(db, c, "efirma", par.cer, par.key, par.password, "uid-a")
        assert sincronizacion.encolar_diarias(db, DESPUES_DE_LAS_DOS) == [cid]
        cfg = db.scalar(select(ConfigDescargaSat).where(ConfigDescargaSat.cliente_id == cid))
        assert cfg.pausada_por == ""
        assert all(a.resuelta for a in db.scalars(select(AlertaDescargaSat)))


# ── bitácora ──


def test_bitacora_marca_completo_en_proceso_fallido_y_sin_movimientos(sesionador, entorno,
                                                                      monkeypatch):
    cid = _alta(sesionador, "uid-a", "taller")
    reloj = Reloj(datetime(2026, 10, 2, 12, tzinfo=UTC))
    monkeypatch.setattr(servicio, "reloj", reloj)
    with sesionador() as db:
        c = db.get(Cliente, cid)
        sel = sincronizacion.Seleccion(emitidos=True, recibidos=False, metadata=False,
                                       cancelados=False)

        def dia(d: int):
            return (servicio.inicio_dia(date(2026, 9, d)), servicio.fin_dia(date(2026, 9, d)))

        completo = sincronizacion.crear_rango(db, c, *dia(1), sel, "manual")[0]
        en_proceso = sincronizacion.crear_rango(db, c, *dia(2), sel, "manual")[0]
        fallido = sincronizacion.crear_rango(db, c, *dia(3), sel, "manual")[0]
        vacio = sincronizacion.crear_rango(db, c, *dia(4), sel, "manual")[0]
        completo.estado, completo.xml_importados = "terminada", 2
        en_proceso.estado = "en_proceso"
        fallido.estado, fallido.mensaje = "fallida", "El SAT dice que la e.firma está revocada."
        vacio.estado = "sin_datos"
        import io

        from app.boveda_cfdi import servicio as boveda

        boveda.importar(db, c, [("x.zip", io.BytesIO(zip_de(_xml_del_dia(date(2026, 9, 1),
                                                                         2))))],
                        servicio.obtener_almacenamiento())
        db.commit()
        dias = {d["fecha"]: d for d in sincronizacion.bitacora(db, c, 2026, 9)}
    assert len(dias) == 30
    assert dias["2026-09-01"]["estado"] == "completo" and dias["2026-09-01"]["emitidos"] == 2
    assert dias["2026-09-02"]["estado"] == "en_proceso"
    assert dias["2026-09-03"]["estado"] == "fallido"
    assert "revocada" in dias["2026-09-03"]["mensaje"]
    assert dias["2026-09-04"]["estado"] == "sin_movimientos"
    assert dias["2026-09-05"]["estado"] == "no_solicitado"


def test_mes_partido_por_5003_la_bitacora_mira_a_las_hijas(sesionador, entorno, monkeypatch):
    cid = _alta(sesionador, "uid-a", "taller")
    monkeypatch.setattr(servicio, "reloj", Reloj(datetime(2026, 10, 2, 12, tzinfo=UTC)))
    with sesionador() as db:
        c = db.get(Cliente, cid)
        p = servicio.Pedido("emitidos", "cfdi", datetime(2026, 9, 1),
                            datetime(2026, 9, 30, 23, 59, 59))
        s, _ = servicio.crear_o_reusar(db, c, p)
        entorno.codigo_solicitud = "5003"
        ctx = servicio.Contexto(entorno, credenciales.obtener_firmante(db, c, "efirma"),
                                AlmacenamientoMemoria())
        servicio.avanzar(db, s, ctx)
        hijas = list(db.scalars(select(SolicitudDescargaSat).where(
            SolicitudDescargaSat.padre_id == s.id)))
        hijas[0].estado = "terminada"
        db.commit()
        dias = {d["fecha"]: d["estado"] for d in sincronizacion.bitacora(db, c, 2026, 9)}
    assert {dias[f"2026-09-{d:02d}"] for d in range(1, 16)} == {"completo"}
    assert {dias[f"2026-09-{d:02d}"] for d in range(16, 31)} == {"en_proceso"}


# ── rutas ──


def test_rutas_config_descargar_historica_solicitudes_bitacora(api, sesionador, entorno):
    _alta(sesionador, "uid-a", "taller", activa=False)
    a = api("uid-a")
    r = a.get("/api/v1/sat/clientes/taller/config")
    assert r.status_code == 200
    assert r.json()["config"]["hora"] == "02:00" and r.json()["config"]["activa"] is False
    assert r.json()["efirma"]["vigente"] is True

    r = a.put("/api/v1/sat/clientes/taller/config",
              json={"activa": True, "recibidos": False, "hora": "03:15", "desde": "2026-01-01"})
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert (cfg["activa"], cfg["recibidos"], cfg["hora"], cfg["desde"]) == (
        True, False, "03:15", "2026-01-01")
    assert a.put("/api/v1/sat/clientes/taller/config", json={"hora": "25:00"}).status_code \
        == 422

    r = a.post("/api/v1/sat/clientes/taller/descargar",
               json={"desde": "2026-08-20", "hasta": "2026-09-10"})
    assert r.status_code == 200, r.text
    assert [(e["inicio"], e["fin"]) for e in r.json()["encolados"]] == [
        ("2026-08-20", "2026-08-31"), ("2026-09-01", "2026-09-10")]
    # Pedirlo otra vez no duplica trabajos vivos.
    r2 = a.post("/api/v1/sat/clientes/taller/descargar",
                json={"desde": "2026-08-20", "hasta": "2026-09-10"})
    assert [e["trabajo_id"] for e in r2.json()["encolados"]] == \
        [e["trabajo_id"] for e in r.json()["encolados"]]

    r = a.post("/api/v1/sat/clientes/taller/historica",
               json={"desde": "2026-01-01", "hasta": "2026-06-30"})
    assert r.status_code == 200 and len(r.json()["encolados"]) == 6

    _correr_cola(sesionador, datetime.now(UTC), vueltas=60)
    r = a.get("/api/v1/sat/clientes/taller/solicitudes?por_pagina=5")
    assert r.status_code == 200
    body = r.json()
    # 8 meses × (emitidos CFDI + metadata de emitidos), por la config (recibidos apagado).
    assert body["total"] == 16 and len(body["solicitudes"]) == 5
    assert {s["direccion"] for s in body["solicitudes"]} == {"emitidos"}

    r = a.get("/api/v1/sat/clientes/taller/bitacora?anio=2026&mes=9")
    assert r.status_code == 200
    dias = r.json()["dias"]
    assert len(dias) == 30
    assert dias[0]["estado"] in ("sin_movimientos", "en_proceso", "completo")
    assert dias[15]["estado"] == "no_solicitado"


def test_descargar_sin_efirma_es_409_con_mensaje(api, sesionador):
    _alta(sesionador, "uid-a", "taller", efirma=False)
    r = api("uid-a").post("/api/v1/sat/clientes/taller/descargar",
                          json={"desde": "2026-09-01", "hasta": "2026-09-02"})
    assert r.status_code == 409
    assert "e.firma" in r.json()["error"]


def test_rango_invalido_422(api, sesionador):
    _alta(sesionador, "uid-a", "taller")
    a = api("uid-a")
    assert a.post("/api/v1/sat/clientes/taller/descargar",
                  json={"desde": "2026-09-10", "hasta": "2026-09-01"}).status_code == 422
    assert a.post("/api/v1/sat/clientes/taller/historica",
                  json={"desde": "2015-01-01", "hasta": "2026-01-01"}).status_code == 422


def test_multi_tenant_despacho_b_no_ve_a(api, sesionador):
    _alta(sesionador, "uid-a", "taller")
    a, b = api("uid-a"), api("uid-b")
    assert a.post("/api/v1/sat/clientes/taller/descargar",
                  json={"desde": "2026-09-01", "hasta": "2026-09-02"}).status_code == 200
    for metodo, ruta, cuerpo in [
        ("get", "/config", None), ("put", "/config", {"activa": True}),
        ("post", "/descargar", {"desde": "2026-09-01", "hasta": "2026-09-02"}),
        ("post", "/historica", {"desde": "2026-01-01"}),
        ("get", "/solicitudes", None), ("get", "/bitacora?anio=2026&mes=9", None),
    ]:
        url = f"/api/v1/sat/clientes/taller{ruta}"
        r = getattr(b, metodo)(url, json=cuerpo) if cuerpo else getattr(b, metodo)(url)
        assert r.status_code == 404, (metodo, ruta, r.status_code)


def test_auxiliar_lee_pero_no_escribe(api, sesionador):
    cid = _alta(sesionador, "uid-a", "taller")
    with sesionador() as db:
        db.add(Usuario(uid="aux", despacho_id="uid-a", rol="auxiliar"))
        db.flush()
        db.add(AsignacionCliente(usuario_uid="aux", cliente_id=cid))
        db.commit()
    aux = api("aux")
    assert aux.get("/api/v1/sat/clientes/taller/config").status_code == 200
    assert aux.get("/api/v1/sat/clientes/taller/bitacora?anio=2026&mes=9").status_code == 200
    assert aux.put("/api/v1/sat/clientes/taller/config", json={"activa": True}).status_code \
        == 403
    assert aux.post("/api/v1/sat/clientes/taller/descargar",
                    json={"desde": "2026-09-01", "hasta": "2026-09-02"}).status_code == 403


def test_rutas_exigen_token(api):
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/v1/sat/clientes/taller/config").status_code == 401


def test_red_de_seguridad_recoge_solicitudes_sin_trabajo_y_no_duplica(sesionador, monkeypatch):
    from app.sat_descarga import trabajos as sat_trabajos

    cid = _alta(sesionador, "uid-a", "taller")
    monkeypatch.setattr(servicio, "reloj", Reloj(datetime(2026, 10, 2, 12, tzinfo=UTC)))
    with sesionador() as db:
        c = db.get(Cliente, cid)
        huerfana, _ = servicio.crear_o_reusar(db, c, servicio.Pedido(
            "emitidos", "cfdi", datetime(2026, 9, 1), datetime(2026, 9, 1, 23, 59, 59)))
        db.commit()
        momento = datetime(2026, 10, 2, 13, tzinfo=UTC)
        assert sat_trabajos._recoger_pendientes(db, momento) == [huerfana.id]
        db.commit()
        sat_trabajos._recoger_pendientes(db, momento + timedelta(minutes=30))
        db.commit()
        vivos = list(db.scalars(select(Trabajo).where(Trabajo.tipo == "sat.descarga.avanzar")))
        assert len(vivos) == 1
