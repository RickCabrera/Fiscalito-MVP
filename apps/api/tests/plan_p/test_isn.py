"""P3-07: ISN por estado.

"Listo cuando": un cliente en Veracruz calcula su ISN con la tasa citada.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.exceptions import FiscalValidationError
from app.fiscal_engine.isn import ConfigISN, PercepcionISN, calcular_isn, tabla_isn, tasa_vigente
from app.schemas.datos_fiscales_cliente import ENTIDADES_C_ESTADO


def test_las_32_entidades_tienen_tasa_con_fuente():
    tabla = tabla_isn()
    assert set(tabla) == ENTIDADES_C_ESTADO - {"DIF"}
    for clave, vigencias in tabla.items():
        for t in vigencias:
            assert t.fuente and t.fundamento, clave
            assert D("0.01") <= t.tasa <= D("0.05"), clave
            if t.verificacion != "ley_citada":
                assert t.fundamento.startswith("FUENTE POR CONFIRMAR"), clave


def test_veracruz_tasa_citada_y_adicional():
    t = tasa_vigente("VER", date(2026, 3, 1))
    assert t.tasa == D("0.03") and t.adicional_sobre_impuesto == D("0.15")
    assert t.verificacion == "ley_citada" and "art" in t.fundamento and "101" in t.fundamento
    r = calcular_isn("VER", date(2026, 3, 1), [
        PercepcionISN("001", D("82345.67")), PercepcionISN("003", D("10000")),
        PercepcionISN("019", D("1500")),
    ])
    assert r.total_erogaciones == D("93845.67") and r.excluido == D("10000.00")
    assert r.base == D("83845.67")
    assert r.impuesto == D("2515.37")  # 83,845.67 × 3 % = 2,515.3701
    assert r.adicional == D("377.31")  # 2,515.37 × 15 %
    assert r.total == D("2892.68")


def test_veracruz_sin_adicional_y_exclusiones_del_despacho():
    r = calcular_isn("VER", date(2026, 3, 1), [PercepcionISN("001", D("1000")),
                                               PercepcionISN("019", D("500"))],
                     ConfigISN(aplicar_adicional=False, claves_excluidas_extra=frozenset({"019"})))
    assert r.base == D("1000.00") and r.adicional == 0 and r.total == D("30.00")


def test_cdmx_dif_y_errores():
    assert tasa_vigente("DIF", date(2026, 1, 1)).entidad == "CMX"
    with pytest.raises(FiscalValidationError):
        tasa_vigente("XXX", date(2026, 1, 1))
    with pytest.raises(FiscalValidationError):
        tasa_vigente("VER", date(2025, 12, 31))
