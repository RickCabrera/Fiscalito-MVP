"""
Layout de la carga masiva (batch) de la DIOT, ejercicios 2025 en adelante (P3-05).

FUENTE
------
SAT, "Instructivo para el armado del archivo de carga masiva — Declaración informativa de
operaciones con terceros (DIOT)", enero de 2025, sección 3 ("ejercicios 2025 en adelante"),
publicado en la plataforma de declaraciones del SAT:
https://wu1pteprostadeclara.blob.core.windows.net/plantillas-imagenes/AyudaCargaMasiva77.pdf
(copia: https://www.mendezalvarado.com.mx/wp-content/uploads/2025-02-06-DIOT_2025_Ayuda_Carga_Masiva.pdf),
consultado el 2026-10-19. Desde febrero de 2025 el SAT rechaza el layout anterior de 25
campos ("se esperan 54 campos y se están recibiendo 25", ElConta.MX 2025-02-06).

Reglas generales del instructivo: separador `|` entre todos los datos; codificación UTF-8;
importes **enteros, sin decimales**, el cero se acepta; campos que no aplican, vacíos.
El instructivo no numera los campos: el número de abajo es su orden de aparición en la
sección 3, que es el orden del archivo.

Catálogos (sección 3.1): tipo de tercero 04 Proveedor nacional, 05 Proveedor extranjero,
15 Proveedor global. Tipo de operación: 02 Enajenación de bienes (nacional y extranjero),
03 Prestación de servicios profesionales (nacional y extranjero), 06 Uso o goce temporal de
bienes (nacional), 07 Importación de bienes o servicios (extranjero), 08 Importación por
transferencia virtual (nacional), 85 Otros (nacional), 87 Operaciones globales (global).
Campo 54 (efectos fiscales): 01 Sí, 02 No. Global: RFC XAXX010101000.

Lo que el instructivo NO dice: la regla de redondeo a enteros. DECISIÓN PROVISIONAL:
ROUND_HALF_UP al peso, por campo, después de sumar por proveedor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TIPOS_TERCERO = {"04": "Proveedor nacional", "05": "Proveedor extranjero",
                 "15": "Proveedor global"}
OPERACIONES = {
    "02": "Enajenación de bienes", "03": "Prestación de servicios profesionales",
    "06": "Uso o goce temporal de bienes", "07": "Importación de bienes o servicios",
    "08": "Importación por transferencia virtual", "85": "Otros",
    "87": "Operaciones globales",
}
OPERACIONES_POR_TERCERO = {"04": {"02", "03", "06", "08", "85"}, "05": {"02", "03", "07"},
                           "15": {"87"}}
RFC_GLOBAL = "XAXX010101000"
RFC_EXTRANJERO = "XEXX010101000"
_RE_RFC = re.compile(r"^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$")
_RE_IMPORTE = re.compile(r"^[0-9]{1,14}$")


@dataclass(frozen=True)
class Campo:
    numero: int
    clave: str
    descripcion: str
    tipo: str = "importe"  # importe | codigo | texto
    maximo: int = 14
    devolucion_de: int | None = None  # devoluciones ≤ valor del campo indicado


def _importe(n: int, clave: str, descripcion: str, devolucion_de: int | None = None) -> Campo:
    return Campo(n, clave, descripcion, "importe", 14, devolucion_de)


_SECCIONES = ("region_norte", "region_sur", "tasa_16", "importacion_tangibles",
              "importacion_intangibles")
_SECC_TXT = ("región fronteriza norte", "región fronteriza sur", "tasa 16% de IVA",
             "importación de bienes tangibles 16%",
             "importación de bienes intangibles y servicios 16%")

_campos: list[Campo] = [
    Campo(1, "tipo_tercero", "Tipo de tercero", "codigo", 2),
    Campo(2, "tipo_operacion", "Tipo de operación", "codigo", 2),
    Campo(3, "rfc", "RFC", "texto", 13),
    Campo(4, "id_fiscal", "Número de identificación fiscal", "texto", 40),
    Campo(5, "nombre_extranjero", "Nombre del extranjero", "texto", 300),
    Campo(6, "pais", "País o jurisdicción de residencia fiscal", "texto", 2),
    Campo(7, "jurisdiccion", "Especificar lugar de jurisdicción fiscal", "texto", 300),
]
for i, (s, t) in enumerate(zip(_SECCIONES, _SECC_TXT, strict=True)):
    valor = 8 + 2 * i
    _campos.append(_importe(valor, f"valor_{s}", f"Valor total de actos o actividades pagadas "
                                                 f"/ {t}"))
    _campos.append(_importe(valor + 1, f"devoluciones_{s}",
                            f"Devoluciones, descuentos y bonificaciones / {t}", valor))
for i, (s, t) in enumerate(zip(_SECCIONES, _SECC_TXT, strict=True)):
    _campos.append(_importe(18 + 2 * i, f"acreditable_gravadas_{s}",
                            f"IVA acreditable exclusivamente de actividades gravadas / {t}"))
    _campos.append(_importe(19 + 2 * i, f"acreditable_proporcion_{s}",
                            f"IVA acreditable asociado a actividades con proporción / {t}"))
for i, (s, t) in enumerate(zip(_SECCIONES, _SECC_TXT, strict=True)):
    for j, (motivo, txt) in enumerate((("proporcion", "con proporción"),
                                       ("requisitos", "que no cumplen requisitos"),
                                       ("exentas", "exentas"), ("no_objeto", "no objeto"))):
        _campos.append(_importe(28 + 4 * i + j, f"no_acreditable_{motivo}_{s}",
                                f"IVA no acreditable asociado a actividades {txt} / {t}"))
_campos += [
    _importe(48, "iva_retenido", "IVA retenido por el contribuyente"),
    _importe(49, "importacion_exentos", "Actos o actividades pagados en la importación de "
                                        "bienes y servicios exentos"),
    _importe(50, "exentos", "Actos o actividades pagados exentos"),
    _importe(51, "tasa_0", "Demás actos o actividades pagados a la tasa del 0%"),
    _importe(52, "no_objeto_nacional", "Actos o actividades no objeto del IVA realizados en "
                                       "territorio nacional"),
    _importe(53, "no_objeto_sin_establecimiento", "Actos o actividades no objeto del IVA por "
                                                  "no contar con establecimiento en territorio "
                                                  "nacional"),
    Campo(54, "efectos_fiscales", "Manifiesto de efectos fiscales a los comprobantes de "
                                  "operaciones con el proveedor", "codigo", 2),
]
CAMPOS: tuple[Campo, ...] = tuple(_campos)
POR_CLAVE = {c.clave: c for c in CAMPOS}
assert [c.numero for c in CAMPOS] == list(range(1, 55)), "El layout son 54 campos en orden"


def linea(valores: dict[str, str | int]) -> str:
    """Un renglón del archivo: los 54 campos en orden, separados por `|`."""
    desconocidas = set(valores) - set(POR_CLAVE)
    if desconocidas:
        raise KeyError(f"Campos que no existen en el layout: {sorted(desconocidas)}")
    return "|".join(str(valores.get(c.clave, "")) for c in CAMPOS)


def validar_linea(texto: str, renglon: int = 1) -> list[str]:
    """Errores de un renglón contra el instructivo (vacío = válido)."""
    errores: list[str] = []
    partes = texto.split("|")
    if len(partes) != len(CAMPOS):
        return [f"Renglón {renglon}: se esperan {len(CAMPOS)} campos y hay {len(partes)}."]
    v = {c.clave: p for c, p in zip(CAMPOS, partes, strict=True)}

    def error(campo: str, msg: str) -> None:
        errores.append(f"Renglón {renglon}, campo {POR_CLAVE[campo].numero} "
                       f"({POR_CLAVE[campo].descripcion}): {msg}")

    tipo, op = v["tipo_tercero"], v["tipo_operacion"]
    if tipo not in TIPOS_TERCERO:
        error("tipo_tercero", f"{tipo!r} no es 04, 05 ni 15.")
    elif op not in OPERACIONES_POR_TERCERO[tipo]:
        error("tipo_operacion", f"{op!r} no se permite con el tipo de tercero {tipo}.")
    extranjero = tipo == "05"
    if tipo in ("04", "15") and not _RE_RFC.match(v["rfc"]):
        error("rfc", "RFC obligatorio y válido para proveedor nacional o global.")
    if tipo == "15" and v["rfc"] != RFC_GLOBAL:
        error("rfc", f"El proveedor global se declara con {RFC_GLOBAL}.")
    if v["rfc"] and v["rfc"] != v["rfc"].upper():
        error("rfc", "El RFC va en mayúsculas.")
    for campo in ("id_fiscal", "nombre_extranjero", "pais"):
        if extranjero and not v[campo]:
            error(campo, "obligatorio para proveedor extranjero.")
        if not extranjero and v[campo]:
            error(campo, "va vacío si el proveedor no es extranjero.")
    if v["pais"] and not re.fullmatch(r"[A-Z]{2,3}", v["pais"]):
        error("pais", "clave del catálogo de países.")
    if (v["pais"] == "ZZZ") != bool(v["jurisdiccion"]):
        error("jurisdiccion", "sólo y obligatorio cuando el país es ZZZ (Otro).")
    for c in CAMPOS:
        valor = v[c.clave]
        if len(valor) > c.maximo:
            error(c.clave, f"pasa de {c.maximo} caracteres.")
        if c.tipo == "importe" and valor and not _RE_IMPORTE.match(valor):
            error(c.clave, "importe entero sin decimales ni signos.")
        tope = v[CAMPOS[c.devolucion_de - 1].clave] if c.devolucion_de else ""
        if (valor and tope and _RE_IMPORTE.match(valor) and _RE_IMPORTE.match(tope)
                and int(valor) > int(tope)):
            error(c.clave, f"no puede ser mayor que el campo {c.devolucion_de}.")
    if v["efectos_fiscales"] not in ("01", "02"):
        error("efectos_fiscales", "obligatorio: 01 (Sí) o 02 (No).")
    return errores


def validar_archivo(contenido: bytes) -> list[str]:
    """Errores del archivo completo: UTF-8, un proveedor por renglón, 54 campos cada uno."""
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        return ["El archivo no está en UTF-8."]
    renglones = [r for r in texto.replace("\r\n", "\n").split("\n") if r]
    if not renglones:
        return ["El archivo no tiene renglones."]
    errores: list[str] = []
    vistos: set[tuple[str, str, str]] = set()
    for i, r in enumerate(renglones, start=1):
        errores += validar_linea(r, i)
        partes = r.split("|")
        llave = (partes[0], partes[1], partes[2] or (partes[3] if len(partes) > 3 else ""))
        if llave in vistos:
            errores.append(f"Renglón {i}: proveedor y tipo de operación repetidos.")
        vistos.add(llave)
    return errores
