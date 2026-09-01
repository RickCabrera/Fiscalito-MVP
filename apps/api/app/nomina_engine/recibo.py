"""
El recibo de nomina como objeto de dominio, con sus totales.

DOS RESPONSABILIDADES SEPARADAS, A PROPOSITO
--------------------------------------------
Este modulo es **aritmetica pura sobre partidas dadas**: recibe percepciones,
deducciones y otros pagos ya determinados y calcula los totales que el CFDI
exige. No decide cuanto ISR se retiene ni cuanto es la cuota obrera.

`armar_recibo()` es la otra mitad: **calcula** las partidas usando
`isr_nomina` y `cuotas`, y despues arma el `Recibo`.

La separacion importa para medir el motor con honestidad. Alimentado con las
partidas del propio CFDI timbrado, este modulo debe reproducir los totales de
los 70 recibos del caso real, **70 de 70**, porque es solo sumar. El camino de
calculo, en cambio, se mide contra lo que ya establecieron §D14 (la cuota
obrera solo se reproduce en 5 de 70) y §D15 (el ISR, en los 28 de abril).
F1-05 no re-litiga esos numeros.

**Prohibido cerrar el neto** metiendo la diferencia en una deduccion clave 004
"Otros": haria cuadrar los 70 sin probar nada.

DEFINICIONES DE LOS TOTALES
---------------------------
Salen del `nomina12.xsd` versionado en `tests/xsd/`, no de la intuicion:

- `TotalSueldos`: percepciones brutas (gravadas y exentas) por sueldos,
  salarios y asimilados — o sea, todo lo que NO sea separacion/indemnizacion
  ni jubilacion.
- `TotalSeparacionIndemnizacion`: claves 022, 023 y 025.
- `TotalJubilacionPensionRetiro`: claves 039 y 044.
- `TotalImpuestosRetenidos`: deducciones con clave **002** (ISR).
- `TotalOtrasDeducciones`: deducciones con clave distinta de 002.

Y en el comprobante:

    SubTotal  = TotalPercepciones + TotalOtrosPagos
    Descuento = TotalDeducciones
    Total     = SubTotal - Descuento
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.exceptions import FiscalValidationError

# Claves de c_TipoPercepcion que NO son sueldos para efectos de los totales.
CLAVES_SEPARACION = frozenset({"022", "023", "025"})
CLAVES_JUBILACION = frozenset({"039", "044"})

# Clave de c_TipoDeduccion del ISR. Todo lo demas es "otras deducciones".
CLAVE_DEDUCCION_ISR = "002"

# Clave de c_TipoOtroPago del subsidio para el empleo.
CLAVE_OTRO_PAGO_SUBSIDIO = "002"

CERO = Decimal("0.00")


@dataclass(frozen=True)
class PartidaPercepcion:
    """
    Una percepcion como va al CFDI.

    `tipo` es la clave del catalogo `c_TipoPercepcion`; `clave` es el **codigo
    interno del patron** y no se deriva del tipo. En el caso real conviven
    `Clave="P019"` con `TipoPercepcion="020"`: derivar uno del otro emite
    claves equivocadas.
    """

    tipo: str
    clave: str
    concepto: str
    gravado: Decimal
    exento: Decimal

    @property
    def importe(self) -> Decimal:
        return self.gravado + self.exento


@dataclass(frozen=True)
class PartidaDeduccion:
    """Una deduccion como va al CFDI. `tipo` es `c_TipoDeduccion`."""

    tipo: str
    clave: str
    concepto: str
    importe: Decimal


@dataclass(frozen=True)
class PartidaOtroPago:
    """
    Un renglon de OtrosPagos. `tipo` es `c_TipoOtroPago`.

    `subsidio_causado` solo aplica a la clave 002. Desde 2024 el subsidio no se
    entrega en efectivo, asi que el `importe` suele ser cero mientras el
    causado lleva monto — es lo que hacen las 70 fixtures del caso real. Ver
    §D16 y la decision abierta del doc 24 §3 sobre como timbrarlo sin rechazo.
    """

    tipo: str
    clave: str
    concepto: str
    importe: Decimal
    subsidio_causado: Decimal | None = None


@dataclass(frozen=True)
class Recibo:
    """
    Un recibo de nomina completo. Los totales son propiedades, no campos: no
    pueden quedar desincronizados de las partidas.
    """

    percepciones: tuple[PartidaPercepcion, ...]
    deducciones: tuple[PartidaDeduccion, ...] = field(default_factory=tuple)
    otros_pagos: tuple[PartidaOtroPago, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.percepciones:
            raise FiscalValidationError("Un recibo de nómina necesita al menos una percepción.")
        for p in self.percepciones:
            if p.gravado < 0 or p.exento < 0:
                raise FiscalValidationError(
                    f"La percepción {p.tipo} tiene importes negativos: "
                    f"gravado={p.gravado}, exento={p.exento}."
                )
        for d in self.deducciones:
            if d.importe < 0:
                raise FiscalValidationError(
                    f"La deducción {d.tipo} no puede ser negativa: {d.importe}."
                )

    # ── Totales del nodo Percepciones ────────────────────────────────

    @property
    def total_gravado(self) -> Decimal:
        return sum((p.gravado for p in self.percepciones), start=CERO)

    @property
    def total_exento(self) -> Decimal:
        return sum((p.exento for p in self.percepciones), start=CERO)

    @property
    def total_percepciones(self) -> Decimal:
        return self.total_gravado + self.total_exento

    def _suma_por_tipos(self, tipos: frozenset[str]) -> Decimal:
        return sum((p.importe for p in self.percepciones if p.tipo in tipos), start=CERO)

    @property
    def total_sueldos(self) -> Decimal:
        """Percepciones brutas que no son separación ni jubilación."""
        return (
            self.total_percepciones
            - self._suma_por_tipos(CLAVES_SEPARACION)
            - self._suma_por_tipos(CLAVES_JUBILACION)
        )

    @property
    def total_separacion_indemnizacion(self) -> Decimal:
        return self._suma_por_tipos(CLAVES_SEPARACION)

    @property
    def total_jubilacion_pension_retiro(self) -> Decimal:
        return self._suma_por_tipos(CLAVES_JUBILACION)

    # ── Totales del nodo Deducciones ─────────────────────────────────

    @property
    def total_impuestos_retenidos(self) -> Decimal:
        return sum(
            (d.importe for d in self.deducciones if d.tipo == CLAVE_DEDUCCION_ISR),
            start=CERO,
        )

    @property
    def total_otras_deducciones(self) -> Decimal:
        return sum(
            (d.importe for d in self.deducciones if d.tipo != CLAVE_DEDUCCION_ISR),
            start=CERO,
        )

    @property
    def total_deducciones(self) -> Decimal:
        return self.total_impuestos_retenidos + self.total_otras_deducciones

    # ── Totales del nodo OtrosPagos y del Comprobante ────────────────

    @property
    def total_otros_pagos(self) -> Decimal:
        return sum((o.importe for o in self.otros_pagos), start=CERO)

    @property
    def subtotal(self) -> Decimal:
        return self.total_percepciones + self.total_otros_pagos

    @property
    def descuento(self) -> Decimal:
        return self.total_deducciones

    @property
    def total(self) -> Decimal:
        """El neto que recibe el trabajador."""
        return self.subtotal - self.descuento


@dataclass(frozen=True)
class DatosPatron:
    """Lo que el CFDI necesita del emisor. Ver §D8 para `clave_entidad`."""

    rfc: str
    nombre: str
    regimen_fiscal: str
    registro_patronal: str
    codigo_postal: str
    clave_entidad: str = "VER"


@dataclass(frozen=True)
class DatosTrabajador:
    """
    Lo que el CFDI necesita del receptor.

    `salario_diario_integrado` se recibe, no se recomputa: por §D9 los factores
    del caso real no son derivables de la antiguedad, asi que cuando el SDI
    viene de un CFDI es dato de entrada.
    """

    rfc: str
    nombre: str
    curp: str
    numero_seguridad_social: str
    codigo_postal: str
    fecha_inicio_relacion_laboral: date
    antiguedad: str
    tipo_contrato: str
    tipo_regimen: str
    numero_empleado: str
    departamento: str
    puesto: str
    riesgo_puesto: str
    periodicidad_pago: str
    salario_base_cotizacion: Decimal
    salario_diario_integrado: Decimal
    sindicalizado: str = "No"
    tipo_jornada: str = "01"
