"""
Inventario y pool sintético de las fixtures de nómina (S-04).

Fuente única de verdad, importada tanto por `scripts/anonimizar_nomina.py` como
por `tests/test_fixtures_nomina.py`. Si el inventario viviera duplicado en los
dos, derivarían y el test dejaría de probar lo que cree probar.

El inventario es la verificación de fondo: no se comprueba que las fixtures "no
contengan datos reales" (una lista negra solo prueba lo que uno se acordó de
extraer), sino que **el conjunto de pares elemento@atributo es exactamente el
declarado** y que **cada atributo sustituido solo toma valores del conjunto
sintético**. Así un campo que se nos haya olvidado no pasa como limpio: aparece
como par no declarado y el test truena.
"""

from __future__ import annotations

import re

# ────────────────────────────────────────────────────────────
# Namespaces
# ────────────────────────────────────────────────────────────

NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "nomina12": "http://www.sat.gob.mx/nomina12",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# `Antigüedad` lleva diéresis: se nombra por constante para que ningún editor la
# rompa silenciosamente.
ANTIGUEDAD = "Antigüedad"

# ────────────────────────────────────────────────────────────
# Identidades sintéticas
# ────────────────────────────────────────────────────────────
#
# Pool curado y revisable a ojo, en el estilo que ya usa la casa en
# tests/test_calculadora.py (raíz de 4 letras + 010101 + 3 alfanuméricos).
# Se asigna BARAJADO con `secrets` en tiempo de generación y la asignación se
# descarta: no hay tabla de mapeo, ni semilla, ni HMAC. Sin llave no existe el
# oráculo de confirmación que permitiría verificar "¿esta persona está aquí?".
#
# Las raíces son deliberadamente ficticias y las CURP no conservan la
# distribución H/M real.

EMPLEADOS_SINTETICOS = [
    {"rfc": "XAAA010101AA1", "curp": "XAAA010101HVZBBB01", "nss": "01010101011",
     "nombre": "ANA BEATRIZ XALA MORA", "cp": "91000"},
    {"rfc": "XABB010101AA2", "curp": "XABB010101MVZBBB02", "nss": "01010101022",
     "nombre": "BRUNO CASTRO XIMENO", "cp": "91010"},
    {"rfc": "XACC010101AA3", "curp": "XACC010101HVZBBB03", "nss": "01010101033",
     "nombre": "CARLA DENISSE XOLO PEREZ", "cp": "91020"},
    {"rfc": "XADD010101AA4", "curp": "XADD010101MVZBBB05", "nss": "01010101044",
     "nombre": "DIEGO ELIAS XUNI ROMAN", "cp": "91030"},
    {"rfc": "XAEE010101AA5", "curp": "XAEE010101HVZBBB05", "nss": "01010101055",
     "nombre": "ELENA FABIOLA XEQUE SOLIS", "cp": "91040"},
    {"rfc": "XAFF010101AA6", "curp": "XAFF010101MVZBBB06", "nss": "01010101066",
     "nombre": "FELIPE GAEL XIRA TOVAR", "cp": "91050"},
    {"rfc": "XAGG010101AA7", "curp": "XAGG010101HVZBBB07", "nss": "01010101077",
     "nombre": "GLORIA HELENA XAMO VEGA", "cp": "91060"},
    {"rfc": "XAHH010101AA8", "curp": "XAHH010101MVZBBB08", "nss": "01010101088",
     "nombre": "HUGO IVAN XENA ZAMORA", "cp": "91070"},
    {"rfc": "XAII010101AA9", "curp": "XAII010101HVZBBB00", "nss": "01010101099",
     "nombre": "IRENE JIMENA XOCO AGUIRRE", "cp": "91080"},
]

PATRON_SINTETICO = {
    "rfc": "XAP0101011X0",
    "nombre": "PATRON DEMO SA DE CV",
    "registro_patronal": "X1234567890",
    "cp": "91090",
    "serie": "DEMOSA",
}

# Sellos y certificado: CONSTANTES FIJAS, nunca aleatorias. Bytes al azar acaban
# casando por casualidad con formas de 5 u 11 dígitos y volverían el test
# intermitente, lo que presiona a aflojarlo — y aflojar un test está prohibido.
# Longitudes iguales a las del origen para que la estructura sea realista.
SELLO_SINTETICO = "A" * 344            # multiplo de 4: base64 decodificable
CERTIFICADO_SINTETICO = "B" * 2148     # idem
NO_CERTIFICADO_SINTETICO = "00001000000000000001"
NO_CERTIFICADO_SAT_SINTETICO = "00001000000000000002"
RFC_PAC_SINTETICO = "XAP0101012X1"   # 3 letras + 6 digitos + 3 alfanumericos

# ────────────────────────────────────────────────────────────
# Inventario: cada par elemento@atributo, clasificado
# ────────────────────────────────────────────────────────────

SUSTITUIDOS: dict[tuple[str, str], str] = {
    # Comprobante — el Certificado es un X.509 que lleva el RFC y nombre del
    # emisor EN CLARO, más RFC y CURP de su representante legal.
    ("cfdi:Comprobante", "Certificado"): "certificado",
    ("cfdi:Comprobante", "Sello"): "sello",
    ("cfdi:Comprobante", "NoCertificado"): "no_certificado",
    ("cfdi:Comprobante", "Serie"): "serie",
    ("cfdi:Comprobante", "Folio"): "folio",
    ("cfdi:Comprobante", "LugarExpedicion"): "cp_patron",
    ("cfdi:Comprobante", "Fecha"): "fecha_derivada",
    # Emisor
    ("cfdi:Emisor", "Rfc"): "rfc_patron",
    ("cfdi:Emisor", "Nombre"): "nombre_patron",
    ("nomina12:Emisor", "RegistroPatronal"): "registro_patronal",
    # Receptor
    ("cfdi:Receptor", "Rfc"): "rfc_empleado",
    ("cfdi:Receptor", "Nombre"): "nombre_empleado",
    ("cfdi:Receptor", "DomicilioFiscalReceptor"): "cp_empleado",
    ("nomina12:Receptor", "Curp"): "curp_empleado",
    ("nomina12:Receptor", "NumSeguridadSocial"): "nss_empleado",
    ("nomina12:Receptor", "NumEmpleado"): "num_empleado",
    ("nomina12:Receptor", "FechaInicioRelLaboral"): "fecha_alta",
    ("nomina12:Receptor", ANTIGUEDAD): "antiguedad",
    ("nomina12:Receptor", "Departamento"): "generico",
    ("nomina12:Receptor", "Puesto"): "generico",
    ("nomina12:Receptor", "TipoJornada"): "generico",
    # Timbre
    ("tfd:TimbreFiscalDigital", "UUID"): "uuid",
    ("tfd:TimbreFiscalDigital", "SelloCFD"): "sello",
    ("tfd:TimbreFiscalDigital", "SelloSAT"): "sello",
    ("tfd:TimbreFiscalDigital", "NoCertificadoSAT"): "no_certificado_sat",
    ("tfd:TimbreFiscalDigital", "RfcProvCertif"): "rfc_pac",
    ("tfd:TimbreFiscalDigital", "FechaTimbrado"): "fecha_derivada",
}

# Intactos por decisión de Ricardo: son el valor fiscal del caso. Los cuatro
# atributos de texto libre (los `Concepto` y la `Descripcion`) el script los
# imprime a stdout antes de generar, para revisarlos a ojo: declararlos intactos
# no prueba que estén limpios, prueba que decidimos no mirarlos.
TEXTO_LIBRE_A_REVISAR = [
    ("cfdi:Concepto", "Descripcion"),
    ("nomina12:Percepcion", "Concepto"),
    ("nomina12:Deduccion", "Concepto"),
    ("nomina12:OtroPago", "Concepto"),
]

INTACTOS: set[tuple[str, str]] = {
    ("cfdi:Comprobante", "Descuento"), ("cfdi:Comprobante", "Exportacion"),
    ("cfdi:Comprobante", "MetodoPago"), ("cfdi:Comprobante", "Moneda"),
    ("cfdi:Comprobante", "SubTotal"), ("cfdi:Comprobante", "TipoDeComprobante"),
    ("cfdi:Comprobante", "Total"), ("cfdi:Comprobante", "Version"),
    ("cfdi:Comprobante", "xsi:schemaLocation"),
    ("cfdi:Concepto", "Cantidad"), ("cfdi:Concepto", "ClaveProdServ"),
    ("cfdi:Concepto", "ClaveUnidad"), ("cfdi:Concepto", "Descripcion"),
    ("cfdi:Concepto", "Descuento"), ("cfdi:Concepto", "Importe"),
    ("cfdi:Concepto", "ObjetoImp"), ("cfdi:Concepto", "ValorUnitario"),
    ("cfdi:Emisor", "RegimenFiscal"),
    ("cfdi:Receptor", "RegimenFiscalReceptor"), ("cfdi:Receptor", "UsoCFDI"),
    ("nomina12:Deduccion", "Clave"), ("nomina12:Deduccion", "Concepto"),
    ("nomina12:Deduccion", "Importe"), ("nomina12:Deduccion", "TipoDeduccion"),
    ("nomina12:Deducciones", "TotalImpuestosRetenidos"),
    ("nomina12:Deducciones", "TotalOtrasDeducciones"),
    ("nomina12:Nomina", "FechaFinalPago"), ("nomina12:Nomina", "FechaInicialPago"),
    ("nomina12:Nomina", "FechaPago"), ("nomina12:Nomina", "NumDiasPagados"),
    ("nomina12:Nomina", "TipoNomina"), ("nomina12:Nomina", "TotalDeducciones"),
    ("nomina12:Nomina", "TotalOtrosPagos"), ("nomina12:Nomina", "TotalPercepciones"),
    ("nomina12:Nomina", "Version"),
    ("nomina12:OtroPago", "Clave"), ("nomina12:OtroPago", "Concepto"),
    ("nomina12:OtroPago", "Importe"), ("nomina12:OtroPago", "TipoOtroPago"),
    ("nomina12:Percepcion", "Clave"), ("nomina12:Percepcion", "Concepto"),
    ("nomina12:Percepcion", "ImporteExento"), ("nomina12:Percepcion", "ImporteGravado"),
    ("nomina12:Percepcion", "TipoPercepcion"),
    ("nomina12:Percepciones", "TotalExento"), ("nomina12:Percepciones", "TotalGravado"),
    ("nomina12:Percepciones", "TotalSueldos"),
    ("nomina12:Receptor", "ClaveEntFed"), ("nomina12:Receptor", "PeriodicidadPago"),
    ("nomina12:Receptor", "RiesgoPuesto"), ("nomina12:Receptor", "SalarioBaseCotApor"),
    ("nomina12:Receptor", "SalarioDiarioIntegrado"), ("nomina12:Receptor", "Sindicalizado"),
    ("nomina12:Receptor", "TipoContrato"), ("nomina12:Receptor", "TipoRegimen"),
    ("nomina12:SubsidioAlEmpleo", "SubsidioCausado"),
    ("tfd:TimbreFiscalDigital", "Version"),
    ("tfd:TimbreFiscalDigital", "xsi:schemaLocation"),
}

INVENTARIO: set[tuple[str, str]] = set(SUSTITUIDOS) | INTACTOS

# Valores genéricos para los cuasi-identificadores de puesto.
GENERICOS = {"Departamento": "OPERACIONES", "Puesto": "OPERATIVO", "TipoJornada": "01"}

# ────────────────────────────────────────────────────────────
# Predicados de verificación
# ────────────────────────────────────────────────────────────
#
# La columna "sustituir" necesita DOS tipos de aserción: pertenencia a conjunto
# para las 9 identidades, y predicado para lo calculado (fechas, folio, uuid,
# antigüedad), que no sale de un pool corto.

RE_UUID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$")
RE_ANTIGUEDAD = re.compile(r"^P\d{1,4}W$")
RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
RE_FECHA_CORTA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_NUM_EMPLEADO = re.compile(r"^E-0[1-9]$")
RE_FOLIO = re.compile(r"^\d{1,3}$")

VALORES_ESPERADOS = {
    "rfc_empleado": {e["rfc"] for e in EMPLEADOS_SINTETICOS},
    "curp_empleado": {e["curp"] for e in EMPLEADOS_SINTETICOS},
    "nss_empleado": {e["nss"] for e in EMPLEADOS_SINTETICOS},
    "nombre_empleado": {e["nombre"] for e in EMPLEADOS_SINTETICOS},
    "cp_empleado": {e["cp"] for e in EMPLEADOS_SINTETICOS},
    "rfc_patron": {PATRON_SINTETICO["rfc"]},
    "nombre_patron": {PATRON_SINTETICO["nombre"]},
    "registro_patronal": {PATRON_SINTETICO["registro_patronal"]},
    "cp_patron": {PATRON_SINTETICO["cp"]},
    "serie": {PATRON_SINTETICO["serie"]},
    "sello": {SELLO_SINTETICO},
    "certificado": {CERTIFICADO_SINTETICO},
    "no_certificado": {NO_CERTIFICADO_SINTETICO},
    "no_certificado_sat": {NO_CERTIFICADO_SAT_SINTETICO},
    "rfc_pac": {RFC_PAC_SINTETICO},
    "generico": set(GENERICOS.values()),
}

PREDICADOS = {
    "uuid": RE_UUID.match,
    "antiguedad": RE_ANTIGUEDAD.match,
    "fecha_derivada": RE_FECHA.match,
    "fecha_alta": RE_FECHA_CORTA.match,
    "num_empleado": RE_NUM_EMPLEADO.match,
    "folio": RE_FOLIO.match,
}

# Antiguedad publicada: se deriva SOLO de datos publicos (el primer periodo del
# empleado en las propias fixtures) y del indice sintetico E-0X, que ya es una
# permutacion independiente del origen. No depende de la fecha de alta real ni
# del orden real de antiguedades, asi que es NO INVERTIBLE por construccion.
#
# Ninguno es multiplo de 7: en el origen todas las altas caen en el mismo dia
# de la semana y conservar esa regularidad seria conservar una huella.
#
# Costo aceptado: la antiguedad publicada es ficticia. Es irrelevante para F1 --
# D9 ya fija que el SalarioDiarioIntegrado se toma como dato de entrada y no se
# deriva de la antiguedad -- y es el precio de que no haya fuga alguna.
ESCALERA_ANTIGUEDAD_DIAS = [190, 410, 645, 870, 1100, 1333, 1555, 1780, 2010]

# Reparto esperado de archivos por semana: la transición 9 -> 8 -> 7 empleados
# es lo que da valor al caso.
REPARTO_SEMANAL = [9, 9, 9, 8, 7, 7, 7, 7, 7]
TOTAL_ARCHIVOS = sum(REPARTO_SEMANAL)  # 70
