"""
Tests del adaptador Hikvision.

El payload de `PAYLOAD_DOC` es el **literal de `docs/D-DEMO-CHECADOR.md`**,
con todos sus campos —`responseStatusStrg`, `numOfMatches`, `serialNo`,
`currentVerifyMode`— y no una versión recortada a lo que al parser le
conviene. El `name` es sintético, del pool de S-04: en el aparato real ese
campo trae el nombre de una persona.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.asistencia.hikvision import parse_acs_event
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import FuenteChecada, TipoChecada

CDMX = timezone(timedelta(hours=-6))

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


def _evento(**cambios):
    base = {
        "major": 5,
        "minor": 75,
        "time": "2026-09-01T08:02:11-06:00",
        "employeeNoString": "7",
        "attendanceStatus": "checkIn",
        "serialNo": 1,
    }
    base.update(cambios)
    return {"AcsEvent": {"InfoList": [base]}}


class TestPayloadDeLaDocumentacion:
    def test_el_payload_literal_produce_una_checada(self):
        (evento,) = parse_acs_event(PAYLOAD_DOC)
        assert evento.empleado_no == "7"
        assert evento.tipo is TipoChecada.ENTRADA
        assert evento.fuente is FuenteChecada.HIKVISION
        assert evento.serial_no == 575

    def test_conserva_el_offset_del_dispositivo(self):
        """
        La hora local es la que importa: 08:02 con offset −06:00. Si se
        guardara en UTC y luego se comparara contra un horario naive, saldrían
        las 14:02 y todos llegarían tarde.
        """
        (evento,) = parse_acs_event(PAYLOAD_DOC)
        assert evento.timestamp == datetime(2026, 9, 1, 8, 2, 11, tzinfo=CDMX)
        assert evento.timestamp.utcoffset() == timedelta(hours=-6)

    def test_guarda_el_evento_original(self):
        (evento,) = parse_acs_event(PAYLOAD_DOC)
        assert evento.raw["currentVerifyMode"] == "face"

    def test_acepta_un_infolist_suelto(self):
        """Es lo que devuelve el poll paginado, sin el envoltorio AcsEvent."""
        assert len(parse_acs_event(PAYLOAD_DOC["AcsEvent"])) == 1


class TestFiltrado:
    @pytest.mark.parametrize("minor", [75, 1, 38])
    def test_los_metodos_de_autenticacion_validos_cuentan(self, minor):
        """Rostro, tarjeta y huella. Ver la decisión provisional del módulo."""
        assert len(parse_acs_event(_evento(minor=minor))) == 1

    @pytest.mark.parametrize("minor", [21, 22, 76])
    def test_los_fallos_de_autenticacion_no_son_checadas(self, minor):
        assert parse_acs_event(_evento(minor=minor)) == ()

    def test_los_eventos_que_no_son_de_acceso_se_ignoran(self):
        assert parse_acs_event(_evento(major=1)) == ()

    def test_un_infolist_vacio_no_es_error(self):
        assert parse_acs_event({"AcsEvent": {"InfoList": []}}) == ()


class TestNadaSeDescartaEnSilencio:
    """
    Un dispositivo mal configurado tiene que hacer ruido. Si estos casos se
    ignoraran, la demo mostraría "todos faltaron" y nadie sabría por qué.
    """

    def test_sin_employee_no(self):
        with pytest.raises(FiscalValidationError) as exc:
            parse_acs_event(_evento(employeeNoString=""))
        assert "employeeNoString" in str(exc.value)

    def test_time_sin_zona_horaria(self):
        """Asumir una zona desplazaría todas las horas y crearía retardos."""
        with pytest.raises(FiscalValidationError) as exc:
            parse_acs_event(_evento(time="2026-09-01T08:02:11"))
        assert "zona horaria" in str(exc.value)

    def test_time_que_no_es_iso(self):
        with pytest.raises(FiscalValidationError):
            parse_acs_event(_evento(time="01/09/2026 08:02"))

    @pytest.mark.parametrize("estado", ["undefined", "breakIn", "overTimeIn", None])
    def test_attendance_status_desconocido_rechaza_el_batch(self, estado):
        """
        DECISIÓN PROVISIONAL: se prefiere el error ruidoso a inventar una
        jornada. Costo conocido en D-08: si el aparato llega sin modo de
        asistencia configurado, no entra ningún evento hasta configurarlo.
        """
        with pytest.raises(FiscalValidationError) as exc:
            parse_acs_event(_evento(attendanceStatus=estado))
        assert "attendanceStatus" in str(exc.value)

    def test_el_payload_no_es_un_objeto(self):
        with pytest.raises(FiscalValidationError):
            parse_acs_event([])


class TestMapeoDeTipo:
    def test_check_in_es_entrada(self):
        (evento,) = parse_acs_event(_evento(attendanceStatus="checkIn"))
        assert evento.tipo is TipoChecada.ENTRADA

    def test_check_out_es_salida(self):
        (evento,) = parse_acs_event(_evento(attendanceStatus="checkOut"))
        assert evento.tipo is TipoChecada.SALIDA

    def test_la_fuente_se_puede_marcar_como_simulada(self):
        (evento,) = parse_acs_event(_evento(), fuente=FuenteChecada.SIMULADO)
        assert evento.fuente is FuenteChecada.SIMULADO
