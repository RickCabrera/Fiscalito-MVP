"""
Guardia de privacidad (P6-05): ningún RFC real en el repo.

Recorre lo que se sirve al público (`apps/store/public`), el código del front,
el código y los tests de la API, la base de conocimiento y los documentos, y
falla si encuentra un RFC con forma válida que no esté en la lista blanca.

Lista blanca:
- RFC genéricos y de prueba publicados por el SAT (público en general,
  extranjeros, certificados de prueba del SAT).
- RFC de proveedores de certificación (PAC) que aparecen en fixtures de
  respuestas de timbrado: son empresas, no personas, y su RFC es público.
- RFC sintéticos con prefijo reconocible: `SINT` (persona física) y `SIN`
  (persona moral), siempre con fecha `010101`. Es el prefijo a usar para
  cualquier fixture nueva.
- RFC sintéticos heredados (inventados a mano antes de fijar el prefijo).
  Cualquiera que se agregue aquí tiene que ser inventado, nunca copiado de un
  CFDI real.

Si este test falla por un RFC nuevo: no lo agregues a la lista sin más —
confirma que es sintético y, de preferencia, cámbialo al prefijo `SIN`/`SINT`.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]

# Carpetas y archivos que se revisan (relativos a la raíz del monorepo).
ALCANCE = [
    "apps/store/public",
    "apps/store/src",
    "apps/api/app",
    "apps/api/tests",
    "apps/api/knowledge_base",
    "docs",
    "README.md",
    "backlog.md",
    "CLAUDE.md",
    "apps/api/CLAUDE.md",
    "apps/store/CLAUDE.md",
]

EXTENSIONES = {
    ".py", ".ts", ".tsx", ".js", ".json", ".xml", ".md", ".txt", ".csv",
    ".yml", ".yaml", ".html", ".css", ".toml", ".env", ".example",
}

CARPETAS_IGNORADAS = {"node_modules", "dist", ".venv", "__pycache__", ".git"}

# RFC públicos del SAT y de PAC (empresas), no identifican a ninguna persona.
RFC_PUBLICOS = {
    "XAXX010101000",  # Público en general (SAT)
    "XEXX010101000",  # Residentes en el extranjero (SAT)
    "EKU9003173C9",   # Certificado de prueba del SAT (persona moral)
    "XIQB891116QE4",  # Certificado de prueba del SAT (persona física)
    "XIA190128J61",   # Certificado de prueba del SAT (persona moral)
    "SAT970701NN3",   # Servicio de Administración Tributaria
    "FIN1203015JA",   # Finkok (PAC), fixtures de timbrado
    "LSO1306189R5",   # SW Sapien (PAC), fixtures de timbrado
}

# Prefijo oficial para fixtures nuevas: SINT (física) / SIN (moral) + 010101.
PATRON_SINTETICO = re.compile(r"^SINT?010101[A-Z0-9]{3}$")

# Sintéticos heredados: inventados a mano en tests y docs antes de P6-05.
RFC_SINTETICOS_HEREDADOS = {
    "AAA000000AA0", "AAA000101AAA", "AAA010101AAA", "AAAA000101AAA",
    "ABC010101AB1", "ABCD010101AB1", "ABCD210101XY1", "ABCD210199XY1",
    "AND010101AB1", "ARRE010101ABC", "ARRE800101ABC", "ARRN010101AB1",
    "BBB000000BB0", "BBB010101BB1", "BBB010101BBB", "CAUA030101ABC",
    "CLIE010101AB1", "COM010101AAA", "COM010101BB2", "ÑAND010101AB1",
    "DES010101AAA", "DES010101AB1", "DES030303CC3", "EFO010101AA1",
    "EMP010101AB1", "EMPR010101AB1", "FAL010101AA0", "FRO010101CC3",
    "GOPE900515XYZ", "GOVA700101AB3", "INQU010101AB1", "LOAM850505AB2",
    "LOP800101AB1", "LOPT800101AB1", "NOL060606FF6", "NUE050505EE5",
    "OTR010101AA1", "PEPJ800101AB1", "PERJ800101AB1", "PERJ800103AB1",
    "PERJ800105AB1", "PERJ800109AB1", "PLAT010101AB2", "PLAT020101AB1",
    "PLAT030101AB1", "PMS010101AB1", "PPD010101DD4", "PRE020202BB2",
    "PRO010101AA1", "PYME123456ABC", "RERR800101XXX", "RESI010101AB3",
    "RESI020101AB1", "SEN040404DD4", "TAL010101AB1", "TDC010101AAA",
    "TEST010101AB1", "TNO010101AB1", "TRAB010101AA1", "VIE700101XY9",
    "VIEJ700101XY9", "XAAA010101AA1", "XABB010101AA2", "XACC010101AA3",
    "XADD010101AA4", "XAEE010101AA5", "XAFF010101AA6", "XAGG010101AA7",
    "XAHH010101AA8", "XAII010101AA9", "XAP0101011X0", "XAP0101012X1",
    "XAXX010101AB1", "XBXX020202BC2", "XEXX010101AB1",
}

# Forma de un RFC: 3 (moral) o 4 (física) letras + AAMMDD + homoclave.
PATRON_RFC = re.compile(r"\b([A-ZÑ&]{3,4})([0-9]{2})([0-9]{2})([0-9]{2})([A-Z0-9]{3})\b")


def _es_fecha_plausible(mm: str, dd: str) -> bool:
    return 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31


def _permitido(rfc: str) -> bool:
    return (
        rfc in RFC_PUBLICOS
        or rfc in RFC_SINTETICOS_HEREDADOS
        or PATRON_SINTETICO.match(rfc) is not None
    )


def _archivos():
    for entrada in ALCANCE:
        ruta = RAIZ / entrada
        assert ruta.exists(), f"Alcance inexistente: {entrada}"
        if ruta.is_file():
            yield ruta
            continue
        for archivo in ruta.rglob("*"):
            if not archivo.is_file():
                continue
            if CARPETAS_IGNORADAS & set(archivo.relative_to(RAIZ).parts):
                continue
            if archivo.suffix.lower() in EXTENSIONES:
                yield archivo


def _rfcs_en(texto: str) -> set[str]:
    encontrados = set()
    for m in PATRON_RFC.finditer(texto):
        if _es_fecha_plausible(m.group(3), m.group(4)):
            encontrados.add(m.group(0))
    return encontrados


def test_ningun_rfc_fuera_de_la_lista_blanca():
    sospechosos: dict[str, set[str]] = {}
    for archivo in _archivos():
        try:
            texto = archivo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rfc in _rfcs_en(texto):
            if not _permitido(rfc):
                sospechosos.setdefault(rfc, set()).add(
                    str(archivo.relative_to(RAIZ))
                )
    detalle = "\n".join(
        f"  {rfc}: {', '.join(sorted(rutas))}" for rfc, rutas in sorted(sospechosos.items())
    )
    assert not sospechosos, (
        "RFC fuera de la lista blanca (¿es real? anonimízalo con prefijo SIN/SINT):\n"
        + detalle
    )


def test_demo_xmls_publicas_usan_rfc_sinteticos():
    """Lo que se sirve en /demo-xmls sólo lleva RFC públicos o con prefijo SIN/SINT."""
    carpeta = RAIZ / "apps/store/public/demo-xmls"
    xmls = list(carpeta.rglob("*.xml"))
    assert xmls, "no hay demo-xmls que revisar"
    for xml in xmls:
        for rfc in _rfcs_en(xml.read_text(encoding="utf-8")):
            assert rfc in RFC_PUBLICOS or PATRON_SINTETICO.match(rfc), (
                f"{xml.name}: RFC {rfc} no es público ni sintético con prefijo"
            )


def test_la_guardia_detecta_un_rfc_real_de_forma():
    """El patrón reconoce un RFC de persona física con fecha real y lo rechaza."""
    # Se arma por partes para que este archivo no contenga el RFC de ejemplo.
    rfc_real_de_forma = "ABCD" + "850315" + "XY9"
    texto = f'Emisor Rfc="{rfc_real_de_forma}" Nombre="X"'
    encontrados = _rfcs_en(texto)
    assert encontrados == {rfc_real_de_forma}
    assert not _permitido(rfc_real_de_forma)
    assert _permitido("SINT010101PF1")
    assert _permitido("SIN010101PM1")
