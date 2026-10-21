"""
ISN del cliente desde la bóveda (P3-07). Salió de `servicio.py` por el tope de 300 líneas
(P6-07); sólo se movió el código. Arma la entrada de `fiscal_engine/isn.py` con los CFDI de
nómina del cliente y su entidad.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.boveda_cfdi.parser import NS_NOMINA12, leer_xml
from app.boveda_cfdi.servicio import leer_xml_original
from app.exceptions import FiscalAgentError
from app.fiscal_engine import isn as motor_isn
from app.impuestos.flujo import nominas_del_mes
from app.impuestos.servicio import _dec, config_de, entidad_de
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente


def percepciones_de_nomina(comp: Comprobante) -> list[motor_isn.PercepcionISN]:
    """Percepciones por clave de un CFDI de nómina (del XML original; si falla, totales)."""
    try:
        raiz = leer_xml(leer_xml_original(comp))
        salida = [
            motor_isn.PercepcionISN(
                p.get("TipoPercepcion", "038"),
                _dec(p.get("ImporteGravado")) + _dec(p.get("ImporteExento")),
                p.get("Concepto", ""),
            )
            for p in raiz.iter(f"{{{NS_NOMINA12}}}Percepcion")
        ]
        otros = sum((_dec(o.get("Importe")) for o in raiz.iter(f"{{{NS_NOMINA12}}}OtroPago")),
                    Decimal("0"))
        if otros:
            salida.append(motor_isn.PercepcionISN("OTP", otros, "Otros pagos (no percepción)"))
        return salida
    except (FiscalAgentError, ValueError):
        tot = (comp.datos or {}).get("nomina", {}).get("percepciones", {})
        total = _dec(tot.get("TotalGravado")) + _dec(tot.get("TotalExento"))
        return [motor_isn.PercepcionISN("038", total, "Total de percepciones (sin desglose)")]


def isn_del_cliente(
    db: Session, cliente: Cliente, anio: int, mes: int, aplicar_adicional: bool | None = None,
    claves_excluidas: list[str] | None = None,
) -> tuple[motor_isn.ResultadoISN, int]:
    """ISN del mes con los CFDI de nómina del cliente y su entidad (`clave_entidad`)."""
    entidad = entidad_de(cliente)
    if not entidad:
        raise FiscalAgentError(
            "El cliente no tiene entidad federativa (clave_entidad) en su ficha; captúrala "
            "para calcular su ISN.", 422)
    cfg = config_de(db, cliente)
    nominas = nominas_del_mes(db, cliente, anio, mes)
    percepciones = [
        p for n in nominas for p in percepciones_de_nomina(n) if p.clave != "OTP"
    ]
    conf = motor_isn.ConfigISN(
        aplicar_adicional=cfg.isn_aplicar_adicional if aplicar_adicional is None
        else aplicar_adicional,
        claves_excluidas_extra=frozenset(cfg.isn_claves_excluidas + (claves_excluidas or [])),
        claves_incluidas_forzadas=frozenset(cfg.isn_claves_incluidas),
    )
    return motor_isn.calcular_isn(entidad, date(anio, mes, 1), percepciones, conf), len(nominas)
