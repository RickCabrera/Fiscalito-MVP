"""
Scotiabank México — Scotia Nómina / Dispersión de fondos. POR CONFIRMAR CON MANUAL DEL BANCO.

QUÉ SÍ ESTÁ PUBLICADO (por el banco)
------------------------------------
- "Pagos por medio de Scotia Nómina. Scotia en Línea"
  (cdn.aglty.io/scotia-bank-mexico/pdf/emp-gob/sel/Manual-Pago-Scotia-Nomina.pdf): número de
  cliente, número de archivo en el día (hasta 99), cuenta de cargo de **11 posiciones**, forma
  de pago 04 (depósito a cuenta), tipo de cuenta 1 (cheques 11), 2 (tarjeta 16), 3 (CLABE
  18), banco receptor (044 Scotiabank), importe **sin puntos ni comas, los dos últimos dígitos
  son centavos**, clave y nombre del beneficiario, referencia, días de vigencia (1).
- "Dispersión de fondos y estados de cuenta" (…/scotia-connect/Manual_Dispersion_de_fondos.pdf):
  los nombres de los campos del archivo (tipo de archivo, tipo de registro, número de
  convenio, secuencia, moneda de la cuenta de cargo 00 MXN, uso futuro en ceros, cuenta de
  cargo, referencia empresa numérica, tipo de movimiento, clave de moneda de pago, importe,
  fecha de aplicación, servicio/concepto, cuenta del beneficiario, tipo de cuenta, banco,
  días de vigencia).

QUÉ NO
------
Las **posiciones**. Ningún documento público las da. Los registros se arman con los
identificadores de uso común (EEHA encabezado de archivo, EEHB de bloque, EEDA detalle, EETB
y EETA totales) y anchuras deducidas de las restricciones publicadas. Todo POR CONFIRMAR.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import (
    POR_CONFIRMAR,
    Abono,
    Cargo,
    DatoBanco,
    Layout,
    Opciones,
    Pago,
    lineas,
    texto,
)
from app.exceptions import FiscalAgentError

ENC_ARCHIVO = (
    Campo("registro", 4), Campo("convenio", 5, "N"), Campo("secuencia", 2, "N"),
    Campo("fecha", 8, "N"), Campo("uso_futuro", 27, "N"),
)
ENC_BLOQUE = (
    Campo("registro", 4), Campo("moneda", 2, "N"), Campo("uso_futuro", 4, "N"),
    Campo("cuenta_cargo", 11, "N"), Campo("referencia_empresa", 10, "N"),
    Campo("filler", 15),
)
DETALLE = (
    Campo("registro", 4), Campo("movimiento", 2, "N"), Campo("moneda", 2, "N"),
    Campo("importe", 15, "N"), Campo("fecha", 8, "N"), Campo("concepto", 2, "N"),
    Campo("clave_beneficiario", 20), Campo("nombre", 40, recortable=True),
    Campo("referencia", 16, recortable=True), Campo("vigencia", 3, "N"),
    Campo("cuenta", 20, "N"), Campo("tipo_cuenta", 1, "N"), Campo("banco", 3, "N"),
)
TOTALES = (
    Campo("registro", 4), Campo("movimientos", 7, "N"), Campo("importe", 17, "N"),
    Campo("filler", 21),
)
TIPO_CUENTA = {"cuenta": "1", "tarjeta": "2", "clabe": "3"}


class Scotiabank(Layout):
    id = "scotiabank"
    nombre = "Scotiabank"
    banco = "044"
    estado = "por_confirmar"
    fuente = (
        f"{POR_CONFIRMAR}. Campos y reglas de 'Pagos por medio de Scotia Nómina' y "
        "'Dispersión de fondos' (manuales públicos de Scotiabank México); posiciones no "
        "publicadas."
    )
    interbancario = True
    cuenta_digitos = (11,)
    datos_requeridos = (
        DatoBanco("convenio", "Número de cliente / convenio Scotiabank (5 dígitos)", r"^\d{1,5}$"),
        DatoBanco("referencia_empresa", "Referencia de empresa (numérica, 10)", r"^\d{1,10}$"),
        DatoBanco("secuencia", "Número de archivo en el día (1-99)", r"^\d{1,2}$",
                  obligatorio=False, default="1"),
    )

    def abono(self, pago: Pago) -> Abono | str:
        if len(rf.ascii_mayusculas(pago.empleado_no)) > 20:
            return "El número de empleado no cabe en la clave de beneficiario (20)."
        return super().abono(pago)

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        if not (cargo.numero.isdigit() and len(cargo.numero) == 11):
            raise FiscalAgentError("La cuenta de cargo Scotiabank son 11 dígitos.", 422)
        fecha = f"{op.fecha_aplicacion:%Y%m%d}"
        total = rf.centavos(sum(p.centavos for p, _ in pagos))
        renglones = [
            rf.escribir(ENC_ARCHIVO, {"registro": "EEHA", "convenio": op.datos_banco["convenio"],
                                      "secuencia": op.datos_banco.get("secuencia", "1"),
                                      "fecha": fecha, "uso_futuro": "0"}, self.nombre),
            rf.escribir(ENC_BLOQUE, {"registro": "EEHB", "moneda": "0", "uso_futuro": "0",
                                     "cuenta_cargo": cargo.numero,
                                     "referencia_empresa": op.datos_banco["referencia_empresa"]},
                        self.nombre),
        ]
        for p, a in pagos:
            renglones.append(rf.escribir(DETALLE, {
                "registro": "EEDA", "movimiento": "04", "moneda": "0",
                "importe": rf.centavos(p.centavos), "fecha": fecha, "concepto": "1",
                "clave_beneficiario": rf.ascii_mayusculas(p.empleado_no),
                "nombre": rf.ascii_mayusculas(p.nombre),
                "referencia": rf.ascii_mayusculas(op.concepto), "vigencia": "1",
                "cuenta": a.numero, "tipo_cuenta": TIPO_CUENTA[a.tipo], "banco": a.banco,
            }, self.nombre))
        for registro in ("EETB", "EETA"):
            renglones.append(rf.escribir(TOTALES, {"registro": registro,
                                                   "movimientos": str(len(pagos)),
                                                   "importe": total}, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido)
                if x.startswith("EEDA")]
