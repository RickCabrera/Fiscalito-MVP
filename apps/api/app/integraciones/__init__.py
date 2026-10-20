"""
Adaptadores de servicios externos (plan P, P0-06).

Cada servicio externo vive en `app/integraciones/<servicio>.py` con:
- un `Protocol` que define lo que la app necesita del servicio,
- una implementación **falsa** (determinística, sin red) para desarrollo y tests,
- una o más implementaciones **reales** que se encienden con variables de entorno.

Se elige con `FISCALITO_<SERVICIO>` (p. ej. `FISCALITO_PAC=finkok`). Sin la variable se usa
`falso` en desarrollo; en producción falta configurarla y `verificar_configuracion()` lo
reporta en `/health/integraciones`. Ver `docs/servicios-externos.md`.
"""
