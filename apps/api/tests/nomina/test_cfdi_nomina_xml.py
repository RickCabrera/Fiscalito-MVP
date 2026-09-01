"""
Generación del CFDI de nómina y validación contra los XSD versionados.

QUÉ MIDE CADA CLASE
-------------------
`TestTotales` alimenta el serializador con **las partidas del propio CFDI
timbrado** y exige que reproduzca sus totales en los **70 de 70**. Es
aritmética pura: si aquí falla algo, es bug del generador, no material de
caracterización.

`TestValidacionXSD` genera un pre-recibo y lo valida sin red.

Lo que este archivo **no** mide es el camino de cálculo —cuánto ISR y cuánta
cuota obrera— que ya está medido en `test_cuotas_caso_real.py` (5 de 70, §D14)
y `test_isr_caso_real.py` (28 de 28 en abril, §D15). F1-05 no re-litiga esos
números.
"""

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.nomina_engine.cfdi_nomina_xml import (
    NO_CERTIFICADO_SIN_TIMBRAR,
    SELLO_SIN_TIMBRAR,
    generar_cfdi_nomina,
)
from app.nomina_engine.recibo import (
    DatosPatron,
    DatosTrabajador,
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)
from tests.nomina.validacion_xsd import errores_de_validacion

NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "n": "http://www.sat.gob.mx/nomina12",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "nomina"

PATRON = DatosPatron(
    rfc="XAP0101011X0",
    nombre="PATRON DEMO SA DE CV",
    regimen_fiscal="601",
    registro_patronal="X1234567890",
    codigo_postal="91090",
)
TRABAJADOR = DatosTrabajador(
    rfc="XACC010101AA3",
    nombre="CARLA DENISSE XOLO PEREZ",
    curp="XACC010101HVZBBB03",
    numero_seguridad_social="01010101033",
    codigo_postal="91020",
    fecha_inicio_relacion_laboral=date(2024, 5, 26),
    antiguedad="P97W",
    tipo_contrato="01",
    tipo_regimen="02",
    numero_empleado="E-03",
    departamento="OPERACIONES",
    puesto="OPERATIVO",
    riesgo_puesto="2",
    periodicidad_pago="02",
    salario_base_cotizacion=Decimal("399.52"),
    salario_diario_integrado=Decimal("399.52"),
)


def _recibo_ejemplo() -> Recibo:
    return Recibo(
        percepciones=(
            PartidaPercepcion("001", "P001", "SUELDO", Decimal("2576.35"), Decimal("0.00")),
            PartidaPercepcion(
                "020", "P019", "PRIMA DOMINICAL", Decimal("0.00"), Decimal("92.01")
            ),
        ),
        deducciones=(
            PartidaDeduccion("002", "D001", "ISR", Decimal("197.66")),
            PartidaDeduccion("001", "D002", "IMSS", Decimal("68.09")),
        ),
        otros_pagos=(
            PartidaOtroPago(
                "002", "D100", "SUBSIDIO PARA EL EMPLEO", Decimal("0.00"), Decimal("123.34")
            ),
        ),
    )


def _generar(recibo: Recibo) -> str:
    return generar_cfdi_nomina(
        recibo,
        PATRON,
        TRABAJADOR,
        datetime(2026, 4, 5, 12, 0, 0),
        date(2026, 3, 30),
        date(2026, 4, 5),
        date(2026, 4, 5),
        Decimal("7"),
        serie="DEMOSA",
        folio="37",
    )


def _partidas_del_cfdi(ruta: Path):
    """Reconstruye el recibo a partir del CFDI timbrado, sin calcular nada."""
    nomina = ET.parse(ruta).getroot().find(".//n:Nomina", NS)
    percepciones = tuple(
        PartidaPercepcion(
            p.attrib["TipoPercepcion"],
            p.attrib["Clave"],
            p.attrib["Concepto"],
            Decimal(p.attrib["ImporteGravado"]),
            Decimal(p.attrib["ImporteExento"]),
        )
        for p in nomina.findall(".//n:Percepcion", NS)
    )
    deducciones = tuple(
        PartidaDeduccion(
            d.attrib["TipoDeduccion"],
            d.attrib["Clave"],
            d.attrib["Concepto"],
            Decimal(d.attrib["Importe"]),
        )
        for d in nomina.findall(".//n:Deduccion", NS)
    )
    otros = []
    for o in nomina.findall(".//n:OtroPago", NS):
        subsidio = o.find("n:SubsidioAlEmpleo", NS)
        otros.append(
            PartidaOtroPago(
                o.attrib["TipoOtroPago"],
                o.attrib["Clave"],
                o.attrib["Concepto"],
                Decimal(o.attrib["Importe"]),
                Decimal(subsidio.attrib["SubsidioCausado"]) if subsidio is not None else None,
            )
        )
    return Recibo(percepciones, deducciones, tuple(otros)), nomina


def _recibos_del_caso_real():
    for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
        yield ruta, *_partidas_del_cfdi(ruta)


class TestTotales:
    """
    Los totales se comparan como `Decimal`, nunca como cadena: el caso real
    emite `TotalOtrosPagos="0"` y el generador `"0.00"`, y las dos son válidas.
    """

    def test_hay_setenta_recibos(self):
        assert len(list(_recibos_del_caso_real())) == 70

    def test_los_totales_del_complemento_cuadran_en_los_setenta(self):
        for ruta, recibo, nomina in _recibos_del_caso_real():
            atributos = nomina.attrib
            assert recibo.total_percepciones == Decimal(atributos["TotalPercepciones"]), ruta
            assert recibo.total_deducciones == Decimal(atributos["TotalDeducciones"]), ruta
            assert recibo.total_otros_pagos == Decimal(atributos["TotalOtrosPagos"]), ruta

    def test_los_totales_de_percepciones_cuadran_en_los_setenta(self):
        for ruta, recibo, nomina in _recibos_del_caso_real():
            nodo = nomina.find("n:Percepciones", NS).attrib
            assert recibo.total_gravado == Decimal(nodo["TotalGravado"]), ruta
            assert recibo.total_exento == Decimal(nodo["TotalExento"]), ruta
            assert recibo.total_sueldos == Decimal(nodo["TotalSueldos"]), ruta

    def test_los_totales_de_deducciones_cuadran_en_los_setenta(self):
        for ruta, recibo, nomina in _recibos_del_caso_real():
            nodo = nomina.find("n:Deducciones", NS)
            if nodo is None:
                assert recibo.total_deducciones == Decimal("0.00"), ruta
                continue
            esperado_isr = Decimal(nodo.attrib.get("TotalImpuestosRetenidos", "0"))
            esperado_otras = Decimal(nodo.attrib.get("TotalOtrasDeducciones", "0"))
            assert recibo.total_impuestos_retenidos == esperado_isr, ruta
            assert recibo.total_otras_deducciones == esperado_otras, ruta

    def test_los_totales_del_comprobante_cuadran_en_los_setenta(self):
        """`SubTotal = percepciones + otros pagos`, `Descuento = deducciones`."""
        for ruta, recibo, _ in _recibos_del_caso_real():
            comprobante = ET.parse(ruta).getroot().attrib
            assert recibo.subtotal == Decimal(comprobante["SubTotal"]), ruta
            assert recibo.descuento == Decimal(comprobante["Descuento"]), ruta
            assert recibo.total == Decimal(comprobante["Total"]), ruta


class TestValidacionXSD:
    def test_el_pre_recibo_generado_valida(self):
        assert errores_de_validacion(_generar(_recibo_ejemplo())) == []

    def test_las_setenta_fixtures_validan(self):
        """
        Ancla del propio validador: si estas dejaran de validar, el problema
        sería del esquema o del resolver, no del generador.
        """
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            assert errores_de_validacion(ruta.read_bytes()) == [], ruta

    def test_el_xsd_rechaza_un_xml_bien_formado_pero_invalido(self):
        """
        La validación no es decorativa. El XML tiene que estar **bien formado**
        para que el error venga del esquema y no del parser: un XML roto
        truena antes de llegar al XSD y el test pasaría sin ejercitarlo.

        Aquí `TipoNomina="X"` está fuera del catálogo `c_TipoNomina`.
        """
        xml = _generar(_recibo_ejemplo()).replace('TipoNomina="O"', 'TipoNomina="X"')
        errores = errores_de_validacion(xml)
        assert errores
        assert any("TipoNomina" in e for e in errores)

    def test_el_xsd_rechaza_un_nodo_sin_sus_totales(self):
        xml = _generar(_recibo_ejemplo()).replace('TotalGravado="2576.35" ', "")
        assert errores_de_validacion(xml)


class TestNoEstaTimbrado:
    """
    Las salvaguardas que sobreviven a una reserialización.

    El comentario de cabecera es cortesía: cualquier reparseo lo borra. Lo que
    hace inconfundible al pre-recibo es la ausencia del timbre y los centinelas
    en los atributos de sello.
    """

    def test_no_lleva_timbre_fiscal_digital(self):
        """
        Aquí muere la confusión: un CFDI timbrado siempre lo trae, con su UUID.
        El XSD no lo exige —`Complemento` es un wildcard— así que su ausencia
        es legal y verificable.
        """
        raiz = ET.fromstring(_generar(_recibo_ejemplo()))
        assert raiz.find(".//tfd:TimbreFiscalDigital", NS) is None

    def test_las_fixtures_timbradas_si_lo_llevan(self):
        """Contraste: lo que sí trae un CFDI timbrado, para que el test anterior signifique algo."""
        ruta = next(iter(sorted(FIXTURES.glob("semana-01/*.xml"))))
        assert ET.parse(ruta).getroot().find(".//tfd:TimbreFiscalDigital", NS) is not None

    def test_los_atributos_de_sello_son_centinelas(self):
        raiz = ET.fromstring(_generar(_recibo_ejemplo()))
        assert raiz.attrib["Sello"] == SELLO_SIN_TIMBRAR
        assert raiz.attrib["Certificado"] == SELLO_SIN_TIMBRAR
        assert raiz.attrib["NoCertificado"] == NO_CERTIFICADO_SIN_TIMBRAR
        assert "SIN-TIMBRAR" in raiz.attrib["Sello"]

    def test_el_comentario_de_cabecera_avisa(self):
        assert "PRE-RECIBO SIN TIMBRAR" in _generar(_recibo_ejemplo())


class TestEstructura:
    def test_la_clave_interna_no_se_deriva_del_tipo_de_catalogo(self):
        """
        En el caso real conviven `Clave="P019"` con `TipoPercepcion="020"`.
        Derivar una de la otra emitiría claves equivocadas.
        """
        raiz = ET.fromstring(_generar(_recibo_ejemplo()))
        prima = next(
            p
            for p in raiz.findall(".//n:Percepcion", NS)
            if p.attrib["TipoPercepcion"] == "020"
        )
        assert prima.attrib["Clave"] == "P019"

    def test_la_antiguedad_lleva_dieresis(self):
        """Si un editor la rompe, el atributo deja de existir y el XSD lo caza."""
        receptor = ET.fromstring(_generar(_recibo_ejemplo())).find(".//n:Receptor", NS)
        assert receptor.attrib["Antigüedad"] == "P97W"

    def test_el_subsidio_va_en_otros_pagos_con_su_causado(self):
        raiz = ET.fromstring(_generar(_recibo_ejemplo()))
        otro = raiz.find(".//n:OtroPago", NS)
        assert otro.attrib["TipoOtroPago"] == "002"
        assert Decimal(otro.attrib["Importe"]) == Decimal("0.00")
        subsidio = otro.find("n:SubsidioAlEmpleo", NS)
        assert Decimal(subsidio.attrib["SubsidioCausado"]) == Decimal("123.34")

    def test_el_concepto_usa_la_clave_de_nomina(self):
        concepto = ET.fromstring(_generar(_recibo_ejemplo())).find(".//cfdi:Concepto", NS)
        assert concepto.attrib["ClaveProdServ"] == "84111505"
        assert concepto.attrib["ClaveUnidad"] == "ACT"

    def test_un_recibo_sin_percepciones_no_se_arma(self):
        from app.exceptions import FiscalValidationError

        with pytest.raises(FiscalValidationError):
            Recibo(percepciones=())
