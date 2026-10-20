"""
Registros de posiciones fijas para los layouts bancarios (P4-12).

Llevado del front (`apps/store/src/services/exportadores/registroFijo.ts`, O-04) con la
misma disciplina:

- **Truncar está prohibido** salvo en los campos marcados `recortable` (nombres y leyendas):
  un nombre largo no cambia a quién se le paga —eso lo decide la cuenta— y los bancos lo
  truncan de todas formas. Una cuenta o un importe que no caben LEVANTAN.
- **Las anchuras se verifican, no se confían**: `escribir` comprueba que la línea mida lo
  que dice el layout; `leer` recorta los mismos campos para el cuadre de vuelta.
- **ASCII**: se transliteran acentos (`MUÑOZ` → `MUNOZ`) salvo que el layout pida otra
  sustitución (Banamex: Ñ → @).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.exceptions import FiscalAgentError


@dataclass(frozen=True)
class Campo:
    """Un campo de un registro: `N` numérico (ceros a la izquierda) o `A` alfanumérico."""

    nombre: str
    ancho: int
    tipo: str = "A"
    recortable: bool = False


def ascii_mayusculas(texto: str, *, enie: str | None = None) -> str:
    """Mayúsculas sin acentos. `enie` reemplaza la Ñ antes de transliterar (Banamex usa @)."""
    t = (texto or "").upper()
    if enie is not None:
        t = t.replace("Ñ", enie)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    return " ".join(t.split())


def _rellenar(campo: Campo, valor: str, layout: str) -> str:
    if campo.tipo == "N":
        if valor and not valor.isdigit():
            raise FiscalAgentError(
                f"El campo numérico '{campo.nombre}' del layout {layout} recibió {valor!r}.", 500
            )
        if len(valor) > campo.ancho:
            raise FiscalAgentError(
                f"{valor!r} no cabe en '{campo.nombre}' ({campo.ancho} posiciones) del layout "
                f"{layout}. Recortarlo cambiaría a quién o cuánto se le paga.",
                422,
            )
        return valor.rjust(campo.ancho, "0")
    if len(valor) > campo.ancho:
        if campo.recortable:
            return valor[: campo.ancho]
        raise FiscalAgentError(
            f"{valor!r} no cabe en '{campo.nombre}' ({campo.ancho} posiciones) del layout "
            f"{layout}.",
            422,
        )
    return valor.ljust(campo.ancho, " ")


def largo(campos: tuple[Campo, ...]) -> int:
    return sum(c.ancho for c in campos)


def escribir(campos: tuple[Campo, ...], valores: dict[str, str], layout: str) -> str:
    """Arma la línea; un campo ausente se rellena entero (ceros o espacios)."""
    desconocidos = set(valores) - {c.nombre for c in campos}
    if desconocidos:  # un nombre mal tecleado se perdería en silencio
        raise FiscalAgentError(f"Campos que no existen en {layout}: {sorted(desconocidos)}", 500)
    linea = "".join(_rellenar(c, valores.get(c.nombre, ""), layout) for c in campos)
    if len(linea) != largo(campos):  # inalcanzable, y aun así se comprueba
        raise FiscalAgentError(f"El registro de {layout} mide {len(linea)}.", 500)
    return linea


def leer(campos: tuple[Campo, ...], linea: str) -> dict[str, str]:
    """El camino de vuelta: corta la línea en sus campos (para el cuadre)."""
    salida, pos = {}, 0
    for c in campos:
        salida[c.nombre] = linea[pos : pos + c.ancho]
        pos += c.ancho
    return salida


def centavos(importe_centavos: int) -> str:
    """Importe sin punto decimal: los dos últimos dígitos son los centavos."""
    if importe_centavos < 0:
        raise FiscalAgentError("Un importe de dispersión no puede ser negativo.", 500)
    return str(importe_centavos)
