"""
¿El despacho puede escribir? ¿Su plan incluye este módulo? (P5-08)

No importa `app.tenancy` (tenancy SÍ importa esto): aquí sólo hay base de datos y fechas.

ESTADO GUARDADO vs ESTADO EFECTIVO
----------------------------------
`suscripciones.estado` es lo último que se supo (por el alta, el cambio, la cancelación o el
webhook). El estado EFECTIVO también mira el reloj, porque un webhook que no llega no debe
dejar abierto el acceso para siempre:

| guardado   | vigente mientras                 | efectivo al pasarse        |
|------------|----------------------------------|----------------------------|
| prueba     | ahora < fin_periodo              | vencida                    |
| activa     | ahora < fin_periodo + gracia     | morosa (en la gracia), luego vencida |
| morosa     | ahora < fin_periodo + gracia     | vencida                    |
| cancelada  | ahora < fin_periodo (ya pagado)  | cancelada (solo lectura)   |
| vencida    | nunca                            | vencida                    |

SIN VIGENCIA = SOLO LECTURA, NUNCA BORRADO
------------------------------------------
`exigir_escritura` (llamada desde `tenancy.contexto_actual`) responde 402 a todo método que
escribe (POST/PUT/PATCH/DELETE) salvo las rutas de `/suscripcion`, que son justo las que
sirven para salir del bloqueo. Leer y descargar sigue funcionando. Nada se borra.

Un despacho sin renglón en `suscripciones` (todos los anteriores a P5-08) recibe uno en
`prueba` desde el momento en que se le pregunta: arrancarle la prueba en su fecha de alta
lo dejaría en solo lectura el día del despliegue sin haber visto nunca la pantalla de planes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Despacho
from app.modelos.suscripciones import Suscripcion
from app.planes import MODULOS, PLANES, Plan, dias_gracia, dias_prueba, modulos_del_plan
from app.planes import plan as plan_de

METODOS_DE_LECTURA = frozenset({"GET", "HEAD", "OPTIONS"})
# Rutas que se pueden usar en solo lectura: las que sacan al despacho del bloqueo.
RUTAS_EXENTAS = ("/api/v1/suscripcion",)


def ahora() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Vigencia:
    estado: str  # efectivo: prueba | activa | morosa | vencida | cancelada
    vigente: bool
    aviso: str
    acceso_hasta: datetime


def asegurar(db: Session, despacho_id: str) -> Suscripcion:
    """La suscripción del despacho; si no tiene, nace en `prueba` desde hoy."""
    s = db.get(Suscripcion, despacho_id)
    if s is not None:
        return s
    inicio = ahora()
    try:
        with db.begin_nested():
            s = Suscripcion(despacho_id=despacho_id, estado="prueba", inicio_periodo=inicio,
                            fin_periodo=inicio + timedelta(days=dias_prueba()))
            db.add(s)
            db.flush()
    except IntegrityError:  # dos requests simultáneos: gana el primero
        s = db.get(Suscripcion, despacho_id)
        if s is None:
            raise
    return s


def _fecha(d: datetime) -> str:
    return d.astimezone(UTC).date().isoformat()


def vigencia(s: Suscripcion, momento: datetime | None = None) -> Vigencia:
    """Estado efectivo de la suscripción en `momento` (ver la tabla del encabezado)."""
    t = momento or ahora()
    fin = s.fin_periodo
    gracia = fin + timedelta(days=dias_gracia())
    solo_lectura = ("La cuenta está en modo solo lectura: puedes consultar y descargar todo, "
                    "pero no dar de alta ni modificar nada hasta que")
    if s.estado == "prueba":
        if t < fin:
            return Vigencia("prueba", True, f"Estás en periodo de prueba hasta el {_fecha(fin)}.",
                            fin)
        return Vigencia("vencida", False, f"Tu periodo de prueba terminó el {_fecha(fin)}. "
                        f"{solo_lectura} te suscribas a un plan.", fin)
    if s.estado in ("activa", "morosa"):
        if s.estado == "activa" and t < fin:
            return Vigencia("activa", True, "", gracia)
        if t < gracia:
            return Vigencia("morosa", True, "No hemos recibido el pago de tu suscripción. "
                            f"Si no se cubre antes del {_fecha(gracia)}, la cuenta pasará a "
                            "solo lectura.", gracia)
        return Vigencia("vencida", False, f"Tu suscripción venció el {_fecha(fin)} sin pago. "
                        f"{solo_lectura} se cubra el pago o te suscribas de nuevo.", gracia)
    if s.estado == "cancelada":
        if t < fin:
            return Vigencia("cancelada", True, "Cancelaste tu suscripción: conservas el acceso "
                            f"completo hasta el {_fecha(fin)}.", fin)
        return Vigencia("cancelada", False, f"Tu suscripción terminó el {_fecha(fin)}. "
                        f"{solo_lectura} te suscribas de nuevo.", fin)
    return Vigencia("vencida", False, f"Tu suscripción está vencida. {solo_lectura} te "
                    "suscribas de nuevo.", fin)


def exigir_escritura(db: Session, despacho_id: str, metodo: str, ruta: str) -> None:
    """402 si el request escribe y la suscripción del despacho no está vigente."""
    if metodo.upper() in METODOS_DE_LECTURA or ruta.startswith(RUTAS_EXENTAS):
        return
    v = vigencia(asegurar(db, despacho_id))
    if not v.vigente:
        raise FiscalAgentError(v.aviso, status_code=402)


def plan_del_despacho(db: Session, despacho_id: str) -> Plan:
    despacho = db.get(Despacho, despacho_id)
    return plan_de(despacho.plan if despacho is not None else None)


def motivo_modulo(p: Plan, modulo: str) -> str:
    """Por qué un módulo no está disponible, dicho para el usuario."""
    con_el = [x.nombre for x in _planes_con(modulo)]
    sugerencia = (f" Está en el plan {' y '.join(con_el)}." if con_el else "")
    return f"El plan {p.nombre} no incluye {MODULOS[modulo]}.{sugerencia} Cámbialo en Planes."


def _planes_con(modulo: str) -> list[Plan]:
    return [p for p in PLANES.values() if modulo in modulos_del_plan(p)]


def exigir_modulo(db: Session, despacho_id: str, modulo: str) -> None:
    """403 con el motivo si el plan del despacho no incluye `modulo` (clave de `MODULOS`)."""
    if modulo not in MODULOS:
        raise KeyError(f"Módulo desconocido: {modulo}")  # error de programación, no de usuario
    p = plan_del_despacho(db, despacho_id)
    if modulo not in modulos_del_plan(p):
        raise FiscalAgentError(motivo_modulo(p, modulo), status_code=403)
