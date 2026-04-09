"""
Schemas de request/response para los endpoints de declaraciones.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from app.schemas.fiscal import PerfilContribuyente, CFDI


# ============================================================
# Requests
# ============================================================

class PreDeclaracionRequest(BaseModel):
    """
    Request para generar una pre-declaracion (mensual, bimestral o anual).
    El cliente manda perfil + facturas del periodo y el Agent devuelve
    los calculos con explicaciones.
    """
    contribuyente: PerfilContribuyente
    facturas: list[CFDI] = Field(..., description="Facturas del periodo a declarar")
    periodo_year: int = Field(..., description="Anio del periodo (ej: 2025)")
    periodo_month: int | None = Field(
        default=None,
        description="Mes del periodo (1-12). None para declaracion anual."
    )
    periodo_bimestre: int | None = Field(
        default=None,
        description="Bimestre (1-6). Solo para RESICO bimestral."
    )
    pagos_provisionales_anteriores: float = Field(
        default=0.0,
        ge=0,
        description="ISR de pagos provisionales ya efectuados en meses anteriores del mismo ejercicio. "
                    "Solo aplica para regimen 612 y 606 en meses posteriores a enero."
    )
    ingresos_acumulados_anteriores: float = Field(
        default=0.0,
        description="Ingresos gravados acumulados de meses anteriores del ejercicio (Art. 106). "
                    "Solo para regimen 612/606. Se suman a los ingresos del mes actual."
    )
    deducciones_acumuladas_anteriores: float = Field(
        default=0.0,
        description="Deducciones autorizadas acumuladas de meses anteriores del ejercicio (Art. 106). "
                    "Solo para regimen 612/606. Se suman a las deducciones del mes actual."
    )
    predial_pagado: float = Field(
        default=0.0,
        ge=0,
        description="Impuesto predial pagado en el periodo. Solo aplica para regimen 606 (arrendamiento) con deduccion ciega."
    )
    incluir_explicacion: bool = Field(
        default=True,
        description="Si es True, incluye explicacion en lenguaje natural de cada calculo"
    )


# ============================================================
# Responses
# ============================================================

class DesgloseFiscal(BaseModel):
    """Desglose numerico de una declaracion."""
    # Ingresos
    total_ingresos_facturados: float = Field(description="Suma de subtotales de facturas de ingreso")
    total_ingresos_gravados: float = Field(description="Ingresos gravados (despues de descuentos)")
    cantidad_facturas_ingreso: int = 0

    # Egresos / Deducciones
    total_egresos: float = Field(default=0, description="Suma de facturas de egreso (gastos)")
    total_deducciones_autorizadas: float = Field(default=0, description="Deducciones que aplican al regimen")
    cantidad_facturas_egreso: int = 0

    # ISR
    base_isr: float = Field(description="Base gravable para ISR")
    tasa_isr: float = Field(description="Tasa de ISR aplicada (decimal, ej: 0.0125 = 1.25%)")
    isr_causado: float = Field(description="ISR a cargo antes de retenciones")
    isr_retenido: float = Field(default=0, description="ISR que ya te retuvieron terceros")
    isr_a_pagar: float = Field(description="ISR neto a pagar (causado - retenido)")

    # IVA
    iva_trasladado_cobrado: float = Field(default=0, description="IVA que cobraste a clientes")
    iva_trasladado_pagado: float = Field(default=0, description="IVA que pagaste en gastos (acreditable)")
    iva_retenido: float = Field(default=0, description="IVA que te retuvieron terceros")
    iva_a_pagar: float = Field(description="IVA neto: cobrado - pagado - retenido")

    # Arrendamiento — deduccion ciega
    deduccion_ciega_aplicada: bool = Field(default=False, description="Si se uso la deduccion ciega del 35%")
    comparacion_deduccion: str | None = Field(default=None, description="Explicacion de cual opcion convino")

    # Pagos provisionales Art. 106
    pagos_provisionales_anteriores: float = Field(default=0, description="ISR de pagos provisionales de meses anteriores (Art. 106)")
    ingresos_acumulados: float = Field(default=0, description="Ingresos acumulados ene-mes (Art. 106). Solo para 612/606 con tabla acumulada.")
    deducciones_acumuladas: float = Field(default=0, description="Deducciones acumuladas ene-mes (Art. 106). Solo para 612/606 con tabla acumulada.")

    # Gastos personales excluidos (Art. 105 LISR)
    gastos_personales_excluidos: float = Field(default=0, description="Monto de gastos excluidos por ser personales (no deducibles)")
    cantidad_gastos_personales: int = Field(default=0, description="Numero de facturas excluidas como gastos personales")

    # Plataformas — retenciones definitivas
    retenciones_definitivas: bool = Field(default=False, description="Si aplican retenciones como pago definitivo")
    ingreso_anualizado_estimado: float = Field(default=0, description="Ingreso anualizado estimado")

    # Total
    total_a_pagar: float = Field(description="ISR + IVA totales a pagar")


class PreDeclaracionResponse(BaseModel):
    """Respuesta completa de una pre-declaracion."""
    exito: bool = True
    tipo_declaracion: str = Field(description="'mensual', 'bimestral' o 'anual'")
    periodo: str = Field(description="Descripcion del periodo (ej: 'Enero 2025')")
    regimen: str = Field(description="Nombre del regimen fiscal aplicado")
    desglose: DesgloseFiscal
    explicacion: str | None = Field(
        default=None,
        description="Explicacion en lenguaje natural de como se llego a estos numeros"
    )
    advertencias: list[str] = Field(
        default_factory=list,
        description="Alertas: facturas sospechosas, deducciones faltantes, etc."
    )
    recomendaciones: list[str] = Field(
        default_factory=list,
        description="Sugerencias para optimizar la carga fiscal"
    )


class ErrorResponse(BaseModel):
    """Respuesta de error estandar."""
    exito: bool = False
    error: str
    detalle: str | None = None
