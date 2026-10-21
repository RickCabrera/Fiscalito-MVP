"""
DIOT del mes desde la bóveda, con cortes por tasa REALES y el layout 2025 (P3-05).

DE DÓNDE SALE CADA IMPORTE
--------------------------
La DIOT reporta actos **pagados** (Art. 32 fr. VIII LIVA): se usan los CFDI RECIBIDOS que
cuentan en el mes por flujo de efectivo (`app/impuestos/flujo.py`: PUE en su mes, PPD en el
mes de cada complemento de pago, en proporción a lo pagado) y cada uno se parte por tasa con
el MISMO desglose que usa el IVA mensual (`impuestos.servicio.movimiento_iva`: los
`Traslado` de IVA de cada CFDI por `TasaOCuota`/`TipoFactor`). Nada se supone al 16 %, salvo
un CFDI sin nodo de traslados que sí trae IVA (se avisa).

- 16 % → valor y IVA de "tasa 16 %" (campos 12 y 22/23); de un proveedor extranjero, de
  "importación" (14/24 tangibles o 16/26 intangibles, según su configuración).
- 8 % → región fronteriza norte (8/18) o sur (10/20), según el proveedor (default norte).
- 0 % → campo 51; exento → 50 (49 si es importación); no objeto → 52.
- IVA retenido al proveedor → 48.
- Notas de crédito recibidas (tipo E) → "devoluciones, descuentos y bonificaciones" de su
  tasa (9, 11, 13, 15, 17) y su IVA se resta del acreditable.
- IVA no acreditable: lo marca el despacho por proveedor (proporción, requisitos, exentas, no
  objeto); además, el IVA de un CFDI con uso de deducción personal o "sin efectos fiscales"
  (`USOS_NO_ACREDITABLES`, el mismo criterio del IVA mensual) va a "no cumple requisitos".

TIPO DE TERCERO Y DE OPERACIÓN (deducidos, editables por proveedor)
-------------------------------------------------------------------
- Tercero: RFC genérico XAXX010101000 → 15 global (operación 87); XEXX010101000 → 05
  extranjero; cualquier otro → 04 nacional.
- Operación (nacional): régimen del emisor 606 o ClaveProdServ 8013xxxx (arrendamiento de
  inmuebles) → 06; persona física con ISR retenido (honorarios) → 03; todos los conceptos
  con ClaveProdServ de bienes (divisiones < 70) → 02; lo demás → 85 Otros.
  Extranjero: 07 importación. DECISIÓN PROVISIONAL: la heurística no sustituye la revisión
  del despacho; la pantalla deja cambiarla y la guarda por proveedor.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.diot import layout
from app.impuestos.flujo import Efectivo, flujo_del_mes
from app.impuestos.servicio import movimiento_iva
from app.modelos.diot import ConfigProveedorDiot
from app.modelos.nucleo import Cliente
from app.schemas.diot_layout import ConfigProveedorDiotSchema

CERO = Decimal("0")


def _entero(v: Decimal) -> int:
    return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def configs(db: Session, cliente: Cliente) -> dict[str, ConfigProveedorDiotSchema]:
    filas = db.scalars(select(ConfigProveedorDiot).where(
        ConfigProveedorDiot.cliente_id == cliente.id))
    return {f.rfc: ConfigProveedorDiotSchema.model_validate(f.datos) for f in filas}


def guardar_config(db: Session, cliente: Cliente, rfc: str,
                   cfg: ConfigProveedorDiotSchema) -> None:
    rfc = rfc.upper()
    fila = db.scalar(select(ConfigProveedorDiot).where(
        ConfigProveedorDiot.cliente_id == cliente.id, ConfigProveedorDiot.rfc == rfc))
    datos = cfg.model_dump(mode="json")
    if fila is None:
        db.add(ConfigProveedorDiot(cliente_id=cliente.id, rfc=rfc, datos=datos))
    else:
        fila.datos = datos
    db.flush()


def deducir_tercero(rfc: str) -> str:
    if rfc == layout.RFC_GLOBAL:
        return "15"
    if rfc == layout.RFC_EXTRANJERO:
        return "05"
    return "04"


def deducir_operacion(tipo_tercero: str, efectivos: list[Efectivo]) -> str:
    if tipo_tercero == "15":
        return "87"
    if tipo_tercero == "05":
        return "07"
    claves: list[str] = []
    for e in efectivos:
        c = e.comprobante
        datos = c.datos or {}
        if str(datos.get("emisor", {}).get("RegimenFiscal", "")) == "606":
            return "06"
        claves += [str(x.get("ClaveProdServ", "")) for x in datos.get("conceptos", [])]
    if any(k.startswith("8013") for k in claves):
        return "06"
    if any(len(e.comprobante.rfc_emisor) == 13 and e.comprobante.isr_retenido > 0
           for e in efectivos):
        return "03"
    if claves and all(k[:2].isdigit() and int(k[:2]) < 70 for k in claves):
        return "02"
    return "85"


@dataclass
class ProveedorDiot:
    rfc: str
    nombre: str
    tipo_tercero: str
    tipo_operacion: str
    capturado: bool
    config: ConfigProveedorDiotSchema
    importes: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: CERO))
    uuids: set[str] = field(default_factory=set)
    advertencias: list[str] = field(default_factory=list)

    def campos(self) -> dict[str, int]:
        """Importes al peso, sin ceros (los vacíos se aceptan)."""
        return {k: _entero(v) for k, v in sorted(self.importes.items()) if _entero(v) > 0}

    def valores(self) -> dict[str, str | int]:
        cfg = self.config
        extranjero = self.tipo_tercero == "05"
        base: dict[str, str | int] = {
            "tipo_tercero": self.tipo_tercero, "tipo_operacion": self.tipo_operacion,
            "rfc": "" if extranjero and self.rfc == layout.RFC_EXTRANJERO else self.rfc,
            "efectos_fiscales": cfg.efectos_fiscales,
        }
        if extranjero:
            base.update({"id_fiscal": cfg.id_fiscal, "nombre_extranjero":
                         cfg.nombre_extranjero or self.nombre, "pais": cfg.pais,
                         "jurisdiccion": cfg.jurisdiccion if cfg.pais == "ZZZ" else ""})
        base.update(self.campos())
        return base

    def linea(self) -> str:
        return layout.linea(self.valores())


def _seccion_16(p: ProveedorDiot) -> str:
    if p.tipo_tercero == "05":
        return f"importacion_{p.config.importacion}"
    return "tasa_16"


def _destino_iva(p: ProveedorDiot, seccion: str, deducible: bool) -> str:
    cfg = p.config
    if cfg.iva_no_acreditable:
        return f"no_acreditable_{cfg.iva_no_acreditable}_{seccion}"
    if not deducible:
        return f"no_acreditable_requisitos_{seccion}"
    return f"acreditable_{cfg.asignacion_iva}_{seccion}"


def _acumular(p: ProveedorDiot, e: Efectivo) -> None:
    m = movimiento_iva(e)
    imp = p.importes
    for base, iva, seccion in ((m.base_16, m.iva_16, _seccion_16(p)),
                               (m.base_8, m.iva_8, f"region_{p.config.region_8}")):
        if not base and not iva:
            continue
        clave = "valor" if m.signo > 0 else "devoluciones"
        imp[f"{clave}_{seccion}"] += base
        imp[_destino_iva(p, seccion, m.deducible)] += iva * m.signo
    imp["importacion_exentos" if p.tipo_tercero == "05" else "exentos"] += m.base_exento * m.signo
    imp["tasa_0"] += m.base_0 * m.signo
    imp["no_objeto_sin_establecimiento" if p.tipo_tercero == "05"
        else "no_objeto_nacional"] += m.base_no_objeto * m.signo
    imp["iva_retenido"] += m.iva_retenido * m.signo
    if (not (e.comprobante.datos or {}).get("impuestos", {}).get("traslados")
            and e.comprobante.iva_trasladado):
        p.advertencias.append(f"El CFDI {e.comprobante.uuid} trae IVA sin desglose por tasa: "
                              "se reportó al 16 %.")
    p.uuids.add(e.comprobante.uuid)


@dataclass
class ResultadoDiot:
    anio: int
    mes: int
    proveedores: list[ProveedorDiot]
    advertencias: list[str]

    def archivo(self) -> bytes:
        return ("\n".join(p.linea() for p in self.proveedores) + "\n").encode("utf-8")

    def errores(self) -> list[str]:
        return layout.validar_archivo(self.archivo()) if self.proveedores else []

    def a_dict(self) -> dict[str, Any]:
        return {
            "anio": self.anio, "mes": self.mes, "total_proveedores": len(self.proveedores),
            "proveedores": [{
                "rfc": p.rfc, "nombre": p.nombre, "tipo_tercero": p.tipo_tercero,
                "tipo_operacion": p.tipo_operacion, "clasificacion_capturada": p.capturado,
                "config": p.config.model_dump(mode="json"), "campos": p.campos(),
                "cantidad_cfdi": len(p.uuids), "advertencias": p.advertencias,
                "linea": p.linea(),
            } for p in self.proveedores],
            "advertencias": self.advertencias,
            "errores_layout": self.errores(),
            "layout": "DIOT carga masiva 2025 (54 campos, separador |, UTF-8)",
        }


def diot_del_mes(db: Session, cliente: Cliente, anio: int, mes: int) -> ResultadoDiot:
    """La DIOT del mes por proveedor, lista para el archivo de carga masiva."""
    cfgs = configs(db, cliente)
    por_rfc: dict[str, list[Efectivo]] = defaultdict(list)
    for e in flujo_del_mes(db, cliente, anio, mes):
        if e.comprobante.direccion == "recibido":
            por_rfc[e.comprobante.rfc_emisor.upper()].append(e)
    proveedores: list[ProveedorDiot] = []
    advertencias: list[str] = []
    for rfc, efectivos in sorted(por_rfc.items()):
        cfg = cfgs.get(rfc, ConfigProveedorDiotSchema())
        tipo = cfg.tipo_tercero or deducir_tercero(rfc)
        op = cfg.tipo_operacion or deducir_operacion(tipo, efectivos)
        nombre = max(efectivos, key=lambda e: e.comprobante.fecha).comprobante.nombre_emisor
        p = ProveedorDiot(rfc, nombre, tipo, op, rfc in cfgs, cfg)
        for e in efectivos:
            _acumular(p, e)
        negativos = [k for k, v in p.importes.items() if v < 0]
        if negativos:
            advertencias.append(f"{rfc}: las notas de crédito superan lo pagado en "
                                f"{', '.join(negativos)}; se reporta cero.")
        proveedores.append(p)
    return ResultadoDiot(anio, mes, proveedores, advertencias)
