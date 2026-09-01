"""
Cuotas contra el caso real de S-04.

QUÉ CUADRA, CON EL NÚMERO EXACTO
--------------------------------
**5 de los 70 recibos.** Todos del empleado `XAHH010101AA8` y todos de abril y
mayo. Ni uno de marzo.

La razón es un hallazgo sobre D2, no un defecto del motor: el software del
patrón usó **redondeo sobre el agregado** hasta marzo y **por concepto** desde
abril. Ese empleado tiene $55.13 en sus cuatro recibos de marzo y $55.12 en los
cinco siguientes, con el mismo SBC y los mismos 7 días — y esos son, al
centavo, los dos órdenes admisibles. El motor aplica D2 (por concepto), así que
empata con la segunda mitad y no con la primera.

QUÉ NO CUADRA, Y POR QUÉ NO ES CULPA DEL MOTOR
-----------------------------------------------
Los otros 8 empleados no se reproducen desde el `SalarioBaseCotApor` timbrado
en su propio CFDI, y tres de ellos tienen una deducción **por debajo del mínimo
legal** que impone ese SBC. Ninguna fórmula puede hacer que un número baje: la
base con la que el patrón determinó la cuota no es la que timbró. Evidencia
completa en `docs/decisiones-nomina.md` §D14.

POR QUÉ NO HAY xfail
--------------------
`xfail` significa "nuestro código está mal y algún día pasará". No es el caso:
el código está bien y el dato es inconsistente. Y si alguien aflojara una tasa
para forzar el cuadre, un `xfail` se volvería XPASS **en silencio**. Aquí todo
pasa, y la caracterización truena si el motor cambia.
"""

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.ceav import CEAV_OBRERO
from app.nomina_engine.cuotas import DiasDelPeriodo, cuotas_empleado
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.tablas_imss import BaseCuota, cuotas_ramos_vigentes
from app.redondeo import redondear

NS = {"cfdi": "http://www.sat.gob.mx/cfd/4", "n": "http://www.sat.gob.mx/nomina12"}
FIXTURES = Path(__file__).parent.parent / "fixtures" / "nomina"
GENERAL = ZonaSalarioMinimo.GENERAL
PRIMA_RT = Decimal("0.0054355")  # prima media clase I; el CFDI trae RiesgoPuesto=1
UN_MARZO = date(2026, 3, 8)

# Los únicos recibos del caso real que el motor reproduce al centavo.
RECIBOS_QUE_CUADRAN = {
    ("XAHH010101AA8", date(2026, 4, 5)),
    ("XAHH010101AA8", date(2026, 4, 12)),
    ("XAHH010101AA8", date(2026, 4, 19)),
    ("XAHH010101AA8", date(2026, 4, 26)),
    ("XAHH010101AA8", date(2026, 5, 3)),
}

# (SBC timbrado, deducción observada en marzo, cuota obrera que da el motor).
# Los tres son literales: los observados registran el hallazgo y el calculado
# fija la salida del motor, para que un cambio silencioso no pase.
CASO_REAL = {
    "XAAA010101AA1": (Decimal("331.58"), Decimal("55.13"), Decimal("55.12")),
    "XABB010101AA2": (Decimal("357.44"), Decimal("57.09"), Decimal("59.58")),
    "XACC010101AA3": (Decimal("399.52"), Decimal("68.10"), Decimal("67.75")),
    "XADD010101AA4": (Decimal("399.05"), Decimal("66.63"), Decimal("67.67")),
    "XAEE010101AA5": (Decimal("343.00"), Decimal("57.28"), Decimal("57.02")),
    "XAFF010101AA6": (Decimal("346.11"), Decimal("57.06"), Decimal("57.55")),
    "XAGG010101AA7": (Decimal("387.23"), Decimal("64.46"), Decimal("65.36")),
    "XAHH010101AA8": (Decimal("331.58"), Decimal("55.13"), Decimal("55.12")),
    "XAII010101AA9": (Decimal("358.34"), Decimal("57.21"), Decimal("59.76")),
}

# Los tres cuya deducción está POR DEBAJO del mínimo legal de su propio SBC.
BAJO_EL_PISO = {"XABB010101AA2", "XAFF010101AA6", "XAII010101AA9"}


def _recibos():
    """(rfc, fecha_pago, sbc, dias, deduccion_imss_timbrada) de cada CFDI."""
    for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
        raiz = ET.parse(ruta).getroot()
        nomina = raiz.find(".//n:Nomina", NS)
        if nomina is None:
            continue
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
        receptor = nomina.find("n:Receptor", NS)
        yield (
            raiz.find("cfdi:Receptor", NS).attrib["Rfc"],
            date.fromisoformat(nomina.attrib["FechaPago"]),
            Decimal(receptor.attrib["SalarioBaseCotApor"]),
            int(Decimal(nomina.attrib["NumDiasPagados"])),
            imss,
        )


def _obrera_calculada(sbc: Decimal, dias: int, fecha: date, zona=GENERAL) -> Decimal:
    return cuotas_empleado(
        clamp_sbc(sbc, fecha, zona), DiasDelPeriodo(dias), fecha, zona, PRIMA_RT
    ).total_obrero


class TestCuadreContraElTimbrado:
    """Compara contra el importe del CFDI, no contra el motor."""

    def test_hay_setenta_recibos(self):
        assert len(list(_recibos())) == 70

    def test_cuadran_exactamente_cinco_recibos(self):
        """
        El conteo honesto. Si sube, alguien cambió el motor o las fixtures y
        hay que explicar cuál de las dos cosas.
        """
        cuadran = {
            (rfc, fecha)
            for rfc, fecha, sbc, dias, timbrada in _recibos()
            if _obrera_calculada(sbc, dias, fecha) == timbrada
        }
        assert cuadran == RECIBOS_QUE_CUADRAN

    def test_el_unico_empleado_que_cuadra_lo_hace_solo_desde_abril(self):
        """
        `XAHH010101AA8`: mismo SBC y mismos 7 días todo el bimestre, pero la
        deducción cambia de $55.13 a $55.12 en el corte marzo→abril. El motor
        (D2, por concepto) empata con abril y no con marzo.
        """
        recibos = [r for r in _recibos() if r[0] == "XAHH010101AA8"]
        assert len(recibos) == 9
        for _, fecha, sbc, dias, timbrada in recibos:
            calculada = _obrera_calculada(sbc, dias, fecha)
            assert calculada == Decimal("55.12")
            assert timbrada == (
                Decimal("55.13") if fecha.month == 3 else Decimal("55.12")
            )

    def test_el_otro_empleado_de_ese_sbc_no_cuadra_en_ninguno(self):
        """
        `XAAA010101AA1` tiene el mismo SBC pero causa baja el 29 de marzo, así
        que **todos** sus recibos son del periodo de redondeo agregado: cero de
        cuatro. Que dos empleados con SBC idéntico cuadren distinto es la
        prueba más limpia de que lo que cambió fue el criterio del software,
        no el dato del trabajador.
        """
        recibos = [r for r in _recibos() if r[0] == "XAAA010101AA1"]
        assert len(recibos) == 4
        assert {fecha.month for _, fecha, _, _, _ in recibos} == {3}
        for _, fecha, sbc, dias, timbrada in recibos:
            assert timbrada == Decimal("55.13")
            assert _obrera_calculada(sbc, dias, fecha) != timbrada


class TestLosDosOrdenesDeRedondeo:
    """HALLAZGO SOBRE D2: la evidencia más directa que da el caso real."""

    def test_los_dos_valores_son_los_dos_ordenes_admisibles(self):
        tasa_obrera = sum(
            (r.obrero for r in cuotas_ramos_vigentes(UN_MARZO) if r.base is BaseCuota.SBC),
            start=Decimal("0"),
        ) + CEAV_OBRERO[2026]
        sbc = Decimal("331.58")
        assert redondear(sbc * 7 * tasa_obrera) == Decimal("55.13")  # agregado
        assert _obrera_calculada(sbc, 7, UN_MARZO) == Decimal("55.12")  # por concepto

    def test_el_quiebre_es_marzo_abril_y_es_permanente(self):
        por_fecha = {
            fecha: imss for rfc, fecha, _, _, imss in _recibos() if rfc == "XAHH010101AA8"
        }
        assert {v for f, v in por_fecha.items() if f.month == 3} == {Decimal("55.13")}
        assert {v for f, v in por_fecha.items() if f.month > 3} == {Decimal("55.12")}


class TestCaracterizacionDelHallazgo:
    """
    Registro ejecutable de que el dato de entrada es inconsistente (§D14).

    Si estos tests fallan es porque alguien cambió el motor: hay que explicar
    qué y por qué, no ajustar los literales.
    """

    @pytest.mark.parametrize("rfc", sorted(set(CASO_REAL) - {"XAHH010101AA8"}))
    def test_la_deduccion_de_marzo_no_se_reproduce(self, rfc):
        sbc, observada, calculada_esperada = CASO_REAL[rfc]
        calculada = _obrera_calculada(sbc, 7, UN_MARZO)
        assert calculada == calculada_esperada, (
            f"cambió la salida del motor para {rfc}: explica qué cambió antes de "
            f"actualizar este literal (§D14)"
        )
        assert calculada != observada

    @pytest.mark.parametrize("rfc", sorted(BAJO_EL_PISO))
    def test_hay_deducciones_por_debajo_del_minimo_legal(self, rfc):
        """
        La prueba de que el problema es el dato y no la fórmula: ningún ramo
        omitido, día faltante ni excedente puede hacer que la cuota BAJE del
        mínimo que impone el SBC timbrado.
        """
        sbc, observada, _ = CASO_REAL[rfc]
        assert observada < _obrera_calculada(sbc, 7, UN_MARZO)

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
