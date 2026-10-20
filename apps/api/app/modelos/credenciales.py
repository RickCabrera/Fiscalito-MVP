"""
Bóveda de credenciales del cliente: e.firma (FIEL) y CSD (P0-05).

QUÉ SE GUARDA Y CÓMO
--------------------
- `cer_der`: el certificado tal cual (DER). Es público: no se cifra.
- `key_cifrada`: el archivo `.key` que subió el despacho (PKCS#8 DER, ya cifrado por el SAT
  con la contraseña del contribuyente) **vuelto a cifrar** con la llave maestra (Fernet).
- `password_cifrada`: la contraseña de la llave, cifrada con la llave maestra.

Sin la llave maestra (`FISCALITO_LLAVE_MAESTRA`) ninguna de las dos se puede leer, y aun con
la base de datos completa en la mano hace falta romper dos capas. La llave privada descifrada
sólo vive en memoria dentro de un `Firmante` (ver `app/credenciales/servicio.py`).

Al subir una credencial nueva del mismo tipo, la anterior queda `activo=False` (historial);
sólo la activa se usa para firmar.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo


class CredencialCliente(ConMarcasDeTiempo, Base):
    """Un certificado del SAT (e.firma o CSD) de un cliente, con su llave cifrada."""

    __tablename__ = "credenciales_cliente"
    __table_args__ = (Index("ix_cred_cliente_tipo", "cliente_id", "tipo", "activo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    # efirma | csd
    tipo: Mapped[str] = mapped_column(String(10))
    rfc: Mapped[str] = mapped_column(String(13))
    numero_certificado: Mapped[str] = mapped_column(String(40))
    valido_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valido_hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cer_der: Mapped[bytes] = mapped_column(LargeBinary)
    key_cifrada: Mapped[bytes] = mapped_column(LargeBinary)
    password_cifrada: Mapped[bytes] = mapped_column(LargeBinary)
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    activo: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:  # nunca imprimir bytes cifrados en logs
        return (
            f"CredencialCliente(id={self.id}, cliente_id={self.cliente_id}, tipo={self.tipo!r}, "
            f"rfc={self.rfc!r}, numero_certificado={self.numero_certificado!r})"
        )
