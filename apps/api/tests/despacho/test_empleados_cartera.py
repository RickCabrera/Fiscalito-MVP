"""
El modelo canónico de empleado y su semilla (G-01), y la llave del checador (G-02).

QUÉ PRUEBA ESTO Y QUÉ NO
------------------------
Que la semilla salga en el MISMO modelo que el despacho guarda, que las dos
llaves —cálculo y checador— sean independientes, y que el NSS no se invente.
**No** prueba persistencia: el backend no persiste nada, el dueño del dato es
Firestore bajo el uid (ver el encabezado de `app/schemas/empleado.py`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.despacho_demo import CLIENTES
from app.main import app
from app.schemas.empleado import (
    EmpleadoCarteraSchema,
    EstatusEnrolamiento,
    PrestacionesSchema,
    TipoContrato,
)
from app.schemas.nomina import EmpleadoNominaSchema


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)


def semilla(cliente_http: TestClient, cliente_id: str = "demo") -> dict:
    r = cliente_http.get(f"/api/v1/despacho/clientes/{cliente_id}/empleados")
    assert r.status_code == 200, r.text
    return r.json()


class TestLaSemilla:
    @pytest.mark.parametrize("cliente", [c.id for c in CLIENTES])
    def test_cada_cliente_devuelve_a_todos_sus_empleados(self, cliente_http, cliente):
        esperado = next(c for c in CLIENTES if c.id == cliente)
        cuerpo = semilla(cliente_http, cliente)
        assert cuerpo["total"] == esperado.num_empleados
        assert len(cuerpo["empleados"]) == esperado.num_empleados

    def test_no_es_una_lista_aparte_sino_los_mismos_empleados(self, cliente_http):
        """
        G-01 pide explícitamente que los empleados actuales se carguen como
        semilla del MISMO modelo, no como una lista paralela. Si esto se
        rompiera, habría dos verdades sobre quién trabaja en el cliente.
        """
        del_catalogo = {e.empleado_no: e for e in CLIENTES[0].empleados}
        for e in semilla(cliente_http, CLIENTES[0].id)["empleados"]:
            fuente = del_catalogo[e["empleado_no"]]
            assert e["nombre"] == fuente.nombre
            assert e["salario_diario"] == str(fuente.salario_diario)
            assert e["salario_diario_integrado"] == str(fuente.salario_diario_integrado)

    def test_un_cliente_que_no_existe_responde_404_con_sobre_propio(self, cliente_http):
        # Sobre `{exito, error}`, no `{"detail": ...}`: el front lee un `detail`
        # string como "esta ruta no existe" y mandaría a reiniciar la API.
        r = cliente_http.get("/api/v1/despacho/clientes/no-existe/empleados")
        assert r.status_code == 404
        assert r.json()["exito"] is False
        assert "no-existe" in r.json()["error"]


class TestLasDosLlavesSonDistintas:
    """
    El corazón de G-02: `empleado_no` (cálculo) y `employee_no` (checador) son
    campos distintos. Fundirlos obligaría a que la llave del cálculo fuera
    nullable, y ahí se pierde gente: o el request revienta con 422 y la nómina
    entera falla, o dos empleados sin vincular entran ambos con "" y colisionan.
    """

    def test_la_semilla_viene_vinculada_para_que_la_demo_siga_igual(self, cliente_http):
        cuerpo = semilla(cliente_http)
        assert cuerpo["sin_vincular"] == 0
        for e in cuerpo["empleados"]:
            assert e["employee_no"] == e["empleado_no"]
            assert e["enrolamiento"] == EstatusEnrolamiento.ENROLADO.value

    def test_un_empleado_puede_no_tener_llave_de_checador(self):
        nuevo = EmpleadoCarteraSchema(
            empleado_no="N-01",
            nombre="EMPLEADO NUEVO",
            salario_diario="450.00",
            salario_diario_integrado="473.85",
        )
        assert nuevo.employee_no is None
        assert nuevo.vinculado_al_checador is False
        assert nuevo.enrolamiento == EstatusEnrolamiento.PENDIENTE

    def test_la_llave_del_calculo_nunca_puede_ser_vacia(self):
        # Si esto dejara de levantar, dos empleados sin vincular entrarían al
        # cálculo con la misma llave y uno se comería las incidencias del otro.
        with pytest.raises(ValidationError):
            EmpleadoCarteraSchema(
                empleado_no="",
                nombre="X",
                salario_diario="450.00",
                salario_diario_integrado="473.85",
            )

    def test_el_conteo_de_no_vinculados_lo_hace_el_backend(self):
        """
        `sin_vincular` se calcula en el servidor y no en la UI: un aviso que
        depende de que alguien se acuerde de filtrar es un aviso que un día no
        sale. Aquí se fija que el campo existe y es el que la pantalla lee.
        """
        from app.schemas.empleado import EmpleadosClienteResponse

        r = EmpleadosClienteResponse(
            cliente_id="x",
            origen="sintetico",
            total=2,
            sin_vincular=1,
            empleados=(
                EmpleadoCarteraSchema(
                    empleado_no="A",
                    nombre="A",
                    salario_diario="450",
                    salario_diario_integrado="473",
                    employee_no="7",
                ),
                EmpleadoCarteraSchema(
                    empleado_no="B",
                    nombre="B",
                    salario_diario="450",
                    salario_diario_integrado="473",
                ),
            ),
        )
        assert sum(1 for e in r.empleados if not e.vinculado_al_checador) == r.sin_vincular


class TestCompatibilidadConElCalculo:
    def test_el_modelo_de_cartera_alimenta_al_de_nomina_sin_remapear(self, cliente_http):
        """
        `EmpleadoCarteraSchema` es un superconjunto compatible de
        `EmpleadoNominaSchema`: la pantalla manda estos objetos tal cual a
        `POST /nomina/calcular-periodo`. Si divergieran, habría que remapear en
        el front, o sea mover datos fiscales a la UI.
        """
        for e in semilla(cliente_http)["empleados"]:
            EmpleadoNominaSchema(**{
                k: e[k]
                for k in ("empleado_no", "nombre", "salario_diario",
                          "salario_diario_integrado", "zona")
            })

    def test_la_nomina_del_periodo_acepta_la_semilla_completa(self, cliente_http):
        """
        El criterio de G-01 —"aparece en el cálculo de nómina de ese cliente"—
        medido de punta a punta contra el endpoint real, no contra el schema.
        """
        empleados = semilla(cliente_http)["empleados"]
        r = cliente_http.post(
            "/api/v1/nomina/calcular-periodo",
            json={
                "cliente": "demo",
                "periodo": {"inicio": "2026-08-16", "fin": "2026-08-31"},
                "incidencias": [
                    {"empleado_no": e["empleado_no"], "dias_periodo": 16,
                     "faltas": 0, "dias_ausentismo": 0}
                    for e in empleados
                ],
                "empleados": [
                    {k: e[k] for k in ("empleado_no", "nombre", "salario_diario",
                                       "salario_diario_integrado", "zona")}
                    for e in empleados
                ],
                "parametros": {"prima_riesgo": "0.0054355", "clave_periodicidad": "04"},
            },
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["recibos"]) == len(empleados)


class TestPrivacidad:
    def test_ningun_empleado_de_la_semilla_trae_nss(self, cliente_http):
        """
        **No se inventa un NSS.** Un NSS de 11 dígitos bien formado es el NSS de
        alguien, y los nueve del caso real vienen de fixtures anonimizadas con
        montos reales: ponerles uno lo dejaría junto a datos verdaderos, que es
        la mezcla que después se confunde con dato real. Mismo criterio que ya
        usa `despacho_demo.py` para `fecha_alta`.
        """
        for cliente in CLIENTES:
            for e in semilla(cliente_http, cliente.id)["empleados"]:
                assert e["nss"] == ""

    def test_el_nss_es_opcional_en_el_schema(self):
        # Requerirlo tumbaría la semilla en tiempo de import, y con ella la demo.
        e = EmpleadoCarteraSchema(
            empleado_no="X", nombre="X",
            salario_diario="450", salario_diario_integrado="473",
        )
        assert e.nss == ""


class TestPrestaciones:
    def test_los_minimos_de_ley_son_el_default(self):
        p = PrestacionesSchema()
        assert p.dias_aguinaldo == 15
        assert p.prima_vacacional == pytest.approx(0.25)

    def test_un_aguinaldo_por_debajo_del_minimo_se_rechaza(self):
        # Art. 87 LFT. Un aguinaldo menor subintegraría el SBC y las cuotas.
        with pytest.raises(ValidationError):
            PrestacionesSchema(dias_aguinaldo=10)

    def test_una_prima_como_porcentaje_se_rechaza(self):
        # 25 en vez de 0.25 infla el SBC 77% sin que ninguna tabla lo detecte.
        with pytest.raises(ValidationError):
            PrestacionesSchema(prima_vacacional=25)

    def test_las_vacaciones_en_cero_caen_a_las_de_ley_de_su_antiguedad(self):
        # Art. 76 LFT reformado: 12 el primer año, +2 por año hasta el quinto.
        assert PrestacionesSchema().vacaciones_efectivas(0) == 12
        assert PrestacionesSchema().vacaciones_efectivas(3) == 16

    def test_las_vacaciones_capturadas_ganan_sobre_las_de_ley(self):
        # Prestación superior: la ley es piso, no techo.
        assert PrestacionesSchema(dias_vacaciones=30).vacaciones_efectivas(0) == 30


class TestTipoDeContrato:
    def test_los_cuatro_tipos_del_art_35_lft(self):
        assert {t.value for t in TipoContrato} == {
            "indeterminado", "determinado", "obra_determinada", "prueba",
        }

    def test_el_default_es_indeterminado(self):
        e = EmpleadoCarteraSchema(
            empleado_no="X", nombre="X",
            salario_diario="450", salario_diario_integrado="473",
        )
        assert e.tipo_contrato == TipoContrato.INDETERMINADO
