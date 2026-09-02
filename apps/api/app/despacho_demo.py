"""
Cartera de clientes del despacho de la demo (épica E). **Demo-only: se borra en F2.**

QUÉ ES ESTO Y QUÉ NO
--------------------
Tres clientes para que la pantalla del contador tenga con qué. **No es una base
de datos de clientes**: es un catálogo estático, sin auth, exactamente como el
resto de la épica D. La persistencia real es F1-09.

DE DÓNDE SALE CADA CLIENTE
--------------------------
- `demo` — el caso real anonimizado de S-04. **Reusa `PLANTILLA_DEMO` de
  `app/demo_nomina.py`, no la copia**: ese módulo es el dueño de esos nueve
  empleados y `tests/nomina/test_plantilla_demo.py` verifica contra las
  fixtures que no diverja. Una tercera copia sería justo la falla que ese test
  existe para evitar.
  **ACOPLAMIENTO A F2:** `demo_nomina.py` está marcado "se borra en F2". Si se
  borra, este módulo se cae con él. Los dos encabezados lo dicen.
- `cafeteria` y `taller` — **sintéticos completos**: personas, salarios y
  fechas inventados. No hay ningún dato de una persona real.

POR QUÉ LOS SDI SON LITERALES Y NO SE CALCULAN AQUÍ
---------------------------------------------------
Para los sintéticos el SDI **sí** se deriva del salario y la antigüedad (no hay
un SDI observado que respetar, a diferencia del caso real de §D9), pero se
escribe como literal y es
`tests/despacho/test_despacho_demo.py` quien comprueba que coincide con lo que
devuelve el motor. Calcularlo en el import tendría dos consecuencias malas:

1. **Deriva temporal.** El factor sube al cruzar un aniversario (Art. 76 LFT), y
   el piso/tope del clamp se mueven el 1-ene y el 1-feb. Un cliente de demo cuyos
   recibos cambian solos de un mes a otro es lo peor que puede pasar enfrente de
   alguien.
2. Un test que reejecuta la función que produjo el dato no prueba nada.

Por eso toda antigüedad, factor y clamp de este módulo se miden contra
`FECHA_REFERENCIA_DEMO`, que es fija, **nunca contra `date.today()`**.

EL `empleado_no` NO SE REPITE ENTRE CLIENTES
--------------------------------------------
`C-01…`, `T-01…` y los `E-01…` de fixtures. El almacén de asistencia es por
cliente, pero `POST /asistencia/eventos` sin `?cliente=` cae en `demo`: con ids
repetidos, una checada del taller aparecería en el panel del cliente equivocado
sin que nada fallara.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.demo_nomina import (
    CLAVE_PERIODICIDAD_DEMO,
    PLANTILLA_DEMO,
    PRIMA_RIESGO_DEMO,
    ZONA_DEMO,
)
from app.nomina_engine.tablas_imss import prima_media_clase

# Fecha contra la que se congelan antigüedad, factor y clamp de los clientes
# sintéticos. Fija a propósito — ver el encabezado.
FECHA_REFERENCIA_DEMO: date = date(2026, 9, 1)


@dataclass(frozen=True)
class EmpleadoCliente:
    """
    Un empleado en la ficha del cliente.

    `fecha_alta` es `None` cuando no se conoce: en el caso real el CFDI timbrado
    no la trae, y **no se inventa**. §D9 advierte que el SDI del caso real no se
    deriva de la antigüedad —los factores implícitos son distintos entre
    empleados y no monótonos—, así que ponerle un alta inventada invitaría a
    comparar factor contra antigüedad y a concluir que el motor está mal.
    """

    empleado_no: str
    nombre: str
    puesto: str
    salario_diario: Decimal
    salario_diario_integrado: Decimal
    fecha_alta: date | None
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL

    @property
    def antiguedad_anios(self) -> int | None:
        """Años cumplidos a `FECHA_REFERENCIA_DEMO`, o `None` si no hay alta."""
        if self.fecha_alta is None:
            return None
        ref, alta = FECHA_REFERENCIA_DEMO, self.fecha_alta
        anios = ref.year - alta.year
        if (ref.month, ref.day) < (alta.month, alta.day):
            anios -= 1
        return anios

    @property
    def factor_implicito(self) -> bool:
        """
        `True` cuando el factor es un cociente OBSERVADO (SDI ÷ SD) y no el de
        ley: puede incluir prestaciones superiores que el CFDI no desglosa, así
        que no es comparable con el factor del Art. 27 LSS.
        """
        return self.fecha_alta is None

    @property
    def factor(self) -> Decimal:
        """SDI ÷ SD, a 4 decimales. Ver `factor_implicito` antes de interpretarlo."""
        return (self.salario_diario_integrado / self.salario_diario).quantize(
            Decimal("0.0001")
        )


@dataclass(frozen=True)
class ClienteDespacho:
    """Un cliente de la cartera. `clase_riesgo` es SUPUESTA — ver el comentario de abajo."""

    id: str
    nombre: str
    giro: str
    origen: str
    prima_riesgo: Decimal
    clave_periodicidad: str
    zona: ZonaSalarioMinimo
    empleados: tuple[EmpleadoCliente, ...]
    clase_riesgo: int | None = None

    @property
    def num_empleados(self) -> int:
        """Derivado, nunca escrito a mano: un literal diverge al agregar gente."""
        return len(self.empleados)


# DECISIÓN PROVISIONAL (nocturno): la clase de riesgo de los dos clientes
# sintéticos es un SUPUESTO, no un dato con fuente. La prima media por clase sí
# está fundada (Art. 73 LSS, `knowledge_base/nomina/22_cuotas_imss_infonavit_2026.md`)
# y se lee del motor con `prima_media_clase()`. Lo que NO se puede citar es la
# asignación giro → clase: sale del catálogo de actividades del RACERF, que no
# está en el repo. Para un cliente real la prima **la autodetermina el patrón
# cada febrero** (Art. 74 LSS) y es dato de entrada, no derivable del giro.
# Ver `docs/decisiones-nomina.md` D22.


def _emp(
    empleado_no: str,
    nombre: str,
    salario_diario: str,
    salario_diario_integrado: str,
    fecha_alta: date,
    puesto: str,
) -> EmpleadoCliente:
    return EmpleadoCliente(
        empleado_no=empleado_no,
        nombre=nombre,
        puesto=puesto,
        salario_diario=Decimal(salario_diario),
        salario_diario_integrado=Decimal(salario_diario_integrado),
        fecha_alta=fecha_alta,
    )


# Los SDI de abajo salen de `sbc_fijo(SD, factor_integracion_de_ley(antigüedad))`
# medido a `FECHA_REFERENCIA_DEMO`, y el test lo verifica contra el motor.
# Los salarios diarios están holgadamente por encima del mínimo (≥ 1.3×) para
# que el clamp del Art. 28 no muerda al cambiar el año.
_CAFETERIA: tuple[EmpleadoCliente, ...] = (
    # 5 anios, factor 1.0548
    _emp(
        "C-01",
        "MARISOL ABREGO QUINTERO",
        "520.00",
        "548.50",
        date(2021, 2, 1),
        "Encargada de tienda",
    ),
    # 2 anios, factor 1.0507
    _emp(
        "C-02",
        "JOEL BARRAGAN QUEZADA",
        "445.00",
        "467.56",
        date(2024, 6, 10),
        "Barista",
    ),
    # 3 anios, factor 1.0521
    _emp(
        "C-03",
        "NADIA CERVANTES QUIROZ",
        "480.00",
        "505.01",
        date(2023, 1, 16),
        "Cocinero",
    ),
    # 0 anios, factor 1.0493
    _emp(
        "C-04",
        "OSCAR DELGADO QUINTANA",
        "420.00",
        "440.71",
        date(2026, 3, 2),
        "Auxiliar de barra",
    ),
)

_TALLER: tuple[EmpleadoCliente, ...] = (
    # 10 anios, factor 1.0562
    _emp(
        "T-01",
        "RAUL ESCOBAR YANEZ",
        "905.00",
        "955.86",
        date(2016, 8, 1),
        "Jefe de taller",
    ),
    # 6 anios, factor 1.0562
    _emp(
        "T-02",
        "SILVIA FIGUEROA YEPEZ",
        "640.00",
        "675.97",
        date(2019, 11, 4),
        "Asesora de servicio",
    ),
    # 8 anios, factor 1.0562
    _emp(
        "T-03",
        "TOMAS GALVAN YUNES",
        "715.00",
        "755.18",
        date(2018, 5, 21),
        "Mecanico A",
    ),
    # 6 anios, factor 1.0562
    _emp(
        "T-04",
        "ULISES HINOJOSA YBARRA",
        "690.00",
        "728.78",
        date(2020, 2, 17),
        "Mecanico A",
    ),
    # 4 anios, factor 1.0534
    _emp(
        "T-05",
        "VERONICA IBARRA YANEZ",
        "575.00",
        "605.71",
        date(2021, 9, 6),
        "Mecanico B",
    ),
    # 4 anios, factor 1.0534
    _emp(
        "T-06",
        "WALTER JUAREZ YRIGOYEN",
        "560.00",
        "589.90",
        date(2022, 3, 14),
        "Mecanico B",
    ),
    # 3 anios, factor 1.0521
    _emp(
        "T-07",
        "XIMENA LARA YSLAS",
        "498.00",
        "523.95",
        date(2023, 7, 3),
        "Hojalatera",
    ),
    # 2 anios, factor 1.0507
    _emp(
        "T-08",
        "YAHIR MEDINA YZAGUIRRE",
        "512.00",
        "537.96",
        date(2023, 10, 16),
        "Pintor",
    ),
    # 2 anios, factor 1.0507
    _emp(
        "T-09",
        "ZOE NAVARRO YAMASAKI",
        "455.00",
        "478.07",
        date(2024, 4, 8),
        "Lavado y detallado",
    ),
    # 1 anio, factor 1.0493
    _emp(
        "T-10",
        "ABEL ORTEGA YERENA",
        "470.00",
        "493.17",
        date(2024, 11, 11),
        "Almacenista",
    ),
    # 1 anio, factor 1.0493
    _emp(
        "T-11",
        "BRENDA PACHECO YURIAR",
        "432.00",
        "453.30",
        date(2025, 6, 2),
        "Auxiliar general",
    ),
    # 0 anios, factor 1.0493
    _emp(
        "T-12",
        "CESAR QUEZADA YEVENES",
        "425.00",
        "445.95",
        date(2026, 1, 19),
        "Auxiliar general",
    ),
)


def _empleados_de_fixtures() -> tuple[EmpleadoCliente, ...]:
    """
    Los nueve de S-04, tomados de `PLANTILLA_DEMO`. Sin alta: no se inventa.

    El puesto tampoco viene en el CFDI del caso; se deja vacío en vez de
    adivinarlo.
    """
    return tuple(
        EmpleadoCliente(
            empleado_no=e.empleado_no,
            nombre=e.nombre,
            puesto="",
            salario_diario=e.salario_diario,
            salario_diario_integrado=e.salario_diario_integrado,
            fecha_alta=None,
            zona=e.zona,
        )
        for e in PLANTILLA_DEMO
    )


CLIENTES: tuple[ClienteDespacho, ...] = (
    ClienteDespacho(
        id="demo",
        nombre="Servicios Administrativos del Golfo",
        giro="Servicios administrativos",
        origen="fixtures-s04",
        # La del caso real: autodeterminada por ese patrón, no prima media.
        prima_riesgo=PRIMA_RIESGO_DEMO,
        clave_periodicidad=CLAVE_PERIODICIDAD_DEMO,
        zona=ZONA_DEMO,
        empleados=_empleados_de_fixtures(),
        clase_riesgo=None,
    ),
    ClienteDespacho(
        id="cafeteria",
        nombre="Cafeteria La Estacion",
        giro="Preparacion de alimentos y bebidas",
        origen="sintetico",
        prima_riesgo=prima_media_clase(2, FECHA_REFERENCIA_DEMO),
        clave_periodicidad="04",
        zona=ZonaSalarioMinimo.GENERAL,
        empleados=_CAFETERIA,
        clase_riesgo=2,
    ),
    ClienteDespacho(
        id="taller",
        nombre="Taller Mecanico Nogal",
        giro="Reparacion de vehiculos automotores",
        origen="sintetico",
        prima_riesgo=prima_media_clase(3, FECHA_REFERENCIA_DEMO),
        clave_periodicidad="04",
        zona=ZonaSalarioMinimo.GENERAL,
        empleados=_TALLER,
        clase_riesgo=3,
    ),
)

_POR_ID: dict[str, ClienteDespacho] = {c.id: c for c in CLIENTES}


def cliente_por_id(cliente_id: str) -> ClienteDespacho | None:
    """El cliente, o `None` si no existe. La ruta traduce el `None` a 404."""
    return _POR_ID.get(cliente_id)
