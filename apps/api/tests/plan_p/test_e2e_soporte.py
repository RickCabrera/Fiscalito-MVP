"""
Lo que el backend agregó para las pruebas de punta a punta (P6-04).

- `FISCALITO_SAT_FALSO_DIR`: el SAT falso entrega los XML de una carpeta, filtrados por
  dirección y fecha, y la descarga los mete a la bóveda como si vinieran del SAT.
- `FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION`: acorta la primera espera (default 2 min).
"""

import io
import zipfile
from datetime import datetime, timedelta

from app.integraciones import registro
from app.integraciones.sat_descarga import DescargaSatFalso, paquetes_de_carpeta
from app.integraciones.sat_soap import ParametrosSolicitud
from app.sat_descarga import servicio
from tests.plan_p.cfdi_sintetico import cfdi, uuid_n


def _carpeta(tmp_path):
    (tmp_path / "emitidos").mkdir()
    (tmp_path / "recibidos").mkdir()
    (tmp_path / "emitidos" / "a.xml").write_bytes(
        cfdi(uuid_n(1), fecha="2026-03-10T10:00:00"))
    (tmp_path / "emitidos" / "b.xml").write_bytes(
        cfdi(uuid_n(2), fecha="2026-04-02T10:00:00"))
    (tmp_path / "recibidos" / "c.xml").write_bytes(
        cfdi(uuid_n(3), fecha="2026-03-15T10:00:00"))
    return tmp_path


def _p(direccion: str, tipo: str = "cfdi") -> ParametrosSolicitud:
    return ParametrosSolicitud(direccion, tipo, datetime(2026, 3, 1), datetime(2026, 3, 31, 23))


def _nombres(zips: list[bytes] | None) -> list[str]:
    assert zips is not None
    return sorted(n for z in zips for n in zipfile.ZipFile(io.BytesIO(z)).namelist())


def test_entrega_por_direccion_y_rango(tmp_path):
    al_solicitar = paquetes_de_carpeta(_carpeta(tmp_path))
    assert _nombres(al_solicitar(_p("emitidos"))) == ["a.xml"]
    assert _nombres(al_solicitar(_p("recibidos"))) == ["c.xml"]


def test_metadata_y_rango_vacio_son_sin_informacion(tmp_path):
    al_solicitar = paquetes_de_carpeta(_carpeta(tmp_path))
    assert al_solicitar(_p("emitidos", "metadata")) is None
    vacio = ParametrosSolicitud("emitidos", "cfdi", datetime(2025, 1, 1), datetime(2025, 1, 31))
    assert al_solicitar(vacio) is None


def test_la_variable_elige_la_carpeta(tmp_path, monkeypatch):
    registro.limpiar_cache()
    monkeypatch.setenv("FISCALITO_SAT_FALSO_DIR", str(_carpeta(tmp_path)))
    sat = registro.obtener("sat_descarga")
    assert isinstance(sat, DescargaSatFalso) and sat.al_solicitar is not None
    registro.limpiar_cache()
    monkeypatch.delenv("FISCALITO_SAT_FALSO_DIR")
    assert registro.obtener("sat_descarga").al_solicitar is None
    registro.limpiar_cache()


def test_primera_verificacion_configurable(monkeypatch):
    monkeypatch.delenv("FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION", raising=False)
    assert servicio.primera_verificacion() == timedelta(minutes=2)
    monkeypatch.setenv("FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION", "1")
    assert servicio.primera_verificacion() == timedelta(seconds=1)
    monkeypatch.setenv("FISCALITO_SAT_SEGUNDOS_PRIMERA_VERIFICACION", "basura")
    assert servicio.primera_verificacion() == timedelta(minutes=2)
