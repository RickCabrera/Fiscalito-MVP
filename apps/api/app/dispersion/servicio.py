"""
Dispersión de una nómina cerrada (P4-12): quién se paga, quién no y por qué, y el cuadre.

DE DÓNDE SALE CADA COSA
-----------------------
- Los netos: los recibos GUARDADOS del periodo (`nomina_recibos`), sin recalcular nada.
- Las cuentas: la ficha del empleado en la cartera (`DatosPagoContactoSchema`).
- La cuenta de cargo: una cuenta bancaria del cliente de conciliación (P2-06).

EL CUADRE, AL CENTAVO
---------------------
1. Σ netos de los recibos = total neto guardado del periodo.
2. Se genera el archivo y se RELEE (`layout.importes`): la suma de lo que dice el archivo debe
   ser igual a la de los pagos incluidos.
3. Σ archivo + Σ excluidos = Σ netos de la nómina.

Si cualquiera falla, no se entrega archivo (500): un archivo que no cuadra paga de más o de
menos, y eso no se descarga "con advertencia".
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import almacen_cartera as almacen
from app import nomina_servicio as srv
from app.dispersion.tipos import Abono, Cargo, Layout, Opciones, Pago
from app.exceptions import FiscalAgentError
from app.modelos.conciliacion import CuentaBancaria
from app.modelos.nomina import NominaPeriodo
from app.modelos.nucleo import Cliente
from app.schemas.empleado import EmpleadoCarteraSchema
from app.schemas.empleado_pago import FormaPagoEmpleado

ESTADOS_DISPERSABLES = ("cerrada", "timbrada")
CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class Excluido:
    empleado_no: str
    nombre: str
    neto: Decimal
    causa: str  # sin_ficha | neto_cero | efectivo | cheque | sin_cuenta | layout
    motivo: str


@dataclass
class Resultado:
    layout: Layout
    nombre_archivo: str | None
    contenido: bytes | None
    incluidos: list[tuple[Pago, Abono]]
    excluidos: list[Excluido]
    total_nomina: Decimal
    total_archivo: Decimal
    total_excluidos: Decimal
    sha256: str = ""
    advertencias: list[str] = field(default_factory=list)

    @property
    def cuadra(self) -> bool:
        return self.total_archivo + self.total_excluidos == self.total_nomina


def a_centavos(neto: Decimal) -> int:
    if neto.quantize(CENTAVO) != neto:
        raise FiscalAgentError(f"Un neto guardado trae más de dos decimales: {neto}.", 500)
    return int(neto * 100)


def de_centavos(c: int) -> Decimal:
    return (Decimal(c) / 100).quantize(CENTAVO)


def exigir_cerrada(periodo: NominaPeriodo) -> None:
    if periodo.estado not in ESTADOS_DISPERSABLES:
        raise FiscalAgentError(
            f"El periodo está '{periodo.estado}': sólo se dispersa una nómina cerrada (o "
            "timbrada). Ciérrala primero para que los netos ya no cambien.",
            409,
        )


def _fichas(db: Session, cliente: Cliente) -> dict[str, tuple[EmpleadoCarteraSchema, dict]]:
    crudos = {f.empleado_no: (f.datos or {}) for f in almacen.empleados_de(db, cliente)}
    legibles, _ = srv.fichas_del_cliente(db, cliente)
    return {f.empleado_no: (f, crudos.get(f.empleado_no, {})) for f in legibles}


def pagos_del_periodo(
    db: Session, cliente: Cliente, periodo: NominaPeriodo
) -> tuple[list[Pago], list[Excluido], Decimal]:
    """Los pagos por transferencia y los excluidos con su motivo, más Σ netos."""
    recibos = srv.recibos_de(db, periodo)
    total = sum((r.neto for r in recibos), start=Decimal("0.00"))
    if total != periodo.total_neto:
        raise FiscalAgentError(
            f"Los recibos suman {total} y el periodo guardó {periodo.total_neto}: el "
            "historial está inconsistente y no se dispersa.", 500)
    fichas = _fichas(db, cliente)
    pagos, fuera = [], []
    for r in sorted(recibos, key=lambda x: x.empleado_no):
        def excluir(causa: str, motivo: str, r=r) -> None:
            fuera.append(Excluido(r.empleado_no, r.nombre, r.neto, causa, motivo))

        if r.neto <= 0:
            excluir("neto_cero", "Neto en cero o negativo: no hay nada que depositar.")
            continue
        par = fichas.get(r.empleado_no)
        if par is None:
            excluir("sin_ficha", "El empleado ya no está (o no es legible) en la cartera.")
            continue
        ficha, crudo = par
        if ficha.forma_pago == FormaPagoEmpleado.EFECTIVO:
            excluir("efectivo", "Se le paga en efectivo (forma de pago de su ficha).")
            continue
        if ficha.forma_pago == FormaPagoEmpleado.CHEQUE:
            excluir("cheque", "Se le paga con cheque (forma de pago de su ficha).")
            continue
        if not (ficha.clabe or ficha.numero_cuenta):
            excluir("sin_cuenta", "Sin CLABE ni cuenta capturada en su ficha.")
            continue
        pagos.append(Pago(
            empleado_no=r.empleado_no, nombre=r.nombre or ficha.nombre,
            centavos=a_centavos(r.neto), banco=ficha.banco, clabe=ficha.clabe,
            numero_cuenta=ficha.numero_cuenta, apellido_paterno=ficha.apellido_paterno,
            apellido_materno=ficha.apellido_materno, nombres=ficha.nombres,
            rfc=str(crudo.get("rfc") or ""),
        ))
    return pagos, fuera, total


def cuenta_de_cargo(db: Session, cliente: Cliente, cuenta_id: int | None,
                    layout: Layout) -> Cargo:
    if cuenta_id is None:
        if layout.banco is None:
            return Cargo(banco="")
        raise FiscalAgentError(
            f"Elige la cuenta de cargo {layout.nombre} del patrón (cuentas de conciliación).", 422
        )
    cb = db.scalar(select(CuentaBancaria).where(
        CuentaBancaria.id == cuenta_id, CuentaBancaria.cliente_id == cliente.id))
    if cb is None:
        raise FiscalAgentError(f"No existe la cuenta bancaria {cuenta_id} de este cliente.", 404)
    if not cb.activa:
        raise FiscalAgentError("La cuenta de cargo está inactiva.", 422)
    if layout.banco is not None and cb.banco != layout.banco:
        raise FiscalAgentError(
            f"La cuenta de cargo es del banco {cb.banco} y el layout de {layout.nombre} carga a "
            f"una cuenta {layout.nombre} ({layout.banco}).", 422)
    return Cargo(banco=cb.banco, numero=cb.numero or "", clabe=cb.clabe or "")


def validar_datos_banco(layout: Layout, datos: dict[str, str]) -> dict[str, str]:
    salida = {}
    for d in layout.datos_requeridos:
        valor = str(datos.get(d.clave) or d.default or "").strip()
        if not valor:
            if d.obligatorio:
                raise FiscalAgentError(f"Falta '{d.etiqueta}' para el layout de "
                                       f"{layout.nombre}.", 422)
            continue
        if not re.match(d.patron, valor):
            raise FiscalAgentError(f"'{d.etiqueta}' no tiene la forma esperada: {valor!r}.", 422)
        salida[d.clave] = valor
    return salida


def generar(
    db: Session, cliente: Cliente, periodo: NominaPeriodo, layout: Layout, cargo: Cargo,
    *, fecha_aplicacion: date | None = None, datos_banco: dict[str, str] | None = None,
) -> Resultado:
    """Arma el archivo de dispersión y su reporte. Ver encabezado: cuadra o no se entrega."""
    exigir_cerrada(periodo)
    pagos, excluidos, total_nomina = pagos_del_periodo(db, cliente, periodo)
    incluidos: list[tuple[Pago, Abono]] = []
    for p in pagos:
        elegido = layout.abono(p)
        if isinstance(elegido, str):
            excluidos.append(Excluido(p.empleado_no, p.nombre, de_centavos(p.centavos),
                                      "layout", elegido))
        else:
            incluidos.append((p, elegido))
    op = Opciones(
        fecha_aplicacion=fecha_aplicacion or periodo.fecha_pago,
        concepto=f"NOMINA {periodo.inicio:%Y%m%d}-{periodo.fin:%Y%m%d}",
        razon_social=cliente.nombre or "",
        referencia_numerica=(periodo.id % 9_999_999) or 1,
        datos_banco=validar_datos_banco(layout, datos_banco or {}),
    )
    total_excluidos = sum((e.neto for e in excluidos), start=Decimal("0.00"))
    resultado = Resultado(layout, None, None, incluidos, excluidos, total_nomina,
                          Decimal("0.00"), total_excluidos)
    if not incluidos:
        resultado.advertencias.append("Ningún pago que dispersar con este layout: revisa los "
                                      "excluidos.")
        return resultado
    contenido = layout.generar(incluidos, cargo, op)
    releido = layout.importes(contenido)
    esperado = [p.centavos for p, _ in incluidos]
    if releido != esperado:
        raise FiscalAgentError(
            f"El archivo de {layout.nombre} no cuadra con los pagos: se escribieron "
            f"{len(esperado)} por {sum(esperado)} centavos y se releyeron {len(releido)} por "
            f"{sum(releido)}. No se entrega.", 500)
    resultado.total_archivo = de_centavos(sum(releido))
    if not resultado.cuadra:
        raise FiscalAgentError(
            f"No cuadra: archivo {resultado.total_archivo} + excluidos {total_excluidos} ≠ "
            f"nómina {total_nomina}. No se entrega.", 500)
    resultado.contenido = contenido
    resultado.nombre_archivo = layout.nombre_archivo(op)
    resultado.sha256 = hashlib.sha256(contenido).hexdigest()
    if layout.estado == "por_confirmar":
        resultado.advertencias.append(
            f"Layout de {layout.nombre} POR CONFIRMAR CON MANUAL DEL BANCO: contrástalo "
            "antes de subirlo. Los importes sí cuadran al centavo.")
    return resultado
