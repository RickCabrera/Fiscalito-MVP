"""
La migración Firestore → SQL, contra un doble en memoria del cliente de Firestore. (P0-01)

El doble imita sólo lo que el script usa —`collection`, `document`, `stream`,
`list_documents`— incluido el detalle que más fácil se pierde: un `users/{uid}` que
sólo tiene subcolecciones **no existe** como documento, así que `stream()` no lo ve y
`list_documents()` sí.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.modelos.nucleo import Cliente, Despacho, Dispositivo, Empleado, Usuario
from scripts.migrar_firestore import migrar


class _Doc:
    def __init__(self, ident: str, datos: dict[str, Any] | None) -> None:
        self.id = ident
        self._datos = datos

    def to_dict(self) -> dict[str, Any] | None:
        return None if self._datos is None else dict(self._datos)


class _RefDoc:
    def __init__(self, raiz: FirestoreEnMemoria, ruta: tuple[str, ...]) -> None:
        self._raiz = raiz
        self._ruta = ruta
        self.id = ruta[-1]

    def collection(self, nombre: str) -> _RefColeccion:
        return _RefColeccion(self._raiz, (*self._ruta, nombre))


class _RefColeccion:
    def __init__(self, raiz: FirestoreEnMemoria, ruta: tuple[str, ...]) -> None:
        self._raiz = raiz
        self._ruta = ruta

    def document(self, ident: str) -> _RefDoc:
        return _RefDoc(self._raiz, (*self._ruta, ident))

    def _hijos(self) -> set[str]:
        n = len(self._ruta)
        return {r[n] for r in self._raiz.docs if len(r) > n and r[:n] == self._ruta}

    def stream(self):
        """Sólo documentos que EXISTEN (tienen datos), como Firestore."""
        for ident in sorted(self._hijos()):
            ruta = (*self._ruta, ident)
            if ruta in self._raiz.docs:
                yield _Doc(ident, self._raiz.docs[ruta])

    def list_documents(self):
        """Incluye documentos "fantasma" que sólo tienen subcolecciones."""
        for ident in sorted(self._hijos()):
            yield _RefDoc(self._raiz, (*self._ruta, ident))


class FirestoreEnMemoria:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, ...], dict[str, Any]] = {}

    def poner(self, ruta: str, datos: dict[str, Any]) -> None:
        self.docs[tuple(ruta.split("/"))] = datos

    def collection(self, nombre: str) -> _RefColeccion:
        return _RefColeccion(self, (nombre,))


EMPLEADO = {
    "empleado_no": "E-01",
    "nombre": "PERSONA UNA",
    "salario_diario": "520.00",
    "salario_diario_integrado": "548.50",
    "zona": "general",
    "tipo_contrato": "indeterminado",
    "prestaciones": {"dias_aguinaldo": 15, "dias_vacaciones": 0, "prima_vacacional": "0.25"},
    "nss": "",
    "employee_no": "7",
    "enrolamiento": "enrolado",
}


@pytest.fixture
def fs() -> FirestoreEnMemoria:
    """Una cuenta de prueba con todo lo que la cartera puede tener, más casos raros."""
    f = FirestoreEnMemoria()
    # uid-a tiene perfil; uid-b NO (sólo subcolecciones): list_documents lo tiene que ver.
    f.poner("users/uid-a", {"contributorType": "contador"})
    f.poner(
        "users/uid-a/clientes/taller",
        {
            "id": "taller",  # un documento viejo con el id adentro: no se duplica en datos
            "nombre": "Taller Mecánico",
            "giro": "Servicios",
            "origen": "propio",
            "prima_riesgo": "0.0054355",
            "clave_periodicidad": "04",
            "zona": "general",
            "rfc": "ABCD010101AB1",
            "campo_de_una_version_vieja": [1, 2, 3],
        },
    )
    f.poner("users/uid-a/clientes/taller/empleados/E-01", EMPLEADO)
    # Legado: NSS de 9 dígitos. Se migra igual y la API lo reporta como ilegible.
    f.poner(
        "users/uid-a/clientes/taller/empleados/E-02",
        {**EMPLEADO, "empleado_no": "E-02", "nss": "123456789"},
    )
    f.poner(
        "users/uid-a/clientes/taller/dispositivos/abc123",
        {"nombre": "Entrada", "ip": "192.168.1.64", "puerto": 80, "employee_nos": ["7"]},
    )
    f.poner("users/uid-a/clientes/vacio", {"nombre": "Sin plantilla"})
    # Historial: no es cartera, no se migra (y no debe romper nada).
    f.poner("users/uid-a/declaraciones/mensual_2026_01", {"isr": 1})
    f.poner("users/uid-b/clientes/otro", {"nombre": "Del despacho B"})
    f.poner("users/uid-b/clientes/otro/empleados/E-01", {**EMPLEADO, "nombre": "OTRA PERSONA"})
    return f


def _todo(db) -> dict[str, Any]:
    """Una foto comparable de lo que quedó en SQL."""
    clientes = {
        (c.despacho_id, c.clave): (c.nombre, c.rfc, c.datos)
        for c in db.scalars(select(Cliente))
    }
    empleados = {
        (e.cliente_id, e.empleado_no): e.datos for e in db.scalars(select(Empleado))
    }
    dispositivos = {(d.cliente_id, d.clave): d.datos for d in db.scalars(select(Dispositivo))}
    return {"clientes": clientes, "empleados": empleados, "dispositivos": dispositivos}


def test_migra_la_cuenta_de_prueba_sin_perder_nada(db_sesion, fs):
    reporte = migrar(db_sesion, fs)

    assert [d.uid for d in reporte.despachos] == ["uid-a", "uid-b"]
    a = reporte.despachos[0]
    assert (a.clientes.nuevos, a.empleados.nuevos, a.dispositivos.nuevos) == (2, 2, 1)
    assert a.omitidos == []

    # Despacho con id = uid, y su usuario dueño.
    assert db_sesion.get(Despacho, "uid-a") is not None
    assert db_sesion.get(Usuario, "uid-b").despacho_id == "uid-b"

    taller = db_sesion.scalar(select(Cliente).where(Cliente.clave == "taller"))
    assert taller.despacho_id == "uid-a"
    assert taller.nombre == "Taller Mecánico" and taller.rfc == "ABCD010101AB1"
    # Todo el documento, campos desconocidos incluidos; el id NO se duplica adentro.
    esperado = dict(fs.docs[("users", "uid-a", "clientes", "taller")])
    esperado.pop("id")
    assert taller.datos == esperado

    empleados = {e.empleado_no: e.datos for e in db_sesion.scalars(select(Empleado))
                 .all() if e.cliente_id == taller.id}
    assert empleados["E-01"] == EMPLEADO
    assert empleados["E-02"]["nss"] == "123456789", "el legado se migró alterado"

    [disp] = db_sesion.scalars(select(Dispositivo)).all()
    assert disp.clave == "abc123" and disp.cliente_id == taller.id
    assert disp.datos["employee_nos"] == ["7"]


def test_es_idempotente(db_sesion, fs):
    migrar(db_sesion, fs)
    foto = _todo(db_sesion)

    reporte = migrar(db_sesion, fs)

    assert _todo(db_sesion) == foto
    a = reporte.despachos[0]
    assert (a.clientes.nuevos, a.empleados.nuevos, a.dispositivos.nuevos) == (0, 0, 0)
    assert (a.clientes.ya_existian, a.empleados.ya_existian, a.dispositivos.ya_existian) == (
        2, 2, 1,
    )


def test_no_pisa_lo_que_el_despacho_edito_despues(db_sesion, fs):
    """Correrla otra vez no puede regresar un cliente a su copia vieja de Firestore."""
    migrar(db_sesion, fs)
    taller = db_sesion.scalar(select(Cliente).where(Cliente.clave == "taller"))
    taller.datos = {**taller.datos, "nombre": "Editado en la app"}
    db_sesion.commit()

    migrar(db_sesion, fs)

    db_sesion.refresh(taller)
    assert taller.datos["nombre"] == "Editado en la app"


def test_completa_lo_que_faltaba(db_sesion, fs):
    """Una corrida cortada a medias se termina con la siguiente."""
    migrar(db_sesion, fs, ["uid-a"])
    fs.poner("users/uid-a/clientes/taller/empleados/E-03", {**EMPLEADO, "empleado_no": "E-03"})

    reporte = migrar(db_sesion, fs)

    assert reporte.despachos[0].empleados.nuevos == 1
    assert reporte.despachos[1].clientes.nuevos == 1


def test_dry_run_no_escribe_nada_y_reporta_lo_mismo(db_sesion, fs):
    simulado = migrar(db_sesion, fs, dry_run=True)

    assert db_sesion.scalars(select(Cliente)).all() == []
    assert db_sesion.get(Despacho, "uid-a") is None
    real = migrar(db_sesion, fs)
    simulado.dry_run = real.dry_run
    assert simulado.como_dict() == real.como_dict()


def test_solo_los_uid_pedidos(db_sesion, fs):
    reporte = migrar(db_sesion, fs, ["uid-b"])
    assert [d.uid for d in reporte.despachos] == ["uid-b"]
    assert [c.clave for c in db_sesion.scalars(select(Cliente))] == ["otro"]


def test_un_id_demasiado_largo_se_reporta_en_vez_de_truncarse(db_sesion, fs):
    fs.poner(f"users/uid-a/clientes/{'x' * 200}", {"nombre": "Largo"})
    reporte = migrar(db_sesion, fs, ["uid-a"])
    assert len(reporte.despachos[0].omitidos) == 1
    assert db_sesion.scalar(select(Cliente).where(Cliente.nombre == "Largo")) is None


def test_lo_migrado_se_lee_por_la_API_con_su_ilegible(db_sesion, fs, api):
    """Cierre del ciclo: lo migrado es la cartera del despacho, y el legado se ve (R-10)."""
    migrar(db_sesion, fs)

    a = api("uid-a")
    clientes = a.get("/api/v1/cartera/clientes").json()["clientes"]
    assert {c["id"] for c in clientes} == {"taller", "vacio"}
    plantilla = a.get("/api/v1/cartera/clientes/taller/empleados").json()
    assert [e["empleado_no"] for e in plantilla["empleados"]] == ["E-01"]
    assert plantilla["ilegibles"] == ["E-02"]
    assert a.get("/api/v1/cartera/clientes/taller/dispositivos").json()["total"] == 1
    # Y el despacho B sigue sin ver nada de A.
    assert api("uid-b").get("/api/v1/cartera/clientes/taller/empleados").status_code == 404
