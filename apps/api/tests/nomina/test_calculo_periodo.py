"""
Tests del orquestador de nómina del periodo (D-06).

QUE MIDE ESTE ARCHIVO
---------------------
`calcular_periodo` **no calcula nada fiscal**: su trabajo es que cada argumento
llegue a la función del motor que le toca. Así que lo que se prueba es
**pass-through**, no aritmética — la aritmética ya la fijaron F1-01…F1-05.

Los esperados son **literales escritos a mano**. Ninguno se obtiene llamando a
`armar_recibo` ni a `cuotas_empleado` dentro del test: eso sería comparar el
motor consigo mismo.

CUIDADO CON LA PERIODICIDAD DE LOS LITERALES
--------------------------------------------
Los números que ya están congelados en `test_armado_recibo.py` y en
`test_cuotas_caso_real.py` son de nómina **SEMANAL** (`DiasDelPeriodo(7)`,
clave `"02"`): el caso real se pagaba cada 7 días. Correrlos con la quincena de
la demo y esperar los mismos importes sería un test que sólo se puede "arreglar"
moviendo parámetros hasta que cuadre. Por eso el pass-through corre en
configuración semanal explícita, y el caso quincenal va aparte y **etiquetado
como caracterización**.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import ZonaSalarioMinimo
from app.exceptions import FiscalValidationError
from app.nomina_engine.cuotas import consolidado_bimestral, consolidado_mensual
from app.nomina_engine.periodo import (
    EmpleadoPeriodo,
    IncidenciasPeriodo,
    calcular_periodo,
)

GENERAL = ZonaSalarioMinimo.GENERAL
ZLFN = ZonaSalarioMinimo.ZLFN
PRIMA_RT = Decimal("0.0054355")

# El caso de F1-03/F1-04: E-08, SBC 331.58, semana de 7 días pagada el 5-abr-2026.
SEMANAL = dict(fecha_pago=date(2026, 4, 5), prima_riesgo=PRIMA_RT, clave_periodicidad="02")


def _empleado(numero="E-08", diario="316.00", sdi="331.58", zona=GENERAL):
    return EmpleadoPeriodo(numero, f"NOMBRE {numero}", Decimal(diario), Decimal(sdi), zona)


def _inc(numero="E-08", dias=7, faltas=0, ausentismo=None, incapacidad=0):
    return IncidenciasPeriodo(
        numero, dias, faltas, faltas if ausentismo is None else ausentismo, incapacidad
    )


def _correr(empleados=None, incidencias=None, **kwargs):
    return calcular_periodo(
        empleados or (_empleado(),),
        incidencias or (_inc(),),
        **{**SEMANAL, **kwargs},
    )


class TestPassThrough:
    """
    Cada argumento llega a donde debe. Los importes son de F1-03 y F1-04.

    Para este empleado y esta semana el motor ya tiene congelados: ISR retenido
    **$34.68** (causado $158.02 − subsidio acreditado $123.34) y cuota obrera
    **$55.12**. Si estos números cambian, cambió el motor, no el orquestador.
    """

    def test_el_isr_y_la_cuota_obrera_son_los_que_fijo_f1(self):
        recibo = _correr().recibos[0]
        por_tipo = {d.tipo: d.importe for d in recibo.recibo.deducciones}
        assert por_tipo == {"002": Decimal("34.68"), "001": Decimal("55.12")}

    def test_el_subsidio_causado_es_el_de_la_formula_del_articulado(self):
        otro = _correr().recibos[0].recibo.otros_pagos[0]
        assert (otro.tipo, otro.importe, otro.subsidio_causado) == (
            "002",
            Decimal("0.00"),
            Decimal("123.34"),
        )

    def test_el_sueldo_es_el_salario_diario_por_los_dias_pagados(self):
        recibo = _correr().recibos[0]
        assert recibo.dias_pagados == 7
        assert recibo.recibo.total_percepciones == Decimal("2212.00")
        assert recibo.recibo.total == Decimal("2122.20")  # 2212.00 − 34.68 − 55.12

    def test_el_sueldo_se_redondea_a_dos_decimales(self):
        """
        Con sueldos de dos decimales y días enteros el redondeo no se nota, así
        que hace falta un salario con más decimales para ejercerlo: el importe
        que va al CFDI lleva dos, y arrastrar 2333.3331 al recibo mete el error
        en todos los totales de abajo.
        """
        recibo = _correr((_empleado(diario="333.3333"),)).recibos[0]
        assert recibo.recibo.total_percepciones == Decimal("2333.33")

    def test_el_sbc_pasa_por_el_clamp(self):
        recibo = _correr().recibos[0]
        assert recibo.sbc.valor == Decimal("331.58")
        assert (recibo.sbc.piso_aplicado, recibo.sbc.tope_aplicado) == (False, False)


class TestLosArgumentosLleganDeVerdad:
    """
    Las cuatro costuras donde un orquestador se rompe en silencio: un parámetro
    que se ignora o se cablea da un resultado plausible y equivocado.
    """

    def test_la_fecha_de_pago_decide_la_vigencia(self):
        """
        Enero rige con la UMA 2025 y el transitorio del subsidio; de febrero en
        adelante, con la UMA 2026 y el porcentaje ordinario. Si el orquestador
        cableara la fecha, los dos darían lo mismo.

        El valor de enero es $123.47, que coincide con el `SubsidioCausado`
        que el CFDI del caso real declara en marzo. **Eso no desempata nada** y
        no hay que leerlo como evidencia: §D15 ya muestra que las dos bases
        candidatas dan las dos $123.47, así que la coincidencia es simétrica —la
        hipótesis del arrastre y la de los considerandos reproducen el número
        igual de bien—. Lo que este test aporta es ancla de regresión: la rama
        del transitorio de enero queda ejercitada.
        """
        enero = _correr(fecha_pago=date(2026, 1, 15)).recibos[0]
        febrero = _correr(fecha_pago=date(2026, 2, 15)).recibos[0]
        subsidio_enero = enero.recibo.otros_pagos[0].subsidio_causado
        subsidio_febrero = febrero.recibo.otros_pagos[0].subsidio_causado
        assert subsidio_enero == Decimal("123.47")
        assert subsidio_febrero == Decimal("123.34")

    def test_la_prima_de_riesgo_llega_y_solo_mueve_riesgos_de_trabajo(self):
        """
        Con la prima al doble, Riesgos de Trabajo se mueve y **ningún otro ramo**.

        Los importes van como literales y NO como `base × 2`: el redondeo es por
        concepto (D2), así que duplicar la tasa no duplica el centavo —12.62
        contra 25.23, no 25.24—. Escribir la relación en vez del número habría
        sido reimplementar el redondeo dentro del test.
        """
        base = {r.clave: r.patron for r in _correr().recibos[0].cuotas.ramos}
        doble = {
            r.clave: r.patron
            for r in _correr(prima_riesgo=Decimal("0.010871")).recibos[0].cuotas.ramos
        }
        assert base["riesgos_trabajo"] == Decimal("12.62")
        assert doble["riesgos_trabajo"] == Decimal("25.23")
        assert {k: v for k, v in doble.items() if k != "riesgos_trabajo"} == {
            k: v for k, v in base.items() if k != "riesgos_trabajo"
        }

    def test_la_zona_decide_el_piso_del_sbc(self):
        """SM general $315.04 contra ZLFN $440.87 (2026)."""
        general = _correr((_empleado(sdi="350.00", zona=GENERAL),)).recibos[0]
        frontera = _correr((_empleado(sdi="350.00", zona=ZLFN),)).recibos[0]
        assert (general.sbc.valor, general.sbc.piso_aplicado) == (Decimal("350.00"), False)
        assert (frontera.sbc.valor, frontera.sbc.piso_aplicado) == (
            Decimal("440.87"),
            True,
        )

    def test_el_ausentismo_reduce_iyv_pero_no_enfermedades_y_maternidad(self):
        """
        Art. 31 LSS, §D3. Se mide sobre los días de cada ramo, y la resta es
        `dias_periodo − dias_ausentismo − dias_incapacidad`: en F1-09 la
        incapacidad deja de ser cero y una aserción cableada a un solo término
        se volvería falsa en silencio.
        """
        resultado = _correr(incidencias=(_inc(dias=7, faltas=2),))
        dias = {r.clave: r.dias for r in resultado.recibos[0].cuotas.ramos}
        assert dias["eym_cuota_fija"] == 7
        assert dias["eym_excedente"] == 7
        assert dias["invalidez_vida"] == 7 - 2 - 0
        assert dias["retiro"] == 7 - 2 - 0
        assert resultado.recibos[0].dias_pagados == 5


class TestSalarioMinimo:
    """
    El predicado del Art. 96 último párrafo tiene que llegar a `armar_recibo`.

    `cuotas_empleado` lo resuelve por dentro, así que la absorción del Art. 36
    funcionaría igual con el flag mal puesto: lo que se rompe en silencio es el
    ISR. Con los SDI de la demo (331.58–399.52 contra SM $315.04) nadie cae en
    el supuesto, así que el defecto cruzaría la demo entera sin verse.
    """

    def test_al_trabajador_de_salario_minimo_no_se_le_retiene_isr(self):
        recibo = _correr((_empleado(diario="315.04", sdi="315.04"),)).recibos[0]
        assert recibo.es_salario_minimo is True
        assert {d.tipo for d in recibo.recibo.deducciones} == set()
        assert recibo.cuotas.total_obrero == Decimal("0.00")
        assert recibo.cuotas.absorbio_cuota_obrera is True

    def test_la_absorcion_no_borra_el_renglon_del_ramo(self):
        """El obrero sigue declarado por ramo: es lo que se concilia con la EMA."""
        recibo = _correr((_empleado(diario="315.04", sdi="315.04"),)).recibos[0]
        assert sum(r.obrero for r in recibo.cuotas.ramos) > Decimal("0")

    def test_un_centavo_arriba_del_minimo_si_retiene(self):
        """Sin esto, el predicado podría estar cableado a True."""
        recibo = _correr((_empleado(diario="315.05", sdi="315.05"),)).recibos[0]
        assert recibo.es_salario_minimo is False
        assert recibo.cuotas.absorbio_cuota_obrera is False


class TestConsolidados:
    def test_la_porcion_es_exactamente_lo_que_da_el_motor(self):
        """
        Orquestador, no motor: `porcion_*` es un renombre del consolidado del
        motor, no una suma nueva.
        """
        resultado = _correr()
        cuotas = tuple(r.cuotas for r in resultado.recibos)
        assert resultado.porcion_mensual == consolidado_mensual(cuotas)
        assert resultado.porcion_bimestral == consolidado_bimestral(cuotas)

    def test_la_advertencia_de_la_porcion_siempre_esta(self):
        avisos = _correr().advertencias
        assert any("NO el entero mensual ni el bimestral" in a for a in avisos)

    def test_el_ausentismo_prolongado_pide_revision_manual(self):
        """
        La advertencia dice que el motor cobra de más y que hay que revisarlo a
        mano, y **no afirma qué concede el Art. 31 LSS**: ese tratamiento sigue
        PROVISIONAL en la `knowledge_base` y en §D3, no hay transcripción contra
        el DOF en el repo, y el texto viaja a la respuesta del endpoint y al
        prompt del LLM. Una afirmación legal sin fuente dirigida a quien entera
        las cuotas es exactamente lo que este repo no publica.
        """
        # O-03: se le pasa `clave_periodicidad="04"` porque la fixture por
        # defecto es SEMANAL y 15 días no es una semana. La guarda nueva de
        # duración lo rechaza antes de llegar al cálculo, y este test mide la
        # advertencia de ausentismo, no la periodicidad.
        #
        # **Cede la fixture, no el rango.** 15 días semanales es lo que estaba
        # mal: ensanchar (7, 7) para que este caso pasara sería aflojar una
        # validación para forzar el verde. 15 sí es una quincena válida, así que
        # el caso sigue midiendo exactamente lo que medía.
        avisos = _correr(
            incidencias=(_inc(dias=15, faltas=8),), clave_periodicidad="04"
        ).advertencias
        aviso = next(a for a in avisos if "revisión manual" in a)
        assert "E-08" in aviso
        assert "cobra de más, nunca de menos" in aviso
        assert "libera al patrón" not in aviso
        assert "Art. 31" not in aviso

    def test_sin_ausentismo_excesivo_no_hay_esa_advertencia(self):
        assert not any("revisión manual" in a for a in _correr().advertencias)


class TestDiasPagadosOverride:
    """
    `dias_pagados` es dinero: pisa `dias_periodo − faltas` para TODA la
    plantilla, así que activarlo por error borra las faltas de la nómina.
    """

    def test_el_override_manda_sobre_las_faltas(self):
        resultado = _correr(
            incidencias=(_inc(dias=7, faltas=2),), dias_pagados_override=7
        )
        recibo = resultado.recibos[0]
        assert recibo.dias_pagados == 7
        assert recibo.recibo.total_percepciones == Decimal("2212.00")

    def test_sin_override_las_faltas_descuentan(self):
        recibo = _correr(incidencias=(_inc(dias=7, faltas=2),)).recibos[0]
        assert recibo.dias_pagados == 5
        assert recibo.recibo.total_percepciones == Decimal("1580.00")

    def test_el_override_no_toca_los_dias_de_cotizacion(self):
        """
        Pagar días no es cotizar días: el ausentismo sigue reduciendo los ramos
        que se reducen (§D3) aunque el patrón decida pagar la quincena completa.
        """
        resultado = _correr(
            incidencias=(_inc(dias=7, faltas=2),), dias_pagados_override=7
        )
        dias = {r.clave: r.dias for r in resultado.recibos[0].cuotas.ramos}
        assert dias["invalidez_vida"] == 5
        assert dias["eym_cuota_fija"] == 7


class TestTotalesDelPeriodo:
    """
    Los totales cruzan las DOS periodicidades de entero.

    Viven en `ResultadoPeriodo` y no en cada consumidor porque los leen la ruta
    (para el prompt del LLM) y la tool del agente: sumarlos a mano en dos
    lugares es como se llega a que el chat y el PDF digan cosas distintas. Una
    versión que sólo sumara la porción mensual dejaría fuera Retiro, CEAV e
    Infonavit, que son la mayor parte de la cuota patronal.
    """

    def _resultado(self):
        return _correr(
            (_empleado("E-01"), _empleado("E-02", diario="326.84", sdi="357.44")),
            (_inc("E-01"), _inc("E-02")),
        )

    def test_los_totales_suman_las_dos_periodicidades(self):
        r = self._resultado()
        assert r.total_obrero == (
            r.porcion_mensual.total_obrero + r.porcion_bimestral.total_obrero
        )
        assert r.total_patron == (
            r.porcion_mensual.total_patron + r.porcion_bimestral.total_patron
        )
        # La porción bimestral no es despreciable: si alguien sumara sólo la
        # mensual, se perderían Retiro, CEAV e Infonavit.
        assert r.porcion_bimestral.total_patron > Decimal("0")
        assert r.total_patron > r.porcion_mensual.total_patron

    def test_los_totales_de_los_recibos_son_la_suma_de_los_recibos(self):
        r = self._resultado()
        assert r.total_neto == sum(x.recibo.total for x in r.recibos)
        assert r.total_isr == sum(x.recibo.total_impuestos_retenidos for x in r.recibos)
        assert r.total_percepciones == sum(x.recibo.total_percepciones for x in r.recibos)
        assert r.total_percepciones == Decimal("2212.00") + Decimal("2287.88")


class TestDescuadres:
    def test_un_empleado_sin_incidencias_levanta(self):
        with pytest.raises(FiscalValidationError, match="no traen incidencias"):
            _correr((_empleado("E-01"), _empleado("E-02")), (_inc("E-01"),))

    def test_una_incidencia_huerfana_levanta(self):
        with pytest.raises(FiscalValidationError, match="no están en la plantilla"):
            _correr((_empleado("E-01"),), (_inc("E-01"), _inc("E-77")))

    def test_una_plantilla_vacia_levanta(self):
        with pytest.raises(FiscalValidationError, match="no puede estar vacía"):
            calcular_periodo((), (), **SEMANAL)

    def test_periodos_de_distinta_duracion_levantan(self):
        with pytest.raises(FiscalValidationError, match="distinta duración"):
            _correr(
                (_empleado("E-01"), _empleado("E-02")),
                (_inc("E-01", dias=7), _inc("E-02", dias=15)),
            )

    def test_mas_faltas_que_dias_levanta(self):
        with pytest.raises(FiscalValidationError, match="días pagados"):
            _correr(incidencias=(_inc(dias=7, faltas=9, ausentismo=7),))

    def test_la_catorcenal_levanta_con_el_motivo_de_d10(self):
        with pytest.raises(FiscalValidationError, match="catorcenal"):
            _correr(clave_periodicidad="03")


class TestCaracterizacionQuincenal:
    """
    CARACTERIZACIÓN, NO VERIFICACIÓN.

    Estos números salen del motor de hoy con la configuración quincenal de la
    demo; **no cuadran contra ningún dato timbrado**, porque el caso real de
    S-04 es semanal. Sirven para detectar una regresión, no para afirmar que el
    motor reproduce nada.
    """

    def test_la_quincena_de_la_demo_es_estable(self):
        resultado = calcular_periodo(
            (_empleado(),),
            (_inc(dias=16, faltas=1),),
            fecha_pago=date(2026, 8, 31),
            prima_riesgo=PRIMA_RT,
            clave_periodicidad="04",
        )
        recibo = resultado.recibos[0]
        assert recibo.dias_pagados == 15
        assert recibo.recibo.total_percepciones == Decimal("4740.00")
        assert {d.tipo for d in recibo.recibo.deducciones} == {"001", "002"}
