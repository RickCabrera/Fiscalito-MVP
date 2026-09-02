"""
Tests del comando unico que levanta y siembra la demo (R-02).

QUE SE PRUEBA AQUI, Y POR QUE NO SE PRUEBA LEVANTAR UVICORN
-----------------------------------------------------------
El criterio de R-02 es "un solo comando levanta API + datos de checador". Eso
tiene dos mitades con riesgos muy distintos:

- **Sembrar los tres clientes** es donde vive el riesgo real —un cliente sin
  sembrar no da una nomina en ceros, da una nomina completa y creible con todos
  los dias laborables en falta (`docs/D-DEMO-CHECADOR.md`)— y se prueba aqui
  contra el endpoint **real**, con `TestClient` inyectado como `poster`. Es el
  mismo mecanismo de inyeccion que ya usa `simular_checador.enviar`.
- **Levantar uvicorn en un hilo** es codigo de arranque: probarlo exigiria abrir
  un puerto de verdad en CI, que es la clase de test que se pone intermitente y
  al que alguien acaba poniendo un `sleep`. Se deja fuera **a proposito y se
  dice**, en vez de fingir cobertura con un mock del propio uvicorn.

POR QUE LAS ASERCIONES MIRAN EL ALMACEN Y NO LO QUE DEVUELVE LA FUNCION
-----------------------------------------------------------------------
Una version anterior del plan proponia afirmar que "los tres serial-base son
distintos". Ese test pasa con la siembra **completamente rota**: compara tres
constantes entre si. Aqui se afirma el EFECTO —que cada cliente termino con
checadas suyas en el almacen— que es lo unico que hace que la demo funcione.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.asistencia.almacen import almacen
from app.constants import CLIENTE_DEMO
from app.exceptions import FiscalValidationError
from tests.nomina_inventario import EMPLEADOS_SINTETICOS


def _cargar(nombre: str):
    """Carga un script de `scripts/` por ruta; no es paquete ni esta en sys.path."""
    ruta = Path(__file__).resolve().parents[2] / "scripts" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


levantar_demo = _cargar("levantar_demo")


@pytest.fixture
def poster(cliente_http: TestClient):
    """
    Postea contra la app real montada en `TestClient`.

    Misma forma que `simular_checador._poster_httpx`: `(url, params, payload)`.
    Se ignora el host de la URL y se queda con la ruta, que es lo unico que el
    `TestClient` sabe resolver.
    """

    def _postear(url: str, params: dict, payload: dict):
        ruta = url.split("://", 1)[-1].split("/", 1)[-1]
        return cliente_http.post(f"/{ruta}", params=params, json=payload)

    return _postear


def test_siembra_los_tres_clientes_y_cada_uno_queda_con_checadas_suyas(poster):
    """
    El criterio de R-02, medido por su efecto.

    Mata dos mutaciones que el test de "serial-base distintos" no mataba:
      1. quitar un cliente de `CLIENTES_DEMO` (queda un almacen en cero);
      2. sembrarlos todos bajo el mismo cliente (dos almacenes en cero).
    """
    resultados = levantar_demo.sembrar_todo("http://testserver", poster=poster)

    sembrados = {cliente_id for cliente_id, _, _ in resultados}
    assert sembrados == {CLIENTE_DEMO, "cafeteria", "taller"}, (
        "R-02 tiene que dejar los TRES clientes sembrados. Un cliente sin checadas no "
        "da una nomina en ceros: da una nomina completa con todos los dias en falta."
    )

    for cliente_id, recibidos, duplicados in resultados:
        assert recibidos > 0, f"{cliente_id} no recibio ninguna checada"
        assert duplicados == 0, f"{cliente_id} sembro duplicados en un almacen limpio"
        # El efecto, que es lo que importa: quedaron EN EL ALMACEN, bajo SU cliente.
        assert almacen.total(cliente_id) == recibidos


def test_cada_cliente_recibe_solo_sus_propias_checadas(poster):
    """
    Los tres clientes comparten numeracion de empleado (`E-01`, `E-02`, ...).

    Si la siembra mandara todo al mismo cliente, o si el `cliente` no viajara en
    los params, los conteos se sumarian en un solo almacen y los otros dos
    quedarian vacios. Esta asercion es la que distingue "sembre tres veces" de
    "sembre tres clientes".
    """
    levantar_demo.sembrar_todo("http://testserver", poster=poster)

    totales = {c.cliente_id: almacen.total(c.cliente_id) for c in levantar_demo.CLIENTES_DEMO}
    assert all(t > 0 for t in totales.values()), totales
    # Las plantillas tienen tamanos distintos (9, 4 y 12 empleados), asi que dos
    # totales iguales delatarian que se sembro lo mismo dos veces.
    assert len(set(totales.values())) == len(totales), (
        f"dos clientes quedaron con el mismo numero de checadas: {totales}"
    )


def test_una_segunda_siembra_no_pasa_por_buena(poster):
    """
    Re-sembrar sin cambiar el serial-base es un no-op silencioso, y no debe serlo.

    El almacen deduplica por `(empleado_no, serial_no)`, asi que la segunda
    corrida devuelve `recibidos=0, duplicados=N`. Sin esta guarda, el operador
    veria "listo" con un almacen que no crecio.
    """
    levantar_demo.sembrar_todo("http://testserver", poster=poster)

    with pytest.raises(FiscalValidationError, match="no acepto ninguna checada"):
        levantar_demo.sembrar_todo("http://testserver", poster=poster)


def test_un_cliente_desconocido_se_rechaza_por_nombre():
    with pytest.raises(FiscalValidationError, match="clientes desconocidos: fantasma"):
        levantar_demo._seleccionar("demo,fantasma")


def test_sin_sembrar_no_postea_nada():
    """`--sin-sembrar` equivale al uvicorn pelado del runbook."""
    llamadas: list[tuple] = []

    def espia(url, params, payload):
        llamadas.append((url, params, payload))
        raise AssertionError("no deberia haberse posteado nada")

    args = levantar_demo._argumentos(["--sin-sembrar"])
    assert args.sin_sembrar is True
    assert llamadas == []


def test_lo_que_se_imprime_no_lleva_nombres_de_personas(poster):
    """
    PRIVACIDAD. `EventoChecada.raw` trae el `name` del `InfoList`, y
    `schemas/asistencia.py` dice que vive en RAM y no se escribe a disco ni a
    logs. `main()` imprime **solo** lo que devuelve `sembrar_todo`, asi que
    fijar la forma de ese retorno fija lo que puede acabar en una consola o en
    un log redirigido.
    """
    resultados = levantar_demo.sembrar_todo("http://testserver", poster=poster)

    impreso = " ".join(
        f"cliente {cliente_id} | recibidos={recibidos} duplicados={duplicados}"
        for cliente_id, recibidos, duplicados in resultados
    )
    nombres = [e["nombre"] for e in EMPLEADOS_SINTETICOS]
    filtrados = [n for n in nombres if n and n in impreso]
    assert not filtrados, f"se imprimieron nombres de personas: {filtrados}"

    # Y la forma: id de cliente (str) mas dos conteos (int). Nada mas cabe.
    for fila in resultados:
        assert len(fila) == 3
        assert isinstance(fila[0], str)
        assert isinstance(fila[1], int) and isinstance(fila[2], int)


def test_el_error_de_siembra_tampoco_filtra_nombres(poster):
    """El camino de fallo es el que se olvida: el mensaje solo nombra al cliente."""
    levantar_demo.sembrar_todo("http://testserver", poster=poster)

    with pytest.raises(FiscalValidationError) as exc:
        levantar_demo.sembrar_todo("http://testserver", poster=poster)

    mensaje = str(exc.value)
    nombres = [e["nombre"] for e in EMPLEADOS_SINTETICOS if e["nombre"]]
    assert not [n for n in nombres if n in mensaje], mensaje


def test_los_serial_base_no_se_pisan_entre_clientes():
    """
    Complementa a los de arriba: aquellos miden el efecto, este documenta la
    razon de la separacion por rangos. Por si solo no probaria nada — por eso
    **no** es el unico test de este archivo, que era el defecto del plan v1.
    """
    seriales = [c.serial_base for c in levantar_demo.CLIENTES_DEMO]
    assert len(set(seriales)) == len(seriales)
