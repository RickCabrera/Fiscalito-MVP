"""
Una nómina CERRADA sembrada por la API, con fichas de pago y contacto (P4-12, P4-13).

Datos sintéticos: nombres, cuentas y CLABE inventados (la CLABE con su verificador bien
calculado, para que pase la validación como pasaría una real).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.contabilidad import catalogo
from app.dispersion.clabe import digito_verificador
from app.modelos.conciliacion import CuentaBancaria
from app.modelos.nucleo import Cliente
from tests.nomina.cartera_sembrada import sembrar_cliente

QUINCENA = {"inicio": "2026-08-16", "fin": "2026-08-31"}


def clabe(banco: str, cuenta: str, plaza: str = "180") -> str:
    """CLABE sintética con verificador correcto: banco 3 + plaza 3 + cuenta 11 + dígito."""
    primeros = f"{banco}{plaza}{cuenta.rjust(11, '0')}"
    return primeros + str(digito_verificador(primeros))


def emp(no: str, diario: str = "500.00", **extra: Any) -> dict[str, Any]:
    return {"empleado_no": no, "nombre": f"PERSONA {no}", "salario_diario": diario,
            "salario_diario_integrado": str(round(float(diario) * 1.05, 2)), **extra}


EMPLEADOS = [
    # Banamex, cuenta propia sucursal 4 + cuenta 7; con apellidos.
    emp("E1", nombres="ANA", apellido_paterno="MUÑOZ", apellido_materno="LOPEZ",
        banco="002", numero_cuenta="12345678901", correo="ana@ejemplo.mx",
        celular="55 1234 5678", consentimiento_whatsapp=True),
    # BBVA por CLABE, con apellidos (interbancario para Banamex/Banorte).
    emp("E2", "650.00", nombres="LUIS", apellido_paterno="PEREZ", apellido_materno="DIAZ",
        clabe=clabe("012", "1234567890"), correo="luis@ejemplo.mx", celular="+525511112222"),
    emp("E3", forma_pago="efectivo", correo="e3@ejemplo.mx"),  # efectivo
    emp("E4"),  # sin cuenta ni contacto
    # Banorte por CLABE, sin apellidos separados.
    emp("E5", "720.50", clabe=clabe("072", "9876543210"), celular="5599998888",
        consentimiento_whatsapp=True),
]


def nomina_cerrada(api: Any, sesionador: Any, uid: str = "uid-disp", clave: str = "disp",
                   empleados: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Siembra, calcula y cierra. Devuelve http, clave, periodo_id y las cuentas de cargo."""
    http = api(uid)
    lista = empleados if empleados is not None else EMPLEADOS
    sembrar_cliente(http, clave, lista)
    r = http.post("/api/v1/nomina/calcular-periodo", json={
        "cliente": clave, "periodo": QUINCENA,
        "incidencias": [{"empleado_no": e["empleado_no"], "dias_periodo": 16, "faltas": 0,
                         "dias_ausentismo": 0} for e in lista]})
    assert r.status_code == 200, r.text
    pid = r.json()["periodo_id"]
    assert http.post(f"/api/v1/nomina/clientes/{clave}/periodos/{pid}/cerrar").status_code == 200
    s = sesionador()
    cli = s.scalar(select(Cliente).where(Cliente.despacho_id == uid, Cliente.clave == clave))
    catalogo.sembrar_base(s, cli)
    contable = catalogo.por_numero(s, cli)["102.01.01"].id
    cuentas = {}
    for banco, numero in (("002", "70001234567"), ("072", "0123456789"), ("012", "0987654321"),
                          ("014", "65501234567"), ("021", "4001234567"),
                          ("044", "01234567890"), ("030", "1234567890")):
        cb = CuentaBancaria(cliente_id=cli.id, banco=banco, nombre=f"Nómina {banco}",
                            numero=numero, cuenta_contable_id=contable)
        s.add(cb)
        s.flush()
        cuentas[banco] = cb.id
    s.commit()
    s.close()
    return {"http": http, "clave": clave, "pid": pid, "cuentas": cuentas,
            "netos": {x["empleado_no"]: x["neto"] for x in r.json()["recibos"]}}
