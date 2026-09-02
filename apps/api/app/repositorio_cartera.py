"""
El backend se vuelve dueño del dato de la cartera. (R-07)

QUÉ CAMBIA, Y POR QUÉ ERA NECESARIO
-----------------------------------
`apps/api/CLAUDE.md` declara el servicio **stateless**, y esa regla es la que
hizo que G-01 no construyera el CRUD que Ricardo pidió: la única persistencia
posible entonces habría sido otro almacén en RAM, que habría hecho literalmente
falso el criterio de G-01 después de cualquier reinicio.

Ricardo tomó la decisión de frente en R-07: **el servicio deja de ser
stateless.** El motivo no es preferencia de arquitectura, es que hoy hay **dos
dueños del mismo dato** —el front escribe Firestore directo y el backend calcula
sobre lo que el front le manda en el body— y eso significa que la plantilla del
cálculo viaja por el cliente. Con un solo dueño, el backend puede leer la
plantilla él mismo y dejar de creerle al navegador.

LA ABSTRACCIÓN NO ES CEREMONIA
------------------------------
`RepositorioCartera` es un Protocol con dos implementaciones:

- `FirestoreCartera` — la de producción, sobre `firebase-admin`.
- `CarteraEnMemoria` — un doble para los tests que corren en CI.

Existe porque **el Admin SDK necesita credenciales y CI no las tiene**. Sin el
doble, la mitad de los tests de esta tarea no correrían en CI; sin la
implementación real ejercitada, el doble sería el único código probado y el
adaptador se entregaría sin haberse ejecutado nunca. Se hacen las dos cosas: los
mismos casos corren contra el doble en CI y **contra el emulador de Firestore**
en local (`pytest -m emulador`), que es un Firestore de verdad y por lo tanto la
única forma de probar rutas, subcolecciones, borrado en cascada y aislamiento
entre uids sin tocar producción.

LAS RUTAS SON LAS MISMAS QUE YA USA EL FRONT
--------------------------------------------
`users/{uid}/clientes/{id}` y `.../empleados/{id}`, idénticas a las de
`carteraFirestore.ts`. **No hay migración de datos**: lo que el contador tenga
guardado se sigue leyendo igual, y encender el backend como dueño no le mueve un
documento.

EL ADMIN SDK IGNORA LAS REGLAS DE SEGURIDAD
-------------------------------------------
Por diseño: son credenciales privilegiadas. Las reglas que R-01 desplegó siguen
siendo la defensa del acceso **directo desde el navegador**; la de este camino es
la verificación del ID token en `auth_firebase.py`. Por eso el `uid` **nunca**
llega por el cuerpo ni por un query param: eso sería suplantación de un renglón.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from app.exceptions import FiscalAgentError

# `users/{uid}/clientes/{clienteId}` y sus subcolecciones. Se nombran aquí para
# que cambiar el árbol sea una edición y no una cacería por el archivo.
COLECCION_USUARIOS = "users"
COLECCION_CLIENTES = "clientes"
COLECCION_EMPLEADOS = "empleados"

# Cota de lo que un uid puede guardar. No es una regla de negocio: es que este
# endpoint escribe en una base que se cobra por operación y por almacenamiento,
# y sin tope un bucle de `curl` con un token válido es una factura.
MAX_CLIENTES_POR_UID = 500
MAX_EMPLEADOS_POR_CLIENTE = 2_000


class RepositorioCartera(Protocol):
    """Lo que las rutas necesitan saber hacer. Nada más."""

    def listar_clientes(self, uid: str) -> list[dict[str, Any]]: ...

    def obtener_cliente(self, uid: str, cliente_id: str) -> dict[str, Any] | None: ...

    def guardar_cliente(self, uid: str, cliente_id: str, datos: dict[str, Any]) -> None: ...

    def borrar_cliente(self, uid: str, cliente_id: str) -> None: ...

    def listar_empleados(self, uid: str, cliente_id: str) -> list[dict[str, Any]]: ...

    def guardar_empleado(
        self, uid: str, cliente_id: str, empleado_no: str, datos: dict[str, Any]
    ) -> None: ...

    def borrar_empleado(self, uid: str, cliente_id: str, empleado_no: str) -> None: ...


class CarteraEnMemoria:
    """
    Doble de `RepositorioCartera` para los tests que corren en CI.

    **No se usa en producción y no es un fallback.** Si alguna vez lo fuera, el
    criterio de R-07 —"sobrevive reinicio de la API"— sería falso otra vez, que
    es exactamente la razón por la que G-01 no construyó este CRUD.
    """

    def __init__(self) -> None:
        # {uid: {cliente_id: {"datos": {...}, "empleados": {no: {...}}}}}
        self._por_uid: dict[str, dict[str, dict[str, Any]]] = {}

    def _cliente(self, uid: str, cliente_id: str) -> dict[str, Any] | None:
        return self._por_uid.get(uid, {}).get(cliente_id)

    def listar_clientes(self, uid: str) -> list[dict[str, Any]]:
        return [
            {**c["datos"], "id": cid}
            for cid, c in sorted(self._por_uid.get(uid, {}).items())
        ]

    def obtener_cliente(self, uid: str, cliente_id: str) -> dict[str, Any] | None:
        c = self._cliente(uid, cliente_id)
        return {**c["datos"], "id": cliente_id} if c else None

    def guardar_cliente(self, uid: str, cliente_id: str, datos: dict[str, Any]) -> None:
        del_uid = self._por_uid.setdefault(uid, {})
        if cliente_id not in del_uid and len(del_uid) >= MAX_CLIENTES_POR_UID:
            raise FiscalAgentError(
                f"Llegaste al tope de {MAX_CLIENTES_POR_UID} clientes.", status_code=409
            )
        existente = del_uid.setdefault(cliente_id, {"datos": {}, "empleados": {}})
        existente["datos"] = dict(datos)

    def borrar_cliente(self, uid: str, cliente_id: str) -> None:
        # En cascada: los empleados cuelgan del cliente y sin esto quedarían
        # huérfanos, reapareciendo al recrear un cliente con el mismo id. Es el
        # mismo cuidado que ya tenía `carteraFirestore.borrarCliente`.
        self._por_uid.get(uid, {}).pop(cliente_id, None)

    def listar_empleados(self, uid: str, cliente_id: str) -> list[dict[str, Any]]:
        c = self._cliente(uid, cliente_id)
        return [dict(e) for _, e in sorted(c["empleados"].items())] if c else []

    def guardar_empleado(
        self, uid: str, cliente_id: str, empleado_no: str, datos: dict[str, Any]
    ) -> None:
        c = self._cliente(uid, cliente_id)
        if c is None:
            raise FiscalAgentError(
                f"El cliente {cliente_id!r} no está en tu cartera.", status_code=404
            )
        if empleado_no not in c["empleados"] and len(c["empleados"]) >= MAX_EMPLEADOS_POR_CLIENTE:
            raise FiscalAgentError(
                f"Llegaste al tope de {MAX_EMPLEADOS_POR_CLIENTE} empleados.", status_code=409
            )
        c["empleados"][empleado_no] = dict(datos)

    def borrar_empleado(self, uid: str, cliente_id: str, empleado_no: str) -> None:
        c = self._cliente(uid, cliente_id)
        if c is not None:
            c["empleados"].pop(empleado_no, None)

    def reset(self) -> None:
        self._por_uid.clear()


class FirestoreCartera:
    """
    La implementación real, sobre `firebase-admin`.

    Se construye con el cliente de Firestore ya inicializado: quién lo inicializa
    —y con qué credenciales— es de `auth_firebase.py`, para que este módulo se
    pueda instanciar contra el emulador sin tocar nada de autenticación.
    """

    def __init__(self, db: Any) -> None:
        self._db = db

    def _clientes(self, uid: str) -> Any:
        return (
            self._db.collection(COLECCION_USUARIOS)
            .document(uid)
            .collection(COLECCION_CLIENTES)
        )

    def _cliente(self, uid: str, cliente_id: str) -> Any:
        return self._clientes(uid).document(cliente_id)

    def _empleados(self, uid: str, cliente_id: str) -> Any:
        return self._cliente(uid, cliente_id).collection(COLECCION_EMPLEADOS)

    def listar_clientes(self, uid: str) -> list[dict[str, Any]]:
        # **Sin `limit`.** Lo tenía, y truncaba en silencio: el cliente 501
        # desaparecía de la lista del contador sin un solo aviso, que es peor
        # que cualquier cosa que el tope viniera a evitar. La cota va del lado
        # de la ESCRITURA, donde puede decir que no.
        return [{**doc.to_dict(), "id": doc.id} for doc in self._clientes(uid).stream()]

    def obtener_cliente(self, uid: str, cliente_id: str) -> dict[str, Any] | None:
        doc = self._cliente(uid, cliente_id).get()
        return {**doc.to_dict(), "id": doc.id} if doc.exists else None

    def guardar_cliente(self, uid: str, cliente_id: str, datos: dict[str, Any]) -> None:
        # **El tope se aplica AQUÍ y no sólo en el doble.** La primera versión lo
        # tenía únicamente en `CarteraEnMemoria`, así que el comentario que lo
        # justifica —"sin tope un bucle de `curl` con un token válido es una
        # factura"— describía una protección que el código real no tenía. Lo
        # midió el revisor de motor.
        #
        # Se cuenta con `limit(MAX+1)` para no traer toda la colección sólo para
        # contarla, y **sólo cuando el cliente es nuevo**: editar uno existente
        # no puede rebotar por el tope.
        if not self._cliente(uid, cliente_id).get().exists:
            cuantos = sum(
                1 for _ in self._clientes(uid).limit(MAX_CLIENTES_POR_UID + 1).stream()
            )
            if cuantos >= MAX_CLIENTES_POR_UID:
                raise FiscalAgentError(
                    f"Llegaste al tope de {MAX_CLIENTES_POR_UID} clientes.", status_code=409
                )
        # `merge=True` como el front: un PUT parcial no debe borrar campos que
        # esta versión de la app todavía no conoce.
        self._cliente(uid, cliente_id).set(datos, merge=True)

    def borrar_cliente(self, uid: str, cliente_id: str) -> None:
        # **Firestore no borra subcolecciones en cascada.** Sin esto los
        # empleados quedan huérfanos y reaparecen al recrear un cliente con el
        # mismo id — con su salario y su NSS. Es el mismo agujero que
        # `carteraFirestore.ts` ya tenía tapado del lado del navegador.
        lote = self._db.batch()
        for doc in self._empleados(uid, cliente_id).stream():
            lote.delete(doc.reference)
        lote.delete(self._cliente(uid, cliente_id))
        lote.commit()

    def listar_empleados(self, uid: str, cliente_id: str) -> list[dict[str, Any]]:
        return [doc.to_dict() for doc in self._empleados(uid, cliente_id).stream()]

    def guardar_empleado(
        self, uid: str, cliente_id: str, empleado_no: str, datos: dict[str, Any]
    ) -> None:
        if not self._cliente(uid, cliente_id).get().exists:
            # No se crea el cliente al vuelo: un empleado colgando de un cliente
            # que no existe es invisible en la lista y aparece en el cálculo.
            raise FiscalAgentError(
                f"El cliente {cliente_id!r} no está en tu cartera.", status_code=404
            )
        ref = self._empleados(uid, cliente_id).document(empleado_no)
        if not ref.get().exists:
            cuantos = sum(
                1
                for _ in self._empleados(uid, cliente_id)
                .limit(MAX_EMPLEADOS_POR_CLIENTE + 1)
                .stream()
            )
            if cuantos >= MAX_EMPLEADOS_POR_CLIENTE:
                raise FiscalAgentError(
                    f"Llegaste al tope de {MAX_EMPLEADOS_POR_CLIENTE} empleados.",
                    status_code=409,
                )
        ref.set(datos, merge=True)

    def borrar_empleado(self, uid: str, cliente_id: str, empleado_no: str) -> None:
        self._empleados(uid, cliente_id).document(empleado_no).delete()


def usando_emulador() -> bool:
    """`True` si hay un emulador de Firestore configurado por entorno."""
    return bool(os.environ.get("FIRESTORE_EMULATOR_HOST"))
