"""
Santander México — Pago de nómina (Enlace / Supernet). POR CONFIRMAR CON MANUAL DEL BANCO.

POR QUÉ NO ESTÁ VERIFICADO
--------------------------
Santander México no publica el layout de nómina: se entrega en el contrato del servicio. Lo
que se encontró en línea (runahr.com "Descarga layout para pagar la nómina en Santander",
worky.mx "Layout bancario Santander") lista los datos —cuenta, importe, nombre— sin
posiciones. Se implementa la versión de uso común en sistemas de nómina mexicanos, con tres
registros:

- Encabezado (39): "1" | secuencia 5 | sentido "E" | fecha de generación MMDDAAAA | cuenta de
  cargo 16 | fecha de aplicación MMDDAAAA.
- Detalle (127): "2" | secuencia 5 | número de empleado 7 | apellido paterno 30 | apellido
  materno 20 | nombre(s) 30 | cuenta 16 | importe 18 (16 enteros + 2 decimales, sin punto).
- Sumario (29): "3" | secuencia 5 | total de registros 5 | importe total 18.

Sólo abona a cuentas Santander (11 dígitos) o tarjetas Santander (16): el pago a otros bancos
va por otro servicio (SPEI) cuyo layout tampoco es público.
"""

from __future__ import annotations

from datetime import date

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import POR_CONFIRMAR, Abono, Cargo, Layout, Opciones, Pago, lineas, texto

ENCABEZADO = (
    Campo("tipo", 1, "N"), Campo("secuencia", 5, "N"), Campo("sentido", 1),
    Campo("fecha_generacion", 8, "N"), Campo("cuenta", 16), Campo("fecha_aplicacion", 8, "N"),
)
DETALLE = (
    Campo("tipo", 1, "N"), Campo("secuencia", 5, "N"), Campo("empleado", 7),
    Campo("paterno", 30, recortable=True), Campo("materno", 20, recortable=True),
    Campo("nombre", 30, recortable=True), Campo("cuenta", 16), Campo("importe", 18, "N"),
)
SUMARIO = (
    Campo("tipo", 1, "N"), Campo("secuencia", 5, "N"), Campo("registros", 5, "N"),
    Campo("importe", 18, "N"),
)


class Santander(Layout):
    id = "santander"
    nombre = "Santander"
    banco = "014"
    estado = "por_confirmar"
    fuente = (
        f"{POR_CONFIRMAR}. Santander no publica el layout de nómina; versión de uso común "
        "(encabezado 1 / detalle 2 / sumario 3)."
    )
    interbancario = False
    cuenta_digitos = (11,)
    acepta_clabe_mismo_banco = False

    def abono(self, pago: Pago) -> Abono | str:
        if len(rf.ascii_mayusculas(pago.empleado_no)) > 7:
            return "El número de empleado no cabe en el layout de Santander (7 posiciones)."
        return super().abono(pago)

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        f = f"{op.fecha_aplicacion:%m%d%Y}"
        hoy = f"{date.today():%m%d%Y}"
        renglones = [rf.escribir(ENCABEZADO, {
            "tipo": "1", "secuencia": "1", "sentido": "E", "fecha_generacion": hoy,
            "cuenta": cargo.numero, "fecha_aplicacion": f,
        }, self.nombre)]
        for i, (p, a) in enumerate(pagos, start=2):
            paterno, materno, nombres = p.apellido_paterno, p.apellido_materno, p.nombres
            if not paterno:  # sin apellidos capturados: el nombre completo, sin partirlo
                nombres = p.nombre
            renglones.append(rf.escribir(DETALLE, {
                "tipo": "2", "secuencia": str(i), "empleado": rf.ascii_mayusculas(p.empleado_no),
                "paterno": rf.ascii_mayusculas(paterno), "materno": rf.ascii_mayusculas(materno),
                "nombre": rf.ascii_mayusculas(nombres), "cuenta": a.numero,
                "importe": rf.centavos(p.centavos),
            }, self.nombre))
        renglones.append(rf.escribir(SUMARIO, {
            "tipo": "3", "secuencia": str(len(pagos) + 2), "registros": str(len(pagos)),
            "importe": rf.centavos(sum(p.centavos for p, _ in pagos)),
        }, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido) if x[0] == "2"]
