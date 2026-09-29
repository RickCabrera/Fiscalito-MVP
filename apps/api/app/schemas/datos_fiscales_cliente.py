"""
Reglas de los datos fiscales del cliente del despacho: RFC y entidad. (C-01)

Viven aparte de `schemas/cartera.py`, que ya pasaba del tope de 300 líneas. Son
las MISMAS reglas que `apps/store/src/components/cartera/datosFiscalesCliente.ts`
aplica en el formulario: si una cambia, cambian las dos, y los tests de los dos
lados llevan el mismo vector.
"""

from __future__ import annotations

RFC_O_VACIO = r"^(?:[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})?$"
"""El `_RFC_PATTERN` de `schemas/fiscal.py`, admitiendo vacío = no capturado."""

LONGITUDES_RFC_POR_REGIMEN: dict[str, tuple[int, ...]] = {
    "601": (12,),
    "612": (13,),
    # DECISIÓN PROVISIONAL (nocturno): el backlog de C-01 dice "626 = 13", pero
    # RESICO también lo tributan personas morales (Arts. 206-215 LISR). Exigir 13
    # dejaría fuera a un RESICO moral legítimo. docs/decisiones-nomina.md §D31.
    "626": (12, 13),
}
"""Mismas reglas que `components/cartera/datosFiscalesCliente.ts` en el front."""

ENTIDADES_C_ESTADO: frozenset[str] = frozenset(
    {
        "AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "CMX", "DIF", "COA", "COL", "DUR",
        "GUA", "GRO", "HID", "JAL", "MEX", "MIC", "MOR", "NAY", "NLE", "OAX", "PUE",
        "QUE", "ROO", "SLP", "SIN", "SON", "TAB", "TAM", "TLA", "VER", "YUC", "ZAC",
    }
)
"""
Claves de México del catálogo `c_Estado` del SAT (Anexo 20, catálogos del CFDI).

Fuente: `tests/xsd/catCFDI.xsd`, simpleType `c_Estado`, versionado offline (su
sha256 lo fija `tests/nomina/test_xsd_versionados.py`). Un test compara este
conjunto contra ese archivo. La Ciudad de México tiene dos claves vigentes en el
catálogo, `CMX` y la anterior `DIF`, y se aceptan las dos.
"""
