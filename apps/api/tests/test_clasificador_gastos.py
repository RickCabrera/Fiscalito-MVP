"""
Tests para el clasificador automatico de deducibilidad.
Ejecutar: pytest tests/test_clasificador_gastos.py -v
"""

from datetime import date
from app.schemas.fiscal import CFDI, TipoFactura
from app.fiscal_engine.clasificador_gastos import (
    es_gasto_deducible,
    obtener_division,
    inferir_actividad_contribuyente,
    clasificar_egresos,
)


class TestClasificadorGastos:

    def test_alimentos_no_deducible_para_servicios(self):
        """Comisionista (div 80) no puede deducir alimentos (div 50)."""
        assert es_gasto_deducible("50202200", {"80"}) is False

    def test_alimentos_si_deducible_para_restaurantero(self):
        """Restaurantero (div 90) SI puede deducir alimentos (div 50)."""
        assert es_gasto_deducible("50202200", {"90"}) is True

    def test_contador_siempre_deducible(self):
        """Servicios contables (div 84) siempre deducibles."""
        assert es_gasto_deducible("84111802", {"80"}) is True

    def test_medicinas_no_deducible(self):
        """Medicamentos (div 51) no deducibles para comisionista."""
        assert es_gasto_deducible("51172100", {"80"}) is False

    def test_colchon_no_deducible(self):
        """Colchon (div 56) no deducible para comisionista."""
        assert es_gasto_deducible("56101508", {"80"}) is False

    def test_estacionamiento_siempre_deducible(self):
        """Estacionamiento (div 78) siempre deducible."""
        assert es_gasto_deducible("78111807", {"80"}) is True

    def test_energia_siempre_deducible(self):
        """Energia solar (div 26) siempre deducible."""
        assert es_gasto_deducible("26111607", {"80"}) is True

    def test_sin_clave_beneficio_duda(self):
        """Sin ClaveProdServ -> beneficio de la duda (deducible)."""
        assert es_gasto_deducible("", {"80"}) is True

    def test_division_gris_default_deducible(self):
        """Division no clasificada -> beneficio de la duda."""
        assert es_gasto_deducible("72153600", {"80"}) is True

    def test_caso_real_comisionista(self):
        """Simular el caso del cliente CADG620317EE0."""
        # Factura emitida (para inferir actividad)
        ingreso = CFDI(
            uuid="E1", fecha=date(2026, 1, 5), tipo=TipoFactura.INGRESO,
            rfc_emisor="AAA", rfc_receptor="BBB",
            subtotal=208_104.35, total=219_203.18,
            clave_prod_serv="80141600",  # Comisionista
        )

        # Gastos
        gastos = [
            # Deducibles
            CFDI(
                uuid="G1", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="BBB", rfc_receptor="AAA",
                subtotal=50_180, total=50_180,
                clave_prod_serv="80131500",  # Arrendamiento -> deducible
            ),
            CFDI(
                uuid="G2", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="BBB", rfc_receptor="AAA",
                subtotal=583.62, total=677,
                clave_prod_serv="78111807",  # Estacionamiento -> deducible
            ),
            # No deducibles
            CFDI(
                uuid="G3", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="BBB", rfc_receptor="AAA",
                subtotal=1_000, total=1_160,
                clave_prod_serv="50202200",  # Tequila -> personal
            ),
            CFDI(
                uuid="G4", fecha=date(2026, 1, 1), tipo=TipoFactura.INGRESO,
                rfc_emisor="BBB", rfc_receptor="AAA",
                subtotal=90_000, total=104_400,
                clave_prod_serv="56101508",  # Colchon -> personal
            ),
        ]

        deducibles, personales, excluido = clasificar_egresos(gastos, [ingreso])
        assert len(deducibles) == 2
        assert len(personales) == 2
        assert excluido == 91_000  # tequila + colchon
