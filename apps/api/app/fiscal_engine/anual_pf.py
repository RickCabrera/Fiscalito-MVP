"""
Cálculo anual de personas físicas con detalle mes a mes (P3-06). Puro.

Reúsa los motores que ya existen —no recalcula nada por su cuenta—:

- **Mes a mes**: `multi_periodo.calcular_multi_periodo` (pagos provisionales acumulativos de
  612/606, Arts. 106 y 116 LISR; mensuales aislados de 626 y 625).
- **Anual 612 / 606 / 625**: `calculadora.calcular_declaracion(es_anual=True)` (tarifa del
  Art. 152 LISR, Anexo 8 RMF 2026; 606 compara deducción ciega del 35 % del Art. 115).
- **Anual 626 (RESICO PF)**: tabla del **Art. 113-F LISR** (abajo), sobre los ingresos
  efectivamente cobrados del ejercicio, sin deducciones.

Lo que NO incluye y se dice en `notas`: deducciones personales (Art. 151; tienen su propio
endpoint), PTU pagada y pérdidas de la PF (Art. 109), y estímulos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.fiscal_engine.calculadora import calcular_declaracion
from app.fiscal_engine.multi_periodo import calcular_multi_periodo
from app.fiscal_engine.personas_morales import Renglon
from app.redondeo import redondear
from app.schemas.fiscal import CFDI, PerfilContribuyente

CERO = Decimal("0.00")
REGIMENES_PF = ("612", "606", "625", "626")

# Art. 113-F LISR (DOF 12/11/2021, vigente): tasa anual de RESICO PF sobre el total de ingresos
# efectivamente cobrados del ejercicio. (límite superior, tasa). Sin indexación anual.
RESICO_TASAS_ANUALES: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("300000.00"), Decimal("0.0100")),
    (Decimal("600000.00"), Decimal("0.0110")),
    (Decimal("1000000.00"), Decimal("0.0150")),
    (Decimal("2500000.00"), Decimal("0.0200")),
    (Decimal("3500000.00"), Decimal("0.0250")),
)


def tasa_resico_anual(ingresos: Decimal) -> Decimal:
    """Tasa del Art. 113-F; arriba de 3.5 MDP se usa la última y se avisa (Art. 113-E)."""
    for limite, tasa in RESICO_TASAS_ANUALES:
        if ingresos <= limite:
            return tasa
    return RESICO_TASAS_ANUALES[-1][1]


@dataclass
class MesPF:
    mes: int
    ingresos: Decimal
    deducciones: Decimal
    base: Decimal
    isr_causado: Decimal
    retenciones: Decimal
    pago_determinado: Decimal
    pago_efectuado: Decimal
    pago_capturado: bool


@dataclass
class ResultadoAnualPF:
    anio: int
    regimen: str
    meses: list[MesPF]
    renglones: list[Renglon]
    a_cargo: Decimal
    a_favor: Decimal
    notas: list[str] = field(default_factory=list)


def _d(v: float) -> Decimal:
    return redondear(Decimal(str(v)))


def anual_pf(
    perfil: PerfilContribuyente, anio: int, facturas: list[CFDI],
    pagos_capturados: dict[int, Decimal] | None = None,
) -> ResultadoAnualPF:
    """Anual de la PF con su mes a mes; `facturas` ya por flujo de efectivo y fechadas."""
    regimen = perfil.regimen
    pagos_capturados = pagos_capturados or {}
    resultados, _ = calcular_multi_periodo(perfil, facturas, anio, list(range(1, 13)))
    meses: list[MesPF] = []
    for i, r in enumerate(resultados, start=1):
        d = r.desglose
        determinado = _d(d.isr_a_pagar)
        cap = i in pagos_capturados
        meses.append(MesPF(
            i, _d(d.total_ingresos_gravados), _d(d.total_deducciones_autorizadas),
            _d(d.base_isr), _d(d.isr_causado), _d(d.isr_retenido), determinado,
            redondear(pagos_capturados[i]) if cap else determinado, cap))

    ingresos = sum((m.ingresos for m in meses), CERO)
    retenciones = sum((m.retenciones for m in meses), CERO)
    pagos = sum((m.pago_efectuado for m in meses), CERO)
    notas: list[str] = []
    if regimen == "626":
        deducciones = CERO
        base = ingresos
        tasa = tasa_resico_anual(ingresos)
        isr = redondear(ingresos * tasa)
        tarifa = f"Art. 113-F LISR (tasa {tasa * 100:.2f} %)"
        if ingresos > RESICO_TASAS_ANUALES[-1][0]:
            notas.append("Ingresos arriba de 3.5 MDP: el contribuyente sale de RESICO "
                         "(Art. 113-E) y tributa en el régimen general.")
    else:
        anual = calcular_declaracion(perfil, facturas, es_anual=True)
        deducciones = _d(anual.total_deducciones_autorizadas)
        base = _d(anual.base_isr)
        isr = _d(anual.isr_causado)
        ingresos = _d(anual.total_ingresos_gravados)
        retenciones = _d(anual.isr_retenido)
        tarifa = "Art. 152 LISR (tarifa anual, Anexo 8 RMF 2026)"
        if anual.deduccion_ciega_aplicada:
            notas.append("Se aplicó la deducción opcional del 35 % (Art. 115 LISR): "
                         + (anual.comparacion_deduccion or ""))
        if anual.retenciones_definitivas:
            notas.append("Plataformas con ingresos hasta $300,000: las retenciones pueden "
                         "ser pago definitivo (Art. 113-B LISR).")
        notas.append("No incluye deducciones personales (Art. 151 LISR): calcúlalas en "
                     "Deducciones personales y réstalas de la base gravable.")
    neto = isr - pagos - retenciones
    renglones = [
        Renglon("ingresos", "Ingresos del ejercicio (flujo de efectivo)", ingresos,
                "Arts. 100, 102, 114 y 113-E LISR"),
        Renglon("deducciones", "Deducciones autorizadas", deducciones,
                "Arts. 103 y 105 LISR" if regimen != "606" else "Art. 115 LISR"),
        Renglon("base", "Base gravable", base, tarifa),
        Renglon("isr_ejercicio", "ISR del ejercicio", isr, tarifa),
        Renglon("pagos_provisionales", "Pagos provisionales efectuados", pagos,
                "Arts. 106, 113-E, 113-A y 116 LISR"),
        Renglon("retenciones", "ISR retenido por terceros", retenciones,
                "Arts. 106 último párrafo y 113-J LISR"),
        Renglon("a_cargo", "ISR a cargo", max(neto, CERO), "Art. 150 LISR"),
        Renglon("a_favor", "ISR a favor", max(-neto, CERO), "Art. 22 CFF"),
    ]
    return ResultadoAnualPF(anio, regimen, meses, renglones, max(neto, CERO),
                            max(-neto, CERO), notas)


def mes_pf_dict(m: MesPF) -> dict[str, object]:
    return {"mes": m.mes, "ingresos": f"{m.ingresos:.2f}",
            "deducciones": f"{m.deducciones:.2f}", "base": f"{m.base:.2f}",
            "isr_causado": f"{m.isr_causado:.2f}", "retenciones": f"{m.retenciones:.2f}",
            "pago_determinado": f"{m.pago_determinado:.2f}",
            "pago_efectuado": f"{m.pago_efectuado:.2f}", "pago_capturado": m.pago_capturado}
