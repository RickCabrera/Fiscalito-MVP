"""
Listados públicos del SAT, art. 69-B y 69 del CFF (P1-04). `FISCALITO_SAT_LISTAS` = falso | sat.

El adaptador sólo DESCARGA el CSV de una lista; el parseo y la carga viven en
`app/sat_verificacion/listas.py`, así el falso y el real pasan por el mismo parser.

URLS
----
El SAT publica los listados en "Datos abiertos" (`omawww.sat.gob.mx/cifras_sat`). Las URLs
cambian de vez en cuando, así que cada una se puede sobrescribir con una variable
`FISCALITO_SAT_LISTA_<LISTA>_URL` (p. ej. `FISCALITO_SAT_LISTA_69B_URL`).

- `69b` — `Listado_Completo_69-B.csv`: presuntos, definitivos, desvirtuados y sentencias
  favorables en UN archivo, con la columna "Situación del contribuyente". URL confirmada
  como la fuente que citan los scrapers públicos (Apify `scrapers_lat/sat-69b-scraper`,
  campo `sourceUrl`, consultado 2026-10-19). # POR CONFIRMAR CON EL SERVICIO REAL: el
  sandbox no resuelve sat.gob.mx; no se descargó desde aquí.
- Listas del art. 69 (no localizados, créditos firmes, exigibles, cancelados, sentencias):
  # URL POR CONFIRMAR: nombres de archivo tomados del portal de datos abiertos del SAT de
  memoria, no verificados. Por eso NO están activas por default: se encienden con
  `FISCALITO_SAT_LISTAS_ACTIVAS=69b,69_no_localizados,...` después de comprobar la URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno, cliente_http, revisar

BASE = "http://omawww.sat.gob.mx/cifras_sat/Documents"

# lista → (URL por default, descripción)
LISTAS: dict[str, tuple[str, str]] = {
    "69b": (f"{BASE}/Listado_Completo_69-B.csv",
            "Art. 69-B: operaciones inexistentes (EFOS)"),
    "69_no_localizados": (f"{BASE}/No%20localizados.csv",  # URL POR CONFIRMAR
                          "Art. 69: no localizados"),
    "69_firmes": (f"{BASE}/Firmes.csv", "Art. 69: créditos fiscales firmes"),  # POR CONFIRMAR
    "69_exigibles": (f"{BASE}/Exigibles.csv",  # URL POR CONFIRMAR
                     "Art. 69: créditos exigibles"),
    "69_cancelados": (f"{BASE}/Cancelados.csv",  # URL POR CONFIRMAR
                      "Art. 69: créditos cancelados"),
    "69_sentencias": (f"{BASE}/Sentencias.csv",  # URL POR CONFIRMAR
                      "Art. 69: sentencia condenatoria por delito fiscal"),
}

ACTIVAS_DEFAULT = "69b"
# Un listado completo del 69-B pesa unos MB; el tope evita llenar memoria con otra cosa.
MAX_BYTES = 80 * 1024 * 1024


def listas_activas() -> list[str]:
    """Las listas que se descargan (`FISCALITO_SAT_LISTAS_ACTIVAS`, default sólo 69-B)."""
    valor = os.environ.get("FISCALITO_SAT_LISTAS_ACTIVAS", "").strip() or ACTIVAS_DEFAULT
    activas = [x.strip().lower() for x in valor.split(",") if x.strip()]
    desconocidas = [x for x in activas if x not in LISTAS]
    if desconocidas:
        raise ValueError(f"Listas desconocidas en FISCALITO_SAT_LISTAS_ACTIVAS: {desconocidas}")
    return activas


def url_de(lista: str) -> str:
    """La URL vigente de la lista: la variable si existe, si no el default."""
    variable = f"FISCALITO_SAT_LISTA_{lista.upper()}_URL"
    return os.environ.get(variable, "").strip() or LISTAS[lista][0]


class SatListas(Protocol):
    def descargar(self, lista: str) -> tuple[bytes, str]:
        """Los bytes del CSV y la URL de donde salió."""
        ...


# CSV sintético con la forma del listado completo del 69-B: dos renglones de título antes
# del encabezado, latin-1, fechas dd/mm/aaaa. RFC inventados (no existen).
CSV_69B_FALSO = (
    "Información actualizada al 15 de octubre de 2026\r\n"
    "Listado completo de contribuyentes (Artículo 69-B del Código Fiscal de la Federación)\r\n"
    "No,RFC,Nombre del Contribuyente,Situación del contribuyente,"
    "Número y fecha de oficio global de presunción SAT,Publicación página SAT presuntos,"
    "Número y fecha de oficio global de presunción DOF,Publicación DOF presuntos,"
    "Número y fecha de oficio global de definitivos SAT,Publicación página SAT definitivos,"
    "Número y fecha de oficio global de definitivos DOF,Publicación DOF definitivos\r\n"
    '1,EFO010101AA1,"EMPRESA FACTURADORA SINTETICA, S.A. DE C.V.",Definitivo,'
    "500-05-2026-0001 de fecha 10 de enero de 2026,10/01/2026,"
    "500-05-2026-0001 de fecha 10 de enero de 2026,15/01/2026,"
    "500-05-2026-0101 de fecha 10 de mayo de 2026,10/05/2026,"
    "500-05-2026-0101 de fecha 10 de mayo de 2026,15/05/2026\r\n"
    "2,PRE020202BB2,PRESUNTA SINTETICA SA DE CV,Presunto,"
    "500-05-2026-0002 de fecha 1 de agosto de 2026,01/08/2026,"
    "500-05-2026-0002 de fecha 1 de agosto de 2026,05/08/2026,,,,\r\n"
)


@dataclass
class SatListasFalso:
    """Sin red. `contenidos` fija el CSV por lista (bytes); sin entrada, 69-B sintético."""

    contenidos: dict[str, bytes] = field(default_factory=dict)
    descargas: list[str] = field(default_factory=list)

    def descargar(self, lista: str) -> tuple[bytes, str]:
        self.descargas.append(lista)
        if lista in self.contenidos:
            return self.contenidos[lista], f"falso://{lista}"
        if lista == "69b":
            return CSV_69B_FALSO.encode("latin-1"), "falso://69b"
        return b"RFC,RAZON SOCIAL,SUPUESTO\r\n", f"falso://{lista}"


class SatListasPortal:
    """Descarga del portal de datos abiertos del SAT."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        # El portal redirige de http a https y a veces entre servidores.
        self.http = cliente_http(http, follow_redirects=True)

    def descargar(self, lista: str) -> tuple[bytes, str]:
        if lista not in LISTAS:
            raise ValueError(f"Lista desconocida: {lista}")
        url = url_de(lista)
        try:
            r = self.http.get(url, timeout=httpx.Timeout(120.0, connect=15.0))
        except httpx.HTTPError as e:
            raise ErrorServicioExterno(f"No se pudo descargar la lista {lista} ({url}): {e}") from e
        revisar(r, f"SAT (lista {lista})")
        if len(r.content) > MAX_BYTES:
            raise ErrorServicioExterno(f"La lista {lista} pesa más de lo esperado; no se carga.")
        tipo = r.headers.get("content-type", "").lower()
        if "html" in tipo:
            raise ErrorServicioExterno(
                f"El SAT respondió una página HTML en vez del CSV de {lista} ({url}): la URL "
                f"probablemente cambió. Corrígela con FISCALITO_SAT_LISTA_{lista.upper()}_URL."
            )
        return r.content, url


_DESCRIPCION = "Listados públicos del SAT (art. 69-B EFOS y art. 69)"
registro.registrar("sat_listas", "falso", SatListasFalso, _DESCRIPCION)
registro.registrar("sat_listas", "sat", SatListasPortal, _DESCRIPCION)


def obtener_sat_listas() -> SatListas:
    return registro.obtener("sat_listas")
