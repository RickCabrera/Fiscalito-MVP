"""
BBVA México — Pago de nómina (BBVA Net Cash). POR CONFIRMAR CON MANUAL DEL BANCO.

POR QUÉ NO ESTÁ VERIFICADO
--------------------------
El layout de nómina de BBVA Net Cash vive detrás del portal empresarial: la guía pública de
BBVA (bbva.mx, "Pago SPEI · Guía rápida… BBVA Net Cash", pagos-spei-v2-05-2020.pdf) describe
la operación, no el archivo. Lo que sí está publicado es de terceros:

- CONTPAQi, carta técnica "Actualización en el layout para la dispersión de nómina del banco
  BBVA Bancomer" (conocimiento.blob.core.windows.net/…/CT_Nominas_1813/…): el archivo lleva
  **tipo de cuenta del empleado** (antes "99" fijo, ahora "01" por omisión y configurable),
  **clave de banco destino** y **clave de plaza destino**.

Con eso se arma la versión más documentada de un renglón por pago, sin encabezado (108):
consecutivo 9 | RFC 16 | tipo de cuenta 2 | cuenta 20 (alineada a la izquierda) | importe 15
(13 enteros + 2 decimales, sin punto) | nombre 40 | banco destino 3 | plaza destino 3.

El tipo de cuenta de las cuentas BBVA se toma del dato "tipo_cuenta_propia" (default "01",
como CONTPAQi); tarjeta "03" y CLABE "40" son las claves de uso común en México.
"""

from __future__ import annotations

from app.dispersion import registro_fijo as rf
from app.dispersion.clabe import plaza_de_clabe
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

DETALLE = (
    Campo("consecutivo", 9, "N"), Campo("rfc", 16), Campo("tipo_cuenta", 2, "N"),
    Campo("cuenta", 20), Campo("importe", 15, "N"), Campo("nombre", 40, recortable=True),
    Campo("banco", 3, "N"), Campo("plaza", 3, "N"),
)


class BBVA(Layout):
    id = "bbva"
    nombre = "BBVA"
    banco = "012"
    estado = "por_confirmar"
    fuente = (
        f"{POR_CONFIRMAR}. Campos según la carta técnica de CONTPAQi 'Actualización en el layout "
        "para la dispersión de nómina del banco BBVA Bancomer' (tipo de cuenta, banco y plaza "
        "destino); posiciones de la versión de uso común. BBVA no publica el manual de Net Cash."
    )
    interbancario = True
    cuenta_digitos = (10,)
    datos_requeridos = (
        DatoBanco("tipo_cuenta_propia", "Tipo de cuenta para cuentas BBVA (01 o 99)",
                  r"^\d{2}$", obligatorio=False, default="01"),
    )

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        propia = op.datos_banco.get("tipo_cuenta_propia", "01")
        renglones = []
        for i, (p, a) in enumerate(pagos, start=1):
            tipo = {"cuenta": propia, "tarjeta": "03", "clabe": "40"}[a.tipo]
            renglones.append(rf.escribir(DETALLE, {
                "consecutivo": str(i), "rfc": rf.ascii_mayusculas(p.rfc), "tipo_cuenta": tipo,
                "cuenta": a.numero, "importe": rf.centavos(p.centavos),
                "nombre": rf.ascii_mayusculas(p.nombre), "banco": a.banco,
                "plaza": plaza_de_clabe(a.numero) if a.tipo == "clabe" else "0",
            }, self.nombre))
        return texto(renglones)

    def importes(self, contenido: bytes) -> list[int]:
        return [int(rf.leer(DETALLE, x)["importe"]) for x in lineas(contenido)]
