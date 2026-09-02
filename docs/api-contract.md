# Contrato de la API — Fiscal Agent

> **PARCIAL.** Cubre los endpoints de la **épica D** —los de **asistencia** que agregó D-04 y
> el de **nómina** que agregó D-06— y los de **despacho** que agregó E-02.
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
reconocimiento; solo se lee la parte JSON y **la foto no se guarda**). Se revisan todas las
partes, **con y sin `filename`**: varios firmwares mandan el evento con filename, y ahí
Starlette lo entrega como archivo en vez de como texto.

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

### `GET /api/v1/despacho/clientes`

Cartera del despacho, para la lista y el selector de cliente activo.

```json
{
  "exito": true,
  "clientes": [
    {
      "id": "demo",
      "nombre": "Servicios Administrativos del Golfo",
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
- `clase_riesgo` — `null` para el caso real. Para los sintéticos es un **SUPUESTO**: la
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

**404 — cliente desconocido.** Usa el sobre de dominio, **no** el `{"detail": ...}` de
`HTTPException`, para que el front tenga un solo camino de lectura de errores:

```json
{ "exito": false, "error": "El cliente 'x' no está en la cartera de la demo. Clientes disponibles: demo, cafeteria, taller." }
```

> Nota de inconsistencia conocida: `GET /nomina/demo/plantilla` responde **422** (no 404) para
> un cliente que no sea `demo`, porque ahí es una validación de dominio. No se unificó: tocar
> `nomina.py` queda fuera del alcance de E-02.

---

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
