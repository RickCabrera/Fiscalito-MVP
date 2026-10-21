"""
Motor de reglas de alertas fiscales (P3-09). Corre como trabajo diario (`alertas.evaluar`).

Cada regla mira UN cliente y devuelve las alertas que hoy aplican, cada una con una `clave`
estable. `sincronizar` las cruza con lo guardado:

- clave nueva → se crea; clave existente → se actualiza el texto (no se duplica);
- alerta abierta cuya clave ya no aparece → resuelta por el sistema (la situación pasó);
- alerta resuelta a mano → no se reabre mientras la clave sea la misma; si el sistema la
  había resuelto y la situación vuelve, se reabre.

REGLAS Y FUENTES
----------------
- `tope_resico`: ingresos cobrados del ejercicio (flujo de efectivo de los CFDI emitidos) contra
  el tope de RESICO: personas físicas 3.5 millones (Art. 113-E LISR, `TOPE_RESICO_ANUAL`);
  personas morales 35 millones (Art. 206 LISR). Avisa al 80 % (media) y al 100 % (alta).
- `efos`: integra los cruces 69-B/69 de P1-04 (`AlertaRiesgo` no atendidas).
- `cfdi_cancelado`: CFDI de la bóveda cancelado ante el SAT que tiene póliza activa sin
  reversa (P2-03) o cuyo mes ya tiene la declaración mensual marcada presentada (P3-10).
- `credencial`: e.firma o CSD activos que vencen en ≤ 30 días (media), ≤ 7 días o vencidos
  (alta). Los umbrales son `DIAS_AVISO`.
- `opinion`: la opinión de cumplimiento más reciente (P1-05) es negativa.
- `descarga_sat`: integra los avisos de la descarga masiva (P1-02) sin resolver.
- `vencimiento`: obligaciones del calendario (P3-10) que vencen en los próximos 7 días (media)
  o que vencieron en los últimos 30 sin marcarse presentadas (alta).
- `diferencia_declarado`: ingresos declarados registrados (P3-10) contra lo cobrado según la
  bóveda; avisa si la diferencia pasa de `TOLERANCIA_PESOS` y de `TOLERANCIA_PCT`.
- `sin_polizas`: mes cerrado del ejercicio con CFDI en la bóveda y sin pólizas, sólo en
  clientes que ya llevan contabilidad en Fiscalito (tienen alguna póliza).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agenda.servicio import obligaciones_cliente
from app.boveda_cfdi.servicio import comprobantes_vigentes, rfc_del_cliente
from app.constants import TOPE_RESICO_ANUAL
from app.impuestos.flujo import flujo_del_mes
from app.modelos.agenda import EstadoObligacion
from app.modelos.alertas import AlertaFiscal
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import Poliza
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente
from app.modelos.sat_descarga import AlertaDescargaSat
from app.modelos.sat_verificacion import AlertaRiesgo, DocumentoCumplimiento

TOPE_RESICO_PM = Decimal("35000000")  # Art. 206 LISR (RESICO personas morales)
UMBRALES_RESICO = (Decimal("1"), Decimal("0.8"))
DIAS_AVISO = (7, 30)
TOLERANCIA_PESOS = Decimal("1000")
TOLERANCIA_PCT = Decimal("0.01")
NOMBRE_CRED = {"efirma": "e.firma", "csd": "CSD"}


@dataclass
class Nueva:
    tipo: str
    severidad: str
    titulo: str
    detalle: str
    fecha: date
    clave: str
    enlace: str = ""
    datos: dict[str, Any] = field(default_factory=dict)


def _mes(fecha: date) -> str:
    return f"{fecha.year}-{fecha.month:02d}"


def regla_tope_resico(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    if str((c.datos or {}).get("regimen") or "") != "626":
        return []
    pf = len(rfc_del_cliente(c)) == 13
    tope = Decimal(str(TOPE_RESICO_ANUAL)) if pf else TOPE_RESICO_PM
    ingresos = Decimal("0")
    for mes in range(1, hoy.month + 1):
        for e in flujo_del_mes(db, c, hoy.year, mes):
            comp = e.comprobante
            if comp.direccion == "emitido":
                ingresos += (comp.subtotal - comp.descuento) * e.factor_pesos * (
                    -1 if comp.tipo == "E" else 1)
    pct = ingresos / tope if tope else Decimal("0")
    for umbral in UMBRALES_RESICO:
        if pct >= umbral:
            nivel = int(umbral * 100)
            return [Nueva(
                "tope_resico", "alta" if umbral >= 1 else "media",
                f"RESICO: ingresos al {pct * 100:.0f} % del tope {hoy.year}",
                f"Ingresos cobrados del ejercicio ${ingresos:,.2f} de un tope de ${tope:,.2f} "
                f"({'Art. 113-E' if pf else 'Art. 206'} LISR). "
                + ("Al rebasarlo deja de tributar en RESICO." if umbral >= 1 else
                   "Revisa la proyección del ejercicio."),
                hoy, f"tope_resico:{hoy.year}:{nivel}", "/app/store/fiscalito/use",
                {"ingresos": str(ingresos), "tope": str(tope)})]
    return []


def regla_efos(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    salida = []
    for a in db.scalars(select(AlertaRiesgo).where(AlertaRiesgo.cliente_id == c.id,
                                                   AlertaRiesgo.atendida.is_(False))):
        sev = {"alto": "alta", "medio": "media"}.get(a.nivel, "baja")
        quien = {"proveedor": "Proveedor", "cliente": "Cliente", "propio": "El propio cliente"}
        salida.append(Nueva(
            "efos", sev, f"{quien.get(a.relacion, 'Contraparte')} en lista {a.lista.upper()}: "
                         f"{a.rfc}",
            f"{a.nombre or a.rfc} aparece como {a.situacion} en el listado {a.lista} del SAT.",
            (a.creado_en or datetime.now(UTC)).date(), f"efos:{a.id}", "/app/sat",
            {"alerta_riesgo_id": a.id}))
    return salida


def regla_cfdi_cancelado(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    salida = []
    cancelados = db.scalars(select(Comprobante).where(
        Comprobante.cliente_id == c.id, Comprobante.estatus_sat == "cancelado",
        Comprobante.fecha >= datetime(hoy.year - 1, 1, 1)))
    presentadas = {e.clave for e in db.scalars(select(EstadoObligacion).where(
        EstadoObligacion.cliente_id == c.id, EstadoObligacion.estado == "presentada"))}
    for comp in cancelados:
        motivos = []
        poliza = db.scalar(select(Poliza.id).where(
            Poliza.cliente_id == c.id, Poliza.clave_origen == f"cfdi:{comp.uuid}",
            Poliza.estado == "activa"))
        reversa = db.scalar(select(Poliza.id).where(
            Poliza.cliente_id == c.id, Poliza.clave_origen == f"reversa:{comp.uuid}"))
        if poliza is not None and reversa is None:
            motivos.append("tiene póliza contable activa sin reversa")
        if f"mensual:{_mes(comp.fecha.date())}" in presentadas:
            motivos.append(f"la declaración de {_mes(comp.fecha.date())} ya se presentó")
        if motivos:
            salida.append(Nueva(
                "cfdi_cancelado", "alta",
                f"CFDI cancelado después de usarse: {comp.uuid[:8]}",
                f"{comp.direccion.capitalize()} {comp.serie}{comp.folio} por "
                f"${comp.total:,.2f} ({comp.rfc_emisor} → {comp.rfc_receptor}): "
                + "; ".join(motivos) + ".",
                (comp.fecha_estatus or datetime.now(UTC)).date(), f"cfdi_cancelado:{comp.uuid}",
                "/app/boveda", {"uuid": comp.uuid}))
    return salida


def regla_credenciales(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    salida = []
    for cred in db.scalars(select(CredencialCliente).where(
            CredencialCliente.cliente_id == c.id, CredencialCliente.activo.is_(True))):
        vence = cred.valido_hasta.date()
        dias = (vence - hoy).days
        nombre = NOMBRE_CRED.get(cred.tipo, cred.tipo)
        if dias < 0:
            nivel, sev, titulo = "vencida", "alta", f"La {nombre} venció el {vence.isoformat()}"
        elif dias <= DIAS_AVISO[0]:
            nivel, sev, titulo = "7", "alta", f"La {nombre} vence en {dias} días"
        elif dias <= DIAS_AVISO[1]:
            nivel, sev, titulo = "30", "media", f"La {nombre} vence en {dias} días"
        else:
            continue
        salida.append(Nueva("credencial", sev, titulo,
                            f"Certificado {cred.numero_certificado}, válido hasta "
                            f"{vence.isoformat()}. Sube la renovada en la ficha del cliente.",
                            vence, f"credencial:{cred.id}:{nivel}", f"/app/clientes/{c.clave}"))
    return salida


def regla_opinion(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    doc = db.scalar(select(DocumentoCumplimiento).where(
        DocumentoCumplimiento.cliente_id == c.id, DocumentoCumplimiento.tipo == "opinion")
        .order_by(DocumentoCumplimiento.fecha.desc(), DocumentoCumplimiento.id.desc()))
    if doc is None or doc.resultado != "negativa":
        return []
    return [Nueva("opinion", "alta", "Opinión de cumplimiento NEGATIVA",
                  f"La opinión del {doc.fecha.isoformat()} (folio {doc.folio or 's/f'}) es "
                  "negativa: revisa las obligaciones omitidas o créditos que señala.",
                  doc.fecha, f"opinion:{doc.id}", "/app/sat")]


def regla_descarga_sat(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    titulos = {"sin_efirma": "Descarga SAT detenida: falta e.firma vigente",
               "atorada": "Descarga SAT atorada", "error_sat": "El SAT rechazó una descarga",
               "agotada": "Descarga SAT agotada (límite de solicitudes)"}
    return [Nueva("descarga_sat", "alta" if a.tipo == "sin_efirma" else "media",
                  titulos.get(a.tipo, "Problema en la descarga SAT"), a.mensaje,
                  (a.creado_en or datetime.now(UTC)).date(), f"descarga:{a.id}", "/app/sat",
                  {"alerta_descarga_id": a.id})
            for a in db.scalars(select(AlertaDescargaSat).where(
                AlertaDescargaSat.cliente_id == c.id, AlertaDescargaSat.resuelta.is_(False)))]


def regla_vencimientos(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    salida = []
    for o in obligaciones_cliente(db, c, hoy - timedelta(days=30), hoy + timedelta(days=7),
                                  hoy):
        if o.tipo == "credencial" or o.estado == "presentada":
            continue
        vencida = o.estado == "vencida"
        sev = "alta" if vencida else ("baja" if o.condicional else "media")
        dias = (o.fecha_limite - hoy).days
        cuando = (f"venció el {o.fecha_limite.isoformat()}" if vencida else
                  "vence hoy" if dias == 0 else f"vence en {dias} días")
        salida.append(Nueva("vencimiento", sev, f"{o.nombre}: {cuando}",
                            f"{o.fundamento}. {o.nota}".strip(), o.fecha_limite,
                            f"vencimiento:{o.clave}", "/app/calendario", {"obligacion": o.clave}))
    return salida


def regla_diferencias(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    salida = []
    for e in db.scalars(select(EstadoObligacion).where(
            EstadoObligacion.cliente_id == c.id, EstadoObligacion.estado == "presentada",
            EstadoObligacion.ingresos_declarados.is_not(None),
            EstadoObligacion.clave.like("mensual:%"))):
        anio, mes = (int(x) for x in e.clave.split(":", 1)[1].split("-"))
        cobrado = Decimal("0")
        for ef in flujo_del_mes(db, c, anio, mes):
            comp = ef.comprobante
            if comp.direccion == "emitido":
                cobrado += (comp.subtotal - comp.descuento) * ef.factor_pesos * (
                    -1 if comp.tipo == "E" else 1)
        declarado = Decimal(e.ingresos_declarados or 0)
        diferencia = (cobrado - declarado).quantize(Decimal("0.01"))
        if abs(diferencia) > max(TOLERANCIA_PESOS, abs(cobrado) * TOLERANCIA_PCT):
            salida.append(Nueva(
                "diferencia_declarado", "media",
                f"Ingresos de {anio}-{mes:02d}: lo declarado no cuadra con la bóveda",
                f"Declarado ${declarado:,.2f}; cobrado según los CFDI de la bóveda "
                f"${cobrado:,.2f} (diferencia ${diferencia:,.2f}).",
                e.fecha_presentacion or hoy, f"diferencia:{anio}-{mes:02d}",
                "/app/store/fiscalito/use",
                {"declarado": str(declarado), "cobrado": str(cobrado)}))
    return salida


def regla_sin_polizas(db: Session, c: Cliente, hoy: date) -> list[Nueva]:
    lleva = db.scalar(select(func.count()).select_from(Poliza).where(Poliza.cliente_id == c.id))
    if not lleva:
        return []
    salida = []
    for mes in range(1, hoy.month):
        inicio = datetime(hoy.year, mes, 1)
        fin = datetime(hoy.year, mes + 1, 1)
        cfdi = db.scalar(comprobantes_vigentes(select(func.count()).select_from(Comprobante)
                         .where(Comprobante.cliente_id == c.id,
                                Comprobante.tipo.in_(("I", "E", "N")),
                                Comprobante.fecha >= inicio, Comprobante.fecha < fin)))
        polizas = db.scalar(select(func.count()).select_from(Poliza).where(
            Poliza.cliente_id == c.id, Poliza.anio == hoy.year, Poliza.mes == mes,
            Poliza.estado == "activa"))
        if cfdi and not polizas:
            salida.append(Nueva("sin_polizas", "baja", f"{hoy.year}-{mes:02d} sin pólizas",
                                f"El mes tiene {cfdi} CFDI en la bóveda y ninguna póliza.",
                                date(hoy.year, mes, 1), f"sin_polizas:{hoy.year}-{mes:02d}",
                                "/app/store/contabilito/use"))
    return salida


REGLAS: dict[str, Callable[[Session, Cliente, date], list[Nueva]]] = {
    "tope_resico": regla_tope_resico, "efos": regla_efos, "cfdi_cancelado": regla_cfdi_cancelado,
    "credencial": regla_credenciales, "opinion": regla_opinion,
    "descarga_sat": regla_descarga_sat, "vencimiento": regla_vencimientos,
    "diferencia_declarado": regla_diferencias, "sin_polizas": regla_sin_polizas,
}


def sincronizar(db: Session, c: Cliente, nuevas: list[Nueva], tipos: set[str]) -> dict[str, int]:
    """Guarda sin duplicar y resuelve lo que ya no aplica (sólo de los `tipos` evaluados)."""
    existentes = {a.clave: a for a in db.scalars(select(AlertaFiscal).where(
        AlertaFiscal.cliente_id == c.id, AlertaFiscal.tipo.in_(tipos)))}
    vistas: set[str] = set()
    creadas = resueltas = 0
    for n in nuevas:
        if n.clave in vistas:
            continue
        vistas.add(n.clave)
        a = existentes.get(n.clave)
        if a is None:
            db.add(AlertaFiscal(despacho_id=c.despacho_id, cliente_id=c.id, tipo=n.tipo,
                                severidad=n.severidad, titulo=n.titulo[:300], detalle=n.detalle,
                                fecha=n.fecha, enlace=n.enlace, clave=n.clave, datos=n.datos))
            creadas += 1
            continue
        a.severidad, a.titulo, a.detalle, a.fecha, a.enlace, a.datos = (
            n.severidad, n.titulo[:300], n.detalle, n.fecha, n.enlace, n.datos)
        if a.resuelta and a.resuelta_por == "sistema":
            a.resuelta, a.resuelta_por, a.resuelta_en = False, "", None
    for clave, a in existentes.items():
        if clave not in vistas and not a.resuelta:
            a.resuelta, a.resuelta_por, a.resuelta_en = True, "sistema", datetime.now(UTC)
            resueltas += 1
    db.flush()
    return {"creadas": creadas, "resueltas": resueltas, "vigentes": len(vistas)}


def evaluar_cliente(db: Session, c: Cliente, hoy: date | None = None,
                    tipos: set[str] | None = None) -> dict[str, int]:
    """Corre las reglas (todas o `tipos`) sobre un cliente y sincroniza."""
    hoy = hoy or date.today()
    tipos = tipos or set(REGLAS)
    nuevas: list[Nueva] = []
    for t in sorted(tipos):
        nuevas += REGLAS[t](db, c, hoy)
    return sincronizar(db, c, nuevas, tipos)


def alerta_json(a: AlertaFiscal, cliente: Cliente) -> dict[str, Any]:
    return {"id": a.id, "cliente": cliente.clave, "cliente_nombre": cliente.nombre,
            "tipo": a.tipo, "severidad": a.severidad, "titulo": a.titulo, "detalle": a.detalle,
            "fecha": a.fecha.isoformat(), "enlace": a.enlace, "resuelta": a.resuelta,
            "resuelta_por": a.resuelta_por,
            "resuelta_en": a.resuelta_en.isoformat() if a.resuelta_en else None}
