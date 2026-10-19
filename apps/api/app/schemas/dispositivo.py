"""
Dispositivos biométricos (checadores) de un cliente. (R-04, R-09 → P0-01)

Misma forma que ya escribía el front en Firestore (`DispositivoChecador` en
`apps/store/src/services/dispositivosApi.ts`) y las mismas reglas que
`validarDispositivo` aplica en el formulario, para que ningún camino acepte lo que el
otro rechaza.

LA IP SE REGISTRA, NO SE CONSULTA
---------------------------------
Es un dato de ficha para que el técnico sepa dónde está el aparato. Nada en el backend
se conecta a ella (hablar ISAPI con el equipo es D-08 / EXT-15).

`employee_nos` SON LLAVES DEL CHECADOR, NO DEL CÁLCULO
------------------------------------------------------
Guardan `employee_no` (el número en el aparato), no `empleado_no`. Fundir las dos llaves
es el defecto que G-02 vino a arreglar.
"""

from __future__ import annotations

import ipaddress

from pydantic import BaseModel, Field, field_validator


class DispositivoSchema(BaseModel):
    """Un checador tal como lo captura el despacho. El `id` va en la URL, no aquí."""

    nombre: str = Field(min_length=1, max_length=120)
    ip: str = Field(default="", max_length=15, description="IPv4 o vacío (no se conoce).")
    puerto: int = Field(default=80, ge=1, le=65535)
    marca: str = Field(default="Hikvision", max_length=60)
    modelo: str = Field(default="", max_length=60)
    serial: str = Field(default="", max_length=60)
    employee_nos: list[str] = Field(
        default_factory=list,
        max_length=5_000,
        description="`employee_no` (llave del CHECADOR) de quienes están enrolados.",
    )
    notas: str = Field(default="", max_length=2_000)

    @field_validator("nombre", "serial", "ip", mode="before")
    @classmethod
    def _sin_espacios(cls, valor: object) -> object:
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, valor: str) -> str:
        if not valor:
            raise ValueError("Ponle un nombre que sirva para encontrarlo.")
        return valor

    @field_validator("ip")
    @classmethod
    def _ipv4_o_vacia(cls, valor: str) -> str:
        """Cuatro octetos de 0 a 255 de verdad: `999.1.1.1` no es una dirección."""
        if valor == "":
            return valor
        try:
            ipaddress.IPv4Address(valor)
        except ValueError as exc:
            raise ValueError(f"{valor!r} no es una dirección IPv4.") from exc
        return valor

    @field_validator("employee_nos")
    @classmethod
    def _llaves_limpias(cls, valor: list[str]) -> list[str]:
        """
        Sin vacíos ni repetidos. Un `""` guardado aquí sería un enrolado fantasma
        permanente: nunca casa con nadie y nunca desaparece.
        """
        limpias: list[str] = []
        for llave in valor:
            llave = llave.strip()
            if llave and llave not in limpias:
                limpias.append(llave)
        return limpias


class DispositivosResponse(BaseModel):
    exito: bool = True
    cliente_id: str
    total: int
    dispositivos: tuple[dict, ...] = Field(
        description="Los dispositivos tal como están guardados, con su `id`. No se tipan "
        "estrictamente al leer, por la misma razón que los clientes: uno traído de "
        "Firestore por la migración puede tener campos que este modelo no conoce."
    )


class DispositivoGuardadoResponse(BaseModel):
    exito: bool = True
    id: str
    mensaje: str
