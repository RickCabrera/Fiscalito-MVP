"""
Datos de pago y de contacto del empleado (P4-12 dispersión, P4-13 envío de recibos).

Viven en un mixin para que `EmpleadoCarteraSchema` sólo cambie su clase base: la ficha la
tocan varias tareas a la vez y así cada una agrega su bloque sin pisar a la otra.

TODO ES OPCIONAL Y NADA SE INVENTA
----------------------------------
Una ficha escrita antes de P4-12 sigue siendo válida: sin cuenta, el empleado queda fuera de
la dispersión **con su motivo** en el reporte de excluidos, nunca con una cuenta en blanco.

- `clabe`: 18 dígitos con dígito verificador de Banxico (`app/dispersion/clabe.py`). Una
  CLABE que no cuadra se RECHAZA, no se corrige.
- `banco`: clave `c_Banco` de 3 dígitos. Si llega CLABE y no banco, se toma de la CLABE; si
  llegan los dos y no coinciden, se rechaza (una de las dos está mal).
- `numero_cuenta`: cuenta (10 a 12 dígitos según el banco) o tarjeta (16) del MISMO banco.
- `celular`: E.164 mexicano, `+52` y 10 dígitos. Se aceptan 10 dígitos sueltos (se les pone
  `+52`) y el prefijo móvil viejo `+521` (se quita: desde 2019 no se marca).
- `consentimiento_whatsapp`: sin él no se manda nada por WhatsApp, aunque haya celular.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.dispersion.clabe import banco_de_clabe, motivo_clabe_invalida

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormaPagoEmpleado(str, Enum):
    """Cómo se le paga el neto. Sólo `transferencia` entra a la dispersión."""

    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"
    CHEQUE = "cheque"


def normalizar_celular(valor: str) -> str:
    """`+52` + 10 dígitos, o `ValueError` con el motivo. Vacío se queda vacío."""
    limpio = re.sub(r"[\s\-().]", "", valor or "")
    if limpio == "":
        return ""
    if re.fullmatch(r"\d{10}", limpio):
        return f"+52{limpio}"
    if re.fullmatch(r"52\d{10}", limpio):
        return f"+{limpio}"
    if re.fullmatch(r"\+521\d{10}", limpio):
        return f"+52{limpio[4:]}"
    if re.fullmatch(r"\+52\d{10}", limpio):
        return limpio
    raise ValueError(
        f"El celular {valor!r} no es un número mexicano E.164: van +52 y 10 dígitos "
        "(p. ej. +525512345678)."
    )


class DatosPagoContactoSchema(BaseModel):
    """Cuenta para la dispersión y contacto para los recibos."""

    forma_pago: FormaPagoEmpleado = Field(
        default=FormaPagoEmpleado.TRANSFERENCIA,
        description="P4-12: transferencia | efectivo | cheque. Efectivo y cheque no se dispersan.",
    )
    banco: str = Field(default="", pattern=r"^(\d{3})?$",
                       description="P4-12: clave c_Banco (3 dígitos). Vacío = la de la CLABE.")
    clabe: str = Field(default="", description="P4-12: CLABE de 18 dígitos (verificador Banxico).")
    numero_cuenta: str = Field(
        default="", pattern=r"^(\d{10,12}|\d{16})?$",
        description="P4-12: cuenta (10-12 dígitos) o tarjeta (16) del mismo banco.",
    )
    correo: str = Field(default="", max_length=254, description="P4-13: correo para recibos.")
    celular: str = Field(default="", description="P4-13: E.164 mexicano (+52 y 10 dígitos).")
    consentimiento_whatsapp: bool = Field(
        default=False, description="P4-13: el trabajador aceptó recibir sus recibos por WhatsApp."
    )

    @field_validator("clabe")
    @classmethod
    def _clabe_valida(cls, valor: str) -> str:
        limpio = re.sub(r"\s", "", valor or "")
        if limpio == "":
            return ""
        motivo = motivo_clabe_invalida(limpio)
        if motivo:
            raise ValueError(motivo)
        return limpio

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, valor: str) -> str:
        limpio = (valor or "").strip()
        if limpio and not _CORREO.match(limpio):
            raise ValueError(f"El correo {limpio!r} no tiene forma de correo.")
        return limpio

    @field_validator("celular")
    @classmethod
    def _celular_e164(cls, valor: str) -> str:
        return normalizar_celular(valor)

    @model_validator(mode="after")
    def _coherencia(self) -> DatosPagoContactoSchema:
        if self.clabe:
            del_clabe = banco_de_clabe(self.clabe)
            if self.banco and self.banco != del_clabe:
                raise ValueError(
                    f"El banco capturado ({self.banco}) no es el de la CLABE ({del_clabe}): "
                    "una de las dos está mal."
                )
            if not self.banco:
                self.banco = del_clabe
        if self.consentimiento_whatsapp and not self.celular:
            raise ValueError("El consentimiento de WhatsApp necesita un celular capturado.")
        return self
