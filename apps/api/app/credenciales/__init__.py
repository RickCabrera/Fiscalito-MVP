"""
Bóveda de credenciales del cliente (plan P, P0-05): e.firma (FIEL) y CSD del SAT.

- `cifrado`: Fernet/MultiFernet con la llave maestra de entorno (con rotación).
- `certificados`: lectura y validación de .cer/.key del SAT (sin base de datos).
- `servicio`: guardar, listar, borrar y `obtener_firmante(db, cliente, tipo)`.

La descarga masiva del SAT y el PAC sólo necesitan `obtener_firmante`: les da un objeto que
firma (SHA256 con RSA, PKCS#1 v1.5) y entrega el certificado en base64. La llave privada
descifrada nunca sale de ese objeto.
"""

from app.credenciales.servicio import Firmante, obtener_firmante

__all__ = ["Firmante", "obtener_firmante"]
