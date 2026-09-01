"""
Simulador del checador Hikvision (D-05). Alimenta la demo sin el aparato.

Genera la quincena completa de los 9 empleados de las fixtures de S-04 —con 2
faltas y 3 retardos sembrados— y la POSTea a `/api/v1/asistencia/eventos` con
**el mismo JSON que manda el dispositivo**: `{"AcsEvent": {"InfoList": [...]}}`.
El endpoint no distingue el origen; lo unico que cambia es `fuente=simulado`,
que es la etiqueta honesta y **no se cambia a `hikvision` para que "se vea
real"**.

Uso (con la API corriendo en el puerto 8000):
    python apps/api/scripts/simular_checador.py                 # todo de golpe
    python apps/api/scripts/simular_checador.py --en-vivo       # ultimo dia gota a gota
    python apps/api/scripts/simular_checador.py --dry-run       # imprime, no postea

Aqui vive solo el CLI y el envio. La generacion —que es lo que se prueba— vive
en `scripts/checador_sintetico.py`, junto con las tres decisiones provisionales
de la tarea.

LO QUE ESTE SCRIPT **NO** DEMUESTRA
-----------------------------------
El "Listo cuando" del backlog dice "corriendolo, el panel se llena solo". El
panel es **D-07 y todavia no existe**: lo que queda probado es que el simulador
alimenta `POST /asistencia/eventos` y que `GET /asistencia/eventos` devuelve lo
que el panel va a consumir. Que la pantalla se llene sola **se cierra en D-07**.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time as espera_modulo
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

import httpx

from app.constants import CLIENTE_DEMO
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import FuenteChecada, HorarioLaboral, Periodo


def _cargar_generador():
    """
    Carga `scripts/checador_sintetico.py` por ruta.

    Mismo patron que `scripts/anonimizar_nomina.py`: `scripts/` no es paquete y
    no esta en `sys.path` al correr el script suelto, y se prefiere cargar por
    ruta antes que manipular `sys.path` y necesitar un `# noqa: E402`.

    A diferencia de aquel, **el modulo se registra en `sys.modules` antes de
    ejecutarlo**: sin eso `@dataclass` revienta con AttributeError, porque
    resuelve el namespace del modulo por su nombre.
    """
    ruta = Path(__file__).resolve().parent / "checador_sintetico.py"
    spec = importlib.util.spec_from_file_location("checador_sintetico", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


_gen = _cargar_generador()

EmpleadoDemo = _gen.EmpleadoDemo
Falta = _gen.Falta
Retardo = _gen.Retardo
Siembra = _gen.Siembra
SIEMBRA_DEMO = _gen.SIEMBRA_DEMO
OFFSET_DEFAULT = _gen.OFFSET_DEFAULT
SERIAL_BASE_DEFAULT = _gen.SERIAL_BASE_DEFAULT
dias_laborables = _gen.dias_laborables
envolver = _gen.envolver
generar_checadas = _gen.generar_checadas
plantilla_desde_fixtures = _gen.plantilla_desde_fixtures
quincena = _gen.quincena
repartir = _gen.repartir
ventana_entrada_normal = _gen.ventana_entrada_normal

RUTA_EVENTOS = "/api/v1/asistencia/eventos"


def _poster_httpx(url: str, params: dict, payload: dict):
    return httpx.post(url, params=params, json=payload, timeout=10.0)


def enviar(
    lotes: Sequence[Sequence[dict]],
    url: str,
    cliente: str,
    fuente: str,
    intervalo: float = 0.0,
    poster: Callable[[str, dict, dict], object] | None = None,
) -> tuple[int, int]:
    """
    Postea cada lote y acumula `(recibidos, duplicados)`.

    `poster` es inyectable para que los tests manejen el camino *push* con un
    `TestClient` y sin esperar: es el mismo camino que ejercera el aparato real
    en D-08, y es donde mas facil se rompe la forma del payload.
    """
    enviar_uno = poster or _poster_httpx
    recibidos = duplicados = 0
    for numero, lote in enumerate(lotes):
        if numero and intervalo > 0:
            espera_modulo.sleep(intervalo)
        respuesta = enviar_uno(url, {"cliente": cliente, "fuente": fuente}, envolver(lote))
        # El status ANTES del cuerpo: un 500 o un 502 de un proxy contesta HTML,
        # y `.json()` levantaria un JSONDecodeError que no es httpx.HTTPError y
        # no lo atrapa nadie. El error util es el codigo, no el parseo.
        if respuesta.status_code != 200:
            raise FiscalValidationError(
                f"el endpoint respondio {respuesta.status_code}: {respuesta.text[:200]}"
            )
        cuerpo = respuesta.json()
        recibidos += cuerpo["recibidos"]
        duplicados += cuerpo["duplicados"]
    return recibidos, duplicados


def _argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulador del checador Hikvision (demo D).")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--cliente", default=CLIENTE_DEMO)
    parser.add_argument("--inicio", type=date.fromisoformat, default=None)
    parser.add_argument("--fin", type=date.fromisoformat, default=None)
    parser.add_argument("--offset", default=OFFSET_DEFAULT)
    # `hikvision` NO esta entre las opciones a proposito: etiquetar lo simulado
    # como si viniera del aparato es falsear el origen del dato, y en D-08
    # dejaria de haber forma de distinguir en `GET /eventos` que salio de cada
    # fuente. La honestidad va en el argparse, no solo en el docstring.
    parser.add_argument(
        "--fuente",
        default=FuenteChecada.SIMULADO.value,
        choices=[FuenteChecada.SIMULADO.value, FuenteChecada.CSV.value],
    )
    parser.add_argument("--serial-base", type=int, default=SERIAL_BASE_DEFAULT)
    parser.add_argument("--en-vivo", action="store_true")
    parser.add_argument("--intervalo", type=float, default=5.0)
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Corre el simulador. Devuelve 0, 1 (la API no respondio) o 2 (mal uso).

    TODO lo que imprime, en stdout y en stderr, es ASCII a proposito: la
    consola de Windows es cp1252 y la demo corre en Windows. Un "→" la
    reventaba con UnicodeEncodeError DESPUES de haber posteado todo, y los
    acentos salen mojibake aunque no revienten.
    """
    args = _argumentos(argv)
    horario = HorarioLaboral()
    if bool(args.inicio) != bool(args.fin):
        print("--inicio y --fin van juntos o no van.", file=sys.stderr)
        return 2
    if args.inicio and args.fin < args.inicio:
        print(
            f"El periodo termina antes de empezar: {args.inicio} a {args.fin}.",
            file=sys.stderr,
        )
        return 2
    periodo = (
        Periodo(inicio=args.inicio, fin=args.fin) if args.inicio else quincena(date.today())
    )
    # La GENERACION va dentro del try, no solo el envio: una fecha o una siembra
    # imposible salia como traceback crudo enfrente del cliente.
    try:
        empleados = plantilla_desde_fixtures()
        eventos = generar_checadas(
            empleados, periodo, horario, args.offset, SIEMBRA_DEMO, args.serial_base
        )
    except (FiscalValidationError, ValueError) as exc:
        print(f"No se pudieron generar las checadas: {exc}", file=sys.stderr)
        return 2
    print(
        f"{len(empleados)} empleados | {periodo.inicio} a {periodo.fin} | "
        f"{len(eventos)} checadas | serial {args.serial_base}"
    )

    if args.dry_run:
        print(json.dumps(envolver(eventos), indent=2, ensure_ascii=False))
        return 0

    try:
        lote, vivos = (
            repartir(eventos, periodo, horario, args.limite)
            if args.en_vivo
            else (eventos, ())
        )
    except FiscalValidationError as exc:
        print(f"No se pudo repartir el envio: {exc}", file=sys.stderr)
        return 2
    lotes = [lote] if lote else []
    lotes += [[evento] for evento in vivos]
    if vivos:
        print(f"{len(vivos)} checadas en vivo, una cada {args.intervalo} s.")
    url = f"{args.api}{RUTA_EVENTOS}"
    try:
        recibidos, duplicados = enviar(
            lotes, url, args.cliente, args.fuente, args.intervalo if vivos else 0.0
        )
    except httpx.HTTPError as exc:
        print(f"No se pudo hablar con la API en {url}: {exc}", file=sys.stderr)
        return 1
    except FiscalValidationError as exc:
        print(f"La API rechazo el envio: {exc}", file=sys.stderr)
        return 1
    print(f"recibidos={recibidos} duplicados={duplicados}")
    if duplicados and not recibidos:
        print(
            "Todo llego duplicado: el almacen ya tenia estos serialNo. "
            "Vuelve a correr con --serial-base distinto.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
