"""
Tests de los tres endpoints de asistencia.

Son los primeros tests de ruta del repo. El almacén es global, así que la
fixture `autouse` de `conftest.py` lo limpia entre tests: sin eso el resultado
dependería del orden y el verde no significaría nada.

Aquí vive el **"Listo cuando"** de D-04: el payload `AcsEvent` literal de
`docs/D-DEMO-CHECADOR.md` recorre el flujo completo —POST → cerrar periodo—
y produce las incidencias esperadas, con los números calculados a mano.
"""

import json

from app.constants import CLIENTE_DEMO

EVENTOS = "/api/v1/asistencia/eventos"
CERRAR = "/api/v1/asistencia/cerrar-periodo"

PAYLOAD_DOC = {
    "AcsEvent": {
        "responseStatusStrg": "OK",
        "numOfMatches": 1,
        "totalMatches": 1,
        "InfoList": [
            {
                "major": 5,
                "minor": 75,
                "time": "2026-09-01T08:02:11-06:00",
                "employeeNoString": "7",
                "name": "ANA BEATRIZ XALA MORA",
                "attendanceStatus": "checkIn",
                "currentVerifyMode": "face",
                "serialNo": 575,
            }
        ],
    }
}


def _checada(empleado, momento, estado="checkIn", serial=None):
    return {
        "major": 5,
        "minor": 75,
        "time": momento,
        "employeeNoString": empleado,
        "attendanceStatus": estado,
        **({"serialNo": serial} if serial is not None else {}),
    }


def _payload(*eventos):
    return {"AcsEvent": {"InfoList": list(eventos)}}


class TestRecibirEventos:
    def test_acepta_el_payload_del_dispositivo_sin_query_params(self, cliente_http):
        """
        La URL que se configura en el Hikvision es fija y no puede llevar el
        cliente, así que el POST pelado tiene que funcionar y caer en el
        cliente de la demo.
        """
        respuesta = cliente_http.post(EVENTOS, json=PAYLOAD_DOC)
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["cliente"] == CLIENTE_DEMO
        assert cuerpo["recibidos"] == 1
        assert cuerpo["total_en_memoria"] == 1

    def test_acepta_multipart_como_lo_manda_el_dispositivo_con_foto(self, cliente_http):
        """
        El aparato manda `multipart/form-data` cuando adjunta la foto del
        reconocimiento. Solo se lee la parte JSON; la foto no se guarda.
        """
        respuesta = cliente_http.post(
            EVENTOS,
            data={"event_log": json.dumps(PAYLOAD_DOC)},
            files={"Picture": ("rostro.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["recibidos"] == 1

    def test_deduplica_los_reintentos_del_push(self, cliente_http):
        """El dispositivo reintenta; los duplicados ensuciarían el panel."""
        cliente_http.post(EVENTOS, json=PAYLOAD_DOC)
        respuesta = cliente_http.post(EVENTOS, json=PAYLOAD_DOC)
        assert respuesta.json() == {
            "exito": True,
            "cliente": CLIENTE_DEMO,
            "recibidos": 0,
            "duplicados": 1,
            "total_en_memoria": 1,
        }

    def test_un_evento_invalido_responde_422_y_no_guarda_nada(self, cliente_http):
        payload = _payload(_checada("7", "2026-09-01T08:00:00-06:00", estado="undefined"))
        respuesta = cliente_http.post(EVENTOS, json=payload)
        assert respuesta.status_code == 422
        assert respuesta.json()["exito"] is False
        assert cliente_http.get(EVENTOS).json()["eventos"] == []

    def test_separa_los_eventos_por_cliente(self, cliente_http):
        cliente_http.post(EVENTOS, params={"cliente": "uno"}, json=PAYLOAD_DOC)
        assert cliente_http.get(EVENTOS, params={"cliente": "uno"}).json()["eventos"]
        assert cliente_http.get(EVENTOS, params={"cliente": "dos"}).json()["eventos"] == []


class TestConsultarEventos:
    def test_un_cliente_sin_eventos_devuelve_lista_vacia_no_404(self, cliente_http):
        respuesta = cliente_http.get(EVENTOS, params={"cliente": "nadie"})
        assert respuesta.status_code == 200
        assert respuesta.json()["eventos"] == []

    def test_los_devuelve_en_orden_cronologico(self, cliente_http):
        """El panel los pinta en orden; llegan desordenados si hubo reintentos."""
        cliente_http.post(
            EVENTOS,
            json=_payload(
                _checada("7", "2026-09-01T17:00:00-06:00", "checkOut", serial=2),
                _checada("7", "2026-09-01T08:00:00-06:00", serial=1),
            ),
        )
        horas = [e["timestamp"] for e in cliente_http.get(EVENTOS).json()["eventos"]]
        assert horas == sorted(horas)

    def test_desde_es_inclusivo(self, cliente_http):
        cliente_http.post(
            EVENTOS,
            json=_payload(
                _checada("7", "2026-09-01T08:00:00-06:00", serial=1),
                _checada("7", "2026-09-02T08:00:00-06:00", serial=2),
            ),
        )
        respuesta = cliente_http.get(
            EVENTOS, params={"desde": "2026-09-02T08:00:00-06:00"}
        )
        assert len(respuesta.json()["eventos"]) == 1


class TestCerrarPeriodo:
    def test_el_listo_cuando_de_d04(self, cliente_http):
        """
        EL CRITERIO DE CIERRE, de punta a punta: el `AcsEvent` **literal de la
        documentación** entra por el endpoint y sale como incidencias.

        La semana es lunes 31-ago a domingo 6-sep de 2026: 7 días naturales,
        5 laborables. El empleado "7" solo checa el martes 1-sep a las 08:02,
        que con tolerancia de 15 minutos **no** es retardo. Números a mano:
        1 día trabajado, 4 faltas (los otros 4 laborables), 0 retardos,
        7 − 4 = 3 días cotizados.
        """
        assert cliente_http.post(EVENTOS, json=PAYLOAD_DOC).status_code == 200
        respuesta = cliente_http.post(
            CERRAR,
            json={
                "cliente": CLIENTE_DEMO,
                "empleados": ["7"],
                "periodo": {"inicio": "2026-08-31", "fin": "2026-09-06"},
            },
        )
        assert respuesta.status_code == 200
        (incidencia,) = respuesta.json()["incidencias"]
        assert incidencia["dias_periodo"] == 7
        assert incidencia["dias_laborables"] == 5
        assert incidencia["dias_trabajados"] == 1
        assert incidencia["faltas"] == 4
        assert incidencia["dias_ausentismo"] == 4
        assert incidencia["retardos"] == 0
        assert incidencia["dias_cotizados"] == 3
        assert respuesta.json()["empleados_desconocidos"] == []

    def test_reporta_los_empleados_que_no_estan_en_plantilla(self, cliente_http):
        cliente_http.post(EVENTOS, json=PAYLOAD_DOC)
        respuesta = cliente_http.post(
            CERRAR,
            json={
                "cliente": CLIENTE_DEMO,
                "empleados": ["8"],
                "periodo": {"inicio": "2026-08-31", "fin": "2026-09-06"},
            },
        )
        assert respuesta.json()["empleados_desconocidos"] == ["7"]

    def test_el_horario_se_puede_ajustar(self, cliente_http):
        """Con entrada a las 08:00 y tolerancia 0, las 08:02 sí son retardo."""
        cliente_http.post(EVENTOS, json=PAYLOAD_DOC)
        respuesta = cliente_http.post(
            CERRAR,
            json={
                "cliente": CLIENTE_DEMO,
                "empleados": ["7"],
                "periodo": {"inicio": "2026-08-31", "fin": "2026-09-06"},
                "horario": {"hora_entrada": "08:00:00", "tolerancia_minutos": 0},
            },
        )
        assert respuesta.json()["incidencias"][0]["retardos"] == 1

    def test_un_periodo_invertido_responde_422(self, cliente_http):
        respuesta = cliente_http.post(
            CERRAR,
            json={
                "cliente": CLIENTE_DEMO,
                "empleados": ["7"],
                "periodo": {"inicio": "2026-09-06", "fin": "2026-08-31"},
            },
        )
        assert respuesta.status_code == 422


class TestAvisoDeDemo:
    def test_los_tres_endpoints_se_anuncian_como_demo_en_openapi(self, cliente_http):
        """
        `/docs` es el plan B de la demo si D-07 no llega, así que el aviso
        tiene que verse ahí: sin auth, en memoria, no desplegar.
        """
        rutas = cliente_http.get("/openapi.json").json()["paths"]
        for ruta, metodo in (
            ("/api/v1/asistencia/eventos", "post"),
            ("/api/v1/asistencia/eventos", "get"),
            ("/api/v1/asistencia/cerrar-periodo", "post"),
        ):
            assert rutas[ruta][metodo]["summary"].startswith("DEMO —")
