"""
Estados de cuenta en PDF de los bancos principales (P2-06).

# POR CONFIRMAR CON PDF REAL: NINGUNO de estos diseños se verificó contra un PDF real de
# su banco (no hay estados de cuenta reales en el repo, y no deben entrar: son datos
# personales). Cada banco se describe con un `DisenoBanco` que imita el diseño público de su
# estado de cuenta de cheques/empresarial, y se probó con un PDF SINTÉTICO que reproduce ese
# texto (`tests/plan_p/test_conciliacion.py`). Un PDF real puede partir las líneas distinto,
# traer columnas en otro orden o fechas en otro formato. Si un PDF real no se lee:
#   1. el endpoint de importación responde 422 con el texto de las primeras líneas para
#      diagnosticar, y
#   2. siempre queda la vía segura: exportar el estado a CSV/XLSX desde la banca en línea e
#      importarlo con una plantilla de columnas (`lectores.py`).
#
# CÓMO SE LEE UN RENGLÓN
# ----------------------
# `pypdf` extrae el texto por líneas y pierde las columnas, así que en una línea como
#     "15/ENE  SPEI RECIBIDO ACME SA  REF 123  1,500.00  11,500.00"
# no se sabe si 1,500.00 era cargo o abono. Se resuelve con el SALDO: si el renglón trae
# importe y saldo, el signo es el que hace cuadrar `saldo_anterior ± importe = saldo`. Sin
# saldo (renglón sin columna de saldo), se usan las palabras del concepto (`_PALABRAS_ABONO`)
# y, si no hay ninguna, se toma como cargo y se ADVIERTE en el reporte de importación.
#
# Las líneas que no empiezan con fecha se pegan al concepto del renglón anterior (los bancos
# parten el concepto en varias líneas).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from app.contabilidad.conciliacion.lectores import (
    CERO,
    LecturaEstado,
    MovimientoLeido,
    fecha,
    importe,
    normalizar,
    validar_tamano,
)
from app.exceptions import FiscalAgentError

_NUM = r"-?\$?\s?\d{1,3}(?:,\d{3})*\.\d{2}-?"


@dataclass(frozen=True)
class DisenoBanco:
    clave: str  # c_Banco del SAT
    nombre: str
    # Texto (normalizado: minúsculas, sin acentos) que identifica al banco en el PDF.
    marcas: tuple[str, ...]
    # Fecha al inicio del renglón.
    fecha_renglon: str = r"(\d{1,2}[/-](?:[a-z]{3}|\d{1,2})(?:[/-]\d{2,4})?)"
    # Del periodo se saca el año cuando el renglón trae sólo día y mes.
    periodo: str = r"periodo[^\n]*?(\d{1,2}[/ -](?:[a-z]{3,10}|\d{1,2})[/ -]\d{4})"
    saldo_inicial: str = r"saldo (?:inicial|anterior)[^\d\-$]*(" + _NUM + ")"
    saldo_final: str = r"saldo (?:final|actual|al corte)[^\d\-$]*(" + _NUM + ")"


# POR CONFIRMAR CON PDF REAL — los 10 diseños de abajo.
DISENOS: tuple[DisenoBanco, ...] = (
    DisenoBanco("012", "BBVA México", ("bbva",)),
    DisenoBanco("002", "Banamex / Citi", ("banamex", "citibanamex", "banco nacional de mexico")),
    DisenoBanco("014", "Santander", ("santander",)),
    DisenoBanco("072", "Banorte", ("banorte",)),
    DisenoBanco("021", "HSBC", ("hsbc",)),
    DisenoBanco("044", "Scotiabank", ("scotiabank",)),
    DisenoBanco("137", "BanCoppel", ("bancoppel",)),
    DisenoBanco("058", "Banregio", ("banregio",)),
    DisenoBanco("036", "Inbursa", ("inbursa",)),
    DisenoBanco("030", "BanBajío", ("bajio", "banbajio")),
)

POR_CLAVE = {d.clave: d for d in DISENOS}

_PALABRAS_ABONO = ("deposito", "abono", "spei recibido", "recibido", "traspaso de",
                   "devolucion", "intereses ganados", "interes a favor", "pago recibido")


def texto_pdf(datos: bytes) -> str:
    validar_tamano(datos)
    if not datos.lstrip()[:5].startswith(b"%PDF-"):
        raise FiscalAgentError("El archivo no es un PDF.", 422)
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(datos))
        return "\n".join((p.extract_text() or "") for p in lector.pages[:60])
    except Exception as e:  # noqa: BLE001
        raise FiscalAgentError("No se pudo leer el texto del PDF (¿escaneado o cifrado?). "
                               "Exporta el estado a CSV/XLSX y usa una plantilla.", 422) from e


def detectar_banco(texto: str) -> DisenoBanco | None:
    plano = normalizar(texto[:4000])
    return next((d for d in DISENOS if any(m in plano for m in d.marcas)), None)


def _anio_del_periodo(plano: str, diseno: DisenoBanco) -> int | None:
    m = re.search(diseno.periodo, plano)
    if m:
        f = fecha(m.group(1))
        if f:
            return f.year
    m = re.search(r"\b(20\d{2})\b", plano)
    return int(m.group(1)) if m else None


def leer_pdf(datos: bytes, banco: str | None = None) -> tuple[LecturaEstado, DisenoBanco]:
    """Lee un estado de cuenta PDF. `banco` (c_Banco) fuerza el diseño; si no, se detecta."""
    texto = texto_pdf(datos)
    if not texto.strip():
        raise FiscalAgentError("El PDF no trae texto (¿escaneado?). Exporta a CSV/XLSX.", 422)
    diseno = POR_CLAVE.get(banco or "") or detectar_banco(texto)
    if diseno is None:
        raise FiscalAgentError(
            "No se reconoció el banco del PDF. Bancos con lector: "
            + ", ".join(d.nombre for d in DISENOS) + ". Usa una plantilla CSV/XLSX.", 422)
    plano_total = normalizar(texto)
    anio = _anio_del_periodo(plano_total, diseno)
    lectura = LecturaEstado()
    m = re.search(diseno.saldo_inicial, plano_total)
    if m:
        lectura.saldo_inicial = importe(m.group(1))
    m = re.search(diseno.saldo_final, plano_total)
    if m:
        lectura.saldo_final = importe(m.group(1))

    patron = re.compile(r"^" + diseno.fecha_renglon + r"\s+(.*)$")
    renglones: list[tuple[str, str]] = []  # (fecha, resto)
    for linea in texto.splitlines():
        plano = normalizar(linea)
        if not plano or re.match(r"saldo (inicial|anterior|final|actual|al corte)", plano):
            continue
        m = patron.match(plano)
        if m and fecha(m.group(1), anio_defecto=anio):
            renglones.append((m.group(1), linea.strip()[len(m.group(1)):].strip()))
        elif renglones and not re.search(_NUM + r"\s*$", plano):
            f, resto = renglones[-1]
            # Línea de continuación: se pega antes de los importes del renglón.
            nums = re.findall(_NUM, resto)
            if nums:
                corte = resto.rfind(nums[0]) if len(nums) == 1 else resto.find(nums[0])
                resto = f"{resto[:corte].rstrip()} {linea.strip()} {resto[corte:]}"
            else:
                resto = f"{resto} {linea.strip()}"
            renglones[-1] = (f, resto)

    saldo_previo = lectura.saldo_inicial
    for f_txt, resto in renglones:
        f = fecha(f_txt, anio_defecto=anio)
        if f is None:
            continue
        numeros = re.findall(_NUM, resto)
        if not numeros:
            continue
        valores = [importe(n) for n in numeros]
        corte = resto.rfind(numeros[-1])
        if len(valores) >= 2:
            monto, saldo = abs(valores[-2] or CERO), valores[-1]
            corte = resto.rfind(numeros[-2], 0, corte)
        else:
            monto, saldo = abs(valores[0] or CERO), None
        cuerpo = resto[:corte].strip()
        referencia = ""
        mr = re.search(r"(?:ref(?:erencia)?\.?:?\s*|rastreo:?\s*)([a-z0-9]{4,30})", cuerpo,
                       re.IGNORECASE)
        if mr:
            referencia = mr.group(1).upper()
        es_abono: bool | None = None
        if saldo is not None and saldo_previo is not None:
            if saldo_previo + monto == saldo:
                es_abono = True
            elif saldo_previo - monto == saldo:
                es_abono = False
        if es_abono is None:
            texto_n = normalizar(cuerpo)
            es_abono = any(p in texto_n for p in _PALABRAS_ABONO)
            lectura.advertencias.append(
                f"{f.isoformat()} {monto}: el signo se dedujo del concepto "
                f"({'abono' if es_abono else 'cargo'}); revísalo.")
        lectura.movimientos.append(MovimientoLeido(
            f, re.sub(r"\s+", " ", cuerpo)[:300], referencia[:100],
            CERO if es_abono else monto, monto if es_abono else CERO, saldo))
        if saldo is not None:
            saldo_previo = saldo
        elif saldo_previo is not None:
            saldo_previo += monto if es_abono else -monto
    if not lectura.movimientos:
        muestra = " | ".join(texto.splitlines()[:8])[:400]
        raise FiscalAgentError(
            f"No se encontraron movimientos en el PDF de {diseno.nombre} (diseño POR "
            f"CONFIRMAR). Primeras líneas: {muestra}. Usa una plantilla CSV/XLSX.", 422)
    if lectura.saldo_final is None and lectura.movimientos[-1].saldo is not None:
        lectura.saldo_final = lectura.movimientos[-1].saldo
    return lectura, diseno
