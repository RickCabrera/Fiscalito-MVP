"""
P0-02: autenticación en todo `/api/v1`, aislamiento entre despachos y límites (429).

El test central recorre TODAS las rutas que publica la app real y exige 401 sin token,
salvo la lista blanca `RUTAS_PUBLICAS`. Un router montado sin la dependencia —o una ruta
nueva que se cuele— sale en rojo aquí el mismo día, con su path en el mensaje.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.acceso import llm as acceso_llm
from app.acceso.dependencias import RUTAS_PUBLICAS
from app.acceso.limitador import LimitadorEnMemoria
from app.asistencia.almacen import almacen, llave_almacen
from app.exceptions import LimiteExcedido
from app.main import app
from app.modelos.acceso import ConsumoLLM, TokenDispositivo
from app.modelos.nucleo import Cliente, Despacho

EVENTOS = "/api/v1/asistencia/eventos"
TOKENS = "/api/v1/asistencia/tokens"
CALENDARIO = "/api/v1/calendario"
CUERPO_CALENDARIO = {"contributor_type": "independiente", "regimen": "626", "rfc": "CAUA030101ABC"}
COMPARAR = "/api/v1/comparar-regimenes"
CHECADA = {
    "AcsEvent": {
        "InfoList": [
            {
                "major": 5,
                "minor": 75,
                "time": "2026-09-01T08:02:11-06:00",
                "employeeNoString": "7",
                "attendanceStatus": "checkIn",
                "serialNo": 575,
            }
        ]
    }
}


def _rutas_v1() -> list[tuple[str, str]]:
    """
    (método, path) de cada operación bajo /api/v1 de la app real.

    Se lee del OpenAPI y no de `app.routes`: en starlette 1.x `route.methods` dejó de ser
    legible como antes y el recorrido salía VACÍO (mismo episodio que documenta
    `scripts/exportar_rutas.py`). Un recorrido vacío es un verde falso; por eso existe
    `test_la_app_publica_suficientes_rutas`.
    """
    salida = set()
    for path, operaciones in app.openapi()["paths"].items():
        if path.startswith("/api/v1"):
            for metodo in operaciones:
                if metodo.upper() not in {"HEAD", "OPTIONS", "PARAMETERS"}:
                    salida.add((metodo.upper(), path))
    return sorted(salida)


RUTAS_PROTEGIDAS = [r for r in _rutas_v1() if r not in RUTAS_PUBLICAS]


def _concreto(path: str) -> str:
    """`/clientes/{clave}/cfdi/{uuid}` → `/clientes/x/cfdi/x` (1 para los ids enteros)."""
    return re.sub(r"\{(\w+)\}", lambda m: "1" if m.group(1).endswith("_id") else "x", path)


@pytest.fixture(autouse=True)
def _almacen_limpio():
    almacen.reset()
    yield
    almacen.reset()


# ─────────────────────────────────────────────────────────────
# 401 en todo /api/v1
# ─────────────────────────────────────────────────────────────


class TestTodoV1ExigeSesion:
    def test_la_app_publica_suficientes_rutas(self):
        """Guarda contra el falso verde: un recorrido de cero rutas no prueba nada."""
        assert len(RUTAS_PROTEGIDAS) >= 40

    @pytest.mark.parametrize(("metodo", "path"), RUTAS_PROTEGIDAS)
    def test_sin_token_es_401(self, api, metodo, path):
        """`api` instala la DB en memoria; el cliente de aquí NO lleva encabezado."""
        r = TestClient(app).request(metodo, _concreto(path))
        assert r.status_code == 401, (
            f"{metodo} {path} respondió {r.status_code} sin token. Todo /api/v1 exige sesión "
            "(P0-02): móntalo con `dependencies=PROTEGIDO` en app/main.py o decláralo en "
            "app/acceso/dependencias.RUTAS_PUBLICAS con su propia verificación."
        )
        assert r.json()["exito"] is False

    @pytest.mark.parametrize(("metodo", "path"), RUTAS_PROTEGIDAS[:5])
    def test_un_token_mal_formado_tambien_es_401(self, api, metodo, path):
        r = TestClient(app).request(
            metodo, _concreto(path), headers={"Authorization": "Basic abc"}
        )
        assert r.status_code == 401

    def test_la_lista_blanca_solo_nombra_rutas_que_existen(self):
        """Una excepción a la auth que apunta a una ruta que ya no existe es una trampa."""
        assert set(RUTAS_PUBLICAS) <= set(_rutas_v1())

    def test_health_sigue_abierto(self):
        cliente = TestClient(app)
        assert cliente.get("/health").status_code == 200
        assert cliente.get("/health/integraciones").status_code == 200

    def test_el_push_sin_ninguna_credencial_es_401(self, api):
        r = TestClient(app).post(EVENTOS, json=CHECADA)
        assert r.status_code == 401
        assert "token de dispositivo" in r.json()["error"]

    def test_con_sesion_un_calculo_sigue_igual(self, api):
        """Los endpoints de cálculo reciben los datos en el cuerpo y siguen funcionando."""
        r = api("uid-a").post(CALENDARIO, json=CUERPO_CALENDARIO)
        assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Multi-tenant: 404 (nunca 403) para lo de otro despacho
# ─────────────────────────────────────────────────────────────


class TestOtroDespacho:
    def _cliente_de_a(self, sesionador) -> None:
        with sesionador() as db:
            db.add(Despacho(id="uid-a"))
            db.flush()
            db.add(Cliente(despacho_id="uid-a", clave="taller-a", nombre="Taller A"))
            db.commit()

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/boveda/clientes/taller-a/cfdi",
            "/api/v1/boveda/clientes/taller-a/resumen",
            "/api/v1/clientes/taller-a/credenciales",
        ],
    )
    def test_un_cliente_de_otro_despacho_es_404(self, api, sesionador, path):
        self._cliente_de_a(sesionador)
        api("uid-a")  # A existe
        assert api("uid-a").get(path).status_code == 200
        r = api("uid-b").get(path)
        assert r.status_code == 404, r.text
        assert "taller-a" in r.json()["error"]

    def test_las_checadas_de_un_despacho_no_se_ven_en_otro(self, api):
        """Mismo cliente del catálogo (`taller`), dos despachos: almacenes separados."""
        a, b = api("uid-a"), api("uid-b")
        assert a.post(EVENTOS, params={"cliente": "taller"}, json=CHECADA).status_code == 200
        assert len(a.get(EVENTOS, params={"cliente": "taller"}).json()["eventos"]) == 1
        assert b.get(EVENTOS, params={"cliente": "taller"}).json()["eventos"] == []

    def test_cerrar_periodo_de_otro_despacho_no_ve_sus_checadas(self, api):
        api("uid-a").post(EVENTOS, params={"cliente": "taller"}, json=CHECADA)
        cuerpo = {
            "cliente": "taller",
            "empleados": ["7"],
            "periodo": {"inicio": "2026-09-01", "fin": "2026-09-01"},
        }
        de_a = api("uid-a").post("/api/v1/asistencia/cerrar-periodo", json=cuerpo).json()
        de_b = api("uid-b").post("/api/v1/asistencia/cerrar-periodo", json=cuerpo).json()
        assert de_a["incidencias"][0]["dias_trabajados"] == 1
        assert de_b["incidencias"][0]["dias_trabajados"] == 0


# ─────────────────────────────────────────────────────────────
# Token de dispositivo
# ─────────────────────────────────────────────────────────────


class TestTokenDeDispositivo:
    def _emitir(self, api, uid="uid-a", cliente="taller") -> dict:
        r = api(uid).post(TOKENS, json={"cliente": cliente, "etiqueta": "Entrada"})
        assert r.status_code == 201, r.text
        return r.json()

    def test_el_checador_empuja_con_su_token_y_cae_en_su_despacho(self, api):
        token = self._emitir(api)["token"]
        assert token.startswith("fdt_")
        r = TestClient(app).post(EVENTOS, params={"token": token}, json=CHECADA)
        assert r.status_code == 200, r.text
        assert r.json()["cliente"] == "taller"
        assert almacen.total(llave_almacen("uid-a", "taller")) == 1
        # Lo ve el despacho dueño, no otro.
        assert len(api("uid-a").get(EVENTOS, params={"cliente": "taller"}).json()["eventos"])
        assert api("uid-b").get(EVENTOS, params={"cliente": "taller"}).json()["eventos"] == []

    def test_tambien_por_encabezado(self, api):
        token = self._emitir(api)["token"]
        r = TestClient(app).post(EVENTOS, headers={"X-Token-Dispositivo": token}, json=CHECADA)
        assert r.status_code == 200

    def test_multipart_con_token_como_lo_manda_el_aparato(self, api):
        import json

        token = self._emitir(api)["token"]
        r = TestClient(app).post(
            EVENTOS,
            params={"token": token},
            data={"event_log": json.dumps(CHECADA)},
            files={"Picture": ("rostro.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
        )
        assert r.status_code == 200, r.text

    def test_un_token_inventado_es_401(self, api):
        r = TestClient(app).post(EVENTOS, params={"token": "fdt_inventado"}, json=CHECADA)
        assert r.status_code == 401

    def test_el_token_no_puede_mandar_checadas_de_otro_cliente(self, api):
        token = self._emitir(api)["token"]
        r = TestClient(app).post(
            EVENTOS, params={"token": token, "cliente": "cafeteria"}, json=CHECADA
        )
        assert r.status_code == 403
        assert almacen.total(llave_almacen("uid-a", "cafeteria")) == 0

    def test_revocado_deja_de_servir_en_el_acto(self, api):
        emitido = self._emitir(api)
        borrar = api("uid-a").delete(f"{TOKENS}/{emitido['registro']['id']}")
        assert borrar.status_code == 200
        r = TestClient(app).post(EVENTOS, params={"token": emitido["token"]}, json=CHECADA)
        assert r.status_code == 401

    def test_solo_se_guarda_el_hash(self, api, sesionador):
        token = self._emitir(api)["token"]
        with sesionador() as db:
            registro = db.scalar(select(TokenDispositivo))
            assert registro.hash_token != token
            assert token not in registro.hash_token
            assert registro.prefijo == token[:12]

    def test_el_listado_no_trae_el_secreto(self, api):
        token = self._emitir(api)["token"]
        cuerpo = api("uid-a").get(TOKENS).json()
        assert len(cuerpo["tokens"]) == 1
        assert token not in str(cuerpo)

    def test_otro_despacho_no_lista_ni_revoca(self, api):
        emitido = self._emitir(api)
        assert api("uid-b").get(TOKENS).json()["tokens"] == []
        r = api("uid-b").delete(f"{TOKENS}/{emitido['registro']['id']}")
        assert r.status_code == 404

    def test_a_un_cliente_de_otro_despacho_no_se_le_emite(self, api, sesionador):
        with sesionador() as db:
            db.add(Despacho(id="uid-a"))
            db.flush()
            db.add(Cliente(despacho_id="uid-a", clave="taller-a"))
            db.commit()
        assert api("uid-a").post(TOKENS, json={"cliente": "taller-a"}).status_code == 201
        assert api("uid-b").post(TOKENS, json={"cliente": "taller-a"}).status_code == 404

    def test_un_auxiliar_no_emite_tokens(self, api, sesionador):
        from app.modelos.nucleo import Usuario

        with sesionador() as db:
            db.add(Despacho(id="uid-a"))
            db.flush()
            db.add(Usuario(uid="uid-aux", despacho_id="uid-a", rol="auxiliar"))
            db.commit()
        assert api("uid-aux").post(TOKENS, json={"cliente": "taller"}).status_code == 403


# ─────────────────────────────────────────────────────────────
# 429: límite por usuario y por LLM, tope diario por despacho
# ─────────────────────────────────────────────────────────────


class TestLimites:
    def test_dentro_del_limite_es_200_y_al_excederlo_429_con_retry_after(
        self, api, monkeypatch
    ):
        monkeypatch.setenv("FISCALITO_RATE_LIMIT_POR_MINUTO", "3")
        cliente = api("uid-a")
        for _ in range(3):
            assert cliente.post(CALENDARIO, json=CUERPO_CALENDARIO).status_code == 200
        r = cliente.post(CALENDARIO, json=CUERPO_CALENDARIO)
        assert r.status_code == 429
        assert r.json()["exito"] is False
        assert 1 <= int(r.headers["Retry-After"]) <= 60

    def test_el_limite_es_por_usuario(self, api, monkeypatch):
        monkeypatch.setenv("FISCALITO_RATE_LIMIT_POR_MINUTO", "1")
        assert api("uid-a").post(CALENDARIO, json=CUERPO_CALENDARIO).status_code == 200
        assert api("uid-a").post(CALENDARIO, json=CUERPO_CALENDARIO).status_code == 429
        assert api("uid-b").post(CALENDARIO, json=CUERPO_CALENDARIO).status_code == 200

    def test_el_limite_de_llm_es_mas_estricto_y_no_frena_el_calculo(self, api, monkeypatch):
        """Con el cupo de LLM agotado, pedir la explicación es 429; el cálculo pelón no."""
        monkeypatch.setenv("FISCALITO_RATE_LIMIT_LLM_POR_MINUTO", "2")
        _sin_red(monkeypatch)
        cuerpo = {"ingresos_mensuales_estimados": 30000, "gastos_mensuales_estimados": 5000}
        cliente = api("uid-a")
        for _ in range(2):
            r = cliente.post(COMPARAR, json={**cuerpo, "incluir_explicacion": True})
            assert r.status_code == 200, r.text
        r = cliente.post(COMPARAR, json={**cuerpo, "incluir_explicacion": True})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        sin_llm = {**cuerpo, "incluir_explicacion": False}
        assert cliente.post(COMPARAR, json=sin_llm).status_code == 200

    def test_el_tope_diario_es_por_despacho_y_se_guarda_en_la_base(
        self, api, sesionador, monkeypatch
    ):
        monkeypatch.setenv("FISCALITO_TOPE_LLM_DIARIO_LLAMADAS", "2")
        _sin_red(monkeypatch)
        cuerpo = {
            "ingresos_mensuales_estimados": 30000,
            "gastos_mensuales_estimados": 5000,
            "incluir_explicacion": True,
        }
        assert api("uid-a").post(COMPARAR, json=cuerpo).status_code == 200
        assert api("uid-a").post(COMPARAR, json=cuerpo).status_code == 200
        r = api("uid-a").post(COMPARAR, json=cuerpo)
        assert r.status_code == 429
        assert "tope" in r.json()["error"]
        # El otro despacho tiene su propio cupo.
        assert api("uid-b").post(COMPARAR, json=cuerpo).status_code == 200
        with sesionador() as db:
            hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
            renglon = db.get(ConsumoLLM, ("uid-a", hoy))
            assert renglon is not None and renglon.llamadas == 2

    def test_sin_pedir_explicacion_no_se_cuenta_nada(self, api, sesionador, monkeypatch):
        monkeypatch.setenv("FISCALITO_TOPE_LLM_DIARIO_LLAMADAS", "1")
        cuerpo = {
            "ingresos_mensuales_estimados": 30000,
            "gastos_mensuales_estimados": 0,
            "incluir_explicacion": False,
        }
        for _ in range(3):
            assert api("uid-a").post(COMPARAR, json=cuerpo).status_code == 200
        with sesionador() as db:
            assert db.scalar(select(ConsumoLLM)) is None

    def test_el_dispositivo_tambien_tiene_limite(self, api, monkeypatch):
        token = api("uid-a").post(TOKENS, json={"cliente": "taller"}).json()["token"]
        monkeypatch.setenv("FISCALITO_RATE_LIMIT_POR_MINUTO", "1")
        sin_sesion = TestClient(app)
        assert sin_sesion.post(EVENTOS, params={"token": token}, json=CHECADA).status_code == 200
        r = sin_sesion.post(EVENTOS, params={"token": token}, json=CHECADA)
        assert r.status_code == 429


def _sin_red(monkeypatch) -> None:
    """Los tests NUNCA pegan al proveedor real: el servicio cae a su fallback estático."""

    async def _revienta(_prompt):
        raise RuntimeError("sin red en tests")

    monkeypatch.setattr("app.services.llm_service._call_openai", _revienta)
    monkeypatch.setattr("app.services.llm_service._call_anthropic", _revienta)


# ─────────────────────────────────────────────────────────────
# Unidades: ventana deslizante y tope diario
# ─────────────────────────────────────────────────────────────


class TestVentanaDeslizante:
    def test_libera_el_cupo_cuando_sale_de_la_ventana(self):
        ahora = [1000.0]
        limitador = LimitadorEnMemoria(reloj=lambda: ahora[0])
        assert limitador.consumir("k", 2) is None
        ahora[0] += 10
        assert limitador.consumir("k", 2) is None
        espera = limitador.consumir("k", 2)
        assert espera == pytest.approx(50.0)
        ahora[0] += 50.01
        assert limitador.consumir("k", 2) is None

    def test_un_rechazo_no_gasta_cupo(self):
        ahora = [0.0]
        limitador = LimitadorEnMemoria(reloj=lambda: ahora[0])
        limitador.consumir("k", 1)
        for _ in range(5):
            assert limitador.consumir("k", 1) is not None
        ahora[0] += 60.01
        assert limitador.consumir("k", 1) is None

    def test_retry_after_nunca_es_cero(self):
        assert LimiteExcedido("x", 0.2).reintentar_en == 1
        assert LimiteExcedido("x", 59.1).reintentar_en == 60


class TestTopeDiario:
    def test_se_reinicia_a_la_medianoche_de_la_ciudad_de_mexico(self, db_sesion):
        db_sesion.add(Despacho(id="d"))
        db_sesion.flush()
        mx = ZoneInfo("America/Mexico_City")
        noche = datetime(2026, 10, 19, 23, 59, tzinfo=mx)
        assert acceso_llm.cobrar_dia(db_sesion, "d", 1, noche) == 1
        with pytest.raises(LimiteExcedido) as exc:
            acceso_llm.cobrar_dia(db_sesion, "d", 1, noche)
        assert exc.value.reintentar_en == 60
        # 00:01 en CDMX ya es otro día, aunque en UTC siga siendo el 20 a las 06:01.
        madrugada = datetime(2026, 10, 20, 0, 1, tzinfo=mx)
        assert acceso_llm.cobrar_dia(db_sesion, "d", 1, madrugada) == 1

    def test_un_valor_invalido_en_el_entorno_no_cae_al_default(self, monkeypatch):
        monkeypatch.setenv("FISCALITO_TOPE_LLM_DIARIO_LLAMADAS", "muchas")
        with pytest.raises(ValueError, match="FISCALITO_TOPE_LLM_DIARIO_LLAMADAS"):
            acceso_llm.tope_diario()
