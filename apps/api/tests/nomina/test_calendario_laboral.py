"""
Tests del calendario de obligaciones patronales (F1-06, entregado por E-07).

EL ORÁCULO NO ES EL CÓDIGO
--------------------------
Las doce fechas de 2026 están **escritas a mano** desde la tabla publicada de
`knowledge_base/nomina/25_calendario_laboral_2026.md` §3. Un test que
reejecutara la función que produjo el dato no probaría nada; éste compara
contra la fuente.

LAS DOS REGLAS QUE SE VEN IGUALES
---------------------------------
Buena parte de este archivo existe para que el calendario del IMSS y el del SAT
no se fundan. El doc 25 §4 advierte que hacerlo "es un bug esperando", y en 2026
la diferencia son dos fechas: las cuotas de marzo y las de junio vencen en lunes
porque el día 17 cae en viernes, y el entero del ISR de esos mismos meses vence
el viernes 17, porque para el CFF el viernes es hábil.
"""

from datetime import date

import pytest

from app.exceptions import FiscalValidationError
from app.nomina_engine.calendario_laboral import (
    Personalidad,
    RegimenDePlazo,
    calendario_patronal,
    fecha_limite_aguinaldo,
    fecha_limite_cuotas,
    fecha_limite_entero_isr,
    fecha_limite_prima_riesgo,
    fecha_limite_ptu,
    prorroga_cff,
    prorroga_racerf,
)

# Tabla de `25_calendario_laboral_2026.md` §3, transcrita a mano.
# mes de las cuotas -> fecha límite publicada.
FECHAS_IMSS_2026 = {
    1: date(2026, 2, 17),
    2: date(2026, 3, 17),
    3: date(2026, 4, 20),  # el 17 cae en VIERNES -> lunes
    4: date(2026, 5, 18),  # el 17 cae en domingo -> lunes
    5: date(2026, 6, 17),
    6: date(2026, 7, 20),  # el 17 cae en VIERNES -> lunes
    7: date(2026, 8, 17),
    8: date(2026, 9, 17),
    9: date(2026, 10, 19),  # el 17 cae en sábado -> lunes
    10: date(2026, 11, 17),
    11: date(2026, 12, 17),
    12: date(2027, 1, 18),  # el 17 cae en domingo -> lunes
}

# Los cinco meses cuyo vencimiento se corre, según el mismo §3.
MESES_CORRIDOS_2026 = {3, 4, 6, 9, 12}


def obligaciones(anio=2026, **kwargs):
    return calendario_patronal(anio, **kwargs)


def de_clave(clave, anio=2026, **kwargs):
    return [o for o in obligaciones(anio, **kwargs) if o.clave == clave]


class TestFechasDelIMSS:
    """El test que vale el archivo."""

    @pytest.mark.parametrize("mes,esperada", sorted(FECHAS_IMSS_2026.items()))
    def test_las_doce_fechas_de_2026_son_las_publicadas(self, mes, esperada):
        assert fecha_limite_cuotas(2026, mes) == esperada

    def test_exactamente_cinco_fechas_se_corren_del_dia_17(self):
        corridos = {
            mes
            for mes, limite in FECHAS_IMSS_2026.items()
            if limite.day != 17
        }
        assert corridos == MESES_CORRIDOS_2026

    def test_el_viernes_tambien_corre_no_solo_el_fin_de_semana(self):
        """
        Si alguien quitara el viernes de `prorroga_racerf` dejando sólo sábado y
        domingo, marzo y junio quedarían en el día 17 y nadie lo notaría hasta
        que el IMSS cobrara el recargo. Ésta es esa regresión.
        """
        viernes = date(2026, 4, 17)
        assert viernes.weekday() == 4
        assert prorroga_racerf(viernes) == date(2026, 4, 20)
        # El CFF, en cambio, deja el viernes donde está.
        assert prorroga_cff(viernes) == viernes

    def test_un_dia_de_descanso_obligatorio_tambien_corre(self):
        """La regla no es sólo del calendario semanal: el Art. 74 LFT cuenta."""
        # 1-ene-2027 es viernes y además descanso obligatorio.
        assert prorroga_racerf(date(2027, 1, 1)) == date(2027, 1, 4)


class TestEnteroDelISRRetenido:
    """
    La regla del SAT (CFF Art. 12) NO es la del IMSS. Este bloque es lo que
    impide que se fundan.
    """

    @pytest.mark.parametrize(
        "mes,esperada",
        [
            (3, date(2026, 4, 17)),  # viernes: hábil para el CFF
            (6, date(2026, 7, 17)),  # viernes: hábil para el CFF
            (4, date(2026, 5, 18)),  # domingo: aquí sí corre
            (9, date(2026, 10, 19)),  # sábado: aquí sí corre
            (12, date(2027, 1, 18)),  # domingo: aquí sí corre
        ],
    )
    def test_el_isr_se_corre_por_inhabil_pero_no_por_viernes(self, mes, esperada):
        assert fecha_limite_entero_isr(2026, mes) == esperada

    @pytest.mark.parametrize("mes", [3, 6])
    def test_en_marzo_y_junio_el_isr_vence_antes_que_las_cuotas(self, mes):
        """
        El par que hay que poder enseñar: mismo mes, dos fechas, dos reglas.
        Si algún día las dos salieran iguales, es que alguien fusionó los
        calendarios que el doc 25 §4 pide no fusionar.
        """
        assert fecha_limite_entero_isr(2026, mes) < fecha_limite_cuotas(2026, mes)

    @pytest.mark.parametrize("mes", [4, 9, 12])
    def test_cuando_el_17_cae_en_fin_de_semana_las_dos_reglas_coinciden(self, mes):
        assert fecha_limite_entero_isr(2026, mes) == fecha_limite_cuotas(2026, mes)

    def test_nunca_se_emite_una_fecha_en_dia_inhabil(self):
        for mes in range(1, 13):
            limite = fecha_limite_entero_isr(2026, mes)
            assert limite.weekday() < 5, f"mes {mes} vence en fin de semana: {limite}"


class TestBimestrales:
    def test_son_seis_y_caen_con_la_mensual_del_mes_par(self):
        bimestrales = de_clave("imss_bimestral")
        assert len(bimestrales) == 6
        for bimestre, obligacion in enumerate(bimestrales, start=1):
            # Ordenadas por fecha, así que el i-ésimo es el bimestre i.
            assert obligacion.fecha_limite == FECHAS_IMSS_2026[2 * bimestre]

    def test_el_bimestre_6_vence_en_enero_del_ano_siguiente(self):
        assert de_clave("imss_bimestral")[-1].fecha_limite == date(2027, 1, 18)


class TestAvisosDeSalarioVariable:
    """
    `None` no es `False`: el modelo no registra el tipo de salario, así que no
    se sabe si el patrón tiene variables. Las tres ramas están probadas porque
    la firma es el contrato para F1-09, no sólo para el router de hoy.
    """

    def test_desconocido_se_emite_condicional_y_con_nota(self):
        avisos = de_clave("aviso_variables")
        assert len(avisos) == 6
        assert all(a.condicional for a in avisos)
        assert all("no registra el tipo de salario" in a.nota for a in avisos)

    def test_con_variables_confirmadas_el_aviso_es_firme(self):
        avisos = de_clave("aviso_variables", tiene_salario_variable=True)
        assert len(avisos) == 6
        assert not any(a.condicional for a in avisos)
        assert all(a.nota == "" for a in avisos)

    def test_sin_variables_no_se_emite_el_aviso(self):
        assert de_clave("aviso_variables", tiene_salario_variable=False) == []

    def test_el_aviso_no_se_corre_por_caer_en_viernes(self):
        """
        Art. 3 RACERF excluye los avisos afiliatorios de la prórroga. Es la
        regla OPUESTA a la de las cuotas y las dos viven en el mismo módulo.
        """
        for aviso in de_clave("aviso_variables"):
            assert aviso.regimen_de_plazo is RegimenDePlazo.IMSS_AVISO
        # 5.º día hábil de marzo de 2026 = viernes 6, y ahí se queda.
        marzo = [a for a in de_clave("aviso_variables") if a.fecha_limite.month == 3]
        assert marzo[0].fecha_limite == date(2026, 3, 6)
        assert marzo[0].fecha_limite.weekday() == 4


class TestObligacionesAnuales:
    def test_el_aguinaldo_vence_el_19_no_el_20(self):
        """
        LFT Art. 87: "antes del día veinte de diciembre". El 20 ya no está
        dentro del plazo, y un día de más es un día que la ley no concede.
        """
        assert fecha_limite_aguinaldo(2026) == date(2026, 12, 19)
        assert fecha_limite_aguinaldo(2026) != date(2026, 12, 20)

    def test_la_prima_de_riesgo_vence_el_ultimo_dia_de_febrero(self):
        assert fecha_limite_prima_riesgo(2026) == date(2026, 2, 28)

    def test_en_bisiesto_la_prima_vence_el_29(self):
        assert fecha_limite_prima_riesgo(2028) == date(2028, 2, 29)

    def test_la_prima_no_se_corre_al_lunes_aunque_caiga_en_sabado(self):
        """
        Decisión provisional §D23: el cómputo del Art. 3 RACERF sí le alcanza
        (se presenta bajo el Art. 32 del mismo reglamento), pero correr la fecha
        hacia adelante es la dirección permisiva y no se toma.
        """
        limite = fecha_limite_prima_riesgo(2026)
        assert limite.weekday() == 5  # sábado
        assert limite != date(2026, 3, 2)

    @pytest.mark.parametrize(
        "personalidad,esperada",
        [(Personalidad.MORAL, date(2026, 5, 30)), (Personalidad.FISICA, date(2026, 6, 29))],
    )
    def test_los_topes_de_ptu_salen_de_los_60_dias_del_art_122(self, personalidad, esperada):
        """Contrastado contra las dos fechas publicadas en el doc 25 §4."""
        assert fecha_limite_ptu(2026, personalidad) == esperada

    def test_sin_personalidad_conocida_se_emiten_las_dos_fechas_condicionales(self):
        ptu = [o for o in obligaciones() if o.clave.startswith("ptu_")]
        assert len(ptu) == 2
        assert all(o.condicional for o in ptu)
        assert all("no registra la personalidad" in o.nota for o in ptu)

    @pytest.mark.parametrize(
        "personalidad,clave",
        [(Personalidad.MORAL, "ptu_moral"), (Personalidad.FISICA, "ptu_fisica")],
    )
    def test_con_personalidad_conocida_se_emite_una_sola_y_firme(self, personalidad, clave):
        ptu = [o for o in obligaciones(personalidad=personalidad) if o.clave.startswith("ptu_")]
        assert [o.clave for o in ptu] == [clave]
        assert not ptu[0].condicional

    def test_la_prima_y_el_ptu_reportan_el_ejercicio_ANTERIOR(self):
        """
        La prima que se presenta en febrero de 2026 reporta la siniestralidad de
        2025 (Art. 74 LSS), y el PTU que se paga en 2026 reparte utilidades de
        2025 (Art. 122 LFT). Decir "2026" ahí sería un dato falso — es el mismo
        error de convención que el doc 25 §2 previene para las cuotas.
        """
        por_clave = {o.clave: o for o in obligaciones()}
        assert por_clave["prima_rt"].periodo_cubierto == "ejercicio 2025"
        assert por_clave["ptu_moral"].periodo_cubierto == "ejercicio 2025"
        # El aguinaldo sí es del propio ejercicio.
        assert por_clave["aguinaldo"].periodo_cubierto == "ejercicio 2026"


class TestNotasDeDiaInhabil:
    def test_toda_obligacion_sin_prorroga_que_cae_en_inhabil_trae_nota(self):
        """
        La doctrina de la corrida: una fecha fija de ley no se mueve sin norma
        que lo autorice, pero tampoco se calla que cae en sábado. Este test es
        lo que impide que la próxima obligación fija entre sin la advertencia.
        """
        sin_prorroga = [
            o
            for o in obligaciones()
            if o.regimen_de_plazo in (RegimenDePlazo.LFT, RegimenDePlazo.IMSS_AVISO)
            or o.clave == "prima_rt"
        ]
        assert sin_prorroga, "el filtro no encontró ninguna obligación sin prórroga"
        for obligacion in sin_prorroga:
            cae_en_finde = obligacion.fecha_limite.weekday() >= 5
            if cae_en_finde:
                assert obligacion.nota, f"{obligacion.clave} cae en inhábil y no trae nota"

    def test_las_tres_que_caen_en_sabado_en_2026_lo_dicen(self):
        por_clave = {o.clave: o for o in obligaciones()}
        for clave in ("prima_rt", "aguinaldo", "ptu_moral"):
            assert "sábado" in por_clave[clave].nota, clave


class TestSemanticaDelAnio:
    def test_el_parametro_es_el_anio_de_las_cuotas_no_el_del_vencimiento(self):
        """
        `calendario_patronal(2026)` cubre las cuotas DE 2026: la primera vence
        en febrero de 2026 y la última en enero de 2027. Lo que vence en enero
        de 2026 son las cuotas de diciembre de 2025 y NO está aquí.
        """
        todas = obligaciones()
        assert todas[0].fecha_limite == date(2026, 2, 17)
        assert todas[-1].fecha_limite.year == 2027
        assert not any(o.fecha_limite < date(2026, 2, 1) for o in todas)

    def test_estan_ordenadas_por_fecha(self):
        fechas = [o.fecha_limite for o in obligaciones()]
        assert fechas == sorted(fechas)

    def test_el_orden_es_estable_entre_corridas(self):
        """Sin desempate, la pantalla se reacomodaría sola entre refrescos."""
        assert [o.clave for o in obligaciones()] == [o.clave for o in obligaciones()]

    @pytest.mark.parametrize("anio", [1999, 2101, 0, -1])
    def test_un_anio_absurdo_levanta_error_de_dominio(self, anio):
        with pytest.raises(FiscalValidationError):
            calendario_patronal(anio)


class TestComposicion:
    def test_el_total_por_defecto(self):
        """12 mensuales + 12 ISR + 6 bimestrales + 6 avisos + prima + aguinaldo + 2 PTU."""
        assert len(obligaciones()) == 40

    def test_toda_obligacion_trae_fundamento_y_regimen_de_plazo(self):
        for obligacion in obligaciones():
            assert obligacion.fundamento, obligacion.clave
            assert isinstance(obligacion.regimen_de_plazo, RegimenDePlazo)

    def test_toda_condicional_trae_nota(self):
        """`condicional` sin nota no le dice al contador qué tiene que verificar."""
        for obligacion in obligaciones():
            if obligacion.condicional:
                assert obligacion.nota, obligacion.clave

    def test_no_se_emite_ninguna_obligacion_de_isn(self):
        """
        El ISN queda fuera porque no hay fuente estatal en `knowledge_base/` ni
        estado del patrón en el modelo. Si alguien lo agrega sin fuente, esto
        se cae y lo obliga a citarla.
        """
        assert not any("isn" in o.clave.lower() for o in obligaciones())
