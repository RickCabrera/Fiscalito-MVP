"""
Banamex (Citi) — Pago de nómina, LayOut "D" de BancaNet Empresarial. VERIFICADO.

FUENTE
------
Banamex, "Formato para la Importación de Archivos de Nómina Banamex - LayOut 'D'", ayuda
pública de BancaNet Empresarial:
https://www.bancanetempresarial.banamex.com.mx/spanishdir/bankhelp/hlp_fimp-nominadispersionesd.htm
(consultada 2026-10-19). Cuatro registros de longitud fija:

- Tipo 1 · Control (84): 1 | cliente 12 | fecha AAMMDD | secuencial 4 | razón social 36 |
  descripción 20 | naturaleza "15" | versión "D" | tipo de cargo "01".
- Tipo 2 · Global (51): 2 | operación "1" (cargo) | moneda "001" | importe 18 | tipo de
  cuenta "01" | cuenta de cargo 20 (sucursal en 10-13, cuenta en 14-20) | número de abonos 6.
- Tipo 3 · Detalle (419): 3 | operación "0" (abono) | método 001 Banamex / 002 interbancario |
  tipo de pago "01" nómina | moneda "001" | importe 18 | tipo de cuenta 01 cheques, 03
  tarjeta, 40 CLABE | cuenta 20 | referencia 16 | beneficiario 55 | 4 referencias de 35 |
  clave de banco 4 | plazo 2 | RFC 14 (blanco) | IVA 8 | 80 + 50 reservados (blanco).
- Tipo 4 · Totales (52): 4 | moneda "001" | abonos 6 | importe abonos 18 | cargos 6 ("1") |
  importe cargos 18.

Importes: 18 posiciones, 16 enteros y 2 decimales, sin punto, ceros a la izquierda.

LO QUE QUEDA POR CONFIRMAR DENTRO DE UN LAYOUT VERIFICADO
--------------------------------------------------------
- La **clave de banco** (4 posiciones) del interbancario sale "del catálogo" de Banamex, que
  no es público. Se escribe la clave ABM de 3 dígitos con un cero a la izquierda.
  POR CONFIRMAR CON MANUAL DEL BANCO.
- El **beneficiario** del interbancario va como "NOMBRE(S),PATERNO/MATERNO" con Ñ → @. El manual
  enumera letras, @, coma y diagonal; los espacios entre palabras de un nombre compuesto se
  conservan. POR CONFIRMAR CON MANUAL DEL BANCO.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.registro_fijo import Campo
from app.dispersion.tipos import Abono, Cargo, DatoBanco, Layout, Opciones, Pago, lineas, texto
from app.exceptions import FiscalAgentError

CONTROL = (
    Campo("tipo", 1, "N"), Campo("cliente", 12, "N"), Campo("fecha", 6, "N"),
    Campo("secuencial", 4, "N"), Campo("razon_social", 36, recortable=True),
    Campo("descripcion", 20, recortable=True), Campo("naturaleza", 2, "N"),
    Campo("version", 1), Campo("tipo_cargo", 2, "N"),
)
GLOBAL = (
    Campo("tipo", 1, "N"), Campo("operacion", 1, "N"), Campo("moneda", 3, "N"),
    Campo("importe", 18, "N"), Campo("tipo_cuenta", 2, "N"), Campo("cuenta", 20, "N"),
    Campo("abonos", 6, "N"),
)
DETALLE = (
    Campo("tipo", 1, "N"), Campo("operacion", 1, "N"), Campo("metodo", 3, "N"),
    Campo("tipo_pago", 2, "N"), Campo("moneda", 3, "N"), Campo("importe", 18, "N"),
    Campo("tipo_cuenta", 2, "N"), Campo("cuenta", 20, "N"), Campo("referencia", 16),
    Campo("beneficiario", 55, recortable=True), Campo("ref1", 35, recortable=True),
    Campo("ref2", 35), Campo("ref3", 35), Campo("ref4", 35), Campo("banco", 4, "N"),
    Campo("plazo", 2, "N"), Campo("rfc", 14), Campo("iva", 8, "N"), Campo("reservado1", 80),
    Campo("reservado2", 50),
)
TOTALES = (
    Campo("tipo", 1, "N"), Campo("moneda", 3, "N"), Campo("abonos", 6, "N"),
    Campo("importe_abonos", 18, "N"), Campo("cargos", 6, "N"), Campo("importe_cargos", 18, "N"),
)
TIPO_CUENTA = {"cuenta": "01", "tarjeta": "03", "clabe": "40"}


def beneficiario(p: Pago) -> str:
    """"NOMBRE(S),PATERNO/MATERNO" con Ñ → @. Vacío si no hay apellidos capturados."""
    if not (p.nombres and p.apellido_paterno):
        return ""
    limpio = [rf.ascii_mayusculas(x, enie="@") for x in (p.nombres, p.apellido_paterno,
                                                         p.apellido_materno)]
    return f"{limpio[0]},{limpio[1]}/{limpio[2]}"


class Banamex(Layout):
    id = "banamex"
    nombre = "Banamex"
    banco = "002"
    estado = "verificado"
    fuente = (
        "Banamex BancaNet Empresarial, 'Formato para la Importación de Archivos de Nómina "
        "Banamex - LayOut D' (bancanetempresarial.banamex.com.mx/spanishdir/bankhelp/"
        "hlp_fimp-nominadispersionesd.htm). Clave de banco interbancaria y formato del "
        "beneficiario: POR CONFIRMAR CON MANUAL DEL BANCO."
    )
    interbancario = True
    cuenta_digitos = (11,)  # sucursal (4) + cuenta (7)
    datos_requeridos = (
        DatoBanco("numero_cliente", "Número de cliente Banamex (12 dígitos)", r"^\d{1,12}$"),
        DatoBanco("secuencial", "Secuencial del archivo en el día (1-99)", r"^\d{1,2}$",
                  obligatorio=False, default="1"),
        DatoBanco("plazo", "Plazo interbancario: 00 mismo día, 24 en 24 horas", r"^(00|24)$",
                  obligatorio=False, default="00"),
    )

    def abono(self, pago: Pago) -> Abono | str:
        elegido = super().abono(pago)
        if isinstance(elegido, Abono) and elegido.interbancario and not beneficiario(pago):
            return (
                "Banamex exige el beneficiario como NOMBRE,PATERNO/MATERNO en los pagos "
                "interbancarios: captura nombre(s) y apellidos separados en la ficha."
            )
        if isinstance(elegido, Abono) and not elegido.interbancario and len(pago.empleado_no) > 16:
            return "El número de empleado no cabe en la referencia de Banamex (16)."
        return elegido

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        if not (cargo.numero.isdigit() and len(cargo.numero) == 11):
            raise FiscalAgentError(
                "La cuenta de cargo Banamex son 11 dígitos: sucursal (4) y cuenta (7).", 422
            )
        total = sum(p.centavos for p, _ in pagos)
        sec = op.datos_banco.get("secuencial", "1")
        renglones = [
            rf.escribir(CONTROL, {
                "tipo": "1", "cliente": op.datos_banco["numero_cliente"],
                "fecha": f"{op.fecha_aplicacion:%y%m%d}", "secuencial": sec,
                "razon_social": rf.ascii_mayusculas(op.razon_social),
                "descripcion": rf.ascii_mayusculas(op.concepto), "naturaleza": "15",
                "version": "D", "tipo_cargo": "01",
            }, self.nombre),
            rf.escribir(GLOBAL, {
                "tipo": "2", "operacion": "1", "moneda": "001", "importe": rf.centavos(total),
                "tipo_cuenta": "01", "cuenta": cargo.numero, "abonos": str(len(pagos)),
            }, self.nombre),
        ]
        for p, a in pagos:
            inter = a.interbancario
            renglones.append(rf.escribir(DETALLE, {
                "tipo": "3", "operacion": "0", "metodo": "002" if inter else "001",
                "tipo_pago": "01", "moneda": "001", "importe": rf.centavos(p.centavos),
                "tipo_cuenta": TIPO_CUENTA[a.tipo], "cuenta": a.numero,
                "referencia": (str(op.referencia_numerica).rjust(7, "0") if inter
                               else rf.ascii_mayusculas(p.empleado_no)),
                "beneficiario": beneficiario(p),
                "ref1": rf.ascii_mayusculas(op.concepto),
                "banco": a.banco if inter else "0",
                "plazo": op.datos_banco.get("plazo", "00") if inter else "00",
                "iva": "0",
            }, self.nombre))
        renglones.append(rf.escribir(TOTALES, {
            "tipo": "4", "moneda": "001", "abonos": str(len(pagos)),
            "importe_abonos": rf.centavos(total), "cargos": "1",
            "importe_cargos": rf.centavos(total),
        }, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido) if x[0] == "3"]
