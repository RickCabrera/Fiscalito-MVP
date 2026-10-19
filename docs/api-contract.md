# Contrato de la API — Fiscal Agent

> **Contrato máquina-legible (P0-08):** [`docs/openapi.json`](openapi.json) — el OpenAPI
> completo, exportado de `app.main:app` — y los tipos TypeScript que el front importa,
> `apps/store/src/services/tiposApi.generados.ts`. Los dos se regeneran con
> `cd apps/api && PYTHONPATH=. python scripts/exportar_openapi.py`, y
> `apps/api/tests/test_contrato_openapi.py` **falla** si el código y el contrato divergen.
> Este archivo es la explicación para humanos: qué garantiza cada endpoint y por qué.

Base: `/api/v1`. Errores de dominio se serializan como `{"exito": false, "error": ...}` con
401 (sin sesión), 403 (rol o recurso ajeno con token de dispositivo), 404 (no existe **en tu
despacho**), 422 (validación), 429 (límite) o 500 (cálculo), vía el handler global de
`main.py`.

## Autenticación, límites y tope de LLM (P0-02)

**Todo `/api/v1` exige sesión** (salvo lo declarado abajo). `/health` y
`/health/integraciones` quedan abiertos.

| Qué | Cómo |
|---|---|
| Sesión | `Authorization: Bearer <ID token de Firebase>`. Sin encabezado o mal formado: **401**. Token inválido o expirado: **401** sin detalle del SDK. Sin credenciales de Firebase en el servidor: **503**. |
| Despacho | Sale del token, nunca del request. El primer request de un uid le crea su despacho (`id = uid`). Un cliente de otro despacho es **404**, nunca 403: un 403 confirmaría que existe. |
| Rutas públicas | `app/acceso/dependencias.RUTAS_PUBLICAS`. Hoy sólo `POST /asistencia/eventos` (token de dispositivo). Un webhook nuevo se declara ahí, se monta sin `PROTEGIDO` y verifica la firma del proveedor dentro de la ruta. `tests/plan_p/test_acceso.py` recorre **todas** las rutas y exige 401 sin token al resto. |
| Límite por usuario | `FISCALITO_RATE_LIMIT_POR_MINUTO` (default **120**), ventana deslizante de 60 s por uid (por token en el caso del checador). Al excederlo: **429** con `Retry-After: <segundos>`. Una petición rechazada no gasta cupo. En memoria del proceso: con varias réplicas el límite efectivo se multiplica; la interfaz `Limitador` está lista para Redis/DB (`FISCALITO_LIMITADOR`). |
| Límite de LLM | `FISCALITO_RATE_LIMIT_LLM_POR_MINUTO` (default **20**) por uid. Cuenta cada llamada al proveedor: cada `incluir_explicacion: true` (pre-declaración, anual, deducciones, comparador, DIOT, retenciones, multi-periodo, estado de cuenta, nómina) y cada vuelta del loop de `/agente/predeclaracion`. El cálculo sin explicación no cuenta. **429** + `Retry-After`. |
| Tope diario de LLM | `FISCALITO_TOPE_LLM_DIARIO_LLAMADAS` (default **500**) llamadas por **despacho** por día de la Ciudad de México, contadas en la tabla `consumo_llm`. Al llegar: **429** con `Retry-After` hasta la medianoche. Se mide en llamadas, no en pesos: los servicios LLM actuales no devuelven tokens; cada llamada tiene `max_tokens` fijo. |

CORS expone `Retry-After` y acepta el encabezado `X-Token-Dispositivo`.

### Token de dispositivo (checador)

El Hikvision no puede mandar un ID token. Cada checador lleva un secreto propio
(`fdt_…`, 256 bits) que el backend guarda **sólo como SHA-256**. Viaja en
`X-Token-Dispositivo: <token>` o en `?token=<token>` (el aparato sólo deja configurar una URL,
así que la forma real es `…/api/v1/asistencia/eventos?token=fdt_…`). El token fija **despacho y
cliente**: un `?cliente=` distinto es **403**; un token inventado o revocado es **401**.

#### `POST /api/v1/asistencia/tokens`
Sesión + rol `dueno`/`contador`. Cuerpo `{cliente, etiqueta?, dispositivo?}`. Responde **201**
`{exito, token, registro}`: es la **única vez** que el token se ve en claro. Un cliente de otro
despacho es 404; los tres clientes del catálogo de demostración (`demo`, `cafeteria`,
`taller`) se aceptan sin renglón en `clientes`.

#### `GET /api/v1/asistencia/tokens?cliente=`
Tokens activos del despacho: `{id, cliente, dispositivo_id, etiqueta, prefijo, creado_en,
ultimo_uso}`. Nunca el secreto ni el hash.

#### `DELETE /api/v1/asistencia/tokens/{token_id}`
Revoca en el acto. Otro despacho: 404.

---

## Asistencia (épica D — demo del checador)

> ⚠️ **DEMO — almacenamiento en memoria del proceso, no desplegar.**
>
> - **Auth (P0-02)**: `POST /eventos` acepta el **token del dispositivo** o la sesión de
>   Firebase (el simulador y las pantallas); `GET /eventos` y `cerrar-periodo` exigen sesión.
>   Ver "Token de dispositivo" arriba.
> - **Aislado por despacho**: el almacén se indexa por `despacho::cliente`. Los clientes de la
>   demo son un catálogo compartido; sin esto, el `taller` de un despacho vería las checadas del
>   `taller` de otro.
> - **En memoria**: los eventos se pierden al reiniciar y no se replican entre workers.
> - Tope duro de 5,000 eventos por cliente (ring buffer). Se pierden los más viejos; el POST
>   nunca falla en medio de la demo.

### `POST /api/v1/asistencia/eventos`

Recibe checadas. Acepta el cuerpo `AcsEvent` **tal como lo manda el Hikvision**, en
`application/json` o en `multipart/form-data` (cuando el aparato adjunta la foto del
reconocimiento; solo se lee la parte JSON y **la foto no se guarda**). Se revisan todas las
partes, **con y sin `filename`**: varios firmwares mandan el evento con filename, y ahí
Starlette lo entrega como archivo en vez de como texto.

| Query param | Default | Notas |
|---|---|---|
| `cliente` | `demo` (o el del token) | El cuerpo del dispositivo **no puede llevar el cliente**: la URL se configura en el aparato y el JSON lo arma él. Con token de dispositivo, el cliente es el del token y otro valor es 403. |
| `token` | — | Token del dispositivo (alternativa a `X-Token-Dispositivo`). |
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
| `desde` | — | ISO 8601 **con offset obligatorio**. **Inclusivo.** Sin zona responde **422**, no 500: compararlo contra los timestamps aware de los eventos sería un `TypeError`, y asumir una zona correría todas las horas. Ej.: `2026-09-01T00:00:00-06:00`. |

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

---

## Despacho (épica E — cartera de clientes)

> ⚠️ **DEMO — sin autenticación, datos estáticos, no desplegar.**
>
> Mismo estatus que la épica D. Es un **catálogo estático de tres clientes**, no una base de
> datos: el alta de clientes y la persistencia son F1-09. La auth del resto de `/api/v1` es
> S-00b.

Los tres clientes: `demo` (el caso real anonimizado de S-04, con sus 9 empleados, reusando
`PLANTILLA_DEMO`), `cafeteria` (4 empleados) y `taller` (12 empleados), estos dos **sintéticos
completos** — personas, salarios y fechas inventados.

> **`empleados` lleva la llave del CHECADOR, no la del cálculo.** Son los
> `employeeNo` del aparato: el motor casa `evento.empleado_no` —el
> `employeeNoString` que manda el Hikvision— contra esta lista. Hasta G-02 las dos
> llaves coincidían siempre y la distinción no se notaba; desde que un empleado
> puede tener un número de aparato distinto del interno, mandar la equivocada hace
> que **no se encuentre ni una de sus checadas**: falta todo el periodo, menos días
> pagados, menor base de cuotas y menor ISR, sin ningún error. Las incidencias
> vuelven con la misma llave que se mandó, así que el llamador tiene que
> traducirlas de regreso antes de `calcular-periodo`, que indexa por la interna.

### `GET /api/v1/despacho/clientes`

Cartera del despacho, para la lista y el selector de cliente activo.

```json
{
  "exito": true,
  "clientes": [
    {
      "id": "demo",
      "nombre": "Servicios Administrativos Integrales",
      "giro": "Servicios administrativos",
      "origen": "fixtures-s04",
      "num_empleados": 9,
      "prima_riesgo": "0.0054355",
      "clase_riesgo": null,
      "clave_periodicidad": "04",
      "zona": "general"
    }
  ]
}
```

- `origen` — `fixtures-s04` (caso real anonimizado) o `sintetico`. La pantalla **distingue los
  dos**: presentar datos inventados con el mismo peso que los reales sería engañoso.
- `prima_riesgo` — del caso real es la **autodeterminada** por ese patrón (Art. 74 LSS); de los
  sintéticos es la **prima media de su clase** (Art. 73 LSS, vía `prima_media_clase()`). Nunca
  es tasa de ley.
- `clase_riesgo` — `null` para el caso real, cuya prima es **autodeterminada** (Art. 74 LSS)
  y no se dedujo de ninguna clase; la ficha lo imprime así, no como "no aplica" (todo patrón
  tiene clase). Para los sintéticos es un **SUPUESTO**: la
  asignación giro → clase sale del catálogo del RACERF, que no está en el repo. Ver
  `docs/decisiones-nomina.md` **D22**.
- `num_empleados` es derivado de la plantilla, nunca un literal.

### `GET /api/v1/despacho/clientes/{cliente_id}`

La ficha: el resumen de arriba más `empleados`, `periodo_sugerido` y `fecha_referencia`.

```json
{
  "exito": true,
  "id": "cafeteria",
  "empleados": [
    {
      "empleado_no": "C-01",
      "nombre": "MARISOL ABREGO QUINTERO",
      "puesto": "Encargada de tienda",
      "salario_diario": "520.00",
      "salario_diario_integrado": "548.50",
      "zona": "general",
      "fecha_alta": "2021-02-01",
      "antiguedad_anios": 5,
      "factor": "1.0548",
      "factor_implicito": false
    }
  ],
  "periodo_sugerido": { "inicio": "2026-08-16", "fin": "2026-08-31", "fecha_pago": "2026-08-31" },
  "fecha_referencia": "2026-09-01"
}
```

- **Los cinco primeros campos del empleado son un superconjunto compatible de
  `EmpleadoNominaSchema`**: `empleado_no`, `nombre`, `salario_diario`,
  `salario_diario_integrado` y `zona` se llaman y se tipan igual, para que la pantalla los mande
  tal cual a `POST /nomina/calcular-periodo` sin remapear. `zona` va **por empleado** porque el
  motor la lee por empleado para el piso del SBC.
- `fecha_alta` y `antiguedad_anios` son `null` para el caso real: el CFDI timbrado no trae la
  fecha de alta y **no se inventa**. §D9 documenta que ahí el SBC no se deriva de la antigüedad.
- `factor_implicito: true` ⇒ el factor es un **cociente observado** (SBC ÷ salario diario), que
  puede incluir prestaciones superiores que el CFDI no desglosa: **no es** el factor de ley del
  Art. 27 LSS y no es comparable con el mínimo de una antigüedad.
- `fecha_referencia` — la fecha FIJA contra la que se midieron antigüedad, factor y clamp de los
  clientes sintéticos. **No es `hoy`**: si lo fuera, el SBC subiría solo al cruzar un
  aniversario (Art. 76 LFT) y las cuotas del cliente de demostración cambiarían sin que nadie
  tocara código.
- `periodo_sugerido` sale de la **misma** `quincena()` que usan el simulador y
  `GET /nomina/demo/plantilla`. Existe para que la pantalla no derive el periodo de las fechas
  de las checadas: eso da 15 días donde la quincena tiene 16 y mueve cuotas e ISR.

> **Desde E-03 la pantalla de nómina toma de aquí la plantilla y la manda en el body de
> `POST /nomina/calcular-periodo`** (obligatorio para los clientes sintéticos: omitirla sólo es
> válido para `demo`). Consecuencia: `origen_plantilla` de la respuesta vale `"request"` para
> los tres clientes, y **ya no distingue nada**. Lo que dependía de ese campo —la banda
> "DATOS DE DEMOSTRACIÓN" del PDF— pasó a colgar del cliente.

**404 — cliente desconocido.** Usa el sobre de dominio, **no** el `{"detail": ...}` de
`HTTPException`, para que el front tenga un solo camino de lectura de errores:

```json
{ "exito": false, "error": "El cliente 'x' no está en la cartera de la demo. Clientes disponibles: demo, cafeteria, taller." }
```

> Nota de inconsistencia conocida: `GET /nomina/demo/plantilla` responde **422** (no 404) para
> un cliente que no sea `demo`, porque ahí es una validación de dominio. No se unificó: tocar
> `nomina.py` queda fuera del alcance de E-02.

### `GET /api/v1/despacho/clientes/{cliente_id}/empleados` (G-01)

Los empleados del cliente en el **modelo canónico de la cartera**, que es el mismo que el
despacho guarda en Firestore.

**Es una SEMILLA, no un CRUD.** El backend está declarado *stateless* (`apps/api/CLAUDE.md`)
y no persiste altas ni bajas: el dueño del dato es `users/{uid}/clientes/{id}/empleados/{id}`
(PLAN_NOMINA §3.3). Esta ruta existe para que una cuenta nueva arranque con los tres clientes
de demostración sin que el front invente sus datos.

**Respuesta 200**

```json
{
  "cliente_id": "demo",
  "origen": "fixtures-s04",
  "total": 9,
  "sin_vincular": 0,
  "empleados": [
    {
      "empleado_no": "E-01",
      "nombre": "ANA BEATRIZ XALA MORA",
      "puesto": "",
      "salario_diario": "316.00",
      "salario_diario_integrado": "331.58",
      "zona": "general",
      "fecha_alta": null,
      "tipo_contrato": "indeterminado",
      "prestaciones": {"dias_aguinaldo": 15, "dias_vacaciones": 0, "prima_vacacional": "0.25"},
      "nss": "",
      "employee_no": "E-01",
      "enrolamiento": "enrolado"
    }
  ]
}
```

**Las dos llaves son distintas y eso es lo importante:**

| Campo | Para qué | ¿Puede ser nulo? |
|---|---|---|
| `empleado_no` | Llave del **cálculo**. La que usan `EmpleadoNominaSchema` y las incidencias. | **Nunca.** |
| `employee_no` | Llave del **checador** (`employeeNoString` del Hikvision). | **Sí.** `null` = no vinculado. |

`docs/D-DEMO-CHECADOR.md` dice que el `employeeNo` del aparato *es* el id del empleado. Aquí se
separan a propósito: fundirlas obligaría a que la llave del cálculo fuera nullable, y ahí se
pierde gente — o el request revienta con 422 y la nómina entera falla, o dos empleados sin
vincular entran ambos con `""` y colisionan en el dedupe del almacén de checadas.

`nss` viene **vacío en toda la semilla** y nunca inventado: un NSS de 11 dígitos bien formado es
el NSS de alguien. Mismo criterio que `fecha_alta`, que es `null` cuando no se conoce.

`sin_vincular` lo cuenta el backend, no la UI: un aviso que depende de que alguien se acuerde de
filtrar es un aviso que un día no sale.

**404** — cliente desconocido, con el sobre `{"exito": false, "error": "..."}`.

### `GET /api/v1/despacho/primas-de-riesgo` (G-03)

Las primas **medias** por clase de riesgo (Art. 73 LSS), con sus límites (Art. 72) y su fecha de
vigencia.

**Por qué existe.** El formulario de alta de cliente necesita proponer una prima al elegir clase.
Copiar esa tabla a TypeScript la dejaba **sin año, sin fuente y sin test**: en el motor vive en
`nomina_engine/tablas_imss.py` indexada por año y se lee con `prima_media_clase(clase, fecha)`,
o sea con función de vigencia. La copia del front habría propuesto las primas del año anterior en
silencio en cuanto cambiara el año.

**Query**

| Parámetro | Tipo | Default | Para qué |
|---|---|---|---|
| `fecha` | `date` | hoy | Vigencia de la tabla. Es por año. |

**Respuesta 200**

```json
{
  "fecha": "2026-09-01",
  "minima": "0.005",
  "maxima": "0.15",
  "medias_por_clase": {
    "1": "0.0054355",
    "2": "0.0113065",
    "3": "0.0259840",
    "4": "0.0465325",
    "5": "0.0758875"
  },
  "fundamento": "Arts. 72 y 73 LSS. La prima real se autodetermina en febrero (Art. 74)."
}
```

`minima` y `maxima` **no son informativos**: el formulario acota contra ellos. Teclear `5.4355`
en vez de `0.0054355` multiplica Riesgos de Trabajo por mil, y ese es el error que el rango
existe para atajar.

**Las medias son un punto de partida, no la prima del cliente.** Aplican a *empresa nueva*; la
prima real **la autodetermina el patrón cada febrero** con su siniestralidad del ejercicio
anterior (Art. 74 LSS), y por eso es dato de entrada y no se deduce del giro (§D22).

**422** — año fuera del rango que cubre la tabla, con el sobre `{"exito": false, "error": "..."}`.

### `GET /api/v1/despacho/calendario` (E-07)

Obligaciones **patronales** de todos los clientes de la cartera, ordenadas por fecha límite y
etiquetadas con su cliente. Es lo que ve un despacho en "Calendario"; el calendario del
CONTRIBUYENTE (`POST /api/v1/calendario`) es otro endpoint y otra cosa.

**Traductor, no motor:** ninguna fecha se calcula aquí. Todas salen de
`app/nomina_engine/calendario_laboral.py` y `plazos_patronales.py`, que es donde viven los
fundamentos y los tests que los contrastan contra la tabla publicada de
`knowledge_base/nomina/25_calendario_laboral_2026.md` §3.

| Parámetro | Tipo | Default | Significado |
|---|---|---|---|
| `anio_de_las_cuotas` | int (2000-2100) | año en curso | Año **del periodo que se reporta**, no del vencimiento |
| `empresa_unica` | bool | `false` | `true` = **un solo patrón**, sin fan-out sobre la cartera (O-01) |

#### `empresa_unica` — el pivote de O-01

Con `true`, el endpoint devuelve **un** juego de obligaciones en vez de repetirlo por cada
cliente del catálogo. No es un segundo calendario: es la **misma** llamada a
`calendario_patronal()`, sin el fan-out. Crear un generador aparte es lo que
`knowledge_base/nomina/25_calendario_laboral_2026.md` §4 llama "un bug esperando", y F1-06 lo
dejó advertido.

Los dos campos de cliente **siguen presentes y obligatorios en el schema**: cambia su valor,
no su forma, así que ningún consumidor existente se rompe.

- `cliente_id` vale `"empresa"` — el id real del cliente implícito en
  `users/{uid}/clientes/empresa`. Sirve de llave y no afirma ningún nombre.
- `cliente_nombre` viene **vacío**. El backend no sabe cómo se llama la empresa —no viaja en
  el query string, y no tiene por qué— así que no lo inventa. El front descarta el vacío al
  agrupar y no pinta la columna de cliente.

`advertencias` también cambia: la que decía *"son las mismas para toda la cartera"* no
significa nada con un solo patrón. Lo que **no** cubre se sigue diciendo igual (el ISN sigue
fuera, §D24).

**`anio_de_las_cuotas` no es "el año del calendario".** Las cuotas de diciembre de 2026 vencen
en enero de 2027 y **sí** vienen; las de diciembre de 2025, que vencen en enero de 2026, **no**.
Por eso la respuesta trae `cubre_desde` y `cubre_hasta`: una pantalla que muestre "2026" sin
decir el rango enseñaría un enero vacío sin poder explicarlo. Los dos son `null` **sólo** si no
hay obligaciones — hoy inalcanzable con la cartera estática, pero la pantalla ya pinta ese
estado y las dos mitades tienen que coincidir.

```json
{
  "exito": true,
  "anio_de_las_cuotas": 2026,
  "cubre_desde": "2026-02-17",
  "cubre_hasta": "2027-01-18",
  "total_obligaciones": 120,
  "obligaciones": [
    {
      "cliente_id": "demo",
      "cliente_nombre": "Servicios Administrativos Integrales",
      "clave": "imss_mensual",
      "nombre": "Cuotas IMSS de marzo 2026",
      "descripcion": "Entero mensual: Riesgos de Trabajo, Enfermedades y Maternidad, Invalidez y Vida, Guarderías.",
      "fecha_limite": "2026-04-20",
      "periodicidad": "mensual",
      "periodo_cubierto": "marzo 2026",
      "fundamento": "Art. 39 LSS",
      "regimen_de_plazo": "imss",
      "condicional": false,
      "nota": ""
    }
  ],
  "advertencias": ["No cubre el ISN..."]
}
```

#### `regimen_de_plazo` — cinco valores, y no se pintan igual

Es **dato**, no adorno: dice qué regla produjo `fecha_limite`. El doc 25 §4 advierte que juntar
obligaciones del IMSS y del SAT en una vista **sin distinguir su regla** "es un bug esperando".

| Valor | Regla | Fundamento |
|---|---|---|
| `imss` | vence en inhábil **o viernes** → siguiente hábil | Art. 3 RACERF |
| `imss_sin_prorroga` | fecha fija, **no** se corre (decisión provisional §D23) | Art. 74 LSS; Art. 32 RACERF |
| `imss_aviso` | no se prorroga nunca | Art. 3 RACERF, que excluye los avisos afiliatorios |
| `sat` | vence en inhábil → siguiente hábil, **sin** la regla del viernes | CFF Art. 12 |
| `lft` | fecha fija de ley | LFT Arts. 87 y 122 |

Se ve en la respuesta: las cuotas del IMSS de marzo de 2026 vencen el **20-abr** y el entero del
ISR retenido de marzo el **17-abr**. `imss` e `imss_sin_prorroga` **no** son intercambiables:
etiquetar la prima de RT como `imss` prometería una prórroga que no ocurre.

#### `condicional` no significa opcional

Significa *verifícalo, porque aquí no consta*. Hoy salen condicionales el **aviso bimestral de
salario variable** (el modelo de cliente no registra el tipo de salario) y las **dos fechas de
PTU** (no registra la personalidad jurídica). Toda condicional trae `nota`. Ver §D24.

#### Lo que NO cubre

`advertencias` lo dice en el cuerpo, para que la pantalla lo imprima sin volver a redactarlo:
el **ISN** (estatal, sin fuente en la base de conocimiento ni entidad en el modelo), y el aviso
de que **hoy ninguna fecha depende del cliente** — son las mismas para toda la cartera hasta que
F1-09 registre RFC, entidad y personalidad.

**422 — año fuera de rango**, con el sobre de dominio del proyecto:

```json
{ "exito": false, "error": "Año fuera de rango: 1999. Debe estar entre 2000 y 2100." }
```

---

## Cartera del despacho — el backend como único dueño del dato (R-07 → P0-01)

**Desde P0-01 la cartera vive en SQL** (`app/modelos/nucleo.py`: `clientes`, `empleados`,
`dispositivos`, con el documento en `datos` JSON) y el front la lee y escribe **sólo por
aquí**: ya no hay Firestore para la cartera ni interruptor `VITE_CARTERA_BACKEND`. Lo que
había en Firestore se trae una vez con `apps/api/scripts/migrar_firestore.py` (ver abajo).

`Authorization: Bearer <ID token de Firebase>`. **No hay parámetro de uid ni de despacho en
ninguna ruta**: el despacho sale del token verificado (`app/tenancy.contexto_actual`; la
primera vez que entra un uid se le crea su despacho con id = uid). Toda ruta obtiene el
cliente con `cliente_o_404`: **un cliente de otro despacho es 404, nunca 403** (un 403
confirmaría que existe). Un usuario con rol `auxiliar` sólo ve sus clientes asignados.

Guardar es **merge**: un `PUT` conserva los campos guardados que el esquema actual no
conoce (p. ej. traídos por la migración) y sobrescribe los que sí manda.

| Código | Cuándo |
|---|---|
| 401 | falta `Authorization`, está mal formado, o el token no es válido |
| 403 | un `auxiliar` intenta dar de alta un cliente |
| 404 | el cliente (o el dispositivo) no está en **tu** despacho |
| 409 | tope de altas: 500 clientes por despacho; 2,000 empleados o 100 dispositivos por cliente (editar nunca rebota) |
| 422 | el cuerpo no pasa la validación (prima de RT fuera del Art. 72, NSS mal formado, id que no coincide con la URL, IP inválida, serial repetido) |
| 503 | **el backend no tiene credenciales de Firebase** para verificar el token. El mensaje dice qué falta |

### `GET /api/v1/cartera/clientes`
Los clientes de quien hace el request. `{exito, total, clientes[]}`.
Los documentos van tal como están guardados: no se tipan estrictamente al leer,
porque una cartera escrita por una versión anterior puede traer campos que el
modelo actual no conoce, y rechazarla dejaría al contador sin sus clientes por un
campo de más.

#### Dos campos nuevos del cliente (O-01)

`rfc` (≤13) y `registro_patronal` (≤11) se agregaron a `ClienteCarteraSchema`. Los dos son
**opcionales y vacíos por default**: los tres clientes de demostración no los traen y una
cartera escrita antes de O-01 tampoco, así que exigirlos dejaría al contador sin sus clientes
por un campo de más — el mismo modo de falla que `ilegibles[]` documenta más abajo.

- `registro_patronal` son **11 caracteres**: los 10 del registro más su dígito verificador
  (posiciones 01-10 y 11 del layout de movimientos afiliatorios del IMSS). Se guarda junto y se
  parte al exportar. **El verificador no se calcula**: no hay algoritmo publicado, y un dígito
  inventado junto a un registro real es peor que un campo vacío.
- Vacío significa que **no se pueden emitir movimientos afiliatorios**, y el exportador lo dice
  en vez de emitirlos mal.

(El modo empresa única, que usaba el cliente `empresa` como Configuración de empresa, se
retiró en K.)

#### `regimen` — el régimen fiscal del CLIENTE (T1)

Clave de `c_RegimenFiscal` del SAT, hasta 3 dígitos, **opcional y vacía por default** por la
misma razón que `rfc`: una cartera escrita antes de T1 no la trae y el catálogo de
demostración tampoco.

Es el régimen **del cliente**, no del despacho. **La API no aplica ninguna regla fiscal sobre
este campo ni valida el catálogo:** lo guarda y lo devuelve. Quien decide qué pantallas de
Fiscalito se le pueden trabajar es el front, y el corte concreto que usa hoy —a un 626 no se le
ofrecen DIOT ni Retenciones, a un 612 sí— es un **criterio heredado de E-01, pendiente de
confirmar con la contadora** (`docs/decisiones-nomina.md` §D30). No se documenta aquí como regla
legal porque no se verificó con fuente oficial, y porque DIOT y Retenciones no comparten
fundamento. El alta de cliente ofrece sólo esas dos claves — las mismas que
`contributorProfiles.ts` declara para el perfil `contador` y las únicas que el motor y el
calendario manejan para persona física.

**Vacío significa "no capturado", y el front lo dice en pantalla** en vez de suponerlo en
silencio: aplica el 612 (el set completo) y avisa de dónde salió ese valor.

El campo está declarado en `ClienteCarteraSchema`: sin declararlo, cada guardado por la API
(el único camino desde P0-01) lo escribiría vacío. Los documentos sin la llave se leen igual.

#### `rfc`, `codigo_postal` y `clave_entidad` — los datos fiscales del cliente (C-01)

El alta y la edición de cliente del despacho los capturan; son **obligatorios en un alta nueva
del formulario** y **opcionales para el contrato**: los tres van vacíos por default, así que un
cliente de demostración o uno guardado antes de C-01 se sigue guardando sin ellos.

- **`rfc`** — se guarda en mayúsculas y sin espacios (el backend normaliza antes de validar).
  Si trae valor: formato `^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$` y, para los regímenes que conoce, la
  longitud tiene que casar con `regimen`: **601 = 12, 612 = 13, 626 = 12 o 13**
  (`docs/decisiones-nomina.md` §D31). Otro régimen, o vacío: sólo formato. Un RFC y un régimen
  que no casan **rebotan en cualquier guardado** con 422, no sólo cuando cambia el RFC; el
  formulario aplica la misma regla, así que ningún camino acepta lo que el otro rechaza.
- **`codigo_postal`** — 5 dígitos (`^(\d{5})?$`), del domicilio fiscal. Sirve como default
  del `LugarExpedicion` del CFDI de nómina, pero **no siempre coinciden** (ABIERTO, contadora).
- **`clave_entidad`** — clave del catálogo `c_Estado` del SAT, sólo México (33 claves: las 32
  entidades con `CMX` y la anterior `DIF` para la Ciudad de México). Fuente:
  `apps/api/tests/xsd/catCFDI.xsd`, y un test compara `ENTIDADES_C_ESTADO` contra ese archivo.
  Sirve como default de la `ClaveEntFed` del CFDI de nómina, pero ésa es la entidad donde el
  **trabajador presta el servicio** (la que pesa para el ISN), no necesariamente la del cliente
  (ABIERTO, contadora).

**En `GET /cartera/clientes`** vienen cuando el documento los tiene y **faltan** cuando no (la
lectura no tipa estricto): el front lee ausente como "Sin capturar".

**ABIERTO — el `PUT` escribe todos los campos del esquema.** `guardar_cliente` hace
`model_dump` de todo el schema, defaults incluidos, así que un `PUT` que no mande
`codigo_postal` o `clave_entidad` los escribe **vacíos** (el merge sólo conserva los campos
que el esquema NO conoce). El formulario de cliente siempre los manda, así que hoy nadie lo
dispara; es el mismo comportamiento que ya tenía `regimen`.

#### `guia_subdelegacion` — el número que asigna el IMSS (O-04)

Cinco dígitos. Va en las posiciones 134-138 de **cada** movimiento afiliatorio y en el registro
de cifras de control. **No se calcula ni se deduce**: lo asigna la subdelegación. Vacío
significa que el archivo del IMSS no se puede emitir, y el exportador lo dice con el nombre del
campo — un archivo con ese campo en blanco lo rechaza el IMSS sin decir cuál faltaba.

#### `apellido_paterno`, `apellido_materno` y `nombres` del empleado (O-04)

Tres campos de 27 caracteres, opcionales y vacíos por default. El layout de movimientos
afiliatorios del IMSS los pide **por separado** (posiciones 23-49, 50-76, 77-103) y la app sólo
guardaba el nombre completo.

**Se capturan; no se parten.** En español el apellido compuesto es la norma ("SANTA CRUZ", "DE
LA TORRE", "MARIA DE LOS ANGELES"), así que cualquier heurística falla en una parte grande de la
plantilla — y un movimiento afiliatorio con el apellido mal partido va sobre **otra persona**.
Misma política del NSS y de `fecha_alta`: vacío cuando no se conoce, nunca inventado. Quien los
tenga vacíos no se exporta, y el exportador lo dice.

#### `parametros` — las prestaciones del patrón (O-03)

`tabla_vacaciones` y `horario` **se validan AL GUARDAR**, con el mismo validador que usa
`POST /nomina/sbc`: una escala bajo el mínimo del Art. 76 devuelve 422 aquí, no tres pantallas
después. `horario` acota las horas a `00:00`-`23:59`, los días laborables a 0-6 sin repetidos,
y exige salida posterior a entrada — **sin días laborables el cierre no marca una sola falta y
la nómina sale completa siempre**, así que no puede quedar en manos de una validación de
navegador.

Objeto anidado con `dias_aguinaldo` (mín. 15, Art. 87 LFT), `prima_vacacional` (proporción,
mín. 0.25, Art. 80 LFT), `tabla_vacaciones` y `horario` (entrada, salida, tolerancia y días
laborables del checador). **Con default completo**: una cartera escrita antes de O-03 no lo
trae y tiene que seguir leyéndose — el default es el mínimo de ley, que es lo que la app
aplicaba hasta ahora.

Alimentan el **factor de integración** y con él el SBC, y el cierre del checador. **Lo que NO
está aquí**: las tablas de ISR, las cuotas del IMSS, la UMA y el salario mínimo. Son de ley,
viven en el motor con su fuente publicada y se actualizan con el DOF, no con un formulario.

### `PUT /api/v1/cartera/clientes/{cliente_id}`
Alta o edición, idempotente. El `id` del cuerpo **debe** coincidir con el de la
URL: adivinar cuál vale escribiría el cliente equivocado. El `id` no se guarda
dentro del documento — ya es su nombre.

### `DELETE /api/v1/cartera/clientes/{cliente_id}`
**Borra en cascada** empleados y dispositivos: sin esto quedarían huérfanos —con su
salario y su NSS— y reaparecerían al recrear un cliente con el mismo id. 404 si el
cliente no está en tu despacho.

### `GET /api/v1/cartera/clientes/{cliente_id}/empleados`
La plantilla del cliente, leída de la cartera que este CRUD escribe. Distinta de
`/despacho/clientes/{id}/empleados`, que es la SEMILLA de demostración y no la
cartera de nadie. `{exito, cliente_id, total, sin_vincular, ilegibles[], ilegibles_detalle[], empleados[]}`.

`ilegibles[]` son los `empleado_no` de documentos guardados que **no pasan la
validación actual** —un NSS de una versión anterior, un campo que falta— y que
por eso **no vienen en `empleados`** ni cuentan en `total`. Se reportan en vez de
tumbar la respuesta con un 500: como el front pide los empleados de todos los
clientes en paralelo, un solo documento legado dejaba la cartera **completa** en
cero. `ilegibles_detalle[]` trae lo mismo con `{empleado_no, nombre, razon}` (P0-01,
R-10): la ficha del cliente los pinta con su razón, junto al aviso de "no vinculados".
`ilegibles[]` se conserva como lista de `empleado_no` por compatibilidad.

> **Todavía nadie la consume para calcular.** Una versión anterior de este
> documento decía "ésta es la fuente que el cálculo de nómina lee, y es lo que
> hace verdadero el criterio de R-07". **Era falso.** `routes/nomina.py` no se
> tocó: `POST /nomina/calcular-periodo` sigue recibiendo `empleados` en el
> cuerpo. El tercer criterio de R-07 **no se cumple**, y encender el interruptor
> no lo cambia — sólo mueve de dónde saca el navegador la plantilla que sigue
> mandando. Cerrar esa costura es tarea propia.

### `PUT /api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}`
El `empleado_no` de la URL es la llave del **cálculo**; `employee_no`, en el
cuerpo, es la del **checador** y puede ser nula. Son distintas, y fundirlas es el
defecto que G-02 vino a arreglar.

El **NSS** se valida con la misma política que el front: 11 dígitos o vacío, **sin
exigir el dígito verificador** (§D25 de `docs/decisiones-nomina.md`). Vacío
siempre se acepta, y eso es lo que hace seguro bloquear por longitud.

### `DELETE /api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}`
Idempotente: borrar uno que no existe responde 200; un cliente de otro despacho, 404.

### Dispositivos del cliente (R-09 → P0-01)

Checadores biométricos. Mismo modelo que `DispositivoChecador` del front
(`dispositivosApi.ts`) y las mismas reglas que su `validarDispositivo`. La IP se
**registra, no se consulta**: nada del backend se conecta al aparato. `employee_nos` son
llaves del **checador** (`employee_no`), no del cálculo.

Cuerpo (`DispositivoSchema`): `{nombre (1-120, obligatorio), ip (IPv4 o ""), puerto
(1-65535, default 80), marca, modelo, serial, employee_nos[], notas}`. Se limpian espacios;
`employee_nos` se guarda sin vacíos ni repetidos. Un `serial` no vacío que ya tenga OTRO
dispositivo del mismo cliente es 422.

- **`GET /api/v1/cartera/clientes/{cliente_id}/dispositivos`** →
  `{exito, cliente_id, total, dispositivos[]}`, cada uno con su `id`. Lectura laxa.
- **`POST /api/v1/cartera/clientes/{cliente_id}/dispositivos`** → **201**
  `{exito, id, mensaje}`. El `id` lo genera el backend: nombre y serial son editables y
  repetibles, y un id derivado de ellos convertiría un cambio de nombre en un aparato nuevo.
- **`PUT /api/v1/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}`** →
  `{exito, id, mensaje}`. 404 si no existe en ese cliente (las altas van por POST). Merge.
- **`DELETE /api/v1/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}`** →
  `{exito, mensaje}`. Idempotente. No borra a nadie de la plantilla ni del aparato.

### Migración única desde Firestore (`apps/api/scripts/migrar_firestore.py`)

`users/{uid}/clientes/{id}`, `.../empleados/{no}` y `.../dispositivos/{id}` → despacho
`id = uid`. Copia cada documento **tal cual** a `datos` (sin validar: un legado se migra y
la API lo reporta en `ilegibles`). **Idempotente**: lo que ya existe en SQL no se toca (ni
se duplica ni se pisa con la copia vieja); lo que falta se agrega. `--dry-run` reporta lo
que haría sin escribir; `--uid` (repetible) limita a esas cuentas. Un id más largo que la
columna se reporta como omitido en vez de truncarse. **No migra** el perfil (`users/{uid}`)
ni el historial de declaraciones: siguen en Firestore hasta tener tabla.

    cd apps/api && python -m scripts.migrar_firestore --dry-run

> **Todavía nadie la consume para calcular.** `POST /nomina/calcular-periodo` sigue
> recibiendo `empleados` en el cuerpo (R-08 → P4-01).

## Nómina (épica D — demo)

> ⚠️ **DEMO — sin autenticación, no desplegar.** La auth de todo `/api/v1` es S-00b.

### `GET /api/v1/nomina/demo/plantilla`

Todo lo que la pantalla de la demo necesita y **no puede inventarse**. Existe para
que el front no escriba **ni una constante fiscal**: sin él tendría que hardcodear en
TypeScript los nueve empleados y la `prima_riesgo` —que tiene fundamento legal
(Art. 72/74 LSS) y dueño en `app/demo_nomina.py`— en un lugar donde ningún test
comprueba que no diverjan.

| Query param | Default | Notas |
|---|---|---|
| `cliente` | `demo` | Cualquier otro responde **422**, con el mismo argumento que `calcular-periodo`: la plantilla por omisión no es la nómina de nadie más. |

```json
{ "exito": true, "cliente": "demo", "origen": "demo",
  "empleados": [{"empleado_no": "E-01", "nombre": "ANA BEATRIZ XALA MORA"}],
  "prima_riesgo": "0.0054355", "clave_periodicidad": "04", "zona": "general",
  "periodo_sugerido": {"inicio": "2026-08-16", "fin": "2026-08-31",
                       "fecha_pago": "2026-08-31"} }
```

- **Sin salarios.** El front no los necesita —los recibos ya los traen— y menos
  superficie es menos que pueda salir por donde no debe. Las identidades son
  sintéticas (fixtures de S-04).
- **`periodo_sugerido` sale de la regla de quincena, no de las checadas.** Deducirlo
  de la primera y la última checada **da mal**: del 16 al 31 de agosto de 2026 son
  **16 días naturales**, pero la primera checada es del 17 porque el 16 es domingo,
  o sea **15**. Ese día de menos entra a `DiasDelPeriodo` y a `dias_pagados`, así que
  movería las cuotas del IMSS y el ISR — en pantalla y en el PDF. Hay test con los
  dos números literales.
- **`fecha_pago` viene explícita, nunca `null`**: la pantalla tiene que poder mostrar
  con qué fecha se va a calcular sin replicar el default. §D18 sigue abierta sobre
  cuál debería ser.
- El periodo es la **última quincena ya terminada**, la misma regla que usa el
  simulador de D-05 al sembrar. **Sembrar y demostrar tienen que caer el mismo día**:
  si se siembra el 15 y se demuestra el 16, son quincenas distintas y el panel sale
  vacío.

### `GET /api/v1/nomina/periodo-sugerido` (O-03)

El **último periodo terminado** para una periodicidad de pago.

| Parámetro | Tipo | Default | Significado |
|---|---|---|---|
| `clave_periodicidad` | str | — | Clave de `c_PeriodicidadPago`: `01` diaria, `02` semanal, `04` quincenal, `05` mensual |
| `fecha` | date | hoy | Desde qué día se mira |

**Respuesta 200**

```json
{
  "exito": true,
  "clave_periodicidad": "05",
  "periodo": { "inicio": "2026-08-01", "fin": "2026-08-31", "fecha_pago": "2026-08-31" },
  "dias_naturales": 31
}
```

**Por qué existe.** Antes de O-03 el front proponía **siempre una quincena**: copiaba el
`periodo_sugerido` del cliente `demo` a todos, sin mirar su clave. Con la periodicidad abierta
a semanal y mensual, elegir Mensual dejaba al patrón con un periodo que el propio motor
rechaza — un selector que rompe la app en dos de sus tres opciones.

**La regla vive aquí y no en TypeScript** porque de la `fecha_pago` dependen la UMA, el salario
mínimo, la tarifa del Anexo 8 y el transitorio de enero del subsidio (§D18): dos
implementaciones serían dos verdades sobre con qué valores se calcula la nómina.

**Siempre el periodo ya TERMINADO**, nunca el que está en curso: `cerrar_periodo` marca falta
todo día laborable sin checada, incluidos los que aún no llegan.

**El endpoint valida lo que propone** contra la misma guarda de duración que usa el cálculo, así
que nunca devuelve un periodo que después se vaya a rechazar. Hay un test que recorre el año
completo, día por día, para las cuatro claves.

**422** para una clave sin tarifa publicada (catorcenal, decenal, bimestral, unidad de obra,
comisión, precio alzado — §D10): proponer un periodo para ellas sería ofrecer un cálculo que
después no se puede hacer.

### `POST /api/v1/nomina/calcular-periodo`

Calcula la nómina completa de un periodo: recibo por empleado y cuotas por ramo.
**Es un orquestador, no un motor**: llama a `armado.py`, `cuotas.py` e
`isr_nomina.py` y no reimplementa ninguna fórmula. Los endpoints granulares
(SBC, cuotas y recibo por separado) son F1-07.

```json
{ "cliente": "demo",
  "periodo": {"inicio": "2026-08-16", "fin": "2026-08-31", "fecha_pago": "2026-08-31"},
  "incidencias": [
    {"empleado_no": "E-01", "dias_periodo": 16, "faltas": 1,
     "dias_ausentismo": 1, "dias_incapacidad": 0}
  ],
  "parametros": {"prima_riesgo": "0.0054355", "clave_periodicidad": "04",
                 "dias_pagados": null},
  "empleados": null,
  "incluir_explicacion": false }
```

| Campo | Notas |
|---|---|
| `periodo.fecha_pago` | Opcional, default `fin`. **La vigencia se lee de aquí**, no del fin: UMA, salario mínimo, tarifa del Anexo 8 y el transitorio de enero del subsidio. Una quincena que cierra el 31-ene y se paga el 5-feb se calcula con los valores de febrero. *DECISIÓN PROVISIONAL (nocturno): que el patrón pague el último día del periodo no lo confirmó nadie.* |
| `incidencias[].dias_periodo` | **Días naturales**, los que devuelve `cerrar-periodo`. Nunca `dias_laborables` ni `dias_cotizados`: ese último es informativo y tomarlo como base de cuotas contradice a `cuotas.py` (Art. 31 LSS, §D3). |
| `incidencias[].dias_ausentismo` | Alimenta `DiasDelPeriodo`. **`faltas` es lo que descuenta días pagados.** Hoy son el mismo número; en F1-09 divergen, porque una incapacidad o unas vacaciones no son ausentismo injustificado y las vacaciones sí se pagan. |
| `parametros.prima_riesgo` | Obligatoria y sin default: se autodetermina cada febrero (Art. 74 LSS), no es tasa de ley. Acotada a 0.005–0.15 (Art. 72). |
| `parametros.clave_periodicidad` | `c_PeriodicidadPago`: 01 diaria, 02 semanal, 04 quincenal, 05 mensual. **Catorcenal (03) y decenal (10) responden 422** con su motivo: nadie publica una tarifa verificada (§D10). |
| `parametros.dias_pagados` | Override opcional. Sin él, `dias_periodo − faltas`. *DECISIÓN PROVISIONAL (nocturno): ante una falta injustificada se descuenta el día y **no** la parte proporcional del séptimo (Art. 69 LFT). Es la lectura que favorece al trabajador.* |
| `empleados` | Opcional. **Omitirlo usa la plantilla de la demo, y sólo es válido para `cliente: "demo"`**: cualquier otro cliente sin `empleados` responde 422. Calcularle a un cliente real la nómina de otras nueve personas —y dejar que la exporte en PDF— sería peor que fallar. El `salario_diario_integrado` es **dato de entrada** y no se deriva de la antigüedad (§D9). |

Respuesta: `{exito, cliente, periodo, origen_plantilla, recibos[], porcion_mensual,
porcion_bimestral, advertencias[], explicacion?}`.

- **`fecha_pago_efectiva`** es la fecha con la que se calculó, **ya resuelto el
  default** (`periodo.fecha_pago` o, si no vino, `periodo.fin`). Se serializa para
  que el cliente no tenga que replicar esa regla: de esa fecha dependen la UMA, el
  salario mínimo, la tarifa del Anexo 8 y el transitorio de enero del subsidio, y
  §D18 está abierta sobre cuál debería ser el default. Un PDF que imprimiera una
  fecha derivada en el cliente mentiría en silencio el día que el default cambie.
- **`origen_plantilla`** es `"demo"` o `"request"`. Existe para que el PDF de D-07 no
  pueda mentir sobre de quién es la nómina.
- **`porcion_mensual` y `porcion_bimestral` NO son el entero del Art. 39 LSS.** Son
  lo **devengado en este periodo** por los ramos de cada periodicidad de entero: una
  quincena trae **media** mensualidad de EyM/IyV y **un doceavo** de bimestre de
  Retiro/CEAV/Infonavit. Para enterar hay que sumar los periodos que caen en el mes o
  en el bimestre. Se llaman así, y no `consolidado_*`, precisamente para que nadie los
  lea como el pago del mes.
- `recibos[].ramos[]` lleva base diaria, días, importes y **fundamento** por ramo: es
  lo que permite conciliar contra la EMA y la EBA renglón por renglón.
- `advertencias[]` siempre trae la nota de la porción del periodo, y además avisa
  cuando algún empleado supera **7 días de ausentismo**: el ausentismo prolongado
  puede tener un tratamiento distinto que el motor **no** aplica —cobra las cuotas
  completas de cada ramo, que es la dirección conservadora— y ese caso requiere
  revisión manual. **La advertencia no afirma qué concede el Art. 31 LSS**: ese
  tratamiento sigue PROVISIONAL (§D3, §D20) y no hay transcripción verificada contra
  el DOF en el repo.

**Límite conocido:** el subsidio se compara contra un ingreso mensual de `SBC × 30.4`
(§D11, provisional) calculado con el SBC **acotado**, mientras la evidencia de §D11 se
construyó con el timbrado. Coinciden en los 9 empleados de la demo y divergen en un
trabajador al piso del Art. 28.

#### Los tres totales del periodo (O-04)

`total_percepciones`, `total_neto` y `total_isr` viajan en la respuesta y salen del **motor**:
`ResultadoPeriodo` ya los calculaba y no se serializaban, así que el front los recomponía
sumando los recibos.

**Son el ancla del cuadre de los exportadores.** Comparar el PDF contra los TXT cuando los dos
derivan del mismo módulo del front es tautológico: sólo cazaría un campo escrito en la posición
equivocada, y un error en la suma pasaría verde en los dos lados. Las cuotas obrera y patronal
ya eran derivables de `porcion_mensual` / `porcion_bimestral`, así que no se duplican.

#### La duración del periodo tiene que casar con la periodicidad (O-03)

`POST /nomina/calcular-periodo` **rechaza con 422** un periodo cuya duración no corresponde a
su `clave_periodicidad`:

| Clave | Duración esperada (días naturales) | De dónde sale |
|---|---|---|
| `01` diaria | 1 | — |
| `02` semanal | 7 | — |
| `04` quincenal | **13 a 16** | mín.: 16→28 de febrero; máx.: 16→31 de un mes de 31 |
| `05` mensual | 28 a 31 | febrero común, bisiesto, y los meses de 30 y 31 |

Hasta O-03 **nadie lo comprobaba**: `periodo.py` sólo verificaba que todas las incidencias
midieran lo mismo entre sí. `backlog.md` §G puntos 3 y 6 describen las dos direcciones — un
patrón Mensual con base de quincena recibiendo la tarifa mensual del Art. 96 (**ISR
subestimado, con recibo creíble**) y el simétrico. La única defensa vivía en el navegador, con
sus propios umbrales.

**El rango quincenal es 13 a 16, y el borde importa.** 17 días no es nunca una quincena, y la
tarifa quincenal se deriva a exactamente 15 (`_derivar_tarifa(TARIFA_MENSUAL_2026, 15)`).

**Bloquea también el periodo PARCIAL de un alta o una baja**, que es una regresión funcional
declarada y conservadora: ver `docs/decisiones-nomina.md` §D26. Y aceptar 13 días abre una
pregunta aparte —si esa quincena se paga 13 o 15— que queda en §D27. Por eso el mensaje del 422
distingue las dos causas — tienen arreglos opuestos, y confundirlas lleva a cambiar la
periodicidad del patrón, que es el dato bueno.

### `POST /api/v1/nomina/sbc` (G-01)

Integra un salario **fijo** (Art. 30 fr. I LSS) con el factor del Art. 27 y lo acota entre 1
salario mínimo y 25 UMA (Art. 28). Lo llama la pantalla de alta de empleado mientras se teclea el
salario, para que el front **no reimplemente la fórmula**: un factor calculado en TypeScript sería
una segunda verdad sobre el Art. 27 sin ningún test que la cuide.

**Orquestador, no motor:** llama a `factor_integracion`, `sbc_fijo` y `clamp_sbc` de
`nomina_engine/integracion.py`. No calcula nada por su cuenta.

**Request**

```json
{
  "salario_diario": "500.00",
  "fecha": "2026-09-01",
  "zona": "general",
  "anios_servicio_cumplidos": 3,
  "dias_aguinaldo": 15,
  "dias_vacaciones": 0,
  "prima_vacacional": "0.25"
}
```

`tabla_vacaciones` (O-03) es la escala propia del patrón, `[[años, días], ...]`. Vacía o
ausente, manda el Art. 76 LFT. **Se manda entera con `anios_servicio_cumplidos`, y el front
NUNCA resuelve los días**: `vacaciones_efectivas` ya define `0 = los de ley` y con una tabla
ese centinela sería ambiguo, además de que buscar el renglón en TypeScript sería una segunda
implementación de la misma búsqueda. Los días que se aplicaron vuelven en
`dias_vacaciones_aplicados`.

Un renglón por **debajo** del mínimo de ley devuelve 422 nombrando cuál y qué exige la ley. Por
**encima** del último renglón capturado se devuelve `max(renglón, ley)`: una tabla corta no
puede bajarle los días a quien gana antigüedad — el Art. 27 LSS integra lo que el patrón
otorga, no el mínimo.

`fecha` es **obligatoria y sin default**: `clamp_sbc` mueve el piso el 1-ene (salario mínimo) y el
tope el 1-feb (UMA), así que un `date.today()` implícito haría que el número del modal cambiara
solo entre enero y febrero. `dias_vacaciones: 0` significa *los de ley que le tocan a su
antigüedad* (Art. 76 LFT).

**Respuesta 200**

```json
{
  "factor": "1.0521",
  "dias_vacaciones_aplicados": 16,
  "sbc_sin_acotar": "526.05",
  "sbc": "526.05",
  "piso_aplicado": false,
  "tope_aplicado": false,
  "piso": "315.04",
  "tope": "2932.75",
  "fundamento": "Arts. 27, 28 y 30 fr. I LSS; Arts. 76, 80 y 87 LFT."
}
```

Las banderas del clamp **no son adorno**: `piso_aplicado` es el único camino por el que un SBC
llega a ser exactamente 1 salario mínimo, que es el supuesto del Art. 36 LSS (el patrón absorbe la
cuota obrera) y el renglón de 3.150% de la tabla de CEAV. Acotar en silencio escondería las dos.

**422** — con el sobre `{"exito": false, "error": "..."}`. Los casos que importan:
aguinaldo menor a 15 días (Art. 87 LFT: subintegraría el SBC y con él todas las cuotas) y prima
vacacional fuera de `[0.25, 1]` — pasar `25` en vez de `0.25` produce un factor de 1.86 y un SBC
inflado 77% que ninguna tabla de referencia detecta.

**Lo que NO hace, a propósito:** no recalcula un SDI que ya venga dado (§D9: cuando sale de un CFDI
timbrado es dato de entrada); no acepta conceptos integrables (§D5: el motor no decide qué integra,
y mandar una despensa completa sobreintegraría); y no usa LLM ni acepta `incluir_explicacion`.

### `POST /api/v1/nomina/cfdi` (T4)

Serializa un recibo **ya calculado** al XML de un CFDI de nómina 4.0 con complemento 1.2,
**sin timbrar**. Expone `nomina_engine/cfdi_nomina_xml.py`, que existía desde F1-05 validado
contra los XSD del SAT y que **nadie importaba**.

**Lo que sale de aquí es estructuralmente válido y fiscalmente nada.** Tres cosas lo hacen
inconfundible, y las tres están en el módulo desde F1-05: no lleva `tfd:TimbreFiscalDigital`
—el XSD no lo exige, así que su ausencia es legal y verificable—, sus atributos de sello son
centinelas explícitos (`PRE-RECIBO-SIN-TIMBRAR`, `NoCertificado` de veinte ceros), y el XML
abre con un comentario que lo dice. **No timbra y no habla con ningún PAC**: está fuera de
alcance por el `CLAUDE.md` de la raíz.

**No calcula nada.** Los importes llegan del motor por `/nomina/calcular-periodo` y aquí sólo
se suman para los totales que el comprobante exige — `nomina_engine/recibo.py` es aritmética
pura sobre partidas dadas. Ni ISR ni cuotas se tocan.

**Request**

```json
{
  "recibo": { "...": "un elemento de `recibos[]` de /nomina/calcular-periodo, sin remapear" },
  "patron": {
    "rfc": "XAP0101011X0",
    "nombre": "PATRON DEMO SA DE CV",
    "regimen_fiscal": "601",
    "registro_patronal": "X1234567890",
    "codigo_postal": "91090",
    "clave_entidad": "VER"
  },
  "trabajador": {
    "rfc": "XACC010101AA3",
    "nombre": "CARLA DENISSE XOLO PEREZ",
    "curp": "XACC010101HVZBBB03",
    "numero_seguridad_social": "01010101033",
    "codigo_postal": "91020",
    "fecha_inicio_relacion_laboral": "2024-05-26",
    "tipo_contrato": "01",
    "numero_empleado": "E-03",
    "puesto": "OPERATIVO",
    "departamento": "OPERACIONES",
    "riesgo_puesto": "2",
    "periodicidad_pago": "04",
    "salario_base_cotizacion": "399.52",
    "salario_diario_integrado": "399.52"
  },
  "periodo": { "inicio": "2026-08-16", "fin": "2026-08-31" },
  "tipo_nomina": "O"
}
```

`recibo` es el **subconjunto** de `ReciboSchema` que el CFDI usa (`empleado_no`, `nombre`,
`dias_pagados`, `percepciones`, `deducciones`, `otros_pagos`). Un elemento de `recibos[]` tal
como sale de `/nomina/calcular-periodo` lo satisface **sin remapear**: los campos de más —SBC,
cuotas, ramos, banderas del clamp— se ignoran. Se declara aparte para que el contrato diga qué
se usa de verdad.

`antiguedad` es **opcional**: vacía se deriva de `fecha_inicio_relacion_laboral` a
`periodo.fin` en **semanas completas** (formato `P##W`, doc 24 §2), medida contra el fin del
periodo que se paga y no contra hoy. Se acepta capturada porque un histórico que venga de un
CFDI timbrado ya la trae. Los otros defaults son claves de catálogo con un valor único para el
caso ordinario: `tipo_regimen` `02` (sueldos y salarios), `tipo_jornada` `01` (diurna),
`sindicalizado` `No`, `tipo_nomina` `O`.

**Respuesta 200**

```json
{
  "exito": true,
  "xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>…",
  "timbrado": false,
  "nombre_archivo": "cfdi-nomina-sin-timbrar-E-03-2026-08-16-2026-08-31.xml",
  "advertencia": "Pre-recibo SIN TIMBRAR. No tiene valor fiscal: …"
}
```

`timbrado` es **siempre `false`** y no es un campo que algún día se vuelva `true` solo:
mientras exista, la respuesta afirma que el documento no tiene valor fiscal. El front lo pinta
como "Pendiente de timbrado PAC". `sin-timbrar` va en el nombre del archivo porque un `.xml`
suelto en la carpeta de descargas del contador no tiene dónde decir lo que es.

**422** — con el sobre `{"exito": false, "error": "..."}`. **No inventa identidades:** RFC,
CURP, NSS, códigos postales, registro patronal y clave de entidad son obligatorios y sin
default. `clave_entidad` no cae a `VER` —es la del patrón del caso real (§D8), no la de nadie
más— ni `riesgo_puesto` a `99`, que es una afirmación sobre el puesto y no un relleno. Una
percepción sin el desglose `gravado`/`exento` también se rechaza: asumir "todo gravado" o
"todo exento" cambiaría la base del ISR de un recibo que alguien va a firmar.

**Lo que el XSD NO valida:** las reglas de la Guía de llenado ni las validaciones adicionales
del Anexo 20 (§D7). Que valide aquí **no es evidencia de que un PAC lo aceptaría**. En
particular, el generador **no emite `FormaPago`**, que el doc 24 §2 pide con valor `99`: el XSD
lo deja pasar porque es opcional, y cambiarlo es tocar el módulo del motor — queda anotado como
deuda, no corregido de paso.

### Tool del agente: `calcular_nomina_periodo`

Disponible en `POST /api/v1/agente/predeclaracion`. Recibe `{periodo_inicio,
periodo_fin, cliente?}` y **arma el cálculo con lo que hay en memoria**: la plantilla
de la demo más las incidencias que salen de `cerrar_periodo` sobre las checadas del
almacén de asistencia, de modo que la pregunta "¿cuánto pago de IMSS este mes?" se
contesta sin que el usuario capture plantilla ni incidencias.

**Dos precisiones para no prometer de más.** (a) El endpoint del agente sigue exigiendo
`contribuyente` y `periodo_year` en el cuerpo, como cualquier otra llamada suya: lo que
esta tool evita es capturar los sueldos y el cierre, no el request completo. (b) Que un
LLM real **decida** invocarla no está verificado: los system prompts la enumeran y los
tests comprueban el registro y el despacho, pero en CI no hay key de ningún proveedor y
ninguna prueba pega a uno.

- **Sin checadas en el periodo devuelve un error, no una nómina.** Con el almacén
  vacío, `cerrar_periodo` marca todos los días laborables como falta y el motor
  produce una nómina perfectamente válida y completamente falsa, que el agente
  afirmaría en el chat como un hecho.
- Avisa de las checadas de `employeeNo` que no estén en la plantilla: **no entran al
  cálculo**, y un alta con el número equivocado en el dispositivo se vería como
  "faltaron todos".
- **El almacén de asistencia no se replica entre workers.** Con más de un proceso, la
  petición del agente puede caer en uno distinto del que recibió el POST del checador
  y no ver ninguna checada. Lo resuelve F1-09 con Firestore.
- La descripción de la tool le dice al modelo que **reporte los importes tal cual y no
  sume, promedie ni derive nada**: la regla de oro del repo es que el LLM explica y
  nunca calcula.

---

## Declaraciones — regímenes sin motor (T6)

`POST /api/v1/pre-declaracion` y `POST /api/v1/pre-declaracion-anual` **rechazan el régimen
601 (General de Ley Personas Morales)** con `400`. Desde P3-01 el `detail` dice a dónde ir: el
motor PM vive en `/api/v1/impuestos/clientes/{clave}/pm/pagos-provisionales` y `.../anual`
(§Personas morales y anual); esta puerta sigue siendo la de `calculadora.py` (personas físicas).

- **El corte va ANTES que cualquier otra validación**, incluida la de "se requiere al menos una
  factura": un 601 sin facturas tiene que enterarse de que no hay motor, no de que le falta un
  XML.
- **Y antes de `calcular_declaracion`.** `app/fiscal_engine/calculadora.py` sólo conoce personas
  físicas y su rama por defecto no falla: devolvería un ISR de persona física, creíble y
  equivocado, calculado sobre los ingresos de una moral. El guard es lo único que separa un 400
  honesto de ese número.
- La lista vive en `REGIMENES_SIN_MOTOR` (`app/routes/declaraciones.py`), no dispersa en `if`s.
- **El 601 SÍ es un valor conocido del catálogo** —`RegimenFiscal.GENERAL_LEY_PM` en
  `app/schemas/fiscal.py` y `NOMBRES_REGIMEN` en `app/constants.py`—, y el resto de los
  endpoints **no lo rechazan**. En particular `POST /api/v1/calendario` lo acepta y le devuelve
  el calendario de `contributor_type: "pyme"` (mensual + DIOT + anual). **Corregido en P3-01:**
  la anual de una persona moral (601, o 626 con RFC de 12 caracteres) vence el **31 de marzo**
  del año siguiente (Arts. 9 último párrafo y 76 fr. V LISR; `fecha_limite_anual` en
  `fiscal_engine/calendario.py`); las personas físicas siguen en abril (Art. 150).

---

## Bóveda de CFDI (plan P, P0-03)

Comprobantes (I, E, P, N, T) **por cliente**, deduplicados por UUID, con el XML original en el
adaptador de almacenamiento (`FISCALITO_ALMACENAMIENTO`, ver `docs/servicios-externos.md`).
Todas las rutas exigen `Authorization: Bearer <ID token>` y resuelven el cliente con
`contexto_actual` + `cliente_o_404`: **un cliente de otro despacho es 404**, igual que uno que no
existe. `{clave}` es la clave pública del cliente (`taller`). El UUID se acepta en cualquier
capitalización y se guarda en mayúsculas. Importes como texto con 2 decimales.

### `POST /api/v1/boveda/clientes/{clave}/cfdi`

`multipart/form-data`, campo `archivos` repetible (máx. 200 por carga): XML sueltos (`.xml` o
`.XML`) y/o ZIP. Del ZIP se lee un miembro a la vez; un ZIP dentro de otro **no** se abre. Cada
XML pasa de 10 MB → rechazado. Respuesta 200:

```json
{ "exito": true, "rfc_cliente": "XEXX010101AB1", "rfc_deducido": false,
  "importados": 498, "duplicados": 1,
  "rechazados": [{"archivo": "lote.zip/notas.txt", "razon": "No es XML."}],
  "importados_detalle": [{"archivo": "lote.zip/a.xml", "uuid": "…", "direccion": "emitido", "tipo": "I"}],
  "duplicados_detalle": [{"archivo": "lote.zip/b.xml", "uuid": "…", "razon": "ya existía"}] }
```

- **Duplicado** = el UUID ya está en la bóveda de ESE cliente o salió antes en el mismo lote.
  No se sobrescribe nada. El mismo UUID sí puede vivir en dos clientes (emisor y receptor).
- **Dirección**: `emitido` si el RFC del cliente es el emisor, `recibido` si es el receptor; si
  no es ninguno, el XML se **rechaza** ("no es emisor ni receptor").
- **Cliente sin RFC**: se toma el RFC más frecuente del lote (`rfc_deducido: true`). La ficha
  del cliente **no** se modifica.
- Rechazos con razón: no es XML ni ZIP, XML ilegible, con DOCTYPE, versión distinta de 3.3/4.0,
  sin timbre, `TipoDeComprobante` inválido, ZIP dañado o anidado.

### `GET /api/v1/boveda/clientes/{clave}/cfdi`

Query (todo opcional): `desde`, `hasta` (AAAA-MM-DD, inclusivos, sobre `Fecha` del CFDI),
`tipo` (`I|E|P|N|T`), `direccion` (`emitido|recibido`), `rfc` (la **contraparte**: receptor de
lo emitido, emisor de lo recibido), `estatus` (`vigente|cancelado|desconocido`), `pagina`
(≥1, default 1), `por_pagina` (1–200, default 50). `desde > hasta` → 422. Orden: fecha
descendente.

```json
{ "exito": true, "total": 500, "pagina": 1, "por_pagina": 50,
  "comprobantes": [{ "uuid": "…", "version": "4.0", "tipo": "I", "fecha": "2026-03-10T10:00:00",
    "serie": "A", "folio": "1", "rfc_emisor": "…", "nombre_emisor": "…", "rfc_receptor": "…",
    "nombre_receptor": "…", "direccion": "emitido", "subtotal": "1000.00", "descuento": "0.00",
    "total": "1160.00", "moneda": "MXN", "metodo_pago": "PUE", "forma_pago": "03",
    "uso_cfdi": "G03", "iva_trasladado": "160.00", "iva_retenido": "0.00",
    "isr_retenido": "0.00", "ieps": "0.00", "estatus_sat": "desconocido", "origen": "manual" }] }
```

`estatus_sat` nace `desconocido` y P1-03 lo pone en `vigente` o `cancelado` (ver §Verificación
SAT). `origen` es `manual` (subido) o `sat` (descarga masiva, P1-01).

Desde P1-03/P1-04 cada comprobante trae además `fecha_estatus` (ISO o `null`: cuándo se
consultó el SAT), `estatus_cancelacion` (texto del SAT, p. ej. `"En proceso"`, o `""`) y
`art_69b`: `null` o `{"lista": "69b", "situacion": "definitivo", "nivel": "alto"}` si la
**contraparte** está en un listado del SAT (`nivel` `alto`/`medio` = rojo, `info` =
desvirtuado o sentencia favorable).

### `GET /api/v1/boveda/clientes/{clave}/cfdi/{uuid}/xml`

El XML **byte por byte** como se subió (`application/xml`, `Content-Disposition: attachment`).
Antes de entregarlo se verifica su SHA-256 contra el guardado: si no coincide, 500 y no se
entrega. 404 si el UUID no está en la bóveda de ese cliente.

### `DELETE /api/v1/boveda/clientes/{clave}/cfdi/{uuid}`

Quita el renglón y el XML del almacenamiento. `{"exito": true, "uuid": "…"}`; 404 si no existe.

### `GET /api/v1/boveda/clientes/{clave}/resumen`

Acepta los mismos filtros que la lista (sin paginar). Conteo y suma de `total` por mes, tipo y
dirección:

```json
{ "exito": true, "renglones": [
  {"periodo": "2026-03", "tipo": "I", "direccion": "emitido", "cantidad": 42, "total": "48720.00"} ] }
```

### `GET /api/v1/boveda/clientes/{clave}/facturas-calculo` (P1-06)

Los CFDI del periodo **ya en la forma del esquema `CFDI`** de `app/schemas/fiscal.py` (lo que
reciben todos los endpoints de cálculo). Query: `desde`, `hasta` (obligatorios, AAAA-MM-DD,
inclusivos, sobre `Fecha` del CFDI), `tipos` (opcional, `I,E,P,T` separados por coma; `N` → 422).
`desde > hasta` → 422. Lógica en `app/boveda_cfdi/calculo.py`; no calcula impuestos.

```json
{ "exito": true, "desde": "2026-03-01", "hasta": "2026-03-31",
  "facturas": [{ "uuid": "…", "fecha": "2026-03-05", "tipo": "I", "rfc_emisor": "…",
    "rfc_receptor": "…", "subtotal": 1000.0, "total": 1160.0, "iva_trasladado": 160.0,
    "iva_retenido": 0.0, "isr_retenido": 0.0, "descuento": 0.0, "uso_cfdi": "G03",
    "descripcion": "Servicio", "clave_prod_serv": "84111506", "metodo_pago": "PUE",
    "uuid_relacionado": null, "monto_pago": null }],
  "relacionados": [ /* originales PPD de OTROS periodos que los pagos del periodo liquidan */ ],
  "resumen": { "comprobantes": 4, "emitidos": 3, "recibidos": 1, "por_tipo": {"I": 3, "P": 1},
    "cancelados_excluidos": 1, "nomina_excluidos": 1, "relacionados_fuera_del_periodo": 1 },
  "advertencias": [] }
```

- **Cancelados fuera** (`estatus_sat = cancelado`, P1-03); los `desconocido` sí cuentan.
- **Nómina (`N`) fuera**: no es ingreso ni gasto del contribuyente en estos cálculos (mismo
  criterio que `facturasFiscales` del front); se cuenta en `nomina_excluidos`.
- **Pagos (`P`)**: uno por `DoctoRelacionado`, con `uuid_relacionado = IdDocumento` y
  `monto_pago = ImpPagado` (o `Monto` del pago si es el único documento y no trae `ImpPagado`).
  Si un pago liquida varias facturas, cada documento sale como `<UUID>#1`, `<UUID>#2`…
- **`relacionados`**: si el original PPD de un pago es de otro periodo, va aquí para que el motor
  lo cruce. **No** se cuenta en `resumen.comprobantes`; DIOT y retenciones no lo reciben.
- **Moneda**: importes a pesos con el `TipoCambio` del CFDI; sin `TipoCambio` en moneda
  extranjera se manda tal cual y se dice en `advertencias`.
- `descripcion` y `clave_prod_serv` son los del primer concepto (como el parser del navegador).

## Cálculos por cliente desde la bóveda (P1-06)

`POST /api/v1/clientes/{clave}/calculos/<calculo>` — el mismo cálculo que el endpoint de siempre,
pero **sin `contribuyente` ni `facturas` en el body**: el RFC y el régimen salen de la ficha del
cliente (`datos.regimen`) y los CFDI de `facturas-calculo` del periodo. Se llama al **mismo
handler** que el endpoint original (no hay motor duplicado). Autenticado; cliente de otro despacho
= 404. La respuesta es la del endpoint original más `boveda` (el `resumen` de arriba +
`advertencias`).

| `<calculo>` | Body | Periodo que lee | Igual que |
|---|---|---|---|
| `pre-declaracion` | `periodo_year`, `periodo_month` **o** `periodo_bimestre`, `pagos_provisionales_anteriores`, `ingresos_acumulados_anteriores`, `deducciones_acumuladas_anteriores`, `predial_pagado`, `incluir_explicacion` | el mes/bimestre (+ `relacionados`) | `POST /pre-declaracion` |
| `pre-declaracion-anual` | `periodo_year`, `incluir_explicacion` | el ejercicio (+ `relacionados`) | `POST /pre-declaracion-anual` |
| `diot` | `periodo_year`, `periodo_month`, `incluir_explicacion` | el mes | `POST /diot` |
| `retenciones-terceros` | `periodo_year`, `periodo_month`/`periodo_bimestre` (opcionales), `incluir_explicacion` | el mes/bimestre/ejercicio | `POST /retenciones-terceros` |
| `multi-periodo` | `periodo_year`, `periodos` (meses 1–12), `incluir_explicacion` | el ejercicio (+ `relacionados`) | `POST /multi-periodo` |
| `estado-cuenta` | `periodo_year`, `incluir_explicacion` | el ejercicio (+ `relacionados`) | `POST /estado-cuenta` |

Errores: cliente sin RFC → 422 `"Captura el RFC de este cliente."`; sin régimen → 422 `"Captura
el régimen de este cliente."`; régimen 601 → 400 (como el original, antes de leer la bóveda);
bóveda sin CFDI vigentes del periodo → 400 `"La bóveda de este cliente no tiene CFDI vigentes de
<periodo>. …"`; pre-declaración sin mes ni bimestre → 422.

**Front (P1-06):** los tabs de Fiscalito y Contabilito usan por defecto
`facturas-calculo` (hook `useFuenteFacturas` / `useFacturasDeBoveda` en
`apps/store/src/components/fiscalito/`) y siguen llamando a los endpoints de siempre con
`facturas`; así el Art. 106 de la pre-declaración, que el front arma desde el historial, no
cambia. Los cálculos por cliente quedan disponibles para integraciones y el agente.

## Credenciales del cliente — e.firma y CSD (P0-05)

Autenticadas (`Authorization: Bearer <ID token>`), multi-despacho (cliente de otro despacho =
404) y sólo para los roles `dueno` y `contador` (auxiliar = 403). Cifrado con
`FISCALITO_LLAVE_MAESTRA` (ver `docs/servicios-externos.md`); sin ella en producción, 503.
**Ninguna respuesta trae la llave privada ni la contraseña.**

Forma de una credencial (`metadatos`):

```json
{
  "id": 7, "tipo": "efirma", "rfc": "XAXX010101AB1",
  "numero_certificado": "30001000000500003416",
  "valido_desde": "2026-01-01T00:00:00+00:00", "valido_hasta": "2030-01-01T00:00:00+00:00",
  "dias_para_vencer": 1200, "vencida": false, "por_vencer": false,
  "creado_por": "uid", "creado_en": "2026-10-19T15:00:00+00:00"
}
```

`por_vencer` = vence en menos de 30 días.

### `POST /api/v1/clientes/{clave}/credenciales`

`multipart/form-data`: `tipo` (`efirma` | `csd`), `password`, `cer` (archivo .cer DER),
`key` (archivo .key PKCS#8 DER cifrada). Respuesta `{"exito": true, "credencial": {...}}`.
Si ya había una activa del mismo tipo, queda inactiva.

Errores 422 con mensaje en español: contraseña que no abre la llave, llave que no corresponde
al certificado, RFC del certificado distinto al RFC del cliente (sólo si el cliente tiene RFC),
e.firma subida como CSD o al revés, certificado vencido o aún no vigente, archivo que no es
certificado, archivo > 64 KB.

### `GET /api/v1/clientes/{clave}/credenciales`

`{"exito": true, "credenciales": [ {...}, ... ]}` — sólo las activas.

### `DELETE /api/v1/clientes/{clave}/credenciales/{credencial_id}`

`{"exito": true}`. Destruye la llave y la contraseña cifradas y deja el renglón inactivo
(historial). 404 si la credencial no es de ese cliente.

### Uso interno (no es endpoint)

`app.credenciales.obtener_firmante(db, cliente, tipo)` → objeto con `firmar(bytes)` (SHA256 con
RSA, PKCS#1 v1.5), `firmar_base64`, `certificado_base64`, `rfc`, `numero_certificado`. Lo usan
la descarga masiva del SAT y el PAC. 404 sin credencial, 422 vencida, 503 si la llave maestra
no la abre.

### `GET /health/integraciones` (P0-06)

Fuera de `/api/v1`, sin autenticación. `{"listo_para_produccion": bool, "servicios": [{servicio,
descripcion, variable, implementacion, disponibles, configurado, es_falso}]}`.
## Trabajos en segundo plano (P0-04)

Autenticado (`Authorization: Bearer <ID token>`), multi-tenant: sólo se ven los trabajos con
`despacho_id` del usuario; los de sistema (despacho nulo) nunca. Un auxiliar ve sólo los de sus
clientes asignados. Trabajo o cliente de otro despacho = **404**.

Forma de un trabajo (`TrabajoSalida`):

```json
{ "id": 7, "tipo": "diagnostico.cliente", "estado": "fallido", "cliente": "taller",
  "intentos": 5, "max_intentos": 5, "ejecutar_en": "2026-10-19T15:00:30Z",
  "iniciado_en": "...", "terminado_en": "...", "creado_en": "...",
  "error": "RuntimeError: ...", "resultado": null, "carga": {} }
```

`estado`: `pendiente | corriendo | hecho | fallido | cancelado`. `cliente` es la clave pública.
Fechas en ISO 8601 UTC.

### `GET /api/v1/trabajos`
Query: `cliente` (clave; 404 si no es del despacho), `estado`, `tipo`, `limite` (1–200, 50).
Más reciente primero. → `{"exito": true, "trabajos": [TrabajoSalida]}`. Estado desconocido → 422.

### `GET /api/v1/trabajos/{trabajo_id}`
→ `{"exito": true, "trabajo": TrabajoSalida}`.

### `POST /api/v1/trabajos/{trabajo_id}/reintentar`
Sólo `fallido` o `cancelado` (si no, **409**). Vuelve a `pendiente` con `intentos = 0` y
`ejecutar_en = ahora`. 409 también si ya hay otro trabajo vivo con su misma `clave_unica`.

### `POST /api/v1/trabajos/{trabajo_id}/cancelar`
Sólo `pendiente` (si no, **409**): uno `corriendo` no se corta a media transacción.

### `POST /api/v1/trabajos/clientes/{clave}/diagnostico`
Trabajo de prueba de la ficha del cliente (cuenta sus empleados). Cuerpo opcional
`{"fallar_intentos": n}` (0–10) para verlo fallar y reintentar. Query opcional `ejecutar_en`
(ISO 8601 **con zona**; sin zona → 422). Clave única por cliente: mientras uno esté vivo, otro
POST devuelve el mismo. → **201** `{"exito": true, "trabajo": TrabajoSalida}`.

**Worker:** `python -m app.trabajos.worker [--una-vez] [--pausa 5]`. Reintento con backoff
exponencial (30 s, 60 s, 2 min… techo 1 h) hasta `max_intentos`; un `corriendo` de más de
15 min vuelve a `pendiente`. Tareas recurrentes en `app/trabajos/programacion.py` (hora diaria
en America/Mexico_City o intervalo); la última ranura se guarda en `ejecuciones_programadas`.

---

## Auditoría (P0-07)

Toda escritura autenticada (`POST/PUT/PATCH/DELETE` que pasó por `contexto_actual`) deja un
renglón: el que registra la ruta (`accion` del dominio, p. ej. `trabajo.reintentar`) o, si la
ruta no registró o falló, el del middleware (`accion: "http.<MÉTODO>"`, `entidad_id` = ruta,
`detalle: {"metodo", "ruta", "status"}`). Escrituras anónimas no dejan renglón.

### `GET /api/v1/auditoria`
Sólo roles `dueno` y `contador` (auxiliar → **403**). Query: `usuario` (uid), `cliente` (clave;
incluye clientes ya borrados), `accion` (exacta, o prefijo con `*`: `trabajo.*`), `desde` y
`hasta` (AAAA-MM-DD, días completos en hora de Ciudad de México; `desde > hasta` → 422),
`pagina` (≥1), `por_pagina` (1–200, 50). Más reciente primero.

```json
{ "exito": true, "total": 1, "pagina": 1, "por_pagina": 50,
  "eventos": [ { "id": 1, "fecha": "2026-10-19T15:00:00Z", "uid": "uid-a", "cliente": "taller",
                 "accion": "trabajo.reintentar", "entidad": "trabajo", "entidad_id": "7",
                 "detalle": {"tipo": "diagnostico.cliente"}, "ip": "201.0.0.1" } ] }
```

---

## Descarga masiva del SAT (P1-01, P1-02)

Todas bajo `/api/v1/sat/clientes/{clave}/...`, autenticadas, con `contexto_actual` +
`cliente_o_404` (**cliente de otro despacho = 404**). Leer: cualquier rol que vea al cliente.
Escribir (`PUT config`, `POST descargar`, `POST historica`): sólo `dueno` y `contador`
(auxiliar → 403). Las descargas **encolan**: el SAT puede tardar de minutos a días y el avance
se ve en la bitácora y en la lista de solicitudes. Detalle del servicio y sus códigos en
`docs/servicios-externos.md` §"Descarga masiva del SAT".

### `GET /config` · `PUT /config`
```json
{ "exito": true,
  "config": { "activa": false, "emitidos": true, "recibidos": true, "metadata": true,
              "cancelados": true, "desde": null, "hora": "02:00", "pausada_por": null,
              "ultimo_dia_encolado": null },
  "efirma": { "vigente": true, "valido_hasta": "2030-01-01T00:00:00+00:00", "mensaje": "" },
  "alertas": [ { "id": 1, "tipo": "atorada", "mensaje": "…", "solicitud_id": 7, "creado_en": "…" } ] }
```
`PUT` acepta cualquiera de `activa`, `emitidos`, `recibidos`, `metadata`, `cancelados`, `desde`
(AAAA-MM-DD), `hora` (`HH:MM`, Ciudad de México; inválida → 422) y devuelve lo mismo. Sin
configuración guardada, todo encendido salvo `activa`. Activarla sin e.firma vigente la deja
`pausada_por: "efirma"` con alerta `sin_efirma`; se reanuda sola al subir una e.firma.
Tipos de alerta: `sin_efirma`, `atorada`, `error_sat`, `agotada`.

### `POST /descargar`
`{"desde": "2026-09-01", "hasta": "2026-09-30", "seleccion"?: {"emitidos", "recibidos",
"metadata", "cancelados"}}` (sin `seleccion` usa la de la config). Un trabajo por mes del rango
(clave única: pedirlo dos veces no duplica). `desde > hasta`, más de 366 días o un día futuro →
422. Sin e.firma vigente → **409** con el motivo.
```json
{ "exito": true, "encolados": [ {"trabajo_id": 12, "inicio": "2026-09-01", "fin": "2026-09-30"} ] }
```

### `POST /historica`
`{"desde": "2024-01-01", "hasta"?: "…", "seleccion"?: {…}}` — `hasta` default ayer. Un trabajo
por mes; más de 72 meses → 422 (el SAT guarda seis años). Misma respuesta que `/descargar`.

### `GET /solicitudes?estado&pagina&por_pagina`
Paginado (`por_pagina` 1–100, default 20), más reciente primero.
```json
{ "exito": true, "total": 16, "pagina": 1, "por_pagina": 20,
  "solicitudes": [ { "id": 7, "direccion": "emitidos", "tipo": "cfdi", "estado_comprobante": "todos",
    "fecha_inicial": "2026-09-01T00:00:00", "fecha_final": "2026-09-30T23:59:59",
    "rfc_contraparte": "", "tipo_comprobante": "", "origen": "diaria|manual|historica|division",
    "padre_id": null, "id_solicitud": "4e80…", "estado": "terminada", "codigo": "5000",
    "mensaje": "Terminada: 120 XML nuevos en la bóveda, 3 ya existían.", "numero_cfdis": 1,
    "paquetes": 1, "paquetes_procesados": 1, "xml_importados": 120, "duplicados": 3,
    "rechazados": 0, "metadata_registros": 0, "veces_solicitada": 1, "verificaciones": 3,
    "intentos": 0, "proxima_verificacion": null, "solicitada_en": "…", "terminada_en": "…",
    "creado_en": "…" } ] }
```
`estado`: `pendiente` · `solicitada` · `en_proceso` · `descargando` · `terminada` · `sin_datos`
(el SAT respondió 5004) · `fallida` · `dividida` (rebasó el tope 5003 y se partió en hijas con
`padre_id`). `mensaje` siempre en español.

### `GET /bitacora?anio=2026&mes=9`
Un renglón por día del mes, para el calendario:
```json
{ "exito": true, "anio": 2026, "mes": 9, "dias": [
  { "fecha": "2026-09-01", "estado": "completo", "solicitudes": 2, "emitidos": 14,
    "recibidos": 0, "metadata": 14, "cancelados": 1, "mensaje": "" } ] }
```
`estado`: `completo` · `en_proceso` · `sin_movimientos` · `fallido` · `no_solicitado`. Manda el
peor de las solicitudes que cubren el día (las `dividida` no cuentan: las cubren sus hijas).
`emitidos`/`recibidos` cuentan la bóveda por `Fecha` del CFDI; `metadata`/`cancelados`, la
metadata del SAT por `FechaEmision`.
## Verificación SAT — estatus de CFDI, listas 69-B y opinión de cumplimiento (P1-03/04/05)

Autenticado; todo lo de `/sat/clientes/{clave}/…` pasa por `contexto_actual` + `cliente_o_404`
(cliente de otro despacho = **404**). Las consultas al SAT corren en la cola de trabajos: las
rutas que consultan **encolan** y devuelven `{"trabajo": {"id", "tipo", "estado"}}`; el avance
se ve en `GET /api/v1/trabajos?cliente=…&tipo=…`. Servicios y variables en
`docs/servicios-externos.md`.

### `POST /api/v1/sat/clientes/{clave}/verificar-estatus`

Body `{"desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD"}` (inclusivos, sobre `Fecha` del CFDI;
`desde > hasta` o más de cinco años → 422). Encola `sat.verificar_estatus` para los CFDI **no
cancelados** del rango (la misma petición viva no se duplica). Respuesta
`{"exito": true, "trabajo": {...}, "comprobantes": 42}`. El trabajo procesa en lotes y deja
`{"consultados", "vigentes", "cancelados", "nuevos_cancelados", "no_encontrados",
"en_proceso", "errores", "pendientes"}` en su `resultado`. Un cancelado queda
`estatus_sat = "cancelado"` en la bóveda y **deja de contar**: los cálculos usan
`app.boveda_cfdi.servicio.comprobantes_vigentes(consulta)` (uso interno).

### `GET /api/v1/sat/listas/estado`

Datos públicos (no dependen del despacho). `{"exito": true, "listas": [{"lista": "69b",
"descripcion", "registros", "cargada_en", "revisada_en", "url", "error"}]}`.

### `GET /api/v1/sat/clientes/{clave}/riesgos-69b`

```json
{ "exito": true, "en_rojo": 1,
  "riesgos": [{ "rfc": "EFO010101AA1", "nombre": "…", "lista": "69b", "situacion": "definitivo",
    "situacion_texto": "Definitivo", "relacion": "proveedor", "nivel": "alto", "rojo": true,
    "comprobantes": 2, "total": "2320.00", "fecha_publicacion_sat": "2026-05-10",
    "fecha_publicacion_dof": "2026-05-15" }],
  "alertas": [{ "id": 1, "tipo": "art69b", "rfc": "…", "nombre": "…", "lista": "69b",
    "situacion": "definitivo", "relacion": "proveedor", "nivel": "alto", "atendida": false,
    "creada_en": "…", "detalle": {"comprobantes": 2, "total": "2320.00"} }],
  "listas": [ … como /sat/listas/estado … ] }
```

`relacion`: `proveedor` (emisor de recibidos), `cliente` (receptor de emitidos; nunca rojo) o
`propio`. `situacion` 69-B: `definitivo` (alto) · `presunto` (medio) · `desvirtuado` y
`sentencia_favorable` (info, no rojo, no alertan).

### `POST /api/v1/sat/clientes/{clave}/alertas/{alerta_id}/atender`

Marca la alerta como atendida. `{"exito": true}`; 404 si no es de ese cliente.

### `GET /api/v1/sat/clientes/{clave}/opinion` · `GET /api/v1/sat/clientes/{clave}/constancia`

```json
{ "exito": true, "tipo": "opinion", "semaforo": "verde",
  "ultimo": { "id": 4, "tipo": "opinion", "fecha": "2026-10-03", "resultado": "positiva",
    "folio": "26NA…", "origen": "falso", "lectura": "pdf", "tamano": 900,
    "creado_en": "…", "aviso": null },
  "historial": [ … ], "via": "falso", "dias_vigencia": 30,
  "config": { "automatico": true, "dia_del_mes": 1, "constancia": true } }
```

`semaforo`: `verde` (positiva o sin obligaciones, ≤ `dias_vigencia` días) · `amarillo` (más
vieja o sentido desconocido) · `rojo` (negativa) · `gris` (sin opinión). `resultado`:
`positiva|negativa|sin_obligaciones|desconocido` (la constancia siempre `desconocido`).
`origen`: `falso|portal_sat|proveedor|manual`. `lectura`: `adaptador|pdf|manual|sin_lectura`.
`aviso`: texto si el RFC del PDF no es el del cliente. `via`: la vía configurada.

### `POST /api/v1/sat/clientes/{clave}/opinion/obtener?tipo=opinion|constancia`

"Obtener ahora": encola `sat.cumplimiento_obtener`. **409** si la vía es `manual`; **422** si el
cliente no tiene RFC. Con `portal_sat`, el trabajo falla con mensaje si el cliente no tiene
e.firma (404) o si el portal cambió (502).

### `POST /api/v1/sat/clientes/{clave}/opinion/pdf`

`multipart/form-data`: `archivo` (PDF ≤ 10 MB), `tipo` (`opinion` default | `constancia`),
`resultado` opcional (lo indica el despacho si el PDF no se lee). Funciona con cualquier vía.
`{"exito": true, "documento": {...}, "semaforo": "rojo" | null}`. El mismo PDF dos veces es
un solo documento. No-PDF → 422.

### `GET /api/v1/sat/clientes/{clave}/opinion/{doc_id}/pdf`

El PDF guardado (opinión o constancia), `application/pdf`, verificado contra su SHA-256.

### `PUT /api/v1/sat/clientes/{clave}/opinion/config`

Body `{"automatico": true, "dia_del_mes": 1-28, "constancia": true}`. Programación mensual del
cliente (default: automático el día 1, con constancia).

### `GET /api/v1/sat/cartera/semaforo`

Por cada cliente visible: `{"clave", "opinion": {"semaforo", "resultado", "fecha"},
"riesgos_69b": <alertas alto/medio sin atender>}`.

### Programación (worker)

`sat_estatus_mes` diario 2:00 (CFDI del mes) · `sat_estatus_anio` semanal (último año) ·
`sat_listas` diario 6:30 · `sat_cumplimiento` diario 7:00 (encola a quien le toca su día).
Hora de Ciudad de México.

## Contabilidad — catálogo, pólizas automáticas, pólizas y balanza (P2-01/02/03/04)

Autenticado; todo lo de `/contabilidad/clientes/{clave}/…` pasa por `contexto_actual` +
`cliente_o_404` (cliente de otro despacho = **404**). Los ids de cuenta, regla y póliza se
buscan junto con el cliente: un id de otro cliente es **404**. Importes como texto con dos
decimales (`"1160.00"`), en pesos. Código en `apps/api/app/contabilidad/`; esquemas de asiento
en `asientos.py`.

### `GET /api/v1/contabilidad/codigo-agrupador`

El código agrupador del SAT completo (Anexo 24, 1080 códigos) con su fuente:
`{"fuente", "codigos": [{"codigo", "nivel" (0 encabezado | 1 | 2), "nombre", "naturaleza",
"tipo", "nota"}]}`. Fuente versionada en `app/contabilidad/datos/codigo_agrupador.csv`.

### Catálogo (P2-01)

- `GET …/cuentas` → `{"cuentas": [{"id", "numero", "nombre", "nivel", "naturaleza", "tipo",
  "padre_id", "codigo_agrupador", "afectable"}]}` ordenadas por número.
- `POST …/cuentas/sembrar` → `{"creadas": n}`. Agrega las cuentas del catálogo base que falten
  (idempotente; no toca las existentes).
- `POST …/cuentas` (201) body `{"numero", "nombre", "codigo_agrupador", "padre_id"?, "nivel"?,
  "naturaleza"?, "tipo"?}`. El nivel lo dicta el padre (uno incoherente → 422); naturaleza y tipo
  se heredan del padre o del agrupador. Agrupador inexistente o encabezado → 422; número repetido
  → 409; subcuenta a una cuenta con movimientos o saldo inicial → 409. El padre deja de ser
  afectable.
- `PATCH …/cuentas/{cuenta_id}` body `{"numero"?, "nombre"?, "codigo_agrupador"?,
  "naturaleza"?, "tipo"?}`. Renumerar una cuenta que usa la configuración → 409.
- `DELETE …/cuentas/{cuenta_id}`. Con subcuentas, con movimientos o usada por la configuración
  (default o personalizada) o por una regla → 409.

### Configuración de pólizas automáticas (P2-02)

- `GET …/config` → `{"config": {"automatica_ingresos", "automatica_egresos",
  "automatica_pagos", "automatica_nomina", "pue_registra_cobro", "uso_s01_no_deducible",
  "efectivo_no_deducible", "tope_activo", "plantilla_concepto", "fecha_saldos_iniciales",
  "cuentas" (rol → número, con defaults), "cuentas_personalizadas", "roles": [{"rol",
  "default", "descripcion"}], "formas_pago" (c_FormaPago → número), "reglas": [...]}}`.
- `PUT …/config` body con cualquiera de esos campos (excepto `roles`, `reglas` y
  `cuentas_personalizadas`; `cuentas` sustituye las personalizadas). Cada cuenta debe existir y
  ser afectable (422). `fecha_saldos_iniciales` debe ser día 1.
- `POST …/reglas` (201) body `{"criterio": "rfc"|"clave"|"prefijo"|"uso"|"descripcion",
  "valor", "cuenta_numero", "prioridad" (menor primero, default 100), "activa"}`;
  `PATCH …/reglas/{regla_id}`; `DELETE …/reglas/{regla_id}`. Aplican a las pólizas NUEVAS.

### Pólizas (P2-03)

- `POST …/polizas/generar` body `{"desde", "hasta", "segundo_plano"?}`. Genera las pólizas
  automáticas de los CFDI **vigentes** de la bóveda del rango que no tengan póliza (idempotente
  por UUID; una póliza cancelada a mano no se regenera) y cancela/revierte las de CFDI ya
  cancelados. Hasta 62 días corre en el request → `{"en_segundo_plano": false, "resultado":
  {"generadas", "ya_existian", "omitidas", "canceladas", "revertidas", "errores": [{"uuid",
  "error"}], "omitidas_detalle"}}`; más largo o `segundo_plano: true` encola
  `contabilidad.generar_polizas` → `{"en_segundo_plano": true, "trabajo": {...}}`. Sin catálogo
  → 409. Rango > 5 años → 422.
- `GET …/polizas?desde&hasta&tipo&origen&estado&uuid&texto&pagina&por_pagina` →
  `{"total", "pagina", "por_pagina", "polizas": [{"id", "folio" ("D-2026-03-0001"), "tipo",
  "numero", "fecha", "concepto", "origen" (automatica|manual), "estado" (activa|cancelada),
  "uuid_cfdi", "tipo_cfdi", "total_cargos", "total_abonos", "diferencia" (total del CFDI − lo
  contabilizado contra la contraparte), "advertencias", "editada", "reversa_de_id",
  "motivo_cancelacion", "cancelada_en"}]}`.
- `GET …/polizas/{poliza_id}` → la póliza con `"movimientos": [{"id", "cuenta_id", "cuenta",
  "nombre_cuenta", "concepto", "cargo", "abono", "uuid", "rfc"}]`.
- `POST …/polizas` (201) body `{"tipo", "fecha", "concepto", "movimientos": [{"cuenta_id",
  "cargo", "abono", "concepto"?, "uuid"?, "rfc"?}]}` (≥ 2). Cada movimiento lleva cargo o abono
  (no los dos), cuentas afectables del cliente, Σ cargos = Σ abonos; si no → 422. Periodo
  cerrado → 409. Folio consecutivo por tipo y mes.
- `PATCH …/polizas/{poliza_id}` body `{"fecha"?, "concepto"?, "movimientos"?}` (mismas
  validaciones; la fecha no puede salir del mes). Cancelada o periodo cerrado → 409.
- `POST …/polizas/{poliza_id}/cancelar` body `{"motivo"}`. Periodo cerrado → 409.
- `GET …/periodos-cerrados` → `{"periodos": [{"anio", "mes", "cerrado_en", "cerrado_por"}]}`.
  **P2-08 retiró `POST …/periodos-cerrados` y `DELETE …/periodos-cerrados/{anio}/{mes}`**:
  cerrar y reabrir van por `…/periodos/{anio}/{mes}/cerrar|reabrir` (con validación, motivo,
  rol y bitácora). Un mes cerrado no acepta pólizas nuevas, ediciones ni
  cancelaciones. Las pólizas con `origen` `cierre` o `apertura` (cierre anual) no se editan ni
  se cancelan a mano (409). Un CFDI cancelado ante el SAT cuya póliza cae en mes cerrado genera una póliza
  de **reversa** con fecha del día (P1-03 lo hace al detectar la cancelación).

### Balanza, auxiliar y saldos iniciales (P2-04)

- `GET …/balanza?desde&hasta&nivel&solo&incluir_cierre` (`solo`: `con_saldo_o_movimiento` default |
  `con_movimiento` | `todas`) → `{"renglones": [{"cuenta_id", "numero", "nombre", "nivel",
  "naturaleza", "tipo", "afectable", "codigo_agrupador", "padre_id", "saldo_inicial",
  "saldo_final" (con signo: deudor +), "inicial_deudor", "inicial_acreedor", "cargos", "abonos",
  "final_deudor", "final_acreedor"}], "totales": {...}, "cuadra", "diferencias":
  {"saldo_inicial", "movimientos", "saldo_final"}}`. Sólo pólizas activas. Saldo inicial =
  movimientos anteriores a `desde` + saldos iniciales capturados. Las cuentas acumulativas suman
  a sus subcuentas. P2-08: la póliza de apertura fechada en `desde` cuenta como saldo inicial;
  las pólizas de cierre/apertura dentro del rango sólo cuentan con `incluir_cierre=true`
  (balanza de cierre). El auxiliar acepta el mismo `incluir_cierre`.
- `GET …/cuentas/{cuenta_id}/auxiliar?desde&hasta` → `{"cuenta", "saldo_inicial", "cargos",
  "abonos", "saldo_final", "movimientos": [{"poliza_id", "folio", "fecha", "tipo_poliza",
  "concepto", "cuenta", "cargo", "abono", "saldo" (corrido), "uuid", "rfc",
  "xml_disponible"}], "truncado"}` (máx. 5,000 movimientos). Incluye las subcuentas. El XML se
  baja con `GET /api/v1/boveda/clientes/{clave}/cfdi/{uuid}/xml`.
- `GET …/saldos-iniciales` → `{"saldos": [{"cuenta_id", "numero", "nombre", "deudor",
  "acreedor"}]}`; `PUT …/saldos-iniciales` body `{"saldos": [{"cuenta_id", "deudor",
  "acreedor"}]}` (0 y 0 lo quita; cuenta no afectable → 422) → `{"totales": {"deudor",
  "acreedor", "cuadra"}, "saldos"}`.
## Impuestos del cliente y calculadoras (P3-02, P3-03, P3-07, P3-08)

Motor: `app/fiscal_engine/{actualizacion,inpc,iva,isn,resumen_impuestos,calculadoras_laborales}.py`;
lectura de la bóveda en `app/impuestos/`. Todo autenticado (`contexto_actual`); las rutas con
`{clave}` usan `cliente_o_404` (otro despacho = 404). Importes en las respuestas como texto con
dos decimales. Fuentes y `FUENTE POR CONFIRMAR` en los docstrings y en `fiscal_engine/datos/*.csv`.

**`por_confirmar` (O12).** Toda respuesta que usa un INPC sin cotejar con el boletín del INEGI,
una tasa de recargos de fuente secundaria (LIF 2020-2025) o una tasa de ISN no verificada trae
`por_confirmar: true` y, donde aplica, `fuentes_por_confirmar: [texto]` (una línea por índice o
tasa). La marca sale de la columna `verificacion` de cada CSV (`boletin_inegi`, `ley`,
`ley_citada` = verificado).

### `GET|PUT /api/v1/impuestos/clientes/{clave}/config`

Criterio del despacho por cliente (DP-3): `modo_factor` (`truncar`|`redondear`|`sin_redondeo`,
default `truncar`), `tipo_recargo` (default `mora`), `tope_meses_recargos` (60),
`region_fronteriza` (false), `proporcion_iva_modo` (`calculada`|`fija`) + `proporcion_iva_fija`,
`asignacion_iva` (UUID → `gravado`|`exento`|`indistinto`), `isn_aplicar_adicional` (true),
`isn_claves_excluidas`, `isn_claves_incluidas`, `saldo_favor_iva_inicial`,
`iva_no_objeto_excluidos` (UUID de CFDI emitidos cuyo valor no objeto no entra a la proporción
del IVA: no es acto del Art. 4o.-A o es concepto del Art. 5o.-C, p. ej. dividendos; default
vacío = todo el no objeto entra). Veracruz: los premios de puntualidad (010) y asistencia (049)
gravan salvo que sean anuales; si lo son, se excluyen con `isn_claves_excluidas`.

### `POST /api/v1/impuestos/clientes/{clave}/resumen`

Body `{"anio", "mes", "fecha_pago", "fecha_limite"?, "capturas": {<clave>: {"importe_a_pagar"?,
"subsidio", "compensaciones"}}, "formato": "json"|"xlsx"|"csv"}`. Sin `fecha_limite`: día 17
del mes siguiente corrido a hábil (Art. 12 CFF; sin prórroga por sexto dígito). Respuesta JSON:
`{"renglones": [{"clave", "grupo", "concepto", "aplica", "importe_sistema", "importe_a_pagar",
"actualizacion", "recargos", "subsidio", "compensaciones", "total", "capturado", "nota",
"factor", "meses_recargo", "por_confirmar"}], "totales", "total_a_pagar_ajustado",
"fecha_limite", "notas", "por_confirmar", "fuentes_por_confirmar"}`.
Claves: `isr_pm`, `isr_pf_empresarial`, `isr_arrendamiento`, `isr_plataformas`,
`isr_resico_pf`, `isr_resico_pm`, `ret_isr_salarios`, `ret_isr_asimilados`,
`ret_isr_honorarios`, `ret_isr_arrendamiento`, `ret_isr_resico`, `iva_a_cargo`, `iva_retenido`.
`subsidio` sólo en `ret_isr_salarios` (422 en otro). `xlsx`/`csv` devuelven el archivo.

### `POST /api/v1/impuestos/clientes/{clave}/iva`

Body `{"anio", "meses": [1..12], "saldo_favor_inicial"?, "opciones_saldo": {mes:
"acreditar"|"devolucion"|"compensacion"}}`. Lee `comprobantes_vigentes` por flujo de efectivo
(PUE en su mes, PPD por complemento de pago). Devuelve `{"meses": [ResultadoIVAMes]}` con
valor de actos por tasa, `valor_no_objeto` y `valor_no_objeto_en_proporcion` (actos del Art.
4o.-A que entran al denominador), proporción (Art. 5o. fr. V c), acreditable, saldo a favor anterior /
aplicado / siguiente (Art. 6o.), IVA retenido a terceros y `notas`.

### `GET /api/v1/impuestos/clientes/{clave}/isn?anio&mes`

ISN del mes con los CFDI de nómina emitidos (por `FechaPago`) y la `clave_entidad` del cliente.

## Personas morales y anual del cliente (P3-01, P3-06)

Router `app/routes/impuestos_anual.py`; motor `app/fiscal_engine/personas_morales.py` (601 y
RESICO PM) y `anual_pf.py` (PF); fuentes en `apps/api/knowledge_base/16_personas_morales.md`.
Persona moral = régimen `601`, o `626` con RFC de 12 caracteres (RESICO PM). Las rutas `/pm/*`
dan **422** si el cliente no lo es; cliente de otro despacho = **404**. En el resumen de
impuestos, `isr_pm` / `isr_resico_pm` traen ya el pago provisional del mes (antes en cero).

### `GET|PUT /api/v1/impuestos/clientes/{clave}/pm/datos/{anio}`

`DatosAnualesPMSchema` (tabla `datos_anuales_pm`, por cliente y ejercicio; sin renglón rigen
los defaults): `coeficiente_utilidad` (el que se aplica en ese ejercicio; null = calcularlo con
`utilidad_fiscal_base`/`ingresos_nominales_base` o con la anual del sistema de hasta cinco
ejercicios atrás), `anticipos_miembros_base`, `ptu_pagada` + `mes_pago_ptu` (5), `perdidas`
`[{ejercicio, remanente, actualizada_a: "AAAA-MM"|null}]`, `retenciones_bancarias` y
`pagos_efectuados` (`{mes: importe}`), `saldos_creditos`/`saldos_deudas` (12 saldos de fin de
mes si no hay contabilidad), `cuentas_creditos`/`cuentas_deudas`/`cuentas_no_deducibles`
(prefijos de código agrupador), `deduccion_inversiones`, `deducciones_adicionales`,
`no_deducibles_adicionales`, `ingresos_adicionales`, `estimulos` `[{concepto, importe,
fundamento, desde_mes, en_provisionales}]`, `fuente` (`auto`|`contabilidad`|`boveda`),
`factor_exentos_nomina` (0.47), `aai_en_resico` (false), `no_deducibles_art28_xxx` (null =
derivarlo: de `cuentas_art28_xxx` con contabilidad, de la nómina de la bóveda sin ella),
`cuentas_art28_xxx` (cuentas donde el despacho registra el no deducible del Art. 28 fr. XXX;
también dejan de deducirse). Respuesta `{"anio", "datos"}`.

### `POST /api/v1/impuestos/clientes/{clave}/pm/pagos-provisionales`

Body `{"anio", "mes"}`. Pagos de enero a `mes`: 601 por el Art. 14 LISR (coeficiente × ingresos
nominales acumulados − PTU en octavos de mayo a diciembre − estímulos − pérdidas, × 30 %, −
pagos anteriores − retenciones Art. 54); RESICO PM por el Art. 211 (cobrado − pagado − PTU −
pérdidas). Respuesta `{"tipo": "pm"|"resico_pm", "fuente", "coeficiente",
"origen_coeficiente", "tasa", "fecha_limite", "pagos": [{"mes", "ingresos_mes",
"ingresos_acumulados", "deducciones_acumuladas", "coeficiente", "utilidad_estimada",
"ptu_disminuida", "estimulos", "perdidas", "base", "isr_causado", "pagos_anteriores",
"retenciones", "pago_determinado", "pago_efectuado", "pago_capturado", "a_pagar_pesos",
"por_confirmar"}], "notas", "por_confirmar", "fuentes_por_confirmar"}`.

### `POST /api/v1/impuestos/clientes/{clave}/anual` · `POST .../anual/papeles`

Body `{"anio", "pagos_provisionales"?: {mes: importe}}` (sólo PF: pagos realmente
presentados; la PM los captura en sus datos). Régimen 612/606/625/626 (PF) → `{"tipo": "pf",
"renglones", "meses": [{"mes", "ingresos", "deducciones", "base", "isr_causado",
"retenciones", "pago_determinado", "pago_efectuado", "pago_capturado"}], "notas"}`. 601 y
RESICO PM → `{"tipo": "pm"|"resico_pm", "fuente", "renglones", "meses": [{"mes", "ingresos",
"deducciones", "no_deducibles", "retenciones", "pago_provisional"}], "ajustes", "cuentas",
"pagos_provisionales", "coeficiente": {"aplicado", "origen", "siguiente", "utilidad_fiscal",
"ingresos_nominales", "anticipos_miembros"}, "aai": {saldos, promedios, factor, acumulable,
deducible}|null, "origen_saldos", "ptu": {"utilidad_antes_ptu", "no_deducibles_art28_xxx",
"origen_art28_xxx": "capturado"|"contabilidad"|"boveda"|"sin dato", "renta_gravable"
(Art. 9 cuarto párrafo), "porcentaje", "fundamento", "a_repartir", "pagada_en_el_ejercicio"},
"perdidas", "notas", "por_confirmar", "fuentes_por_confirmar"}`. Los factores INPC (`aai.factor`,
`perdidas[].factores[]`) traen `por_confirmar` y `fuentes_por_confirmar`. Cada renglón: `{"clave", "concepto",
"importe", "fundamento"}`. Otro régimen → 422. `/anual/papeles` devuelve el `.xlsx` (hojas PF:
Cálculo ISR, Mes a mes, Notas; PM: Cálculo ISR, Ingresos, Deducciones, Ajuste por inflación,
Coeficiente [601], PTU, Pérdidas, Pagos provisionales, Notas) armado del MISMO diccionario.

### `POST /api/v1/calculadoras/actualizacion-recargos`

Body `{"monto", "fecha_limite", "fecha_pago", "tipo_recargo"?, "modo_factor"?, "tope_meses"?}`.
Respuesta: `factor` (INPC usados, cortado y sin cortar), `monto_actualizado`, `actualizacion`,
`meses`, `tasa_acumulada`, `recargos`, `total`, `total_a_pagar_ajustado` (Art. 20 CFF),
`detalle_meses`, `notas`, `inpc_ultimo_publicado`, `por_confirmar`, `fuentes_por_confirmar`
(también dentro de `factor`).

### `GET /api/v1/calculadoras/fecha-limite?anio&mes`

`{"fecha_limite"}`.

### `POST /api/v1/calculadoras/isn` · `GET /api/v1/calculadoras/isn/tasas?fecha`

Con `{"cliente", "anio", "mes"}` usa la bóveda (igual que el módulo); sin cliente,
`{"entidad", "fecha", "percepciones": [{"clave", "importe"}] | "total_erogaciones",
"aplicar_adicional", "claves_excluidas"}`. Respuesta: `tasa`, `adicional_sobre_impuesto`,
`fundamento`, `fuente`, `por_confirmar`, `base`, `impuesto`, `adicional`, `total`,
`detalle_exclusiones`, `notas`. `/isn/tasas`: las 32 entidades.

### `POST /api/v1/calculadoras/isr-sueldos` · `isr-resico` · `aguinaldo` · `ptu` · `finiquito`

- `isr-sueldos`: `{"base_gravable", "clave_periodicidad", "fecha_pago",
  "ingreso_gravado_mensual"?, "dias_periodo", "es_trabajador_de_salario_minimo"}` →
  `isr_causado`, `subsidio`, `subsidio_acreditado`, `isr_retenido` (motor de nómina).
- `isr-resico`: `{"ingresos_cobrados", "isr_retenido"}` → `tasa`, `isr_causado`, `isr_a_pagar`.
- `aguinaldo`: `{"salario_diario", "dias_aguinaldo", "dias_trabajados_en_el_anio",
  "fecha_pago"}` → `importe`, `partidas` (exento/gravado), `isr`, `neto`.
- `ptu`: `{"utilidad_repartible", "dias_trabajador", "salario_trabajador", "total_dias_todos",
  "total_salarios_todos", "salario_diario", "promedio_ptu_3_anios", "fecha_pago"}`.
- `finiquito`: `{"salario_diario", "fecha_ingreso", "fecha_baja", "tipo":
  "renuncia"|"despido_injustificado", ...}` → `partidas`, `separacion`, `isr`, `neto`.
  Aguinaldo/PTU/finiquito son versión mínima: P4 las reemplaza con `nomina_engine`.

### Reportes contables (P2-05)

Mismas reglas de tenencia. Filtros comunes (query): `desde`, `hasta` (obligatorios), `nivel`
(1–10), `solo` (`con_saldo_o_movimiento` | `con_movimiento` | `todas`), `agrupar` (`cuenta` |
`agrupador`: por código agrupador del SAT), `moneda` (default `MXN`), `tipo_cambio` (MXN por 1
unidad; **obligatorio si `moneda` ≠ MXN**, 422 si falta: el sistema no guarda tipos de cambio),
`idioma` (`es` | `en`: etiquetas), `comparar` (`ninguno` | `periodo_anterior` |
`anio_anterior`), `incluir_cierre` (bool).

- `GET …/reportes/estado-resultados` → `{"reporte", "titulo", "cliente", "desde", "hasta",
  "moneda", "tipo_cambio", "idioma", "comparativo": {"tipo", "desde", "hasta"} | null,
  "columnas": [{"clave", "etiqueta"}] (`importe`, `acumulado` del 1-ene a `hasta`, y con
  comparativo `comparativo`, `variacion`), "lineas": [{"tipo": "encabezado" | "cuenta" |
  "subtotal" | "total", "clave", "etiqueta", "nivel", "numero"?, "cuenta_id"?, "valores"?}],
  "resumen": {"ingresos", "costo", "utilidad_bruta", "gastos", "utilidad_operacion",
  "utilidad_antes_impuestos", "utilidad_neta", "utilidad_neta_acumulada"}}`. Importes =
  movimiento del periodo (cargos − abonos) de las cuentas de resultados, presentados en
  positivo según su naturaleza.
- `GET …/reportes/balance-general` → misma forma (columnas `importe` = saldo final a `hasta`,
  y `comparativo`/`variacion`), `"resumen": {"activo", "pasivo", "capital", "resultado",
  "resultados_sin_cierre", "pasivo_mas_capital", "cuentas_de_orden"}, "cuadra", "diferencia"`.
  Cuadre: activo = pasivo + capital + resultado del ejercicio.
- Clasificación por el primer segmento del código agrupador de cada cuenta: 101–149 activo
  circulante, 150–199 no circulante, 201–249 pasivo corto plazo, 250–299 largo plazo, 3xx
  capital, 401–402 ingresos, 5xx costo, 6xx gastos (611 → impuestos a la utilidad), 403/702/704
  otros ingresos y productos financieros, 701/703 gastos financieros y otros gastos, 8xx orden.
- `GET …/reportes/polizas?desde&hasta&estado` → `{"total", "truncado", "polizas": [póliza con
  "movimientos"]}` (máx. 2,000; para imprimir).
- `GET …/reportes/excel?reporte=balanza|auxiliar|estado_resultados|balance_general|polizas&…`
  (+ `cuenta_id` para `auxiliar`, 422 si falta) → archivo `.xlsx` (openpyxl) con importes
  numéricos en formato `#,##0.00` y sus totales. El PDF se arma en el front (jspdf) con la
  misma respuesta JSON.

### Cierre de periodo y de ejercicio (P2-08)

- `GET …/periodos/{anio}` → `{"anio", "meses": [{"mes", "estado": "abierto" | "cerrado",
  "cerrado_en", "cerrado_por", "polizas"}], "historial": [{"mes" (0 = ejercicio), "accion":
  "cerrar" | "reabrir" | "cierre_anual" | "deshacer_cierre_anual", "motivo", "uid", "fecha"}],
  "cierre_anual": {"hecho", "polizas"}}`.
- `GET …/periodos/{anio}/{mes}/validacion` → `{"desde", "hasta", "balanza_cuadra",
  "diferencias", "cfdi_sin_poliza": [{"uuid", "fecha", "tipo", "direccion", "rfc", "total",
  "moneda"}] (máx. 200), "total_cfdi_sin_poliza", "se_puede_cerrar"}`. CFDI sin póliza =
  vigentes del mes (sin traslados ni nómina recibida) sin póliza que los cite.
- `POST …/periodos/{anio}/{mes}/cerrar` body `{"forzar"?: false, "motivo"?}` →
  `{"validacion"}`. Balanza descuadrada → 409 (no se fuerza). CFDI sin póliza → 409 salvo
  `forzar: true` con motivo (≥ 5 caracteres, si no 422). Ya cerrado → 409.
- `POST …/periodos/{anio}/{mes}/reabrir` body `{"motivo"}` (≥ 5, si no 422). Sólo rol `dueno`
  o `contador` (auxiliar → 403). No cerrado → 404.
- `GET …/cierre-anual/{anio}/validacion` → misma forma, sobre el ejercicio (desde la fecha de
  saldos iniciales si la contabilidad arrancó ese año).
- `POST …/cierre-anual/{anio}` body `{"traspasar_resultado"?: false, "forzar"?: false,
  "motivo"?}` → `{"anio", "resultado" (utilidad +), "tipo_resultado": "utilidad" | "perdida",
  "polizas", "validacion"}`. Genera tres pólizas de diario: cierre de resultados (31-dic,
  contra 305.01/305.02), cierre de balance (31-dic) y apertura (1-ene siguiente; con
  `traspasar_resultado` el resultado abre en 304.01/304.02). Cuentas por rol
  `resultado_utilidad`, `resultado_perdida`, `utilidad_anteriores`, `perdida_anteriores`
  (configurables). Cierra los doce meses. Mismas validaciones que el mensual; ya cerrado o
  enero siguiente cerrado → 409.
- `POST …/cierre-anual/{anio}/deshacer` body `{"motivo"}` → `{"canceladas"}`. Dueño o contador;
  cancela las tres pólizas (si enero siguiente sigue abierto) y reabre diciembre.

## Conciliación bancaria (P2-06)

Autenticado; todo `/api/v1/conciliacion/clientes/{clave}/…` pasa por `contexto_actual` +
`cliente_o_404` (otro despacho = **404**). Ids de cuenta bancaria, plantilla, movimiento y
conciliación se buscan junto con el cliente. Importes como texto con dos decimales. Código en
`apps/api/app/contabilidad/conciliacion/`.

- `GET /api/v1/conciliacion/bancos` → `{"bancos": [{"clave" (c_Banco), "nombre"}]}`: bancos
  con lector de PDF (diseños **POR CONFIRMAR CON PDF REAL**).
- Cuentas bancarias: `GET …/cuentas` · `POST …/cuentas` (201) body `{"banco" (3 dígitos
  c_Banco), "nombre", "numero", "clabe" (18 dígitos o ""), "moneda", "cuenta_contable_id"
  (afectable; si no, 422), "ventana_dias" (0–31, default 3), "umbral" (50–100, default 60),
  "activa"}` · `PATCH …/cuentas/{id}` · `DELETE …/cuentas/{id}` (409 si ya tiene estados
  importados). Cada cuenta: `{"id", "banco", "nombre", "numero", "clabe", "moneda",
  "cuenta_contable_id", "cuenta_contable", "ventana_dias", "umbral", "activa"}`.
- Plantillas de columnas: `GET …/plantillas` · `PUT …/plantillas` body `{"nombre", "banco",
  "formato": "csv"|"xlsx", "mapeo": {"fecha", "concepto", "referencia", "cargo", "abono",
  "importe", "saldo", "formato_fecha", "fila_encabezado", "separador", "signo_importe", "hoja"}}`
  (crea o reemplaza por nombre; columna por encabezado, letra o número) · `DELETE
  …/plantillas/{id}`.
- `POST …/cuentas/{id}/estados` multipart `archivo` + opcionales `formato`
  (`csv|xlsx|ofx|pdf`; si no, por extensión/contenido), `plantilla_id`, `mapeo` (JSON que se
  encima a la plantilla) → `{"estado": {"id", "archivo", "formato", "desde", "hasta",
  "saldo_inicial", "saldo_final", "nuevos", "duplicados", "advertencias"}, "banco_pdf"}`.
  Reimportar no duplica (huella por renglón). PDF ilegible/banco desconocido → 422 que
  sugiere plantilla CSV/XLSX. `GET …/cuentas/{id}/estados` lista los importados.
- `GET …/cuentas/{id}/movimientos?desde&hasta&incluir_cfdi=true` → `{"cuenta", "banco":
  [{"clave": "b:<id>", "id", "fecha", "concepto", "referencia", "cargo", "abono", "saldo",
  "conciliacion_id"}], "libros": [{"clave": "p:<id>"|"c:<id>", "id", "origen":
  "poliza"|"cfdi", "poliza_id", "folio", "fecha", "concepto", "cargo", "abono", "uuid", "rfc",
  "conciliacion_id"}], "pendientes_banco", "pendientes_libros"}`. Libros = movimientos de
  pólizas activas sobre la cuenta contable ligada (+ complementos de pago y facturas PUE de la
  bóveda que mueven bancos y aún no tienen póliza). `conciliacion_id` null = pendiente.
- `POST …/cuentas/{id}/conciliar` body `{"desde", "hasta", "incluir_cfdi"}` → `{"resultado":
  {"conciliados", "uno_a_varios", "ambiguos", "pendientes_banco", "pendientes_libros"}}`.
  Importe exacto + ventana de fechas + referencia/UUID/RFC en el concepto, puntaje ≥ umbral;
  uno a uno y uno a varios (suma exacta, hasta 4). Empates exactos quedan pendientes.
- `POST …/cuentas/{id}/conciliaciones` (201) body `{"banco": ["b:…"], "libros": ["p:…",
  "c:…"], "motivo"}` → `{"conciliacion_id"}`. Sumas distintas → 422; ya conciliado → 409.
- `DELETE …/cuentas/{id}/conciliaciones/{conciliacion_id}` deshace (las partidas vuelven a
  pendientes).
- `GET …/cuentas/{id}/movimientos/{mov_id}/sugerencia` → `{"sugerida": {"cuenta_id",
  "numero", "nombre"} | null}` (comisiones 701.10, intereses 702.04/701.04, IVA 118.01…).
- `POST …/cuentas/{id}/movimientos/{mov_id}/poliza` (201) body `{"contrapartidas":
  [{"cuenta_id", "importe"}], "concepto"}` (deben sumar el importe del movimiento) → crea la
  póliza (ingreso si entra dinero, egreso si sale) y la concilia: `{"poliza",
  "conciliacion_id"}`.
- `GET …/cuentas/{id}/reporte?corte=AAAA-MM-DD&formato=json|xlsx` → `{"reporte": {"corte",
  "cuenta_bancaria", "saldo_banco", "saldo_libros", "depositos_en_transito",
  "retiros_en_transito", "abonos_banco_no_registrados", "cargos_banco_no_registrados",
  "totales", "saldo_banco_conciliado", "saldo_libros_conciliado", "diferencia", "cuadra",
  "advertencias"}}` o el XLSX.

## Contabilidad electrónica — Anexo 24 (P2-07)

Autenticado; `/api/v1/contabilidad-electronica/clientes/{clave}/…` con `cliente_o_404`.
Código en `apps/api/app/contabilidad/anexo24/`; XSD 1.3 oficiales versionados (fuente en
`apps/api/tests/xsd/contabilidad/README.md`).

Body común (`SolicitudEntrada`): `{"documento": "catalogo"|"balanza"|"polizas"|
"auxiliar_cuentas"|"auxiliar_folios", "anio" (≥ 2015), "mes" (1–12), "tipo_envio": "N"|"C",
"fecha_mod_bal" (exigida con C), "tipo_solicitud": ""|"AF"|"FC"|"DE"|"CO" (exigida en pólizas
y auxiliares), "num_orden" (AF/FC, `AAA0000000/00`), "num_tramite" (DE/CO,
`AA000000000000`), "sellar": bool}`. `sellar: true` usa la e.firma activa del cliente (404 si
no hay; 422 si venció).

- `GET /api/v1/contabilidad-electronica/documentos` → `{"documentos": [{"clave", "nombre",
  "sufijo", "a_solicitud"}], "instrucciones_portal": [str]}`.
- `POST …/validar` → `{"nombre" (RFC+AAAA+MM+sufijo), "valido", "errores" (del XSD),
  "advertencias", "sellado", "xml"}`.
- `POST …/zip` → `application/zip` con `Content-Disposition: filename="<nombre>.zip"`
  (CT, BN/BC, PL, XC, XF). 422 si el XML no valida.
- `POST …/enviar` → `{"via", "acuse": {"folio", "estado", "mensaje"}, "zip_base64"}` por el
  adaptador `buzon_sat` (`falso` = simulación; `portal_sat` responde 501, POR CONFIRMAR). El SAT
  no tiene API: el envío real se hace en el portal.
