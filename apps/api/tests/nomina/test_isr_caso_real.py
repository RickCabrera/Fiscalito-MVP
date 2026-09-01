"""
ISR y exenciones contra el caso real de S-04.

EL RESULTADO, EN UNA LÍNEA
--------------------------
**El motor reproduce al centavo los 28 recibos de abril, sin excepciones.**
Marzo cuadra en 6 de 35 y mayo en 0 de 7.

Marzo falla por dos causas que se acumulan: el CFDI declara ahí un subsidio de
**$123.47** en vez de los $123.34 que da la fórmula del articulado, y el tope
de ingresos todavía no mordía. **Cuidado con la causa del $123.47**: es
compatible con DOS bases que no se distinguen al centavo —el peso de los
considerandos del decreto ($536.22) y el transitorio de enero arrastrado sin
refrescar ($536.21)— y las fixtures no traen recibos de enero para desempatar.
Ver §D15; no se afirma cuál fue.

Lo que sí es un hecho es que desde abril el subsidio declarado es $123.34, que
es exactamente lo que calcula el motor.

LO QUE ESTE ARCHIVO NO PUEDE PROBAR
-----------------------------------
Las fixtures van del 8-mar al 3-may-2026, así que **ninguna vigencia de enero**
se ejercita aquí: ni la UMA 2025 en las exenciones ni el porcentaje transitorio
del subsidio. Eso solo lo prueban los tests unitarios de `test_isr_nomina.py`.

Y sobre la prima dominical: los 45 importes observados ($79.00 y $92.01) están
**los dos por debajo de 1 UMA** ($117.31), así que este archivo confirma que la
exención se aplica pero **no puede distinguir un tope de 1 UMA de uno de 15, de
30, ni de 1 salario mínimo**. Esa distinción es de `test_isr_nomina.py`.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.nomina_engine.isr_nomina import (
    ContextoExencion,
    Percepcion,
    base_gravable,
    isr_retenido,
)
from app.redondeo import redondear

NS = {"cfdi": "http://www.sat.gob.mx/cfd/4", "n": "http://www.sat.gob.mx/nomina12"}
FIXTURES = Path(__file__).parent.parent / "fixtures" / "nomina"
DIAS_MES_FISCAL = Decimal("30.4")

# Cuadre por mes, verificado recibo por recibo contra el ISR timbrado.
CUADRE_POR_MES = {"2026-03": (6, 35), "2026-04": (28, 28), "2026-05": (0, 7)}

# `SubsidioCausado` que declara el propio CFDI, por mes. La base cambia en el
# corte marzo→abril: $536.22 (considerandos) → $535.65 (fórmula). Ver §D15.
SUBSIDIO_DECLARADO = {
    "2026-03": {Decimal("123.47")},
    "2026-04": {Decimal("123.34")},
    "2026-05": {Decimal("103.73"), Decimal("127.05")},
}


def _recibos():
    for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
        raiz = ET.parse(ruta).getroot()
        nomina = raiz.find(".//n:Nomina", NS)
        if nomina is None:
            continue
        receptor = nomina.find("n:Receptor", NS)
        nodos_isr = [
            d for d in nomina.findall(".//n:Deduccion", NS)
            if d.attrib["TipoDeduccion"] == "002"
        ]
        subsidio = nomina.find(".//n:SubsidioAlEmpleo", NS)
        yield {
            "rfc": raiz.find("cfdi:Receptor", NS).attrib["Rfc"],
            "fecha": date.fromisoformat(nomina.attrib["FechaPago"]),
            "sbc": Decimal(receptor.attrib["SalarioBaseCotApor"]),
            "dias": int(Decimal(nomina.attrib["NumDiasPagados"])),
            "percepciones": tuple(
                Percepcion(
                    p.attrib["TipoPercepcion"],
                    p.attrib["Concepto"],
                    Decimal(p.attrib["ImporteGravado"]) + Decimal(p.attrib["ImporteExento"]),
                )
                for p in nomina.findall(".//n:Percepcion", NS)
            ),
            "gravado_timbrado": sum(
                Decimal(p.attrib["ImporteGravado"])
                for p in nomina.findall(".//n:Percepcion", NS)
            ),
            "exento_timbrado": sum(
                Decimal(p.attrib["ImporteExento"])
                for p in nomina.findall(".//n:Percepcion", NS)
            ),
            # None y 0.00 no son lo mismo: 5 recibos no traen el nodo de ISR.
            "isr_timbrado": Decimal(nodos_isr[0].attrib["Importe"]) if nodos_isr else None,
            "subsidio_declarado": (
                Decimal(subsidio.attrib["SubsidioCausado"]) if subsidio is not None else None
            ),
        }


def _isr_calculado(recibo) -> Decimal:
    """
    ISR que da el motor. El ingreso mensual sale de `SBC × 30.4`, que es la
    lectura de §D11 que el caso real respalda (las otras dos quedan refutadas).
    """
    return isr_retenido(
        recibo["gravado_timbrado"],
        "02",
        recibo["fecha"],
        redondear(recibo["sbc"] * DIAS_MES_FISCAL),
        recibo["dias"],
    ).retenido


class TestExenciones:
    """La exención sí cuadra en el 100 % de los recibos que la ejercitan."""

    def test_el_gravado_y_el_exento_del_motor_coinciden_con_el_timbrado(self):
        for recibo in _recibos():
            _, base = base_gravable(
                recibo["percepciones"], ContextoExencion(fecha=recibo["fecha"])
            )
            assert base == recibo["gravado_timbrado"], recibo["rfc"]

    def test_los_cuarenta_y_cinco_recibos_con_prima_dominical(self):
        con_prima = [
            r for r in _recibos()
            if any(p.clave == "020" for p in r["percepciones"])
        ]
        assert len(con_prima) == 45
        for recibo in con_prima:
            desglose, _ = base_gravable(
                recibo["percepciones"], ContextoExencion(fecha=recibo["fecha"])
            )
            prima = next(d for d in desglose if d.clave == "020")
            assert prima.exento == prima.importe
            assert prima.gravado == Decimal("0.00")

    def test_la_prima_dominical_es_el_25_por_ciento_de_un_dia(self):
        """
        Corrobora la suposición de **un domingo por recibo semanal**, que el
        CFDI no trae: la prima dominical es el 25 % del salario del día
        (Art. 71 LFT), y el salario diario es el sueldo gravado entre 7.
        """
        for recibo in _recibos():
            primas = [p for p in recibo["percepciones"] if p.clave == "020"]
            if not primas:
                continue
            sueldo = next(p for p in recibo["percepciones"] if p.clave == "001")
            esperada = redondear(sueldo.importe / 7 * Decimal("0.25"))
            assert primas[0].importe == esperada


class TestCuadreDelISR:
    def test_abril_cuadra_completo(self):
        """Los 28 recibos de abril, al centavo, sin excepciones."""
        de_abril = [r for r in _recibos() if r["fecha"].month == 4]
        assert len(de_abril) == 28
        for recibo in de_abril:
            assert _isr_calculado(recibo) == recibo["isr_timbrado"], (
                f"{recibo['rfc']} {recibo['fecha']}"
            )

    def test_cuadre_por_mes(self):
        """
        El conteo honesto. Marzo falla por la base del subsidio y por el tope
        que todavía no mordía; mayo son recibos de otra naturaleza (§D15).
        """
        conteo = defaultdict(lambda: [0, 0])
        for recibo in _recibos():
            mes = recibo["fecha"].strftime("%Y-%m")
            conteo[mes][1] += 1
            if recibo["isr_timbrado"] is not None and _isr_calculado(recibo) == recibo[
                "isr_timbrado"
            ]:
                conteo[mes][0] += 1
        assert {m: tuple(v) for m, v in conteo.items()} == CUADRE_POR_MES


class TestElSubsidioDeclaradoPorElCFDI:
    """
    §D15. El CFDI declara `SubsidioCausado` y ahí se ve el cambio de base.
    """

    def test_el_subsidio_de_marzo_no_es_el_de_la_formula(self):
        """
        $123.47 no es lo que da la fórmula del articulado ($123.34), y es
        compatible con DOS bases que no se distinguen al centavo: el peso de
        los considerandos ($536.22) y el transitorio de enero ($536.21)
        arrastrado sin refrescar el 1 de febrero. Este test afirma la
        ambigüedad, no una de las dos causas.
        """
        assert SUBSIDIO_DECLARADO["2026-03"] == {Decimal("123.47")}
        assert redondear(Decimal("536.22") / DIAS_MES_FISCAL * 7) == Decimal("123.47")
        assert redondear(Decimal("536.21") / DIAS_MES_FISCAL * 7) == Decimal("123.47")
        assert redondear(Decimal("535.65") / DIAS_MES_FISCAL * 7) == Decimal("123.34")

    def test_abril_usa_el_que_da_la_formula_del_articulado(self):
        """$535.65 / 30.4 × 7 = $123.34 — lo que calcula el motor."""
        assert SUBSIDIO_DECLARADO["2026-04"] == {Decimal("123.34")}
        assert redondear(Decimal("535.65") / DIAS_MES_FISCAL * 7) == Decimal("123.34")

    def test_el_cambio_de_base_esta_en_el_cfdi(self):
        declarado = defaultdict(set)
        for recibo in _recibos():
            if recibo["subsidio_declarado"] is not None:
                declarado[recibo["fecha"].strftime("%Y-%m")].add(
                    recibo["subsidio_declarado"]
                )
        assert dict(declarado) == SUBSIDIO_DECLARADO

    def test_el_cfdi_de_marzo_es_internamente_inconsistente(self):
        """
        En marzo el ISR retenido **no** es `causado − SubsidioCausado` del propio
        comprobante: el subsidio implícito en la retención (123.34 / 123.35) no
        es el declarado (123.47). El comprobante se contradice a sí mismo.
        """
        for recibo in _recibos():
            if recibo["fecha"].month != 3 or recibo["isr_timbrado"] is None:
                continue
            causado = isr_retenido(
                recibo["gravado_timbrado"], "02", recibo["fecha"],
                Decimal("0"), recibo["dias"],
            ).causado
            implicito = causado - recibo["isr_timbrado"]
            if implicito <= Decimal("0"):
                continue  # semanas de ajuste, otra naturaleza
            assert implicito != recibo["subsidio_declarado"]
            assert implicito in {Decimal("123.34"), Decimal("123.35"), Decimal("194.01")}


class TestCaracterizacionDeLoQueNoCuadra:
    def test_cinco_recibos_no_traen_nodo_de_isr(self):
        """`None` y $0.00 no son lo mismo: sin esta distinción el conteo miente."""
        sin_nodo = [r for r in _recibos() if r["isr_timbrado"] is None]
        assert len(sin_nodo) == 5
        assert {r["fecha"].month for r in sin_nodo} == {3}

    def test_mayo_son_recibos_de_otra_naturaleza(self):
        """
        HIPÓTESIS, no hallazgo: parecen semanas de ajuste mensual de ISR. Lo
        que sí es un hecho es que su `SubsidioCausado` **varía por empleado**
        ($103.73 y $127.05), cosa que el esquema plano de 2024 no produce, y
        que $127.05 es mayor que el subsidio semanal de quienes en abril no
        recibieron nada. F1-04 no implementa el ajuste mensual: no está en su
        alcance.
        """
        de_mayo = [r for r in _recibos() if r["fecha"].month == 5]
        assert len(de_mayo) == 7
        assert {r["subsidio_declarado"] for r in de_mayo} == SUBSIDIO_DECLARADO["2026-05"]
        for recibo in de_mayo:
            assert _isr_calculado(recibo) != recibo["isr_timbrado"]

    @pytest.mark.parametrize(
        "rfc,sbc,sobre_el_tope",
        [
            ("XACC010101AA3", "399.52", True),
            ("XADD010101AA4", "399.05", True),
            ("XAGG010101AA7", "387.23", True),
            ("XAII010101AA9", "358.34", False),
            ("XAHH010101AA8", "331.58", False),
        ],
    )
    def test_el_tope_del_subsidio_separa_a_los_empleados_en_abril(
        self, rfc, sbc, sobre_el_tope
    ):
        """
        §D11. `SBC × 30.4` contra el tope de $11,492.66 separa exactamente a
        los tres empleados a los que el patrón dejó de dar subsidio en abril.
        Las otras dos lecturas de D11 quedan refutadas: proyectar el gravado
        semanal da $11,188.72 y acumular el mes calendario da $10,305.40, y las
        dos predicen subsidio para esos tres.
        """
        mensual = redondear(Decimal(sbc) * DIAS_MES_FISCAL)
        assert (mensual > Decimal("11492.66")) is sobre_el_tope
        de_abril = [
            r for r in _recibos() if r["rfc"] == rfc and r["fecha"].month == 4
        ]
        for recibo in de_abril:
            resultado = isr_retenido(
                recibo["gravado_timbrado"], "02", recibo["fecha"], mensual, recibo["dias"]
            )
            assert (resultado.subsidio == Decimal("0.00")) is sobre_el_tope
            assert resultado.retenido == recibo["isr_timbrado"]
