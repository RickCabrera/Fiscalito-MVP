"""
`POST /api/v1/nomina/sbc` — integración de un salario fijo (G-01).

QUÉ PRUEBA ESTO Y QUÉ NO
------------------------
Que la ruta sea **traductor y no motor**. Las fórmulas están probadas en
`tests/nomina/test_integracion.py` contra la tabla de factores mínimos de ley de
PLAN_NOMINA §2.2; aquí se prueba que la ruta llame al motor y no decida nada por
su cuenta, que no se trague las validaciones, y que no acote en silencio.

POR QUÉ ESTA RUTA EXISTE
------------------------
Para que la pantalla de alta de empleado muestre SBC y factor mientras se teclea
el salario **sin reimplementar la fórmula en TypeScript**. Un factor calculado en
el front sería una segunda verdad sobre el Art. 27 sin ningún test que la cuide.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.main import app
from app.nomina_engine.integracion import (
    clamp_sbc,
    dias_vacaciones_de_ley,
    factor_integracion,
    sbc_fijo,
)
from app.schemas.nomina import SBCRequest

RUTA = "/api/v1/nomina/sbc"
FECHA = "2026-09-01"


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


def pedir(cliente_http: TestClient, **campos) -> dict:
    cuerpo = {"salario_diario": "500.00", "fecha": FECHA, **campos}
    r = cliente_http.post(RUTA, json=cuerpo)
    assert r.status_code == 200, r.text
    return r.json()


class TestTraductorNoMotor:
    @pytest.mark.parametrize("anios", [0, 1, 3, 5, 10, 25])
    def test_el_factor_es_exactamente_el_del_motor(self, cliente_http, anios):
        """
        Si alguna vez difieren, es que la ruta se puso a integrar por su cuenta.
        """
        del_motor = factor_integracion(15, dias_vacaciones_de_ley(anios), Decimal("0.25"))
        assert pedir(cliente_http, anios_servicio_cumplidos=anios)["factor"] == str(del_motor)

    @pytest.mark.parametrize("salario", ["316.00", "500.00", "1250.75", "5000.00"])
    def test_el_sbc_es_exactamente_el_del_motor(self, cliente_http, salario):
        factor = factor_integracion(15, dias_vacaciones_de_ley(0), Decimal("0.25"))
        esperado = clamp_sbc(
            sbc_fijo(Decimal(salario), factor), date(2026, 9, 1), ZonaSalarioMinimo.GENERAL
        )
        cuerpo = pedir(cliente_http, salario_diario=salario)
        assert cuerpo["sbc"] == str(esperado.valor)
        assert cuerpo["sbc_sin_acotar"] == str(sbc_fijo(Decimal(salario), factor))

    def test_el_piso_y_el_tope_son_los_del_motor(self, cliente_http):
        cuerpo = pedir(cliente_http)
        assert cuerpo["piso"] == str(
            salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.GENERAL)
        )
        assert Decimal(cuerpo["tope"]) == (uma_vigente(date(2026, 9, 1)) * 25).quantize(
            Decimal("0.01")
        )


class TestElClampNoEsSilencioso:
    def test_un_salario_por_debajo_del_minimo_reporta_que_se_aplico_el_piso(self, cliente_http):
        """
        `piso_aplicado` es el ÚNICO camino por el que un SBC llega a ser
        exactamente 1 salario mínimo, que es el supuesto del Art. 36 LSS (el
        patrón absorbe la cuota obrera) y el renglón de 3.150% de CEAV. Acotar
        sin decirlo escondería las dos cosas.
        """
        cuerpo = pedir(cliente_http, salario_diario="100.00")
        assert cuerpo["piso_aplicado"] is True
        assert cuerpo["tope_aplicado"] is False
        assert cuerpo["sbc"] == cuerpo["piso"]
        assert Decimal(cuerpo["sbc_sin_acotar"]) < Decimal(cuerpo["sbc"])

    def test_un_salario_altisimo_reporta_que_se_aplico_el_tope(self, cliente_http):
        cuerpo = pedir(cliente_http, salario_diario="99999.00")
        assert cuerpo["tope_aplicado"] is True
        assert cuerpo["sbc"] == cuerpo["tope"]

    def test_un_salario_normal_no_reporta_ningun_clamp(self, cliente_http):
        cuerpo = pedir(cliente_http)
        assert cuerpo["piso_aplicado"] is False
        assert cuerpo["tope_aplicado"] is False
        assert cuerpo["sbc"] == cuerpo["sbc_sin_acotar"]


class TestNoSeTragaLasValidaciones:
    def test_una_prima_como_porcentaje_responde_422_y_no_un_sbc_inflado(self, cliente_http):
        """
        25 en vez de 0.25 produce un factor de 1.86 y un SBC inflado 77% que
        ninguna tabla de referencia detecta. Un "mejor esfuerzo" que lo dejara
        pasar mataría el guard que `factor_integracion` documenta.
        """
        r = cliente_http.post(
            RUTA, json={"salario_diario": "500.00", "fecha": FECHA, "prima_vacacional": "25"}
        )
        assert r.status_code == 422
        assert r.json()["exito"] is False
        assert "0.25" in r.json()["error"]

    def test_un_aguinaldo_menor_al_minimo_responde_422(self, cliente_http):
        # Art. 87 LFT: subintegraría el SBC y con él todas las cuotas.
        r = cliente_http.post(
            RUTA, json={"salario_diario": "500.00", "fecha": FECHA, "dias_aguinaldo": 10}
        )
        assert r.status_code == 422
        assert "87" in r.json()["error"]

    def test_un_salario_de_cero_se_rechaza_en_el_schema(self, cliente_http):
        r = cliente_http.post(RUTA, json={"salario_diario": "0", "fecha": FECHA})
        assert r.status_code == 422


class TestLaFechaEsObligatoria:
    def test_sin_fecha_no_se_calcula(self, cliente_http):
        """
        `clamp_sbc` mueve el piso el 1-ene (salario mínimo) y el tope el 1-feb
        (UMA). Un `date.today()` implícito haría que el número del modal cambiara
        solo entre enero y febrero — la deriva contra la que está escrito todo el
        encabezado de `despacho_demo.py`.
        """
        r = cliente_http.post(RUTA, json={"salario_diario": "500.00"})
        assert r.status_code == 422

    def test_enero_y_febrero_de_2026_dan_topes_distintos(self, cliente_http):
        """
        En enero rige la UMA 2025 y en febrero la 2026. Si el tope no cambiara,
        la fecha no se estaría usando.
        """
        enero = pedir(cliente_http, fecha="2026-01-15", salario_diario="99999.00")
        febrero = pedir(cliente_http, fecha="2026-02-15", salario_diario="99999.00")
        assert Decimal(enero["tope"]) < Decimal(febrero["tope"])


class TestLoQueLaRutaNoHace:
    def test_rechaza_conceptos_integrables_en_vez_de_ignorarlos(self, cliente_http):
        """
        §D5: el motor no decide qué integra, el catálogo es dato y
        `ConceptoIntegrable.monto_diario` es *la porción que integra, ya
        calculada por el llamador*. Esta ruta no los acepta.

        **Y los RECHAZA en vez de ignorarlos.** Ignorarlos devolvería 200 con un
        SBC calculado sólo sobre el salario —o sea, **subintegrado**— sin
        ninguna señal. Subintegrar es la dirección peligrosa: cuotas de menos y
        crédito fiscal del IMSS. Es la misma deriva silenciosa que se rechazó en
        `fecha` y en el clamp, sólo que al revés.
        """
        r = cliente_http.post(
            RUTA,
            json={
                "salario_diario": "500.00",
                "fecha": FECHA,
                "conceptos": [{"clave": "029", "monto_diario": "50.00", "integra": True}],
            },
        )
        assert r.status_code == 422

    def test_no_devuelve_explicacion_de_llm(self, cliente_http):
        # Aquí no hay nada que explicar que no sea el número, y el LLM nunca
        # entra a un cálculo (regla de oro).
        assert "explicacion" not in pedir(cliente_http)

    def test_devuelve_los_dias_de_vacaciones_con_los_que_integro(self, cliente_http):
        """
        Si el motor recibiera 0 y aplicara el de ley por dentro, la pantalla no
        podría decir con cuántos días integró — y el contador no podría
        verificarlo.
        """
        assert pedir(cliente_http, anios_servicio_cumplidos=3)[
            "dias_vacaciones_aplicados"
        ] == dias_vacaciones_de_ley(3)

    def test_unas_vacaciones_capturadas_ganan_sobre_las_de_ley(self, cliente_http):
        # Prestación superior a la de ley: la ley es piso, no techo.
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=0, dias_vacaciones=30)
        assert cuerpo["dias_vacaciones_aplicados"] == 30
        assert Decimal(cuerpo["factor"]) > factor_integracion(
            15, dias_vacaciones_de_ley(0), Decimal("0.25")
        )


class TestFundamento:
    def test_la_respuesta_cita_su_fundamento_legal(self, cliente_http):
        fundamento = pedir(cliente_http)["fundamento"]
        for articulo in ("27", "28", "30", "76", "80", "87"):
            assert articulo in fundamento


class TestLaZonaSeUsa:
    """
    El paso de `zona` a `clamp_sbc`, que no estaba probado por nada.

    Sin esto, un `ZonaSalarioMinimo.GENERAL` hardcodeado en la ruta pasaba los
    24 tests: todos usaban el default. A un patrón de la franja fronteriza se le
    diría que su SBC está por encima del piso cuando está por debajo — y con
    `piso_aplicado: false` se pierden además el Art. 36 (el patrón absorbe la
    cuota obrera) y el renglón de 3.150% de CEAV.
    """

    def test_la_frontera_tiene_un_piso_mas_alto_que_el_resto_del_pais(self, cliente_http):
        general = pedir(cliente_http, zona="general")
        frontera = pedir(cliente_http, zona="zlfn")
        assert Decimal(frontera["piso"]) > Decimal(general["piso"])
        assert frontera["piso"] == str(
            salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.ZLFN)
        )

    def test_un_salario_entre_los_dos_pisos_solo_se_acota_en_la_frontera(self, cliente_http):
        """
        El caso que delataría un `zona` hardcodeado: el mismo salario, dos
        respuestas distintas. Si la ruta ignorara la zona, serían iguales.
        """
        piso_general = salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.GENERAL)
        piso_frontera = salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.ZLFN)
        salario = str(((piso_general + piso_frontera) / 2).quantize(Decimal("0.01")))

        assert pedir(cliente_http, salario_diario=salario, zona="general")["piso_aplicado"] is False
        assert pedir(cliente_http, salario_diario=salario, zona="zlfn")["piso_aplicado"] is True


class TestElClampEnLaIgualdad:
    """
    `clamp_sbc` usa `<` y `>` estrictos: caer EXACTAMENTE en el piso no es
    acotar. Sin esto, un cambio a `<=` pasaría inadvertido y marcaría como
    acotados SBC que la ley deja pasar tal cual.
    """

    def test_un_sbc_exactamente_en_el_piso_no_se_reporta_como_acotado(self, cliente_http):
        piso = salario_minimo_vigente(date(2026, 9, 1), ZonaSalarioMinimo.GENERAL)
        factor = factor_integracion(15, dias_vacaciones_de_ley(0), Decimal("0.25"))
        salario = (piso / factor).quantize(Decimal("0.01"))
        cuerpo = pedir(cliente_http, salario_diario=str(salario))
        # El redondeo a centavos puede no dar el piso exacto; sólo se afirma
        # cuando sí cae justo, que es el caso que interesa.
        if Decimal(cuerpo["sbc_sin_acotar"]) == piso:
            assert cuerpo["piso_aplicado"] is False
            assert cuerpo["sbc"] == cuerpo["sbc_sin_acotar"]


class TestFilaDorada:
    """
    Una fila con LITERALES, en la frontera que consume el front.

    Los demás tests comparan la respuesta contra el motor llamado desde el test:
    prueban el cableado —un argumento intercambiado, una zona perdida, un
    `clamp_sbc` olvidado— pero no cachan un cambio en el motor, porque esperado y
    real se mueven juntos. Estos números son los que se verificaron a mano contra
    la API viva, y son los que hacen el SBC del modal reproducible por inspección.
    """

    def test_los_numeros_del_modal_son_estos(self, cliente_http):
        cuerpo = pedir(
            cliente_http,
            salario_diario="500.00",
            fecha="2026-09-01",
            anios_servicio_cumplidos=3,
        )
        assert cuerpo["factor"] == "1.0521"
        assert cuerpo["dias_vacaciones_aplicados"] == 16
        assert cuerpo["sbc_sin_acotar"] == "526.05"
        assert cuerpo["sbc"] == "526.05"
        assert cuerpo["piso"] == "315.04"
        assert cuerpo["tope"] == "2932.75"
        assert cuerpo["piso_aplicado"] is False
        assert cuerpo["tope_aplicado"] is False


class TestTablaDeVacacionesDelPatron:
    """
    O-03: la escala de vacaciones del patrón llega al factor por el endpoint.

    Sin esto, capturarla en la pantalla sería un formulario decorativo: el SBC
    seguiría saliendo con los días de ley.

    **El front manda la tabla y la antigüedad, y NUNCA resuelve los días.**
    `vacaciones_efectivas` ya define `0 = los de ley`, y con una tabla ese
    centinela sería ambiguo; además, buscar el renglón en TypeScript sería una
    segunda implementación de la misma búsqueda. Por eso
    `dias_vacaciones_aplicados` vuelve en la respuesta — y el modal ya lo pinta.
    """

    TABLA = [[1, 15], [3, 20], [5, 25], [10, 30]]

    def test_la_tabla_cambia_el_factor_y_el_SBC(self, cliente_http):
        sin_tabla = pedir(cliente_http, anios_servicio_cumplidos=3)
        con_tabla = pedir(cliente_http, anios_servicio_cumplidos=3, tabla_vacaciones=self.TABLA)

        # De ley son 16 días al tercer año; la tabla da 20.
        assert sin_tabla["dias_vacaciones_aplicados"] == 16
        assert con_tabla["dias_vacaciones_aplicados"] == 20
        assert sin_tabla["factor"] == "1.0521"
        assert con_tabla["factor"] == "1.0548"
        # 500 x 0.0027 = 1.35, al centavo.
        assert Decimal(con_tabla["sbc"]) - Decimal(sin_tabla["sbc"]) == Decimal("1.35")

    def test_la_respuesta_DICE_con_cuantos_dias_integro(self, cliente_http):
        """
        Es lo que hace posible que el front no resuelva los días él mismo. Sin
        este campo, la pantalla tendría que buscar el renglón para poder
        explicar el número, y ahí nacería la segunda implementación.
        """
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=7, tabla_vacaciones=self.TABLA)
        assert cuerpo["dias_vacaciones_aplicados"] == 25

    def test_por_encima_del_ultimo_renglon_NO_le_bajan_los_dias(self, cliente_http):
        """
        Tabla hasta el año 10 con 30 días, trabajador con 11. La ley da 24: si
        el endpoint cayera a la ley, su SBC **bajaría al cumplir un año más**.
        """
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=11, tabla_vacaciones=self.TABLA)
        assert cuerpo["dias_vacaciones_aplicados"] == 30

    def test_pero_la_LEY_gana_cuando_supera_a_la_tabla(self, cliente_http):
        """Con 40 años la ley da 34, más que los 30 del último renglón."""
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=40, tabla_vacaciones=self.TABLA)
        assert cuerpo["dias_vacaciones_aplicados"] == 34

    def test_una_tabla_bajo_el_minimo_de_ley_devuelve_422(self, cliente_http):
        """
        Art. 76 LFT. El 422 trae el sobre del proyecto y el renglón infractor,
        para que quien la capturó pueda arreglarla sin adivinar.
        """
        r = cliente_http.post(
            RUTA,
            json={
                "salario_diario": "500.00",
                "fecha": FECHA,
                "anios_servicio_cumplidos": 5,
                "tabla_vacaciones": [[1, 15], [5, 19]],
            },
        )
        assert r.status_code == 422
        cuerpo = r.json()
        assert cuerpo["exito"] is False
        assert "19 días al año 5" in cuerpo["error"]
        assert "Art. 76 LFT" in cuerpo["error"]

    def test_sin_tabla_todo_sigue_exactamente_igual(self, cliente_http):
        """El default no cambia para nadie: es la ley, como antes de O-03."""
        cuerpo = pedir(cliente_http, anios_servicio_cumplidos=3)
        assert cuerpo["factor"] == "1.0521"
        assert cuerpo["dias_vacaciones_aplicados"] == 16


class TestContratoConElFront:
    """
    El payload **verbatim** que manda el modal de alta, contra el schema real.

    POR QUÉ EXISTE ESTA CLASE
    -------------------------
    F-01. En la UI, `POST /nomina/sbc` devolvía `422 extra_forbidden` por
    `tabla_vacaciones` y **ningún empleado se podía dar de alta**: el modal
    deshabilita "Dar de alta" mientras el SBC no cuadre, así que un campo de más
    en el request tumba el alta entera.

    La causa no era el schema de esta rama —`tabla_vacaciones` entró al
    `SBCRequest` en O-03 (ab0ce73)— sino una API **anterior a O-03** contra la
    que el front nuevo ya mandaba el campo. Es la cara fea de `extra="forbid"`:
    protege contra el front que manda de más (subintegrar en silencio), y a
    cambio convierte cualquier desfase de versión en un 422 total.

    Por eso el contrato se fija aquí, del lado que puede romperlo: mientras este
    archivo sea el payload literal de `ModalEmpleado.tsx`, quitar o renombrar un
    campo del `SBCRequest` pone rojo el CI en vez de la pantalla de alta.
    """

    # Copiado LITERAL de `apps/store/src/components/cartera/ModalEmpleado.tsx`
    # (el `integrarSBC({...})` del efecto con debounce). Si el modal cambia lo
    # que manda, este diccionario cambia con él **en el mismo entregable**.
    PAYLOAD_DEL_FRONT = {
        "salario_diario": "420",
        "fecha": "2026-09-03",
        "zona": "general",
        "anios_servicio_cumplidos": 2,
        "dias_aguinaldo": 15,
        "dias_vacaciones": 0,
        "prima_vacacional": "0.25",
        "tabla_vacaciones": [],
    }

    def test_el_payload_del_modal_de_alta_pasa(self, cliente_http):
        """
        El caso que estaba tumbando el alta: tabla VACÍA, que es "manda la ley".

        Se afirma el 200 **y** el número, porque un 200 con el factor de otra
        antigüedad dejaría el alta funcionando con un SBC equivocado, que es
        peor que el 422.
        """
        r = cliente_http.post(RUTA, json=self.PAYLOAD_DEL_FRONT)
        assert r.status_code == 200, r.text
        cuerpo = r.json()

        # Tabla vacía + 2 años cumplidos = los 14 días del Art. 76 LFT.
        assert cuerpo["dias_vacaciones_aplicados"] == dias_vacaciones_de_ley(2) == 14
        assert cuerpo["factor"] == str(
            factor_integracion(15, dias_vacaciones_de_ley(2), Decimal("0.25"))
        )
        assert cuerpo["sbc"] == str(
            clamp_sbc(
                sbc_fijo(Decimal("420"), factor_integracion(15, 14, Decimal("0.25"))),
                date(2026, 9, 3),
                ZonaSalarioMinimo.GENERAL,
            ).valor
        )

    def test_ningun_campo_del_front_es_extra_para_el_schema(self):
        """
        La guarda estructural contra el modo de falla de F-01.

        El test de arriba prueba ESTE payload; éste prueba la **regla**: con
        `extra="forbid"`, cualquier llave que el front mande y el schema no
        declare es un 422 que apaga la pantalla entera. Se compara contra los
        campos declarados, no contra una lista escrita a mano, para que agregar
        un campo al schema no exija tocar este test.
        """
        del_schema = set(SBCRequest.model_fields)
        del_front = set(self.PAYLOAD_DEL_FRONT)
        assert del_front <= del_schema, (
            f"El modal manda campos que el SBCRequest no declara: "
            f"{sorted(del_front - del_schema)}. Con extra='forbid' eso es un 422 "
            f"y el alta de empleado deja de funcionar (F-01)."
        )

    def test_con_renglones_la_tabla_del_patron_manda_sobre_la_ley(self, cliente_http):
        """
        El otro medio contrato: la tabla no es decoración, integra.

        Mismo payload del modal, con la escala del patrón que el proveedor de
        parámetros inyecta cuando la empresa tiene una. 16 días al año 2 están
        sobre los 14 de ley, así que el SBC sube.
        """
        r = cliente_http.post(
            RUTA,
            json={**self.PAYLOAD_DEL_FRONT, "tabla_vacaciones": [[1, 14], [2, 16]]},
        )
        assert r.status_code == 200, r.text
        cuerpo = r.json()
        assert cuerpo["dias_vacaciones_aplicados"] == 16
        assert cuerpo["factor"] == str(factor_integracion(15, 16, Decimal("0.25")))
