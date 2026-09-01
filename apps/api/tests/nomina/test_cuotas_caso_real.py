"""
Cuotas contra el caso real de S-04.

QUÉ PRUEBA ESTE ARCHIVO Y QUÉ NO
--------------------------------
La deducción de IMSS del caso real **no es reproducible** desde el
`SalarioBaseCotApor` timbrado en el propio CFDI: 7 de 9 empleados no cuadran, y
tres de ellos tienen una deducción **por debajo del mínimo legal**, cosa que
ninguna fórmula puede producir. El problema está en el dato de entrada, no en
el motor. La evidencia completa está en `docs/decisiones-nomina.md` §D14.

Por eso aquí hay dos clases de test, **las dos pasan**, ningún skip ni xfail:

1. `TestCuadreEstricto` — los dos empleados que sí cuadran, las nueve semanas,
   con literales. Es un cuadre real contra el caso real, solo que más angosto.
2. `TestCaracterizacionDelHallazgo` — los siete que no cuadran, con sus
   importes observados como literales. Si alguien "arregla" el motor y estos
   empiezan a cuadrar, el test truena y obliga a explicar qué cambió. No es un
   test de que el motor esté mal: es el registro ejecutable de que el dato lo
   está.

Un `xfail` habría sido peor que inútil: significa "nuestro código está mal y
algún día pasará", y si alguien aflojara una tasa para forzar el cuadre se
volvería XPASS en silencio.
"""

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.cuotas import DiasDelPeriodo, cuotas_empleado
from app.nomina_engine.integracion import clamp_sbc
from app.redondeo import redondear

NS = {"cfdi": "http://www.sat.gob.mx/cfd/4", "n": "http://www.sat.gob.mx/nomina12"}
FIXTURES = Path(__file__).parent.parent / "fixtures" / "nomina"
GENERAL = ZonaSalarioMinimo.GENERAL
PRIMA_RT = Decimal("0.0054355")  # prima media clase I; el CFDI trae RiesgoPuesto=1

# Los dos empleados cuya deducción sí se reproduce con la fórmula de ley.
CUADRAN = {"XAAA010101AA1", "XAHH010101AA8"}

# Deducción observada de los que NO cuadran, por RFC sintético. Literales a
# propósito: son el registro del hallazgo (D14).
NO_CUADRAN = {
    "XABB010101AA2": (Decimal("357.44"), Decimal("57.09")),
    "XACC010101AA3": (Decimal("399.52"), Decimal("68.10")),
    "XADD010101AA4": (Decimal("399.05"), Decimal("66.63")),
    "XAEE010101AA5": (Decimal("343.00"), Decimal("57.28")),
    "XAFF010101AA6": (Decimal("346.11"), Decimal("57.06")),
    "XAGG010101AA7": (Decimal("387.23"), Decimal("64.46")),
    "XAII010101AA9": (Decimal("358.34"), Decimal("57.21")),
}

# Los tres cuya deducción está POR DEBAJO del mínimo legal. Es la prueba de que
# la base usada no es el SBC timbrado: ningún ramo omitido ni día faltante
# puede hacer que un número baje.
BAJO_EL_PISO = {"XABB010101AA2", "XAFF010101AA6", "XAII010101AA9"}


def _recibos():
    """(rfc, fecha_pago, sbc, dias, deduccion_imss) de cada CFDI de nómina."""
    for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
        raiz = ET.parse(ruta).getroot()
        nomina = raiz.find(".//n:Nomina", NS)
        if nomina is None:
            continue
        rfc = raiz.find("cfdi:Receptor", NS).attrib["Rfc"]
        receptor = nomina.find("n:Receptor", NS)
        imss = next(
            (
                Decimal(d.attrib["Importe"])
                for d in nomina.findall(".//n:Deduccion", NS)
                if d.attrib["TipoDeduccion"] == "001"
            ),
            None,
        )
        if imss is None:
            continue
        yield (
            rfc,
            date.fromisoformat(nomina.attrib["FechaPago"]),
            Decimal(receptor.attrib["SalarioBaseCotApor"]),
            int(float(nomina.attrib["NumDiasPagados"])),
            imss,
        )


def _obrera_calculada(sbc: Decimal, dias: int, fecha: date) -> Decimal:
    acotado = clamp_sbc(sbc, fecha, GENERAL)
    return cuotas_empleado(
        acotado, DiasDelPeriodo(dias), fecha, GENERAL, PRIMA_RT
    ).total_obrero


class TestCuadreEstricto:
    """Los dos empleados que sí se reproducen, con el orden de redondeo fijado."""

    def test_hay_recibos_que_analizar(self):
        assert len(list(_recibos())) == 70

    @pytest.mark.parametrize("rfc", sorted(CUADRAN))
    def test_la_cuota_obrera_se_reproduce(self, rfc):
        """
        Con redondeo por concepto (D2) el motor da $55.12, que es exactamente
        la deducción observada de abril y mayo.
        """
        recibos = [r for r in _recibos() if r[0] == rfc]
        assert recibos, f"sin recibos de {rfc}"
        for _, fecha, sbc, dias, _ in recibos:
            assert _obrera_calculada(sbc, dias, fecha) == Decimal("55.12")

    def test_los_dos_ordenes_de_redondeo_estan_en_el_caso_real(self):
        """
        HALLAZGO SOBRE D2, y la evidencia más directa que da el caso real.

        El empleado XAHH010101AA8 tiene deducción $55.13 en marzo y $55.12 de
        abril en adelante, con el mismo SBC y los mismos 7 días. Esos dos
        valores son, al centavo, los dos órdenes de redondeo admisibles:

            por concepto (D2, lo que hace el motor) → 55.12
            sobre el agregado                      → 55.13

        O sea que el software del patrón cambió de orden de redondeo en el
        corte marzo→abril. No es ruido: es una decisión de redondeo observable.
        """
        por_fecha = {
            fecha: imss for rfc, fecha, _, _, imss in _recibos() if rfc == "XAHH010101AA8"
        }
        marzo = {v for f, v in por_fecha.items() if f.month == 3}
        despues = {v for f, v in por_fecha.items() if f.month > 3}
        assert marzo == {Decimal("55.13")}
        assert despues == {Decimal("55.12")}

        sbc = Decimal("331.58")
        tasa_obrera = Decimal("0.0025") + Decimal("0.00375") + Decimal("0.00625")
        tasa_obrera += Decimal("0.01125")
        assert redondear(sbc * 7 * tasa_obrera) == Decimal("55.13")
        assert _obrera_calculada(sbc, 7, date(2026, 3, 8)) == Decimal("55.12")


class TestCaracterizacionDelHallazgo:
    """
    Registro ejecutable de que el dato de entrada del caso real es inconsistente.

    Ver `docs/decisiones-nomina.md` §D14. Si estos tests empiezan a fallar es
    porque alguien cambió el motor: hay que explicar qué y por qué, no ajustar
    los literales.
    """

    @pytest.mark.parametrize("rfc", sorted(NO_CUADRAN))
    def test_la_deduccion_observada_no_se_reproduce(self, rfc):
        sbc, observada = NO_CUADRAN[rfc]
        calculada = _obrera_calculada(sbc, 7, date(2026, 3, 8))
        assert calculada != observada, (
            f"{rfc} empezó a cuadrar: revisa qué cambió en el motor antes de "
            f"actualizar este test (ver D14)"
        )

    @pytest.mark.parametrize("rfc", sorted(BAJO_EL_PISO))
    def test_hay_deducciones_por_debajo_del_minimo_legal(self, rfc):
        """
        La prueba de que el problema es el dato y no la fórmula: ningún ramo
        omitido, día faltante ni excedente puede hacer que la cuota BAJE del
        mínimo que impone el SBC timbrado.
        """
        sbc, observada = NO_CUADRAN[rfc]
        piso_legal = _obrera_calculada(sbc, 7, date(2026, 3, 8))
        assert observada < piso_legal

    def test_el_caso_real_no_ejercita_enero_ni_ausentismos(self):
        """
        Alcance de S-04, para que nadie asuma que cubre más de lo que cubre:
        las fixtures van de marzo a mayo de 2026, así que **no** ejercitan el
        transitorio de enero (ni el de la UMA ni el del subsidio), y todos los
        recibos traen 7 días pagados, así que **no** validan D3.
        """
        fechas = [fecha for _, fecha, _, _, _ in _recibos()]
        assert min(fechas) == date(2026, 3, 8)
        assert max(fechas) == date(2026, 5, 3)
        assert {dias for _, _, _, dias, _ in _recibos()} == {7}
