# Contrato de la API — Fiscal Agent

> **PARCIAL.** Cubre únicamente los endpoints de **asistencia** que agregó D-04.
> **S-03 lo completa** con los 11 endpoints existentes exportados del OpenAPI de FastAPI y
> reemplaza por una referencia a este archivo las secciones duplicadas de
> `apps/api/CLAUDE.md` y `apps/store/CLAUDE.md`. Ese trabajo **no** está hecho: S-03 sigue
> abierta con su criterio intacto.

Base: `/api/v1`. Errores de dominio se serializan como `{"exito": false, "error": ...}` con
422 (validación) o 500 (cálculo), vía el handler global de `main.py`.

---

## Asistencia (épica D — demo del checador)

> ⚠️ **DEMO — sin autenticación, almacenamiento en memoria del proceso, no desplegar.**
>
> - **Sin auth**: el push del Hikvision no sabe mandar un ID token de Firebase. La
>   autenticación del dispositivo está mandada a **F3**; la del resto de `/api/v1`, a S-00b.
> - **En memoria**: los eventos se pierden al reiniciar y no se replican entre workers. Los
>   reemplaza Firestore en F1-09 (`clientes/{id}/asistencia/{periodoId}`).
> - Tope duro de 5,000 eventos por cliente (ring buffer): un `POST` abierto y sin auth sería
>   si no un agotamiento de memoria de una línea de `curl`. Se pierden los más viejos; el POST
>   nunca falla en medio de la demo.

### `POST /api/v1/asistencia/eventos`

Recibe checadas. Acepta el cuerpo `AcsEvent` **tal como lo manda el Hikvision**, en
`application/json` o en `multipart/form-data` (cuando el aparato adjunta la foto del
reconocimiento; solo se lee la parte JSON y **la foto no se guarda**).

| Query param | Default | Notas |
|---|---|---|
| `cliente` | `demo` | El cuerpo del dispositivo **no puede llevar el cliente**: la URL se configura en el aparato y el JSON lo arma él. Por eso va como query con default y `POST /asistencia/eventos` pelado funciona. |
| `fuente` | `hikvision` | `hikvision` · `simulado` · `csv` |

Cuerpo (campos que se leen de `AcsEvent.InfoList[]`):

```json
{ "AcsEvent": { "InfoList": [ {
  "major": 5, "minor": 75,
  "time": "2026-09-01T08:02:11-06:00",
  "employeeNoString": "7",
  "attendanceStatus": "checkIn",
  "serialNo": 575
} ] } }
```

- Se aceptan `major == 5` (acceso) con `minor` en **75 (rostro), 1 (tarjeta) o 38 (huella)**.
  Los fallos de autenticación (21, 22, 76) y todo lo que no sea acceso **se ignoran**.
- `time` **debe traer offset**. Sin él responde 422: asumir una zona desplazaría todas las
  horas y convertiría la jornada en retardos.
- `attendanceStatus` sólo admite `checkIn` / `checkOut`. Cualquier otro valor —`undefined`,
  `breakIn`, `overTimeIn`, que es lo que manda el aparato **sin modo de asistencia
  configurado**— responde 422 y **rechaza el batch completo**, en vez de inventar una jornada.
- Dedupe por `(employeeNoString, serialNo)` cuando venga `serialNo`: el push reintenta.

Respuesta: `{exito, cliente, recibidos, duplicados, total_en_memoria}`.

### `GET /api/v1/asistencia/eventos`

Para el panel en vivo (D-07 hace polling cada 3 s).

| Query param | Default | Notas |
|---|---|---|
| `cliente` | `demo` | Un cliente sin eventos devuelve **lista vacía y 200**, no 404. |
| `desde` | — | ISO 8601. **Inclusivo.** |

Respuesta: `{exito, cliente, eventos[]}`, **ordenados cronológicamente**.

### `POST /api/v1/asistencia/cerrar-periodo`

Calcula incidencias del periodo a partir de las checadas en memoria.

```json
{ "cliente": "demo",
  "empleados": ["7", "8"],
  "periodo": {"inicio": "2026-08-31", "fin": "2026-09-06"},
  "horario": {"hora_entrada": "08:00:00", "hora_salida": "17:00:00",
              "tolerancia_minutos": 15, "dias_laborables": [0,1,2,3,4]} }
```

Reglas de hoy: día con ≥1 checada = trabajado; día laborable sin checada = falta; primera
**entrada** después de `hora_entrada + tolerancia` = retardo. El retardo se evalúa sólo sobre
entradas — medirlo sobre "la primera checada del día" haría que una salida a las 18:00 fuera
retardo. La hora se interpreta en **la zona del propio evento**, no en UTC.

Respuesta: `{exito, cliente, periodo, incidencias[], empleados_desconocidos[]}`.

- `empleados_desconocidos` son los `employeeNo` que checaron y no están en `empleados`. **La
  pantalla debe mostrarlos**: si se ignoraran, un alta con el número equivocado en el
  dispositivo se vería como "faltaron todos" y nadie sabría por qué.
- **`dias_cotizados` es informativo.** La base de las cuotas del IMSS la determina
  `nomina_engine.cuotas.DiasDelPeriodo` **según el ramo** —el ausentismo no reduce
  Enfermedades y Maternidad (Art. 31 LSS, §D3)— y se construye con `dias_periodo` y
  `dias_ausentismo`, que por eso se exponen. Tomar `dias_cotizados` como base contradice a
  `cuotas.py`.

**Limitaciones conocidas** (F1-09): toda ausencia cuenta como falta —no se distinguen
vacaciones, permisos ni incapacidades, que legalmente no son ausentismo injustificado— y los
turnos nocturnos caen en dos días calendario.
