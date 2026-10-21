"""
Layouts de posiciones fijas del IMSS: movimientos afiliatorios (IDSE/DISPMAG) y SUA (P4-09).

No calcula nada: escribe registros con datos ya resueltos. Es el puerto al backend de
`apps/store/src/services/exportadores/layoutImss.ts` + `registroFijo.ts` (O-04), con los tres
movimientos y el SUA.

FUENTES
-------
**Movimientos afiliatorios (IDSE).** Transcritos en O-04 del documento oficial, campo por campo:

- *Estructura de Movimientos afiliatorios*, IMSS —
  https://www.imss.gob.mx/sites/all/statics/sua/dispmag/EstructuraMovimientosAfiliatorios.pdf
- *Guía de operación DISP-MAG*, IMSS —
  http://www.imss.gob.mx/sites/all/statics/pdf/formatos/GuiaOperacionDISP-MAG_2009.pdf
  ("Longitud de los registros 168 fija", "Código de grabación ASCII", salario en 6
  posiciones: 4 para pesos con ceros a la izquierda y 2 para centavos).

No se volvieron a descargar en P4-09 (sin red hacia imss.gob.mx desde este entorno): las
posiciones son las de O-04, que ya pasaron revisión y tienen test de cobertura 1..168.

**Catálogo de causas de baja (posición 149).** 1 Término de contrato, 2 Separación voluntaria,
3 Abandono de empleo, 4 Defunción, 5 Clausura, 6 Otras, 7 Ausentismo, 8 Rescisión de contrato,
9 Jubilación, A Pensión. # POR CONFIRMAR contra la Guía DISP-MAG vigente (en particular la
clave alfabética "A"; por eso el campo se trata como alfanumérico).

**SUA (importación de trabajadores y de movimientos).** # POR CONFIRMAR: el IMSS publica los
layouts de importación dentro del manual del SUA, que no se pudo descargar desde este entorno y
del que no se encontró copia pública verificable; las fuentes secundarias consultadas no traen
posiciones. Se transcriben de la estructura de importación del SUA 3.x tal como la usan los
sistemas de nómina comerciales (registro patronal 11, NSS 11, RFC 13, CURP 18, nombre 50 con
`$` entre apellidos y nombre, tipo de trabajador, jornada, fecha DDMMAAAA, SDI de 7 con 2
decimales implícitos...). Las longitudes son datos de esta tabla, NO lógica: si el manual
difiere, se corrige aquí y el test de cobertura lo vuelve a medir.

TRUNCAR ESTÁ PROHIBIDO
----------------------
Un valor que no cabe **levanta**: cortar un apellido o un NSS produce un movimiento sobre otra
persona, o sobre nadie, y el archivo seguiría midiendo lo mismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.exceptions import FiscalValidationError

LARGO_IDSE = 168
IDENTIFICADOR_FORMATO = "9"
TIPO_ALTA_REINGRESO = "08"
TIPO_MODIFICACION = "07"
TIPO_BAJA = "02"

CAUSAS_BAJA = {
    "1": "Término de contrato",
    "2": "Separación voluntaria",
    "3": "Abandono de empleo",
    "4": "Defunción",
    "5": "Clausura",
    "6": "Otras",
    "7": "Ausentismo",
    "8": "Rescisión de contrato",
    "9": "Jubilación",
    "A": "Pensión",
}

_EQUIVALENCIAS = str.maketrans(
    "ÁÉÍÓÚÜáéíóúüÑñÀÈÌÒÙÂÊÎÔÛÇç", "AEIOUUaeiouuNnAEIOUAEIOUCc"
)


@dataclass(frozen=True)
class Campo:
    """Un campo del layout. Posiciones 1-indexadas e inclusivas, como el documento."""

    nombre: str
    tipo: str  # AN | A | N
    desde: int
    hasta: int
    relleno: str = " "

    @property
    def ancho(self) -> int:
        return self.hasta - self.desde + 1

    @property
    def a_la_derecha(self) -> bool:
        return self.tipo == "N"


def _c(nombre: str, tipo: str, desde: int, hasta: int, relleno: str = " ") -> Campo:
    return Campo(nombre, tipo, desde, hasta, relleno)


# ── IDSE / DISPMAG (168 posiciones) ──

_CABEZA = (
    _c("registro_patronal", "AN", 1, 10),
    _c("digito_rp", "N", 11, 11, "0"),
    _c("nss", "N", 12, 21, "0"),
    _c("digito_nss", "N", 22, 22, "0"),
    _c("apellido_paterno", "A", 23, 49),
    _c("apellido_materno", "A", 50, 76),
    _c("nombres", "A", 77, 103),
)

ALTA: tuple[Campo, ...] = (
    *_CABEZA,
    _c("sbc", "N", 104, 109, "0"),
    _c("filler_110", "A", 110, 115),
    _c("tipo_trabajador", "N", 116, 116, "0"),
    _c("tipo_salario", "N", 117, 117, "0"),
    _c("jornada", "N", 118, 118, "0"),
    _c("fecha_movimiento", "N", 119, 126, "0"),
    _c("umf", "N", 127, 129, "0"),
    _c("filler_130", "AN", 130, 131),
    _c("tipo_movimiento", "N", 132, 133, "0"),
    _c("guia", "N", 134, 138, "0"),
    _c("clave_trabajador", "AN", 139, 148),
    _c("filler_149", "AN", 149, 149),
    _c("curp", "AN", 150, 167),
    _c("identificador", "N", 168, 168, "0"),
)

# Modificación (07): la 116 es filler y no hay UMF (127-131 en blanco).
MODIFICACION: tuple[Campo, ...] = (
    *_CABEZA,
    _c("sbc", "N", 104, 109, "0"),
    _c("filler_110", "A", 110, 115),
    _c("filler_116", "N", 116, 116),
    _c("tipo_salario", "N", 117, 117, "0"),
    _c("jornada", "N", 118, 118, "0"),
    _c("fecha_movimiento", "N", 119, 126, "0"),
    _c("filler_127", "AN", 127, 131),
    _c("tipo_movimiento", "N", 132, 133, "0"),
    _c("guia", "N", 134, 138, "0"),
    _c("clave_trabajador", "AN", 139, 148),
    _c("filler_149", "AN", 149, 149),
    _c("curp", "AN", 150, 167),
    _c("identificador", "N", 168, 168, "0"),
)

# Baja (02): 104-118 en CEROS, causa en la 149 y 150-167 en blanco (sin CURP).
BAJA: tuple[Campo, ...] = (
    *_CABEZA,
    _c("filler_104", "AN", 104, 118, "0"),
    _c("fecha_movimiento", "N", 119, 126, "0"),
    _c("filler_127", "AN", 127, 131),
    _c("tipo_movimiento", "N", 132, 133, "0"),
    _c("guia", "N", 134, 138, "0"),
    _c("clave_trabajador", "AN", 139, 148),
    _c("causa_baja", "AN", 149, 149),
    _c("filler_150", "AN", 150, 167),
    _c("identificador", "N", 168, 168, "0"),
)

CIFRAS_CONTROL: tuple[Campo, ...] = (
    _c("asteriscos", "AN", 1, 13),
    _c("filler_14", "AN", 14, 56),
    _c("total_registros", "N", 57, 62, "0"),
    _c("filler_63", "AN", 63, 133),
    _c("guia", "N", 134, 138, "0"),
    _c("filler_139", "AN", 139, 167),
    _c("identificador", "N", 168, 168, "0"),
)

LAYOUT_IDSE = {TIPO_ALTA_REINGRESO: ALTA, TIPO_MODIFICACION: MODIFICACION, TIPO_BAJA: BAJA}

# ── SUA (POR CONFIRMAR, ver docstring) ──

LARGO_SUA_TRABAJADOR = 164
LARGO_SUA_MOVIMIENTO = 49

SUA_TRABAJADOR: tuple[Campo, ...] = (
    _c("registro_patronal", "AN", 1, 11),
    _c("nss", "N", 12, 22, "0"),
    _c("rfc", "AN", 23, 35),
    _c("curp", "AN", 36, 53),
    _c("nombre", "A", 54, 103),
    _c("tipo_trabajador", "N", 104, 104, "0"),
    _c("jornada", "N", 105, 105, "0"),
    _c("fecha_alta", "N", 106, 113, "0"),
    _c("sdi", "N", 114, 120, "0"),
    _c("clave_ubicacion", "AN", 121, 137),
    _c("credito_infonavit", "AN", 138, 147),
    _c("fecha_inicio_descuento", "N", 148, 155, "0"),
    _c("tipo_descuento", "N", 156, 156, "0"),
    _c("valor_descuento", "N", 157, 164, "0"),
)

SUA_MOVIMIENTO: tuple[Campo, ...] = (
    _c("registro_patronal", "AN", 1, 11),
    _c("nss", "N", 12, 22, "0"),
    _c("tipo_movimiento", "N", 23, 24, "0"),
    _c("fecha_movimiento", "N", 25, 32, "0"),
    _c("folio_incapacidad", "AN", 33, 40),
    _c("dias_incidencia", "N", 41, 42, "0"),
    _c("sdi", "N", 43, 49, "0"),
)


# ── escritura ──


def a_ascii(texto: str) -> tuple[str, bool]:
    """Translitera acentos y Ñ; descarta lo que no tenga equivalente. (texto, cambió)."""
    salida = []
    cambio = False
    for ch in texto.translate(_EQUIVALENCIAS):
        if 32 <= ord(ch) <= 126:
            salida.append(ch)
        else:
            cambio = True
    resultado = "".join(salida)
    return resultado, cambio or resultado != texto


def verificar_layout(campos: tuple[Campo, ...], largo: int) -> None:
    """Los campos cubren 1..largo sin huecos ni traslapes. Se corre en cada escritura."""
    esperado = 1
    for c in campos:
        if c.desde != esperado:
            tipo = "hueco" if c.desde > esperado else "traslape"
            raise FiscalValidationError(
                f"El layout tiene un {tipo} antes de {c.nombre!r}: se esperaba la posición "
                f"{esperado} y empieza en {c.desde}."
            )
        if c.hasta < c.desde:
            raise FiscalValidationError(f"El campo {c.nombre!r} termina antes de empezar.")
        esperado = c.hasta + 1
    if esperado - 1 != largo:
        raise FiscalValidationError(
            f"El layout cubre {esperado - 1} posiciones y el registro son {largo}."
        )


def _rellenar(campo: Campo, valor: str) -> str:
    if len(valor) > campo.ancho:
        raise FiscalValidationError(
            f"{valor!r} no cabe en el campo {campo.nombre!r} ({campo.ancho} posiciones). "
            "Truncarlo produciría un movimiento sobre otra persona: corrige el dato."
        )
    if campo.tipo == "N" and valor and not valor.isdigit():
        raise FiscalValidationError(f"El campo numérico {campo.nombre!r} recibió {valor!r}.")
    if campo.a_la_derecha:
        return valor.rjust(campo.ancho, campo.relleno)
    return valor.ljust(campo.ancho, campo.relleno)


def escribir_registro(
    campos: tuple[Campo, ...], valores: dict[str, str], largo: int
) -> tuple[str, list[str]]:
    """La línea de `largo` posiciones y los campos que se transliteraron."""
    verificar_layout(campos, largo)
    linea, cambiados = [], []
    for campo in campos:
        crudo = valores.get(campo.nombre, "") or ""
        texto, cambio = a_ascii(crudo) if crudo else ("", False)
        if cambio:
            cambiados.append(campo.nombre)
        linea.append(_rellenar(campo, texto))
    resultado = "".join(linea)
    if len(resultado) != largo:
        raise FiscalValidationError(f"El registro mide {len(resultado)} y debería medir {largo}.")
    return resultado, cambiados


def fecha_ddmmaaaa(fecha: date) -> str:
    """Fecha `DDMMAAAA`, sin separadores."""
    return fecha.strftime("%d%m%Y")


def importe_implicito(importe: Decimal, enteros: int) -> str:
    """
    Importe con 2 decimales implícitos: `enteros` posiciones de pesos + 2 de centavos.

    IDSE: 4 + 2 (`$526.05` → `052605`). SUA: 5 + 2. Si no cabe, LEVANTA.
    """
    if importe < 0:
        raise FiscalValidationError(f"El salario no puede ser negativo: {importe}.")
    centavos = int((importe * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    ancho = enteros + 2
    if centavos >= 10**ancho:
        raise FiscalValidationError(
            f"El salario {importe} no cabe en {ancho} posiciones. Truncarlo declararía un "
            "salario distinto al real."
        )
    return str(centavos).rjust(ancho, "0")


def partir_registro_patronal(rp: str) -> tuple[str, str]:
    """11 caracteres: 10 del registro y su dígito verificador (no se calcula, se captura)."""
    limpio = (rp or "").strip().upper()
    if len(limpio) != 11:
        raise FiscalValidationError(
            f"El registro patronal son 11 caracteres (10 + dígito verificador) y hay "
            f"{len(limpio)}. Captúralo en la ficha del cliente."
        )
    return limpio[:10], limpio[10:]
