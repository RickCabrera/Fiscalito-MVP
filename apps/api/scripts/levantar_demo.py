"""
Levanta la API y le siembra las checadas de los tres clientes. Un comando. (R-02)

    .venv/Scripts/python.exe scripts/levantar_demo.py

Sustituye a los cuatro comandos que pedia el runbook —uvicorn mas tres corridas
de `simular_checador.py`— sin cambiar ninguno de ellos: el camino manual de
`docs/D-DEMO-CHECADOR.md` sigue existiendo tal cual y este script **reusa** su
funcion de envio en vez de reimplementarla.

POR QUE LEVANTAR Y SEMBRAR TIENEN QUE IR EN EL MISMO COMANDO
------------------------------------------------------------
El almacen de checadas es **memoria del proceso** (`app/asistencia/almacen.py`).
De ahi salen las dos reglas del runbook que este script automatiza sin
romperlas:

- No se puede sembrar antes de levantar: no hay donde.
- No se puede reiniciar despues de sembrar: se borran las 194 checadas.

Y de ahi sale tambien el modo de falla que este script **elimina de raiz**: un
`uvicorn` levantado hace dias sirve los endpoints de SU commit, asi que las
rutas nuevas responden 404 y en pantalla se lee como un error de red. Paso el
2026-09-02 con `/despacho/calendario`. Aqui el proceso **nace del commit
actual**, asi que el pre-flight del paso 0 del runbook no aplica a este camino.

`--reload` SIGUE PROHIBIDO, y este script no lo reintroduce por la puerta de
atras: `D-DEMO-CHECADOR.md` lo prohibe porque cualquier guardado reiniciaria el
proceso y borraria lo sembrado, enfrente del proyector.

PRIVACIDAD: NADA DE LO QUE SE IMPRIME SALE DE `raw`
---------------------------------------------------
`EventoChecada.raw` puede traer el **nombre de la persona** (campo `name` del
`InfoList`), y `schemas/asistencia.py` dice que vive en RAM y no debe escribirse
a disco ni a logs. Lo que este script imprime son conteos, ids de cliente y
fechas — nunca nada derivado de `raw`, **ni siquiera al fallar**. Hay un test
que lo fija.

TODO EL STDOUT ES ASCII, a proposito: la consola de Windows es cp1252, la demo
corre en Windows, y un "->" de verdad la reventaba con UnicodeEncodeError
DESPUES de haber posteado todo.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import threading
import time as espera
from collections.abc import Callable, Sequence
from pathlib import Path

import uvicorn

from app.constants import CLIENTE_DEMO
from app.exceptions import FiscalValidationError


def _cargar_simulador():
    """
    Carga `scripts/simular_checador.py` por ruta.

    Mismo patron que usa ese archivo para cargar `checador_sintetico.py`, y por
    la misma razon: `scripts/` no es paquete ni esta en `sys.path` al correr un
    script suelto, y se prefiere cargar por ruta antes que manipular `sys.path`
    y necesitar un `# noqa: E402`. El modulo se registra en `sys.modules` antes
    de ejecutarlo porque `@dataclass` resuelve el namespace por nombre.
    """
    ruta = Path(__file__).resolve().parent / "simular_checador.py"
    spec = importlib.util.spec_from_file_location("simular_checador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


_sim = _cargar_simulador()


class ClienteSembrable:
    """Un cliente de la demo y con que serial se le siembra."""

    def __init__(self, cliente_id: str, serial_base: int) -> None:
        self.cliente_id = cliente_id
        self.serial_base = serial_base


# Los mismos tres clientes y los mismos serial-base que el runbook manual, para
# que las dos rutas produzcan exactamente el mismo estado.
#
# LOS SERIAL-BASE TIENEN QUE SER DISTINTOS ENTRE CLIENTES. El dedupe del almacen
# es por `(empleado_no, serial_no)` **dentro de un cliente**, asi que repetirlos
# no colisiona hoy... pero los tres clientes comparten numeracion de empleado
# (`E-01`, `E-02`, ...), y el dia que se siembre mas de un cliente en el mismo
# almacen o se unifique el dedupe, un serial repetido descartaria checadas
# reales en silencio. Se separan por rango y el test lo fija por sus efectos.
CLIENTES_DEMO: tuple[ClienteSembrable, ...] = (
    ClienteSembrable(CLIENTE_DEMO, 900_001),
    ClienteSembrable("cafeteria", 2_000_000),
    ClienteSembrable("taller", 3_000_000),
)

# Arrancar no puede colgar sin decir nada: un arranque roto dejaria al operador
# mirando una consola muda enfrente del proyector.
ESPERA_MAXIMA_S = 10.0
INTERVALO_SONDEO_S = 0.05


def sembrar_todo(
    api: str,
    clientes: Sequence[ClienteSembrable] = CLIENTES_DEMO,
    poster: Callable[[str, dict, dict], object] | None = None,
) -> list[tuple[str, int, int]]:
    """
    Siembra la quincena de cada cliente contra una API que ya esta viva.

    `poster` es inyectable —igual que en `simular_checador.enviar`— para que los
    tests ejerciten el camino real con un `TestClient` y sin levantar un puerto.

    Returns:
        Una tupla `(cliente_id, recibidos, duplicados)` por cliente.

    Raises:
        FiscalValidationError: si algun cliente no pudo sembrarse. **No se
            continua con los demas**: una demo con dos de tres clientes
            sembrados es peor que una que no arranco, porque el tercero da una
            nomina completa y creible con todos los dias en falta.
    """
    resultados: list[tuple[str, int, int]] = []
    for cliente in clientes:
        empleados = _sim.plantilla_de_cliente(cliente.cliente_id)
        periodo = _sim.quincena(_hoy())
        eventos = _sim.generar_checadas(
            empleados,
            periodo,
            _sim.HorarioLaboral(),
            _sim.OFFSET_DEFAULT,
            _sim.siembra_para(cliente.cliente_id, empleados),
            cliente.serial_base,
        )
        recibidos, duplicados = _sim.enviar(
            [eventos],
            f"{api}{_sim.RUTA_EVENTOS}",
            cliente.cliente_id,
            _sim.FuenteChecada.SIMULADO.value,
            poster=poster,
        )
        if not recibidos:
            raise FiscalValidationError(
                f"el cliente {cliente.cliente_id!r} no acepto ninguna checada "
                f"({duplicados} duplicadas). Con el almacen ya sembrado, corre con "
                f"otro --serial-base; si no, la siembra esta rota."
            )
        # Conteos, id de cliente y fechas. Nada derivado de `raw`.
        resultados.append((cliente.cliente_id, recibidos, duplicados))
    return resultados


def _hoy():
    """`date.today()` indirecto, para que los tests puedan fijar el dia."""
    from datetime import date

    return date.today()


def _esperar_arranque(server: uvicorn.Server, limite_s: float = ESPERA_MAXIMA_S) -> None:
    """
    Bloquea hasta que uvicorn este sirviendo, o revienta con un mensaje util.

    La cota es obligatoria: sin ella un arranque roto —puerto ocupado es el caso
    tipico— se ve igual que uno lento, y son la misma consola muda.
    """
    limite = espera.monotonic() + limite_s
    while espera.monotonic() < limite:
        if server.started:
            return
        espera.sleep(INTERVALO_SONDEO_S)
    raise FiscalValidationError(
        f"la API no arranco en {limite_s:.0f} s. Lo mas probable es que el puerto ya "
        f"este ocupado por otro uvicorn: matalo, o usa --puerto."
    )


def _argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Levanta la API y siembra las checadas de la demo (R-02).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=8000)
    parser.add_argument(
        "--sin-sembrar",
        action="store_true",
        help="Solo levanta la API. Equivale al uvicorn pelado del runbook.",
    )
    parser.add_argument(
        "--clientes",
        default=",".join(c.cliente_id for c in CLIENTES_DEMO),
        help="Ids separados por coma. Por defecto, los tres de la demo.",
    )
    return parser.parse_args(argv)


def _seleccionar(ids: str) -> tuple[ClienteSembrable, ...]:
    pedidos = [i.strip() for i in ids.split(",") if i.strip()]
    conocidos = {c.cliente_id: c for c in CLIENTES_DEMO}
    faltantes = [i for i in pedidos if i not in conocidos]
    if faltantes:
        raise FiscalValidationError(
            f"clientes desconocidos: {', '.join(faltantes)}. "
            f"Conocidos: {', '.join(conocidos)}."
        )
    return tuple(conocidos[i] for i in pedidos)


def main(argv: Sequence[str] | None = None) -> int:
    """Devuelve 0, 1 (la siembra fallo) o 2 (mal uso)."""
    args = _argumentos(argv)
    try:
        seleccion = _seleccionar(args.clientes)
    except FiscalValidationError as exc:
        print(f"No se pudo elegir los clientes: {exc}", file=sys.stderr)
        return 2

    config = uvicorn.Config(
        "app.main:app", host=args.host, port=args.puerto, log_level="info"
    )
    server = uvicorn.Server(config)

    # En un hilo, y no en subprocess: en Windows el manejo de senales y el
    # cierre limpio de un hijo son el modo de falla obvio, y aqui el operador
    # solo tiene Ctrl+C. Como `Server.run` no corre en el hilo principal,
    # uvicorn NO instala sus manejadores de senal; el Ctrl+C llega aqui como
    # KeyboardInterrupt y se traduce a `should_exit`.
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()

    api = f"http://{args.host}:{args.puerto}"
    try:
        _esperar_arranque(server)
    except FiscalValidationError as exc:
        print(f"No se pudo levantar la API: {exc}", file=sys.stderr)
        return 1
    print(f"API viva en {api}", flush=True)

    if args.sin_sembrar:
        print("--sin-sembrar: no se siembra nada.", flush=True)
    else:
        try:
            for cliente_id, recibidos, duplicados in sembrar_todo(api, seleccion):
                print(
                    f"cliente {cliente_id} | recibidos={recibidos} duplicados={duplicados}",
                    flush=True,
                )
        except FiscalValidationError as exc:
            # El mensaje de `exc` lo construimos nosotros arriba y no toca `raw`.
            print(f"No se pudo sembrar: {exc}", file=sys.stderr)
            server.should_exit = True
            hilo.join(timeout=5)
            return 1
        except Exception as exc:  # noqa: BLE001
            # Red, JSON, lo que sea. Se imprime el TIPO y el mensaje de la
            # excepcion, que no lleva eventos; no se vuelca el payload, que si
            # llevaria nombres de personas.
            print(
                f"No se pudo sembrar ({type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
            server.should_exit = True
            hilo.join(timeout=5)
            return 1

    print("Listo. La API sigue corriendo; Ctrl+C para parar.", flush=True)
    try:
        while hilo.is_alive():
            hilo.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nParando...")
        server.should_exit = True
        hilo.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
