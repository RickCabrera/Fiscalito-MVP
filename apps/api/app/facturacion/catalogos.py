"""
Catálogos SAT mínimos para emitir CFDI 4.0 de ingreso, egreso y pago (P5-04).

FUENTE
------
- Claves: las enumeraciones de `catCFDI.xsd` (c_FormaPago, c_MetodoPago, c_UsoCFDI,
  c_RegimenFiscal, c_ObjetoImp, c_TipoRelacion, c_Exportacion, c_Impuesto, c_ClaveUnidad,
  c_ClaveProdServ) que viven en `app/nomina_cfdi/xsd/catCFDI.xsd` (descargado del SAT el
  2026-09-01, SHA-256 en `tests/xsd/README.md`). `tests/plan_p/test_facturacion.py` verifica
  que CADA clave de aquí exista en esa enumeración: si el SAT la retira, el test lo dice.
- Descripciones: la base de catálogos del paquete `satcfdi` 26.10.1 (MIT,
  `satcfdi/catalogs/catalogs.db`, tablas `C756_c_*`), que transcribe el catálogo del Anexo 20.
- Tasas: IVA 16 % (Art. 1o. LIVA), 0 % (Art. 2o.-A LIVA); retención de IVA de dos terceras
  partes (Art. 1o.-A fr. II inciso a LIVA y Art. 3o. fr. I RLIVA → 0.106667 al declarar con seis
  decimales); retención de ISR 10 % por servicios profesionales de persona física a persona
  moral (Art. 106 último párrafo LISR) y 1.25 % al RESICO de personas físicas (Art. 113-J LISR).
  Son PRESETS de la pantalla, no reglas: el despacho captura la tasa de cada concepto.

Sólo es lo MÍNIMO para facturar servicios. No incluye la matriz de compatibilidad UsoCFDI ↔
RegimenFiscalReceptor del catálogo c_UsoCFDI: la valida el PAC real (el falso no).
# FUENTE POR CONFIRMAR: matriz UsoCFDI ↔ régimen del receptor del catálogo vigente.
"""

from __future__ import annotations

from decimal import Decimal

FORMA_PAGO = {
    "01": "Efectivo", "02": "Cheque nominativo", "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito", "05": "Monedero electrónico", "06": "Dinero electrónico",
    "08": "Vales de despensa", "12": "Dación en pago", "13": "Pago por subrogación",
    "14": "Pago por consignación", "15": "Condonación", "17": "Compensación",
    "23": "Novación", "24": "Confusión", "25": "Remisión de deuda",
    "26": "Prescripción o caducidad", "27": "A satisfacción del acreedor",
    "28": "Tarjeta de débito", "29": "Tarjeta de servicios", "30": "Aplicación de anticipos",
    "31": "Intermediario pagos", "99": "Por definir",
}
METODO_PAGO = {"PUE": "Pago en una sola exhibición", "PPD": "Pago en parcialidades o diferido"}
USO_CFDI = {
    "G01": "Adquisición de mercancías", "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general", "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones", "I03": "Equipo de transporte",
    "I04": "Equipo de computo y accesorios", "I06": "Comunicaciones telefónicas",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales", "CP01": "Pagos",
}
REGIMEN_FISCAL = {
    "601": "General de Ley Personas Morales", "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios", "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes", "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses", "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades", "624": "Coordinados",
    "625": "Régimen de las Actividades Empresariales con ingresos a través de Plataformas "
           "Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
}
# Sólo los que este emisor sabe declarar: 01 sin nodo de impuestos, 02 con desglose, 03 sin
# desglose. 04-08 tienen reglas propias (IEPS, PODEBI) que este módulo no implementa.
OBJETO_IMP = {
    "01": "No objeto de impuesto", "02": "Sí objeto de impuesto",
    "03": "Sí objeto del impuesto y no obligado al desglose",
}
TIPO_RELACION = {
    "01": "Nota de crédito de los documentos relacionados",
    "02": "Nota de débito de los documentos relacionados",
    "03": "Devolución de mercancía sobre facturas o traslados previos",
    "04": "Sustitución de los CFDI previos",
    "07": "CFDI por aplicación de anticipo",
}
EXPORTACION = {"01": "No aplica"}
IMPUESTO = {"001": "ISR", "002": "IVA"}
CLAVE_UNIDAD = {"E48": "Unidad de servicio", "ACT": "Actividad", "H87": "Pieza"}
# Claves de producto o servicio sugeridas (la pantalla deja capturar cualquiera de 8 dígitos;
# el XSD la valida contra el catálogo completo).
CLAVE_PROD_SERV = {
    "84111500": "Servicios contables", "84111502": "Servicio de contabilidad financiera",
    "84111503": "Servicio de contabilidad fiscal", "84111504": "Servicios de teneduría de libros",
    "84111505": "Servicios de contabilidad de sueldos y salarios",
    "84111506": "Servicios de facturación", "01010101": "No existe en el catálogo",
}
# El CFDI de pago lleva un solo concepto fijo (Guía de llenado del complemento de pagos 2.0).
CONCEPTO_PAGO = {"ClaveProdServ": "84111506", "Cantidad": "1", "ClaveUnidad": "ACT",
                 "Descripcion": "Pago", "ValorUnitario": "0", "Importe": "0", "ObjetoImp": "01"}
MOTIVO_CANCELACION = {
    "01": "Comprobante emitido con errores con relación",
    "02": "Comprobante emitido con errores sin relación",
    "03": "No se llevó a cabo la operación",
    "04": "Operación nominativa relacionada en una factura global",
}

TASA_IVA_GENERAL = Decimal("0.160000")
TASA_IVA_CERO = Decimal("0.000000")
TASA_RET_IVA_DOS_TERCIOS = Decimal("0.106667")
TASA_RET_ISR_HONORARIOS = Decimal("0.100000")
TASA_RET_ISR_RESICO = Decimal("0.012500")
PRESETS = {
    "traslados": [
        {"clave": "iva16", "impuesto": "002", "tipo_factor": "Tasa", "tasa": "0.160000",
         "nombre": "IVA 16 %"},
        {"clave": "iva0", "impuesto": "002", "tipo_factor": "Tasa", "tasa": "0.000000",
         "nombre": "IVA 0 %"},
        {"clave": "exento", "impuesto": "002", "tipo_factor": "Exento", "tasa": None,
         "nombre": "IVA exento"},
    ],
    "retenciones": [
        {"clave": "ret_iva", "impuesto": "002", "tasa": "0.106667",
         "nombre": "Retención IVA 2/3"},
        {"clave": "ret_isr10", "impuesto": "001", "tasa": "0.100000",
         "nombre": "Retención ISR 10 %"},
        {"clave": "ret_isr_resico", "impuesto": "001", "tasa": "0.012500",
         "nombre": "Retención ISR RESICO 1.25 %"},
    ],
}
# Topes de tasa que acepta la captura (no son legales: evitan una errata de dedo).
# c_TasaOCuota (Anexo 20): IVA trasladado con factor Tasa sólo admite 0, 8 % y 16 %.
TASAS_IVA_TRASLADO = frozenset({Decimal("0"), Decimal("0.08"), Decimal("0.16")})
TASA_MAXIMA = {("traslado", "002"): Decimal("0.16"), ("retencion", "002"): Decimal("0.16"),
               ("retencion", "001"): Decimal("0.35")}


def como_lista(cat: dict[str, str]) -> list[dict[str, str]]:
    return [{"clave": k, "descripcion": v} for k, v in cat.items()]


def todos() -> dict[str, object]:
    """Lo que pinta la pantalla de facturación."""
    return {
        "forma_pago": como_lista(FORMA_PAGO), "metodo_pago": como_lista(METODO_PAGO),
        "uso_cfdi": como_lista(USO_CFDI), "regimen_fiscal": como_lista(REGIMEN_FISCAL),
        "objeto_imp": como_lista(OBJETO_IMP), "tipo_relacion": como_lista(TIPO_RELACION),
        "clave_unidad": como_lista(CLAVE_UNIDAD), "clave_prod_serv": como_lista(CLAVE_PROD_SERV),
        "motivo_cancelacion": como_lista(MOTIVO_CANCELACION), "presets": PRESETS,
    }
