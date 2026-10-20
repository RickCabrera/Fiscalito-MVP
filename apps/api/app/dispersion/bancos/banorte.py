"""
Banorte — Nómina Empresarial (NE), dispersión masiva de pagos. VERIFICADO (con una nota).

FUENTE
------
Banorte, "Layout Pago de Nómina" (tutorial público de banca empresarial):
https://www.banorte.com/cms/empresas/tutoriales/pdf/Layout%20Pago%20de%20Nomina.pdf
(consultado 2026-10-19).

- Encabezado: H | "NE" | emisora 5 | fecha de proceso AAAAMMDD | consecutivo 2 (1-98) |
  registros 6 | importe 15 | altas 6 + 15 | bajas 6 + 15 | cuentas a verificar 6 (ceros) |
  acción 1 ("0" pago de nómina) | CR chequera 4 (blancos) | fecha adelanto fin 8 (sólo
  acción 1; blancos) | cuenta de cargo 10 | filler.
- Detalle (165): D | fecha de aplicación AAAAMMDD | número de empleado 10 | referencia del
  servicio 40 (blancos) | leyenda del ordenante 40 | importe 15 | banco receptor 3 | tipo de
  cuenta 2 (01 cheques, 03 tarjeta de débito, 40 CLABE) | cuenta 18 | tipo de movimiento "0" |
  acción "0" | IVA 8 (ceros) | filler 18.

Importes: 15 posiciones, 13 enteros y 2 decimales (sin punto).

NOTA — POR CONFIRMAR CON MANUAL DEL BANCO
----------------------------------------
El documento declara el encabezado de **169** posiciones pero su filler va de la 111 a la
165: los campos suman 165, igual que el detalle. Se emite a 165. Además CONTPAQi publicó en
2026 una "Actualización de Layout Banorte" (nómina programada AAAAMMDDHHMM tras la cuenta de
cargo, cuenta emisora en blancos) que el tutorial público no recoge.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import Abono, Cargo, DatoBanco, Layout, Opciones, Pago, lineas, texto
from app.exceptions import FiscalAgentError

ENCABEZADO = (
    Campo("tipo", 1), Campo("servicio", 2), Campo("emisora", 5, "N"), Campo("fecha", 8, "N"),
    Campo("consecutivo", 2, "N"), Campo("registros", 6, "N"), Campo("importe", 15, "N"),
    Campo("altas", 6, "N"), Campo("importe_altas", 15, "N"), Campo("bajas", 6, "N"),
    Campo("importe_bajas", 15, "N"), Campo("verificar", 6, "N"), Campo("accion", 1),
    Campo("cr_chequera", 4), Campo("fecha_adelanto", 8), Campo("cuenta_cargo", 10),
    Campo("filler", 55),
)
DETALLE = (
    Campo("tipo", 1), Campo("fecha", 8, "N"), Campo("empleado", 10),
    Campo("ref_servicio", 40), Campo("leyenda", 40, recortable=True), Campo("importe", 15, "N"),
    Campo("banco", 3, "N"), Campo("tipo_cuenta", 2, "N"), Campo("cuenta", 18, "N"),
    Campo("movimiento", 1, "N"), Campo("accion", 1), Campo("iva", 8, "N"), Campo("filler", 18),
)
TIPO_CUENTA = {"cuenta": "01", "tarjeta": "03", "clabe": "40"}


class Banorte(Layout):
    id = "banorte"
    nombre = "Banorte"
    banco = "072"
    estado = "verificado"
    fuente = (
        "Banorte, 'Layout Pago de Nómina' (banorte.com/cms/empresas/tutoriales/pdf/"
        "Layout Pago de Nomina.pdf), clave de servicio NE. Longitud del encabezado (169 vs "
        "165) POR CONFIRMAR CON MANUAL DEL BANCO."
    )
    interbancario = True
    cuenta_digitos = (10,)
    datos_requeridos = (
        DatoBanco("emisora", "Número de emisora Banorte (5 dígitos)", r"^\d{1,5}$"),
        DatoBanco("consecutivo", "Consecutivo del archivo en el día (1-98)", r"^\d{1,2}$",
                  obligatorio=False, default="1"),
    )

    def abono(self, pago: Pago) -> Abono | str:
        if len(rf.ascii_mayusculas(pago.empleado_no)) > 10:
            return "El número de empleado no cabe en el layout de Banorte (10 posiciones)."
        return super().abono(pago)

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        if not (cargo.numero.isdigit() and len(cargo.numero) == 10):
            raise FiscalAgentError("La cuenta de cargo Banorte son 10 dígitos.", 422)
        fecha = f"{op.fecha_aplicacion:%Y%m%d}"
        total = sum(p.centavos for p, _ in pagos)
        renglones = [rf.escribir(ENCABEZADO, {
            "tipo": "H", "servicio": "NE", "emisora": op.datos_banco["emisora"], "fecha": fecha,
            "consecutivo": op.datos_banco.get("consecutivo", "1"), "registros": str(len(pagos)),
            "importe": rf.centavos(total), "accion": "0", "cuenta_cargo": cargo.numero,
        }, self.nombre)]
        for p, a in pagos:
            renglones.append(rf.escribir(DETALLE, {
                "tipo": "D", "fecha": fecha, "empleado": rf.ascii_mayusculas(p.empleado_no),
                "leyenda": rf.ascii_mayusculas(op.concepto), "importe": rf.centavos(p.centavos),
                "banco": a.banco, "tipo_cuenta": TIPO_CUENTA[a.tipo], "cuenta": a.numero,
                "movimiento": "0", "accion": "0", "iva": "0",
            }, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido) if x[0] == "D"]
