"""
Traducción entre los esquemas de la API y los tipos del motor de nómina (P4).

Sin aritmética: sólo mueve campos. Vive aparte de la ruta por el tope de 300 líneas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app import nomina_servicio as srv
from app.constants import DIAS_MES_FISCAL
from app.modelos.nucleo import Cliente
from app.nomina_engine import variables as var
from app.nomina_engine.criterios import prestacion_efectiva
from app.nomina_engine.periodo_completo import ReciboCompleto
from app.redondeo import redondear
from app.schemas.empleado import EmpleadoCarteraSchema
from app.schemas.nomina_p4 import VariablesEmpleadoSchema
from app.tenancy import Contexto

CERO = Decimal("0.00")


def variables_del_schema(v: VariablesEmpleadoSchema) -> var.VariablesEmpleado:
    return var.VariablesEmpleado(
        empleado_no=v.empleado_no,
        horas_dobles=v.horas_dobles,
        horas_triples=v.horas_triples,
        horas_jornada=v.horas_jornada,
        domingos_trabajados=v.domingos_trabajados,
        prima_dominical=v.prima_dominical,
        dias_vacaciones=v.dias_vacaciones,
        prima_vacacional=v.prima_vacacional,
        incapacidades=tuple(var.Incapacidad(i.tipo, i.dias) for i in v.incapacidades),
        faltas_adicionales=v.faltas_adicionales,
        percepciones=tuple(
            var.PercepcionCapturada(p.clave, p.importe, p.concepto) for p in v.percepciones
        ),
        infonavit=var.CreditoInfonavit(
            v.infonavit.tipo, v.infonavit.valor, v.infonavit.valor_unidad_diario
        )
        if v.infonavit
        else None,
        fonacot=v.fonacot,
        prestamo=v.prestamo,
        pension=var.PensionAlimenticia(v.pension.tipo, v.pension.valor, v.pension.base)
        if v.pension
        else None,
        viaticos_comprobados=v.viaticos_comprobados,
        prima_vacacional_exenta_previa=v.prima_vacacional_exenta_previa,
        horas_extra_por_dia=tuple(v.horas_extra_por_dia),
    )


def recibo_como_dict(r: ReciboCompleto) -> dict[str, Any]:
    rec = r.recibo
    cuotas = r.cuotas
    return {
        "empleado_no": r.empleado_no,
        "nombre": r.nombre,
        "sbc": r.sbc,
        "sbc_piso_aplicado": r.sbc_piso_aplicado,
        "sbc_tope_aplicado": r.sbc_tope_aplicado,
        "es_salario_minimo": r.es_salario_minimo,
        "dias_periodo": r.dias_periodo,
        "dias_ausentismo": r.dias_ausentismo,
        "dias_pagados": r.dias_pagados,
        "percepciones": [
            {
                "tipo": p.tipo,
                "clave": p.clave,
                "concepto": p.concepto,
                "importe": p.importe,
                "gravado": p.gravado,
                "exento": p.exento,
            }
            for p in rec.percepciones
        ],
        "deducciones": [
            {"tipo": d.tipo, "clave": d.clave, "concepto": d.concepto, "importe": d.importe}
            for d in rec.deducciones
        ],
        "otros_pagos": [
            {
                "tipo": o.tipo,
                "clave": o.clave,
                "concepto": o.concepto,
                "importe": o.importe,
                "subsidio_causado": o.subsidio_causado,
            }
            for o in rec.otros_pagos
        ],
        "total_percepciones": rec.total_percepciones,
        "total_deducciones": rec.total_deducciones,
        "neto": rec.total,
        "cuota_obrera": cuotas.total_obrero if cuotas else CERO,
        "cuota_patronal": cuotas.total_patron if cuotas else CERO,
        "absorbio_cuota_obrera": cuotas.absorbio_cuota_obrera if cuotas else False,
        "ramos": [
            {
                "clave": x.clave,
                "nombre": x.nombre,
                "base_diaria": x.base_diaria,
                "dias": x.dias,
                "patron": x.patron,
                "obrero": x.obrero,
                "fundamento": x.fundamento,
            }
            for x in (cuotas.ramos if cuotas else ())
        ],
        "tipo_regimen": r.tipo_regimen,
        "dias_en_periodo": r.dias_en_periodo,
        "dias_incapacidad": r.dias_incapacidad,
        "parcial": r.parcial,
        "tarifa": r.tarifa,
        "isr_causado": r.isr_causado,
        "subsidio_causado": r.subsidio_causado,
        "sbc_variable_integrable": r.sbc_variable_integrable,
    }


def a_json(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: a_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [a_json(v) for v in x]
    if isinstance(x, (Decimal, date)):
        return str(x)
    return x


def fichas_por_numero(ctx: Contexto, cliente: Cliente) -> dict[str, EmpleadoCarteraSchema]:
    fichas, _ = srv.fichas_del_cliente(ctx.db, cliente)
    return {f.empleado_no: f for f in fichas}


def parametros_patron(cliente: Cliente) -> dict[str, Any]:
    return (cliente.datos or {}).get("parametros") or {}


def dias_aguinaldo_efectivos(cliente: Cliente, f: EmpleadoCarteraSchema) -> int:
    criterios = srv.criterios_del_cliente(cliente)
    del_patron = int(parametros_patron(cliente).get("dias_aguinaldo", 15))
    return prestacion_efectiva(del_patron, f.prestaciones.dias_aguinaldo, criterios.prestaciones)


def ordinario_mensual(f: EmpleadoCarteraSchema) -> Decimal:
    # DECISIÓN PROVISIONAL (nocturno): el ingreso ordinario mensual que piden el
    # Art. 96 y el Art. 174 RLISR es salario diario × 30.4 (mes fiscal).
    return redondear(f.salario_diario * DIAS_MES_FISCAL)


def guardar_calculo(
    ctx: Contexto,
    cliente: Cliente,
    tipo: str,
    inicio: date,
    fin: date,
    pago: date,
    entrada: Any,
    resultado: Any,
    filas: list[dict[str, Any]],
) -> int | None:
    """Guarda una nómina extraordinaria en el historial (P4-02)."""
    periodo = srv.guardar_periodo(
        ctx.db,
        cliente,
        ctx.despacho_id,
        ctx.uid,
        tipo=tipo,
        clave="99",
        inicio=inicio,
        fin=fin,
        fecha_pago=pago,
        criterios=srv.criterios_del_cliente(cliente).como_dict(),
        parametros=srv.parametros_vigentes(pago, "05", filas[0]["zona"] if filas else "general"),
        entrada=a_json(entrada),
        resultado=a_json(resultado),
        recibos=a_json(filas),
    )
    return periodo.id
