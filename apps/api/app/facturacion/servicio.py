"""
Emisión, consulta y cancelación de CFDI 4.0 de ingreso, egreso y pago (P5-04).

FLUJO DE UNA EMISIÓN (síncrona, como el CFDI de retenciones de P3-04)
---------------------------------------------------------------------
1. Emisor = el cliente de la URL (su RFC, régimen y CP de la cartera). Receptor capturado o
   tomado de otro cliente del despacho (`receptor_clave`).
2. `calculo.comprobante` / `calculo.pago`: importes e impuestos (motor determinístico).
3. `armado.factura` / `armado.pago` → XML sin sellar.
4. Sellado con el CSD del emisor (`obtener_firmante(db, cliente, "csd")`) sobre la cadena
   original del XSLT oficial (`nomina_cfdi.servicio.sellar`, Anexo 20).
5. Validación contra cfdv40 + Pagos20 + TFD: si no valida NO se manda al PAC.
6. `pac.timbrar` (FISCALITO_PAC; el falso devuelve un TFD sintético marcado NO FISCAL) y se
   vuelve a validar lo que devolvió.
7. El XML timbrado entra a la bóveda del emisor (origen `emision`) y, si el receptor es otro
   cliente del despacho, a la suya como recibido. Si ampara un cargo de cobranza (P5-03),
   el cargo guarda el UUID.

LAS FACTURAS DEL PROPIO DESPACHO
--------------------------------
El despacho factura sus honorarios como un cliente más de su cartera (con su RFC y su CSD),
marcado en `ConfigFacturacion.cliente_propio_id` — la misma idea que P5-03 ya pedía para ligar
pagos ("da de alta al despacho como cliente propio"). Sólo dueño y contador emiten o cancelan
a nombre del despacho (son sus honorarios: `ROLES_COBRANZA`).

DECISIONES PROVISIONALES
------------------------
- Borrador desde un cargo: la iguala capturada en cobranza es ANTES de IVA ("$5,000 + IVA"),
  método PPD con forma 99 (se factura antes de cobrar); retenciones de IVA 2/3 e ISR 10 % si el
  despacho es persona física y el cliente persona moral (Art. 1o.-A LIVA, Art. 106 LISR), o
  IVA 2/3 e ISR 1.25 % si el despacho tributa en RESICO (Art. 113-J LISR). Es un borrador: se edita.
- Egreso: exige PUE y al menos un CFDI relacionado (por defecto TipoRelacion 01).
- Cancelación con motivo 01: el folio sustituto debe ser una factura vigente del mismo emisor
  que relacione a ésta con TipoRelacion 04.
- Una factura con complementos de pago vigentes no se cancela: primero se cancelan los pagos.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.boveda_cfdi import servicio as boveda
from app.cobranza.servicio import ROLES_COBRANZA
from app.credenciales.servicio import obtener_firmante
from app.exceptions import FiscalAgentError
from app.facturacion import armado, calculo, catalogos, esquemas
from app.integraciones.almacenamiento import obtener_almacenamiento
from app.integraciones.pac import Pac, obtener_pac
from app.modelos.cfdi import Comprobante
from app.modelos.cobranza import CargoCobranza
from app.modelos.facturacion import ConfigFacturacion, DocumentoPagoFactura, Factura, FolioFactura
from app.modelos.nucleo import Cliente
from app.nomina_cfdi.servicio import sellar
from app.tenancy import Contexto, cliente_o_404, exigir_rol

ZONA = ZoneInfo("America/Mexico_City")
SERIE = {"I": "F", "E": "NC", "P": "P"}
VIGENTES = ("timbrado", "cancelacion_en_proceso")
UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                     r"[0-9A-Fa-f]{12}$")
CERO = Decimal("0.00")


def _error(msg: str, status: int = 422) -> FiscalAgentError:
    return FiscalAgentError(msg, status)


# ── configuración: el cliente que ES el despacho ──


def config_de(db: Session, despacho_id: str) -> ConfigFacturacion | None:
    return db.get(ConfigFacturacion, despacho_id)


def es_propio(db: Session, cliente: Cliente) -> bool:
    cfg = config_de(db, cliente.despacho_id)
    return cfg is not None and cfg.cliente_propio_id == cliente.id


def guardar_config(ctx: Contexto, clave: str | None) -> ConfigFacturacion:
    exigir_rol(ctx, *ROLES_COBRANZA)
    cfg = config_de(ctx.db, ctx.despacho_id)
    if cfg is None:
        cfg = ConfigFacturacion(despacho_id=ctx.despacho_id)
        ctx.db.add(cfg)
    cfg.cliente_propio_id = cliente_o_404(ctx, clave).id if clave else None
    ctx.db.flush()
    registrar(ctx, "facturacion.config", "config_facturacion", ctx.despacho_id,
              {"cliente_propio": clave or ""})
    return cfg


def clave_propio(ctx: Contexto) -> str | None:
    cfg = config_de(ctx.db, ctx.despacho_id)
    if cfg is None or cfg.cliente_propio_id is None:
        return None
    c = ctx.db.get(Cliente, cfg.cliente_propio_id)
    return c.clave if c is not None else None


def _exigir_si_propio(ctx: Contexto, cliente: Cliente) -> None:
    if es_propio(ctx.db, cliente):
        exigir_rol(ctx, *ROLES_COBRANZA)


# ── entradas ──


@dataclass
class ReceptorEntrada:
    rfc: str = ""
    nombre: str = ""
    regimen: str = ""
    codigo_postal: str = ""
    uso_cfdi: str = "G03"
    clave_cliente: str | None = None  # otro cliente del despacho


@dataclass
class EntradaFactura:
    tipo: str
    receptor: ReceptorEntrada
    conceptos: list[calculo.ConceptoEntrada]
    forma_pago: str
    metodo_pago: str
    serie: str | None = None
    condiciones_pago: str = ""
    relacionados: list[armado.Relacion] = field(default_factory=list)
    cargo_id: int | None = None


@dataclass
class PagoDocEntrada:
    factura_id: int
    importe_pagado: Decimal


@dataclass
class EntradaPago:
    fecha_pago: datetime
    forma_pago: str
    documentos: list[PagoDocEntrada]
    num_operacion: str = ""
    serie: str | None = None
    relacionados: list[armado.Relacion] = field(default_factory=list)


# ── piezas comunes ──


def emisor_de(cliente: Cliente) -> tuple[armado.Emisor, str]:
    datos = cliente.datos or {}
    rfc, regimen, cp = boveda.rfc_del_cliente(cliente), str(datos.get("regimen") or ""), str(
        datos.get("codigo_postal") or "")
    falta = [n for n, v in (("RFC del emisor", rfc), ("régimen del emisor", regimen),
                            ("código postal del emisor", cp)) if not v]
    if falta:
        raise _error("Falta capturar en la ficha: " + ", ".join(falta) + ".")
    if regimen not in catalogos.REGIMEN_FISCAL:
        raise _error(f"Régimen del emisor {regimen} fuera del catálogo c_RegimenFiscal.")
    return armado.Emisor(rfc, (cliente.nombre or "").upper(), regimen), cp


def _receptor(ctx: Contexto, emisor: Cliente, r: ReceptorEntrada,
              uso: str) -> tuple[armado.Receptor, Cliente | None]:
    otro = None
    if r.clave_cliente:
        otro = cliente_o_404(ctx, r.clave_cliente)
        if otro.id == emisor.id:
            raise _error("El receptor no puede ser el mismo emisor.")
        d = otro.datos or {}
        r = ReceptorEntrada(rfc=r.rfc or boveda.rfc_del_cliente(otro),
                            nombre=r.nombre or otro.nombre or "",
                            regimen=r.regimen or str(d.get("regimen") or ""),
                            codigo_postal=r.codigo_postal or str(d.get("codigo_postal") or ""),
                            uso_cfdi=r.uso_cfdi, clave_cliente=r.clave_cliente)
    falta = [n for n, v in (("RFC del receptor", r.rfc), ("nombre del receptor", r.nombre),
                            ("régimen del receptor", r.regimen),
                            ("código postal del receptor", r.codigo_postal)) if not v]
    if falta:
        raise _error("Falta: " + ", ".join(falta) + ".")
    if r.regimen not in catalogos.REGIMEN_FISCAL:
        raise _error(f"Régimen del receptor {r.regimen} fuera del catálogo.")
    if uso not in catalogos.USO_CFDI:
        raise _error(f"UsoCFDI {uso} fuera del catálogo.")
    return armado.Receptor(r.rfc.strip().upper(), r.nombre.strip().upper(), r.regimen,
                           r.codigo_postal, uso), otro


def _validar_relacionados(rels: list[armado.Relacion]) -> None:
    for rel in rels:
        if rel.tipo_relacion not in catalogos.TIPO_RELACION:
            raise _error(f"TipoRelacion {rel.tipo_relacion} fuera del catálogo.")
        if not rel.uuids or any(not UUID_RE.match(u) for u in rel.uuids):
            raise _error("Cada CFDI relacionado debe ser un UUID válido.")


def siguiente_folio(db: Session, cliente: Cliente, serie: str) -> str:
    fila = db.scalar(select(FolioFactura).where(
        FolioFactura.cliente_id == cliente.id, FolioFactura.serie == serie).with_for_update())
    if fila is None:
        fila = FolioFactura(cliente_id=cliente.id, serie=serie, siguiente=1)
        db.add(fila)
    folio = fila.siguiente
    fila.siguiente = folio + 1
    db.flush()
    return str(folio)


def _ahora() -> datetime:
    return datetime.now(ZONA).replace(tzinfo=None, microsecond=0)


def _timbrar(db: Session, cliente: Cliente, doc: Any, pac: Pac) -> tuple[bytes, Any]:
    xml, _ = sellar(armado.a_bytes(doc), obtener_firmante(db, cliente, "csd"))
    errores = esquemas.validar(esquemas.parsear(xml))
    if errores:
        raise _error("El CFDI no valida contra el XSD del SAT: " + "; ".join(errores[:5]))
    timbre = pac.timbrar(xml, "cfdi")
    errores = esquemas.validar(esquemas.parsear(timbre.xml_timbrado))
    if errores:
        raise _error("El PAC devolvió un XML que no valida: " + "; ".join(errores[:5]), 502)
    return xml, timbre


def _guardar(db: Session, emisor: Cliente, receptor: Cliente | None, timbre: Any,
             rfc_emisor: str, rfc_receptor: str) -> str:
    almacen = obtener_almacenamiento()
    nombre = f"emision-{timbre.uuid}.xml"
    boveda.importar(db, emisor, [(nombre, io.BytesIO(timbre.xml_timbrado))], almacen,
                    origen="emision", rfc=rfc_emisor, detalle=False)
    if receptor is not None:
        boveda.importar(db, receptor, [(nombre, io.BytesIO(timbre.xml_timbrado))], almacen,
                        origen="emision", rfc=rfc_receptor, detalle=False)
    return boveda.ruta_del_xml(emisor, timbre.uuid)


def _fila(ctx: Contexto, cliente: Cliente, tipo: str, serie: str, folio: str, timbre: Any,
          receptor: armado.Receptor, otro: Cliente | None, ruta: str, pac: Pac,
          fecha: datetime, **campos: Any) -> Factura:
    fecha_t = timbre.fecha if timbre.fecha.tzinfo else timbre.fecha.replace(tzinfo=ZONA)
    f = Factura(
        despacho_id=ctx.despacho_id, cliente_id=cliente.id,
        cliente_receptor_id=otro.id if otro else None, tipo=tipo, serie=serie, folio=folio,
        uuid=timbre.uuid, rfc_receptor=receptor.rfc, nombre_receptor=receptor.nombre,
        uso_cfdi=receptor.uso_cfdi, estado="timbrado", pac=getattr(pac, "nombre", ""),
        es_prueba=getattr(pac, "nombre", "") == "falso",
        fecha_emision=fecha.replace(tzinfo=ZONA), fecha_timbrado=fecha_t, ruta_xml=ruta,
        sha256=hashlib.sha256(timbre.xml_timbrado).hexdigest(), creado_por=ctx.uid, **campos)
    ctx.db.add(f)
    ctx.db.flush()
    return f


# ── ingreso y egreso ──


def _cargo(ctx: Contexto, emisor: Cliente, cargo_id: int, otro: Cliente | None,
           rels: list[armado.Relacion]) -> CargoCobranza:
    if not es_propio(ctx.db, emisor):
        raise _error("Sólo las facturas del propio despacho se ligan a un cargo de cobranza.")
    cargo = ctx.db.get(CargoCobranza, cargo_id)
    if cargo is None or cargo.despacho_id != ctx.despacho_id:
        raise _error("No existe ese cargo.", 404)
    if otro is None or cargo.cliente_id != otro.id:
        raise _error("El receptor de la factura debe ser el cliente del cargo.")
    if cargo.cancelado:
        raise _error("El cargo está cancelado.", 409)
    sustituidos = {u.upper() for r in rels if r.tipo_relacion == "04" for u in r.uuids}
    if cargo.uuid_cfdi and cargo.uuid_cfdi.upper() not in sustituidos:
        raise _error("Ese cargo ya está facturado; para refacturarlo relaciona la factura "
                     "anterior con TipoRelacion 04 (sustitución).", 409)
    return cargo


def emitir_factura(ctx: Contexto, cliente: Cliente, e: EntradaFactura,
                   pac: Pac | None = None) -> Factura:
    """Arma, sella, valida, timbra y guarda un CFDI de ingreso o egreso."""
    _exigir_si_propio(ctx, cliente)
    if e.tipo not in ("I", "E"):
        raise _error("Tipo de comprobante: I (ingreso) o E (egreso).")
    if e.forma_pago not in catalogos.FORMA_PAGO or e.metodo_pago not in catalogos.METODO_PAGO:
        raise _error("Forma o método de pago fuera del catálogo.")
    if e.metodo_pago == "PPD" and e.forma_pago != "99":
        raise _error("Con método PPD la forma de pago es 99 (Por definir).")
    if e.metodo_pago == "PUE" and e.forma_pago == "99":
        raise _error("Con método PUE captura la forma de pago real (no 99).")
    if e.tipo == "E":
        if e.metodo_pago != "PUE":
            raise _error("Un egreso (nota de crédito) se emite con método PUE.")
        if not e.relacionados:
            raise _error("Un egreso debe relacionar el CFDI que acredita (TipoRelacion 01).")
    _validar_relacionados(e.relacionados)
    emisor, cp = emisor_de(cliente)
    receptor, otro = _receptor(ctx, cliente, e.receptor, e.receptor.uso_cfdi)
    cargo = _cargo(ctx, cliente, e.cargo_id, otro, e.relacionados) if e.cargo_id else None
    comp = calculo.comprobante(e.conceptos)
    serie = (e.serie or SERIE[e.tipo]).strip()[:25]
    folio = siguiente_folio(ctx.db, cliente, serie)
    fecha = _ahora()
    enc = armado.Encabezado(serie, folio, fecha, cp, emisor, receptor, e.relacionados)
    doc = armado.factura(armado.DatosFactura(e.tipo, enc, e.forma_pago, e.metodo_pago, comp,
                                             e.condiciones_pago))
    pac = pac or obtener_pac()
    _, timbre = _timbrar(ctx.db, cliente, doc, pac)
    ruta = _guardar(ctx.db, cliente, otro, timbre, emisor.rfc, receptor.rfc)
    f = _fila(ctx, cliente, e.tipo, serie, folio, timbre, receptor, otro, ruta, pac, fecha,
              cargo_id=cargo.id if cargo else None, metodo_pago=e.metodo_pago,
              forma_pago=e.forma_pago, subtotal=comp.subtotal, descuento=comp.descuento,
              traslados=comp.total_traslados or CERO,
              retenciones=comp.total_retenciones or CERO, total=comp.total,
              datos={"traslados": [t.a_dict() for t in comp.traslados],
                     "retenciones": [r.a_dict() for r in comp.retenciones_detalle],
                     "relacionados": [{"tipo_relacion": r.tipo_relacion, "uuids": list(r.uuids)}
                                      for r in e.relacionados]})
    if cargo is not None:
        cargo.uuid_cfdi, cargo.facturar = f.uuid, True
    registrar(ctx, "facturacion.emitir", "factura", f.id,
              {"tipo": f.tipo, "uuid": f.uuid, "total": str(f.total), "receptor": f.rfc_receptor},
              cliente)
    ctx.db.flush()
    return f


# ── pagos ──


def pagado_de(db: Session, factura: Factura) -> tuple[Decimal, int]:
    """(importe ya pagado, número de parcialidades) por complementos NO cancelados."""
    fila = db.execute(
        select(func.coalesce(func.sum(DocumentoPagoFactura.importe_pagado), 0),
               func.count(DocumentoPagoFactura.id))
        .join(Factura, Factura.id == DocumentoPagoFactura.pago_id)
        .where(DocumentoPagoFactura.factura_id == factura.id, Factura.estado != "cancelado")
    ).one()
    return Decimal(fila[0]).quantize(Decimal("0.01")), int(fila[1])


def saldo_de(db: Session, factura: Factura) -> Decimal | None:
    if factura.tipo != "I" or factura.metodo_pago != "PPD":
        return None
    return factura.total - pagado_de(db, factura)[0]


def _impuestos(lista: list[dict[str, Any]]) -> tuple[calculo.ImpuestoCalculado, ...]:
    return tuple(calculo.ImpuestoCalculado(
        i["tipo"], i["impuesto"], i["tipo_factor"],
        Decimal(i["tasa"]) if i.get("tasa") is not None else None, Decimal(i["base"]),
        Decimal(i["importe"]) if i.get("importe") is not None else None) for i in lista)


def emitir_pago(ctx: Contexto, cliente: Cliente, e: EntradaPago,
                pac: Pac | None = None) -> Factura:
    """CFDI de pago (complemento 2.0) para facturas PPD emitidas aquí por el mismo emisor."""
    _exigir_si_propio(ctx, cliente)
    if e.forma_pago not in catalogos.FORMA_PAGO or e.forma_pago == "99":
        raise _error("Forma de pago fuera del catálogo (no puede ser 99 en un pago).")
    _validar_relacionados(e.relacionados)
    emisor, cp = emisor_de(cliente)
    docs: list[calculo.DocumentoPagado] = []
    facturas: list[Factura] = []
    for d in e.documentos:
        # Bloquea la factura: dos pagos simultáneos no deben pasarse del saldo (revisor P5).
        f = ctx.db.get(Factura, d.factura_id, with_for_update=True)
        if f is None or f.cliente_id != cliente.id:
            raise _error(f"No existe la factura {d.factura_id} de este emisor.", 404)
        if f.tipo != "I" or f.metodo_pago != "PPD" or f.estado not in VIGENTES:
            raise _error(f"La factura {f.serie}-{f.folio} no es un ingreso PPD vigente.")
        pagado, n = pagado_de(ctx.db, f)
        docs.append(calculo.DocumentoPagado(
            f.uuid, f.serie, f.folio, f.total, f.total - pagado, n + 1, d.importe_pagado,
            _impuestos(f.datos.get("traslados", [])), _impuestos(f.datos.get("retenciones", []))))
        facturas.append(f)
    if len({(f.rfc_receptor, f.cliente_receptor_id) for f in facturas}) > 1:
        raise _error("Todas las facturas de un pago deben ser del mismo receptor.")
    p = calculo.pago(docs)
    base = facturas[0]
    otro = ctx.db.get(Cliente, base.cliente_receptor_id) if base.cliente_receptor_id else None
    xml_base = esquemas.parsear(obtener_almacenamiento().leer(base.ruta_xml))
    rec = xml_base.find(f"{{{esquemas.NS_CFDI}}}Receptor")
    receptor = armado.Receptor(base.rfc_receptor, base.nombre_receptor,
                               rec.get("RegimenFiscalReceptor", ""),
                               rec.get("DomicilioFiscalReceptor", ""), "CP01")
    serie = (e.serie or SERIE["P"]).strip()[:25]
    folio = siguiente_folio(ctx.db, cliente, serie)
    fecha = _ahora()
    enc = armado.Encabezado(serie, folio, fecha, cp, emisor, receptor, e.relacionados)
    doc = armado.pago(armado.DatosPago(enc, e.fecha_pago, e.forma_pago, p, e.num_operacion))
    pac = pac or obtener_pac()
    _, timbre = _timbrar(ctx.db, cliente, doc, pac)
    ruta = _guardar(ctx.db, cliente, otro, timbre, emisor.rfc, receptor.rfc)
    f = _fila(ctx, cliente, "P", serie, folio, timbre, receptor, otro, ruta, pac, fecha,
              forma_pago=e.forma_pago, total=p.monto,
              datos={"fecha_pago": e.fecha_pago.isoformat(), "totales":
                     {k: str(v) for k, v in p.totales.items()}})
    for dc in p.documentos:
        ctx.db.add(DocumentoPagoFactura(
            pago_id=f.id, factura_id=next(x.id for x in facturas if x.uuid == dc.doc.uuid),
            num_parcialidad=dc.doc.num_parcialidad, saldo_anterior=dc.doc.saldo_anterior,
            importe_pagado=dc.doc.importe_pagado, saldo_insoluto=dc.saldo_insoluto))
    registrar(ctx, "facturacion.pago", "factura", f.id,
              {"uuid": f.uuid, "monto": str(p.monto), "facturas": [x.uuid for x in facturas]},
              cliente)
    ctx.db.flush()
    return f


# ── consulta y cancelación ──


def obtener(db: Session, cliente: Cliente, factura_id: int) -> Factura:
    f = db.get(Factura, factura_id)
    if f is None or f.cliente_id != cliente.id:
        raise _error("No existe esa factura en este cliente.", 404)
    return f


def listar(db: Session, cliente: Cliente, tipo: str | None = None) -> list[Factura]:
    q = select(Factura).where(Factura.cliente_id == cliente.id)
    if tipo:
        q = q.where(Factura.tipo == tipo)
    return list(db.scalars(q.order_by(Factura.fecha_emision.desc(), Factura.id.desc())))


def leer_xml(f: Factura) -> bytes:
    return obtener_almacenamiento().leer(f.ruta_xml)


def cancelar(ctx: Contexto, cliente: Cliente, factura_id: int, motivo: str,
             folio_sustitucion: str | None, pac: Pac | None = None) -> Factura:
    """Cancela con el PAC (motivos 01-04), guarda el acuse y marca la bóveda y el cargo."""
    _exigir_si_propio(ctx, cliente)
    f = obtener(ctx.db, cliente, factura_id)
    if f.estado not in VIGENTES:
        raise _error("Esa factura ya está cancelada.", 409)
    if motivo not in catalogos.MOTIVO_CANCELACION:
        raise _error("Motivo de cancelación: 01, 02, 03 o 04.")
    sustituta = None
    if motivo == "01":
        if not folio_sustitucion or not UUID_RE.match(folio_sustitucion):
            raise _error("El motivo 01 exige el UUID de la factura que la sustituye.")
        sustituta = ctx.db.scalar(select(Factura).where(
            Factura.cliente_id == cliente.id, Factura.uuid == folio_sustitucion.upper(),
            Factura.estado.in_(VIGENTES)))
        relaciona = sustituta is not None and any(
            r["tipo_relacion"] == "04" and f.uuid in [u.upper() for u in r["uuids"]]
            for r in (sustituta.datos or {}).get("relacionados", []))
        if not relaciona:
            raise _error("La factura sustituta debe ser vigente, del mismo emisor y relacionar "
                         "a ésta con TipoRelacion 04.")
    elif folio_sustitucion:
        raise _error("Sólo el motivo 01 lleva folio de sustitución.")
    if f.tipo == "I" and pagado_de(ctx.db, f)[1]:
        raise _error("La factura tiene complementos de pago vigentes: cancélalos primero.", 409)
    pac = pac or obtener_pac()
    firmante = obtener_firmante(ctx.db, cliente, "csd") if pac.nombre == "finkok" else None
    try:
        acuse = pac.cancelar(f.uuid, boveda.rfc_del_cliente(cliente), motivo,
                             folio_sustitucion.upper() if folio_sustitucion else None,
                             tipo="cfdi", firmante=firmante)
    except ValueError as exc:
        raise _error(str(exc)) from exc
    if acuse.estatus == "rechazado":
        raise _error(f"El PAC rechazó la cancelación: {acuse.codigo} {acuse.mensaje}")
    if acuse.acuse_xml:
        f.ruta_acuse = obtener_almacenamiento().guardar(
            acuse.acuse_xml, f"facturas/{cliente.despacho_id}/{cliente.id}/{f.uuid}-acuse.xml")
    f.estado = "cancelado" if acuse.estatus == "cancelado" else "cancelacion_en_proceso"
    f.motivo_cancelacion, f.folio_sustitucion = motivo, (folio_sustitucion or "").upper()
    if f.estado == "cancelado":
        ids = [cliente.id] + ([f.cliente_receptor_id] if f.cliente_receptor_id else [])
        ctx.db.execute(update(Comprobante).where(
            Comprobante.cliente_id.in_(ids), Comprobante.uuid == f.uuid,
        ).values(estatus_sat="cancelado"))
        if f.cargo_id:
            cargo = ctx.db.get(CargoCobranza, f.cargo_id)
            if cargo is not None and (cargo.uuid_cfdi or "").upper() == f.uuid:
                nuevo = sustituta.uuid if sustituta is not None and \
                    sustituta.cargo_id == cargo.id else None
                cargo.uuid_cfdi = nuevo
    registrar(ctx, "facturacion.cancelar", "factura", f.id,
              {"uuid": f.uuid, "motivo": motivo, "sustituta": f.folio_sustitucion}, cliente)
    ctx.db.flush()
    return f


def factura_json(db: Session, f: Factura) -> dict[str, Any]:
    saldo = saldo_de(db, f)
    return {
        "id": f.id, "tipo": f.tipo, "serie": f.serie, "folio": f.folio, "uuid": f.uuid,
        "rfc_receptor": f.rfc_receptor, "nombre_receptor": f.nombre_receptor,
        "metodo_pago": f.metodo_pago, "forma_pago": f.forma_pago, "uso_cfdi": f.uso_cfdi,
        "subtotal": str(f.subtotal), "descuento": str(f.descuento),
        "traslados": str(f.traslados), "retenciones": str(f.retenciones), "total": str(f.total),
        "saldo": str(saldo) if saldo is not None else None, "estado": f.estado, "pac": f.pac,
        "es_prueba": f.es_prueba, "fecha_emision": f.fecha_emision.isoformat(),
        "fecha_timbrado": f.fecha_timbrado.isoformat(), "cargo_id": f.cargo_id,
        "motivo_cancelacion": f.motivo_cancelacion, "folio_sustitucion": f.folio_sustitucion,
        "relacionados": (f.datos or {}).get("relacionados", []),
    }


# ── borrador desde un cargo de cobranza (P5-03) ──


def borrador_de_cargo(ctx: Contexto, cargo_id: int) -> dict[str, Any]:
    """La factura sugerida para un cargo: emisor = el despacho, receptor = su cliente."""
    exigir_rol(ctx, *ROLES_COBRANZA)
    propio = clave_propio(ctx)
    if propio is None:
        raise _error("Primero marca qué cliente de la cartera es el propio despacho.", 409)
    cargo = ctx.db.get(CargoCobranza, cargo_id)
    if cargo is None or cargo.despacho_id != ctx.despacho_id:
        raise _error("No existe ese cargo.", 404)
    receptor = ctx.db.get(Cliente, cargo.cliente_id)
    emisor = cliente_o_404(ctx, propio)
    assert receptor is not None
    rfc_e, rfc_r = boveda.rfc_del_cliente(emisor), boveda.rfc_del_cliente(receptor)
    regimen_e = str((emisor.datos or {}).get("regimen") or "")
    impuestos: list[dict[str, Any]] = [
        {"tipo": "traslado", "impuesto": "002", "tipo_factor": "Tasa", "tasa": "0.160000"}]
    if len(rfc_e) == 13 and len(rfc_r) == 12:
        if regimen_e == "626":
            # RESICO no quita la retención de IVA de 2/3 (Art. 1o.-A fr. II inciso a LIVA y
            # Art. 3o. fr. I RLIVA); sólo cambia la de ISR a 1.25 % (Art. 113-J LISR).
            impuestos += [
                {"tipo": "retencion", "impuesto": "002", "tipo_factor": "Tasa",
                 "tasa": str(catalogos.TASA_RET_IVA_DOS_TERCIOS)},
                {"tipo": "retencion", "impuesto": "001", "tipo_factor": "Tasa",
                 "tasa": str(catalogos.TASA_RET_ISR_RESICO)}]
        else:
            impuestos += [
                {"tipo": "retencion", "impuesto": "002", "tipo_factor": "Tasa",
                 "tasa": str(catalogos.TASA_RET_IVA_DOS_TERCIOS)},
                {"tipo": "retencion", "impuesto": "001", "tipo_factor": "Tasa",
                 "tasa": str(catalogos.TASA_RET_ISR_HONORARIOS)}]
    return {
        "emisor": propio, "cargo_id": cargo.id, "tipo": "I", "forma_pago": "99",
        "metodo_pago": "PPD", "receptor": {"clave_cliente": receptor.clave, "uso_cfdi": "G03"},
        "conceptos": [{"clave_prod_serv": "84111500", "cantidad": "1", "clave_unidad": "E48",
                       "descripcion": cargo.concepto, "valor_unitario": str(cargo.importe),
                       "objeto_imp": "02", "impuestos": impuestos}],
        "relacionados": ([{"tipo_relacion": "04", "uuids": [cargo.uuid_cfdi]}]
                         if cargo.uuid_cfdi else []),
    }
