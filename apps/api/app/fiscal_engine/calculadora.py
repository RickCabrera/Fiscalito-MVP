"""
Motor de calculo fiscal — el cerebro numerico del Fiscal Agent.

Calcula ISR e IVA segun el regimen del contribuyente y las facturas
del periodo. NO usa LLM para los calculos (son deterministas),
el LLM solo se usa para generar explicaciones en lenguaje natural.
"""

from __future__ import annotations
from app.schemas.fiscal import CFDI, PerfilContribuyente, TipoFactura, PeriodicidadDeclaracion
from app.schemas.declaraciones import DesgloseFiscal
from app.fiscal_engine.tablas_isr import (
    RESICO_TASAS_MENSUALES,
    TABLA_ISR_MENSUAL,
    TABLA_ISR_ANUAL,
    TASA_IVA,
    generar_tabla_acumulada,
)
from app.fiscal_engine.clasificador_gastos import clasificar_egresos


def clasificar_facturas(
    facturas: list[CFDI], rfc_contribuyente: str
) -> tuple[list[CFDI], list[CFDI]]:
    """
    Clasifica facturas en ingresos y egresos desde la perspectiva del contribuyente.

    Aplica base de flujo de efectivo (Art. 102 LISR):
    - PUE: se acumula en el mes de emision del CFDI.
    - PPD: NO se acumula hasta que exista un complemento de pago (tipo P).
    - Tipo P (complemento): acumula proporcionalmente con fecha del pago.
    """
    ingresos: list[CFDI] = []
    egresos: list[CFDI] = []

    rfc = rfc_contribuyente.upper()

    # Indexar facturas PPD por UUID para buscarlas desde complementos
    facturas_ppd = {
        f.uuid.upper(): f for f in facturas if f.metodo_pago == "PPD"
    }

    for f in facturas:
        # --- Facturas PUE: se acumulan normal ---
        if f.metodo_pago == "PUE" and f.tipo == TipoFactura.INGRESO:
            if f.rfc_emisor.upper() == rfc:
                ingresos.append(f)
            elif f.rfc_receptor.upper() == rfc:
                egresos.append(f)

        # --- Facturas PPD: se IGNORAN (no se acumulan) ---
        elif f.metodo_pago == "PPD" and f.tipo != TipoFactura.PAGO:
            pass  # No sumar. Se acumulara cuando llegue el complemento.

        # --- Complementos de Pago (tipo P): acumular el pago ---
        elif f.tipo == TipoFactura.PAGO:
            if f.uuid_relacionado:
                original = facturas_ppd.get(f.uuid_relacionado.upper())
                if original:
                    proporcion = (
                        (f.monto_pago or 0) / original.total
                        if original.total > 0 else 0
                    )
                    cfdi_efectivo = CFDI(
                        uuid=f.uuid,
                        fecha=f.fecha,
                        tipo=original.tipo,
                        rfc_emisor=original.rfc_emisor,
                        rfc_receptor=original.rfc_receptor,
                        subtotal=round(original.subtotal * proporcion, 2),
                        total=round(f.monto_pago or 0, 2),
                        iva_trasladado=round(original.iva_trasladado * proporcion, 2),
                        iva_retenido=round(original.iva_retenido * proporcion, 2),
                        isr_retenido=round(original.isr_retenido * proporcion, 2),
                        descuento=round(original.descuento * proporcion, 2),
                        metodo_pago="PUE",
                    )
                    if original.rfc_emisor.upper() == rfc:
                        ingresos.append(cfdi_efectivo)
                    elif original.rfc_receptor.upper() == rfc:
                        egresos.append(cfdi_efectivo)

        # --- Notas de credito (tipo E): mantener logica existente ---
        elif f.tipo == TipoFactura.EGRESO:
            if f.rfc_emisor.upper() == rfc:
                ingresos.append(f)
            else:
                egresos.append(f)

    return ingresos, egresos


def calcular_isr_resico(ingresos_gravados: float) -> tuple[float, float]:
    """
    Calcula ISR para RESICO PF: tasa fija sobre ingresos brutos.
    Art. 113-E LISR. Pagos mensuales definitivos.
    Retorna (isr_causado, tasa_aplicada).
    """
    if ingresos_gravados <= 0:
        return 0.0, 0.0

    for lim_inf, lim_sup, tasa in RESICO_TASAS_MENSUALES:
        if lim_inf <= ingresos_gravados <= lim_sup:
            return round(ingresos_gravados * tasa, 2), tasa

    # Si excede el rango mas alto, aplica tasa maxima
    tasa_max = RESICO_TASAS_MENSUALES[-1][2]
    return round(ingresos_gravados * tasa_max, 2), tasa_max


def _facturas_cubren_acumulado(ingresos: list[CFDI]) -> bool:
    """
    Safeguard Art. 106 LISR: verifica que las facturas de ingreso incluyan
    datos desde enero del ejercicio. Si la factura de ingreso mas temprana
    es posterior a enero, el contribuyente NO proporciono los meses
    anteriores y la tabla acumulada (x N meses) se aplicaria sobre una
    base incompleta -> el calculo seria incorrecto.

    Retorna True si puede aplicarse tabla acumulada, False si debe
    forzarse tabla mensual simple.
    """
    meses_con_ingreso = {f.fecha.month for f in ingresos if f.es_ingreso}
    if not meses_con_ingreso:
        return False
    return min(meses_con_ingreso) <= 1


def calcular_isr_general(
    base_gravable: float,
    es_anual: bool = False,
    meses_acumulados: int = 1,
) -> tuple[float, float]:
    """
    Calcula ISR con tabla progresiva (Art. 96 mensual / Art. 152 anual).

    Para pagos provisionales acumulativos (Art. 106, regimen 612),
    se usa meses_acumulados > 1 para generar la tabla acumulada.

    Retorna (isr_causado, tasa_efectiva).
    """
    if es_anual:
        tabla = TABLA_ISR_ANUAL
    elif meses_acumulados > 1:
        tabla = generar_tabla_acumulada(meses_acumulados)
    else:
        tabla = TABLA_ISR_MENSUAL

    if base_gravable <= 0:
        return 0.0, 0.0

    for lim_inf, lim_sup, cuota_fija, tasa_excedente in tabla:
        if lim_inf <= base_gravable <= lim_sup:
            excedente = base_gravable - lim_inf
            isr = cuota_fija + (excedente * tasa_excedente)
            tasa_efectiva = isr / base_gravable if base_gravable > 0 else 0
            return round(isr, 2), round(tasa_efectiva, 4)

    # Ultimo rango (sin limite superior)
    last = tabla[-1]
    excedente = base_gravable - last[0]
    isr = last[2] + (excedente * last[3])
    tasa_efectiva = isr / base_gravable
    return round(isr, 2), round(tasa_efectiva, 4)


def calcular_declaracion(
    contribuyente: PerfilContribuyente,
    facturas: list[CFDI],
    es_anual: bool = False,
    periodo_month: int | None = None,
    pagos_provisionales_anteriores: float = 0.0,
    predial_pagado: float = 0.0,
    ingresos_acumulados_anteriores: float = 0.0,
    deducciones_acumuladas_anteriores: float = 0.0,
) -> DesgloseFiscal:
    """
    Calcula una declaracion completa (ISR + IVA) para cualquier regimen.
    Este es el metodo principal que orquesta todo el calculo.

    Args:
        periodo_month: Mes del periodo (1-12). Para regimen 612/606, se usa como
            meses_acumulados en pagos provisionales Art. 106/116.
        pagos_provisionales_anteriores: ISR ya pagado en meses anteriores del
            mismo ejercicio. Se resta del ISR causado (Art. 106/116).
        ingresos_acumulados_anteriores: Ingresos gravados de meses anteriores
            del ejercicio (Art. 106). Para 612/606 con month > 1, se suman a los
            ingresos del mes actual para formar la base acumulada. Esto permite
            que el frontend mande SOLO las facturas del mes y los totales
            acumulados (que ya tiene en Firestore), sin necesidad de reenviar
            todas las facturas anteriores.
        deducciones_acumuladas_anteriores: Idem para deducciones autorizadas.
    """
    # 1. Clasificar facturas
    ingresos, egresos = clasificar_facturas(facturas, contribuyente.rfc)

    # 2. Filtrar gastos personales no deducibles (Art. 105 LISR / Art. 5-I LIVA)
    # Para 612/606/625: afecta ISR y IVA
    # Para 626 (RESICO): solo afecta IVA (ISR no deduce, pero IVA si acredita)
    regimen = contribuyente.regimen
    gastos_personales_excluidos = 0.0
    cantidad_gastos_personales = 0
    if regimen in ("612", "606", "625", "626"):
        egresos, personales, gastos_personales_excluidos = clasificar_egresos(
            egresos, ingresos,
        )
        cantidad_gastos_personales = len(personales)

    # 3. Sumar ingresos
    total_ingresos = sum(f.base_gravable for f in ingresos if f.es_ingreso)
    # Restar notas de credito emitidas
    notas_credito = sum(f.total for f in ingresos if f.es_egreso)
    ingresos_netos = total_ingresos - notas_credito

    # 4. Sumar egresos (gastos deducibles)
    total_egresos = sum(f.base_gravable for f in egresos)

    # 5. Calcular ISR segun regimen
    isr_causado = 0.0
    tasa_isr = 0.0
    base_isr = 0.0
    deducciones = 0.0
    deduccion_ciega_aplicada = False
    comparacion_deduccion: str | None = None
    retenciones_definitivas = False
    ingreso_anualizado_estimado = 0.0
    aplica_acumulado_art106 = False  # True solo si tabla acumulada x N realmente se uso
    ingresos_acumulados_resp = 0.0
    deducciones_acumuladas_resp = 0.0

    if regimen == "626":
        # RESICO: ISR sobre ingresos brutos, SIN deducciones (Art. 113-E)
        # Art. 113-J: si factura a PM, la retencion del 1.25% se acredita en paso 6
        # NOTA: deducciones ISR = 0, pero egresos ya fueron filtrados por el
        # clasificador para que IVA acreditable solo incluya gastos del negocio (Art. 5-I LIVA)
        base_isr = ingresos_netos
        deducciones = 0.0  # RESICO no deduce gastos operativos para ISR
        isr_causado, tasa_isr = calcular_isr_resico(base_isr)

    elif regimen == "606":
        # Arrendamiento: comparar deduccion real vs ciega (35%)
        # Art. 116: pagos provisionales con tabla acumulativa (Art. 106)
        meses = periodo_month if periodo_month and not es_anual else 1

        # Nuevo flujo Art. 106: si el caller mando totales acumulados de meses
        # anteriores explicitamente, los sumamos al mes actual y bypaseamos el
        # safeguard de facturas-cubren-enero (el caller ya tiene los datos).
        usar_acumulados_explicitos = (
            not es_anual and meses > 1 and (
                ingresos_acumulados_anteriores > 0
                or deducciones_acumuladas_anteriores > 0
            )
        )

        if usar_acumulados_explicitos:
            ingresos_para_isr = ingresos_netos + ingresos_acumulados_anteriores
            aplica_acumulado_art106 = True
        else:
            # Safeguard Art. 106 legacy: requiere facturas desde enero
            if meses > 1 and not _facturas_cubren_acumulado(ingresos):
                meses = 1
            aplica_acumulado_art106 = meses > 1
            ingresos_para_isr = ingresos_netos

        # Escenario A: deducciones reales (acumuladas si aplica)
        deducciones_reales_mes = total_egresos
        deducciones_reales_total = (
            deducciones_reales_mes + deducciones_acumuladas_anteriores
            if usar_acumulados_explicitos else deducciones_reales_mes
        )
        base_real = max(ingresos_para_isr - deducciones_reales_total, 0)
        isr_real, tasa_real = calcular_isr_general(
            base_real, es_anual=es_anual, meses_acumulados=meses,
        )

        # Escenario B: deduccion ciega del 35% + predial (Art. 115 LISR)
        # La ciega se aplica sobre los ingresos que pagaran ISR (acumulados si aplica)
        deducciones_ciega_total = (ingresos_para_isr * 0.35) + predial_pagado
        base_ciega = max(ingresos_para_isr - deducciones_ciega_total, 0)
        isr_ciega, tasa_ciega = calcular_isr_general(
            base_ciega, es_anual=es_anual, meses_acumulados=meses,
        )

        if isr_ciega <= isr_real:
            # Para el response: total_deducciones_autorizadas debe reflejar
            # solo el mes actual. Calculamos la ciega del mes only para el response.
            deducciones_ciega_mes = (ingresos_netos * 0.35) + predial_pagado
            deducciones = deducciones_ciega_mes
            deducciones_para_acum = deducciones_ciega_total
            base_isr = base_ciega
            isr_causado = isr_ciega
            tasa_isr = tasa_ciega
            deduccion_ciega_aplicada = True
            comparacion_deduccion = (
                f"Se aplico deduccion ciega (35%) porque resulta en menor ISR: "
                f"${isr_ciega:,.2f} vs ${isr_real:,.2f} con deducciones reales."
            )
        else:
            deducciones = deducciones_reales_mes
            deducciones_para_acum = deducciones_reales_total
            base_isr = base_real
            isr_causado = isr_real
            tasa_isr = tasa_real
            deduccion_ciega_aplicada = False
            comparacion_deduccion = (
                f"Se aplicaron deducciones reales porque resultan en menor ISR: "
                f"${isr_real:,.2f} vs ${isr_ciega:,.2f} con deduccion ciega."
            )

        # Totales acumulados para el response (Art. 106)
        if aplica_acumulado_art106:
            ingresos_acumulados_resp = ingresos_para_isr
            deducciones_acumuladas_resp = deducciones_para_acum
        else:
            ingresos_acumulados_resp = 0.0
            deducciones_acumuladas_resp = 0.0

    elif regimen == "612":
        # Actividad Empresarial / Honorarios: ingresos - deducciones
        # Art. 106: pagos provisionales acumulativos (tabla x meses)
        deducciones = total_egresos  # del mes actual
        meses = periodo_month if periodo_month and not es_anual else 1

        # Nuevo flujo Art. 106: si el caller mando totales acumulados de meses
        # anteriores explicitamente, los sumamos al mes actual y bypaseamos el
        # safeguard de facturas-cubren-enero. Esto permite que el frontend
        # envie SOLO las facturas del mes + los totales que ya tiene en Firestore.
        usar_acumulados_explicitos = (
            not es_anual and meses > 1 and (
                ingresos_acumulados_anteriores > 0
                or deducciones_acumuladas_anteriores > 0
            )
        )

        if usar_acumulados_explicitos:
            ingresos_para_isr = ingresos_netos + ingresos_acumulados_anteriores
            deducciones_para_isr = deducciones + deducciones_acumuladas_anteriores
            aplica_acumulado_art106 = True
        else:
            # Safeguard Art. 106 legacy: requiere facturas desde enero
            if meses > 1 and not _facturas_cubren_acumulado(ingresos):
                meses = 1
            aplica_acumulado_art106 = meses > 1
            ingresos_para_isr = ingresos_netos
            deducciones_para_isr = deducciones

        base_isr = max(ingresos_para_isr - deducciones_para_isr, 0)
        isr_causado, tasa_isr = calcular_isr_general(
            base_isr, es_anual=es_anual, meses_acumulados=meses,
        )

        # Totales acumulados para el response (Art. 106)
        if aplica_acumulado_art106:
            ingresos_acumulados_resp = ingresos_para_isr
            deducciones_acumuladas_resp = deducciones_para_isr
        else:
            ingresos_acumulados_resp = 0.0
            deducciones_acumuladas_resp = 0.0

    elif regimen == "625":
        # Plataformas Tecnologicas
        # Anualizar ingresos para determinar si aplican retenciones definitivas
        if es_anual:
            ingreso_anualizado_estimado = ingresos_netos
        else:
            ingreso_anualizado_estimado = ingresos_netos * 12

        if ingreso_anualizado_estimado <= 300_000:
            # Retenciones como pago definitivo (Art. 113-B LISR + LIF 2026)
            # La plataforma ya retuvo ISR e IVA. El contribuyente NO declara.
            retenciones_definitivas = True
            base_isr = ingresos_netos
            deducciones = 0.0
            isr_causado = 0.0
            tasa_isr = 0.0
        else:
            # Debe declarar normalmente, acreditando retenciones
            retenciones_definitivas = False
            deducciones = total_egresos
            base_isr = max(ingresos_netos - deducciones, 0)
            isr_causado, tasa_isr = calcular_isr_general(base_isr, es_anual=es_anual)

    elif regimen == "605":
        # Sueldos y Salarios: el patron ya retiene, solo aplica en anual
        base_isr = ingresos_netos
        deducciones = total_egresos  # Deducciones personales en anual
        if es_anual:
            base_isr = max(ingresos_netos - deducciones, 0)
        isr_causado, tasa_isr = calcular_isr_general(base_isr, es_anual=es_anual)

    else:
        # Regimen generico: usar tabla general
        deducciones = total_egresos
        base_isr = max(ingresos_netos - deducciones, 0)
        isr_causado, tasa_isr = calcular_isr_general(base_isr, es_anual=es_anual)

    # 5. Restar pagos provisionales anteriores (Art. 106/116)
    # Solo aplica cuando se uso tabla acumulada (meses > 1). Si el safeguard
    # forzo tabla mensual simple, los pagos anteriores NO se restan porque
    # el ISR causado ya corresponde solo al mes actual.
    pagos_aplicados = 0.0
    if (
        regimen in ("612", "606")
        and not es_anual
        and pagos_provisionales_anteriores > 0
        and aplica_acumulado_art106
    ):
        pagos_aplicados = pagos_provisionales_anteriores
        isr_causado = max(isr_causado - pagos_aplicados, 0)

    # 6. ISR retenido por terceros
    isr_retenido_total = sum(f.isr_retenido for f in ingresos)
    isr_a_pagar = max(isr_causado - isr_retenido_total, 0)

    # 7. Calcular IVA
    if retenciones_definitivas:
        # Pago definitivo: las retenciones de la plataforma cubren ISR e IVA
        # El contribuyente NO declara IVA aparte (Art. 113-B LISR)
        iva_cobrado = 0.0
        iva_pagado = 0.0
        iva_retenido_total = 0.0
        iva_a_pagar = 0.0
    else:
        # Calculo normal de IVA
        iva_cobrado = sum(f.iva_trasladado for f in ingresos if f.es_ingreso)
        iva_pagado = sum(f.iva_trasladado for f in egresos)
        iva_retenido_total = sum(f.iva_retenido for f in ingresos)
        iva_a_pagar = iva_cobrado - iva_pagado - iva_retenido_total
        # IVA puede ser negativo (saldo a favor)

    return DesgloseFiscal(
        total_ingresos_facturados=round(total_ingresos, 2),
        total_ingresos_gravados=round(ingresos_netos, 2),
        cantidad_facturas_ingreso=len([f for f in ingresos if f.es_ingreso]),
        total_egresos=round(total_egresos, 2),
        total_deducciones_autorizadas=round(deducciones, 2),
        cantidad_facturas_egreso=len(egresos),
        base_isr=round(base_isr, 2),
        tasa_isr=tasa_isr,
        isr_causado=round(isr_causado, 2),
        isr_retenido=round(isr_retenido_total, 2),
        isr_a_pagar=round(isr_a_pagar, 2),
        iva_trasladado_cobrado=round(iva_cobrado, 2),
        iva_trasladado_pagado=round(iva_pagado, 2),
        iva_retenido=round(iva_retenido_total, 2),
        iva_a_pagar=round(iva_a_pagar, 2),
        deduccion_ciega_aplicada=deduccion_ciega_aplicada,
        comparacion_deduccion=comparacion_deduccion,
        pagos_provisionales_anteriores=round(pagos_aplicados, 2),
        ingresos_acumulados=round(ingresos_acumulados_resp, 2),
        deducciones_acumuladas=round(deducciones_acumuladas_resp, 2),
        gastos_personales_excluidos=round(gastos_personales_excluidos, 2),
        cantidad_gastos_personales=cantidad_gastos_personales,
        retenciones_definitivas=retenciones_definitivas,
        ingreso_anualizado_estimado=round(ingreso_anualizado_estimado, 2),
        total_a_pagar=round(isr_a_pagar + max(iva_a_pagar, 0), 2),
    )
