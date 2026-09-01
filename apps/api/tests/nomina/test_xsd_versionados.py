"""
Los XSD versionados son los que publicó el SAT, y siguen siéndolo.

Un README con hashes que nadie ejecuta es prosa. Este test los recalcula.

Si falla, alguien editó un XSD del SAT — cosa que **no** hay que hacer: la
resolución offline se logra con el resolver de `validacion_xsd.py`, no
reescribiendo los archivos, precisamente para que estos hashes sigan
verificando contra la fuente oficial.
"""

import hashlib
from pathlib import Path

import pytest

XSD = Path(__file__).resolve().parent.parent / "xsd"

# Descargados el 2026-09-01 con `scripts/descargar_xsd.py`. Ver `xsd/README.md`
# para las URLs de origen y la advertencia de caducidad del snapshot.
HASHES = {
    "cfdv40.xsd": "2489b5b535f5cbc6a6c2db6132620de1833f85372512d01deea62880e700e276",
    "nomina12.xsd": "ac5db22ceee35c2224aad8745a3ab968c9c3d04d36adb50d056c83c4c1a29083",
    "TimbreFiscalDigitalv11.xsd": (
        "fb3d061fe9914500bef8beb3ea2e8722ee8a8224fa3af63643877a64c0ea05f7"
    ),
    "catCFDI.xsd": "6c58936cb77576f839a4d7915953ceaf252b9eb9319f9458fe5bb67ae2bb0bb1",
    "catNomina.xsd": "aeabf62f9901d75d5dccf0fbed13dd9dca6295e5b0ef40c9d89edcae3c641bc9",
    "tdCFDI.xsd": "b3b81fe4017b95d5477f23a32f47e8b0571683cfddfff1330508c75e02b504cd",
}


@pytest.mark.parametrize("nombre", sorted(HASHES))
def test_el_xsd_es_byte_identico_al_publicado(nombre):
    ruta = XSD / nombre
    assert ruta.exists(), f"falta {nombre}: corre scripts/descargar_xsd.py"
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == HASHES[nombre]


def test_no_hay_xsd_del_sat_sin_hash_declarado():
    """
    Un archivo nuevo sin hash pasaría desapercibido. El envoltorio es la única
    excepción: lo escribimos nosotros y no viene de ninguna autoridad.
    """
    presentes = {p.name for p in XSD.glob("*.xsd")}
    assert presentes == set(HASHES) | {"envoltorio_validacion.xsd"}


def test_el_envoltorio_no_es_del_sat():
    """Que quede en la suite que ese archivo es nuestro, no una fuente oficial."""
    contenido = (XSD / "envoltorio_validacion.xsd").read_text(encoding="utf-8")
    assert "NO ES DEL SAT" in contenido
