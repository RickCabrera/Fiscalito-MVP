"""
Qué documentos del cliente se pueden enviar y sus archivos (P5-05).

No genera nada nuevo: cada tipo sale del módulo que ya lo produce.

| tipo            | origen                                              | archivos      |
|-----------------|-----------------------------------------------------|---------------|
| factura         | `facturas` (P5-04): emitidas por el cliente o del    | XML + PDF     |
|                 | despacho al cliente (`cliente_receptor_id`)          |               |
| cfdi            | bóveda (`comprobantes`, P0-03)                       | XML           |
| retencion       | `cfdi_retenciones` (P3-04), constancia               | XML + PDF     |
| opinion         | `documentos_cumplimiento` (P1-05)                    | PDF           |
| constancia      | `documentos_cumplimiento` (constancia de situación)  | PDF           |
| declaracion /   | `documentos_cliente` (subidos aquí)                  | el archivo    |
| acuse / otro    |                                                      |               |
| recibo_nomina   | `nomina_cfdi` timbrado (P4-11)                       | XML + PDF     |

Toda búsqueda filtra por el cliente: un `ref` de otro cliente es 404.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.facturacion import pdf as pdf_factura
from app.integraciones.almacenamiento import obtener_almacenamiento
from app.modelos.cfdi import Comprobante
from app.modelos.envio_documentos import DocumentoCliente
from app.modelos.facturacion import Factura
from app.modelos.imss import CfdiNomina
from app.modelos.nucleo import Cliente
from app.modelos.retenciones_cfdi import CfdiRetencion
from app.modelos.sat_verificacion import DocumentoCumplimiento
from app.nomina_cfdi import pdf as pdf_nomina
from app.retenciones_cfdi import pdf as pdf_retencion
from app.sat_verificacion import cumplimiento

TIPOS = ("factura", "cfdi", "retencion", "opinion", "constancia", "declaracion", "acuse",
         "otro", "recibo_nomina")
NOMBRE_TIPO = {"factura": "Factura", "cfdi": "CFDI", "retencion": "Constancia de retenciones",
               "opinion": "Opinión de cumplimiento", "constancia": "Constancia de situación "
               "fiscal", "declaracion": "Declaración", "acuse": "Acuse",
               "otro": "Documento", "recibo_nomina": "Recibo de nómina"}
LIMITE_LISTA = 25
PDF, XML = "application/pdf", "application/xml"


@dataclass(frozen=True)
class Archivo:
    nombre: str
    contenido: bytes
    mime: str


@dataclass(frozen=True)
class Paquete:
    descripcion: str
    archivos: tuple[Archivo, ...]

    def de_tipo(self, mime: str) -> Archivo | None:
        return next((a for a in self.archivos if a.mime == mime), None)


def _no_existe() -> FiscalAgentError:
    return FiscalAgentError("No existe ese documento en este cliente.", 404)


def _int(ref: str) -> int:
    try:
        return int(ref)
    except ValueError as e:
        raise _no_existe() from e


def _factura(db: Session, cliente: Cliente, ref: str) -> Factura:
    f = db.get(Factura, _int(ref))
    if f is None or cliente.id not in (f.cliente_id, f.cliente_receptor_id):
        raise _no_existe()
    return f


def descripcion_factura(f: Factura) -> str:
    return f"Factura {f.serie}-{f.folio} ({f.uuid})"


def paquete(db: Session, cliente: Cliente, tipo: str, ref: str) -> Paquete:
    """Los archivos del documento (lanza 404 si no es de este cliente)."""
    almacen = obtener_almacenamiento()
    if tipo == "factura":
        f = _factura(db, cliente, ref)
        xml = almacen.leer(f.ruta_xml)
        base = f"{f.serie}-{f.folio}_{f.uuid}"
        return Paquete(descripcion_factura(f), (
            Archivo(f"{base}.pdf", pdf_factura.factura(xml, f.es_prueba), PDF),
            Archivo(f"{base}.xml", xml, XML)))
    if tipo == "cfdi":
        c = db.scalar(select(Comprobante).where(Comprobante.cliente_id == cliente.id,
                                                Comprobante.uuid == ref.upper()))
        if c is None:
            raise _no_existe()
        return Paquete(f"CFDI {c.serie}{c.folio} {c.uuid}",
                       (Archivo(f"{c.uuid}.xml", almacen.leer(c.ruta_xml), XML),))
    if tipo == "retencion":
        r = db.scalar(select(CfdiRetencion).where(CfdiRetencion.cliente_id == cliente.id,
                                                  CfdiRetencion.id == _int(ref)))
        if r is None:
            raise _no_existe()
        xml = almacen.leer(r.ruta_xml)
        return Paquete(f"Constancia de retenciones {r.ejercicio} a {r.rfc_tercero}", (
            Archivo(f"retenciones_{r.uuid}.pdf", pdf_retencion.constancia(xml, r.es_prueba),
                    PDF), Archivo(f"retenciones_{r.uuid}.xml", xml, XML)))
    if tipo in ("opinion", "constancia"):
        d = db.scalar(select(DocumentoCumplimiento).where(
            DocumentoCumplimiento.cliente_id == cliente.id, DocumentoCumplimiento.tipo == tipo,
            DocumentoCumplimiento.id == _int(ref)))
        if d is None:
            raise _no_existe()
        return Paquete(f"{NOMBRE_TIPO[tipo]} del {d.fecha:%d/%m/%Y}",
                       (Archivo(f"{tipo}_{d.fecha:%Y%m%d}.pdf", cumplimiento.leer_pdf(d), PDF),))
    if tipo in ("declaracion", "acuse", "otro"):
        s = db.scalar(select(DocumentoCliente).where(
            DocumentoCliente.cliente_id == cliente.id, DocumentoCliente.tipo == tipo,
            DocumentoCliente.id == _int(ref)))
        if s is None:
            raise _no_existe()
        return Paquete(s.descripcion or f"{NOMBRE_TIPO[tipo]} {s.periodo}".strip(),
                       (Archivo(s.nombre_archivo, almacen.leer(s.ruta), s.mime),))
    if tipo == "recibo_nomina":
        n = db.scalar(select(CfdiNomina).where(CfdiNomina.cliente_id == cliente.id,
                                               CfdiNomina.id == _int(ref)))
        if n is None or not n.ruta_xml:
            raise _no_existe()
        xml = almacen.leer(n.ruta_xml)
        return Paquete(f"Recibo de nómina {n.empleado_no} ({n.uuid})", (
            Archivo(f"nomina_{n.empleado_no}_{n.uuid}.pdf", pdf_nomina.recibo(xml, n.es_prueba),
                    PDF), Archivo(f"nomina_{n.empleado_no}_{n.uuid}.xml", xml, XML)))
    raise FiscalAgentError(f"Tipo de documento desconocido: {tipo}.", 422)


def _fila(tipo: str, ref: Any, descripcion: str, fecha: Any, estado: str = "") -> dict[str, Any]:
    return {"tipo": tipo, "ref": str(ref), "nombre_tipo": NOMBRE_TIPO[tipo],
            "descripcion": descripcion, "fecha": fecha.isoformat() if fecha else None,
            "estado": estado}


def enviables(db: Session, cliente: Cliente) -> list[dict[str, Any]]:
    """Los documentos más recientes de cada tipo (hasta `LIMITE_LISTA` por tipo)."""
    salida: list[dict[str, Any]] = []
    facturas = list(db.scalars(select(Factura).where(or_(
        Factura.cliente_id == cliente.id, Factura.cliente_receptor_id == cliente.id))
        .order_by(Factura.id.desc()).limit(LIMITE_LISTA)))
    salida += [_fila("factura", f.id, descripcion_factura(f), f.fecha_emision, f.estado)
               for f in facturas]
    ya = {f.uuid for f in facturas}
    salida += [_fila("cfdi", c.uuid, f"{c.tipo} {c.direccion} {c.serie}{c.folio} "
                     f"{c.nombre_emisor if c.direccion == 'recibido' else c.nombre_receptor}"
                     f" ${c.total:,.2f}", c.fecha, c.estatus_sat)
               for c in db.scalars(select(Comprobante).where(Comprobante.cliente_id == cliente.id)
                                   .order_by(Comprobante.fecha.desc()).limit(LIMITE_LISTA))
               if c.uuid not in ya]
    salida += [_fila("retencion", r.id, f"Retenciones {r.ejercicio} {r.mes_ini:02d}-"
                     f"{r.mes_fin:02d} a {r.rfc_tercero}", r.fecha_timbrado, r.estado)
               for r in db.scalars(select(CfdiRetencion).where(
                   CfdiRetencion.cliente_id == cliente.id)
                   .order_by(CfdiRetencion.id.desc()).limit(LIMITE_LISTA))]
    salida += [_fila(d.tipo, d.id, f"{NOMBRE_TIPO[d.tipo]} ({d.resultado})", d.fecha)
               for d in db.scalars(select(DocumentoCumplimiento).where(
                   DocumentoCumplimiento.cliente_id == cliente.id)
                   .order_by(DocumentoCumplimiento.fecha.desc(), DocumentoCumplimiento.id.desc())
                   .limit(LIMITE_LISTA)) if d.tipo in ("opinion", "constancia")]
    salida += [_fila(s.tipo, s.id, s.descripcion or s.nombre_archivo, s.creado_en)
               for s in db.scalars(select(DocumentoCliente).where(
                   DocumentoCliente.cliente_id == cliente.id)
                   .order_by(DocumentoCliente.id.desc()).limit(LIMITE_LISTA))]
    salida += [_fila("recibo_nomina", n.id, f"Recibo {n.empleado_no} ({n.uuid})",
                     n.fecha_timbrado, n.estado)
               for n in db.scalars(select(CfdiNomina).where(
                   CfdiNomina.cliente_id == cliente.id, CfdiNomina.ruta_xml != "")
                   .order_by(CfdiNomina.id.desc()).limit(LIMITE_LISTA))]
    return salida
