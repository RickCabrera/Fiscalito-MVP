"""
Impuestos del cliente desde la bóveda (P3-02, P3-03, P3-07).

Lee los CFDI vigentes del cliente, los lleva a flujo de efectivo (`flujo.py`) y llama a los
motores existentes — `calculadora.calcular_declaracion` / `multi_periodo` para el ISR propio,
`iva.py` para el IVA, `isn.py` para el ISN—. No calcula nada por su cuenta: sólo arma la
entrada de cada motor y junta las salidas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.boveda_cfdi.parser import NS_NOMINA12, leer_xml
from app.boveda_cfdi.servicio import leer_xml_original
from app.exceptions import FiscalAgentError
from app.fiscal_engine import isn as motor_isn
from app.fiscal_engine import iva as motor_iva
from app.fiscal_engine.calculadora import calcular_declaracion
from app.fiscal_engine.multi_periodo import calcular_multi_periodo
from app.fiscal_engine.resumen_impuestos import ImporteSistema
from app.impuestos.flujo import Efectivo, flujo_del_mes, nominas_del_mes
from app.modelos.cfdi import Comprobante
from app.modelos.impuestos import ConfigImpuestosCliente
from app.modelos.nucleo import Cliente
from app.redondeo import redondear
from app.schemas.fiscal import CFDI, PerfilContribuyente, TipoFactura
from app.schemas.impuestos import ConfigImpuestosSchema

CERO = Decimal("0.00")
# c_TipoRegimen del complemento de nómina: 02 sueldos; 05 a 11 asimilados a salarios.
REGIMEN_SALARIOS = {"02", "03", "04"}
REGIMEN_ASIMILADOS = {"05", "06", "07", "08", "09", "10", "11"}
# Uso de CFDI de deducciones personales (D01-D10) o "sin efectos fiscales" (S01): su IVA no es
# de la actividad (Art. 5o. fr. I LIVA, estrictamente indispensable). DECISIÓN PROVISIONAL.
USOS_NO_ACREDITABLES = {f"D{n:02d}" for n in range(1, 11)} | {"S01", "CN01"}


# ── configuración del cliente (DP-3) ──


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


# ── IVA ──


def _dec(v: object) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except Exception:  # noqa: BLE001 - importe ilegible en un XML ajeno: cuenta como cero
        return Decimal("0")


def movimiento_iva(e: Efectivo) -> motor_iva.MovimientoIVA:
    """Un `Efectivo` de la bóveda como movimiento del motor de IVA, por tasa (TasaOCuota)."""
    c = e.comprobante
    k = e.factor_pesos
    traslados = (c.datos or {}).get("impuestos", {}).get("traslados", [])
    b16 = i16 = b8 = i8 = b0 = bex = Decimal("0")
    for t in traslados:
        if t.get("Impuesto") != "002":
            continue
        base, imp = _dec(t.get("Base")), _dec(t.get("Importe"))
        if t.get("TipoFactor") == "Exento":
            bex += base
            continue
        tasa = _dec(t.get("TasaOCuota"))
        if tasa == Decimal("0.16"):
            b16, i16 = b16 + base, i16 + imp
        elif tasa == Decimal("0.08"):
            b8, i8 = b8 + base, i8 + imp
        elif tasa == 0:
            b0 += base
        else:
            b16, i16 = b16 + base, i16 + imp
    if not traslados and c.iva_trasladado:
        # CFDI sin desglose por tasa: se supone 16 % sobre el subtotal (se avisa en notas).
        b16, i16 = c.subtotal - c.descuento, c.iva_trasladado
    no_objeto = max(c.subtotal - c.descuento - b16 - b8 - b0 - bex, Decimal("0"))
    uso = (c.uso_cfdi or "").upper()
    return motor_iva.MovimientoIVA(
        uuid=c.uuid, direccion="emitido" if c.direccion == "emitido" else "recibido",
        base_16=b16 * k, iva_16=i16 * k, base_8=b8 * k, iva_8=i8 * k, base_0=b0 * k,
        base_exento=bex * k, base_no_objeto=no_objeto * k, iva_retenido=c.iva_retenido * k,
        signo=-1 if c.tipo == "E" else 1, origen=e.origen,
        deducible=not (c.direccion == "recibido" and uso in USOS_NO_ACREDITABLES),
    )


def config_iva(cfg: ConfigImpuestosSchema) -> motor_iva.ConfigIVA:
    return motor_iva.ConfigIVA(
        region_fronteriza=cfg.region_fronteriza, proporcion_modo=cfg.proporcion_iva_modo,
        proporcion_fija=cfg.proporcion_iva_fija, modo_corte=cfg.modo_factor,
        no_objeto_excluidos=frozenset(cfg.iva_no_objeto_excluidos),
    )


def iva_periodos(
    db: Session, cliente: Cliente, anio: int, meses: list[int],
    saldo_inicial: Decimal | None = None,
    opciones_saldo: dict[int, motor_iva.OpcionSaldo] | None = None,
) -> list[motor_iva.ResultadoIVAMes]:
    """IVA de varios meses desde la bóveda, arrastrando el saldo a favor (Art. 6o. LIVA)."""
    cfg = config_de(db, cliente)
    movs = {
        m: [movimiento_iva(e) for e in flujo_del_mes(db, cliente, anio, m)]
        for m in sorted(set(meses))
    }
    return motor_iva.calcular_iva_periodos(
        anio, meses, movs,
        saldo_inicial if saldo_inicial is not None else cfg.saldo_favor_iva_inicial,
        config_iva(cfg), cfg.asignacion_iva, opciones_saldo,
    )


# ── ISR propio (reusa calculadora.py) ──


def _como_cfdi(e: Efectivo) -> CFDI:
    """El efectivo como `CFDI` del motor viejo, ya proporcionado y marcado PUE."""
    c, k = e.comprobante, e.factor_pesos
    concepto = ((c.datos or {}).get("conceptos") or [{}])[0]
    return CFDI(
        uuid=c.uuid, fecha=e.fecha,
        tipo=TipoFactura.EGRESO if c.tipo == "E" else TipoFactura.INGRESO,
        rfc_emisor=c.rfc_emisor, rfc_receptor=c.rfc_receptor,
        subtotal=float(c.subtotal * k), total=float(c.total * k),
        iva_trasladado=float(c.iva_trasladado * k), iva_retenido=float(c.iva_retenido * k),
        isr_retenido=float(c.isr_retenido * k), descuento=float(c.descuento * k),
        uso_cfdi=c.uso_cfdi or "G03", clave_prod_serv=str(concepto.get("ClaveProdServ", "")),
        metodo_pago="PUE",
    )


CLAVE_ISR_POR_REGIMEN = {
    "612": "isr_pf_empresarial", "606": "isr_arrendamiento", "625": "isr_plataformas",
    "626": "isr_resico_pf",
}


def isr_propio(db: Session, cliente: Cliente, anio: int, mes: int) -> list[ImporteSistema]:
    """Renglón de ISR propio según el régimen del cliente, con el motor existente."""
    # P3-01: personas morales (601) y RESICO PM con su motor (Art. 14 / Art. 211 LISR).
    from app.impuestos.personas_morales import isr_del_mes  # importa este módulo

    pm = isr_del_mes(db, cliente, anio, mes)
    if pm is not None:
        return [pm]
    regimen = regimen_de(cliente)
    clave = CLAVE_ISR_POR_REGIMEN.get(regimen)
    if clave is None:
        return []
    perfil = PerfilContribuyente(rfc=cliente.rfc or "XAXX010101000", regimen=regimen,
                                 nombre=cliente.nombre)
    if regimen in ("612", "606"):
        facturas = [
            _como_cfdi(e) for m in range(1, mes + 1) for e in flujo_del_mes(db, cliente, anio, m)
        ]
        resultados, _ = calcular_multi_periodo(perfil, facturas, anio, list(range(1, mes + 1)))
        desglose = resultados[-1].desglose
        nota = "Pago provisional acumulado (Art. 106/116 LISR) con los meses de la bóveda."
    else:
        facturas = [_como_cfdi(e) for e in flujo_del_mes(db, cliente, anio, mes)]
        desglose = calcular_declaracion(perfil, facturas, periodo_month=mes)
        nota = "Retenciones como pago definitivo" if desglose.retenciones_definitivas else ""
    return [ImporteSistema(clave, redondear(Decimal(str(desglose.isr_a_pagar))), nota)]


# ── retenciones ──


def retenciones_isr(db: Session, cliente: Cliente, anio: int, mes: int) -> list[ImporteSistema]:
    """ISR retenido a enterar: nómina (salarios/asimilados) y CFDI recibidos pagados en el mes."""
    salarios = asimilados = Decimal("0")
    for n in nominas_del_mes(db, cliente, anio, mes):
        regimen = (n.datos or {}).get("nomina", {}).get("receptor", {}).get("TipoRegimen", "02")
        if regimen in REGIMEN_ASIMILADOS:
            asimilados += n.isr_retenido
        else:
            salarios += n.isr_retenido
    por_regimen = {"612": Decimal("0"), "606": Decimal("0"), "626": Decimal("0")}
    for e in flujo_del_mes(db, cliente, anio, mes):
        c = e.comprobante
        if c.direccion != "recibido" or not c.isr_retenido:
            continue
        reg = str((c.datos or {}).get("emisor", {}).get("RegimenFiscal", "612"))
        por_regimen[reg if reg in por_regimen else "612"] += c.isr_retenido * e.factor_pesos * (
            -1 if c.tipo == "E" else 1)
    nota_nom = ("ISR de los CFDI de nómina con fecha de pago en el mes; ya viene neto del "
                "subsidio acreditado en cada recibo.")
    return [
        ImporteSistema("ret_isr_salarios", redondear(salarios), nota_nom),
        ImporteSistema("ret_isr_asimilados", redondear(asimilados), nota_nom),
        ImporteSistema("ret_isr_honorarios", redondear(por_regimen["612"]),
                       "CFDI recibidos pagados en el mes (régimen del emisor 612 u otro)."),
        ImporteSistema("ret_isr_arrendamiento", redondear(por_regimen["606"])),
        ImporteSistema("ret_isr_resico", redondear(por_regimen["626"]),
                       "Art. 113-J LISR: 1.25 % retenido a RESICO PF."),
    ]


def importes_del_periodo(
    db: Session, cliente: Cliente, anio: int, mes: int
) -> tuple[list[ImporteSistema], list[str]]:
    """Todos los importes del sistema para el resumen."""
    notas: list[str] = []
    importes = isr_propio(db, cliente, anio, mes)
    if not regimen_de(cliente):
        notas.append("El cliente no tiene régimen capturado: no se calcula ISR propio.")
    importes += retenciones_isr(db, cliente, anio, mes)
    iva = iva_periodos(db, cliente, anio, list(range(1, mes + 1)))[-1]
    importes.append(ImporteSistema(
        "iva_a_cargo", iva.iva_a_pagar,
        f"Acreditado saldo a favor anterior {iva.saldo_favor_anterior:.2f}; saldo a favor "
        f"siguiente {iva.saldo_favor_siguiente:.2f}." if iva.saldo_favor_anterior
        or iva.saldo_favor_siguiente else "",
    ))
    importes.append(ImporteSistema("iva_retenido", iva.iva_retenido_a_terceros,
                                   "Art. 1o.-A LIVA: IVA retenido a terceros por enterar."))
    notas += iva.notas
    return importes, notas


# ── ISN ──


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


def resumen_iva_json(r: motor_iva.ResultadoIVAMes) -> dict[str, Any]:
    return motor_iva.resultado_iva_dict(r)
