"""
Schemas del cálculo de nómina de un periodo (D-06).

El endpoint es un **orquestador de demo**: un solo cálculo de punta a punta.
Los granulares (SBC, cuotas, recibo por separado) son F1-07.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.tablas_imss import PRIMA_RT_MAXIMA, PRIMA_RT_MINIMA


class PeriodoNomina(BaseModel):
    """
    Periodo de nómina, inclusivo en los dos extremos.

    `fecha_pago` está separada de `fin` a propósito, y no es un detalle: la
    vigencia de UMA, salario mínimo, tarifa del Anexo 8 y el transitorio de
    enero del subsidio se leen de **la fecha de pago**. Una quincena que cierra
    el 31-ene y se paga el 5-feb se calcula con los valores de febrero.
    """

    inicio: date
    fin: date
    fecha_pago: date | None = Field(
        default=None,
        description="Default: `fin`. DECISIÓN PROVISIONAL (nocturno): se asume "
        "que el patrón paga el último día del periodo. Decide los números de enero.",
    )

    @model_validator(mode="after")
    def _no_invertido(self) -> PeriodoNomina:
        """Un periodo al revés daría días negativos y cuotas sin sentido."""
        if self.fin < self.inicio:
            raise ValueError(
                f"El periodo termina antes de empezar: {self.inicio} a {self.fin}."
            )
        return self

    @property
    def pago(self) -> date:
        return self.fecha_pago or self.fin


class EmpleadoDemoSchema(BaseModel):
    """
    Un empleado de la plantilla de demostración, **sin salarios**.

    El front sólo necesita el número y el nombre: los importes vienen en los
    recibos. Menos superficie es menos que pueda salir por donde no debe.
    """

    empleado_no: str
    nombre: str


class PeriodoSugeridoResponse(BaseModel):
    """
    El último periodo terminado para una periodicidad. (O-03)

    Existe para que el front **no replique la regla del periodo**. De la
    `fecha_pago` que sale de aquí dependen la UMA, el salario mínimo, la tarifa
    del Anexo 8 y el transitorio de enero del subsidio (§D18): dos
    implementaciones serían dos verdades sobre con qué valores se calcula la
    nómina.

    Antes de O-03 el front proponía **siempre una quincena** —copiaba la del
    cliente de demostración a todos, sin mirar su clave— así que elegir Mensual
    dejaba a la empresa con un periodo que el propio motor rechaza.

    `dias_naturales` viaja calculado y no se deriva en el cliente: es el mismo
    número que `duracion_periodo` valida, y restar fechas en JavaScript con
    zonas horarias es de las cosas que dan 15 donde hay 16.
    """

    exito: bool = True
    clave_periodicidad: str
    periodo: PeriodoNomina
    dias_naturales: int


class PlantillaDemoResponse(BaseModel):
    """
    Todo lo que la pantalla de la demo necesita y **no puede inventarse**.

    Existe para que el front no escriba ni una constante fiscal. Sin este
    endpoint tendría que hardcodear los nueve empleados y la prima de riesgo
    —que tiene fundamento legal (Art. 72/74 LSS) y dueño en `demo_nomina.py`—
    en TypeScript, donde ningún test verifica que no diverjan.

    `periodo_sugerido` sale de la **regla de quincena real**, no de las fechas
    de las checadas: deducirlo de la primera y la última da 15 días donde la
    quincena tiene 16 —el día 16 cae en fin de semana— y ese día de menos
    entra a `DiasDelPeriodo` y a los días pagados, o sea a las cuotas y al ISR.
    """

    exito: bool = True
    cliente: str
    origen: str = "demo"
    empleados: tuple[EmpleadoDemoSchema, ...]
    prima_riesgo: Decimal
    clave_periodicidad: str
    zona: ZonaSalarioMinimo
    periodo_sugerido: PeriodoNomina


class EmpleadoNominaSchema(BaseModel):
    """Un empleado de la plantilla. El SDI es dato de entrada (§D9)."""

    empleado_no: str
    nombre: str = ""
    salario_diario: Decimal = Field(gt=0)
    salario_diario_integrado: Decimal = Field(gt=0)
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL


class IncidenciasEmpleadoSchema(BaseModel):
    """
    Incidencias de un empleado, tal como las devuelve `cerrar-periodo`.

    `dias_periodo` son **días naturales**, no laborables ni cotizados.
    `dias_ausentismo` alimenta `DiasDelPeriodo`; `faltas` descuenta días
    pagados. Hoy son el mismo número; en F1-09 divergen.
    """

    empleado_no: str
    dias_periodo: int = Field(gt=0, le=31)
    faltas: int = Field(ge=0)
    dias_ausentismo: int = Field(ge=0)
    dias_incapacidad: int = Field(default=0, ge=0)


class ParametrosPatron(BaseModel):
    """Parámetros de la empresa que el motor necesita y no puede adivinar."""

    prima_riesgo: Decimal = Field(
        ge=PRIMA_RT_MINIMA,
        le=PRIMA_RT_MAXIMA,
        description=f"Prima de RT autodeterminada (Art. 72 LSS): entre "
        f"{PRIMA_RT_MINIMA} y {PRIMA_RT_MAXIMA}. No es tasa de ley y no tiene default. "
        f"El motor también la valida; aquí se acota para responder 422 en la frontera "
        f"en vez de 500 desde el motor.",
    )
    clave_periodicidad: str = Field(
        default="04",
        description="Clave de c_PeriodicidadPago. 01 diaria, 02 semanal, 04 quincenal, "
        "05 mensual. Catorcenal (03) y decenal (10) responden 422: nadie publica su "
        "tarifa verificada (§D10).",
    )
    dias_pagados: int | None = Field(
        default=None,
        ge=0,
        description="Override de días pagados para todos. Sin él, "
        "`dias_periodo − faltas`.",
    )


class CalcularPeriodoRequest(BaseModel):
    cliente: str
    periodo: PeriodoNomina
    incidencias: tuple[IncidenciasEmpleadoSchema, ...]
    parametros: ParametrosPatron
    empleados: tuple[EmpleadoNominaSchema, ...] | None = Field(
        default=None,
        description="Omitirlo usa la plantilla de la demo, y SÓLO es válido para el "
        "cliente `demo`: calcularle a un cliente real la nómina de otras 9 personas "
        "sería peor que fallar.",
    )
    incluir_explicacion: bool = False

    @model_validator(mode="after")
    def _incidencias_no_vacias(self) -> CalcularPeriodoRequest:
        if not self.incidencias:
            raise ValueError(
                "Se requieren incidencias del periodo. Cierra el periodo en "
                "`/asistencia/cerrar-periodo` antes de calcular."
            )
        return self


class PartidaSchema(BaseModel):
    tipo: str
    clave: str
    concepto: str
    importe: Decimal
    gravado: Decimal | None = None
    exento: Decimal | None = None
    subsidio_causado: Decimal | None = None


class CuotaRamoSchema(BaseModel):
    """Un ramo calculado, con lo necesario para conciliarlo contra la EMA."""

    clave: str
    nombre: str
    base_diaria: Decimal
    dias: int
    patron: Decimal
    obrero: Decimal
    fundamento: str


class ReciboSchema(BaseModel):
    empleado_no: str
    nombre: str
    sbc: Decimal
    sbc_piso_aplicado: bool
    sbc_tope_aplicado: bool
    es_salario_minimo: bool
    dias_periodo: int
    dias_ausentismo: int
    dias_pagados: int
    percepciones: tuple[PartidaSchema, ...]
    deducciones: tuple[PartidaSchema, ...]
    otros_pagos: tuple[PartidaSchema, ...]
    total_percepciones: Decimal
    total_deducciones: Decimal
    neto: Decimal
    cuota_obrera: Decimal
    cuota_patronal: Decimal
    absorbio_cuota_obrera: bool
    ramos: tuple[CuotaRamoSchema, ...]


class PorcionConsolidada(BaseModel):
    """
    Lo devengado en ESTE periodo por los ramos de una periodicidad de entero.

    **No es el entero del Art. 39 LSS.** Una quincena trae media mensualidad de
    EyM/IyV y un doceavo de bimestre de Retiro/CEAV/Infonavit. Para enterar hay
    que sumar los periodos que caen en el mes o en el bimestre.
    """

    periodicidad: str
    por_ramo: dict[str, Decimal]
    total_patron: Decimal
    total_obrero: Decimal
    total: Decimal
    empleados: int


class CalcularPeriodoResponse(BaseModel):
    """
    El resultado del periodo.

    LOS TRES TOTALES SON EL ANCLA DEL CUADRE DE O-04
    ------------------------------------------------
    `ResultadoPeriodo` ya los calculaba —los usa `_resumen_para_llm`— y **no
    viajaban**. El front los recomponía sumando los recibos para el PDF, y O-04
    iba a hacer lo mismo para los TXT.

    Un revisor lo llamó por su nombre: comparar el PDF contra los TXT cuando los
    dos derivan del mismo módulo del front es **tautológico**. Sólo puede fallar
    si un generador escribe el campo en la posición equivocada; un error en la
    suma pasa verde en los dos lados.

    Con estos tres campos el cuadre tiene un tercer punto que no depende del
    navegador: los bytes emitidos se parsean de vuelta y se comparan **contra el
    motor**. Las cuotas obrera y patronal ya eran derivables de
    `porcion_mensual` / `porcion_bimestral`, así que no se duplican aquí.
    """

    exito: bool = True
    cliente: str
    periodo: PeriodoNomina
    origen_plantilla: str = Field(
        description="`demo` si se usó la plantilla del servidor, `request` si vino en "
        "el cuerpo. El PDF no puede mentir sobre de quién es la nómina."
    )
    fecha_pago_efectiva: date = Field(
        description="La fecha con la que se calculó, ya resuelto el default "
        "(`periodo.fecha_pago` o, si no vino, `periodo.fin`). Se serializa porque "
        "de ella dependen UMA, salario mínimo, tarifa del Anexo 8 y el transitorio "
        "de enero del subsidio: si el front tuviera que replicar el default para "
        "mostrarla, mentiría en silencio el día que el default cambie — y §D18 está "
        "abierta justamente sobre eso."
    )
    recibos: tuple[ReciboSchema, ...]
    porcion_mensual: PorcionConsolidada
    porcion_bimestral: PorcionConsolidada

    total_percepciones: Decimal = Field(
        description="Suma de las percepciones de todos los recibos. **Del MOTOR**, no "
        "recompuesta por el cliente (O-04)."
    )
    total_neto: Decimal = Field(description="Suma de los netos. Del motor.")
    total_isr: Decimal = Field(description="Suma del ISR retenido. Del motor.")

    advertencias: tuple[str, ...] = ()
    explicacion: str | None = None


class SBCRequest(BaseModel):
    """
    Lo que se necesita para integrar un salario fijo (Art. 27 y 30 fr. I LSS).

    **`fecha` es obligatoria y no tiene default.** `clamp_sbc` mueve el piso el
    1 de enero (salario mínimo) y el tope el 1 de febrero (UMA), así que un
    `date.today()` implícito haría que el SBC del modal cambiara solo entre
    enero y febrero. Todo el encabezado de `despacho_demo.py` está escrito
    contra esa clase de deriva.
    """

    # `extra="forbid"` porque el silencio aquí subintegra. Sin esto, un front
    # que mandara `conceptos` —que esta ruta NO acepta (§D5: el motor no decide
    # qué integra)— recibiría un SBC calculado sólo sobre el salario, sin
    # ninguna señal. Subintegrar es la dirección peligrosa: cuotas de menos y
    # crédito fiscal del IMSS. Es la misma deriva silenciosa que se rechazó en
    # `fecha` y en el clamp, al revés.
    model_config = ConfigDict(extra="forbid")

    salario_diario: Decimal = Field(gt=0)
    fecha: date = Field(
        description="Fecha contra la que se miden piso y tope. Obligatoria a "
        "propósito: piso y tope se mueven en fechas distintas."
    )
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    anios_servicio_cumplidos: int = Field(
        default=0,
        ge=0,
        description="Antigüedad cumplida. Decide los días de vacaciones de ley "
        "cuando no se capturan (Art. 76 LFT). **Sin tope superior**: el docstring "
        "de `dias_vacaciones_de_ley` advierte que la regla no es una tabla "
        "cerrada y que un trabajador con 37 años de antigüedad existe.",
    )
    dias_aguinaldo: int = Field(default=15, ge=0)
    dias_vacaciones: int = Field(
        default=0, ge=0, description="0 = los de ley que le tocan a su antigüedad."
    )
    prima_vacacional: Decimal = Field(default=Decimal("0.25"), ge=0)
    tabla_vacaciones: tuple[tuple[int, int], ...] = Field(
        default=(),
        description="Escala de vacaciones del PATRÓN: `[[años_cumplidos, días], ...]` "
        "(O-03). El Art. 76 LFT fija el mínimo y el patrón puede otorgar más; se rechaza "
        "renglón por renglón lo que quede por debajo. Vacía = manda la ley. "
        "**El front manda la tabla y la antigüedad; NUNCA resuelve los días él mismo.** "
        "`vacaciones_efectivas` ya define `0 = los de ley`, y con una tabla ese centinela "
        "sería ambiguo — además de que buscar el renglón en TypeScript sería una segunda "
        "implementación de la misma búsqueda. Los días aplicados vuelven en "
        "`dias_vacaciones_aplicados`.",
    )


class SBCResponse(BaseModel):
    """
    El SBC integrado, con todo lo que la pantalla necesita para explicarlo.

    Las banderas del clamp **no son adorno**: `piso_aplicado` es el único camino
    por el que un SBC llega a ser exactamente 1 salario mínimo, que es el
    supuesto del Art. 36 LSS (el patrón absorbe la cuota obrera) y el renglón de
    3.150% de la tabla de CEAV. Acotar en silencio escondería eso.
    """

    factor: Decimal
    dias_vacaciones_aplicados: int
    sbc_sin_acotar: Decimal
    sbc: Decimal
    piso_aplicado: bool
    tope_aplicado: bool
    piso: Decimal
    tope: Decimal
    fundamento: str


# ── CFDI de nómina 4.0 + complemento 1.2, SIN TIMBRAR (T4) ──────────────────
#
# LO QUE ESTE REQUEST NO HACE, Y ES LO IMPORTANTE
# -----------------------------------------------
# **No inventa identidades.** RFC, CURP, NSS, códigos postales y registro
# patronal son obligatorios y no tienen default: un CFDI con un RFC inventado
# es un papel con el nombre de una persona real y los datos de nadie. Si el
# operador no los tiene capturados, la respuesta correcta es un 422 que diga
# cuáles faltan — no un XML que parezca bueno.
#
# Los únicos defaults son claves de catálogo con un valor único para el caso
# ordinario (`TipoRegimen = 02` sueldos y salarios, `TipoJornada = 01` diurna,
# `Sindicalizado = No`, `TipoNomina = O`), cada uno citado abajo contra
# `knowledge_base/nomina/24_cfdi_nomina_12.md` §2 y §3.


class ReciboCFDISchema(BaseModel):
    """
    Lo que el CFDI necesita de un recibo, y nada más.

    **Es el subconjunto de `ReciboSchema`**: un elemento de `recibos[]` tal como
    sale de `POST /nomina/calcular-periodo` lo satisface sin remapear, porque
    Pydantic ignora los campos de más (SBC, cuotas, ramos, banderas del clamp).
    Se declara aparte en vez de reusar `ReciboSchema` entero para que el
    contrato diga qué se usa de verdad: el día que el front arme un recibo a
    mano, `sbc_piso_aplicado` no puede ser la razón de un 422.

    **Los importes no se recalculan aquí.** Llegan del motor y el serializador
    sólo los suma para los totales del comprobante (`recibo.py` es aritmética
    pura sobre partidas dadas). Este endpoint no es el motor.
    """

    empleado_no: str
    nombre: str = ""
    dias_pagados: int = Field(ge=0)
    percepciones: tuple[PartidaSchema, ...]
    deducciones: tuple[PartidaSchema, ...] = ()
    otros_pagos: tuple[PartidaSchema, ...] = ()


class DatosPatronCFDI(BaseModel):
    """El emisor. Ver `24_cfdi_nomina_12.md` §2."""

    rfc: str = Field(min_length=12, max_length=13)
    nombre: str = Field(min_length=1)
    regimen_fiscal: str = Field(
        min_length=3, max_length=3, description="Clave de `c_RegimenFiscal` del patrón."
    )
    registro_patronal: str = Field(
        min_length=1,
        description="Registro patronal del IMSS. Va en `nomina12:Emisor`.",
    )
    codigo_postal: str = Field(
        min_length=5, max_length=5, description="`LugarExpedicion` del comprobante."
    )
    clave_entidad: str = Field(
        min_length=3,
        max_length=3,
        description="`ClaveEntFed` del catálogo `c_Estado`. **Sin default**: "
        "`VER` es la del patrón del caso real (§D8), no la de nadie más.",
    )


class DatosTrabajadorCFDI(BaseModel):
    """
    El receptor. Ver `24_cfdi_nomina_12.md` §2.

    `salario_base_cotizacion` y `salario_diario_integrado` se **reciben**, no se
    recomputan: por §D9 el SDI que viene de un CFDI es dato de entrada y los
    factores del caso real no son derivables de la antigüedad.
    """

    rfc: str = Field(min_length=12, max_length=13)
    nombre: str = Field(min_length=1)
    curp: str = Field(min_length=18, max_length=18)
    numero_seguridad_social: str = Field(min_length=1)
    codigo_postal: str = Field(
        min_length=5, max_length=5, description="`DomicilioFiscalReceptor`."
    )
    fecha_inicio_relacion_laboral: date
    tipo_contrato: str = Field(
        min_length=2, max_length=2, description="Clave de `c_TipoContrato`."
    )
    numero_empleado: str = Field(min_length=1)
    puesto: str = Field(min_length=1)
    riesgo_puesto: str = Field(
        min_length=1,
        max_length=2,
        description="Clave de `c_RiesgoPuesto`: la clase de riesgo del patrón "
        "(I–V). **Sin default**: el `99` de 'no aplica' es una afirmación sobre "
        "el puesto, no un relleno.",
    )
    periodicidad_pago: str = Field(
        min_length=2, max_length=2, description="Clave de `c_PeriodicidadPago`."
    )
    salario_base_cotizacion: Decimal = Field(ge=0)
    salario_diario_integrado: Decimal = Field(ge=0)
    antiguedad: str = Field(
        default="",
        description="`Antigüedad` en formato ISO 8601 `P##W` (§2 del doc 24). "
        "Vacío = se deriva de `fecha_inicio_relacion_laboral` a la fecha final "
        "del periodo, en semanas completas. Se acepta capturada porque el CFDI "
        "timbrado del que venga un histórico ya la trae y reescribirla movería "
        "un dato que no es nuestro.",
    )
    departamento: str = ""
    sindicalizado: str = Field(default="No", pattern="^(Sí|Si|No)$")
    tipo_jornada: str = Field(
        default="01", min_length=2, max_length=2, description="`c_TipoJornada`: 01 diurna."
    )
    tipo_regimen: str = Field(
        default="02",
        min_length=2,
        max_length=2,
        description="`c_TipoRegimen`: 02 sueldos y salarios (doc 24 §2).",
    )


class CFDINominaRequest(BaseModel):
    """
    Todo lo que hace falta para serializar un pre-recibo. Ver `CFDINominaResponse`.

    `extra="forbid"` por la misma razón que en `SBCRequest`: un campo que este
    endpoint no conoce —un `total` "de cortesía", un `sello`— se ignoraría en
    silencio y el emisor creería que viajó.
    """

    model_config = ConfigDict(extra="forbid")

    recibo: ReciboCFDISchema
    patron: DatosPatronCFDI
    trabajador: DatosTrabajadorCFDI
    periodo: PeriodoNomina = Field(
        description="`FechaInicialPago`, `FechaFinalPago` y `FechaPago` del "
        "complemento. La fecha de pago sale de `periodo.fecha_pago` con el "
        "mismo default que el resto del motor (`fin` si no viene)."
    )
    tipo_nomina: str = Field(
        default="O",
        pattern="^[OE]$",
        description="`c_TipoNomina`: O ordinaria, E extraordinaria.",
    )
    serie: str = ""
    folio: str = ""


class CFDINominaResponse(BaseModel):
    """
    El XML del pre-recibo. **`timbrado` es siempre `False` y no es decorativo.**

    Lo que sale de aquí es estructuralmente válido contra los XSD del SAT y
    fiscalmente nada: no lleva `tfd:TimbreFiscalDigital` y sus atributos de
    sello son centinelas explícitos. El timbrado con un PAC está **fuera de
    alcance** por el `CLAUDE.md` de la raíz, así que este campo no es un `False`
    que algún día se vuelva `True` solo: mientras exista, la respuesta afirma
    que el documento no tiene valor fiscal.
    """

    exito: bool = True
    xml: str
    timbrado: bool = Field(
        default=False,
        description="Siempre `false`. Este endpoint no timbra y no habla con ningún PAC.",
    )
    nombre_archivo: str = Field(
        description="Nombre sugerido para la descarga. Lleva `sin-timbrar` a "
        "propósito: un archivo suelto en la carpeta de descargas del contador "
        "no tiene dónde decir lo que es si no lo dice su nombre."
    )
    advertencia: str
