"""
Tests del camino de **cálculo** del recibo.

`armar_recibo()` deriva las deducciones del motor, así que se mide contra lo que
ya establecieron F1-03 y F1-04, no contra el caso real otra vez: la cuota obrera
se reproduce en 5 de 70 (§D14) y el ISR en los 28 de abril (§D15). Aquí se
prueba que el armado **usa** esos motores y arma bien el recibo, no que el caso
real cuadre.
"""

from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.armado import armar_recibo
from app.nomina_engine.cuotas import DiasDelPeriodo
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.isr_nomina import Percepcion

ABRIL = date(2026, 4, 5)
GENERAL = ZonaSalarioMinimo.GENERAL
PRIMA_RT = Decimal("0.0054355")


def _armar(**kwargs):
    base = {
        "percepciones": (
            (Percepcion("001", "SUELDO", Decimal("2212.00")), "P001"),
            (Percepcion("020", "PRIMA DOMINICAL", Decimal("79.00")), "P019"),
        ),
        "sbc": clamp_sbc(Decimal("331.58"), ABRIL, GENERAL),
        "dias": DiasDelPeriodo(7),
        "fecha": ABRIL,
        "zona": GENERAL,
        "prima_riesgo": PRIMA_RT,
        "ingreso_gravado_mensual": Decimal("10080.03"),
        "clave_periodicidad": "02",
    }
    return armar_recibo(**{**base, **kwargs})


class TestArmado:
    def test_las_percepciones_conservan_su_clave_interna(self):
        """La clave del patrón no se deriva del tipo de catálogo."""
        recibo = _armar()
        assert {p.tipo: p.clave for p in recibo.percepciones} == {"001": "P001", "020": "P019"}

    def test_la_exencion_se_aplica_al_armar(self):
        recibo = _armar()
        prima = next(p for p in recibo.percepciones if p.tipo == "020")
        assert prima.exento == Decimal("79.00")
        assert prima.gravado == Decimal("0.00")
        assert recibo.total_gravado == Decimal("2212.00")

    def test_el_isr_y_la_cuota_obrera_entran_como_deducciones(self):
        """
        Los importes son los que ya fijaron F1-04 y F1-03 para este caso: ISR
        $34.68 (causado $158.02 − subsidio $123.34) y cuota obrera $55.12.
        """
        recibo = _armar()
        por_tipo = {d.tipo: d.importe for d in recibo.deducciones}
        assert por_tipo == {"002": Decimal("34.68"), "001": Decimal("55.12")}
        assert recibo.total_impuestos_retenidos == Decimal("34.68")
        assert recibo.total_otras_deducciones == Decimal("55.12")

    def test_el_subsidio_va_como_otro_pago_con_importe_cero(self):
        """
        Desde 2024 no se entrega en efectivo: lo acreditado ya redujo el ISR.
        Es lo que hacen las 70 fixtures del caso real.
        """
        recibo = _armar()
        (subsidio,) = recibo.otros_pagos
        assert subsidio.tipo == "002"
        assert subsidio.importe == Decimal("0.00")
        assert subsidio.subsidio_causado == Decimal("123.34")

    def test_sobre_el_tope_no_aparece_el_renglon_de_subsidio(self):
        recibo = _armar(ingreso_gravado_mensual=Decimal("12145.41"))
        assert recibo.otros_pagos == ()
        assert recibo.total_otros_pagos == Decimal("0.00")

    def test_al_trabajador_de_salario_minimo_no_se_le_retiene_isr(self):
        """
        Art. 96 último párrafo. El subsidio queda causado pero sin acreditar ni
        entregar (§D16), así que el renglón de OtrosPagos sigue apareciendo.
        """
        recibo = _armar(
            sbc=clamp_sbc(Decimal("315.04"), ABRIL, GENERAL),
            es_trabajador_de_salario_minimo=True,
        )
        assert all(d.tipo != "002" for d in recibo.deducciones)
        (subsidio,) = recibo.otros_pagos
        assert subsidio.subsidio_causado == Decimal("123.34")

    def test_el_patron_absorbe_la_cuota_obrera_del_salario_minimo(self):
        """Art. 36 LSS: no hay deducción de IMSS en su recibo."""
        recibo = _armar(sbc=clamp_sbc(Decimal("315.04"), ABRIL, GENERAL))
        assert all(d.tipo != "001" for d in recibo.deducciones)

    def test_los_totales_del_recibo_son_coherentes(self):
        recibo = _armar()
        assert recibo.subtotal == recibo.total_percepciones + recibo.total_otros_pagos
        assert recibo.descuento == recibo.total_deducciones
        assert recibo.total == recibo.subtotal - recibo.descuento
        assert recibo.total == Decimal("2201.20")

    def test_no_se_cierra_el_neto_con_una_deduccion_de_ajuste(self):
        """
        Prohibido explícitamente: meter la diferencia en una deducción clave
        004 "Otros" haría cuadrar el caso real sin probar nada. El armado solo
        emite las deducciones que el motor calcula.
        """
        recibo = _armar()
        assert {d.tipo for d in recibo.deducciones} <= {"001", "002"}
