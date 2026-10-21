"""
Del recibo GUARDADO (P4-02) a los datos del CFDI de nómina: patrón, trabajador, partidas y
nodos opcionales (P4-11).

No calcula nada: los importes son los del motor tal como se guardaron. Lo que se decide aquí es
CÓMO se declaran, y cada decisión cita la Guía de llenado del CFDI de nómina (CFDI 4.0 /
complemento 1.2 rev. E, SAT):

- `MetodoPago` PUE, `Exportacion` 01, `ObjetoImp` 01, `ClaveProdServ` 84111505, `UsoCFDI`
  CN01, `RegimenFiscalReceptor` 605 (asalariados Y asimilados), `DomicilioFiscalReceptor` =
  CP del trabajador (obligatorio en 4.0).
- `FormaPago`: la Guía no lo enumera entre los atributos que deben registrarse en el CFDI de
  nómina; se OMITE (es opcional en `cfdv40.xsd`). # POR CONFIRMAR con la Guía vigente / PAC.
- `TipoNomina` O para ordinaria y asimilados; E para extraordinaria, finiquito, aguinaldo y PTU,
  con `PeriodicidadPago` 99 (la Guía: "si el tipo de nómina es extraordinaria, se debe
  registrar la clave 99").
- Asimilados (`TipoRegimen` 05-11): sin `RegistroPatronal` y, por la regla de la Guía, sin
  NSS, inicio de relación, antigüedad, riesgo, SBC ni SDI. `TipoContrato` 09 (modalidades de
  contratación donde no existe relación de trabajo).
- Finiquito con separación (022, 023, 025): la Guía pide `TipoRegimen` 13 (indemnización o
  separación). DECISIÓN PROVISIONAL (POR CONFIRMAR con la contadora): con 13 se declara
  `TipoContrato` 99 y SIN datos del IMSS, porque la matriz del SAT sólo admite TipoRegimen
  02-04 con TipoContrato 01-08. Un finiquito SIN separación sale como ordinario-extraordinario
  (TipoRegimen 02).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.exceptions import FiscalAgentError
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nucleo import Cliente
from app.nomina_engine.cfdi_nomina_xml import (
    ExtrasNomina,
    HorasExtraCfdi,
    IncapacidadCfdi,
    SeparacionCfdi,
)
from app.nomina_engine.periodo_completo_tipos import REGIMENES_ASIMILADOS
from app.nomina_engine.recibo import (
    CLAVES_SEPARACION,
    DatosPatron,
    DatosTrabajador,
    PartidaDeduccion,
    PartidaOtroPago,
    PartidaPercepcion,
    Recibo,
)
from app.nomina_engine.reglas_periodo import clasificar_horas_extra
from app.nomina_engine.variables_tipos import VariablesEmpleado
from app.schemas.empleado import EmpleadoCarteraSchema

CERO = Decimal("0.00")
TIPOS_ORDINARIOS = ("ordinaria", "asimilados")
CONTRATO = {"indeterminado": "01", "obra_determinada": "02", "determinado": "03", "prueba": "05"}
# DECISIÓN PROVISIONAL: horas extra por día para declarar `Dias` del nodo HorasExtra cuando la
# captura sólo trae horas. 3 es el máximo diario del Art. 66 LFT; dividir entre 3 da el MÍNIMO
# de días compatible con la ley.
HORAS_EXTRA_MAX_DIA = 3


@dataclass(frozen=True)
class DatosCfdi:
    recibo: Recibo
    patron: DatosPatron
    trabajador: DatosTrabajador
    extras: ExtrasNomina
    tipo_nomina: str
    dias_pagados: Decimal
    inicio: date
    fin: date
    pago: date


def _d(v: Any) -> Decimal:
    return Decimal(str(v if v not in (None, "") else "0"))


def antiguedad_semanas(inicio: date, fin: date) -> str:
    """`Antigüedad` en semanas completas hasta el fin del periodo (formato `P##W`)."""
    return f"P{max((fin - inicio).days, 0) // 7}W"


def _detalle(periodo: NominaPeriodo, empleado_no: str) -> dict[str, Any]:
    for r in (periodo.resultado or {}).get("recibos", []):
        if r.get("empleado_no") == empleado_no:
            return r
    return {}


def _variables(periodo: NominaPeriodo, empleado_no: str) -> dict[str, Any]:
    for v in (periodo.entrada or {}).get("variables", []) or []:
        if v.get("empleado_no") == empleado_no:
            return v
    return {}


def _texto(v: Any, defecto: str) -> str:
    s = str(v or "").strip()
    return s[:100] if s else defecto


def partidas(rec: ReciboNomina) -> Recibo:
    percepciones = tuple(
        PartidaPercepcion(
            tipo=p["tipo"], clave=_texto(p.get("clave"), f"P{p['tipo']}"),
            concepto=_texto(p.get("concepto"), f"Percepción {p['tipo']}"),
            gravado=_d(p.get("gravado")), exento=_d(p.get("exento")),
        ) for p in rec.percepciones
    )
    deducciones = [
        PartidaDeduccion(
            tipo=d["tipo"], clave=_texto(d.get("clave"), f"D{d['tipo']}"),
            concepto=_texto(
                d.get("concepto"), "ISR" if d["tipo"] == "002" else f"Deducción {d['tipo']}"),
            importe=_d(d.get("importe")),
        ) for d in rec.deducciones if _d(d.get("importe")) > 0
    ]
    if rec.isr > 0 and not any(d.tipo == "002" for d in deducciones):
        deducciones.insert(0, PartidaDeduccion("002", "D002", "ISR", rec.isr))
    otros = tuple(
        PartidaOtroPago(
            tipo=o["tipo"], clave=_texto(o.get("clave"), f"O{o['tipo']}"),
            concepto=_texto(o.get("concepto"), "Subsidio para el empleo"),
            importe=_d(o.get("importe")),
            subsidio_causado=_d(o["subsidio_causado"])
            if o.get("subsidio_causado") not in (None, "") else None,
        ) for o in rec.otros_pagos
    )
    return Recibo(percepciones=percepciones, deducciones=tuple(deducciones), otros_pagos=otros)


def _extras(
    periodo: NominaPeriodo, rec: ReciboNomina, recibo: Recibo, separacion: bool
) -> ExtrasNomina:
    var = _variables(periodo, rec.empleado_no)
    # La MISMA clasificación que el cálculo del recibo (tope diario + semanal proporcional):
    # si no, el CFDI declara horas que no cuadran con el importe (revisor P6-07, B1).
    capturadas = VariablesEmpleado(
        empleado_no=rec.empleado_no,
        horas_dobles=Decimal(str(var.get("horas_dobles") or 0)),
        horas_triples=Decimal(str(var.get("horas_triples") or 0)),
        horas_extra_por_dia=tuple(Decimal(str(h)) for h in var.get("horas_extra_por_dia") or ()),
    )
    clasificadas, _ = clasificar_horas_extra(
        capturadas, (periodo.fin - periodo.inicio).days + 1, periodo.fin, rec.empleado_no)
    dobles, triples = clasificadas.horas_dobles, clasificadas.horas_triples
    horas = []
    for p in recibo.percepciones:
        if p.tipo != "019":
            continue
        tipo, cantidad = ("02", triples) if p.clave.endswith("T") else ("01", dobles)
        if not cantidad or Decimal(str(cantidad)) <= 0:
            # Sin horas capturadas no se declara una hora inventada (revisor P4, obs. 6).
            raise FiscalAgentError(
                f"{rec.empleado_no}: falta capturar las horas extra ({p.clave}) del periodo.", 422)
        n = math.ceil(Decimal(str(cantidad)))
        horas.append(HorasExtraCfdi(p.clave, max(1, math.ceil(n / HORAS_EXTRA_MAX_DIA)), tipo, n,
                                    p.importe))
    incapacidades = tuple(
        IncapacidadCfdi(int(i["dias"]), str(i["tipo"]))
        for i in var.get("incapacidades", []) or [] if int(i.get("dias") or 0) > 0
    )
    sep = None
    if separacion:
        res = periodo.resultado or {}
        seps = [p for p in recibo.percepciones if p.tipo in CLAVES_SEPARACION]
        gravado = sum((p.gravado for p in seps), start=CERO)
        ultimo = _d(res.get("ultimo_sueldo_mensual"))
        acumulable = min(ultimo, gravado)
        sep = SeparacionCfdi(
            total_pagado=sum((p.importe for p in seps), start=CERO),
            anios_servicio=int(res.get("anios_para_exencion") or 0),
            ultimo_sueldo_mensual=ultimo, ingreso_acumulable=acumulable,
            ingreso_no_acumulable=gravado - acumulable,
        )
    return ExtrasNomina(horas_extra=tuple(horas), incapacidades=incapacidades, separacion=sep)


def armar(
    cliente: Cliente, periodo: NominaPeriodo, rec: ReciboNomina, ficha: EmpleadoCarteraSchema | None
) -> DatosCfdi:
    """Todo lo que necesita el generador, o 422 con la lista de lo que falta capturar."""
    datos = cliente.datos or {}
    if ficha is None:
        raise FiscalAgentError(f"{rec.empleado_no} ya no está en la cartera del cliente.", 422)
    recibo = partidas(rec)
    separacion = any(p.tipo in CLAVES_SEPARACION for p in recibo.percepciones)
    asimilado = ficha.tipo_regimen in REGIMENES_ASIMILADOS
    con_imss = not asimilado and not separacion
    falta = [n for n, v in (
        ("RFC del cliente", cliente.rfc or datos.get("rfc")),
        ("régimen del cliente", datos.get("regimen")),
        ("código postal del cliente", datos.get("codigo_postal")),
        ("entidad federativa del cliente", datos.get("clave_entidad")),
        ("RFC del trabajador", ficha.rfc), ("CURP del trabajador", ficha.curp),
        ("código postal (domicilio fiscal) del trabajador", ficha.codigo_postal),
    ) if not v]
    if len(str(cliente.rfc or datos.get("rfc") or "")) == 13 and not datos.get("curp"):
        # Guía de llenado nómina 1.2, Emisor/Curp: obligatoria si el patrón es persona física.
        falta.append("CURP del cliente (patrón persona física)")
    if con_imss:
        falta += [n for n, v in (
            ("registro patronal del cliente", datos.get("registro_patronal")),
            ("clase de riesgo del cliente", datos.get("clase_riesgo")),
            ("NSS del trabajador", ficha.nss), ("fecha de alta del trabajador", ficha.fecha_alta),
        ) if not v]
    if falta:
        raise FiscalAgentError(f"{rec.empleado_no}: falta capturar " + ", ".join(falta) + ".", 422)
    if abs(recibo.total - rec.neto) > Decimal("0.01"):
        raise FiscalAgentError(
            f"{rec.empleado_no}: el total del CFDI ({recibo.total}) no cuadra con el neto "
            f"guardado ({rec.neto}); no se timbra un recibo que no cuadra.", 422)
    rfc_patron = str(cliente.rfc or datos.get("rfc")).upper()
    patron = DatosPatron(
        rfc=rfc_patron, nombre=(cliente.nombre or "").upper(), regimen_fiscal=str(datos["regimen"]),
        registro_patronal=str(datos.get("registro_patronal") or "").upper() if con_imss else "",
        codigo_postal=str(datos["codigo_postal"]), clave_entidad=str(datos["clave_entidad"]),
        curp=str(datos.get("curp") or "") if len(rfc_patron) == 13 else "",
    )
    ordinaria = periodo.tipo in TIPOS_ORDINARIOS
    detalle = _detalle(periodo, rec.empleado_no)
    sbc = _d(detalle.get("sbc")) or ficha.salario_diario_integrado
    tipo_regimen = "13" if separacion else ficha.tipo_regimen
    contrato = "99" if separacion else ("09" if asimilado else CONTRATO[ficha.tipo_contrato.value])
    alta = ficha.fecha_alta
    trabajador = DatosTrabajador(
        rfc=ficha.rfc, nombre=ficha.nombre.upper(), curp=ficha.curp,
        numero_seguridad_social=ficha.nss, codigo_postal=ficha.codigo_postal,
        fecha_inicio_relacion_laboral=alta,
        antiguedad=antiguedad_semanas(alta, periodo.fin) if alta else "",
        tipo_contrato=contrato, tipo_regimen=tipo_regimen, numero_empleado=ficha.empleado_no,
        puesto=ficha.puesto[:100], riesgo_puesto=str(datos.get("clase_riesgo") or ""),
        periodicidad_pago=periodo.periodicidad if ordinaria else "99",
        salario_base_cotizacion=sbc if con_imss else None,
        salario_diario_integrado=ficha.salario_diario_integrado if con_imss else None,
        sindicalizado="Sí" if ficha.sindicalizado else "No",
        departamento=ficha.departamento[:100],
    )
    dias = _d(detalle.get("dias_pagados")) if ordinaria else Decimal("1")
    return DatosCfdi(
        recibo=recibo, patron=patron, trabajador=trabajador,
        extras=_extras(periodo, rec, recibo, separacion),
        tipo_nomina="O" if ordinaria else "E", dias_pagados=dias or Decimal("1"),
        inicio=periodo.inicio, fin=periodo.fin, pago=periodo.fecha_pago,
    )
