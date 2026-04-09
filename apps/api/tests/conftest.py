"""
Shared fixtures para los tests del Fiscal Agent API.

Este archivo es ADITIVO: no mueve ni reemplaza helpers existentes
en los archivos de test individuales. Provee fixtures reutilizables
de pytest para datos comunes (perfiles, facturas).
"""

import pytest
from datetime import date

from app.schemas.fiscal import (
    PerfilContribuyente,
    CFDI,
    TipoFactura,
    PeriodicidadDeclaracion,
)


# ============================================================
# Fixtures — perfiles de contribuyente
# ============================================================

@pytest.fixture
def perfil_resico_fixture() -> PerfilContribuyente:
    """Perfil RESICO generico para tests."""
    return PerfilContribuyente(
        rfc="CAUA030101ABC",
        regimen="626",
        nombre="Timmy Freelancer",
        periodicidad=PeriodicidadDeclaracion.MENSUAL,
    )


@pytest.fixture
def perfil_empresarial_fixture() -> PerfilContribuyente:
    """Perfil Actividad Empresarial generico para tests."""
    return PerfilContribuyente(
        rfc="GOPE900515XYZ",
        regimen="612",
        nombre="Pedro Gonzalez",
        periodicidad=PeriodicidadDeclaracion.MENSUAL,
    )


@pytest.fixture
def perfil_arrendamiento_fixture() -> PerfilContribuyente:
    """Perfil Arrendamiento generico para tests."""
    return PerfilContribuyente(
        rfc="ARRE800101ABC",
        regimen="606",
        nombre="Arrendador Test",
        periodicidad=PeriodicidadDeclaracion.MENSUAL,
    )


# ============================================================
# Fixtures — facturas CFDI de ejemplo
# ============================================================

@pytest.fixture
def factura_ingreso_fixture() -> CFDI:
    """Factura de ingreso PUE basica."""
    return CFDI(
        uuid="TEST-ING-001",
        fecha=date(2026, 1, 10),
        tipo=TipoFactura.INGRESO,
        rfc_emisor="CAUA030101ABC",
        rfc_receptor="EMPRESA_SA_RFC",
        subtotal=15000.00,
        total=17400.00,
        iva_trasladado=2400.00,
        metodo_pago="PUE",
    )


@pytest.fixture
def factura_egreso_fixture() -> CFDI:
    """Factura de egreso PUE basica (gasto recibido)."""
    return CFDI(
        uuid="TEST-EGR-001",
        fecha=date(2026, 1, 15),
        tipo=TipoFactura.INGRESO,
        rfc_emisor="PROVEEDOR_RFC",
        rfc_receptor="CAUA030101ABC",
        subtotal=5000.00,
        total=5800.00,
        iva_trasladado=800.00,
        metodo_pago="PUE",
    )
