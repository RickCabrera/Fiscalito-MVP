"""
El contrato de un layout de dispersión (P4-12) y el punto de extensión.

CÓMO SE AGREGA UN BANCO
-----------------------
Un módulo en `app/dispersion/bancos/` con una subclase de `Layout` y un renglón en
`catalogo.LAYOUTS`. Todo layout DECLARA SU FUENTE (`fuente`) y su `estado`:

- `verificado` — transcrito de la documentación pública del banco, citada.
- `por_confirmar` — no hay manual público que lo respalde entero: **POR CONFIRMAR CON MANUAL
  DEL BANCO**. La pantalla lo pinta, el archivo lo lleva en el nombre y el reporte lo dice.

No hay un tercer estado: un archivo que se sube al banco o está respaldado por su manual o el
operador tiene que saber que no lo está.

LO QUE SÍ ESTÁ GARANTIZADO EN TODOS
-----------------------------------
Los importes. Salen de los netos guardados de la nómina cerrada, en centavos enteros, y
`servicio.generar` relee el archivo generado con `importes()` y exige que la suma cuadre al
centavo contra Σ netos − Σ excluidos. Si el layout está mal, el banco rechaza el archivo; si
los importes estuvieran mal, pagaría de más o de menos — y de eso sí hay garantía.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

from app.dispersion.clabe import nombre_banco

POR_CONFIRMAR = "POR CONFIRMAR CON MANUAL DEL BANCO"
CRLF = "\r\n"


@dataclass(frozen=True)
class Pago:
    """Un neto por pagar, con lo que la ficha del empleado sabe de su cuenta."""

    empleado_no: str
    nombre: str
    centavos: int
    banco: str = ""
    clabe: str = ""
    numero_cuenta: str = ""
    apellido_paterno: str = ""
    apellido_materno: str = ""
    nombres: str = ""
    rfc: str = ""


@dataclass(frozen=True)
class Abono:
    """La cuenta que el layout eligió para abonar el pago."""

    tipo: str  # cuenta | tarjeta | clabe
    numero: str
    banco: str
    interbancario: bool


@dataclass(frozen=True)
class Cargo:
    """La cuenta del patrón de donde sale el dinero (`cuentas_bancarias`, P2-06)."""

    banco: str
    numero: str = ""
    clabe: str = ""


@dataclass(frozen=True)
class DatoBanco:
    """Un dato del contrato del patrón con el banco (número de cliente, emisora…)."""

    clave: str
    etiqueta: str
    patron: str
    obligatorio: bool = True
    default: str = ""


@dataclass(frozen=True)
class Opciones:
    fecha_aplicacion: date
    concepto: str
    razon_social: str = ""
    referencia_numerica: int = 1
    datos_banco: dict[str, str] = field(default_factory=dict)


class Layout:
    """Base de los layouts bancarios. Las subclases llenan los ClassVar y tres métodos."""

    id: ClassVar[str]
    nombre: ClassVar[str]
    banco: ClassVar[str | None]  # clave c_Banco; None = genérico
    estado: ClassVar[str]  # verificado | por_confirmar
    fuente: ClassVar[str]
    interbancario: ClassVar[bool] = False
    cuenta_digitos: ClassVar[tuple[int, ...]] = (10,)
    acepta_tarjeta: ClassVar[bool] = True
    acepta_clabe_mismo_banco: ClassVar[bool] = True
    datos_requeridos: ClassVar[tuple[DatoBanco, ...]] = ()
    extension: ClassVar[str] = "txt"
    mime: ClassVar[str] = "text/plain"

    def abono(self, pago: Pago) -> Abono | str:
        """La cuenta a la que se abona, o el motivo por el que este layout no puede pagarle."""
        banco = self.banco or ""
        nombre = self.nombre
        if pago.banco == banco:
            n = pago.numero_cuenta
            if n:
                if len(n) in self.cuenta_digitos:
                    return Abono("cuenta", n, banco, False)
                if len(n) == 16 and self.acepta_tarjeta:
                    return Abono("tarjeta", n, banco, False)
                if not (pago.clabe and self.acepta_clabe_mismo_banco):
                    largos = " o ".join(str(x) for x in self.cuenta_digitos)
                    return (
                        f"La cuenta capturada tiene {len(n)} dígitos; el layout de {nombre} pide "
                        f"{largos} (cuenta){' o 16 (tarjeta)' if self.acepta_tarjeta else ''}."
                    )
            if pago.clabe and self.acepta_clabe_mismo_banco:
                return Abono("clabe", pago.clabe, banco, False)
            return f"El layout de {nombre} pide la cuenta o tarjeta {nombre} del trabajador."
        destino = nombre_banco(pago.banco) or pago.banco or "otro banco"
        if not self.interbancario:
            return (
                f"La cuenta es de {destino} y el layout de {nombre} sólo abona a cuentas "
                f"{nombre}: dispérsalo con un layout que admita SPEI o con el genérico."
            )
        if pago.clabe:
            return Abono("clabe", pago.clabe, pago.banco, True)
        return f"La cuenta es de {destino}: para pagar a otro banco hace falta la CLABE."

    def generar(self, pagos: list[tuple[Pago, Abono]], cargo: Cargo, op: Opciones) -> bytes:
        raise NotImplementedError

    def importes(self, contenido: bytes) -> list[int]:
        """Los centavos de cada renglón de detalle, releídos del archivo ya generado."""
        raise NotImplementedError

    def nombre_archivo(self, op: Opciones) -> str:
        marca = "_POR_CONFIRMAR" if self.estado == "por_confirmar" else ""
        return f"Dispersion_{self.id}{marca}_{op.fecha_aplicacion:%Y%m%d}.{self.extension}"


def lineas(contenido: bytes) -> list[str]:
    return [x for x in contenido.decode("ascii").split(CRLF) if x]


def texto(lineas_: list[str]) -> bytes:
    """ASCII con CRLF al final de cada renglón (lo que esperan los portales bancarios)."""
    return (CRLF.join(lineas_) + CRLF).encode("ascii")
