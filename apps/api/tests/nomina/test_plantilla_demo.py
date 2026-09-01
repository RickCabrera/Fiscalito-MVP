"""
La plantilla de `app/demo_nomina.py` no puede divergir de las fixtures de S-04.

POR QUE EXISTE ESTE ARCHIVO
---------------------------
`PLANTILLA_DEMO` es una **copia** de datos que viven en
`tests/fixtures/nomina/`. La copia es necesaria —`pip install -e .` sólo
empaqueta `app*`, así que un módulo de runtime que leyera `tests/` reventaría
en Cloud Run— pero una copia sin verificación es deuda: el día que las dos
diverjan, la demo enseñaría sueldos que no son los del caso.

El mismo argumento por el que la plantilla NO se hardcodea en TypeScript en
D-07 obliga a este test aquí.

Se compara contra el XML, que es la fuente, no contra `nomina_inventario.py`
(que sólo tiene identidades, no montos).
"""

import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

from app.demo_nomina import PLANTILLA_DEMO

NS = {"cfdi": "http://www.sat.gob.mx/cfd/4", "n": "http://www.sat.gob.mx/nomina12"}
FIXTURES = Path(__file__).parent.parent / "fixtures" / "nomina"
CLAVE_SUELDO = "001"


def _del_caso_real() -> dict[str, dict[str, set]]:
    """Por empleado: sus SDI, sus salarios diarios y sus nombres observados."""
    observado: dict[str, dict[str, set]] = {}
    for ruta in sorted(FIXTURES.glob("semana-*/*.xml")):
        raiz = ET.parse(ruta).getroot()
        nomina = raiz.find(".//n:Nomina", NS)
        receptor = nomina.find("n:Receptor", NS)
        numero = receptor.get("NumEmpleado")
        del_empleado = observado.setdefault(
            numero, {"sdi": set(), "diario": set(), "nombre": set()}
        )
        del_empleado["sdi"].add(Decimal(receptor.get("SalarioBaseCotApor")))
        del_empleado["nombre"].add(raiz.find("cfdi:Receptor", NS).get("Nombre"))
        sueldos = [
            p
            for p in nomina.findall(".//n:Percepcion", NS)
            if p.get("TipoPercepcion") == CLAVE_SUELDO
        ]
        if sueldos:
            importe = Decimal(sueldos[0].get("ImporteGravado")) + Decimal(
                sueldos[0].get("ImporteExento")
            )
            dias = Decimal(nomina.get("NumDiasPagados"))
            del_empleado["diario"].add(importe / dias)
    return observado


class TestNoDivergencia:
    def test_son_los_mismos_nueve_empleados(self):
        assert {e.empleado_no for e in PLANTILLA_DEMO} == set(_del_caso_real())

    def test_cada_empleado_tiene_un_solo_sueldo_en_las_nueve_semanas(self):
        """
        Si un empleado tuviera dos SDI distintos, copiar "el" suyo a la
        plantilla sería una decisión escondida y no una copia.
        """
        for numero, valores in _del_caso_real().items():
            assert len(valores["sdi"]) == 1, f"{numero} tiene varios SBC: {valores['sdi']}"
            assert len(valores["diario"]) == 1, f"{numero}: {valores['diario']}"

    def test_el_sdi_y_el_salario_diario_coinciden_con_el_caso_real(self):
        observado = _del_caso_real()
        for empleado in PLANTILLA_DEMO:
            del_caso = observado[empleado.empleado_no]
            assert empleado.salario_diario_integrado == next(iter(del_caso["sdi"]))
            assert empleado.salario_diario == next(iter(del_caso["diario"]))

    def test_los_nombres_coinciden_con_el_caso_real(self):
        """
        Ancla contra el remapeo: `scripts/anonimizar_nomina.py` baraja las
        identidades en cada corrida, así que si alguien lo vuelve a correr, el
        par número→nombre cambia y esto se pone rojo.
        """
        observado = _del_caso_real()
        for empleado in PLANTILLA_DEMO:
            assert empleado.nombre == next(iter(observado[empleado.empleado_no]["nombre"]))


class TestPrivacidad:
    def test_la_plantilla_no_trae_rfc_curp_ni_nss(self):
        """
        Los montos son reales; las identidades, sintéticas. La plantilla no
        necesita RFC ni CURP para calcular, así que no los lleva: lo que no
        está no se puede filtrar.
        """
        campos = set(vars(PLANTILLA_DEMO[0]))
        assert not campos & {"rfc", "curp", "nss"}
