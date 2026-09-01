"""
Tests del simulador de checador (D-05).

QUE SE PRUEBA AQUI Y QUE NO
---------------------------
El "Listo cuando" del backlog dice "corriendolo, el panel se llena solo". El
panel es **D-07 y no existe todavia**, asi que aqui se cubre la mitad que si
existe: que lo que genera el simulador entra por `POST /asistencia/eventos`,
que `GET /asistencia/eventos` devuelve exactamente lo que el panel va a
consumir —incluido el nombre— y que `cerrar-periodo` produce las 2 faltas y los
3 retardos sembrados. **Que la pantalla se llene sola se cierra en D-07.**

FECHAS LITERALES, NUNCA `date.today()`
--------------------------------------
Los numeros esperados (194 eventos, 11 dias laborables, 16 naturales) valen
para la quincena del 16 al 31 de agosto de 2026 y **para ninguna otra**: la
quincena del 1 al 15 tiene 15 dias naturales y la de febrero 2027 tiene 9
laborables. Si el periodo saliera de `quincena(date.today())`, este archivo se
pondria rojo solo en un PR que no toco nada, y la presion seria aflojar la
asercion. `quincena()` se prueba aparte, pasandole el `hoy` por parametro.
"""

import importlib.util
import sys
from datetime import date, time
from pathlib import Path

import pytest

from app.asistencia.hikvision import parse_acs_event
from app.constants import CLIENTE_DEMO

# `quincena` vive en `app/demo_nomina.py` desde D-07: el endpoint de la
# plantilla la necesita en runtime y `scripts/` no se empaqueta. Es la MISMA
# funcion que usa el simulador al sembrar; si divergieran, el panel de la
# demo saldria vacio.
from app.demo_nomina import quincena
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import FuenteChecada, HorarioLaboral, Periodo
from tests.nomina_inventario import EMPLEADOS_SINTETICOS

EVENTOS = "/api/v1/asistencia/eventos"
CERRAR = "/api/v1/asistencia/cerrar-periodo"

PERIODO = Periodo(inicio=date(2026, 8, 16), fin=date(2026, 8, 31))
TOTAL_EVENTOS = 194  # 9 empleados x 11 dias laborables x 2, menos 2 faltas x 2

# Numero de empleado -> nombre, derivado de `tests/nomina_inventario.py` y NO de
# lo que el simulador lea de los XML. `scripts/anonimizar_nomina.py:286` asigna
# `E-{i+1:02d}` al i-esimo de EMPLEADOS_SINTETICOS, y esa es la unica llave de
# mapeo. Comparar contra la plantilla que devuelve el propio simulador seria
# validarlo consigo mismo: con dos nombres intercambiados pasaria verde.
NOMBRES = {f"E-{i:02d}": EMPLEADOS_SINTETICOS[i - 1]["nombre"] for i in range(1, 10)}

# La tabla completa, escrita a mano. No se deriva de `SIEMBRA_DEMO`: si el test
# leyera la siembra probaria que el simulador es consistente consigo mismo, y
# cambiar la siembra tiene que poner esto rojo.
# (dias_periodo, dias_laborables, dias_trabajados, faltas, ausentismo, retardos, cotizados)
ESPERADO = {
    "E-01": (16, 11, 11, 0, 0, 0, 16),
    "E-02": (16, 11, 11, 0, 0, 1, 16),
    "E-03": (16, 11, 11, 0, 0, 0, 16),
    "E-04": (16, 11, 11, 0, 0, 0, 16),
    "E-05": (16, 11, 10, 1, 1, 0, 15),
    "E-06": (16, 11, 11, 0, 0, 1, 16),
    "E-07": (16, 11, 11, 0, 0, 0, 16),
    "E-08": (16, 11, 10, 1, 1, 0, 15),
    "E-09": (16, 11, 11, 0, 0, 1, 16),
}


def _cargar_simulador():
    """
    Carga `scripts/simular_checador.py` por ruta.

    `scripts/` no es paquete y `pip install -e .` solo empaqueta `app*`, asi que
    no es importable por nombre ni en local ni en CI. La ruta se resuelve desde
    `__file__` y no del cwd. El modulo se registra en `sys.modules` **antes** de
    ejecutarlo: sin eso `@dataclass` revienta con AttributeError, porque busca
    el namespace del modulo por su nombre.
    """
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "simular_checador.py"
    spec = importlib.util.spec_from_file_location("simular_checador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


sim = _cargar_simulador()


@pytest.fixture
def plantilla():
    return sim.plantilla_desde_fixtures()


@pytest.fixture
def eventos(plantilla):
    return sim.generar_checadas(plantilla, PERIODO)


def _poster(cliente_http, registro):
    """Poster inyectable que pega al endpoint real y anota cada POST."""

    def enviar(url, params, payload):
        registro.append((url, params, payload))
        return cliente_http.post(url, params=params, json=payload)

    return enviar


def _cerrar(cliente_http, plantilla):
    respuesta = cliente_http.post(
        CERRAR,
        json={
            "cliente": CLIENTE_DEMO,
            "empleados": [e.numero for e in plantilla],
            "periodo": {"inicio": PERIODO.inicio.isoformat(), "fin": PERIODO.fin.isoformat()},
        },
    )
    assert respuesta.status_code == 200
    return respuesta.json()


class TestElListoCuandoDeD05:
    """
    El recorrido que la demo hace de verdad: simulador → POST → GET → cerrar.

    Se mide contra la respuesta de los endpoints, no contra lo que el simulador
    cree haber generado.
    """

    def test_el_flujo_completo_produce_las_dos_faltas_y_los_tres_retardos(
        self, cliente_http, plantilla, eventos
    ):
        registro = []
        recibidos, duplicados = sim.enviar(
            [eventos], EVENTOS, CLIENTE_DEMO, FuenteChecada.SIMULADO.value,
            poster=_poster(cliente_http, registro),
        )
        assert (recibidos, duplicados) == (TOTAL_EVENTOS, 0)

        # El GET es la ruta que el panel de D-07 pollea cada 3 s.
        listado = cliente_http.get(EVENTOS, params={"cliente": CLIENTE_DEMO}).json()
        assert len(listado["eventos"]) == TOTAL_EVENTOS
        momentos = [e["timestamp"] for e in listado["eventos"]]
        assert momentos == sorted(momentos)
        # El nombre es el unico dato que sale del proceso por esta costura, y es
        # lo que el panel pinta junto a la hora. Se compara el PAR completo, no
        # "que traiga algo": con `all(...)` a secas, intercambiar los nombres de
        # dos empleados pasaba verde y el panel pintaria a una persona junto al
        # numero de otra.
        assert {e["empleado_no"]: e["raw"]["name"] for e in listado["eventos"]} == NOMBRES
        assert all(e["fuente"] == "simulado" for e in listado["eventos"])

        cerrado = _cerrar(cliente_http, plantilla)
        obtenido = {
            i["empleado_no"]: (
                i["dias_periodo"], i["dias_laborables"], i["dias_trabajados"],
                i["faltas"], i["dias_ausentismo"], i["retardos"], i["dias_cotizados"],
            )
            for i in cerrado["incidencias"]
        }
        assert obtenido == ESPERADO
        assert cerrado["empleados_desconocidos"] == []
        assert sum(v[3] for v in obtenido.values()) == 2
        assert sum(v[5] for v in obtenido.values()) == 3


class TestPlantilla:
    def test_son_los_nueve_empleados_de_s04(self, plantilla):
        assert [e.numero for e in plantilla] == [f"E-0{n}" for n in range(1, 10)]

    def test_cada_numero_trae_el_nombre_que_le_toca(self, plantilla):
        """
        Contraverificacion entre las dos fuentes sin duplicar la lista: las
        fixtures XML y `tests/nomina_inventario.py` tienen que decir lo mismo.

        Se comparan los PARES, no los conjuntos: con conjuntos, intercambiar dos
        nombres pasa verde y el panel de D-07 pinta a una persona junto al
        numero de otra.
        """
        assert {e.numero: e.nombre for e in plantilla} == NOMBRES


class TestFormaDelPayload:
    def test_todo_evento_sobrevive_el_adaptador_del_dispositivo(self, eventos):
        """Si el adaptador lo parsea, es el JSON que manda el aparato."""
        checadas = parse_acs_event(sim.envolver(eventos), fuente=FuenteChecada.SIMULADO)
        assert len(checadas) == TOTAL_EVENTOS
        assert all(c.timestamp.tzinfo is not None for c in checadas)
        assert all(c.serial_no is not None for c in checadas)

    def test_el_sobre_es_el_de_acsevent(self, eventos):
        sobre = sim.envolver(eventos)
        assert list(sobre) == ["AcsEvent"]
        assert sobre["AcsEvent"]["InfoList"][0]["employeeNoString"]
        assert sobre["AcsEvent"]["totalMatches"] == TOTAL_EVENTOS

    def test_es_determinista(self, plantilla):
        assert sim.generar_checadas(plantilla, PERIODO) == sim.generar_checadas(
            plantilla, PERIODO
        )


class TestSiembra:
    def _por_empleado_y_dia(self, eventos):
        agrupado = {}
        for evento in eventos:
            llave = (evento["employeeNoString"], evento["time"][:10])
            agrupado.setdefault(llave, []).append(evento)
        return agrupado

    def test_un_dia_de_falta_no_emite_ningun_evento(self, eventos):
        """
        Ni entrada ni salida. `cerrar_periodo()` marca trabajado con >= 1
        checada de cualquier tipo: dejar la salida de las 17:00 haria que E-05
        no faltara y la tabla de la demo no mostraria la falta sembrada.
        """
        agrupado = self._por_empleado_y_dia(eventos)
        # 2.º y 5.º dia laborable del periodo: 18 y 21 de agosto de 2026.
        assert ("E-05", "2026-08-18") not in agrupado
        assert ("E-08", "2026-08-21") not in agrupado
        assert ("E-05", "2026-08-17") in agrupado

    def test_cada_dia_trabajado_lleva_entrada_y_salida_en_ese_orden(self, eventos):
        for (_, _), delta in self._por_empleado_y_dia(eventos).items():
            estados = [e["attendanceStatus"] for e in delta]
            assert estados == ["checkIn", "checkOut"]
            assert delta[0]["time"] < delta[1]["time"]

    def test_no_hay_checadas_en_fin_de_semana(self, eventos):
        dias = {date.fromisoformat(e["time"][:10]) for e in eventos}
        assert all(d.weekday() < 5 for d in dias)
        assert len(dias) == 11

    def test_un_dia_sembrado_fuera_del_periodo_levanta(self, plantilla):
        siembra = sim.Siembra(faltas=(sim.Falta("E-05", 99),), retardos=())
        with pytest.raises(FiscalValidationError, match="día laborable"):
            sim.generar_checadas(plantilla, PERIODO, siembra=siembra)


class TestHorarioDerivado:
    """
    Nada de horas hardcodeadas: si el horario cambia, el simulador lo sigue.

    Sin esto, un 08:12 literal fabricaria un retardo por empleado y por dia en
    cuanto alguien bajara la tolerancia.
    """

    def test_con_tolerancia_mas_corta_no_aparecen_retardos_fantasma(
        self, cliente_http, plantilla
    ):
        horario = HorarioLaboral(tolerancia_minutos=10)
        eventos = sim.generar_checadas(plantilla, PERIODO, horario)
        cliente_http.post(EVENTOS, params={"cliente": CLIENTE_DEMO}, json=sim.envolver(eventos))
        respuesta = cliente_http.post(
            CERRAR,
            json={
                "cliente": CLIENTE_DEMO,
                "empleados": [e.numero for e in plantilla],
                "periodo": {
                    "inicio": PERIODO.inicio.isoformat(),
                    "fin": PERIODO.fin.isoformat(),
                },
                "horario": {"tolerancia_minutos": 10},
            },
        )
        retardos = {i["empleado_no"]: i["retardos"] for i in respuesta.json()["incidencias"]}
        assert retardos == {**{e.numero: 0 for e in plantilla}, "E-02": 1, "E-06": 1, "E-09": 1}

    def test_un_retardo_que_ya_no_supera_la_tolerancia_levanta(self, plantilla):
        """Sembrar algo que el motor no va a contar es sembrar de mentiras."""
        with pytest.raises(FiscalValidationError, match="no supera la tolerancia"):
            sim.generar_checadas(plantilla, PERIODO, HorarioLaboral(tolerancia_minutos=60))

    def test_la_ventana_de_entrada_queda_bajo_el_limite_de_retardo(self):
        temprano, tarde = sim.ventana_entrada_normal(HorarioLaboral())
        assert (temprano, tarde) == (time(7, 45), time(8, 12))
        temprano_10, tarde_10 = sim.ventana_entrada_normal(
            HorarioLaboral(tolerancia_minutos=10)
        )
        assert (temprano_10, tarde_10) == (time(7, 45), time(8, 7))

    def test_una_jornada_invertida_levanta(self):
        with pytest.raises(FiscalValidationError, match="jornada quedaría invertida"):
            sim.ventana_entrada_normal(HorarioLaboral(hora_salida=time(8, 5)))

    def test_un_retardo_que_cruza_la_hora_de_salida_levanta(self, plantilla):
        """
        +600 min pondría la entrada después de la salida. Hoy `SIEMBRA_DEMO` no
        llega ahí, pero el guardia de "nada se siembra en silencio" tiene que
        cubrirlo: es la misma clase de error que el retardo bajo la tolerancia.
        """
        siembra = sim.Siembra(faltas=(), retardos=(sim.Retardo("E-02", 1, 600),))
        with pytest.raises(FiscalValidationError, match="jornada quedaría invertida"):
            sim.generar_checadas(plantilla, PERIODO, siembra=siembra)


class TestDedupeYReensayo:
    def test_repetir_el_envio_no_duplica(self, cliente_http, plantilla, eventos):
        poster = _poster(cliente_http, [])
        sim.enviar([eventos], EVENTOS, CLIENTE_DEMO, "simulado", poster=poster)
        recibidos, duplicados = sim.enviar(
            [eventos], EVENTOS, CLIENTE_DEMO, "simulado", poster=poster
        )
        assert (recibidos, duplicados) == (0, TOTAL_EVENTOS)

    def test_con_otro_serial_base_el_ensayo_se_puede_repetir(
        self, cliente_http, plantilla, eventos
    ):
        """
        El ensayo es a las 6 pm y nadie va a reiniciar la API enfrente del
        cliente. `--serial-base` es lo que permite volver a llenar el panel.
        """
        poster = _poster(cliente_http, [])
        sim.enviar([eventos], EVENTOS, CLIENTE_DEMO, "simulado", poster=poster)
        otros = sim.generar_checadas(plantilla, PERIODO, serial_base=5_000_000)
        recibidos, duplicados = sim.enviar(
            [otros], EVENTOS, CLIENTE_DEMO, "simulado", poster=poster
        )
        assert (recibidos, duplicados) == (TOTAL_EVENTOS, 0)


class TestEnVivo:
    """
    El camino *push*: un POST por evento. Es el que ejercera el aparato en D-08
    y el que mas facil se rompe, asi que se prueba contra el endpoint real.
    """

    def test_manda_un_post_por_evento_del_ultimo_dia_laborable(
        self, cliente_http, eventos
    ):
        lote, vivos = sim.repartir(eventos, PERIODO, HorarioLaboral(), None)
        assert len(vivos) == 18  # 9 empleados x entrada y salida del 31 de agosto
        assert len(lote) + len(vivos) == TOTAL_EVENTOS
        assert all(e["time"].startswith("2026-08-31") for e in vivos)

        registro = []
        recibidos, _ = sim.enviar(
            [lote, *([e] for e in vivos)],
            EVENTOS, CLIENTE_DEMO, "simulado",
            intervalo=0.0, poster=_poster(cliente_http, registro),
        )
        assert recibidos == TOTAL_EVENTOS
        assert len(registro) == 1 + 18
        for _, _, payload in registro[1:]:
            assert len(payload["AcsEvent"]["InfoList"]) == 1

    def test_el_limite_mueve_el_corte_pero_no_descarta_eventos(self, eventos):
        lote, vivos = sim.repartir(eventos, PERIODO, HorarioLaboral(), 5)
        assert (len(lote), len(vivos)) == (TOTAL_EVENTOS - 5, 5)

    @pytest.mark.parametrize("limite", [9_999, 0, -1])
    def test_un_limite_imposible_levanta(self, eventos, limite):
        """`--limite 0` no puede colarse como "usa el default"."""
        with pytest.raises(FiscalValidationError, match="límite en vivo"):
            sim.repartir(eventos, PERIODO, HorarioLaboral(), limite)


class TestCLI:
    def test_lo_que_imprime_cabe_en_la_consola_de_windows(self, capsys):
        """
        Regresión: el resumen traía un "→" y la consola de Windows es cp1252.
        `main()` moría con UnicodeEncodeError **después** de generar todo, o sea
        en la demo y no en los tests, porque pytest captura en UTF-8. Se ejerce
        con `--dry-run`, que imprime además los 194 eventos con los nombres.
        """
        assert sim.main(
            ["--dry-run", "--inicio", "2026-08-16", "--fin", "2026-08-31"]
        ) == 0
        capsys.readouterr().out.encode("cp1252")

    def test_inicio_sin_fin_no_arranca(self, capsys):
        """Media fecha daría un periodo que nadie pidió; mejor no correr."""
        assert sim.main(["--inicio", "2026-08-16"]) == 2
        assert "van juntos" in capsys.readouterr().err

    def test_un_periodo_invertido_sale_con_mensaje_y_no_con_traceback(self, capsys):
        """
        Enfrente del cliente, un stack trace es peor que un mensaje. Y el
        mensaje tiene que nombrar la causa real —las fechas— y no el síntoma
        ("el periodo sólo tiene 0 días laborables").
        """
        assert sim.main(["--inicio", "2026-08-31", "--fin", "2026-08-16", "--dry-run"]) == 2
        assert "termina antes de empezar" in capsys.readouterr().err

    def test_no_se_puede_etiquetar_lo_simulado_como_del_aparato(self, capsys):
        """
        `--fuente hikvision` haría pasar el simulador por el checador, y en D-08
        ya no habría forma de distinguir en `GET /eventos` qué salió de cada uno.
        argparse lo rechaza con exit 2; el docstring solo no basta.
        """
        with pytest.raises(SystemExit) as salida:
            sim.main(["--fuente", "hikvision", "--dry-run"])
        assert salida.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    def test_un_500_de_la_api_no_revienta_parseando_html(self):
        """
        Un 502 de proxy contesta HTML: mirar el cuerpo antes del status daba un
        JSONDecodeError, que no es httpx.HTTPError y no lo atrapaba nadie.
        """

        class RespuestaHTML:
            status_code = 502
            text = "<html>Bad Gateway</html>"

            def json(self):
                raise AssertionError("no se debe parsear el cuerpo de un 502")

        with pytest.raises(FiscalValidationError, match="respondio 502"):
            sim.enviar(
                [[{"x": 1}]], EVENTOS, CLIENTE_DEMO, "simulado",
                poster=lambda *_: RespuestaHTML(),
            )


class TestQuincena:
    """
    La ultima quincena YA TERMINADA. Los dias salen de las fechas: del 16 al 31
    son 16 dias, no 15.
    """

    @pytest.mark.parametrize(
        "hoy,inicio,fin",
        [
            (date(2026, 9, 2), date(2026, 8, 16), date(2026, 8, 31)),
            (date(2026, 9, 1), date(2026, 8, 16), date(2026, 8, 31)),
            (date(2026, 9, 15), date(2026, 8, 16), date(2026, 8, 31)),
            (date(2026, 9, 16), date(2026, 9, 1), date(2026, 9, 15)),
            (date(2026, 9, 30), date(2026, 9, 1), date(2026, 9, 15)),
            (date(2027, 3, 1), date(2027, 2, 16), date(2027, 2, 28)),
            (date(2028, 3, 1), date(2028, 2, 16), date(2028, 2, 29)),
        ],
    )
    def test_bordes(self, hoy, inicio, fin):
        periodo = quincena(hoy)
        assert (periodo.inicio, periodo.fin) == (inicio, fin)
