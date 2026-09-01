"""
Fixtures de asistencia.

El almacén es un objeto global del proceso, así que sin limpiarlo entre tests
el resultado depende del orden en que corran — y un verde así no significa
nada. La fixture es `autouse` a propósito: olvidarla en un test nuevo sería
justo el modo de falla que buscamos evitar.
"""

import pytest
from fastapi.testclient import TestClient

from app.asistencia.almacen import almacen
from app.main import app


@pytest.fixture(autouse=True)
def _almacen_limpio():
    almacen.reset()
    yield
    almacen.reset()


@pytest.fixture
def cliente_http() -> TestClient:
    return TestClient(app)
