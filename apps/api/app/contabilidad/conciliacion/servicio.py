"""
Conciliación bancaria (P2-06): cuentas bancarias, plantillas, importación, emparejamiento,
conciliación manual, deshacer y pólizas desde un movimiento del banco.

El reporte vive en `reporte.py`; la lectura de archivos en `lectores.py` / `pdf_bancos.py`;
la regla de emparejamiento (pura) en `emparejador.py`.

SIGNO COMÚN
-----------
Todo importe que se compara va con signo desde el punto de vista del banco: + entra dinero,
− sale. Banco: `abono − cargo`. Libros (movimiento de póliza sobre la cuenta contable de
bancos): `cargo − abono`. CFDI de la bóveda: emitido (cobro) +, recibido (pago) −.

QUÉ CFDI ENTRAN AL LADO DE LIBROS
---------------------------------
Complementos de pago (P) y facturas PUE (I) con forma de pago que mueve bancos, vigentes,
que todavía NO tengan póliza automática: si la tienen, su movimiento de bancos ya está en el
lado de pólizas y contarlo otra vez sería conciliar el mismo dinero dos veces.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contabilidad import catalogo, polizas
from app.contabilidad.conciliacion import emparejador, lectores, pdf_bancos
from app.contabilidad.conciliacion.emparejador import Partida
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.conciliacion import (
    Conciliacion,
    CuentaBancaria,
    EstadoCuenta,
    MovimientoBancario,
    PartidaConciliacion,
    PlantillaEstadoCuenta,
)
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, Poliza
from app.modelos.nucleo import Cliente

CERO = Decimal("0")
FORMATOS = ("csv", "xlsx", "ofx", "pdf")
FORMAS_BANCO = {"02", "03", "04", "05", "06", "28", "29", "31"}

# Cuenta sugerida (código agrupador) para una póliza creada desde el banco, por palabras
# del concepto. El despacho puede elegir otra; esto sólo llena el campo.
SUGERENCIAS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("iva",), "ambos", "118.01"),
    (("isr ret", "retencion isr", "ret isr"), "ambos", "113.02"),
    (("comision", "com.", "cuota", "anualidad", "manejo de cuenta"), "cargo", "701.10"),
    (("interes",), "abono", "702.04"),
    (("interes",), "cargo", "701.04"),
)


# ── cuentas bancarias ──


def bancos_sat() -> list[dict[str, str]]:
    """Bancos con lector de PDF (los del catálogo c_Banco se aceptan todos)."""
    return [{"clave": d.clave, "nombre": d.nombre} for d in pdf_bancos.DISENOS]


def _validar_cuenta_contable(db: Session, cliente: Cliente, cuenta_id: int) -> CuentaContable:
    c = catalogo.obtener(db, cliente, cuenta_id)
    if not c.afectable:
        raise FiscalAgentError(
            f"La cuenta {c.numero} tiene subcuentas; liga la cuenta bancaria a una afectable.",
            422)
    return c


def crear_cuenta(db: Session, cliente: Cliente, datos: dict[str, Any]) -> CuentaBancaria:
    _validar_cuenta_contable(db, cliente, datos["cuenta_contable_id"])
    cb = CuentaBancaria(cliente_id=cliente.id, **datos)
    db.add(cb)
    db.flush()
    return cb


def cuentas(db: Session, cliente: Cliente) -> list[CuentaBancaria]:
    return list(db.scalars(select(CuentaBancaria).where(CuentaBancaria.cliente_id == cliente.id)
                           .order_by(CuentaBancaria.id)))


def cuenta_o_404(db: Session, cliente: Cliente, cuenta_id: int) -> CuentaBancaria:
    cb = db.scalar(select(CuentaBancaria).where(CuentaBancaria.id == cuenta_id,
                                                CuentaBancaria.cliente_id == cliente.id))
    if cb is None:
        raise FiscalAgentError("No existe esa cuenta bancaria en este cliente.", 404)
    return cb


def actualizar_cuenta(db: Session, cliente: Cliente, cuenta_id: int,
                      cambios: dict[str, Any]) -> CuentaBancaria:
    cb = cuenta_o_404(db, cliente, cuenta_id)
    if cambios.get("cuenta_contable_id") is not None:
        _validar_cuenta_contable(db, cliente, cambios["cuenta_contable_id"])
    for k, v in cambios.items():
        if v is not None:
            setattr(cb, k, v)
    db.flush()
    return cb


def borrar_cuenta(db: Session, cliente: Cliente, cuenta_id: int) -> None:
    cb = cuenta_o_404(db, cliente, cuenta_id)
    hay = db.scalar(select(func.count(MovimientoBancario.id))
                    .where(MovimientoBancario.cuenta_bancaria_id == cb.id))
    if hay:
        raise FiscalAgentError("La cuenta tiene estados de cuenta importados; desactívala en "
                               "vez de borrarla.", 409)
    db.delete(cb)
    db.flush()


def cuenta_dict(db: Session, cb: CuentaBancaria) -> dict[str, Any]:
    cc = db.get(CuentaContable, cb.cuenta_contable_id)
    return {"id": cb.id, "banco": cb.banco, "nombre": cb.nombre, "numero": cb.numero,
            "clabe": cb.clabe, "moneda": cb.moneda, "cuenta_contable_id": cb.cuenta_contable_id,
            "cuenta_contable": cc.numero if cc else "", "ventana_dias": cb.ventana_dias,
            "umbral": cb.umbral, "activa": cb.activa}


# ── plantillas ──


def plantillas(db: Session, cliente: Cliente) -> list[PlantillaEstadoCuenta]:
    return list(db.scalars(select(PlantillaEstadoCuenta)
                           .where(PlantillaEstadoCuenta.cliente_id == cliente.id)
                           .order_by(PlantillaEstadoCuenta.nombre)))


def guardar_plantilla(db: Session, cliente: Cliente, nombre: str, banco: str, formato: str,
                      mapeo: dict[str, Any]) -> PlantillaEstadoCuenta:
    p = db.scalar(select(PlantillaEstadoCuenta).where(
        PlantillaEstadoCuenta.cliente_id == cliente.id, PlantillaEstadoCuenta.nombre == nombre))
    if p is None:
        p = PlantillaEstadoCuenta(cliente_id=cliente.id, nombre=nombre)
        db.add(p)
    p.banco, p.formato, p.mapeo = banco, formato, mapeo
    db.flush()
    return p


def plantilla_o_404(db: Session, cliente: Cliente, plantilla_id: int) -> PlantillaEstadoCuenta:
    p = db.scalar(select(PlantillaEstadoCuenta).where(
        PlantillaEstadoCuenta.id == plantilla_id, PlantillaEstadoCuenta.cliente_id == cliente.id))
    if p is None:
        raise FiscalAgentError("No existe esa plantilla en este cliente.", 404)
    return p


def plantilla_dict(p: PlantillaEstadoCuenta) -> dict[str, Any]:
    return {"id": p.id, "nombre": p.nombre, "banco": p.banco, "formato": p.formato,
            "mapeo": p.mapeo}


# ── importación ──


def formato_de(nombre: str, datos: bytes, formato: str | None) -> str:
    if formato:
        if formato not in FORMATOS:
            raise FiscalAgentError(f"Formato inválido; usa uno de {', '.join(FORMATOS)}.", 422)
        return formato
    ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
    if ext in FORMATOS:
        return ext
    if datos.lstrip()[:5] == b"%PDF-":
        return "pdf"
    if datos[:2] == b"PK":
        return "xlsx"
    if b"<OFX>" in datos[:4096].upper():
        return "ofx"
    return "csv"


def _huellas(movs: list[lectores.MovimientoLeido]) -> list[str]:
    vistos: Counter[str] = Counter()
    salida = []
    for m in movs:
        base = f"{m.fecha}|{m.concepto}|{m.referencia}|{m.cargo}|{m.abono}|{m.saldo}"
        vistos[base] += 1
        salida.append(hashlib.sha256(f"{base}|{vistos[base]}".encode()).hexdigest())
    return salida


@dataclass
class Importacion:
    estado: EstadoCuenta
    banco_pdf: str | None = None


def importar(db: Session, cliente: Cliente, cb: CuentaBancaria, *, nombre: str, datos: bytes,
             formato: str | None = None, mapeo: dict[str, Any] | None = None,
             uid: str = "") -> Importacion:
    """Lee el archivo y guarda sus movimientos (sin duplicar los que ya estaban)."""
    fmt = formato_de(nombre, datos, formato)
    banco_pdf = None
    if fmt == "csv":
        lectura = lectores.leer_csv(datos, mapeo)
    elif fmt == "xlsx":
        lectura = lectores.leer_xlsx(datos, mapeo)
    elif fmt == "ofx":
        lectura = lectores.leer_ofx(datos)
    else:
        lectura, diseno = pdf_bancos.leer_pdf(datos, cb.banco)
        banco_pdf = diseno.nombre
        lectura.advertencias.insert(0, f"PDF leído con el diseño de {diseno.nombre} "
                                       "(POR CONFIRMAR CON PDF REAL): revisa los importes.")
    existentes = set(db.scalars(select(MovimientoBancario.huella)
                                .where(MovimientoBancario.cuenta_bancaria_id == cb.id)))
    fechas = [m.fecha for m in lectura.movimientos]
    estado = EstadoCuenta(
        cliente_id=cliente.id, cuenta_bancaria_id=cb.id, archivo=nombre[:200], formato=fmt,
        sha256=hashlib.sha256(datos).hexdigest(), desde=min(fechas), hasta=max(fechas),
        saldo_inicial=lectura.saldo_inicial, saldo_final=lectura.saldo_final,
        advertencias=lectura.advertencias[:200], creado_por=uid)
    db.add(estado)
    db.flush()
    nuevos = duplicados = 0
    for n, (m, h) in enumerate(zip(lectura.movimientos, _huellas(lectura.movimientos),
                                   strict=True)):
        if h in existentes:
            duplicados += 1
            continue
        existentes.add(h)
        db.add(MovimientoBancario(
            cliente_id=cliente.id, cuenta_bancaria_id=cb.id, estado_cuenta_id=estado.id,
            fecha=m.fecha, concepto=m.concepto, referencia=m.referencia, cargo=m.cargo,
            abono=m.abono, saldo=m.saldo, renglon=n, huella=h))
        nuevos += 1
    estado.nuevos, estado.duplicados = nuevos, duplicados
    db.flush()
    return Importacion(estado, banco_pdf)


def estado_dict(e: EstadoCuenta) -> dict[str, Any]:
    def s(v: Decimal | None) -> str | None:
        return f"{v:.2f}" if v is not None else None

    return {"id": e.id, "archivo": e.archivo, "formato": e.formato,
            "desde": e.desde.isoformat() if e.desde else None,
            "hasta": e.hasta.isoformat() if e.hasta else None,
            "saldo_inicial": s(e.saldo_inicial), "saldo_final": s(e.saldo_final),
            "nuevos": e.nuevos, "duplicados": e.duplicados,
            "advertencias": list(e.advertencias or [])}


def estados(db: Session, cb: CuentaBancaria) -> list[EstadoCuenta]:
    return list(db.scalars(select(EstadoCuenta).where(EstadoCuenta.cuenta_bancaria_id == cb.id)
                           .order_by(EstadoCuenta.id.desc())))


# ── los dos lados ──


def _mapa_conciliados(db: Session, cb: CuentaBancaria) -> dict[str, int]:
    """clave de partida ("b:1", "p:2", "c:3") → id de la conciliación."""
    filas = db.execute(select(PartidaConciliacion, Conciliacion.id)
                       .join(Conciliacion, Conciliacion.id == PartidaConciliacion.conciliacion_id)
                       .where(Conciliacion.cuenta_bancaria_id == cb.id))
    salida = {}
    for p, cid in filas:
        if p.movimiento_bancario_id:
            salida[f"b:{p.movimiento_bancario_id}"] = cid
        if p.movimiento_poliza_id:
            salida[f"p:{p.movimiento_poliza_id}"] = cid
        if p.comprobante_id:
            salida[f"c:{p.comprobante_id}"] = cid
    return salida


def movimientos_banco(db: Session, cb: CuentaBancaria, desde: date | None,
                      hasta: date | None) -> list[MovimientoBancario]:
    cond = [MovimientoBancario.cuenta_bancaria_id == cb.id]
    if desde:
        cond.append(MovimientoBancario.fecha >= desde)
    if hasta:
        cond.append(MovimientoBancario.fecha <= hasta)
    return list(db.scalars(select(MovimientoBancario).where(*cond).order_by(
        MovimientoBancario.fecha, MovimientoBancario.estado_cuenta_id,
        MovimientoBancario.renglon)))


def movimientos_libros(db: Session, cliente: Cliente, cb: CuentaBancaria, desde: date | None,
                       hasta: date | None) -> list[tuple[MovimientoPoliza, Poliza]]:
    cond = [Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
            MovimientoPoliza.cuenta_id == cb.cuenta_contable_id]
    if desde:
        cond.append(Poliza.fecha >= desde)
    if hasta:
        cond.append(Poliza.fecha <= hasta)
    return list(db.execute(select(MovimientoPoliza, Poliza)
                           .join(Poliza, Poliza.id == MovimientoPoliza.poliza_id)
                           .where(*cond).order_by(Poliza.fecha, Poliza.id, MovimientoPoliza.orden)
                           ).all())


def _cfdi_importe(c: Comprobante, cliente: Cliente) -> tuple[date, Decimal] | None:
    signo = Decimal(1) if c.direccion == "emitido" else Decimal(-1)
    if c.tipo == "P":
        pagos = (c.datos or {}).get("pagos") or {}
        if not any((p.get("FormaDePagoP") or "") in FORMAS_BANCO for p in pagos.get("pagos", [])):
            return None
        monto = Decimal(str(pagos.get("monto_total") or "0")).quantize(Decimal("0.01"))
        fp = next((p.get("FechaPago") for p in pagos.get("pagos", []) if p.get("FechaPago")), "")
        f = lectores.fecha(fp[:10]) if fp else None
        return (f or c.fecha.date(), signo * monto) if monto else None
    if c.tipo == "I" and c.metodo_pago == "PUE" and c.forma_pago in FORMAS_BANCO \
            and c.moneda == "MXN":
        return c.fecha.date(), signo * c.total
    return None


def cfdi_sin_poliza(db: Session, cliente: Cliente, desde: date | None,
                    hasta: date | None) -> list[tuple[Comprobante, date, Decimal]]:
    cond = [Comprobante.cliente_id == cliente.id, Comprobante.tipo.in_(("I", "P")),
            Comprobante.estatus_sat != "cancelado"]
    con_poliza = select(Poliza.uuid_cfdi).where(Poliza.cliente_id == cliente.id,
                                                Poliza.estado == "activa",
                                                Poliza.uuid_cfdi.is_not(None))
    cond.append(Comprobante.uuid.not_in(con_poliza))
    salida = []
    for c in db.scalars(select(Comprobante).where(*cond).order_by(Comprobante.fecha)):
        r = _cfdi_importe(c, cliente)
        if r is None:
            continue
        f, imp = r
        if (desde and f < desde) or (hasta and f > hasta):
            continue
        salida.append((c, f, imp))
    return salida


def _partidas(db: Session, cliente: Cliente, cb: CuentaBancaria, desde: date | None,
              hasta: date | None, incluir_cfdi: bool
              ) -> tuple[list[Partida], list[Partida]]:
    banco = [Partida(f"b:{m.id}", m.fecha, m.abono - m.cargo, m.concepto.lower(),
                     m.referencia) for m in movimientos_banco(db, cb, desde, hasta)]
    libros = [Partida(f"p:{m.id}", p.fecha, m.cargo - m.abono,
                      f"{p.concepto} {m.concepto}".lower(), "", m.uuid_cfdi or p.uuid_cfdi or "",
                      m.rfc_tercero) for m, p in movimientos_libros(db, cliente, cb, desde, hasta)]
    if incluir_cfdi:
        for c, f, imp in cfdi_sin_poliza(db, cliente, desde, hasta):
            rfc = c.rfc_receptor if c.direccion == "emitido" else c.rfc_emisor
            libros.append(Partida(f"c:{c.id}", f, imp,
                                  f"{c.serie}{c.folio} {c.nombre_receptor}".lower(),
                                  f"{c.serie}{c.folio}", c.uuid, rfc))
    return banco, libros


def vista(db: Session, cliente: Cliente, cb: CuentaBancaria, desde: date | None,
          hasta: date | None, incluir_cfdi: bool = True) -> dict[str, Any]:
    """Las dos tablas de la pantalla, con su marca de conciliado."""
    conc = _mapa_conciliados(db, cb)
    banco = [{
        "clave": f"b:{m.id}", "id": m.id, "fecha": m.fecha.isoformat(), "concepto": m.concepto,
        "referencia": m.referencia, "cargo": f"{m.cargo:.2f}", "abono": f"{m.abono:.2f}",
        "saldo": f"{m.saldo:.2f}" if m.saldo is not None else None,
        "conciliacion_id": conc.get(f"b:{m.id}"),
    } for m in movimientos_banco(db, cb, desde, hasta)]
    libros = [{
        "clave": f"p:{m.id}", "id": m.id, "origen": "poliza", "poliza_id": p.id,
        "folio": polizas.folio(p), "fecha": p.fecha.isoformat(),
        "concepto": m.concepto or p.concepto, "cargo": f"{m.cargo:.2f}",
        "abono": f"{m.abono:.2f}", "uuid": m.uuid_cfdi, "rfc": m.rfc_tercero,
        "conciliacion_id": conc.get(f"p:{m.id}"),
    } for m, p in movimientos_libros(db, cliente, cb, desde, hasta)]
    if incluir_cfdi:
        for c, f, imp in cfdi_sin_poliza(db, cliente, desde, hasta):
            libros.append({
                "clave": f"c:{c.id}", "id": c.id, "origen": "cfdi", "poliza_id": None,
                "folio": f"{c.tipo} {c.serie}{c.folio}".strip(), "fecha": f.isoformat(),
                "concepto": (c.nombre_receptor if c.direccion == "emitido"
                             else c.nombre_emisor) or c.uuid,
                "cargo": f"{max(imp, CERO):.2f}", "abono": f"{max(-imp, CERO):.2f}",
                "uuid": c.uuid, "rfc": c.rfc_receptor if c.direccion == "emitido"
                else c.rfc_emisor, "conciliacion_id": conc.get(f"c:{c.id}"),
            })
    libros.sort(key=lambda x: (x["fecha"], x["clave"]))
    pend_b = sum(1 for x in banco if x["conciliacion_id"] is None)
    pend_l = sum(1 for x in libros if x["conciliacion_id"] is None)
    return {"cuenta": cuenta_dict(db, cb), "banco": banco, "libros": libros,
            "pendientes_banco": pend_b, "pendientes_libros": pend_l}


# ── conciliar ──


def _guardar(db: Session, cliente: Cliente, cb: CuentaBancaria, banco: list[str],
             libros: list[str], *, tipo: str, puntaje: int, motivo: str,
             uid: str) -> Conciliacion:
    c = Conciliacion(cliente_id=cliente.id, cuenta_bancaria_id=cb.id, tipo=tipo,
                     puntaje=puntaje, motivo=motivo[:300], creado_por=uid)
    db.add(c)
    db.flush()
    for clave in [*banco, *libros]:
        tipo_p, ident = clave.split(":")
        campo = {"b": "movimiento_bancario_id", "p": "movimiento_poliza_id",
                 "c": "comprobante_id"}[tipo_p]
        db.add(PartidaConciliacion(conciliacion_id=c.id, **{campo: int(ident)}))
    db.flush()
    return c


def conciliar_automatico(db: Session, cliente: Cliente, cb: CuentaBancaria, desde: date | None,
                         hasta: date | None, *, incluir_cfdi: bool = True,
                         uid: str = "") -> dict[str, Any]:
    conc = _mapa_conciliados(db, cb)
    banco, libros = _partidas(db, cliente, cb, desde, hasta, incluir_cfdi)
    banco = [b for b in banco if b.clave not in conc]
    libros = [x for x in libros if x.clave not in conc]
    r = emparejador.emparejar(banco, libros, ventana=cb.ventana_dias, umbral=cb.umbral)
    for e in r.emparejados:
        _guardar(db, cliente, cb, e.banco, e.libros, tipo="automatica", puntaje=e.puntaje,
                 motivo=e.motivo, uid=uid)
    return {"conciliados": len(r.emparejados),
            "uno_a_varios": sum(1 for e in r.emparejados
                                if len(e.banco) > 1 or len(e.libros) > 1),
            "ambiguos": r.ambiguos,
            "pendientes_banco": len(banco) - sum(len(e.banco) for e in r.emparejados),
            "pendientes_libros": len(libros) - sum(len(e.libros) for e in r.emparejados)}


def _importe_de(db: Session, cliente: Cliente, cb: CuentaBancaria, clave: str) -> Decimal:
    tipo, ident = clave.split(":") if ":" in clave else ("", "")
    if not ident.isdigit():
        raise FiscalAgentError(f"Partida inválida: {clave}.", 422)
    i = int(ident)
    if tipo == "b":
        m = db.scalar(select(MovimientoBancario).where(
            MovimientoBancario.id == i, MovimientoBancario.cuenta_bancaria_id == cb.id))
        if m is None:
            raise FiscalAgentError("Un movimiento del banco no es de esta cuenta.", 404)
        return m.abono - m.cargo
    if tipo == "p":
        fila = db.execute(select(MovimientoPoliza, Poliza)
                          .join(Poliza, Poliza.id == MovimientoPoliza.poliza_id)
                          .where(MovimientoPoliza.id == i, Poliza.cliente_id == cliente.id,
                                 MovimientoPoliza.cuenta_id == cb.cuenta_contable_id)).first()
        if fila is None:
            raise FiscalAgentError("Un movimiento de póliza no es de la cuenta de bancos "
                                   "ligada a esta cuenta bancaria.", 404)
        if fila[1].estado != "activa":
            raise FiscalAgentError("No se concilia contra una póliza cancelada.", 409)
        return fila[0].cargo - fila[0].abono
    if tipo == "c":
        c = db.scalar(select(Comprobante).where(Comprobante.id == i,
                                                Comprobante.cliente_id == cliente.id))
        r = _cfdi_importe(c, cliente) if c else None
        if r is None:
            raise FiscalAgentError("Ese CFDI no mueve bancos o no es de este cliente.", 404)
        return r[1]
    raise FiscalAgentError(f"Partida inválida: {clave}.", 422)


def conciliar_manual(db: Session, cliente: Cliente, cb: CuentaBancaria, banco: list[str],
                     libros: list[str], motivo: str, uid: str) -> Conciliacion:
    """Concilia lo seleccionado en las dos tablas. Las sumas deben ser iguales."""
    if not banco or not libros:
        raise FiscalAgentError("Selecciona al menos un movimiento de cada lado.", 422)
    if any(not b.startswith("b:") for b in banco) or any(x.startswith("b:") for x in libros):
        raise FiscalAgentError("Del lado del banco van movimientos del estado de cuenta; del "
                               "otro, pólizas o CFDI.", 422)
    if len(set(banco + libros)) != len(banco + libros):
        raise FiscalAgentError("Una partida viene repetida.", 422)
    conc = _mapa_conciliados(db, cb)
    ya = [k for k in banco + libros if k in conc]
    if ya:
        raise FiscalAgentError(f"Ya están conciliadas: {', '.join(ya)}. Deshaz primero.", 409)
    suma_b = sum((_importe_de(db, cliente, cb, k) for k in banco), CERO)
    suma_l = sum((_importe_de(db, cliente, cb, k) for k in libros), CERO)
    if suma_b != suma_l:
        raise FiscalAgentError(
            f"No cuadra: banco {suma_b:.2f} vs libros {suma_l:.2f} "
            f"(diferencia {suma_b - suma_l:.2f}).", 422)
    return _guardar(db, cliente, cb, banco, libros, tipo="manual", puntaje=100,
                    motivo=motivo or "Conciliación manual", uid=uid)


def deshacer(db: Session, cliente: Cliente, cb: CuentaBancaria, conciliacion_id: int) -> None:
    c = db.scalar(select(Conciliacion).where(Conciliacion.id == conciliacion_id,
                                             Conciliacion.cliente_id == cliente.id,
                                             Conciliacion.cuenta_bancaria_id == cb.id))
    if c is None:
        raise FiscalAgentError("No existe esa conciliación en esta cuenta.", 404)
    db.delete(c)
    db.flush()


# ── póliza desde un movimiento del banco ──


def sugerir_cuenta(db: Session, cliente: Cliente, mov: MovimientoBancario) -> dict[str, Any] | None:
    """Cuenta sugerida para la contrapartida (comisiones, intereses, IVA, ISR retenido)."""
    texto = lectores.normalizar(mov.concepto)
    lado = "abono" if mov.abono > 0 else "cargo"
    codigo = next((cod for palabras, l_, cod in SUGERENCIAS
                   if (l_ in ("ambos", lado)) and any(p in texto for p in palabras)), None)
    if codigo is None:
        codigo = "704.23" if lado == "abono" else "701.11"
    cuenta = db.scalar(select(CuentaContable).where(
        CuentaContable.cliente_id == cliente.id, CuentaContable.afectable,
        CuentaContable.codigo_agrupador == codigo).order_by(CuentaContable.numero))
    if cuenta is None:
        return None
    return {"cuenta_id": cuenta.id, "numero": cuenta.numero, "nombre": cuenta.nombre}


def crear_poliza(db: Session, cliente: Cliente, cb: CuentaBancaria, movimiento_id: int,
                 contrapartidas: list[tuple[int, Decimal]], concepto: str,
                 uid: str) -> tuple[Poliza, Conciliacion]:
    """
    Póliza para un movimiento del banco sin CFDI (comisión, intereses…), y la concilia.

    `contrapartidas`: (cuenta_id, importe) — la suma debe ser el importe del movimiento (p. ej.
    comisión 100 + IVA 16 contra un cargo de 116).
    """
    mov = db.scalar(select(MovimientoBancario).where(
        MovimientoBancario.id == movimiento_id, MovimientoBancario.cuenta_bancaria_id == cb.id))
    if mov is None:
        raise FiscalAgentError("No existe ese movimiento en esta cuenta bancaria.", 404)
    if f"b:{mov.id}" in _mapa_conciliados(db, cb):
        raise FiscalAgentError("Ese movimiento ya está conciliado.", 409)
    entra = mov.abono > 0
    total = mov.abono if entra else mov.cargo
    if not contrapartidas:
        raise FiscalAgentError("Indica la cuenta de la contrapartida.", 422)
    if sum((i for _c, i in contrapartidas), CERO) != total:
        raise FiscalAgentError(f"Las contrapartidas deben sumar {total:.2f}.", 422)
    texto = (concepto or mov.concepto or "Movimiento bancario")[:300]
    movs = [polizas.MovimientoEntrada(cb.cuenta_contable_id, total if entra else CERO,
                                      CERO if entra else total, texto)]
    movs += [polizas.MovimientoEntrada(cid, CERO if entra else imp, imp if entra else CERO,
                                       texto) for cid, imp in contrapartidas]
    p = polizas.crear_manual(db, cliente, tipo="ingreso" if entra else "egreso",
                             fecha=mov.fecha, concepto=texto, movimientos=movs, uid=uid)
    banco_mov = db.scalar(select(MovimientoPoliza).where(
        MovimientoPoliza.poliza_id == p.id, MovimientoPoliza.cuenta_id == cb.cuenta_contable_id)
        .order_by(MovimientoPoliza.orden))
    assert banco_mov is not None
    c = _guardar(db, cliente, cb, [f"b:{mov.id}"], [f"p:{banco_mov.id}"], tipo="poliza",
                 puntaje=100, motivo=f"Póliza {polizas.folio(p)} creada desde el banco", uid=uid)
    return p, c
