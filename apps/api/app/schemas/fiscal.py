"""
Schemas de datos fiscales — el contrato entre Fiscalito/Otter y el Fiscal Agent.

Estos schemas definen EXACTAMENTE que datos necesitan mandar las apps cliente
para que el Agent pueda calcular declaraciones. Cuando actualices Fiscalito,
estos schemas te dicen que campos agregar al UserModel y CfdiModel.
"""

from __future__ import annotations
import re
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import date

# Patron RFC: 3-4 letras (incluye Ñ y &) + 6 digitos + 3 alfanumericos
_RFC_PATTERN = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


# ============================================================
# Enums — Catalogos del SAT
# ============================================================

class RegimenFiscal(str, Enum):
    """Regimenes fiscales principales para personas fisicas."""
    RESICO = "626"
    ACTIVIDAD_EMPRESARIAL = "612"
    HONORARIOS = "612"  # Mismo codigo, se distingue por actividad
    SUELDOS_SALARIOS = "605"
    ARRENDAMIENTO = "606"
    PLATAFORMAS_TECNOLOGICAS = "625"
    RIF = "621"  # Regimen de Incorporacion Fiscal (en extincion)


class TipoFactura(str, Enum):
    INGRESO = "I"
    EGRESO = "E"
    TRASLADO = "T"
    PAGO = "P"


class PeriodicidadDeclaracion(str, Enum):
    MENSUAL = "mensual"
    BIMESTRAL = "bimestral"
    ANUAL = "anual"


class ContributorType(str, Enum):
    """Tipo de contribuyente en el ecosistema Fiscalito."""
    ASALARIADO = "asalariado"
    INDEPENDIENTE = "independiente"
    ARRENDAMIENTO = "arrendamiento"
    PLATAFORMAS = "plataformas"
    PYME = "pyme"


# ============================================================
# Perfil del contribuyente
# ============================================================

class PerfilContribuyente(BaseModel):
    """
    Datos del contribuyente necesarios para calcular declaraciones.

    Fiscalito hoy tiene: rfc, regimenFiscalCodigo, regimenFiscalNombre.
    Campos nuevos que necesitara agregar: tipo_persona, actividad_economica,
    periodicidad, tiene_empleados, retenedor_iva.
    """
    rfc: str = Field(..., description="RFC del contribuyente (12-13 caracteres)")
    regimen: str = Field(..., description="Codigo del regimen fiscal SAT (ej: '626' para RESICO)")
    nombre: str = Field(default="", description="Nombre del contribuyente (opcional)")

    @field_validator("rfc")
    @classmethod
    def validar_rfc(cls, v: str) -> str:
        """Valida formato de RFC mexicano: 3-4 letras + 6 digitos + 3 alfanumericos."""
        v = v.upper().strip()
        if not _RFC_PATTERN.match(v):
            raise ValueError(
                f"RFC invalido: '{v}'. Formato esperado: 3-4 letras + 6 digitos + 3 caracteres alfanumericos."
            )
        return v
    tipo_persona: str = Field(default="fisica", description="'fisica' o 'moral'")
    actividad_economica: str = Field(default="", description="Clave de actividad economica SAT")
    periodicidad: PeriodicidadDeclaracion = Field(
        default=PeriodicidadDeclaracion.MENSUAL,
        description="Periodicidad de declaracion segun regimen"
    )
    tiene_empleados: bool = Field(default=False)
    retenedor_iva: bool = Field(default=False)
    fecha_inicio_actividades: date | None = Field(
        default=None, description="Fecha de inicio de actividades ante el SAT"
    )
    contributor_type: ContributorType | None = Field(
        default=None, description="Tipo de contribuyente: asalariado, independiente, arrendamiento, plataformas, pyme"
    )


# ============================================================
# Factura CFDI
# ============================================================

class CFDI(BaseModel):
    """
    Datos de una factura CFDI necesarios para calculos fiscales.

    Fiscalito hoy tiene: uuid, folio, emisor, rfcEmisor, rfcReceptor, monto, fecha, tipo.
    Campos NUEVOS que necesitara agregar: subtotal, iva_trasladado, iva_retenido,
    isr_retenido, descuento, uso_cfdi.
    """
    uuid: str = Field(..., description="Folio fiscal UUID del CFDI")
    fecha: date = Field(..., description="Fecha de emision")
    tipo: TipoFactura = Field(..., description="Tipo de comprobante: I=Ingreso, E=Egreso")
    rfc_emisor: str = Field(..., description="RFC de quien emite la factura")
    rfc_receptor: str = Field(..., description="RFC de quien recibe la factura")
    subtotal: float = Field(..., description="Subtotal antes de impuestos")
    total: float = Field(..., description="Monto total de la factura")
    iva_trasladado: float = Field(default=0.0, description="IVA trasladado (16%)")
    iva_retenido: float = Field(default=0.0, description="IVA retenido (2/3 del IVA)")
    isr_retenido: float = Field(default=0.0, description="ISR retenido por el receptor")
    descuento: float = Field(default=0.0, description="Descuento aplicado")
    uso_cfdi: str = Field(default="G03", description="Clave de uso CFDI (G03=Gastos en general)")
    descripcion: str = Field(default="", description="Descripcion o concepto principal")
    clave_prod_serv: str = Field(default="", description="Clave de producto/servicio del catalogo SAT (8 digitos)")
    metodo_pago: str = Field(default="PUE", description="Metodo de pago: PUE o PPD")
    uuid_relacionado: str | None = Field(default=None, description="UUID del CFDI original al que hace referencia un complemento de pago tipo P")
    monto_pago: float | None = Field(default=None, description="Monto efectivamente pagado (solo para complementos tipo P)")

    @property
    def es_ingreso(self) -> bool:
        return self.tipo == TipoFactura.INGRESO

    @property
    def es_egreso(self) -> bool:
        return self.tipo == TipoFactura.EGRESO

    @property
    def base_gravable(self) -> float:
        """Subtotal menos descuentos — la base para calcular impuestos."""
        return self.subtotal - self.descuento
