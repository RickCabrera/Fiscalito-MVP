"""
CLABE interbancaria y catálogo de bancos (P4-12).

EL DÍGITO VERIFICADOR
---------------------
La CLABE son 18 dígitos: 3 del banco, 3 de la plaza, 11 de la cuenta y 1 verificador.
Algoritmo publicado por Banxico ("Estructura de la CLABE", banxico.org.mx, sección
Sistemas de pago → SPEI → CLABE) y descrito igual en la norma de la ABM:

1. Se multiplican los primeros 17 dígitos por los factores 3, 7, 1, 3, 7, 1, … en orden.
2. De cada producto se toma sólo el dígito de las unidades (módulo 10) y se suman.
3. Se toma el módulo 10 de la suma; el verificador es (10 − ese módulo) módulo 10.

Ejemplo público (artículo "CLABE" de Wikipedia, que cita el mismo algoritmo):
032180000118359719 → verificador 9. El vector de pruebas de `tests/plan_p/test_dispersion.py`
y de `apps/store/src/services/clabe.test.ts` es el mismo, para que divergir rompa una prueba.

Una CLABE con el verificador mal se RECHAZA: no se "corrige" el último dígito, porque una
CLABE con un dígito tecleado mal es la cuenta de otra persona o de nadie.

EL CATÁLOGO
-----------
Claves del catálogo `c_Banco` del SAT (Anexo 24), que para estos bancos coinciden con los
tres primeros dígitos de la CLABE (clave ABM). Sólo los más comunes: una clave que no esté
aquí no invalida la CLABE —el banco existe aunque este catálogo no lo nombre—, sólo deja el
nombre vacío.
"""

from __future__ import annotations

import re

FACTORES = (3, 7, 1) * 6

BANCOS: dict[str, str] = {
    "002": "BANAMEX",
    "006": "BANCOMEXT",
    "009": "BANOBRAS",
    "012": "BBVA MEXICO",
    "014": "SANTANDER",
    "019": "BANJERCITO",
    "021": "HSBC",
    "030": "BAJIO",
    "036": "INBURSA",
    "042": "MIFEL",
    "044": "SCOTIABANK",
    "058": "BANREGIO",
    "059": "INVEX",
    "060": "BANSI",
    "062": "AFIRME",
    "072": "BANORTE",
    "106": "BANK OF AMERICA",
    "113": "VE POR MAS",
    "127": "AZTECA",
    "128": "AUTOFIN",
    "130": "COMPARTAMOS",
    "132": "MULTIVA",
    "133": "ACTINVER",
    "136": "INTERCAM BANCO",
    "137": "BANCOPPEL",
    "138": "ABC CAPITAL",
    "140": "CONSUBANCO",
    "143": "CIBANCO",
    "145": "BBASE",
    "152": "BANCREA",
    "156": "SABADELL",
    "166": "BANCO DEL BIENESTAR",
    "646": "STP",
}

_DIGITOS = re.compile(r"^\d+$")


def digito_verificador(primeros_17: str) -> int:
    """El verificador de los primeros 17 dígitos (ver encabezado)."""
    if len(primeros_17) != 17 or not _DIGITOS.match(primeros_17):
        raise ValueError("El verificador se calcula sobre exactamente 17 dígitos.")
    suma = sum((int(d) * f) % 10 for d, f in zip(primeros_17, FACTORES, strict=False))
    return (10 - suma % 10) % 10


def motivo_clabe_invalida(clabe: str) -> str | None:
    """`None` si la CLABE es válida; si no, por qué (texto para el usuario)."""
    if not _DIGITOS.match(clabe or ""):
        return "La CLABE sólo lleva dígitos."
    if len(clabe) != 18:
        return f"La CLABE son 18 dígitos y llegaron {len(clabe)}."
    esperado = digito_verificador(clabe[:17])
    if int(clabe[17]) != esperado:
        return (
            f"El dígito verificador de la CLABE no cuadra (termina en {clabe[17]} y debería "
            f"terminar en {esperado}): revisa que no haya un dígito tecleado mal."
        )
    return None


def es_clabe_valida(clabe: str) -> bool:
    return motivo_clabe_invalida(clabe) is None


def banco_de_clabe(clabe: str) -> str:
    """La clave del banco (3 dígitos) de una CLABE."""
    return clabe[:3]


def plaza_de_clabe(clabe: str) -> str:
    return clabe[3:6]


def nombre_banco(clave: str) -> str:
    return BANCOS.get(clave, "")
