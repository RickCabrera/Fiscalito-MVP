"""
BanBajío — Nómina electrónica (BajíoNet). POR CONFIRMAR CON MANUAL DEL BANCO.

SIN FUENTE PÚBLICA
------------------
BanBajío no publica el layout: su página de "Nómina Electrónica para Empresas"
(bb.com.mx/…/e-nomina-electronica) remite al ejecutivo, y la nota técnica pública de CONTPAQi
("Banco del Bajío", NT_Listado_Reportes_Nominas/banco_del_bajio.html) sólo dice que el TXT
lleva neto, cuenta y sucursal del empleado, y que "la estructura varía por banco".

Se implementa la versión mínima con lo que todo layout de nómina lleva —cuenta de cargo,
cuenta de abono, importe sin punto, nombre y referencia— en tres registros (01 encabezado, 02
detalle, 09 totales). **No subir sin contrastar contra el manual que entrega el banco al
contratar el servicio.** Sólo cuentas BanBajío (el interbancario no está documentado).

- 01 (51): "01" | cuenta de cargo 20 | fecha de aplicación AAAAMMDD | registros 6 | importe 15.
- 02 (95): "02" | secuencia 6 | tipo de cuenta 2 (01 cuenta, 03 tarjeta, 40 CLABE) | cuenta 20 |
  importe 15 (13 + 2, sin punto) | nombre 40 | referencia 10.
- 09 (23): "09" | registros 6 | importe 15.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import POR_CONFIRMAR, Abono, Cargo, Layout, Opciones, Pago, lineas, texto

ENCABEZADO = (
    Campo("registro", 2), Campo("cuenta_cargo", 20, "N"), Campo("fecha", 8, "N"),
    Campo("registros", 6, "N"), Campo("importe", 15, "N"),
)
DETALLE = (
    Campo("registro", 2), Campo("secuencia", 6, "N"), Campo("tipo_cuenta", 2, "N"),
    Campo("cuenta", 20, "N"), Campo("importe", 15, "N"), Campo("nombre", 40, recortable=True),
    Campo("referencia", 10),
)
TOTALES = (Campo("registro", 2), Campo("registros", 6, "N"), Campo("importe", 15, "N"))
TIPO_CUENTA = {"cuenta": "01", "tarjeta": "03", "clabe": "40"}


class BanBajio(Layout):
    id = "banbajio"
    nombre = "BanBajío"
    banco = "030"
    estado = "por_confirmar"
    fuente = (
        f"{POR_CONFIRMAR}. BanBajío no publica el layout de nómina; versión mínima con los "
        "datos que todo layout lleva (cuenta, importe sin punto, nombre, referencia)."
    )
    interbancario = False
    cuenta_digitos = (10, 11, 12)

    def abono(self, pago: Pago) -> Abono | str:
        if len(rf.ascii_mayusculas(pago.empleado_no)) > 10:
            return "El número de empleado no cabe en la referencia de BanBajío (10)."
        return super().abono(pago)

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        total = rf.centavos(sum(p.centavos for p, _ in pagos))
        renglones = [rf.escribir(ENCABEZADO, {
            "registro": "01", "cuenta_cargo": cargo.numero or cargo.clabe,
            "fecha": f"{op.fecha_aplicacion:%Y%m%d}", "registros": str(len(pagos)),
            "importe": total}, self.nombre)]
        for i, (p, a) in enumerate(pagos, start=1):
            renglones.append(rf.escribir(DETALLE, {
                "registro": "02", "secuencia": str(i), "tipo_cuenta": TIPO_CUENTA[a.tipo],
                "cuenta": a.numero, "importe": rf.centavos(p.centavos),
                "nombre": rf.ascii_mayusculas(p.nombre),
                "referencia": rf.ascii_mayusculas(p.empleado_no),
            }, self.nombre))
        renglones.append(rf.escribir(TOTALES, {"registro": "09", "registros": str(len(pagos)),
                                               "importe": total}, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido)
                if x.startswith("02")]
