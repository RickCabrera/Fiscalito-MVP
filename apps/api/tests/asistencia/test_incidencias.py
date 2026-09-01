"""
Tests de incidencias.

Los esperados van como **literales calculados a mano**, nunca llamando al
propio motor: un `assert inc.retardos == calcular_retardos(...)` no probaría
nada.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.asistencia.incidencias import cerrar_periodo
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import (
    EventoChecada,
    FuenteChecada,
    HorarioLaboral,
    Periodo,
    TipoChecada,
)

CDMX = timezone(timedelta(hours=-6))
# Lunes 31-ago a domingo 6-sep de 2026: 5 laborables y 2 de fin de semana.
SEMANA = Periodo(inicio=date(2026, 8, 31), fin=date(2026, 9, 6))
EMPLEADO = "7"


def _checada(dia: int, hora: str, tipo=TipoChecada.ENTRADA, empleado=EMPLEADO, mes=9):
    h, m = (int(x) for x in hora.split(":"))
    return EventoChecada(
        empleado_no=empleado,
        timestamp=datetime(2026, mes, dia, h, m, tzinfo=CDMX),
        tipo=tipo,
        fuente=FuenteChecada.SIMULADO,
    )


def _cerrar(eventos, empleados=(EMPLEADO,), horario=None, periodo=SEMANA):
    return cerrar_periodo(eventos, empleados, periodo, horario)


class TestDiasYFaltas:
    def test_la_semana_tiene_siete_dias_y_cinco_laborables(self):
        """`dias_periodo` sale de las fechas, nunca de una constante."""
        (inc,), _ = _cerrar([])
        assert inc.dias_periodo == 7
        assert inc.dias_laborables == 5

    def test_un_dia_con_una_checada_es_trabajado(self):
        (inc,), _ = _cerrar([_checada(1, "08:00")])
        assert inc.dias_trabajados == 1

    def test_dia_laborable_sin_checada_es_falta(self):
        """Sin ninguna checada: los 5 laborables son falta, los 2 del finde no."""
        (inc,), _ = _cerrar([])
        assert inc.faltas == 5
        assert inc.dias_trabajados == 0

    def test_el_fin_de_semana_sin_checada_no_es_falta(self):
        """Checa los 5 laborables (lun 31-ago a vie 4-sep) y nada el fin de semana."""
        eventos = [_checada(31, "08:00", mes=8)] + [
            _checada(dia, "08:00") for dia in (1, 2, 3, 4)
        ]
        (inc,), _ = _cerrar(eventos)
        assert inc.dias_trabajados == 5
        assert inc.faltas == 0

    def test_dias_ausentismo_es_igual_a_faltas(self):
        """Es el campo que va a `DiasDelPeriodo`, no `dias_cotizados`."""
        (inc,), _ = _cerrar([_checada(1, "08:00")])
        assert inc.dias_ausentismo == inc.faltas == 4

    def test_dias_cotizados_descuenta_las_faltas(self):
        (inc,), _ = _cerrar([_checada(1, "08:00")])
        assert inc.dias_cotizados == 7 - 4

    def test_periodo_invertido(self):
        with pytest.raises(FiscalValidationError):
            _cerrar([], periodo=Periodo(inicio=date(2026, 9, 6), fin=date(2026, 9, 1)))


class TestRetardos:
    """La hora se mide en la zona del evento, no en UTC."""

    def test_la_hora_de_la_doc_no_es_retardo(self):
        """08:02:11−06:00 con tolerancia de 15 minutos: entra a tiempo."""
        (inc,), _ = _cerrar([_checada(1, "08:02")])
        assert inc.retardos == 0

    def test_pasada_la_tolerancia_si_es_retardo(self):
        """08:16 con entrada 08:00 y tolerancia 15."""
        (inc,), _ = _cerrar([_checada(1, "08:16")])
        assert inc.retardos == 1

    def test_justo_en_el_limite_no_es_retardo(self):
        (inc,), _ = _cerrar([_checada(1, "08:15")])
        assert inc.retardos == 0

    def test_una_salida_tarde_no_es_retardo(self):
        """
        El retardo se mide solo sobre ENTRADAS. Medirlo sobre "la primera
        checada del día" convertiría una salida a las 18:00 en retardo.
        """
        (inc,), _ = _cerrar([_checada(1, "18:00", tipo=TipoChecada.SALIDA)])
        assert inc.dias_trabajados == 1
        assert inc.retardos == 0

    def test_manda_la_primera_entrada_del_dia(self):
        eventos = [_checada(1, "09:30"), _checada(1, "08:05")]
        (inc,), _ = _cerrar(eventos)
        assert inc.retardos == 0

    def test_la_tolerancia_es_configurable(self):
        horario = HorarioLaboral(hora_entrada=time(9, 0), tolerancia_minutos=0)
        (inc,), _ = _cerrar([_checada(1, "09:01")], horario=horario)
        assert inc.retardos == 1


class TestEmpleadosDesconocidos:
    def test_una_checada_de_alguien_fuera_de_plantilla_se_reporta(self):
        """
        Si se ignorara en silencio, un alta con el `employeeNo` equivocado en
        el dispositivo se vería como "faltaron todos" y nadie sabría por qué.
        """
        (inc,), desconocidos = _cerrar([_checada(1, "08:00", empleado="99")])
        assert desconocidos == ("99",)
        assert inc.dias_trabajados == 0

    def test_sin_desconocidos_la_tupla_va_vacia(self):
        _, desconocidos = _cerrar([_checada(1, "08:00")])
        assert desconocidos == ()


class TestFueraDelPeriodo:
    def test_las_checadas_de_otro_periodo_se_ignoran(self):
        (inc,), _ = _cerrar([_checada(20, "08:00")])
        assert inc.dias_trabajados == 0
        assert inc.faltas == 5


class TestAlmacen:
    """El tope no puede cubrir solo la mitad de la estructura."""

    def test_el_indice_de_duplicados_tambien_tiene_tope(self):
        """
        Acotar la cola de eventos dejaba `_vistos` creciendo sin límite: un
        POST en loop con `serialNo` incremental seguía comiendo memoria, que es
        justo lo que el tope existía para cerrar.
        """
        from app.asistencia.almacen import MAX_EVENTOS_POR_CLIENTE, AlmacenChecadas

        almacen = AlmacenChecadas()
        for numero in range(MAX_EVENTOS_POR_CLIENTE + 50):
            almacen.agregar("x", (_checada(1, "08:00").model_copy(
                update={"serial_no": numero}
            ),))
        assert len(almacen._vistos["x"]) <= MAX_EVENTOS_POR_CLIENTE
        assert almacen.total("x") == MAX_EVENTOS_POR_CLIENTE

    def test_sigue_deduplicando_dentro_del_tope(self):
        from app.asistencia.almacen import AlmacenChecadas

        almacen = AlmacenChecadas()
        evento = _checada(1, "08:00").model_copy(update={"serial_no": 1})
        assert almacen.agregar("x", (evento,)) == (1, 0)
        assert almacen.agregar("x", (evento,)) == (0, 1)


class TestVariosEmpleados:
    def test_cada_empleado_lleva_su_cuenta(self):
        eventos = [_checada(1, "08:00"), _checada(1, "08:30", empleado="8")]
        incidencias, _ = _cerrar(eventos, empleados=("7", "8"))
        por_empleado = {i.empleado_no: i for i in incidencias}
        assert por_empleado["7"].retardos == 0
        assert por_empleado["8"].retardos == 1

    def test_un_empleado_sin_checadas_sale_con_todas_las_faltas(self):
        incidencias, _ = _cerrar([_checada(1, "08:00")], empleados=("7", "8"))
        sin_checar = next(i for i in incidencias if i.empleado_no == "8")
        assert sin_checar.faltas == 5
        assert sin_checar.dias_trabajados == 0
