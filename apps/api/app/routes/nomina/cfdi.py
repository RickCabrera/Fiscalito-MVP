"""
CFDI de nómina 4.0 + complemento 1.2, SIN TIMBRAR (T4).

Vive aparte de `periodo.py` (F1-07): serializa un recibo ya calculado; no calcula nada.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.exceptions import FiscalValidationError
from app.nomina_engine.cfdi_nomina_xml import generar_cfdi_nomina
from app.nomina_engine.recibo import (
    DatosPatron,
    DatosTrabajador,
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)
from app.routes.nomina._comun import router
from app.schemas.declaraciones import ErrorResponse
from app.schemas.nomina import (
    CFDINominaRequest,
    CFDINominaResponse,
    PartidaSchema,
)

# ── CFDI de nómina sin timbrar (T4) ─────────────────────────────────────────


def _percepciones_cfdi(partidas: tuple[PartidaSchema, ...]) -> tuple[PartidaPercepcion, ...]:
    """
    Las percepciones tal como llegaron, partidas en gravado y exento.

    `gravado` y `exento` son opcionales en `PartidaSchema` porque deducciones y
    otros pagos no los usan. En una percepción, que llegue `null` NO significa
    cero exento: significa que el emisor no partió la percepción. Se rechaza en
    vez de asumir, porque asumir "todo gravado" o "todo exento" cambia la base
    del ISR de un recibo que alguien va a firmar.
    """
    partidas_cfdi = []
    for p in partidas:
        if p.gravado is None or p.exento is None:
            raise FiscalValidationError(
                f"La percepción {p.tipo} ({p.concepto}) no trae el desglose "
                f"gravado/exento que el CFDI exige. Sale de "
                f"`/nomina/calcular-periodo`, que siempre lo manda."
            )
        partidas_cfdi.append(
            PartidaPercepcion(
                tipo=p.tipo,
                clave=p.clave,
                concepto=p.concepto,
                gravado=p.gravado,
                exento=p.exento,
            )
        )
    return tuple(partidas_cfdi)


def _antiguedad_en_semanas(inicio: date, fin_del_periodo: date) -> str:
    """
    `Antigüedad` del complemento, en el formato ISO 8601 `P##W` del doc 24 §2.

    **Semanas COMPLETAS transcurridas**, medidas contra la fecha final del
    periodo que se paga y no contra hoy: un recibo de una quincena de agosto
    emitido en septiembre no le agrega semanas al trabajador.

    Es aritmética de calendario, no de dinero, y por eso vive en la ruta y no
    en el motor: no toca ninguna base gravable. El emisor que ya la traiga
    —porque su histórico viene de un CFDI timbrado— la manda y ésta no se usa.
    """
    dias = (fin_del_periodo - inicio).days
    if dias < 0:
        raise FiscalValidationError(
            f"La relación laboral empieza el {inicio}, después del fin del "
            f"periodo ({fin_del_periodo}): no hay antigüedad que declarar."
        )
    return f"P{dias // 7}W"


@router.post(
    "/nomina/cfdi",
    response_model=CFDINominaResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Generar el CFDI de nómina 4.0 + complemento 1.2, SIN TIMBRAR",
    description="Serializa un recibo ya calculado a XML **estructuralmente válido contra "
    "los XSD del SAT y fiscalmente nada**: sin `tfd:TimbreFiscalDigital` y con centinelas "
    "explícitos en los atributos de sello.\n\n"
    "**No timbra y no habla con ningún PAC** — está fuera de alcance por el `CLAUDE.md` de "
    "la raíz. `timbrado` viaja en la respuesta y siempre vale `false`.\n\n"
    "**No calcula nada.** Los importes llegan de `/nomina/calcular-periodo` y aquí sólo se "
    "suman para los totales que el comprobante exige (`nomina_engine/recibo.py` es "
    "aritmética pura sobre partidas dadas). Ni ISR ni cuotas se tocan.\n\n"
    "**No inventa identidades:** RFC, CURP, NSS, códigos postales, registro patronal y "
    "clave de entidad son obligatorios. Sin ellos responde 422 diciendo cuál falta, que es "
    "lo único honesto — un CFDI con datos de relleno lleva el nombre de una persona real.\n\n"
    "**Lo que el XSD NO valida:** las reglas de la Guía de llenado ni las validaciones "
    "adicionales del Anexo 20. Que valide aquí no es evidencia de que un PAC lo aceptaría.",
)
async def cfdi_de_nomina(req: CFDINominaRequest) -> CFDINominaResponse:
    trabajador = req.trabajador
    recibo = Recibo(
        percepciones=_percepciones_cfdi(req.recibo.percepciones),
        deducciones=tuple(
            PartidaDeduccion(tipo=d.tipo, clave=d.clave, concepto=d.concepto, importe=d.importe)
            for d in req.recibo.deducciones
        ),
        otros_pagos=tuple(
            PartidaOtroPago(
                tipo=o.tipo,
                clave=o.clave,
                concepto=o.concepto,
                importe=o.importe,
                subsidio_causado=o.subsidio_causado,
            )
            for o in req.recibo.otros_pagos
        ),
    )

    xml = generar_cfdi_nomina(
        recibo=recibo,
        patron=DatosPatron(
            rfc=req.patron.rfc,
            nombre=req.patron.nombre,
            regimen_fiscal=req.patron.regimen_fiscal,
            registro_patronal=req.patron.registro_patronal,
            codigo_postal=req.patron.codigo_postal,
            clave_entidad=req.patron.clave_entidad,
        ),
        trabajador=DatosTrabajador(
            rfc=trabajador.rfc,
            nombre=trabajador.nombre,
            curp=trabajador.curp,
            numero_seguridad_social=trabajador.numero_seguridad_social,
            codigo_postal=trabajador.codigo_postal,
            fecha_inicio_relacion_laboral=trabajador.fecha_inicio_relacion_laboral,
            antiguedad=trabajador.antiguedad
            or _antiguedad_en_semanas(
                trabajador.fecha_inicio_relacion_laboral, req.periodo.fin
            ),
            tipo_contrato=trabajador.tipo_contrato,
            tipo_regimen=trabajador.tipo_regimen,
            numero_empleado=trabajador.numero_empleado,
            puesto=trabajador.puesto,
            departamento=trabajador.departamento,
            riesgo_puesto=trabajador.riesgo_puesto,
            periodicidad_pago=trabajador.periodicidad_pago,
            salario_base_cotizacion=trabajador.salario_base_cotizacion,
            salario_diario_integrado=trabajador.salario_diario_integrado,
            sindicalizado=trabajador.sindicalizado,
            tipo_jornada=trabajador.tipo_jornada,
        ),
        # La hora de emisión es la del servidor y NO es un dato del negocio: el
        # comprobante no está timbrado, así que no hay plazo de 72 horas que
        # cumplir ni fecha que conciliar. Lo que sí importa —y viene del
        # periodo— son las tres fechas de pago del complemento.
        fecha_emision=datetime.now(),
        fecha_inicial_pago=req.periodo.inicio,
        fecha_final_pago=req.periodo.fin,
        fecha_pago=req.periodo.pago,
        # `NumDiasPagados` es fraccionable (doc 24 §2) y el motor lo devuelve
        # entero: se promueve sin redondear a nada.
        dias_pagados=Decimal(req.recibo.dias_pagados),
        tipo_nomina=req.tipo_nomina,
        serie=req.serie,
        folio=req.folio,
    )

    return CFDINominaResponse(
        xml=xml,
        nombre_archivo=(
            f"cfdi-nomina-sin-timbrar-{req.recibo.empleado_no}-"
            f"{req.periodo.inicio}-{req.periodo.fin}.xml"
        ),
        advertencia=(
            "Pre-recibo SIN TIMBRAR. No tiene valor fiscal: no lleva Timbre Fiscal "
            "Digital y sus atributos de sello son centinelas. Para que sea un CFDI "
            "hay que timbrarlo con un PAC."
        ),
    )
