"""
Configuración de impuestos del cliente (DP-3) y lectura tolerante de importes. Salió de
`impuestos/servicio.py` en P6-05 (tope de 300 líneas) sin cambiar nada; ese módulo la
reexporta.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.modelos.impuestos import ConfigImpuestosCliente
from app.modelos.nucleo import Cliente
from app.schemas.impuestos import ConfigImpuestosSchema


def config_de(db: Session, cliente: Cliente) -> ConfigImpuestosSchema:
    """Criterio guardado del cliente o los defaults documentados."""
    fila = db.get(ConfigImpuestosCliente, cliente.id)
    return ConfigImpuestosSchema.model_validate(fila.datos if fila else {})


def guardar_config(db: Session, cliente: Cliente, cfg: ConfigImpuestosSchema) -> None:
    """Guarda el criterio del cliente (reemplaza el anterior)."""
    fila = db.get(ConfigImpuestosCliente, cliente.id)
    datos = cfg.model_dump(mode="json")
    if fila is None:
        db.add(ConfigImpuestosCliente(cliente_id=cliente.id, datos=datos))
    else:
        fila.datos = datos
    db.flush()


def regimen_de(cliente: Cliente) -> str:
    return str((cliente.datos or {}).get("regimen") or "")


def entidad_de(cliente: Cliente) -> str:
    return str((cliente.datos or {}).get("clave_entidad") or "")


def _dec(v: object) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except Exception:  # noqa: BLE001 - importe ilegible en un XML ajeno: cuenta como cero
        return Decimal("0")
