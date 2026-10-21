"""
HSBC México — Pago de nómina, archivo MXPRLF (HSBCnet). POR CONFIRMAR CON MANUAL DEL BANCO.

FUENTE
------
No hay manual público de HSBC con posiciones (HSBC remite a "Carga de Archivos" de HSBCnet:
connect-content.us.hsbc.com, "Cuentas en México: identifique sus archivos de pagos de
nómina"). La especificación se tomó de la transcripción que publica Aspel NOI, "Generar
depósitos de pago de la nómina" (noiportaldeclientes.aspel.com.mx/generar-depositos-de-pago-
de-la-nomina/, consultada 2026-10-19):

- Encabezado (85): "MXPRLF" | nivel de autorización "F" | cuenta de cargo 10 | importe total
  14 (12 enteros + 2 decimales, sin punto) | total de operaciones 7 | fecha valor DDMMAAAA |
  hora de aplicación 5 (blancos si no se programa) | referencia del lote 34.
- Detalle (93): cuenta del beneficiario 10 (sólo cuentas HSBC de 10 dígitos) | importe 14 |
  referencia 34 (se imprime en el estado de cuenta) | nombre 35.

Es transcripción de un tercero, no del banco: por eso POR CONFIRMAR. Sólo abona a cuentas HSBC.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import POR_CONFIRMAR, Abono, Cargo, Layout, Opciones, Pago, lineas, texto
from app.exceptions import FiscalAgentError

ENCABEZADO = (
    Campo("formato", 6), Campo("autorizacion", 1), Campo("cuenta", 10, "N"),
    Campo("importe", 14, "N"), Campo("operaciones", 7, "N"), Campo("fecha", 8, "N"),
    Campo("hora", 5), Campo("referencia", 34, recortable=True),
)
DETALLE = (
    Campo("cuenta", 10, "N"), Campo("importe", 14, "N"), Campo("referencia", 34, recortable=True),
    Campo("nombre", 35, recortable=True),
)


class HSBC(Layout):
    id = "hsbc"
    nombre = "HSBC"
    banco = "021"
    estado = "por_confirmar"
    fuente = (
        f"{POR_CONFIRMAR}. Formato MXPRLF según la transcripción de Aspel NOI ('Generar depósitos "
        "de pago de la nómina'); HSBC no publica el manual."
    )
    interbancario = False
    cuenta_digitos = (10,)
    acepta_tarjeta = False
    acepta_clabe_mismo_banco = False

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        if not (cargo.numero.isdigit() and len(cargo.numero) == 10):
            raise FiscalAgentError("La cuenta de cargo HSBC son 10 dígitos.", 422)
        renglones = [rf.escribir(ENCABEZADO, {
            "formato": "MXPRLF", "autorizacion": "F", "cuenta": cargo.numero,
            "importe": rf.centavos(sum(p.centavos for p, _ in pagos)),
            "operaciones": str(len(pagos)), "fecha": f"{op.fecha_aplicacion:%d%m%Y}",
            "referencia": rf.ascii_mayusculas(op.concepto),
        }, self.nombre)]
        for p, a in pagos:
            renglones.append(rf.escribir(DETALLE, {
                "cuenta": a.numero, "importe": rf.centavos(p.centavos),
                "referencia": rf.ascii_mayusculas(f"{op.concepto} {p.empleado_no}"),
                "nombre": rf.ascii_mayusculas(p.nombre),
            }, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido)[1:]]
