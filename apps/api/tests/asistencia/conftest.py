"""
Fixtures de asistencia.

El almacén es un objeto global del proceso, así que sin limpiarlo entre tests
el resultado depende del orden en que corran — y un verde así no significa
nada. La fixture es `autouse` a propósito: olvidarla en un test nuevo sería
justo el modo de falla que buscamos evitar.
"""

import pytest

from app.asistencia.almacen import almacen


@pytest.fixture(autouse=True)
def _almacen_limpio():
    almacen.reset()
    yield
    almacen.reset()


# `cliente_http` viene de tests/conftest.py: autenticado (P0-02) y sobre SQLite.
