"""
Migración única de la cartera: Firestore → SQL. (P0-01)

QUÉ TRAE
--------
Por cada uid de Firestore (`users/{uid}`), al despacho con **id = uid** (así lo crea
`app/tenancy.asegurar_usuario`, y por eso no hay que traducir ids):

- `users/{uid}/clientes/{id}`                       → tabla `clientes` (clave = id)
- `users/{uid}/clientes/{id}/empleados/{no}`        → tabla `empleados` (empleado_no = no)
- `users/{uid}/clientes/{id}/dispositivos/{id}`     → tabla `dispositivos` (clave = id)

Los documentos se copian **tal cual** a `datos` (sin el `id`), sin validarlos: un empleado
que no pase la validación actual se migra igual y la API lo reporta en `ilegibles` con su
razón. Validar aquí sería perder datos en silencio, que es lo único que esto no puede hacer.

QUÉ NO TRAE
-----------
El historial de declaraciones (`users/{uid}/declaraciones`) y el perfil
(`users/{uid}` mismo) siguen en Firestore: no tienen tabla todavía. Se migran cuando la
tengan (ver el reporte de P0-01).

IDEMPOTENTE
-----------
Lo que ya existe en SQL **no se toca**: ni se duplica ni se sobrescribe. Correrlo dos
veces deja lo mismo, y correrlo después de que el despacho editó algo por la API no le
pisa la edición con la copia vieja de Firestore. Lo que falta (p. ej. tras una corrida
que se cortó a medias) se agrega.

USO
---
    cd apps/api
    python -m scripts.migrar_firestore --dry-run            # todos los uid, sin escribir
    python -m scripts.migrar_firestore --uid <uid> [--uid <otro>]
    python -m scripts.migrar_firestore                      # todos los uid

Necesita credenciales de Firebase (`GOOGLE_APPLICATION_CREDENTIALS` o ADC, ver
`app/auth_firebase.py`) y `DATABASE_URL` apuntando a la base destino.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app import almacen_cartera as almacen
from app.tenancy import asegurar_usuario

COLECCION_USUARIOS = "users"
COLECCION_CLIENTES = "clientes"
COLECCION_EMPLEADOS = "empleados"
COLECCION_DISPOSITIVOS = "dispositivos"

# Largo de las llaves en SQL (`app/modelos/nucleo.py`). Un id de Firestore más largo no
# cabe: se reporta como omitido en vez de truncarlo (truncar podría fundir dos).
_LARGO_CLAVE_CLIENTE = 120
_LARGO_EMPLEADO_NO = 60
_LARGO_CLAVE_DISPOSITIVO = 120


class DocumentoFirestore(Protocol):
    """Lo mínimo de un `DocumentSnapshot` que usa la migración."""

    id: str

    def to_dict(self) -> dict[str, Any] | None: ...


class ClienteFirestore(Protocol):
    """Lo mínimo del cliente de Firestore que usa la migración (lo cumple el doble)."""

    def collection(self, nombre: str) -> Any: ...


@dataclass
class Conteo:
    nuevos: int = 0
    ya_existian: int = 0


@dataclass
class ReporteDespacho:
    uid: str
    clientes: Conteo = field(default_factory=Conteo)
    empleados: Conteo = field(default_factory=Conteo)
    dispositivos: Conteo = field(default_factory=Conteo)
    omitidos: list[str] = field(default_factory=list)


@dataclass
class Reporte:
    dry_run: bool
    despachos: list[ReporteDespacho] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


def _datos(doc: DocumentoFirestore) -> dict[str, Any]:
    datos = dict(doc.to_dict() or {})
    datos.pop("id", None)
    return datos


def _uids(fs: ClienteFirestore) -> list[str]:
    """
    Todos los uid con algo debajo de `users/`.

    `list_documents()` y no `stream()`: un `users/{uid}` que sólo tiene subcolecciones
    (nunca se escribió el perfil) **no existe** como documento y `stream()` no lo ve.
    Sus clientes se quedarían en Firestore sin que nadie lo notara.
    """
    return sorted(ref.id for ref in fs.collection(COLECCION_USUARIOS).list_documents())


def migrar_uid(db: Session, fs: ClienteFirestore, uid: str) -> ReporteDespacho:
    """Migra un uid a su despacho. No hace commit: eso lo decide quien llama."""
    reporte = ReporteDespacho(uid=uid)
    asegurar_usuario(db, uid)
    usuario = fs.collection(COLECCION_USUARIOS).document(uid)

    for doc_cliente in usuario.collection(COLECCION_CLIENTES).stream():
        clave = doc_cliente.id
        if len(clave) > _LARGO_CLAVE_CLIENTE:
            reporte.omitidos.append(f"cliente {clave[:40]}…: id de más de {_LARGO_CLAVE_CLIENTE}")
            continue
        cliente = almacen.buscar_cliente(db, uid, clave)
        if cliente is None:
            cliente = almacen.crear_cliente(db, uid, clave, _datos(doc_cliente), con_tope=False)
            reporte.clientes.nuevos += 1
        else:
            reporte.clientes.ya_existian += 1

        ref_cliente = usuario.collection(COLECCION_CLIENTES).document(clave)

        for doc_emp in ref_cliente.collection(COLECCION_EMPLEADOS).stream():
            numero = doc_emp.id
            if len(numero) > _LARGO_EMPLEADO_NO:
                reporte.omitidos.append(
                    f"empleado {clave}/{numero[:40]}…: número de más de {_LARGO_EMPLEADO_NO}"
                )
                continue
            if almacen.buscar_empleado(db, cliente, numero) is None:
                almacen.guardar_empleado(db, cliente, numero, _datos(doc_emp), con_tope=False)
                reporte.empleados.nuevos += 1
            else:
                reporte.empleados.ya_existian += 1

        for doc_disp in ref_cliente.collection(COLECCION_DISPOSITIVOS).stream():
            ident = doc_disp.id
            if len(ident) > _LARGO_CLAVE_DISPOSITIVO:
                reporte.omitidos.append(f"dispositivo {clave}/{ident[:40]}…: id demasiado largo")
                continue
            if almacen.buscar_dispositivo(db, cliente, ident) is None:
                almacen.guardar_dispositivo(db, cliente, ident, _datos(doc_disp), con_tope=False)
                reporte.dispositivos.nuevos += 1
            else:
                reporte.dispositivos.ya_existian += 1

    return reporte


def migrar(
    db: Session, fs: ClienteFirestore, uids: list[str] | None = None, *, dry_run: bool = False
) -> Reporte:
    """
    Migra los `uids` (o todos) y hace commit, salvo en `dry_run`, que deshace todo.

    El dry-run corre **el mismo camino** que la corrida real y luego hace rollback: así
    el reporte de "nuevos" y "ya existían" es exactamente lo que haría la real, en vez de
    una simulación aparte que podría divergir.
    """
    reporte = Reporte(dry_run=dry_run)
    try:
        for uid in uids if uids else _uids(fs):
            reporte.despachos.append(migrar_uid(db, fs, uid))
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    return reporte


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migra la cartera de Firestore a SQL.")
    parser.add_argument("--uid", action="append", help="Sólo este uid (repetible).")
    parser.add_argument(
        "--dry-run", action="store_true", help="Reporta lo que haría, sin escribir nada."
    )
    args = parser.parse_args(argv)

    from app.auth_firebase import cliente_firestore
    from app.db.session import SesionLocal, crear_tablas

    crear_tablas()
    db = SesionLocal()
    try:
        reporte = migrar(db, cliente_firestore(), args.uid, dry_run=args.dry_run)
    finally:
        db.close()
    json.dump(reporte.como_dict(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
