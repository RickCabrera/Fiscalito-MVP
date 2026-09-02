"""
Cartera de clientes de la demo (E-02).

LO QUE ESTE ARCHIVO PROTEGE
---------------------------
1. Que los datos del cliente `demo` **no divirjan** de `PLANTILLA_DEMO`, que es
   su dueño y a su vez está atado a las fixtures de S-04.
2. Que los SDI literales de los clientes sintéticos sean **exactamente** los que
   produce el motor a `FECHA_REFERENCIA_DEMO`. El literal es el valor humano
   verificable; el motor es contra quien se contrasta.
3. Que el factor de cada antigüedad usada coincida con la **tabla publicada** de
   `docs/PLAN_NOMINA.md` §2.2. Sin esto, el punto 2 sería el motor hablando
   consigo mismo: si `factor_integracion_de_ley` estuviera mal, los literales
   estarían igual de mal y los dos coincidirían.
4. Que ningún cliente de demostración lleve datos fuera de rango legal.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente
from app.demo_nomina import PLANTILLA_DEMO, PRIMA_RIESGO_DEMO
from app.despacho_demo import (
    CLIENTES,
    FECHA_REFERENCIA_DEMO,
    cliente_por_id,
)
from app.nomina_engine.integracion import (
    clamp_sbc,
    factor_integracion_de_ley,
    sbc_fijo,
)
from app.nomina_engine.tablas_imss import (
    PRIMA_RT_MAXIMA,
    PRIMA_RT_MINIMA,
    prima_media_clase,
)

SINTETICOS = [c for c in CLIENTES if c.origen == "sintetico"]
TODOS_LOS_EMPLEADOS = [(c, e) for c in CLIENTES for e in c.empleados]


class TestCartera:
    def test_hay_tres_clientes_con_ids_estables(self):
        assert [c.id for c in CLIENTES] == ["demo", "cafeteria", "taller"]

    def test_cliente_desconocido_es_none(self):
        assert cliente_por_id("no-existe") is None

    def test_num_empleados_es_derivado_no_literal(self):
        for cliente in CLIENTES:
            assert cliente.num_empleados == len(cliente.empleados)

    def test_los_giros_y_tamanos_son_distintos(self):
        """El enunciado pide dos sintéticos con distinto giro y tamaño."""
        giros = {c.giro for c in CLIENTES}
        assert len(giros) == 3
        assert len({c.num_empleados for c in SINTETICOS}) == len(SINTETICOS)

    def test_ningun_empleado_no_se_repite_entre_clientes(self):
        """
        Ids repetidos harían que una checada del taller cayera en el panel del
        cliente equivocado: `POST /asistencia/eventos` sin `?cliente=` usa `demo`.
        """
        numeros = [e.empleado_no for _, e in TODOS_LOS_EMPLEADOS]
        assert len(numeros) == len(set(numeros))


class TestClienteDeFixtures:
    """El cliente `demo` es el caso real anonimizado: no se le inventa nada."""

    def test_son_los_nueve_de_la_plantilla_con_los_mismos_montos(self):
        demo = cliente_por_id("demo")
        assert demo is not None
        assert demo.num_empleados == len(PLANTILLA_DEMO) == 9

        por_numero = {e.empleado_no: e for e in demo.empleados}
        for original in PLANTILLA_DEMO:
            copia = por_numero[original.empleado_no]
            assert copia.nombre == original.nombre
            assert copia.salario_diario == original.salario_diario
            assert copia.salario_diario_integrado == original.salario_diario_integrado
            assert copia.zona == original.zona

    def test_no_se_les_inventa_fecha_de_alta(self):
        """
        §D9: el SDI del caso real es dato de entrada y NO se deriva de la
        antigüedad. Un alta inventada invitaría a comparar factor contra
        antigüedad y a concluir que el motor está mal.
        """
        demo = cliente_por_id("demo")
        assert demo is not None
        for empleado in demo.empleados:
            assert empleado.fecha_alta is None
            assert empleado.antiguedad_anios is None

    def test_su_factor_esta_marcado_como_implicito(self):
        demo = cliente_por_id("demo")
        assert demo is not None
        for empleado in demo.empleados:
            assert empleado.factor_implicito is True
            esperado = (
                empleado.salario_diario_integrado / empleado.salario_diario
            ).quantize(Decimal("0.0001"))
            assert empleado.factor == esperado

    def test_su_prima_es_la_del_patron_real_y_no_se_dedujo_de_una_clase(self):
        """
        Es la autodeterminada de ese patrón (Art. 74 LSS), la misma que usan los
        tests del caso real de F1-03 y F1-04. Sin fijar el valor, nada impediría
        cambiarla y descuadrar las cuotas contra el timbrado.
        """
        demo = cliente_por_id("demo")
        assert demo is not None
        assert demo.clase_riesgo is None
        assert demo.prima_riesgo == PRIMA_RIESGO_DEMO


class TestClientesSinteticos:
    def test_el_sdi_literal_es_el_que_calcula_el_motor(self):
        """
        No-divergencia contra el motor, medida a la fecha FIJA de referencia.
        Si alguien edita un SDI a mano, o cambia la escala del Art. 76 LFT, esto
        se cae.
        """
        for cliente in SINTETICOS:
            for empleado in cliente.empleados:
                anios = empleado.antiguedad_anios
                assert anios is not None
                factor = factor_integracion_de_ley(anios)
                assert empleado.salario_diario_integrado == sbc_fijo(
                    empleado.salario_diario, factor
                ), f"{cliente.id}/{empleado.empleado_no}"

    @pytest.mark.parametrize(
        ("anios_cumplidos", "factor_publicado"),
        [
            # docs/PLAN_NOMINA.md §2.2 — aguinaldo 15 días (Art. 87 LFT),
            # vacaciones del Art. 76 reformado 2023, prima vacacional 25 %
            # (Art. 80 LFT). Fuente EXTERNA al motor a propósito.
            (1, "1.0493"),
            (2, "1.0507"),
            (3, "1.0521"),
            (4, "1.0534"),
            (5, "1.0548"),
            # El renglón 6–10 de la tabla. T-01 (10 años) tiene el SDI más alto
            # de toda la cartera y sin estos dos casos su factor sólo estaría
            # validado contra el motor, que es justo el agujero que este test
            # existe para tapar.
            (6, "1.0562"),
            (8, "1.0562"),
            (10, "1.0562"),
        ],
    )
    def test_el_factor_de_ley_coincide_con_la_tabla_publicada(
        self, anios_cumplidos, factor_publicado
    ):
        assert factor_integracion_de_ley(anios_cumplidos) == Decimal(factor_publicado)

    def test_las_antiguedades_usadas_estan_todas_en_la_tabla_publicada(self):
        """
        Que el hueco no se reabra al agregar un empleado con una antigüedad que
        nadie contrastó contra §2.2.

        El 0 se exceptúa a propósito: la tabla publicada empieza en el año 1, y
        para un alta nueva el motor usa los 12 días que va a devengar en su
        primer año — lo justifica el docstring de `dias_vacaciones_de_ley`.
        """
        parametrizadas = {1, 2, 3, 4, 5, 6, 8, 10}
        usadas = {
            e.antiguedad_anios
            for c in SINTETICOS
            for e in c.empleados
            if e.antiguedad_anios != 0
        }
        assert usadas <= parametrizadas, f"sin contrastar contra §2.2: {usadas - parametrizadas}"

    def test_el_factor_que_pinta_la_ficha_es_el_de_ley(self):
        """
        `factor` se calcula como SDI ÷ SD cuantizado, y la ficha lo muestra SIN
        marca, o sea afirmando que es el del Art. 27. Que hoy el round-trip dé
        exacto es aritmética afortunada, no un invariante: mover un salario
        puede cuantizar a otro valor y la pantalla enseñaría un factor
        equivocado sin advertirlo.
        """
        for cliente in SINTETICOS:
            for empleado in cliente.empleados:
                anios = empleado.antiguedad_anios
                assert anios is not None
                assert empleado.factor == factor_integracion_de_ley(anios), (
                    f"{cliente.id}/{empleado.empleado_no}"
                )

    def test_el_clamp_no_muerde_a_la_fecha_de_referencia(self):
        """
        Un salario pegado al mínimo caería bajo el piso al cambiar el año y
        `clamp_sbc` lo subiría en silencio, moviendo las cuotas del cliente de
        demostración sin que nadie tocara código.
        """
        for cliente in SINTETICOS:
            for empleado in cliente.empleados:
                acotado = clamp_sbc(
                    empleado.salario_diario_integrado,
                    FECHA_REFERENCIA_DEMO,
                    empleado.zona,
                )
                assert acotado.piso_aplicado is False
                assert acotado.tope_aplicado is False
                assert acotado.valor == empleado.salario_diario_integrado

    def test_los_salarios_tienen_holgura_sobre_el_minimo(self):
        minimo = salario_minimo_vigente(FECHA_REFERENCIA_DEMO, ZonaSalarioMinimo.GENERAL)
        for cliente in SINTETICOS:
            for empleado in cliente.empleados:
                assert empleado.salario_diario >= minimo * Decimal("1.3")

    def test_su_prima_es_la_media_de_la_clase_que_declaran(self):
        for cliente in SINTETICOS:
            assert cliente.clase_riesgo is not None
            assert cliente.prima_riesgo == prima_media_clase(
                cliente.clase_riesgo, FECHA_REFERENCIA_DEMO
            )

    def test_ningun_factor_esta_marcado_implicito(self):
        """Aquí el factor SÍ es el de ley: hay antigüedad conocida detrás."""
        for cliente in SINTETICOS:
            for empleado in cliente.empleados:
                assert empleado.factor_implicito is False


class TestRangosLegales:
    def test_todas_las_primas_caen_en_el_rango_del_art_72(self):
        for cliente in CLIENTES:
            assert PRIMA_RT_MINIMA <= cliente.prima_riesgo <= PRIMA_RT_MAXIMA

    def test_ningun_salario_es_cero_o_negativo(self):
        for _, empleado in TODOS_LOS_EMPLEADOS:
            assert empleado.salario_diario > 0
            assert empleado.salario_diario_integrado > 0

    def test_el_sdi_nunca_es_menor_que_el_salario_diario(self):
        for _, empleado in TODOS_LOS_EMPLEADOS:
            assert empleado.salario_diario_integrado >= empleado.salario_diario
