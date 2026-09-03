"""
La duracion del periodo tiene que casar con su periodicidad. (O-03)

POR QUE EXISTE ESTE ARCHIVO
---------------------------
`backlog.md` seccion G lo dejo escrito dos veces, y nadie lo cubria:

- **Punto 3.** Un patron marcado Mensual (05) con base de 15-16 dias recibe la
  tarifa MENSUAL del Art. 96. Sus limites inferiores son mucho mas altos, asi
  que el ingreso cae en un renglon mas bajo y el **ISR sale subestimado, con un
  recibo perfectamente creible y sin un solo error**.
- **Punto 6.** El simetrico —un patron Quincenal (04) al que le arrastran las
  fechas a un mes completo— **no lo cubria nadie**: tarifa quincenal sobre base
  mensual, ISR sobrestimado.

Los dos inputs de fecha de la pantalla son libres, asi que las dos direcciones
estan a dos clics. Hasta O-03 la unica defensa vivia en el navegador
(`useNominaCliente`), con sus propios umbrales hardcodeados — o sea, dos
verdades sobre la misma regla.

LOS RANGOS SE DERIVAN DEL CALENDARIO, Y AQUI SE VERIFICA QUE ASI SEA
---------------------------------------------------------------------
El caso mas importante del archivo es `test_la_quincena_mas_corta_del_ano`: el
rango quincenal es (13, 16) y **no** (14, 17), que fue lo que yo escribi
primero. Del 16 al 28 de febrero son 13 dias, y ese es el periodo que la propia
app propone entre el 1 y el 15 de marzo (`demo_nomina.quincena`), asi que el
rango equivocado habria hecho que el motor rechazara su propio default.

Era un defecto **latente**: el 3 de septiembre —el dia que se escribio esto— el
periodo sugerido mide 16 dias y pasa. Habria dormido hasta marzo.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.demo_nomina import quincena
from app.exceptions import FiscalValidationError
from app.nomina_engine.duracion_periodo import (
    DURACION_ESPERADA,
    validar_duracion_periodo,
)


def dias_naturales(inicio: date, fin: date) -> int:
    """Como los cuenta `asistencia/incidencias._dias_del_periodo`: inclusivo."""
    return (fin - inicio).days + 1


class TestLosRangosSalenDelCalendario:
    """No son numeros de gusto: cada extremo tiene un mes que lo produce."""

    def test_la_quincena_mas_corta_del_ano(self):
        """
        Del 16 al 28 de febrero en año no bisiesto: **13 dias**.

        Es el minimo del rango quincenal, y es el periodo que la app propone
        sola durante la primera quincena de marzo.
        """
        assert dias_naturales(date(2026, 2, 16), date(2026, 2, 28)) == 13
        assert DURACION_ESPERADA["04"][0] == 13
        validar_duracion_periodo("04", 13)  # no levanta

    def test_la_quincena_mas_larga_del_ano(self):
        """Del 16 al 31 de un mes de 31 dias: **16**. Y 17 no es una quincena."""
        assert dias_naturales(date(2026, 8, 16), date(2026, 8, 31)) == 16
        assert DURACION_ESPERADA["04"][1] == 16
        validar_duracion_periodo("04", 16)
        with pytest.raises(FiscalValidationError):
            validar_duracion_periodo("04", 17)

    def test_EL_PERIODO_QUE_LA_APP_PROPONE_SIEMPRE_PASA(self):
        """
        EL CASO QUE VALE EL ARCHIVO.

        Se recorre **el año entero** pidiendole a `quincena()` su propuesta para
        cada dia y comprobando que el motor la acepte. Con el rango equivocado
        (14, 17) esto falla en 15 dias de marzo — y sólo en marzo, que es lo que
        lo hacia un defecto latente en vez de uno visible.
        """
        dia = date(2026, 1, 1)
        while dia <= date(2026, 12, 31):
            periodo = quincena(dia)
            dias = dias_naturales(periodo.inicio, periodo.fin)
            # No levanta para ningun dia del año.
            validar_duracion_periodo("04", dias)
            dia += timedelta(days=1)

    def test_y_tambien_en_año_bisiesto(self):
        """2028 es bisiesto: del 16 al 29 de febrero son 14, que tambien cae."""
        assert dias_naturales(date(2028, 2, 16), date(2028, 2, 29)) == 14
        validar_duracion_periodo("04", 14)

    @pytest.mark.parametrize(
        "primero, ultimo, dias",
        [
            (date(2026, 2, 1), date(2026, 2, 28), 28),
            (date(2028, 2, 1), date(2028, 2, 29), 29),
            (date(2026, 4, 1), date(2026, 4, 30), 30),
            (date(2026, 1, 1), date(2026, 1, 31), 31),
        ],
    )
    def test_los_cuatro_largos_de_mes_son_mensuales(self, primero, ultimo, dias):
        assert dias_naturales(primero, ultimo) == dias
        validar_duracion_periodo("05", dias)


class TestRechazaLoQueNoCuadra:
    def test_mensual_con_una_quincena_es_el_ISR_SUBESTIMADO_del_backlog(self):
        """§G punto 3: tarifa mensual sobre base de 15-16 dias."""
        with pytest.raises(FiscalValidationError, match="mensual"):
            validar_duracion_periodo("05", 15)

    def test_quincenal_con_un_mes_es_el_SIMETRICO_que_nadie_cubria(self):
        """§G punto 6: tarifa quincenal sobre base mensual."""
        with pytest.raises(FiscalValidationError, match="quincenal"):
            validar_duracion_periodo("04", 31)

    def test_semanal_es_exactamente_siete(self):
        validar_duracion_periodo("02", 7)
        for dias in (6, 8, 14, 15):
            with pytest.raises(FiscalValidationError):
                validar_duracion_periodo("02", dias)

    def test_diaria_es_exactamente_uno(self):
        validar_duracion_periodo("01", 1)
        with pytest.raises(FiscalValidationError):
            validar_duracion_periodo("01", 2)


class TestElMensajeDistingueLasDosCausas:
    """
    Son dos problemas con arreglos OPUESTOS, y confundirlos sale caro.

    Si el mensaje solo dijera "no cuadra", el operador iria a cambiar la
    periodicidad de la empresa —que es el dato bueno— para que le deje calcular.
    Eso deja mal configurado al patron para siempre, que es peor que el 422.
    """

    def test_dice_los_dias_que_midio_y_los_que_esperaba(self):
        with pytest.raises(FiscalValidationError) as e:
            validar_duracion_periodo("05", 15)
        mensaje = str(e.value)
        assert "15 días" in mensaje
        assert "28 a 31 días" in mensaje
        assert "mensual (05)" in mensaje

    def test_ofrece_las_dos_salidas_reales(self):
        with pytest.raises(FiscalValidationError) as e:
            validar_duracion_periodo("04", 31)
        mensaje = str(e.value)
        assert "Corrige la periodicidad de la empresa, o las fechas" in mensaje

    def test_y_NOMBRA_el_periodo_parcial_con_su_decision_abierta(self):
        """
        Un alta o una baja a media quincena produce un periodo corto legitimo, y
        esta guarda lo bloquea. Es lo conservador y es una **regresion
        funcional** declarada: el mensaje tiene que decirlo, con la referencia
        de dónde se está decidiendo.
        """
        with pytest.raises(FiscalValidationError) as e:
            validar_duracion_periodo("04", 8)
        mensaje = str(e.value)
        assert "PARCIAL" in mensaje
        assert "§D26" in mensaje


class TestLoQueNO_valida:
    """
    Las claves sin rango se dejan pasar **a proposito**.

    `tarifa_por_periodicidad` ya las rechaza con su motivo (catorcenal y decenal
    por falta de tarifa publicada, §D10; bimestral y las de unidad de obra
    porque no son periodos). Duplicar ese rechazo aqui daria dos mensajes
    distintos para la misma causa, y el de alla es el que explica el porque.
    """

    @pytest.mark.parametrize("clave", ["03", "10", "06", "07", "08", "09", "99"])
    def test_las_claves_sin_tarifa_no_se_validan_por_duracion(self, clave):
        validar_duracion_periodo(clave, 14)  # no levanta: lo hace el motor de tarifas

    def test_pero_el_MOTOR_si_las_rechaza(self):
        """Para que 'lo hace el otro' no sea una promesa sin medir."""
        from app.nomina_engine.tablas_isr_periodicas import tarifa_por_periodicidad

        with pytest.raises(FiscalValidationError, match="catorcenal"):
            tarifa_por_periodicidad("03", date(2026, 9, 15))
