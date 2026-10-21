# Respuestas grabadas del web service de Descarga Masiva del SAT (v1.5)

Plantillas de las respuestas SOAP que usa `tests/plan_p/test_sat_descarga.py` con un
`httpx.MockTransport`: ningún test toca la red. Los `{CAMPOS}` los llena el test.

Forma tomada de los documentos oficiales del SAT ("WS Solicitud / Verificación / Descarga de
Solicitudes Exitosas V1.5") y de las respuestas reales publicadas como fixtures por
phpcfdi/sat-ws-descarga-masiva (MIT). RFC, UUID y tokens son sintéticos.

- `autenticacion_token.xml` — `AutenticaResponse` con Timestamp y token.
- `fault_seguridad.xml` — `s:Fault` `a:InvalidSecurity` (token vencido o firma inválida).
- `solicitud.xml` — `SolicitaDescarga{Emitidos,Recibidos}Result` con `CodEstatus`.
- `verificacion.xml` — `VerificaSolicitudDescargaResult` con `EstadoSolicitud` e `IdsPaquetes`.
- `descarga.xml` — `respuesta` en el encabezado y `Paquete` (ZIP en base64) en el cuerpo.
Los `DigestValue` que phpcfdi obtuvo con la e.firma de pruebas del SAT (EKU9003173C9) para
autenticación, solicitud, verificación y descarga están en
`tests/plan_p/test_sat_soap.py::test_digest_igual_al_de_phpcfdi`.
