"""
Calendario de vencimientos de toda la cartera y agenda semanal del despacho (P3-10).

Une, por cliente visible del usuario (`clientes_visibles`):
- **fiscales**: `fiscal_engine/vencimientos.py` con el RFC y el régimen de la ficha (prórroga
  por sexto dígito y día 17 inhábil corregido);
- **patronales**: `nomina_engine/calendario_laboral.calendario_patronal` (F1-06, ya con sus
  fundamentos y la regla del IMSS), para los clientes con empleados o registro patronal. El
  "entero del ISR retenido" patronal se omite cuando el cliente ya tiene su declaración
  mensual: es la misma declaración (las retenciones viajan en ella) y su fecha correcta es la
  del cliente, con prórroga si es persona física;
- **credenciales**: vencimiento de la e.firma y el CSD activos.

El estado de cada obligación: `presentada` si hay `EstadoObligacion` presentada (marcada a
mano o por `registrar_declaracion`), si no `vencida` cuando la fecha ya pasó, si no
`pendiente`. Las credenciales nunca se "presentan": se renuevan subiendo la nueva.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import rfc_del_cliente
from app.exceptions import FiscalAgentError
from app.fiscal_engine.vencimientos import vencimientos_fiscales
from app.modelos.agenda import EstadoObligacion, TareaAgenda
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente, Empleado, Usuario
from app.nomina_engine.calendario_laboral import ANIO_MAXIMO, ANIO_MINIMO, calendario_patronal
from app.tenancy import Contexto, clientes_visibles

TIPOS = ("fiscal", "patronal", "credencial")
NOMBRE_CREDENCIAL = {"efirma": "e.firma", "csd": "CSD"}


@dataclass
class Obligacion:
    clave: str
    cliente: str
    cliente_nombre: str
    tipo: str
    nombre: str
    periodo: str
    fecha_limite: date
    fundamento: str
    condicional: bool
    nota: str
    estado: str = "pendiente"
    origen_estado: str = ""
    fecha_presentacion: date | None = None
    responsable_uid: str = ""

    def a_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fecha_limite"] = self.fecha_limite.isoformat()
        d["fecha_presentacion"] = (self.fecha_presentacion.isoformat()
                                   if self.fecha_presentacion else None)
        return d


def _es_patron(db: Session, cliente: Cliente) -> bool:
    if str((cliente.datos or {}).get("registro_patronal") or "").strip():
        return True
    return bool(db.scalar(select(func.count()).select_from(Empleado).where(
        Empleado.cliente_id == cliente.id)))


def obligaciones_cliente(
    db: Session, cliente: Cliente, desde: date, hasta: date, hoy: date | None = None
) -> list[Obligacion]:
    """Todas las obligaciones del cliente con fecha límite en [desde, hasta], con estado."""
    datos = cliente.datos or {}
    rfc, regimen = rfc_del_cliente(cliente), str(datos.get("regimen") or "")
    base = {"cliente": cliente.clave, "cliente_nombre": cliente.nombre}
    salida: list[Obligacion] = []
    anios = range(desde.year - 1, hasta.year + 1)
    if rfc and regimen:
        for anio in anios:
            for v in vencimientos_fiscales(rfc, regimen, anio,
                                           dictamina=bool(datos.get("dictamina"))):
                salida.append(Obligacion(clave=v.clave, tipo="fiscal", nombre=v.nombre,
                                         periodo=v.periodo, fecha_limite=v.fecha_limite,
                                         fundamento=v.fundamento, condicional=v.condicional,
                                         nota=v.nota, **base))
    tiene_mensual = any(o.clave.startswith("mensual:") for o in salida)
    if _es_patron(db, cliente):
        for anio in anios:
            if not ANIO_MINIMO <= anio <= ANIO_MAXIMO:
                continue
            for o in calendario_patronal(anio):
                if o.clave == "isr_retenido" and tiene_mensual:
                    continue
                salida.append(Obligacion(
                    clave=f"patronal:{o.clave}:{o.periodo_cubierto}", tipo="patronal",
                    nombre=o.nombre, periodo=o.periodo_cubierto, fecha_limite=o.fecha_limite,
                    fundamento=o.fundamento, condicional=o.condicional, nota=o.nota, **base))
    for cred in db.scalars(select(CredencialCliente).where(
            CredencialCliente.cliente_id == cliente.id, CredencialCliente.activo.is_(True))):
        vence = cred.valido_hasta.date()
        salida.append(Obligacion(
            clave=f"credencial:{cred.tipo}:{cred.id}", tipo="credencial",
            nombre=f"Vence la {NOMBRE_CREDENCIAL.get(cred.tipo, cred.tipo)} "
                   f"({cred.numero_certificado})", periodo=vence.isoformat(),
            fecha_limite=vence, fundamento="Art. 17-D CFF (vigencia del certificado)",
            condicional=False, nota="Renovarla antes de esa fecha.", **base))
    salida = [o for o in salida if desde <= o.fecha_limite <= hasta]
    estados = {e.clave: e for e in db.scalars(select(EstadoObligacion).where(
        EstadoObligacion.cliente_id == cliente.id))}
    hoy = hoy or date.today()
    for o in salida:
        e = estados.get(o.clave)
        if e is not None:
            o.responsable_uid = e.responsable_uid
        if e is not None and e.estado == "presentada" and o.tipo != "credencial":
            o.estado, o.origen_estado, o.fecha_presentacion = "presentada", e.origen, \
                e.fecha_presentacion
        elif o.fecha_limite < hoy:
            o.estado = "vencida"
    return salida


def calendario(
    ctx: Contexto, desde: date, hasta: date, *, cliente: str = "", tipo: str = "",
    responsable: str = "", estado: str = "",
) -> list[Obligacion]:
    """El calendario de la cartera, filtrado y ordenado por fecha y cliente."""
    if hasta < desde or (hasta - desde).days > 400:
        raise FiscalAgentError("El rango del calendario va de 1 día a 400 días.", 422)
    if tipo and tipo not in TIPOS:
        raise FiscalAgentError(f"Tipo inválido: usa uno de {', '.join(TIPOS)}.", 422)
    salida: list[Obligacion] = []
    for c in clientes_visibles(ctx):
        if cliente and c.clave != cliente:
            continue
        salida += obligaciones_cliente(ctx.db, c, desde, hasta)
    salida = [o for o in salida if (not tipo or o.tipo == tipo)
              and (not responsable or o.responsable_uid == responsable)
              and (not estado or o.estado == estado)]
    return sorted(salida, key=lambda o: (o.fecha_limite, o.cliente_nombre, o.clave))


def marcar(
    db: Session, cliente: Cliente, clave: str, estado: str, usuario: str, *,
    origen: str = "manual", fecha_presentacion: date | None = None,
    ingresos_declarados: Decimal | None = None, importe_pagado: Decimal | None = None,
    numero_operacion: str = "", responsable_uid: str | None = None, nota: str = "",
) -> EstadoObligacion:
    """Marca una obligación (presentada | pendiente). Idempotente por (cliente, clave)."""
    if estado not in ("presentada", "pendiente"):
        raise FiscalAgentError("El estado es 'presentada' o 'pendiente'.", 422)
    fila = db.scalar(select(EstadoObligacion).where(
        EstadoObligacion.cliente_id == cliente.id, EstadoObligacion.clave == clave))
    if fila is None:
        fila = EstadoObligacion(cliente_id=cliente.id, clave=clave)
        db.add(fila)
    fila.estado, fila.origen, fila.actualizado_por = estado, origen, usuario
    fila.fecha_presentacion = (fecha_presentacion or date.today()) if estado == "presentada" \
        else None
    if ingresos_declarados is not None:
        fila.ingresos_declarados = ingresos_declarados
    if importe_pagado is not None:
        fila.importe_pagado = importe_pagado
    if numero_operacion:
        fila.numero_operacion = numero_operacion
    if responsable_uid is not None:
        fila.responsable_uid = responsable_uid
    if nota:
        fila.nota = nota
    db.flush()
    return fila


def registrar_declaracion(
    db: Session, cliente: Cliente, tipo: str, periodo: str, usuario: str, **kw: Any
) -> EstadoObligacion:
    """
    Registra una declaración presentada: la obligación del periodo queda `presentada`
    automáticamente (origen `declaracion`). `tipo`: mensual (YYYY-MM) | diot (YYYY-MM) |
    balanza (YYYY-MM) | anual (YYYY).
    """
    if tipo not in ("mensual", "diot", "balanza", "anual"):
        raise FiscalAgentError("Tipo de declaración inválido.", 422)
    largo = 4 if tipo == "anual" else 7
    if len(periodo) != largo or not periodo[:4].isdigit():
        raise FiscalAgentError("Periodo inválido: YYYY-MM (o YYYY para la anual).", 422)
    return marcar(db, cliente, f"{tipo}:{periodo}", "presentada", usuario,
                  origen="declaracion", **kw)


# ── agenda ──


def usuarios_despacho(ctx: Contexto) -> list[dict[str, str]]:
    filas = ctx.db.scalars(select(Usuario).where(Usuario.despacho_id == ctx.despacho_id,
                                                 Usuario.activo.is_(True)).order_by(Usuario.uid))
    return [{"uid": u.uid, "nombre": u.nombre or u.email or u.uid, "rol": u.rol} for u in filas]


def _validar_responsable(ctx: Contexto, uid: str) -> None:
    if uid and uid not in {u["uid"] for u in usuarios_despacho(ctx)}:
        raise FiscalAgentError("El responsable no es usuario de tu despacho.", 422)


def tarea_de(ctx: Contexto, tarea_id: int) -> TareaAgenda:
    t = ctx.db.get(TareaAgenda, tarea_id)
    if t is None or t.despacho_id != ctx.despacho_id:
        raise FiscalAgentError("No existe esa tarea en tu despacho.", 404)
    if ctx.es_auxiliar and t.cliente_id is not None and t.cliente_id not in {
            c.id for c in clientes_visibles(ctx)}:
        raise FiscalAgentError("No existe esa tarea en tu despacho.", 404)
    return t


def tareas(ctx: Contexto, desde: date, hasta: date, *, cliente_id: int | None = None,
           responsable: str = "", estado: str = "") -> list[TareaAgenda]:
    visibles = {c.id for c in clientes_visibles(ctx)}
    q = select(TareaAgenda).where(TareaAgenda.despacho_id == ctx.despacho_id,
                                  TareaAgenda.fecha >= desde, TareaAgenda.fecha <= hasta)
    if cliente_id is not None:
        q = q.where(TareaAgenda.cliente_id == cliente_id)
    if responsable:
        q = q.where(TareaAgenda.responsable_uid == responsable)
    if estado:
        q = q.where(TareaAgenda.estado == estado)
    return [t for t in ctx.db.scalars(q.order_by(TareaAgenda.fecha, TareaAgenda.id))
            if t.cliente_id is None or t.cliente_id in visibles]


def crear_tarea(ctx: Contexto, *, titulo: str, fecha: date, cliente: Cliente | None,
                responsable_uid: str = "", descripcion: str = "",
                estado: str = "pendiente") -> TareaAgenda:
    _validar_responsable(ctx, responsable_uid)
    t = TareaAgenda(despacho_id=ctx.despacho_id, cliente_id=cliente.id if cliente else None,
                    titulo=titulo, fecha=fecha, responsable_uid=responsable_uid,
                    descripcion=descripcion, estado=estado, origen="manual",
                    creado_por=ctx.uid)
    ctx.db.add(t)
    ctx.db.flush()
    return t


def actualizar_tarea(ctx: Contexto, t: TareaAgenda, cambios: dict[str, Any]) -> TareaAgenda:
    if "responsable_uid" in cambios:
        _validar_responsable(ctx, cambios["responsable_uid"] or "")
    for k in ("titulo", "descripcion", "responsable_uid", "fecha", "estado"):
        if k in cambios and cambios[k] is not None:
            setattr(t, k, cambios[k])
    ctx.db.flush()
    return t


def generar_tareas(ctx: Contexto, desde: date, hasta: date, *, cliente: str = "",
                   responsable_uid: str = "") -> list[TareaAgenda]:
    """Una tarea por obligación pendiente o vencida del rango. Idempotente."""
    _validar_responsable(ctx, responsable_uid)
    por_clave = {c.clave: c for c in clientes_visibles(ctx)}
    nuevas = []
    for o in calendario(ctx, desde, hasta, cliente=cliente):
        if o.estado == "presentada":
            continue
        c = por_clave[o.cliente]
        existe = ctx.db.scalar(select(TareaAgenda.id).where(
            TareaAgenda.despacho_id == ctx.despacho_id, TareaAgenda.cliente_id == c.id,
            TareaAgenda.obligacion_clave == o.clave))
        if existe is not None:
            continue
        t = TareaAgenda(despacho_id=ctx.despacho_id, cliente_id=c.id, titulo=o.nombre,
                        fecha=o.fecha_limite, responsable_uid=responsable_uid or
                        o.responsable_uid, descripcion=o.nota, origen="obligacion",
                        obligacion_clave=o.clave, creado_por=ctx.uid,
                        datos={"tipo": o.tipo, "fundamento": o.fundamento})
        ctx.db.add(t)
        nuevas.append(t)
    ctx.db.flush()
    return nuevas


def tarea_json(t: TareaAgenda, clientes: dict[int, Cliente]) -> dict[str, Any]:
    c = clientes.get(t.cliente_id) if t.cliente_id else None
    return {"id": t.id, "titulo": t.titulo, "descripcion": t.descripcion,
            "cliente": c.clave if c else None, "cliente_nombre": c.nombre if c else "",
            "responsable_uid": t.responsable_uid, "fecha": t.fecha.isoformat(),
            "estado": t.estado, "origen": t.origen, "obligacion_clave": t.obligacion_clave}
