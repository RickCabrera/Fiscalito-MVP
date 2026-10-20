"""
Siembra un cliente y su plantilla en la cartera SQL por la API. (P4-01)

Desde P4-01 `POST /nomina/calcular-periodo` exige autenticación y lee la plantilla
de la cartera del despacho: los tests de la ruta ya no pueden mandarla en el cuerpo,
la tienen que sembrar. Se siembra por los endpoints de `/cartera/*` —no escribiendo
la base a mano— para que el camino sea el mismo que recorre la pantalla.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

UID = "uid-prueba"  # el mismo `UID_PRUEBA` de tests/conftest.py: asistencia es por despacho


def sembrar_cliente(
    http: Any,
    clave: str,
    empleados: Iterable[Any],
    *,
    prima: str = "0.0054355",
    periodicidad: str = "04",
    criterios: dict[str, str] | None = None,
    parametros: dict[str, Any] | None = None,
    extra_empleado: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Da de alta el cliente y sus empleados. `empleados` acepta EmpleadoPeriodo o dicts."""
    cuerpo: dict[str, Any] = {
        "id": clave,
        "nombre": f"CLIENTE {clave.upper()}",
        "prima_riesgo": prima,
        "clave_periodicidad": periodicidad,
    }
    if criterios:
        cuerpo["criterios_nomina"] = criterios
    if parametros:
        cuerpo["parametros"] = parametros
    r = http.put(f"/api/v1/cartera/clientes/{clave}", json=cuerpo)
    assert r.status_code == 200, r.text
    for e in empleados:
        datos = (
            e
            if isinstance(e, dict)
            else {
                "empleado_no": e.empleado_no,
                "nombre": e.nombre,
                "salario_diario": str(e.salario_diario),
                "salario_diario_integrado": str(e.salario_diario_integrado),
                "zona": e.zona.value,
            }
        )
        datos = {**datos, **(extra_empleado or {}).get(datos["empleado_no"], {})}
        r = http.put(
            f"/api/v1/cartera/clientes/{clave}/empleados/{datos['empleado_no']}", json=datos
        )
        assert r.status_code == 200, r.text


def sembrar_catalogo(http: Any) -> None:
    """Siembra los tres clientes del catálogo de demostración (demo, cafeteria, taller)."""
    from app.despacho_demo import cliente_por_id

    for clave in ("demo", "cafeteria", "taller"):
        c = cliente_por_id(clave)
        assert c is not None
        sembrar_cliente(
            http, clave, c.empleados, prima=str(c.prima_riesgo), periodicidad=c.clave_periodicidad
        )
