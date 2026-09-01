"""
Descarga los XSD del SAT que `tests/nomina/test_cfdi_nomina_xml.py` usa para
validar el CFDI de nomina generado, y los deja en `tests/xsd/`.

Los archivos se guardan **byte-identicos a lo que publica el SAT**: no se les
reescribe el `schemaLocation` ni nada mas. La resolucion offline de sus imports
la hace el test con un resolver de lxml que mapea las URLs del SAT a los
archivos locales. Guardar el original es lo que permite publicar un SHA-256 que
de verdad verifica contra la fuente oficial: un archivo editado hashea a la
salida del editor, no a lo que publico la autoridad.

Uso:
    python scripts/descargar_xsd.py

El script NO se importa desde los tests: hace red, y los tests corren sin ella.
Se ejecuta a mano cuando haya que refrescar el snapshot, y despues se
actualizan los hashes de `tests/xsd/README.md` y de
`tests/nomina/test_xsd_versionados.py`.
"""

from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
from collections import deque
from datetime import date
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "tests" / "xsd"

RAIZ = (
    "http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd",
    "http://www.sat.gob.mx/sitio_internet/cfd/nomina/nomina12.xsd",
    "http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd",
)


def nombre_local(url: str) -> str:
    """Nombre plano del archivo. Los basename del SAT no chocan entre si."""
    return url.rsplit("/", 1)[-1]


def descargar_todo() -> dict[str, bytes]:
    """Descarga las raices y, recursivamente, todo lo que importen."""
    contenidos: dict[str, bytes] = {}
    pendientes = deque(RAIZ)
    while pendientes:
        url = pendientes.popleft()
        if url in contenidos:
            continue
        print(f"  descargando {url}")
        with urllib.request.urlopen(url, timeout=60) as respuesta:
            datos = respuesta.read()
        contenidos[url] = datos
        for referencia in re.findall(
            r'schemaLocation="(http[^"]+)"', datos.decode("utf-8", "replace")
        ):
            pendientes.append(referencia)
    return contenidos


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    contenidos = descargar_todo()

    filas = []
    for url, datos in sorted(contenidos.items()):
        destino = DESTINO / nombre_local(url)
        destino.write_bytes(datos)
        sha = hashlib.sha256(datos).hexdigest()
        filas.append((nombre_local(url), url, len(datos), sha))
        print(f"  guardado {destino.name}  {len(datos):,} B  sha256={sha[:16]}...")

    print()
    print(f"Descargados {len(filas)} archivos, {sum(f[2] for f in filas):,} bytes.")
    print(f"Fecha de descarga: {date.today().isoformat()}")
    print()
    print("Pega esto en tests/xsd/README.md y en test_xsd_versionados.py:")
    for nombre, url, tam, sha in filas:
        print(f'    "{nombre}": "{sha}",  # {tam:,} B — {url}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
