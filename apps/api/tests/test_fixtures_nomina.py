"""
Verificación de las fixtures de nómina (S-04).

Corre en CI **sin el origen** y sin skips: la comprobación es por inventario
sobre las fixtures versionadas, no por comparación contra los XML reales.

Por qué inventario y no lista negra: una lista negra ("que no aparezca ninguno
de los valores reales") solo prueba lo que uno se acordó de extraer, y una lista
blanca por *forma* tampoco alcanza — un nombre, un registro patronal o un puesto
que se escapara no se parece a un RFC ni a una CURP y pasaría limpio. Aquí se
afirma que el conjunto de pares elemento@atributo es exactamente el declarado
(así un campo olvidado aparece como par no declarado y truena) y que cada
atributo sustituido solo toma valores de su conjunto sintético.
"""

from __future__ import annotations

import base64
import math
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from tests.nomina_inventario import (
    ANTIGUEDAD,
    INVENTARIO,
    NS,
    PREDICADOS,
    REPARTO_SEMANAL,
    SUSTITUIDOS,
    TOTAL_ARCHIVOS,
    VALORES_ESPERADOS,
)

FIXTURES = Path(__file__).parent / "fixtures" / "nomina"

PREFIJO = {uri: pre for pre, uri in NS.items()}


def _archivos() -> list[Path]:
    return sorted(FIXTURES.glob("semana-*/*.xml"))


# Conteo duro ANTES de parametrizar: un parametrize sobre un glob vacío colecta
# cero tests y reporta verde, que es un skip silencioso disfrazado.
ARCHIVOS = _archivos()
assert len(ARCHIVOS) == TOTAL_ARCHIVOS, (
    f"se esperaban {TOTAL_ARCHIVOS} fixtures y hay {len(ARCHIVOS)}"
)


def _calificado(tag: str) -> str:
    if tag.startswith("{"):
        uri, nombre = tag[1:].split("}")
        return f"{PREFIJO.get(uri, uri)}:{nombre}"
    return tag


def _attr_calificado(attr: str) -> str:
    if attr.startswith("{"):
        uri, nombre = attr[1:].split("}")
        return f"{PREFIJO.get(uri, uri)}:{nombre}"
    return attr


def _monto(valor: str | None) -> float:
    """Los montos del CFDI son cadenas con 2 decimales."""
    return round(float(valor or 0), 2)


def _pares(raiz: ET.Element):
    for el in raiz.iter():
        for a, v in el.attrib.items():
            yield (_calificado(el.tag), _attr_calificado(a)), v


class TestEstructura:
    def test_reparto_semanal(self):
        """La transición 9 -> 8 -> 7 empleados es lo que da valor al caso."""
        reparto = [
            len(list((FIXTURES / f"semana-{i:02d}").glob("*.xml")))
            for i in range(1, len(REPARTO_SEMANAL) + 1)
        ]
        assert reparto == REPARTO_SEMANAL

    @pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_es_cfdi_de_nomina(self, ruta: Path):
        raiz = ET.parse(ruta).getroot()
        assert raiz.get("Version") == "4.0"
        assert raiz.get("TipoDeComprobante") == "N"
        nomina = raiz.find(f".//{{{NS['nomina12']}}}Nomina")
        assert nomina is not None and nomina.get("Version") == "1.2"
        for nodo in ("Percepciones", "Deducciones", "OtrosPagos"):
            assert raiz.find(f".//{{{NS['nomina12']}}}{nodo}") is not None
        assert raiz.find(f".//{{{NS['tfd']}}}TimbreFiscalDigital") is not None


class TestPrivacidad:
    @pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_sin_pares_no_declarados(self, ruta: Path):
        """Un campo olvidado aparece aquí como par no declarado."""
        vistos = {par for par, _ in _pares(ET.parse(ruta).getroot())}
        assert not (vistos - INVENTARIO), f"pares no declarados: {vistos - INVENTARIO}"

    @pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_sustituidos_solo_toman_valores_sinteticos(self, ruta: Path):
        for par, valor in _pares(ET.parse(ruta).getroot()):
            if (clase := SUSTITUIDOS.get(par)) is None:
                continue
            if clase in VALORES_ESPERADOS:
                assert valor in VALORES_ESPERADOS[clase], f"{par} = {valor!r}"
            else:
                assert PREDICADOS[clase](valor), f"{par} = {valor!r} no cumple {clase}"

    @pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_sellos_decodificados_no_traen_identificadores(self, ruta: Path):
        """El Certificado del origen es un X.509 con RFC y CURP en claro.

        Greppear texto plano no lo vería: va en base64. Se decodifica y se busca
        forma de RFC o CURP en los bytes.
        """
        raiz = ET.parse(ruta).getroot()
        timbre = raiz.find(f".//{{{NS['tfd']}}}TimbreFiscalDigital")
        for b64 in (raiz.get("Sello"), raiz.get("Certificado"),
                    timbre.get("SelloCFD"), timbre.get("SelloSAT")):
            crudo = base64.b64decode(b64, validate=False)
            texto = crudo.decode("latin-1")
            assert not re.search(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", texto), "forma de RFC"
            assert not re.search(r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d", texto), "forma de CURP"

    def test_identidad_coherente_entre_semanas(self):
        """Cada E-0X es la misma persona en todas sus semanas.

        Sin esto, un bug que reasignara por archivo pasaría desapercibido y los
        valores esperados de F1-03/F1-04 se construirían sobre personas que
        cambian de identidad a media semana.
        """
        por_empleado: dict[str, set[tuple]] = {}
        for ruta in ARCHIVOS:
            raiz = ET.parse(ruta).getroot()
            rec_c = raiz.find(f"{{{NS['cfdi']}}}Receptor")
            rec_n = raiz.find(f".//{{{NS['nomina12']}}}Receptor")
            num = rec_n.get("NumEmpleado")
            por_empleado.setdefault(num, set()).add((
                rec_c.get("Rfc"), rec_c.get("Nombre"),
                rec_c.get("DomicilioFiscalReceptor"),
                rec_n.get("Curp"), rec_n.get("NumSeguridadSocial"),
                rec_n.get("FechaInicioRelLaboral"),
            ))
        assert len(por_empleado) == 9
        for num, identidades in por_empleado.items():
            assert len(identidades) == 1, f"{num} cambia de identidad entre semanas"

    def test_timestamps_normalizados(self):
        """Fecha y FechaTimbrado son la llave de cruce mas fuerte que queda.

        El predicado de formato solo comprueba que parezcan una fecha, y
        cualquier timestamp real lo cumple: si una regeneracion olvidara
        normalizarlos, el test seguiria verde. Aqui se afirma la relacion.
        """
        from datetime import datetime, timedelta
        for ruta in ARCHIVOS:
            raiz = ET.parse(ruta).getroot()
            nom = raiz.find(f".//{{{NS['nomina12']}}}Nomina")
            timbre = raiz.find(f".//{{{NS['tfd']}}}TimbreFiscalDigital")
            pago = date.fromisoformat(nom.get("FechaPago"))
            esperada = datetime.combine(pago, datetime.min.time()) + timedelta(hours=12)
            assert raiz.get("Fecha") == esperada.strftime("%Y-%m-%dT%H:%M:%S"), ruta.name
            assert timbre.get("FechaTimbrado") == (
                esperada + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"), ruta.name

    def test_folios_renumerados(self):
        """El conjunto exacto, no solo "parece un numero corto"."""
        folios = {int(ET.parse(r).getroot().get("Folio")) for r in ARCHIVOS}
        assert folios == set(range(1, TOTAL_ARCHIVOS + 1))

    def test_sin_nodos_de_texto(self):
        """El inventario es de atributos: no veria un nodo con texto libre."""
        for ruta in ARCHIVOS:
            for el in ET.parse(ruta).getroot().iter():
                assert not (el.text or "").strip(), f"{ruta.name}: texto en {el.tag}"
                assert not (el.tail or "").strip(), f"{ruta.name}: cola en {el.tag}"

    def test_fechas_de_alta_anteriores_al_periodo(self):
        """La única restricción que los datos imponen de verdad."""
        for ruta in ARCHIVOS:
            raiz = ET.parse(ruta).getroot()
            rec = raiz.find(f".//{{{NS['nomina12']}}}Receptor")
            nom = raiz.find(f".//{{{NS['nomina12']}}}Nomina")
            alta = date.fromisoformat(rec.get("FechaInicioRelLaboral"))
            inicio = date.fromisoformat(nom.get("FechaInicialPago"))
            assert alta < inicio, f"{ruta.name}: alta {alta} no precede a {inicio}"

    def test_antiguedad_coherente_con_la_fecha_de_alta(self):
        """`ceil(días/7)`: recomputarla es seguro porque la alta ya es sintética."""
        for ruta in ARCHIVOS:
            raiz = ET.parse(ruta).getroot()
            rec = raiz.find(f".//{{{NS['nomina12']}}}Receptor")
            nom = raiz.find(f".//{{{NS['nomina12']}}}Nomina")
            alta = date.fromisoformat(rec.get("FechaInicioRelLaboral"))
            fin = date.fromisoformat(nom.get("FechaFinalPago"))
            esperado = f"P{math.ceil((fin - alta).days / 7)}W"
            assert rec.get(ANTIGUEDAD) == esperado, ruta.name


class TestMontosIntactos:
    """Lo que F1-03 y F1-04 necesitan para cuadrar al centavo."""

    @pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_invariantes_aritmeticas(self, ruta: Path):
        raiz = ET.parse(ruta).getroot()
        nom = raiz.find(f".//{{{NS['nomina12']}}}Nomina")
        assert round(_monto(raiz.get("SubTotal")) - _monto(raiz.get("Descuento")), 2) == _monto(
            raiz.get("Total")
        )

        total = (_monto(nom.get("TotalPercepciones")) - _monto(nom.get("TotalDeducciones"))
                 + _monto(nom.get("TotalOtrosPagos")))
        assert round(total, 2) == _monto(raiz.get("Total"))

        percepciones = raiz.find(f".//{{{NS['nomina12']}}}Percepciones")
        suma = sum(_monto(p.get("ImporteGravado")) + _monto(p.get("ImporteExento"))
                   for p in raiz.iter(f"{{{NS['nomina12']}}}Percepcion"))
        assert round(suma, 2) == round(
            _monto(percepciones.get("TotalGravado")) + _monto(percepciones.get("TotalExento")), 2)

        deducciones = raiz.find(f".//{{{NS['nomina12']}}}Deducciones")
        suma_d = sum(_monto(d.get("Importe")) for d in raiz.iter(f"{{{NS['nomina12']}}}Deduccion"))
        assert round(suma_d, 2) == round(
            _monto(deducciones.get("TotalImpuestosRetenidos"))
            + _monto(deducciones.get("TotalOtrasDeducciones")), 2)
