"""El catálogo de layouts de dispersión (P4-12). Un banco nuevo = un renglón aquí."""

from __future__ import annotations

from app.dispersion.bancos.banamex import Banamex
from app.dispersion.bancos.banbajio import BanBajio
from app.dispersion.bancos.banorte import Banorte
from app.dispersion.bancos.bbva import BBVA
from app.dispersion.bancos.generico import Generico
from app.dispersion.bancos.hsbc import HSBC
from app.dispersion.bancos.santander import Santander
from app.dispersion.bancos.scotiabank import Scotiabank
from app.dispersion.tipos import Layout
from app.exceptions import FiscalAgentError

LAYOUTS: dict[str, type[Layout]] = {
    c.id: c for c in (BBVA, Banamex, Santander, Banorte, HSBC, Scotiabank, BanBajio, Generico)
}


def layout_por_id(layout_id: str, **config: object) -> Layout:
    """Una instancia del layout. Sólo el genérico recibe configuración (columnas, formato)."""
    clase = LAYOUTS.get(layout_id)
    if clase is None:
        raise FiscalAgentError(
            f"No hay layout '{layout_id}'. Disponibles: {', '.join(LAYOUTS)}.", 422
        )
    return clase(**config) if clase is Generico else clase()  # type: ignore[arg-type]


def descripcion(clase: type[Layout]) -> dict[str, object]:
    """Lo que la pantalla necesita para pintar el selector."""
    return {
        "id": clase.id,
        "nombre": clase.nombre,
        "banco": clase.banco,
        "estado": clase.estado,
        "fuente": clase.fuente,
        "interbancario": clase.interbancario,
        "datos_requeridos": [
            {"clave": d.clave, "etiqueta": d.etiqueta, "patron": d.patron,
             "obligatorio": d.obligatorio, "default": d.default}
            for d in clase.datos_requeridos
        ],
    }
