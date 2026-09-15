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

## Cartera del despacho — el backend como dueño del dato (R-07)

**El único grupo de rutas del repo que EXIGE autenticación.** El resto de
`/api/v1` sigue abierto (S-00b) y eso no cambia aquí.

`Authorization: Bearer <ID token de Firebase>`. **No hay parámetro de uid en
ninguna ruta**: pasarlo por el cuerpo o por la URL haría que cualquiera leyera la
cartera de cualquiera cambiando un renglón, y esta cartera guarda el salario y el
NSS de trabajadores de terceros. El uid sale del token verificado.

| Código | Cuándo |
|---|---|
| 401 | falta `Authorization`, está mal formado, o el token no es válido |
| 404 | el cliente no está en **tu** cartera |
| 422 | el cuerpo no pasa la validación (prima de RT fuera del Art. 72, NSS mal formado, id que no coincide con la URL) |
| 503 | **el backend no tiene credenciales de Firebase.** El mensaje dice qué falta |

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

En modo empresa única este documento (`users/{uid}/clientes/empresa`) es **la Configuración de
empresa**: lo lee y lo escribe la pantalla de Perfil, por el mismo despachador de R-07.

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

El campo existe en `ClienteCarteraSchema` **aunque hoy el dueño del dato siga siendo Firestore**
(R-07 continúa apagada): sin declararlo, encender R-07 borraría el régimen de cada cliente en el
primer guardado, porque pydantic descarta lo que no conoce. No hay migración: los documentos sin
la llave se leen igual.

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
**Borra en cascada.** Firestore no lo hace solo: sin esto los empleados quedarían
huérfanos —con su salario y su NSS— y reaparecerían al recrear un cliente con el
mismo id. Hay un test contra el emulador que lo fija, y el doble en memoria **no
puede** cazar ese bug.

### `GET /api/v1/cartera/clientes/{cliente_id}/empleados`
La plantilla del cliente, leída de la cartera que este CRUD escribe. Distinta de
`/despacho/clientes/{id}/empleados`, que es la SEMILLA de demostración y no la
cartera de nadie. `{exito, cliente_id, total, sin_vincular, ilegibles[], empleados[]}`.

`ilegibles[]` son los `empleado_no` de documentos guardados que **no pasan la
validación actual** —un NSS de una versión anterior, un campo que falta— y que
por eso **no vienen en `empleados`** ni cuentan en `total`. Se reportan en vez de
tumbar la respuesta con un 500: como el front pide los empleados de todos los
clientes en paralelo, un solo documento legado dejaba la cartera **completa** en
cero. **Hoy el front no los pinta**; pintarlos es tarea pendiente, y hasta
entonces ese empleado queda fuera del cálculo sin que el contador lo vea.

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

### Estado: **el interruptor está APAGADO**

El front sigue escribiendo Firestore directo. Lo que falta para encenderlo no es
código: son **credenciales** (`GOOGLE_APPLICATION_CREDENTIALS` o ADC), y
encenderlo sin ellas daría 503 en todo el CRUD. Se enciende con
`VITE_CARTERA_BACKEND=1` en `apps/store/.env` **después** de comprobar que
`GET /api/v1/cartera/clientes` responde 200. **No hay migración de datos**: las
rutas de Firestore son las mismas de los dos lados.

T2 le dio al flag la misma lectura que a `VITE_MODO_EMPRESA_UNICA`
(`services/flagEncendido.ts`): además de `1` encienden `true`, `on`, `yes`, `si`
y `sí`, y todo lo demás lo deja apagado. Antes sólo valía `=== '1'`, así que un
`.env` con `VITE_CARTERA_BACKEND=true` dejaba el backend apagado sin decirlo.

**Dispositivos NO están aquí.** R-04 los dejó viviendo en Firestore escritos por
el front; meterlos en la misma corrida haría nacer la colección con dos dueños
dentro del mismo día, que es el problema que R-07 cierra. Es tarea propia.

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
