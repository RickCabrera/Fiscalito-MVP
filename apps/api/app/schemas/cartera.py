"""
Esquemas de la cartera del despacho cuando el backend es su dueño. (R-07)

POR QUÉ HAY UN `ClienteCarteraSchema` NUEVO
-------------------------------------------
`ClienteResumen` y `ClienteDetalle` (E-02) describen el **catálogo de
demostración**: son de sólo lectura, salen de `despacho_demo.py` y llevan campos
derivados (`num_empleados`, `fecha_referencia`) que un cliente capturado por el
contador no tiene. Reusarlos aquí obligaría a inventar esos campos al guardar,
que es exactamente el tipo de dato falso que este repo evita en todos lados.

Éste describe lo que el DESPACHO captura, con la misma forma que el front ya
escribe en Firestore — para que encender R-07 no exija migrar un solo documento.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.tablas_imss import PRIMA_RT_MAXIMA, PRIMA_RT_MINIMA

# Horario, parámetros salariales y criterios de nómina viven en `cartera_parametros.py`
# (P6-05, tope de 300 líneas); se reexportan aquí.
from app.schemas.cartera_parametros import (  # noqa: E402, F401
    HORA,
    CriteriosNominaSchema,
    HorarioSchema,
    ParametrosSalarialesSchema,
)
from app.schemas.datos_fiscales_cliente import (
    ENTIDADES_C_ESTADO,
    LONGITUDES_RFC_POR_REGIMEN,
    RFC_O_VACIO,
)
from app.schemas.nomina import PeriodoNomina


class ClienteCarteraSchema(BaseModel):
    """Un cliente tal como lo captura el despacho."""

    id: str = Field(min_length=1, max_length=120)
    nombre: str = Field(min_length=1)
    giro: str = ""
    origen: str = Field(
        default="propio",
        description="`propio` = lo capturó el contador. `sintetico` y `fixtures-s04` son "
        "los clientes de DEMOSTRACIÓN, y el front los oculta fuera de cuentas de "
        "desarrollo (R-06).",
    )

    regimen: str = Field(
        default="",
        max_length=3,
        pattern=r"^\d{0,3}$",
        description="Clave del régimen fiscal del CLIENTE (c_RegimenFiscal del SAT), no del "
        "despacho. Lo consume el FRONT para decidir qué pantallas de Fiscalito se le pueden "
        "trabajar (T1). **Este schema no valida el catálogo**; la única regla que aplica con "
        "él es que la longitud del `rfc` case con 601/612/626 (C-01, ver `rfc`). El corte "
        "concreto 612/626 de los tabs es un criterio heredado de E-01, pendiente de "
        "confirmar con la contadora "
        "(docs/decisiones-nomina.md §D30). **Vacío = no capturado**, y el front lo dice en "
        "pantalla en vez de suponerlo en silencio; una cartera escrita antes de T1 no lo "
        "trae. El campo existe aquí aunque hoy el dueño del dato sea Firestore (R-07 sigue "
        "apagada) porque sin él, encender R-07 borraría el régimen de cada cliente en el "
        "primer guardado: pydantic descarta lo que no declara.",
    )
    rfc: str = Field(
        default="",
        max_length=13,
        pattern=RFC_O_VACIO,
        description="RFC del cliente (el patrón, en nómina). **Vacío cuando no se conoce y "
        "nunca inventado**, misma política que el NSS del empleado. Lo capturan el alta y la "
        "edición de cliente (C-01) y la Configuración de empresa (O-01). Se guarda en "
        "mayúsculas y sin espacios. Si trae valor, se valida el formato y, para los regímenes "
        "601/612/626, que la longitud case (601 = 12, 612 = 13, 626 = 12 o 13).",
    )
    codigo_postal: str = Field(
        default="",
        pattern=r"^(\d{5})?$",
        description="CP del domicilio fiscal (C-01), 5 dígitos. Vacío = no capturado. Sólo "
        "candidato a default del `LugarExpedicion` del CFDI de nómina: no siempre coinciden.",
    )
    clave_entidad: str = Field(
        default="",
        description="Entidad del cliente (C-01), catálogo `c_Estado`. Vacío = no capturada. "
        "Sólo candidata a default de `ClaveEntFed`, que es donde el trabajador presta el servicio.",
    )
    guia_subdelegacion: str = Field(
        default="",
        max_length=5,
        pattern=r"^\d{0,5}$",
        description="Número de guía que la subdelegación del IMSS asigna al patrón (O-04). "
        "Va en las posiciones 134-138 de cada movimiento afiliatorio y en el registro de "
        "cifras de control. **No se calcula ni se deduce**: lo asigna la subdelegación. "
        "Vacío = no se puede emitir el archivo, y el exportador lo dice.",
    )
    registro_patronal: str = Field(
        default="",
        max_length=11,
        description="Registro patronal del IMSS: **11 caracteres**, los 10 del registro más "
        "su dígito verificador (posiciones 01-10 y 11 del layout de movimientos "
        "afiliatorios del IMSS). Se guarda junto y se parte al exportar. El verificador "
        "**no se calcula**: no hay algoritmo publicado, y un dígito inventado junto a un "
        "registro real es peor que un campo vacío. Vacío = no se pueden emitir "
        "movimientos afiliatorios, y el exportador lo dice en vez de emitirlos mal.",
    )

    prima_riesgo: Decimal = Field(
        ge=PRIMA_RT_MINIMA,
        le=PRIMA_RT_MAXIMA,
        description=f"Fracción, no porcentaje. Arts. 72 y 73 LSS acotan a "
        f"[{PRIMA_RT_MINIMA}, {PRIMA_RT_MAXIMA}]. Se valida aquí porque capturar "
        f"5.4355 en vez de 0.0054355 multiplica Riesgos de Trabajo por mil y ninguna "
        f"tabla lo detecta después.",
    )
    clase_riesgo: int | None = Field(default=None, ge=1, le=5)
    clave_periodicidad: str = Field(
        default="04",
        description="Clave de `c_PeriodicidadPago`. Hoy el front sólo ofrece `04` "
        "(quincenal): nadie valida que la duración del periodo case con la clave, y un "
        "cliente Mensual recibiría la tarifa mensual del Art. 96 sobre 15-16 días — ISR "
        "subestimado con recibo creíble (backlog, sección G).",
    )
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    parametros: ParametrosSalarialesSchema = Field(
        default_factory=ParametrosSalarialesSchema,
        description="Prestaciones y horario del patrón (O-03). Con default completo: una "
        "cartera escrita antes de O-03 no lo trae y tiene que seguir leyéndose — el "
        "default es el mínimo de ley, que es lo que la app aplicaba hasta ahora.",
    )
    criterios_nomina: CriteriosNominaSchema = Field(
        default_factory=CriteriosNominaSchema,
        description="Criterios del despacho para este cliente (§D26, §D27, §D28, Art. 174 "
        "RLISR, remanente de PTU). Con default completo: un cliente guardado antes de P4 "
        "no lo trae y se lee con los defaults.",
    )
    periodo_sugerido: PeriodoNomina | None = Field(
        default=None,
        description="Puede faltar: el primer cliente de una cuenta nueva nace sin él y la "
        "pantalla de nómina pide capturar las fechas (R-06).",
    )

    @field_validator("rfc", mode="before")
    @classmethod
    def _rfc_normalizado(cls, valor: object) -> object:
        """Mayúsculas y sin espacios antes del patrón, igual que `normalizarRfc` del front."""
        return valor.strip().upper() if isinstance(valor, str) else valor

    @field_validator("clave_entidad")
    @classmethod
    def _entidad_del_catalogo(cls, valor: str) -> str:
        if valor and valor not in ENTIDADES_C_ESTADO:
            raise ValueError(f"La clave de entidad {valor!r} no está en el catálogo c_Estado.")
        return valor

    @model_validator(mode="after")
    def _rfc_casa_con_el_regimen(self) -> ClienteCarteraSchema:
        """
        Un RFC de 12 es de persona moral y uno de 13 de persona física.

        **Se valida en cada guardado, no sólo cuando cambia el RFC**: un cliente
        con RFC y régimen que no casan no se vuelve a guardar hasta corregir uno
        de los dos, y el mensaje dice cuál es el conflicto. El front aplica la
        misma regla y bloquea el mismo guardado, así que no hay un camino que
        acepte lo que el otro rechaza.
        """
        admitidas = LONGITUDES_RFC_POR_REGIMEN.get(self.regimen)
        if self.rfc and admitidas and len(self.rfc) not in admitidas:
            raise ValueError(
                f"El RFC {self.rfc!r} tiene {len(self.rfc)} caracteres y el régimen "
                f"{self.regimen} admite {' o '.join(map(str, admitidas))}."
            )
        return self


# Las respuestas viven en `cartera_respuestas.py` (P6-07); se reexportan para quien las importe
# de aquí (P6-05 partió el mismo módulo por otro lado).
from app.schemas.cartera_respuestas import (  # noqa: E402, F401
    ClientesCarteraResponse,
    EmpleadoIlegible,
    EmpleadosCarteraResponse,
    OperacionResponse,
)
