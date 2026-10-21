"""
Acceso a la API (plan P, P0-02): quién puede llamar, cuántas veces y cuánto LLM gasta.

- `dependencias.usuario_autenticado`: la dependencia que se monta en TODO router de
  `/api/v1` (ver `app/main.py`). Exige el ID token de Firebase y aplica el límite por usuario.
- `limitador`: ventana deslizante por llave, en memoria del proceso (interfaz para Redis/DB).
- `llm.cobrar_llm`: límite por minuto de lo que gasta LLM y tope diario por despacho (en DB).
- `dispositivos`: token secreto por checador, para el push del Hikvision (no trae Firebase).
"""
