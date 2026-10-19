"""
P1-01: cliente de descarga masiva del SAT contra respuestas grabadas (sin red).

"Listo cuando": con respuestas del SAT grabadas, una solicitud de un mes termina con los XML
en la bóveda, y una solicitud atorada se reintenta sin duplicar.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.credenciales.certificados import abrir_llave
from app.credenciales.servicio import Firmante
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.sat_descarga import DescargaSatFalso, DescargaSatReal
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import AlertaDescargaSat, MetadataCfdiSat, SolicitudDescargaSat
from app.sat_descarga import servicio
from app.sat_descarga.servicio import Contexto, Pedido
from app.tenancy import asegurar_usuario
from tests.plan_p import certs_sat
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_COMPRADOR, RFC_PROVEEDOR, cfdi, uuid_n
from tests.plan_p.sat_simulado import Reloj, SatSimulado, zip_de

MARZO = Pedido("emitidos", "cfdi", datetime(2026, 3, 1), datetime(2026, 3, 31, 23, 59, 59),
               "todos")


@pytest.fixture(scope="module")
def firmante() -> Firmante:
    par = certs_sat.generar(rfc=RFC_CLIENTE)
    return Firmante(abrir_llave(par.key, par.password), par.cer, RFC_CLIENTE, par.numero,
                    "efirma")


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    return c


@pytest.fixture
def sat():
    return SatSimulado()


@pytest.fixture
def ctx(sat, firmante, monkeypatch):
    monkeypatch.setattr(servicio, "reloj", sat.reloj)
    real = DescargaSatReal(http=sat.cliente(), reloj=sat.reloj)
    return Contexto(real, firmante, AlmacenamientoMemoria())


def _mes(n: int, desde: int = 0, emitido: bool = True) -> dict[str, bytes]:
    return {
        f"{uuid_n(i)}.xml": cfdi(
            uuid_n(i), emisor=RFC_CLIENTE if emitido else RFC_PROVEEDOR,
            receptor=RFC_COMPRADOR if emitido else RFC_CLIENTE,
            fecha=f"2026-03-{(i % 28) + 1:02d}T10:00:00",
        )
        for i in range(desde, desde + n)
    }


def _hasta_terminar(db, s, ctx, sat, pasos=30):
    for _ in range(pasos):
        servicio.correr_hasta_esperar(db, s, ctx)
        db.commit()
        if s.estado in servicio.TERMINALES:
            return s
        sat.reloj.momento = max(sat.reloj.momento, s.proxima_verificacion or sat.reloj())
    return s


def _en_boveda(db, cliente) -> int:
    return db.scalar(select(func.count(Comprobante.id)).where(
        Comprobante.cliente_id == cliente.id))


# ── listo cuando ──


def test_solicitud_de_un_mes_termina_con_los_xml_en_la_boveda(db_sesion, cliente, ctx, sat):
    sat.paquetes_por_solicitud = [[zip_de(_mes(120)), zip_de(_mes(80, desde=120))]]
    sat.en_proceso = 2
    s, nueva = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    assert nueva

    _hasta_terminar(db_sesion, s, ctx, sat)

    assert s.estado == "terminada", s.mensaje
    assert (s.xml_importados, s.duplicados, s.rechazados) == (200, 0, 0)
    assert len(s.paquetes_procesados) == 2
    assert _en_boveda(db_sesion, cliente) == 200
    comp = db_sesion.scalar(select(Comprobante).where(Comprobante.uuid == uuid_n(5)))
    assert (comp.origen, comp.direccion) == ("sat", "emitido")
    # Una autenticación, una solicitud, 3 verificaciones (2 en proceso), 2 descargas.
    assert sat.contar("SolicitaDescargaEmitidos") == 1
    assert sat.contar("VerificaSolicitudDescarga") == 3
    assert sat.contar("Descargar") == 2


def test_solicitud_atorada_se_reintenta_sin_duplicar(db_sesion, cliente, ctx, sat):
    """En proceso ~30 horas: se verifica con backoff, avisa, y al terminar no duplica."""
    sat.paquetes_por_solicitud = [[zip_de(_mes(50))]]
    sat.en_proceso = 25
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    _hasta_terminar(db_sesion, s, ctx, sat, pasos=60)

    assert s.estado == "terminada"
    assert sat.contar("SolicitaDescargaEmitidos") == 1  # nunca se volvió a pedir
    assert s.veces_solicitada == 1
    assert s.xml_importados == 50 and _en_boveda(db_sesion, cliente) == 50
    # El backoff tiene techo de 2 h: ~30 h de espera con 25 verificaciones.
    assert sat.reloj() - datetime(2026, 10, 1, 12, 0, tzinfo=sat.reloj().tzinfo) > \
        timedelta(hours=24)
    alerta = db_sesion.scalar(select(AlertaDescargaSat).where(
        AlertaDescargaSat.tipo == "atorada"))
    assert alerta is not None and "en proceso" in alerta.mensaje

    # Pedir lo mismo otra vez: misma solicitud, nada nuevo al SAT.
    otra, nueva = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    assert (otra.id, nueva) == (s.id, False)
    servicio.correr_hasta_esperar(db_sesion, otra, ctx)
    assert sat.contar("SolicitaDescargaEmitidos") == 1


def test_atorada_mas_alla_del_tope_falla_con_mensaje(db_sesion, cliente, ctx, sat, monkeypatch):
    monkeypatch.setenv("FISCALITO_SAT_DIAS_MAX_ESPERA", "1")
    sat.en_proceso = 10_000
    sat.paquetes_por_solicitud = [[zip_de(_mes(1))]]
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    _hasta_terminar(db_sesion, s, ctx, sat, pasos=80)
    assert s.estado == "fallida" and "no terminó la solicitud en 1 días" in s.mensaje


def test_worker_que_muere_a_media_descarga_retoma_sin_duplicar(db_sesion, cliente, ctx, sat):
    sat.paquetes_por_solicitud = [[zip_de(_mes(30)), zip_de(_mes(30, desde=30))]]
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    original = ctx.sat.descargar
    llamadas = {"n": 0}

    def descargar_y_morir(f, pid, destino):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("se cayó el worker")
        return original(f, pid, destino)

    ctx.sat.descargar = descargar_y_morir
    with pytest.raises(RuntimeError):
        _hasta_terminar(db_sesion, s, ctx, sat)
    db_sesion.rollback()
    db_sesion.refresh(s)
    assert s.paquetes_procesados == [s.paquetes[0]]  # el primero quedó confirmado
    assert _en_boveda(db_sesion, cliente) == 30

    ctx.sat.descargar = original
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert s.estado == "terminada"
    assert _en_boveda(db_sesion, cliente) == 60
    # El worker murió ANTES de pedir el segundo; al retomar no se vuelve a bajar el primero
    # (el SAT sólo entrega dos veces cada paquete): una descarga por paquete.
    assert sat.contar("Descargar") == 2


def test_zip_guardado_antes_de_importar_y_retomado_sin_volver_a_descargar(
        db_sesion, cliente, ctx, sat, monkeypatch):
    """Revisión P1: si el proceso muere AL IMPORTAR, el paquete no se vuelve a pedir."""
    from app.boveda_cfdi import servicio as boveda

    sat.paquetes_por_solicitud = [[zip_de(_mes(10))]]
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    original = boveda.importar

    def importar_y_morir(*a, **k):
        raise RuntimeError("se cayó el worker importando")

    monkeypatch.setattr(boveda, "importar", importar_y_morir)
    with pytest.raises(RuntimeError):
        _hasta_terminar(db_sesion, s, ctx, sat)
    db_sesion.rollback()
    db_sesion.refresh(s)
    assert not s.paquetes_procesados and _en_boveda(db_sesion, cliente) == 0
    zips = [k for k in ctx.almacen.archivos if k.startswith(
        f"sat/paquetes/{cliente.despacho_id}/{cliente.id}/{s.id}/")]
    assert len(zips) == 1  # el ZIP quedó guardado ANTES de importar
    assert sat.contar("Descargar") == 1

    monkeypatch.setattr(boveda, "importar", original)
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert s.estado == "terminada" and _en_boveda(db_sesion, cliente) == 10
    assert sat.contar("Descargar") == 1  # se retomó del almacén


def test_bloqueo_de_fila_for_update_skip_locked():
    """Revisión P1: dos workers no avanzan la misma solicitud (Postgres)."""
    from sqlalchemy.dialects import postgresql, sqlite

    sql_pg = str(servicio.consulta_bloqueo(7).compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql_pg
    sql_lite = str(servicio.consulta_bloqueo(7).compile(dialect=sqlite.dialect()))
    assert "FOR UPDATE" not in sql_lite  # SQLite: sin bloqueo de fila, sigue igual


def test_solicitud_tomada_por_otro_worker_se_omite(db_sesion, cliente, monkeypatch):
    from app.modelos.trabajos import Trabajo
    from app.sat_descarga import trabajos as sat_trabajos

    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    monkeypatch.setattr(servicio, "bloquear", lambda db, sid: None)  # otro la tiene
    t = Trabajo(tipo="sat.descarga.avanzar", carga={"solicitud_id": s.id})
    assert sat_trabajos.avanzar_solicitud(db_sesion, t) == {
        "omitido": "otro worker la está procesando"}
    assert s.estado == "pendiente"
    monkeypatch.setattr(servicio, "bloquear", lambda db, sid: None)
    t2 = Trabajo(tipo="sat.descarga.avanzar", carga={"solicitud_id": 999_999})
    assert sat_trabajos.avanzar_solicitud(db_sesion, t2) == {"omitido": "solicitud borrada"}


def test_token_expirado_se_renueva(db_sesion, cliente, ctx, sat):
    sat.paquetes_por_solicitud = [[zip_de(_mes(3))]]
    sat.en_proceso = 1
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert sat.contar("Autentica") == 1
    sat.reloj.avanzar(minutes=10)  # el token de 5 minutos ya venció
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert s.estado == "terminada"
    assert sat.contar("Autentica") >= 2


def test_token_rechazado_por_el_sat_se_renueva_una_vez(db_sesion, cliente, ctx, sat):
    sat.paquetes_por_solicitud = [[zip_de(_mes(2))]]
    sat.rechazar_token_una_vez = True
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert s.estado in ("solicitada", "terminada")
    assert sat.contar("Autentica") == 2
    assert sat.contar("SolicitaDescargaEmitidos") == 2  # la primera rebotó por el token


def test_paquete_con_xml_ya_existentes_cuenta_duplicados(db_sesion, cliente, ctx, sat):
    import io

    from app.boveda_cfdi import servicio as boveda

    previos = _mes(10)
    boveda.importar(db_sesion, cliente, [("previos.zip", io.BytesIO(zip_de(previos)))],
                    ctx.almacen)
    sat.paquetes_por_solicitud = [[zip_de(_mes(25))]]  # 10 repetidos + 15 nuevos
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert (s.xml_importados, s.duplicados) == (15, 10)
    assert _en_boveda(db_sesion, cliente) == 25
    assert "15 XML nuevos" in s.mensaje and "10 ya existían" in s.mensaje


@pytest.mark.parametrize(("codigo", "estado", "texto"), [
    ("5002", "fallida", "agotaron las solicitudes de por vida"),
    ("5001", "fallida", "tercero no autorizado"),
    ("305", "fallida", "certificado"),
    ("5004", "sin_datos", "no encontró"),
])
def test_error_del_sat_con_mensaje_legible(db_sesion, cliente, ctx, sat, codigo, estado, texto):
    sat.codigo_solicitud = codigo
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert s.estado == estado
    assert s.codigo == codigo
    assert texto in s.mensaje.lower()


def test_error_no_controlado_404_se_reintenta_con_backoff(db_sesion, cliente, ctx, sat):
    sat.codigo_solicitud = "404"
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert (s.estado, s.intentos) == ("pendiente", 1)
    assert s.proxima_verificacion > sat.reloj()
    sat.codigo_solicitud = "5000"
    sat.paquetes_por_solicitud = [[zip_de(_mes(1))]]
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert s.estado == "terminada"


def test_5005_solicitud_duplicada_espera_y_no_falla(db_sesion, cliente, ctx, sat):
    sat.codigo_solicitud = "5005"
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert s.estado == "pendiente" and "ya hay una solicitud vigente" in s.mensaje.lower()
    assert s.proxima_verificacion - sat.reloj() >= timedelta(hours=1)


def test_tope_5003_parte_el_rango_en_dos(db_sesion, cliente, ctx, sat):
    sat.codigo_solicitud = "5003"
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert s.estado == "dividida"
    hijas = list(db_sesion.scalars(select(SolicitudDescargaSat).where(
        SolicitudDescargaSat.padre_id == s.id).order_by(SolicitudDescargaSat.fecha_inicial)))
    assert [(h.fecha_inicial.day, h.fecha_final.day) for h in hijas] == [(1, 16), (17, 31)]
    assert hijas[1].fecha_inicial == datetime(2026, 3, 17)


def test_solicitud_perdida_en_el_sat_se_pide_otra_vez_solo_una(db_sesion, cliente, ctx, sat):
    sat.paquetes_por_solicitud = [[zip_de(_mes(1))], [zip_de(_mes(1))]]
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)  # solicitada
    sat.codigo_verificacion = "5004"
    sat.reloj.avanzar(minutes=3)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    assert s.estado in ("pendiente", "solicitada")
    servicio.correr_hasta_esperar(db_sesion, s, ctx)
    sat.reloj.avanzar(minutes=3)
    servicio.correr_hasta_esperar(db_sesion, s, ctx)  # 5004 otra vez: ya no quedan
    assert s.veces_solicitada == 2
    assert s.estado == "fallida"
    assert "Ya se pidió 2 veces" in s.mensaje
    assert sat.contar("SolicitaDescargaEmitidos") == 2


def test_metadata_guarda_y_marca_cancelados_de_la_boveda(db_sesion, cliente, ctx, sat):
    import io

    from app.boveda_cfdi import servicio as boveda

    boveda.importar(db_sesion, cliente, [("a.zip", io.BytesIO(zip_de(_mes(2))))], ctx.almacen)
    encabezado = ("Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~"
                  "FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion")
    filas = [
        f"{uuid_n(0)}~{RFC_CLIENTE}~TALLER~{RFC_COMPRADOR}~COMPRADOR~SAT970701NN3~"
        "2026-03-01 10:00:00~2026-03-01 10:00:30~1160.00~I~1~",
        f"{uuid_n(1)}~{RFC_CLIENTE}~TALLER~{RFC_COMPRADOR}~COMPRADOR~SAT970701NN3~"
        "2026-03-02 10:00:00~2026-03-02 10:00:30~1160.00~I~0~2026-03-05 09:00:00",
        # Nombre con un LF suelto en un archivo CRLF: defecto conocido de los paquetes.
        f"{uuid_n(99)}~{RFC_PROVEEDOR}~PROVEEDOR\nPARTIDO~{RFC_CLIENTE}~TALLER~SAT970701NN3~"
        "2026-03-03 10:00:00~2026-03-03 10:00:30~500.50~E~1~",
    ]
    txt = ("\r\n".join([encabezado, *filas]) + "\r\n").encode()
    sat.paquetes_por_solicitud = [[zip_de({"meta_01.txt": txt})]]
    s, _ = servicio.crear_o_reusar(
        db_sesion, cliente, Pedido("emitidos", "metadata", MARZO.fecha_inicial,
                                   MARZO.fecha_final))
    _hasta_terminar(db_sesion, s, ctx, sat)
    assert s.estado == "terminada" and s.metadata_registros == 3
    meta = {m.uuid: m for m in db_sesion.scalars(select(MetadataCfdiSat))}
    assert meta[uuid_n(1)].estatus == "cancelado"
    assert meta[uuid_n(1)].fecha_cancelacion == datetime(2026, 3, 5, 9)
    assert meta[uuid_n(99)].nombre_emisor == "PROVEEDORPARTIDO"
    assert str(meta[uuid_n(99)].monto) == "500.50"
    assert meta[uuid_n(99)].direccion == "recibido"
    estatus = dict(db_sesion.execute(select(Comprobante.uuid, Comprobante.estatus_sat)).all())
    assert estatus == {uuid_n(0): "vigente", uuid_n(1): "cancelado"}


def test_falso_no_toca_la_red_y_sigue_el_mismo_ciclo(db_sesion, cliente, firmante, monkeypatch):
    reloj = Reloj()
    monkeypatch.setattr(servicio, "reloj", reloj)
    falso = DescargaSatFalso(al_solicitar=lambda p: [zip_de(_mes(4))], en_proceso=1)
    ctx = Contexto(falso, firmante, AlmacenamientoMemoria())
    s, _ = servicio.crear_o_reusar(db_sesion, cliente, MARZO)
    for _ in range(5):
        servicio.correr_hasta_esperar(db_sesion, s, ctx)
        reloj.avanzar(minutes=5)
    assert s.estado == "terminada" and s.xml_importados == 4
    assert [op for op, _ in falso.llamadas] == ["solicitar", "verificar", "verificar",
                                                "descargar"]


def test_ventanas_por_mes():
    v = servicio.ventanas_por_mes(datetime(2026, 1, 15).date(), datetime(2026, 3, 2).date())
    assert [(a.isoformat(), b.isoformat()) for a, b in v] == [
        ("2026-01-15T00:00:00", "2026-01-31T23:59:59"),
        ("2026-02-01T00:00:00", "2026-02-28T23:59:59"),
        ("2026-03-01T00:00:00", "2026-03-02T23:59:59"),
    ]
