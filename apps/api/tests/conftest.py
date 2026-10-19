"""
Shared fixtures para los tests del Fiscal Agent API.

Este archivo es ADITIVO: no mueve ni reemplaza helpers existentes
en los archivos de test individuales. Provee fixtures reutilizables
de pytest para datos comunes (perfiles, facturas).
"""

from datetime import date
from pathlib import Path

import pytest

from app.schemas.fiscal import (
    CFDI,
    PerfilContribuyente,
    PeriodicidadDeclaracion,
    TipoFactura,
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


# ============================================================
# Fixtures de nómina (S-04) — caso real anonimizado
# ============================================================

_FIXTURES_NOMINA = Path(__file__).parent / "fixtures" / "nomina"


@pytest.fixture
def nomina_bimestre() -> list[Path]:
    """Los 70 CFDI de nómina del bimestre marzo-abril, en orden cronológico."""
    return sorted(_FIXTURES_NOMINA.glob("semana-*/*.xml"))


@pytest.fixture
def nomina_por_semana() -> dict[str, list[Path]]:
    """Los CFDI agrupados por semana: 9, 9, 9, 8, 7, 7, 7, 7, 7."""
    return {
        carpeta.name: sorted(carpeta.glob("*.xml"))
        for carpeta in sorted(_FIXTURES_NOMINA.glob("semana-*"))
    }


# ============================================================
# Fixtures — plan P: base de datos y API autenticada
# ============================================================
#
# `db_sesion` da un SQLite en memoria con todas las tablas, aislado por test.
# `api` da un TestClient cuyo `obtener_db` usa ese SQLite y cuyo usuario autenticado
# es el que se le pida: `api("uid-a")`. Así se prueba multi-tenant sin Firebase.

from collections.abc import Callable, Iterator  # noqa: E402

from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


@pytest.fixture
def sesionador() -> Iterator[sessionmaker]:
    """Fábrica de sesiones sobre un SQLite en memoria con el esquema completo."""
    from sqlalchemy import create_engine, event

    import app.modelos  # noqa: F401
    from app.db.base import Base

    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(motor, "connect")
    def _fk(conexion, _registro):  # type: ignore[no-untyped-def]
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    yield sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    motor.dispose()


@pytest.fixture
def db_sesion(sesionador: sessionmaker) -> Iterator[Session]:
    """Una sesión lista para usar en tests de dominio."""
    sesion = sesionador()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def api(sesionador: sessionmaker) -> Iterator[Callable[[str], object]]:
    """`api("uid")` → TestClient autenticado como ese uid, sobre el SQLite del test."""
    from fastapi.testclient import TestClient

    from app.auth_firebase import usuario_actual
    from app.db.session import obtener_db
    from app.integraciones import registro
    from app.main import app

    def _db() -> Iterator[Session]:
        sesion = sesionador()
        try:
            yield sesion
            sesion.commit()
        except Exception:
            sesion.rollback()
            raise
        finally:
            sesion.close()

    clientes: dict[str, TestClient] = {}

    def _fabrica(uid: str = "uid-prueba") -> TestClient:
        if uid not in clientes:
            sub = TestClient(app)
            sub.headers.update({"Authorization": f"Bearer {uid}"})
            clientes[uid] = sub
        return clientes[uid]

    app.dependency_overrides[obtener_db] = _db

    from fastapi import Header

    def _usuario(authorization: str | None = Header(default=None)) -> str:
        # Mismas reglas de formato que producción (401 sin encabezado o mal
        # formado); sólo se salta la verificación criptográfica del token.
        from app.auth_firebase import token_del_encabezado

        return token_del_encabezado(authorization)

    app.dependency_overrides[usuario_actual] = _usuario
    registro.limpiar_cache()
    try:
        yield _fabrica
    finally:
        app.dependency_overrides.pop(obtener_db, None)
        app.dependency_overrides.pop(usuario_actual, None)
        registro.limpiar_cache()
