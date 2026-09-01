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
    puesto="OPERATIVO",
    departamento="OPERACIONES",
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


def _generar_raiz(recibo: Recibo) -> ET.Element:
    return ET.fromstring(_generar(recibo))


def _datos_del_cfdi(ruta: Path):
    """Emisor, receptor y periodo tal como vienen en el CFDI timbrado."""
    raiz = ET.parse(ruta).getroot()
    nomina = raiz.find(".//n:Nomina", NS)
    emisor = raiz.find("cfdi:Emisor", NS).attrib
    receptor = raiz.find("cfdi:Receptor", NS).attrib
    n_emisor = nomina.find("n:Emisor", NS).attrib
    r = nomina.find("n:Receptor", NS).attrib
    patron = DatosPatron(
        rfc=emisor["Rfc"],
        nombre=emisor["Nombre"],
        regimen_fiscal=emisor["RegimenFiscal"],
        registro_patronal=n_emisor["RegistroPatronal"],
        codigo_postal=raiz.attrib["LugarExpedicion"],
        clave_entidad=r["ClaveEntFed"],
    )
    trabajador = DatosTrabajador(
        rfc=receptor["Rfc"],
        nombre=receptor["Nombre"],
        curp=r["Curp"],
        numero_seguridad_social=r["NumSeguridadSocial"],
        codigo_postal=receptor["DomicilioFiscalReceptor"],
        fecha_inicio_relacion_laboral=date.fromisoformat(r["FechaInicioRelLaboral"]),
        antiguedad=r["Antigüedad"],
        tipo_contrato=r["TipoContrato"],
        tipo_regimen=r["TipoRegimen"],
        numero_empleado=r["NumEmpleado"],
        departamento=r.get("Departamento", ""),  # opcional: 61 de 70 lo traen
        puesto=r["Puesto"],
        riesgo_puesto=r["RiesgoPuesto"],
        periodicidad_pago=r["PeriodicidadPago"],
        salario_base_cotizacion=Decimal(r["SalarioBaseCotApor"]),
        salario_diario_integrado=Decimal(r["SalarioDiarioIntegrado"]),
        sindicalizado=r["Sindicalizado"],
        tipo_jornada=r["TipoJornada"],
    )
    return patron, trabajador


def _regenerar(ruta: Path) -> ET.Element:
    """
    Vuelve a emitir el CFDI del fixture con el generador y devuelve la raiz del
    **XML emitido**.

    Es lo que permite comparar contra lo que el generador escribio, y no contra
    lo que el objeto de dominio calcula.
    """
    original = ET.parse(ruta).getroot()
    nomina = original.find(".//n:Nomina", NS)
    recibo, _ = _partidas_del_cfdi(ruta)
    patron, trabajador = _datos_del_cfdi(ruta)
    xml = generar_cfdi_nomina(
        recibo,
        patron,
        trabajador,
        datetime.fromisoformat(original.attrib["Fecha"]),
        date.fromisoformat(nomina.attrib["FechaInicialPago"]),
        date.fromisoformat(nomina.attrib["FechaFinalPago"]),
        date.fromisoformat(nomina.attrib["FechaPago"]),
        Decimal(nomina.attrib["NumDiasPagados"]),
        tipo_nomina=nomina.attrib["TipoNomina"],
        serie=original.attrib.get("Serie", ""),
        folio=original.attrib.get("Folio", ""),
    )
    return ET.fromstring(xml)


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


class TestTotales:
    """
    Los totales se leen del **XML que emite el generador**, no del objeto
    `Recibo`.

    Comparar propiedades del recibo contra el fixture prueba que la aritmetica
    del dominio esta bien, pero deja pasar un generador que escriba
    `TotalSueldos` donde va `TotalPercepciones`, o que emita un `Total` que
    ignore el descuento. Estos tests deben ponerse en rojo ante esas mutaciones.

    Se comparan como `Decimal`, nunca como cadena: el caso real emite
    `TotalOtrosPagos="0"` y el generador `"0.00"`, y las dos son validas.
    """

    def test_hay_setenta_recibos(self):
        assert len(list(FIXTURES.glob("semana-*/*.xml"))) == 70

    def test_los_totales_del_complemento_cuadran_en_los_setenta(self):
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            original = ET.parse(ruta).getroot().find(".//n:Nomina", NS).attrib
            emitido = _regenerar(ruta).find(".//n:Nomina", NS).attrib
            for attr in ("TotalPercepciones", "TotalDeducciones", "TotalOtrosPagos"):
                assert Decimal(emitido[attr]) == Decimal(original[attr]), f"{ruta.name} {attr}"

    def test_los_totales_de_percepciones_cuadran_en_los_setenta(self):
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            original = ET.parse(ruta).getroot().find(".//n:Percepciones", NS).attrib
            emitido = _regenerar(ruta).find(".//n:Percepciones", NS).attrib
            for attr in ("TotalSueldos", "TotalGravado", "TotalExento"):
                assert Decimal(emitido[attr]) == Decimal(original[attr]), f"{ruta.name} {attr}"

    def test_los_totales_de_deducciones_cuadran_en_los_setenta(self):
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            original = ET.parse(ruta).getroot().find(".//n:Deducciones", NS)
            emitido = _regenerar(ruta).find(".//n:Deducciones", NS)
            if original is None:
                assert emitido is None, ruta
                continue
            for attr in ("TotalImpuestosRetenidos", "TotalOtrasDeducciones"):
                esperado = Decimal(original.attrib.get(attr, "0"))
                assert Decimal(emitido.attrib.get(attr, "0")) == esperado, f"{ruta.name} {attr}"

    def test_los_totales_del_comprobante_cuadran_en_los_setenta(self):
        """`SubTotal = percepciones + otros pagos`, `Descuento = deducciones`."""
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            original = ET.parse(ruta).getroot().attrib
            emitido = _regenerar(ruta).attrib
            for attr in ("SubTotal", "Descuento", "Total"):
                assert Decimal(emitido[attr]) == Decimal(original[attr]), f"{ruta.name} {attr}"

    def test_el_concepto_replica_los_totales_del_comprobante(self):
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            emitido = _regenerar(ruta)
            concepto = emitido.find(".//cfdi:Concepto", NS).attrib
            assert Decimal(concepto["Importe"]) == Decimal(emitido.attrib["SubTotal"]), ruta
            assert Decimal(concepto["Descuento"]) == Decimal(emitido.attrib["Descuento"]), ruta


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


class TestSeparacionYJubilacion:
    """
    Las claves que el caso real NO ejercita.

    Las 70 fixtures solo traen `TipoPercepcion` 001 y 020, así que en ellas
    `TotalSueldos == TotalPercepciones` siempre y el cuadre 70/70 no distingue
    una propiedad de la otra. Un finiquito sí las separa, y esa rama estaría sin
    cubrir si no fuera por estos tests.
    """

    def _recibo_con_finiquito(self) -> Recibo:
        return Recibo(
            percepciones=(
                PartidaPercepcion("001", "P001", "SUELDO", Decimal("2000.00"), Decimal("0.00")),
                PartidaPercepcion(
                    "022", "P022", "PRIMA DE ANTIGÜEDAD", Decimal("500.00"), Decimal("300.00")
                ),
                PartidaPercepcion(
                    "039", "P039", "JUBILACIÓN", Decimal("100.00"), Decimal("150.00")
                ),
            ),
        )

    def test_total_sueldos_excluye_separacion_y_jubilacion(self):
        recibo = self._recibo_con_finiquito()
        assert recibo.total_percepciones == Decimal("3050.00")
        assert recibo.total_sueldos == Decimal("2000.00")
        assert recibo.total_separacion_indemnizacion == Decimal("800.00")
        assert recibo.total_jubilacion_pension_retiro == Decimal("250.00")

    def test_el_xml_emite_los_totales_condicionales(self):
        emitido = _generar_raiz(self._recibo_con_finiquito())
        percepciones = emitido.find(".//n:Percepciones", NS).attrib
        assert Decimal(percepciones["TotalSueldos"]) == Decimal("2000.00")
        assert Decimal(percepciones["TotalSeparacionIndemnizacion"]) == Decimal("800.00")
        assert Decimal(percepciones["TotalJubilacionPensionRetiro"]) == Decimal("250.00")

    def test_sin_finiquito_esos_totales_no_se_emiten(self):
        """Son condicionales: emitirlos en cero sería incorrecto."""
        percepciones = _generar_raiz(_recibo_ejemplo()).find(".//n:Percepciones", NS).attrib
        assert "TotalSeparacionIndemnizacion" not in percepciones
        assert "TotalJubilacionPensionRetiro" not in percepciones

    def test_un_recibo_con_finiquito_valida(self):
        assert errores_de_validacion(_generar(self._recibo_con_finiquito())) == []


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
