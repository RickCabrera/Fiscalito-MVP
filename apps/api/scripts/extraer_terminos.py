"""
Extrae los términos identificables del ORIGEN para el control cruzado de S-04.

Emite **solo a stdout**, un término por línea, y se niega a escribir dentro del
repo: su salida es un dosier en claro de nueve personas. Se usa con el comando
de verificación documentado (grep con control positivo) y el archivo temporal
que lo recibe se borra con `trap`.

Uso:
    python apps/api/scripts/extraer_terminos.py

Esto es la LISTA NEGRA, que solo prueba lo que uno se acordó de extraer. La
verificación de fondo es la lista blanca por inventario de
`tests/test_fixtures_nomina.py`, que corre en CI sin necesitar el origen.
"""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _cargar_inventario():
    """Carga tests/nomina_inventario.py por ruta.

    `scripts/` no es paquete y `tests/` no esta en sys.path al correr el script
    suelto. Se carga por ruta en vez de manipular sys.path para no necesitar un
    `# noqa: E402`: el arbol quedo en cero noqa tras S-01 y no vale la pena
    abrir esa puerta por una comodidad de import.
    """
    ruta = Path(__file__).resolve().parents[1] / "tests" / "nomina_inventario.py"
    spec = importlib.util.spec_from_file_location("nomina_inventario", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_inv = _cargar_inventario()

ANTIGUEDAD = _inv.ANTIGUEDAD
NS = _inv.NS

RAIZ = Path(__file__).resolve().parents[3]
ORIGEN = RAIZ / "03. CFDI DE NOMINA"


def q(prefijo: str, nombre: str) -> str:
    return f"{{{NS[prefijo]}}}{nombre}"


def terminos() -> set[str]:
    """Todo valor del origen que pueda identificar a alguien."""
    out: set[str] = set()
    for ruta in sorted(ORIGEN.glob("0[34]*/**/*.xml")):
        # El nombre del archivo empieza con el RFC del patrón: también es término.
        out.add(ruta.stem)
        out.add(ruta.parent.name)
        raiz = ET.parse(ruta).getroot()
        emisor_c = raiz.find(q("cfdi", "Emisor"))
        emisor_n = raiz.find(f".//{q('nomina12', 'Emisor')}")
        recep_c = raiz.find(q("cfdi", "Receptor"))
        recep_n = raiz.find(f".//{q('nomina12', 'Receptor')}")
        timbre = raiz.find(f".//{q('tfd', 'TimbreFiscalDigital')}")

        valores = [
            raiz.get("Serie"), raiz.get("Folio"), raiz.get("NoCertificado"),
            raiz.get("Sello"), raiz.get("Certificado"), raiz.get("LugarExpedicion"),
            raiz.get("Fecha"),
            emisor_c.get("Rfc"), emisor_c.get("Nombre"),
            emisor_n.get("RegistroPatronal") if emisor_n is not None else None,
            recep_c.get("Rfc"), recep_c.get("Nombre"),
            recep_c.get("DomicilioFiscalReceptor"),
            recep_n.get("Curp"), recep_n.get("NumSeguridadSocial"),
            recep_n.get("NumEmpleado"), recep_n.get("FechaInicioRelLaboral"),
            recep_n.get(ANTIGUEDAD), recep_n.get("Departamento"),
            recep_n.get("Puesto"), recep_n.get("TipoJornada"),
            timbre.get("UUID"), timbre.get("SelloCFD"), timbre.get("SelloSAT"),
            timbre.get("NoCertificadoSAT"), timbre.get("RfcProvCertif"),
            timbre.get("FechaTimbrado"),
        ]
        out.update(v for v in valores if v)
        # Cada token del nombre por separado: un apellido suelto también fuga.
        for nombre in (emisor_c.get("Nombre"), recep_c.get("Nombre")):
            if nombre:
                out.update(t for t in nombre.split() if len(t) >= 4)
    return out


# Umbral alto a proposito: los valores cortos (folio de 4 digitos, claves, dias)
# casan como subcadena dentro de un UUID o de un monto y ahogan la senal con
# ruido que no es fuga. Los identificadores de verdad son largos: RFC 12-13,
# CURP 18, NSS 11, UUID 36, nombres, fechas ISO. Lo corto lo cubre la lista
# blanca por inventario del test.
LARGO_MINIMO = 8


def main() -> None:
    # Finales de linea LF: con CRLF cada patron termina en \r y
    # `grep -F -f` no casa nunca -> reporta 0 coincidencias y parece que
    # todo esta limpio. Es el peor falso negativo posible.
    sys.stdout.reconfigure(newline="\n")
    if sys.stdout.isatty():
        print(
            "ADVERTENCIA: esto imprime datos personales en claro. "
            "Redirige a un archivo FUERA del repo y bórralo al terminar.",
            file=sys.stderr,
        )
    if not ORIGEN.exists():
        sys.exit(f"ABORTA: no existe {ORIGEN}")
    # Se emiten las variantes de caja en vez de usar `grep -i`: con un archivo
    # de patrones grande, `grep -F -i -f` devuelve 0 coincidencias en silencio
    # (verificado en este entorno), que es el peor falso negativo posible.
    #
    # Se descartan los terminos de menos de LARGO_MINIMO caracteres: con `-F`
    # casan en cualquier parte y ahogan la senal. Los valores cortos que si
    # importan (NumEmpleado) los cubre la lista blanca por inventario del test.
    salida: set[str] = set()
    for t in terminos():
        if len(t) >= LARGO_MINIMO:
            salida.update({t, t.upper(), t.lower()})
    for t in sorted(salida):
        print(t)


if __name__ == "__main__":
    main()
