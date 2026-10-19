"""
Configuración de pólizas automáticas por cliente (P2-02), al estilo de la pantalla
"Configuración de pólizas automáticas" de Contadigital: reglas de automatización, cuentas
contables por rol, opciones especiales y concepto de las pólizas.

CUENTAS POR ROL
---------------
`ROLES` dice qué cuenta usa el generador para cada papel (clientes, IVA trasladado cobrado,
ISR retenido por honorarios…). El default apunta al catálogo base (`catalogo.CATALOGO_BASE`);
el cliente guarda sólo lo que cambia. Toda cuenta configurada debe existir en su catálogo y
ser afectable: se valida al guardar y otra vez al generar (el catálogo pudo cambiar).

REGLAS DE EGRESOS
-----------------
Se aplican por concepto de cada CFDI recibido, de menor a mayor `prioridad`; gana la primera
que coincide. Criterios: `rfc` (RFC del proveedor), `clave` (ClaveProdServ exacta), `prefijo`
(ClaveProdServ que empieza con), `uso` (UsoCFDI) y `descripcion` (texto contenido en la
descripción del concepto, sin distinguir mayúsculas). Sin regla, en este orden:
1. UsoCFDI S01 (sin efectos fiscales) → gastos no deducibles, si `uso_s01_no_deducible`.
2. Forma de pago 01 (efectivo) con total > $2,000 → no deducibles, si `efectivo_no_deducible`
   (Art. 27, fr. III, LISR: los pagos mayores a $2,000 deben hacerse por transferencia,
   cheque nominativo o tarjeta para ser deducibles). Apagado por default: es criterio del
   despacho y la regla tiene excepciones (combustibles, zonas sin bancos).
3. UsoCFDI de inversiones (I01–I08) → la cuenta de activo fijo de ese uso.
4. Base del concepto ≥ `tope_activo` (si es mayor que 0) → activo fijo. Default 0: el despacho
   decide su tope; no hay un monto legal único.
5. UsoCFDI G01 (adquisición de mercancías) → compras.
6. Lo demás → gastos generales (la cuenta por default).

RETENCIONES EN PPD (`retenciones_al_pago`, default true)
--------------------------------------------------------
La obligación de retener (y el derecho a acreditar lo retenido) nace con el PAGO (arts. 1-A
LIVA y 106 LISR). Con `true`, las retenciones de una factura PPD se registran en cuentas de
"retenido pendiente" (`*_pendiente`) y el complemento de pago las traspasa a 216.xx / 113.xx
en proporción a lo pagado (todo lo que quede, en la última parcialidad). Con `false`, se
registran directo en 216.xx / 113.xx al facturar (comportamiento anterior). Las PUE no
cambian: se pagan al facturar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contabilidad import catalogo
from app.exceptions import FiscalAgentError
from app.modelos.contabilidad import ConfigContable, CuentaContable, ReglaEgreso
from app.modelos.nucleo import Cliente

# rol → (cuenta default, descripción para la pantalla)
ROLES: dict[str, tuple[str, str]] = {
    "clientes": ("105.01", "Clientes"),
    "proveedores": ("201.01", "Proveedores"),
    "bancos": ("102.01.01", "Bancos (si la forma de pago no tiene cuenta)"),
    "caja": ("101.01", "Caja (pagos en efectivo)"),
    "ingresos": ("401.01", "Ingresos gravados a tasa general"),
    "ingresos_tasa_0": ("401.04", "Ingresos gravados al 0 %"),
    "ingresos_exentos": ("401.07", "Ingresos exentos"),
    "devoluciones_ingresos": ("402.01", "Devoluciones y descuentos sobre ventas (notas)"),
    "iva_trasladado_cobrado": ("208.01", "IVA trasladado cobrado"),
    "iva_trasladado_no_cobrado": ("209.01", "IVA trasladado no cobrado"),
    "ieps_trasladado_cobrado": ("208.02", "IEPS trasladado cobrado"),
    "ieps_trasladado_no_cobrado": ("209.02", "IEPS trasladado no cobrado"),
    "iva_acreditable_pagado": ("118.01", "IVA acreditable pagado"),
    "iva_acreditable_pendiente": ("119.01", "IVA acreditable pendiente de pago"),
    "iva_retenido_por_clientes": ("113.01", "IVA que nos retuvieron los clientes"),
    "isr_retenido_por_clientes": ("113.02", "ISR que nos retuvieron los clientes"),
    "iva_retenido_por_enterar": ("216.10", "IVA retenido a proveedores, por enterar"),
    "isr_retenido_honorarios": ("216.04", "ISR retenido por servicios profesionales"),
    "isr_retenido_arrendamiento": ("216.03", "ISR retenido por arrendamiento"),
    "gastos": ("601.84", "Gastos generales (cuenta por default)"),
    "gastos_no_deducibles": ("601.83", "Gastos no deducibles"),
    "compras": ("501.01", "Compras de mercancía (UsoCFDI G01)"),
    "activo_fijo": ("160.01", "Activo fijo (tope o UsoCFDI de inversión)"),
    "sueldos": ("601.01", "Sueldos y salarios (nómina)"),
    "asimilados": ("601.31", "Asimilados a salarios (nómina)"),
    "isr_retenido_salarios": ("216.01", "ISR retenido por sueldos"),
    "isr_retenido_asimilados": ("216.02", "ISR retenido por asimilados"),
    # Nómina (revisión P2): cada deducción y otro pago a su cuenta, según el agrupador.
    "imss_obrero_nomina": ("216.11", "Cuota obrera IMSS retenida (216.11 del agrupador)"),
    "otras_deducciones_nomina": ("205.06", "Otras deducciones de nómina (préstamos, "
                                 "Infonavit, pensión alimenticia…)"),
    "otros_pagos_nomina": ("110.01", "Subsidio para el empleo (TipoOtroPago 002, 007, 008)"),
    "viaticos_nomina": ("107.01", "Viáticos entregados en nómina (TipoOtroPago 003)"),
    "reintegro_isr_nomina": ("216.01", "Reintegro / compensación de ISR en nómina "
                             "(TipoOtroPago 001, 004, 005)"),
    "otros_pagos_distintos_nomina": ("601.84", "Otros pagos de nómina (TipoOtroPago 006, "
                                     "009, 999)"),
    # Retenciones de facturas PPD mientras no se pagan (`retenciones_al_pago`).
    "iva_retenido_por_clientes_pendiente": ("113.08.01", "IVA que nos retendrán los clientes "
                                            "(PPD pendiente de cobro)"),
    "isr_retenido_por_clientes_pendiente": ("113.08.02", "ISR que nos retendrán los clientes "
                                            "(PPD pendiente de cobro)"),
    "iva_retenido_por_enterar_pendiente": ("216.12.01", "IVA retenido a proveedores pendiente de "
                                           "pago (PPD)"),
    "isr_retenido_honorarios_pendiente": ("216.12.02", "ISR por servicios profesionales "
                                          "pendiente de pago (PPD)"),
    "isr_retenido_arrendamiento_pendiente": ("216.12.03", "ISR por arrendamiento pendiente de "
                                             "pago (PPD)"),
    # P2-08: cierre anual y apertura.
    "resultado_utilidad": ("305.01", "Utilidad del ejercicio (póliza de cierre)"),
    "resultado_perdida": ("305.02", "Pérdida del ejercicio (póliza de cierre)"),
    "utilidad_anteriores": ("304.01", "Utilidad de ejercicios anteriores (apertura)"),
    "perdida_anteriores": ("304.02", "Pérdida de ejercicios anteriores (apertura)"),
}

# c_FormaPago del SAT → rol de la cuenta de efectivo. Las formas que no mueven dinero
# (dación, compensación, condonación, 99 "por definir"…) no están: no generan cobro.
FORMAS_DINERO: dict[str, str] = {
    "01": "caja", "02": "bancos", "03": "bancos", "04": "bancos", "05": "bancos",
    "06": "bancos", "08": "bancos", "28": "bancos", "29": "bancos", "31": "bancos",
}

# UsoCFDI de inversiones → cuenta de activo fijo del catálogo base.
USO_ACTIVO: dict[str, str] = {
    "I01": "152.01", "I02": "155.01", "I03": "154.01", "I04": "156.01",
    "I05": "160.01", "I06": "160.01", "I07": "160.01", "I08": "153.01",
}

CRITERIOS = ("rfc", "clave", "prefijo", "uso", "descripcion")
TOPE_EFECTIVO = Decimal("2000")  # Art. 27, fr. III, LISR.


def obtener_o_crear(db: Session, cliente: Cliente) -> ConfigContable:
    config = db.get(ConfigContable, cliente.id)
    if config is None:
        config = ConfigContable(cliente_id=cliente.id, cuentas={}, formas_pago={},
                                tope_activo=Decimal("0"), plantilla_concepto="",
                                retenciones_al_pago=True)
        db.add(config)
        db.flush()
    return config


@dataclass
class ConfigEfectiva:
    """La configuración con los defaults resueltos, lista para el generador."""

    config: ConfigContable
    cuentas: dict[str, str]
    formas_pago: dict[str, str]
    reglas: list[ReglaEgreso]

    def cuenta(self, rol: str) -> str:
        return self.cuentas[rol]

    def cuenta_forma_pago(self, forma: str) -> str | None:
        """La cuenta de caja/bancos de esa forma de pago, o None si no mueve dinero."""
        if forma in self.formas_pago:
            return self.formas_pago[forma]
        rol = FORMAS_DINERO.get(forma)
        return self.cuentas[rol] if rol else None


def efectiva(db: Session, cliente: Cliente) -> ConfigEfectiva:
    config = obtener_o_crear(db, cliente)
    cuentas = {rol: default for rol, (default, _d) in ROLES.items()}
    cuentas.update({k: v for k, v in (config.cuentas or {}).items() if v})
    reglas = list(db.scalars(
        select(ReglaEgreso).where(ReglaEgreso.cliente_id == cliente.id, ReglaEgreso.activa)
        .order_by(ReglaEgreso.prioridad, ReglaEgreso.id)
    ))
    return ConfigEfectiva(config, cuentas, dict(config.formas_pago or {}), reglas)


def _validar_cuenta(cuentas: dict[str, CuentaContable], numero: str, para: str) -> None:
    cuenta = cuentas.get(numero)
    if cuenta is None:
        raise FiscalAgentError(f"{para}: la cuenta {numero} no existe en el catálogo.", 422)
    if not cuenta.afectable:
        raise FiscalAgentError(
            f"{para}: la cuenta {numero} tiene subcuentas; elige una cuenta afectable.", 422)


def guardar(db: Session, cliente: Cliente, datos: dict[str, Any]) -> ConfigContable:
    """Guarda la configuración (sólo los campos presentes) y valida sus cuentas."""
    config = obtener_o_crear(db, cliente)
    cuentas_catalogo = catalogo.por_numero(db, cliente)
    if "cuentas" in datos:
        nuevas = {k: str(v).strip() for k, v in (datos["cuentas"] or {}).items() if v}
        for rol, numero in nuevas.items():
            if rol not in ROLES:
                raise FiscalAgentError(f"Rol de cuenta desconocido: {rol}.", 422)
            _validar_cuenta(cuentas_catalogo, numero, ROLES[rol][1])
        config.cuentas = nuevas
    if "formas_pago" in datos:
        formas = {k: str(v).strip() for k, v in (datos["formas_pago"] or {}).items() if v}
        for forma, numero in formas.items():
            _validar_cuenta(cuentas_catalogo, numero, f"Forma de pago {forma}")
        config.formas_pago = formas
    for campo in ("automatica_ingresos", "automatica_egresos", "automatica_pagos",
                  "automatica_nomina", "pue_registra_cobro", "uso_s01_no_deducible",
                  "efectivo_no_deducible", "retenciones_al_pago"):
        if campo in datos and datos[campo] is not None:
            setattr(config, campo, bool(datos[campo]))
    if datos.get("tope_activo") is not None:
        tope = Decimal(str(datos["tope_activo"]))
        if tope < 0:
            raise FiscalAgentError("El tope para activo fijo no puede ser negativo.", 422)
        config.tope_activo = tope.quantize(Decimal("0.01"))
    if "plantilla_concepto" in datos and datos["plantilla_concepto"] is not None:
        config.plantilla_concepto = str(datos["plantilla_concepto"])[:200]
    if "fecha_saldos_iniciales" in datos:
        fecha = datos["fecha_saldos_iniciales"]
        if fecha is not None and fecha.day != 1:
            raise FiscalAgentError("Los saldos iniciales arrancan el día 1 de un mes.", 422)
        config.fecha_saldos_iniciales = fecha
    db.flush()
    return config


def como_dict(db: Session, cliente: Cliente) -> dict[str, Any]:
    ef = efectiva(db, cliente)
    c = ef.config
    return {
        "automatica_ingresos": c.automatica_ingresos, "automatica_egresos": c.automatica_egresos,
        "automatica_pagos": c.automatica_pagos, "automatica_nomina": c.automatica_nomina,
        "pue_registra_cobro": c.pue_registra_cobro,
        "uso_s01_no_deducible": c.uso_s01_no_deducible,
        "efectivo_no_deducible": c.efectivo_no_deducible,
        "retenciones_al_pago": c.retenciones_al_pago is not False,
        "tope_activo": f"{c.tope_activo:.2f}",
        "plantilla_concepto": c.plantilla_concepto,
        "fecha_saldos_iniciales": c.fecha_saldos_iniciales.isoformat()
        if c.fecha_saldos_iniciales else None,
        "cuentas": ef.cuentas,
        "cuentas_personalizadas": dict(c.cuentas or {}),
        "roles": [{"rol": r, "default": d, "descripcion": t} for r, (d, t) in ROLES.items()],
        "formas_pago": {**{f: ef.cuentas[r] for f, r in FORMAS_DINERO.items()}, **ef.formas_pago},
        "reglas": [regla_dict(r) for r in reglas(db, cliente)],
    }


# ── reglas ──


def reglas(db: Session, cliente: Cliente) -> list[ReglaEgreso]:
    return list(db.scalars(select(ReglaEgreso).where(ReglaEgreso.cliente_id == cliente.id)
                           .order_by(ReglaEgreso.prioridad, ReglaEgreso.id)))


def regla_dict(r: ReglaEgreso) -> dict[str, Any]:
    return {"id": r.id, "prioridad": r.prioridad, "criterio": r.criterio, "valor": r.valor,
            "cuenta_numero": r.cuenta_numero, "activa": r.activa}


def _regla_valida(db: Session, cliente: Cliente, criterio: str, valor: str, cuenta: str) -> None:
    if criterio not in CRITERIOS:
        raise FiscalAgentError(f"Criterio de regla desconocido: {criterio}.", 422)
    if not valor.strip():
        raise FiscalAgentError("La regla necesita un valor.", 422)
    _validar_cuenta(catalogo.por_numero(db, cliente), cuenta, "Regla de egresos")


def crear_regla(db: Session, cliente: Cliente, *, criterio: str, valor: str,
                cuenta_numero: str, prioridad: int = 100, activa: bool = True) -> ReglaEgreso:
    _regla_valida(db, cliente, criterio, valor, cuenta_numero)
    regla = ReglaEgreso(cliente_id=cliente.id, criterio=criterio, valor=valor.strip(),
                        cuenta_numero=cuenta_numero.strip(), prioridad=prioridad, activa=activa)
    db.add(regla)
    db.flush()
    return regla


def regla_o_404(db: Session, cliente: Cliente, regla_id: int) -> ReglaEgreso:
    regla = db.scalar(select(ReglaEgreso).where(ReglaEgreso.id == regla_id,
                                                ReglaEgreso.cliente_id == cliente.id))
    if regla is None:
        raise FiscalAgentError("No existe esa regla en este cliente.", 404)
    return regla


def actualizar_regla(db: Session, cliente: Cliente, regla_id: int,
                     datos: dict[str, Any]) -> ReglaEgreso:
    regla = regla_o_404(db, cliente, regla_id)
    criterio = datos.get("criterio") or regla.criterio
    valor = datos.get("valor") if datos.get("valor") is not None else regla.valor
    cuenta = datos.get("cuenta_numero") or regla.cuenta_numero
    _regla_valida(db, cliente, criterio, valor, cuenta)
    regla.criterio, regla.valor, regla.cuenta_numero = criterio, valor.strip(), cuenta.strip()
    if datos.get("prioridad") is not None:
        regla.prioridad = int(datos["prioridad"])
    if datos.get("activa") is not None:
        regla.activa = bool(datos["activa"])
    db.flush()
    return regla


def regla_aplicable(reglas_activas: list[ReglaEgreso], *, rfc: str, clave: str, uso: str,
                    descripcion: str) -> ReglaEgreso | None:
    """La primera regla (por prioridad) que coincide con el concepto."""
    desc = descripcion.lower()
    for r in reglas_activas:
        v = r.valor.strip()
        if ((r.criterio == "rfc" and rfc.upper() == v.upper())
                or (r.criterio == "clave" and clave == v)
                or (r.criterio == "prefijo" and clave.startswith(v))
                or (r.criterio == "uso" and uso.upper() == v.upper())
                or (r.criterio == "descripcion" and v.lower() in desc)):
            return r
    return None
