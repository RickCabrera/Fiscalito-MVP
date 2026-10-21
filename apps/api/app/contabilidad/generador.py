"""
Generador de pólizas automáticas desde la bóveda (P2-03).

QUÉ GENERA
----------
Para un cliente y un rango de fechas, una póliza por CFDI **vigente** (`comprobantes_vigentes`:
los no cancelados) que todavía no tenga póliza, con el esquema de `asientos.py`:

| CFDI                    | Dirección | Póliza                          | Interruptor          |
|-------------------------|-----------|---------------------------------|----------------------|
| I (ingreso)             | emitido   | venta (diario o ingreso si PUE) | automatica_ingresos  |
| E (nota de crédito)     | emitido   | venta invertida                 | automatica_ingresos  |
| I                       | recibido  | gasto (diario o egreso si PUE)  | automatica_egresos   |
| E                       | recibido  | gasto invertido                 | automatica_egresos   |
| P (complemento de pago) | ambos     | cobro / pago + IVA efectivo     | automatica_pagos     |
| N (nómina)              | emitido   | nómina (egreso)                 | automatica_nomina    |

Los traslados (T) y la nómina recibida (el cliente como trabajador) no generan póliza.

IDEMPOTENTE POR UUID
--------------------
La póliza lleva `clave_origen = "cfdi:<UUID>"`, única por cliente: correr dos veces el mismo
mes (o un trabajo que se reintenta) no duplica. Un CFDI cuya póliza se canceló a mano NO se
vuelve a generar: la decisión del contador manda.

COMPLEMENTOS DE PAGO: FECHA = `FechaPago` (§D-C1)
-------------------------------------------------
La póliza de un CFDI P lleva la fecha de pago de su complemento, no la de emisión, y entra
al periodo por esa fecha: un cobro del 31 de octubre timbrado el 3 de noviembre es de
octubre (flujo de efectivo, arts. 1-B LIVA y 102 LISR). Si el complemento trae pagos de
días distintos se genera una póliza por día: la primera con `clave_origen = "cfdi:<UUID>"`
si es la única, o `"cfdi:<UUID>@AAAA-MM-DD"` cuando hay varias.

NOTAS DE CRÉDITO SOBRE PPD
--------------------------
Las E se generan después de las I y antes de los P, y revierten sus impuestos contra lo
que siga pendiente de la factura PPD relacionada (`asientos.redirigir_a_pendientes`).

CANCELADOS
----------
Antes de generar, los CFDI ya cancelados ante el SAT que tienen póliza activa la cancelan (o
la revierten si su mes está cerrado). P1-03 además lo hace en el momento en que detecta la
cancelación (`app/sat_verificacion/estatus.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boveda_cfdi.fechas_pago import VENTANA_ANTES, VENTANA_DESPUES, pagos_por_fecha
from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.contabilidad import asientos, catalogo, polizas
from app.contabilidad.asientos import CERO, DocumentoPagado, NoContabilizable, Pendiente, d
from app.contabilidad.config import ConfigEfectiva, efectiva
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, Poliza
from app.modelos.nucleo import Cliente

LOTE = 200
CONCEPTOS = {
    ("I", "emitido"): "Venta", ("I", "recibido"): "Compra/gasto",
    ("E", "emitido"): "Nota de crédito a cliente",
    ("E", "recibido"): "Nota de crédito de proveedor",
    ("P", "emitido"): "Cobro de cliente", ("P", "recibido"): "Pago a proveedor",
    ("N", "emitido"): "Nómina",
}


@dataclass
class ResultadoGeneracion:
    generadas: int = 0
    ya_existian: int = 0
    omitidas: int = 0
    canceladas: int = 0
    revertidas: int = 0
    errores: list[dict[str, str]] = field(default_factory=list)
    omitidas_detalle: list[dict[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {"generadas": self.generadas, "ya_existian": self.ya_existian,
                "omitidas": self.omitidas, "canceladas": self.canceladas,
                "revertidas": self.revertidas, "errores": self.errores[:100],
                "omitidas_detalle": self.omitidas_detalle[:100]}


def _rango(desde: date, hasta: date) -> list[Any]:
    return [Comprobante.fecha >= datetime.combine(desde, time.min),
            Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), time.min)]


def _habilitado(ef: ConfigEfectiva, comp: Comprobante) -> str | None:
    """None si se contabiliza; si no, la razón."""
    cfg = ef.config
    if comp.tipo == "T":
        return "Traslado: no mueve cuentas."
    if comp.tipo == "N":
        if comp.direccion != "emitido":
            return "Nómina recibida (el cliente es el trabajador)."
        return None if cfg.automatica_nomina else "Contabilidad automática de nómina apagada."
    if comp.tipo == "P":
        return None if cfg.automatica_pagos else "Contabilidad automática de pagos apagada."
    if comp.direccion == "emitido":
        return None if cfg.automatica_ingresos else "Contabilidad automática de ingresos apagada."
    return None if cfg.automatica_egresos else "Contabilidad automática de egresos apagada."


def _concepto(ef: ConfigEfectiva, comp: Comprobante) -> str:
    contraparte = comp.nombre_receptor if comp.direccion == "emitido" else comp.nombre_emisor
    rfc = comp.rfc_receptor if comp.direccion == "emitido" else comp.rfc_emisor
    etiqueta = CONCEPTOS.get((comp.tipo, comp.direccion), comp.tipo)
    folio = f"{comp.serie}{comp.folio}".strip()
    plantilla = ef.config.plantilla_concepto or "{etiqueta} {folio} {contraparte}"
    try:
        texto = plantilla.format(etiqueta=etiqueta, folio=folio, contraparte=contraparte or rfc,
                                 rfc=rfc, uuid=comp.uuid, tipo=comp.tipo)
    except (KeyError, IndexError, ValueError):
        texto = f"{etiqueta} {folio} {contraparte or rfc}"
    return " ".join(texto.split())[:500]


RELACION_NOTA = ("01", "03")  # c_TipoRelacion: nota de crédito / devolución de mercancía


class Pendientes:
    """
    Lo pendiente de cada factura PPD (por UUID y dirección), calculado una vez por corrida y
    mutado en memoria por las notas y los pagos del mismo lote.

    - `original`: lo que dejó la póliza de la factura en cada cuenta pendiente (base de la
      proporción de cada parcialidad). Sin póliza pero en la bóveda (PPD): IVA e IEPS del
      CFDI, como antes.
    - `restante`: `original` sin póliza, más el saldo de TODOS los movimientos activos con
      el UUID de la factura en esa cuenta (la factura, pagos previos, notas de crédito).
    """

    def __init__(self, db: Session, cliente: Cliente, ef: ConfigEfectiva) -> None:
        self.db, self.cliente, self.ef = db, cliente, ef
        self.cache: dict[tuple[str, bool], DocumentoPagado] = {}

    def de(self, uuids: set[str], emitido: bool) -> dict[str, DocumentoPagado]:
        faltan = {u for u in uuids if u and (u, emitido) not in self.cache}
        if faltan:
            self._cargar(faltan, emitido)
        return {u: self.cache[(u, emitido)] for u in uuids if (u, emitido) in self.cache}

    def _cargar(self, uuids: set[str], emitido: bool) -> None:
        db, cliente = self.db, self.cliente
        db.flush()
        mapa = asientos.cuentas_pendientes(self.ef, emitido)
        facturas = {c.uuid: c for c in db.scalars(select(Comprobante).where(
            Comprobante.cliente_id == cliente.id, Comprobante.uuid.in_(uuids)))}
        con_poliza = set(db.scalars(select(Poliza.uuid_cfdi).where(
            Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
            Poliza.clave_origen.in_([f"cfdi:{u}" for u in uuids]))))
        original: dict[tuple[str, str], Any] = {}
        saldo: dict[tuple[str, str], Any] = {}
        filas = db.execute(
            select(MovimientoPoliza.uuid_cfdi, CuentaContable.numero, MovimientoPoliza.cargo,
                   MovimientoPoliza.abono, Poliza.clave_origen)
            .join(Poliza, Poliza.id == MovimientoPoliza.poliza_id)
            .join(CuentaContable, CuentaContable.id == MovimientoPoliza.cuenta_id)
            .where(Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
                   MovimientoPoliza.uuid_cfdi.in_(uuids), CuentaContable.numero.in_(list(mapa))))
        for uuid, numero, cargo, abono, clave in filas:
            deudora = mapa[numero][1]
            neto = (cargo - abono) if deudora else (abono - cargo)
            k = (uuid, numero)
            saldo[k] = saldo.get(k, CERO) + neto
            if clave == f"cfdi:{uuid}":
                original[k] = original.get(k, CERO) + neto
        iva_rol = "iva_trasladado_no_cobrado" if emitido else "iva_acreditable_pendiente"
        for uuid in uuids:
            f = facturas.get(uuid)
            if f is None:
                self.cache[(uuid, emitido)] = DocumentoPagado(CERO, {}, conocido=False)
                continue
            base: dict[str, Any] = {}
            if uuid not in con_poliza and f.metodo_pago == "PPD":
                factor = asientos.factor_moneda(f.moneda, f.tipo_cambio)
                base[self.ef.cuenta(iva_rol)] = asientos.c(f.iva_trasladado * factor)
                if emitido:
                    base[self.ef.cuenta("ieps_trasladado_no_cobrado")] = asientos.c(
                        f.ieps * factor)
            pendientes = {}
            for numero, (destino, deudora, etiqueta) in mapa.items():
                orig = original.get((uuid, numero), CERO) + base.get(numero, CERO)
                resta = saldo.get((uuid, numero), CERO) + base.get(numero, CERO)
                if orig or resta:
                    pendientes[numero] = Pendiente(destino, deudora, etiqueta, orig, resta)
            self.cache[(uuid, emitido)] = DocumentoPagado(d(f.total), pendientes, conocido=True)


def _uuids_pagados(lista: list[dict[str, Any]]) -> set[str]:
    return {str(doc.get("IdDocumento") or "").upper()
            for p in lista for doc in p.get("documentos") or []} - {""}


def _relacionados_ppd(comp: Comprobante, pend: Pendientes) -> list[tuple[str, dict[str, Any]]]:
    """Facturas PPD (con algo pendiente) a las que una E se relaciona como nota/devolución."""
    uuids = [u.upper() for g in (comp.datos or {}).get("cfdi_relacionados") or []
             if g.get("tipo_relacion") in RELACION_NOTA for u in g.get("uuids") or []]
    if not uuids:
        return []
    docs = pend.de(set(uuids), comp.direccion == "emitido")
    return [(u, docs[u].pendientes) for u in dict.fromkeys(uuids)
            if u in docs and docs[u].conocido and docs[u].pendientes]


def _asiento(comp: Comprobante, ef: ConfigEfectiva, existentes: set[str],
             pend: Pendientes, lista: list[dict[str, Any]] | None = None,
             usar_totales: bool = True) -> asientos.Asiento:
    if comp.tipo == "N":
        return asientos.nomina(comp, ef)
    if comp.tipo == "P":
        docs = pend.de(_uuids_pagados(lista or []), comp.direccion == "emitido")
        return asientos.pago(comp, ef, docs, lista or [], usar_totales=usar_totales)
    nota = comp.tipo == "E"
    if comp.direccion == "emitido":
        asiento = asientos.factura_emitida(comp, ef, nota=nota)
    else:
        asiento = asientos.factura_recibida(comp, ef, existentes, nota=nota)
    if nota:
        relacionados = _relacionados_ppd(comp, pend)
        if relacionados:
            asientos.redirigir_a_pendientes(asiento, relacionados)
    return asiento


@dataclass
class _Unidad:
    """Una póliza por generar: el CFDI, su clave, su fecha y (en un P) sus pagos."""

    comp: Comprobante
    clave: str
    fecha: date
    pagos: list[dict[str, Any]] | None = None
    unica: bool = True


def _unidades(comp: Comprobante, desde: date, hasta: date) -> list[_Unidad]:
    if comp.tipo != "P":
        return [_Unidad(comp, f"cfdi:{comp.uuid}", comp.fecha.date())]
    grupos = pagos_por_fecha(comp) or {comp.fecha.date(): []}
    unica = len(grupos) == 1
    return [_Unidad(comp, f"cfdi:{comp.uuid}" if unica else f"cfdi:{comp.uuid}@{f.isoformat()}",
                    f, lista, unica)
            for f, lista in sorted(grupos.items()) if desde <= f <= hasta]


def revertir_cancelados(db: Session, cliente: Cliente, desde: date | None = None,
                        hasta: date | None = None) -> tuple[int, int]:
    """Cancela (o revierte) las pólizas activas de CFDI que ya están cancelados ante el SAT."""
    db.flush()  # la sesión no tiene autoflush: un estatus recién cambiado debe verse
    cond = [Comprobante.cliente_id == cliente.id, Comprobante.estatus_sat == "cancelado",
            Poliza.estado == "activa", Poliza.reversa_de_id.is_(None)]
    if desde and hasta:
        cond += _rango(desde, hasta)
    # Un P partido por fecha de pago tiene varias pólizas (`cfdi:<UUID>@fecha`): todas
    # llevan `uuid_cfdi` = el UUID del complemento.
    comps = db.scalars(
        select(Comprobante).join(Poliza, (Poliza.cliente_id == Comprobante.cliente_id)
                                 & (Poliza.uuid_cfdi == Comprobante.uuid))
        .where(*cond, Poliza.clave_origen.like("cfdi:%")).distinct())
    canceladas = revertidas = 0
    for comp in comps:
        r = polizas.cancelar_por_cfdi_o_alertar(db, comp)
        canceladas += r == "cancelada"
        revertidas += r == "reversa"
    return canceladas, revertidas


def _respaldo(comp: Comprobante, u: _Unidad, pend: Pendientes) -> list[tuple[Pendiente, Any]]:
    """Los `restante` que este CFDI puede mutar, para devolverlos si su póliza falla."""
    emitido = comp.direccion == "emitido"
    if comp.tipo == "P":
        docs = pend.de(_uuids_pagados(u.pagos or []), emitido)
    elif comp.tipo == "E":
        docs = {uuid: pend.de({uuid}, emitido)[uuid] for uuid, _p in _relacionados_ppd(comp, pend)}
    else:
        return []
    return [(p, p.restante) for doc in docs.values() for p in doc.pendientes.values()]


def _generar_una(db: Session, cliente: Cliente, ef: ConfigEfectiva, u: _Unidad,
                 existentes: set[str], cuentas: dict[str, CuentaContable], pend: Pendientes,
                 ya: set[str], r: ResultadoGeneracion, uid: str) -> None:
    comp = u.comp
    respaldo = _respaldo(comp, u, pend)
    try:
        polizas.exigir_abierto(db, cliente.id, u.fecha)
        asiento = _asiento(comp, ef, existentes, pend, u.pagos, usar_totales=u.unica)
        if not asiento.renglones:
            raise NoContabilizable("El CFDI no tiene importes que contabilizar.")
        if asiento.total_cargos != asiento.total_abonos:  # defensa: nunca debe pasar
            raise NoContabilizable(
                f"Asiento descuadrado ({asiento.total_cargos} ≠ {asiento.total_abonos}).")
        faltan = {x.cuenta for x in asiento.renglones} - set(cuentas)
        if faltan and catalogo.asegurar_base(db, cliente, faltan):
            # Cuentas del catálogo base que el cliente no tenía (sembrado antes de que
            # existieran, p. ej. retenciones pendientes): se agregan al usarlas.
            cuentas.update(catalogo.por_numero(db, cliente))
            existentes.update(cuentas)
        movs = polizas.movimientos_de_asiento(asiento, cuentas)
    except (NoContabilizable, FiscalAgentError) as e:
        for pendiente, restante in respaldo:  # el asiento no se guardó: nada se traspasó
            pendiente.restante = restante
        r.errores.append({"uuid": comp.uuid, "error": str(e)})
        return
    advertencias = list(asiento.advertencias)
    if asiento.diferencia:
        advertencias.append(
            f"Diferencia de {asiento.diferencia:.2f} contra el total del CFDI (impuestos "
            "que no se leen, p. ej. locales).")
    if comp.tipo == "P" and u.fecha != comp.fecha.date():
        advertencias.append(f"Fecha de la póliza = FechaPago {u.fecha.isoformat()} (el "
                            f"complemento se emitió el {comp.fecha.date().isoformat()}).")
    poliza = Poliza(
        cliente_id=cliente.id, tipo=asiento.tipo, fecha=u.fecha, concepto=_concepto(ef, comp),
        origen="automatica", estado="activa", uuid_cfdi=comp.uuid, tipo_cfdi=comp.tipo,
        clave_origen=u.clave, diferencia=asiento.diferencia,
        advertencias=advertencias, creado_por=uid,
    )
    polizas.guardar(db, poliza, movs)
    ya.add(u.clave)
    r.generadas += 1


def generar(db: Session, cliente: Cliente, desde: date, hasta: date,
            uid: str = "") -> ResultadoGeneracion:
    """Genera las pólizas automáticas del rango. Idempotente. No hace commit."""
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    if not catalogo.cuentas(db, cliente):
        raise FiscalAgentError(
            "El cliente no tiene catálogo de cuentas: siembra el catálogo base primero.", 409)
    r = ResultadoGeneracion()
    r.canceladas, r.revertidas = revertir_cancelados(db, cliente, desde, hasta)
    ef = efectiva(db, cliente)
    cuentas = catalogo.por_numero(db, cliente)
    existentes = set(cuentas)

    ya = set(db.scalars(select(Poliza.clave_origen).where(
        Poliza.cliente_id == cliente.id, Poliza.clave_origen.is_not(None))))
    consulta = comprobantes_vigentes(
        select(Comprobante).where(Comprobante.cliente_id == cliente.id, Comprobante.tipo != "P",
                                  *_rango(desde, hasta)))
    # Los P entran por su FechaPago (§D-C1): se buscan en una ventana amplia y se filtran.
    consulta_p = comprobantes_vigentes(
        select(Comprobante).where(Comprobante.cliente_id == cliente.id, Comprobante.tipo == "P",
                                  *_rango(desde - VENTANA_ANTES, hasta + VENTANA_DESPUES)))
    # Facturas, luego notas, luego pagos: una nota o un pago del mismo lote encuentra la
    # póliza de su factura.
    comps = sorted([*db.scalars(consulta), *db.scalars(consulta_p)],
                   key=lambda c: (c.tipo == "P", c.tipo == "E", c.fecha, c.id))
    pend = Pendientes(db, cliente, ef)
    for comp in comps:
        unidades = _unidades(comp, desde, hasta)
        if not unidades:
            continue  # P cuyos pagos son de otro periodo
        razon = _habilitado(ef, comp)
        if razon is not None:
            if any(u.clave not in ya for u in unidades):
                r.omitidas += 1
                r.omitidas_detalle.append({"uuid": comp.uuid, "razon": razon})
            else:
                r.ya_existian += 1
            continue
        for u in unidades:
            if u.clave in ya:
                r.ya_existian += 1
                continue
            _generar_una(db, cliente, ef, u, existentes, cuentas, pend, ya, r, uid)
            if r.generadas and r.generadas % LOTE == 0:
                db.flush()
    db.flush()
    return r
