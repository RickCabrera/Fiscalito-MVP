"""
Verificaciones contra el SAT (plan P, P1-03/04/05).

- `estatus`: estatus de los CFDI de la bóveda (vigente / cancelado) con el servicio público
  del SAT, en lotes con límite de concurrencia y ritmo.
- `listas`: listados del art. 69-B (EFOS) y 69 del CFF: carga del CSV y cruce con las
  contrapartes de cada cliente (alertas).
- `cumplimiento`: opinión de cumplimiento 32-D y constancia de situación fiscal (PDF en el
  almacenamiento, historial, semáforo).
- `trabajos`: manejadores de la cola y tareas recurrentes.
- `pdf`: lectura del texto de los PDF del SAT.
"""
