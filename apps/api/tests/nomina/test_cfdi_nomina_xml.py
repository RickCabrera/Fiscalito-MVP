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
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.constants import CLIENTE_DEMO
from app.main import app
from app.nomina_engine.cfdi_nomina_xml import (
    ATRIBUTO_ANTIGUEDAD,
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


def _es_numero(valor: str) -> bool:
    try:
        Decimal(valor)
    except (ArithmeticError, ValueError):
        return False
    return True


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


# Atributos que el pre-recibo DEBE emitir distintos del original: son
# justamente los que dicen que no esta timbrado.
ATRIBUTOS_QUE_DIFIEREN = frozenset({"Sello", "NoCertificado", "Certificado"})


def _atributos_por_ruta(raiz: ET.Element) -> dict[str, dict[str, str]]:
    """
    Aplana el documento a {ruta_del_nodo: atributos}, ignorando el timbre.

    La ruta lleva el indice del hermano para que dos percepciones no se pisen.
    """
    plano: dict[str, dict[str, str]] = {}

    def recorrer(nodo: ET.Element, ruta: str) -> None:
        etiqueta = nodo.tag.split("}")[-1]
        if etiqueta == "TimbreFiscalDigital":
            return
        plano[ruta] = dict(nodo.attrib)
        contador: dict[str, int] = {}
        for hijo in nodo:
            nombre = hijo.tag.split("}")[-1]
            indice = contador.get(nombre, 0)
            contador[nombre] = indice + 1
            recorrer(hijo, f"{ruta}/{nombre}[{indice}]")

    recorrer(raiz, "Comprobante")
    return plano


class TestIdaYVuelta:
    """
    Todo atributo del que el generador es responsable, no solo los totales.

    `TestTotales` compara totales y `TestValidacionXSD` comprueba que el
    documento es valido; ninguno de los dos mira los **renglones**. Sin este
    test, intercambiar `ImporteGravado` con `ImporteExento` en cada percepcion
    —invirtiendo la exencion del Art. 93 que F1-04 existe para calcular— deja
    los totales intactos y no mueve nada: un CFDI que se contradice a si mismo.

    Se excluyen a proposito los atributos de sello y el TimbreFiscalDigital,
    que **tienen** que diferir: son lo que dice que el pre-recibo no esta
    timbrado.
    """

    def test_el_documento_emitido_coincide_con_el_original(self):
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            original = _atributos_por_ruta(ET.parse(ruta).getroot())
            emitido = _atributos_por_ruta(_regenerar(ruta))
            assert set(emitido) == set(original), f"{ruta.name}: nodos distintos"
            for nodo, atributos in original.items():
                for nombre, valor in atributos.items():
                    if nombre in ATRIBUTOS_QUE_DIFIEREN or nombre.startswith("{"):
                        continue
                    obtenido = emitido[nodo].get(nombre)
                    assert obtenido is not None, f"{ruta.name} {nodo}/@{nombre}: falta"
                    iguales = (
                        Decimal(obtenido) == Decimal(valor)
                        if _es_numero(valor) and _es_numero(obtenido)
                        else obtenido == valor
                    )
                    assert iguales, f"{ruta.name} {nodo}/@{nombre}: {obtenido} != {valor}"

    def test_lo_que_el_caso_real_no_puede_distinguir(self):
        """
        Tres atributos que el ida y vuelta NO puede probar, porque el dataset
        no varía: los 70 recibos traen `TotalOtrosPagos=0`, `NumDiasPagados`
        siempre 7.000 y `SalarioBaseCotApor == SalarioDiarioIntegrado`.

        Con esos valores, emitir `SubTotal` sin sumar los otros pagos, fijar los
        días a "7.000" o intercambiar el SBC con el SDI da exactamente el mismo
        XML. Sin un caso sintético que los separe, las tres mutaciones pasan
        desapercibidas.
        """
        recibo = Recibo(
            percepciones=(
                PartidaPercepcion("001", "P001", "SUELDO", Decimal("1000.00"), Decimal("0.00")),
            ),
            otros_pagos=(
                PartidaOtroPago("004", "D200", "SALDO A FAVOR", Decimal("250.00")),
            ),
        )
        # `TipoNomina` cae en la misma clase: los 70 fixtures son "O" y el
        # default también, así que cablearlo en duro no movería nada. El
        # extraordinario —aguinaldo, finiquito, PTU— es justo el que vale.
        trabajador = replace(
            TRABAJADOR,
            salario_base_cotizacion=Decimal("300.00"),
            salario_diario_integrado=Decimal("315.50"),
        )
        xml = generar_cfdi_nomina(
            recibo,
            PATRON,
            trabajador,
            datetime(2026, 4, 5, 12, 0, 0),
            date(2026, 3, 21),
            date(2026, 4, 5),
            date(2026, 4, 5),
            Decimal("15"),
            tipo_nomina="E",
            serie="DEMOSA",
            folio="1",
        )
        raiz = ET.fromstring(xml)

        # SubTotal suma los otros pagos, no solo las percepciones.
        assert Decimal(raiz.attrib["SubTotal"]) == Decimal("1250.00")

        nomina = raiz.find(".//n:Nomina", NS)
        assert nomina.attrib["NumDiasPagados"] == "15.000"
        assert nomina.attrib["TipoNomina"] == "E"

        receptor = raiz.find(".//n:Receptor", NS)
        assert Decimal(receptor.attrib["SalarioBaseCotApor"]) == Decimal("300.00")
        assert Decimal(receptor.attrib["SalarioDiarioIntegrado"]) == Decimal("315.50")

        assert errores_de_validacion(xml) == []

    def test_los_atributos_de_sello_si_difieren(self):
        """Si dejaran de diferir, el pre-recibo estaria copiando un sello ajeno."""
        ruta = next(iter(sorted(FIXTURES.glob("semana-01/*.xml"))))
        original = ET.parse(ruta).getroot().attrib
        emitido = _regenerar(ruta).attrib
        for atributo in ATRIBUTOS_QUE_DIFIEREN:
            assert emitido[atributo] != original[atributo]


class TestValidacionXSD:
    def test_el_pre_recibo_generado_valida(self):
        assert errores_de_validacion(_generar(_recibo_ejemplo())) == []

    def test_los_setenta_generados_validan(self):
        """
        Lo que prueba al generador: el XML que emite, no el que ya existía.

        No es redundante con el pre-recibo de ejemplo: 9 de los 70 no traen
        `Departamento`, que es una variante estructural que el ejemplo único no
        ejercita.
        """
        for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
            xml = ET.tostring(_regenerar(ruta), encoding="unicode")
            assert errores_de_validacion(xml) == [], ruta

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


class TestEndpointCFDI:
    """
    `POST /api/v1/nomina/cfdi` (T4): el mismo XSD, ahora por HTTP.

    **Es el mismo `errores_de_validacion` de `TestValidacionXSD`, apuntado al
    endpoint.** Lo que agrega no es la validación —ésa ya estaba— sino el
    eslabón que faltaba: que el recibo tal como lo devuelve
    `/nomina/calcular-periodo` entra al generador **sin remapear**. El módulo
    llevaba desde F1-05 sin que nadie lo importara; si el contrato de los dos
    endpoints se separa, aquí truena.
    """

    @staticmethod
    def _cliente() -> TestClient:
        return TestClient(app)

    @staticmethod
    def _recibo_del_motor(cliente: TestClient) -> dict:
        """El recibo de E-03 tal como sale del motor, sin tocarle un campo."""
        res = cliente.post(
            "/api/v1/nomina/calcular-periodo",
            json={
                "cliente": CLIENTE_DEMO,
                "periodo": {"inicio": "2026-08-16", "fin": "2026-08-31"},
                "parametros": {"prima_riesgo": "0.0054355", "clave_periodicidad": "04"},
                "incidencias": [
                    {
                        "empleado_no": "E-03",
                        "dias_periodo": 16,
                        "faltas": 0,
                        "dias_ausentismo": 0,
                    }
                ],
                "empleados": [
                    {
                        "empleado_no": "E-03",
                        "nombre": TRABAJADOR.nombre,
                        "salario_diario": "368.05",
                        "salario_diario_integrado": "399.52",
                    }
                ],
            },
        )
        assert res.status_code == 200, res.text
        return res.json()["recibos"][0]

    @classmethod
    def _cuerpo(cls, recibo: dict, **extra) -> dict:
        return {
            "recibo": recibo,
            "patron": {
                "rfc": PATRON.rfc,
                "nombre": PATRON.nombre,
                "regimen_fiscal": PATRON.regimen_fiscal,
                "registro_patronal": PATRON.registro_patronal,
                "codigo_postal": PATRON.codigo_postal,
                "clave_entidad": PATRON.clave_entidad,
            },
            "trabajador": {
                "rfc": TRABAJADOR.rfc,
                "nombre": TRABAJADOR.nombre,
                "curp": TRABAJADOR.curp,
                "numero_seguridad_social": TRABAJADOR.numero_seguridad_social,
                "codigo_postal": TRABAJADOR.codigo_postal,
                "fecha_inicio_relacion_laboral": "2024-05-26",
                "tipo_contrato": TRABAJADOR.tipo_contrato,
                "numero_empleado": TRABAJADOR.numero_empleado,
                "puesto": TRABAJADOR.puesto,
                "departamento": TRABAJADOR.departamento,
                "riesgo_puesto": TRABAJADOR.riesgo_puesto,
                "periodicidad_pago": "04",
                "salario_base_cotizacion": "399.52",
                "salario_diario_integrado": "399.52",
                **extra.pop("trabajador", {}),
            },
            "periodo": {"inicio": "2026-08-16", "fin": "2026-08-31"},
            **extra,
        }

    def test_el_xml_del_endpoint_valida_contra_el_xsd(self):
        cliente = self._cliente()
        res = cliente.post(
            "/api/v1/nomina/cfdi", json=self._cuerpo(self._recibo_del_motor(cliente))
        )
        assert res.status_code == 200, res.text
        cuerpo = res.json()
        assert errores_de_validacion(cuerpo["xml"]) == []

    def test_la_respuesta_dice_que_no_esta_timbrado(self):
        """
        `timbrado: false` no es decorativo: es lo que el front pinta como
        "Pendiente de timbrado PAC". Si alguien lo vuelve `true` sin timbrar de
        verdad, este test es el que lo caza.
        """
        cliente = self._cliente()
        cuerpo = cliente.post(
            "/api/v1/nomina/cfdi", json=self._cuerpo(self._recibo_del_motor(cliente))
        ).json()
        assert cuerpo["timbrado"] is False
        assert "sin-timbrar" in cuerpo["nombre_archivo"]
        assert "TIMBRAR" in cuerpo["advertencia"].upper()
        raiz = ET.fromstring(cuerpo["xml"])
        assert raiz.find(".//tfd:TimbreFiscalDigital", NS) is None
        assert raiz.attrib["Sello"] == SELLO_SIN_TIMBRAR
        assert raiz.attrib["NoCertificado"] == NO_CERTIFICADO_SIN_TIMBRAR

    def test_la_antiguedad_se_deriva_del_inicio_de_la_relacion_laboral(self):
        """
        Semanas completas hasta el FIN DEL PERIODO, no hasta hoy. Del 2024-05-26
        al 2026-08-31 van 827 días = 118 semanas y 1 día.
        """
        cliente = self._cliente()
        cuerpo = cliente.post(
            "/api/v1/nomina/cfdi", json=self._cuerpo(self._recibo_del_motor(cliente))
        ).json()
        receptor = ET.fromstring(cuerpo["xml"]).find(".//n:Receptor", NS)
        assert receptor.attrib[ATRIBUTO_ANTIGUEDAD] == "P118W"

    def test_una_antiguedad_capturada_manda_sobre_la_derivada(self):
        cliente = self._cliente()
        cuerpo = self._cuerpo(
            self._recibo_del_motor(cliente), trabajador={"antiguedad": "P97W"}
        )
        res = cliente.post("/api/v1/nomina/cfdi", json=cuerpo)
        receptor = ET.fromstring(res.json()["xml"]).find(".//n:Receptor", NS)
        assert receptor.attrib[ATRIBUTO_ANTIGUEDAD] == "P97W"

    def test_sin_curp_no_hay_xml(self):
        """
        **El 422 es la entrega, no el fallo.** Un CFDI con una CURP de relleno
        lleva el nombre de una persona real y los datos de nadie; el endpoint
        prefiere decir qué falta.
        """
        cliente = self._cliente()
        cuerpo = self._cuerpo(self._recibo_del_motor(cliente))
        del cuerpo["trabajador"]["curp"]
        res = cliente.post("/api/v1/nomina/cfdi", json=cuerpo)
        assert res.status_code == 422
        assert "curp" in res.text.lower()

    def test_el_total_del_comprobante_es_el_neto_del_motor(self):
        """
        El serializador **suma**, no recalcula: si el `Total` del XML se separa
        del `neto` que devolvió `/calcular-periodo`, alguien metió aritmética
        nueva en el camino.
        """
        cliente = self._cliente()
        recibo = self._recibo_del_motor(cliente)
        cuerpo = cliente.post("/api/v1/nomina/cfdi", json=self._cuerpo(recibo)).json()
        raiz = ET.fromstring(cuerpo["xml"])
        assert Decimal(raiz.attrib["Total"]) == Decimal(recibo["neto"])
        nomina = raiz.find(".//n:Nomina", NS)
        assert Decimal(nomina.attrib["TotalPercepciones"]) == Decimal(
            recibo["total_percepciones"]
        )
        assert Decimal(nomina.attrib["TotalDeducciones"]) == Decimal(
            recibo["total_deducciones"]
        )
        assert nomina.attrib["NumDiasPagados"] == f"{recibo['dias_pagados']}.000"
