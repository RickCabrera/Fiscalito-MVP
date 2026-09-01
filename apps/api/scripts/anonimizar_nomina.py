"""
Genera las fixtures anonimizadas de nómina (S-04) del bimestre marzo-abril.

Lee "03. CFDI DE NOMINA/" en SOLO LECTURA y escribe únicamente en
apps/api/tests/fixtures/nomina/. Nunca modifica el origen, y nunca copia el
árbol de archivos: junto a los 70 XML hay 78 PDF con nombre, RFC, CURP, NSS y
montos en claro que jamás deben entrar al repo. Sí se parsea y muta el árbol
XML de cada comprobante, que es lo que preserva verbatim los atributos intactos
y hace que la aserción de multiset signifique algo.

Uso:
    python apps/api/scripts/anonimizar_nomina.py [--revisar-texto-libre]

Se corre UNA VEZ. No regenerar: la asignación de identidades se baraja y se
descarta, así que una segunda corrida movería a las personas entre E-01..E-09 y
rompería en silencio los valores esperados que F1-03/F1-04 construyan encima.

────────────────────────────────────────────────────────────────────────────
RIESGOS RESIDUALES ACEPTADOS POR RICARDO (2026-09-01)
────────────────────────────────────────────────────────────────────────────

1. La antigüedad publicada es FICTICIA. La fecha de alta se deriva del primer
   periodo del empleado en las propias fixtures y de su indice sintetico, no de
   la real: no hay fuga, pero tampoco refleja la antiguedad verdadera ni su
   orden entre empleados. Es irrelevante para F1 (ver D9: el SDI se toma como
   dato de entrada y no se deriva de la antiguedad) y es el precio de que la
   fecha real no sea reconstruible.

   Historia, porque el modo de fallo es instructivo: la primera version sorteaba
   un corrimiento acotado contra la fecha real. Cuando la holgura era corta el
   rango colapsaba a un solo valor, el corrimiento se volvia la constante 40 y,
   con el script versionado, la fecha real se despejaba al dia para 3 de los 9
   empleados. Un corrimiento derivado del dato que se quiere esconder no es
   anonimizacion, por mucho que se sortee.

2. `ClaveEntFed` se conserva (lo pide PLAN_NOMINA §5.8 para el ISN). Con 9
   empleados, montos exactos y estructura semanal, el k-anonimato es bajo:
   entidad más tamaño de nómina acota mucho. Aceptado por escrito, por dos
   razones: el repo es privado y todas las identidades son sintéticas.

3. Dos empleados aparecen solo en 3 y en 4 de las 9 semanas, así que su fecha de
   baja queda anclada a una ventana de 7 días. No se corrige: la transición
   9 -> 7 es justamente lo que el backlog pide del caso.

Nota para F1: el SalarioDiarioIntegrado de este caso NO se puede recomputar
desde la antigüedad. Los factores implícitos son superiores al mínimo de ley,
distintos entre empleados y no monótonos con la antigüedad. Se trata como dato
de entrada. Ver docs/decisiones-nomina.md §D5/§D9.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import secrets
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
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
CERTIFICADO_SINTETICO = _inv.CERTIFICADO_SINTETICO
EMPLEADOS_SINTETICOS = _inv.EMPLEADOS_SINTETICOS
ESCALERA_ANTIGUEDAD_DIAS = _inv.ESCALERA_ANTIGUEDAD_DIAS
GENERICOS = _inv.GENERICOS
NO_CERTIFICADO_SAT_SINTETICO = _inv.NO_CERTIFICADO_SAT_SINTETICO
NO_CERTIFICADO_SINTETICO = _inv.NO_CERTIFICADO_SINTETICO
NS = _inv.NS
PATRON_SINTETICO = _inv.PATRON_SINTETICO
REPARTO_SEMANAL = _inv.REPARTO_SEMANAL
RFC_PAC_SINTETICO = _inv.RFC_PAC_SINTETICO
SELLO_SINTETICO = _inv.SELLO_SINTETICO
TEXTO_LIBRE_A_REVISAR = _inv.TEXTO_LIBRE_A_REVISAR
TOTAL_ARCHIVOS = _inv.TOTAL_ARCHIVOS

# Se registran los 4 prefijos o ElementTree serializa como ns0:, ns1:...
for _pre, _uri in NS.items():
    ET.register_namespace(_pre, _uri)

RAIZ = Path(__file__).resolve().parents[3]
ORIGEN = RAIZ / "03. CFDI DE NOMINA"
DESTINO = RAIZ / "apps" / "api" / "tests" / "fixtures" / "nomina"



def q(prefijo: str, nombre: str) -> str:
    """'cfdi:Comprobante' -> '{uri}Comprobante'."""
    return f"{{{NS[prefijo]}}}{nombre}"


def _validar_destino() -> None:
    """El destino cae dentro del repo, fuera del origen y en la ruta esperada.

    La version anterior comparaba DESTINO.resolve() contra una re-derivacion
    literal de la misma expresion desde el mismo RAIZ: no podia fallar nunca.
    Una guardia que no puede fallar es peor que ninguna, porque se lee como
    proteccion sin serlo.
    """
    destino, origen, raiz = DESTINO.resolve(), ORIGEN.resolve(), RAIZ.resolve()
    if not destino.is_relative_to(raiz):
        sys.exit(f"ABORTA: el destino cae fuera del repo: {destino}")
    if destino == origen or destino.is_relative_to(origen):
        sys.exit(f"ABORTA: el destino cae dentro del origen: {destino}")
    if destino.name != "nomina" or destino.parent.name != "fixtures":
        sys.exit(f"ABORTA: el destino no es tests/fixtures/nomina: {destino}")


def _archivos_origen() -> list[Path]:
    archivos = sorted(
        p for p in ORIGEN.glob("0[34]*/**/*.xml") if p.is_file()
    )
    if len(archivos) != TOTAL_ARCHIVOS:
        sys.exit(f"ABORTA: se esperaban {TOTAL_ARCHIVOS} XML y hay {len(archivos)}")
    return archivos


def revisar_texto_libre(archivos: list[Path]) -> None:
    """Imprime a stdout los valores de texto libre que se van a CONSERVAR.

    Declarar un atributo como intacto no prueba que su valor esté limpio: prueba
    que decidimos no mirarlo. Son pocos valores; se revisan a ojo antes de
    commitear. Nunca se escriben a archivo.
    """
    vistos: dict[str, set[str]] = {}
    for ruta in archivos:
        arbol = ET.parse(ruta)
        for prefijo_elem, attr in TEXTO_LIBRE_A_REVISAR:
            pre, nom = prefijo_elem.split(":")
            for el in arbol.getroot().iter(q(pre, nom)):
                if (v := el.get(attr)) is not None:
                    vistos.setdefault(f"{prefijo_elem}@{attr}", set()).add(v)
    print("Valores de texto libre que se CONSERVAN (revisar antes de commitear):")
    for clave in sorted(vistos):
        print(f"\n  {clave}")
        for v in sorted(vistos[clave]):
            print(f"    - {v}")


def _alta_publicada(primer_periodo: date, indice_sintetico: int) -> date:
    """Fecha de alta derivada SOLO de datos publicos.

    No depende de la fecha real ni del orden real de antiguedades: solo del
    primer periodo del empleado (que va intacto en las fixtures) y de su indice
    sintetico, que ya es una permutacion independiente del origen. Es no
    invertible por construccion.

    La version anterior acotaba el sorteo contra la fecha real y, cuando la
    holgura era corta, el rango colapsaba a un solo valor: el corrimiento se
    volvia la constante 40 y la fecha real se despejaba al dia. Con el script
    publicado, eso era una fuga exacta para 3 de los 9 empleados.
    """
    return primer_periodo - timedelta(days=ESCALERA_ANTIGUEDAD_DIAS[indice_sintetico])


def _antiguedad(alta: date, fin_periodo: date) -> str:
    """`ceil(días/7)`, elegido explícitamente.

    En el origen `ceil` y `round` aciertan igual, pero solo porque todas las
    altas caen en el mismo residuo módulo 7. En cuanto el corrimiento no es
    múltiplo de 7 divergen, así que la elección se fija aquí y no se deja al azar.
    """
    return f"P{math.ceil((fin_periodo - alta).days / 7)}W"


def anonimizar() -> None:
    _validar_destino()
    archivos = _archivos_origen()

    # Identidades barajadas con secrets; el mapeo vive solo en memoria.
    pool = list(EMPLEADOS_SINTETICOS)
    orden = list(range(len(pool)))
    for i in range(len(orden) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        orden[i], orden[j] = orden[j], orden[i]

    # Un RFC real -> un índice del pool barajado. El orden de descubrimiento no
    # puede venir del nombre de archivo (empiezan con el RFC del patrón) ni del
    # orden alfabético de RFC (filtraría el orden de apellidos): se asigna sobre
    # el recorrido cronológico ya barajado.
    asignado: dict[str, int] = {}
    primer_periodo: dict[str, date] = {}

    for ruta in archivos:
        r = ET.parse(ruta).getroot()
        rfc = r.find(q("cfdi", "Receptor")).get("Rfc")
        nom = r.find(f".//{q('nomina12', 'Nomina')}")
        ini = date.fromisoformat(nom.get("FechaInicialPago")[:10])
        if rfc not in asignado:
            asignado[rfc] = orden[len(asignado)]
            primer_periodo[rfc] = ini
        primer_periodo[rfc] = min(primer_periodo[rfc], ini)

    altas = {rfc: _alta_publicada(primer_periodo[rfc], asignado[rfc]) for rfc in asignado}

    # Pre-pasada: los guardias corren ANTES de borrar nada, para no dejar el
    # destino a medias si un archivo tardio trae algo inesperado.
    permitidos = {q("tfd", "TimbreFiscalDigital"), q("nomina12", "Nomina")}
    for ruta in archivos:
        raiz = ET.parse(ruta).getroot()
        if raiz.find(q("cfdi", "Addenda")) is not None:
            sys.exit(f"ABORTA: {ruta.name} trae Addenda")
        for comp in raiz.iter(q("cfdi", "Complemento")):
            for hijo in list(comp):
                if hijo.tag not in permitidos:
                    sys.exit(f"ABORTA: Complemento con hijo inesperado {hijo.tag}")

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)

    # Carpetas semanales neutras, en orden cronológico de periodo.
    semanas = sorted({p.parent for p in archivos},
                     key=lambda d: min(
                         date.fromisoformat(
                             ET.parse(x).getroot()
                             .find(f".//{q('nomina12', 'Nomina')}").get("FechaInicialPago")[:10])
                         for x in d.glob("*.xml")))
    idx_semana = {d: f"semana-{i + 1:02d}" for i, d in enumerate(semanas)}

    folio = 0
    generados: list[Path] = []
    for ruta in archivos:
        # ElementTree descarta comentarios y PIs al parsear: no se copian.
        arbol = ET.parse(ruta)
        raiz = arbol.getroot()
        folio += 1

        emisor_c = raiz.find(q("cfdi", "Emisor"))
        emisor_n = raiz.find(f".//{q('nomina12', 'Emisor')}")
        recep_c = raiz.find(q("cfdi", "Receptor"))
        recep_n = raiz.find(f".//{q('nomina12', 'Receptor')}")
        nomina = raiz.find(f".//{q('nomina12', 'Nomina')}")
        timbre = raiz.find(f".//{q('tfd', 'TimbreFiscalDigital')}")

        rfc_real = recep_c.get("Rfc")
        emp = pool[asignado[rfc_real]]

        # Comprobante
        raiz.set("Sello", SELLO_SINTETICO)
        raiz.set("Certificado", CERTIFICADO_SINTETICO)
        raiz.set("NoCertificado", NO_CERTIFICADO_SINTETICO)
        raiz.set("Serie", PATRON_SINTETICO["serie"])
        raiz.set("Folio", str(folio))
        raiz.set("LugarExpedicion", PATRON_SINTETICO["cp"])

        # Fecha y FechaTimbrado: con UUID, sellos y certificado ya sustituidos,
        # estos dos timestamps al segundo son la llave de cruce más fuerte que
        # queda contra los registros del emisor y del PAC. Se normalizan.
        fecha_pago = date.fromisoformat(nomina.get("FechaPago")[:10])
        fecha_comp = datetime.combine(fecha_pago, datetime.min.time()) + timedelta(hours=12)
        raiz.set("Fecha", fecha_comp.strftime("%Y-%m-%dT%H:%M:%S"))
        timbre.set("FechaTimbrado", (fecha_comp + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"))

        # Emisor
        emisor_c.set("Rfc", PATRON_SINTETICO["rfc"])
        emisor_c.set("Nombre", PATRON_SINTETICO["nombre"])
        if emisor_n is not None:
            emisor_n.set("RegistroPatronal", PATRON_SINTETICO["registro_patronal"])

        # Receptor
        recep_c.set("Rfc", emp["rfc"])
        recep_c.set("Nombre", emp["nombre"])
        recep_c.set("DomicilioFiscalReceptor", emp["cp"])
        recep_n.set("Curp", emp["curp"])
        recep_n.set("NumSeguridadSocial", emp["nss"])
        recep_n.set("NumEmpleado", f"E-{asignado[rfc_real] + 1:02d}")

        alta = altas[rfc_real]
        recep_n.set("FechaInicioRelLaboral", alta.isoformat())
        recep_n.set(ANTIGUEDAD, _antiguedad(
            alta, date.fromisoformat(nomina.get("FechaFinalPago")[:10])))
        for attr, valor in GENERICOS.items():
            if recep_n.get(attr) is not None:
                recep_n.set(attr, valor)

        # Timbre
        timbre.set("UUID", str(_uuid4_sintetico()).upper())
        timbre.set("SelloCFD", SELLO_SINTETICO)
        timbre.set("SelloSAT", SELLO_SINTETICO)
        timbre.set("NoCertificadoSAT", NO_CERTIFICADO_SAT_SINTETICO)
        timbre.set("RfcProvCertif", RFC_PAC_SINTETICO)

        carpeta = DESTINO / idx_semana[ruta.parent]
        carpeta.mkdir(exist_ok=True)
        # Nombre generado: los del origen empiezan con el RFC del patrón.
        salida = carpeta / f"{recep_n.get('NumEmpleado')}.xml"
        tmp = salida.with_suffix(".tmp")
        arbol.write(str(tmp), encoding="UTF-8", xml_declaration=True)
        tmp.replace(salida)
        generados.append(salida)

    reparto = [len(list((DESTINO / idx_semana[d]).glob("*.xml"))) for d in semanas]
    if reparto != REPARTO_SEMANAL:
        sys.exit(f"ABORTA: reparto semanal {reparto}, esperado {REPARTO_SEMANAL}")
    print(f"Generadas {len(generados)} fixtures en {DESTINO.relative_to(RAIZ)}")
    print(f"Reparto semanal: {reparto}")


def _uuid4_sintetico() -> str:
    b = bytearray(secrets.token_bytes(16))
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--revisar-texto-libre", action="store_true",
                    help="Imprime los valores de texto libre que se conservan y sale")
    args = ap.parse_args()
    if not ORIGEN.exists():
        sys.exit(f"ABORTA: no existe {ORIGEN}")
    if args.revisar_texto_libre:
        revisar_texto_libre(_archivos_origen())
    else:
        anonimizar()
