"""
Descarga masiva del SAT (plan P, P1-01 y P1-02).

- `servicio`: máquina de estados de una solicitud (solicitar → verificar → descargar →
  importar a la bóveda), idempotente y tolerante a que el SAT tarde días.
- `metadata`: lectura de los paquetes de metadata y su guardado.
- `sincronizacion`: configuración por cliente, descarga diaria, histórica y bitácora.
- `trabajos`: manejadores de la cola y tareas recurrentes.

El protocolo (SOAP, firma) vive en `app/integraciones/sat_soap.py` y el transporte en
`app/integraciones/sat_descarga.py`.
"""
