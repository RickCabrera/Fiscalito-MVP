# D — Demo 2026-09-02: nómina + checador Hikvision (1 día)

> Pegar la sección "Épica D" en `backlog.md` **encima de F0** y poner D-01…D-07 al frente de la
> cola. Es una **rama vertical de demo**, no sustituye F0/F1: cuando la demo pase, el código
> del motor se reabsorbe en F1 (mismos módulos, mismos nombres) y lo demo-only se borra.
> Reglas del día: salario **fijo** únicamente, **1 cliente**, **quincenal**, sin XML, sin
> IDSE, sin `apps/despacho`. Todo lo que no esté en esta lista **no se toca hoy**.

## Alcance de la demo (lo que el cliente ve)

1. Pantalla "Cliente demo" con sus empleados (de las fixtures S-04, ya anonimizadas).
2. Panel **Checador en vivo**: llegan checadas (entrada/salida) con nombre y hora. Fuente:
   dispositivo real si está en la misma red, o el simulador (mismo JSON). El cliente no
   distingue.
3. Botón **"Cerrar quincena"** → tabla de incidencias por empleado (días trabajados, faltas,
   retardos) calculada desde las checadas.
4. Botón **"Calcular nómina"** → por empleado: SBC, ISR, subsidio, cuota obrera IMSS, neto.
   Y consolidado: cuotas patronales por ramo + Infonavit del mes/bimestre. PDF con el
   patrón de export existente.
5. Fiscalito (texto; voz solo si S-00 queda antes — NO es requisito) responde "¿cuánto pago
   de IMSS este mes?" llamando al endpoint.

**Lo que se dice en voz alta en la demo, no se esconde:** "timbrado, avisos IDSE y salario
variable son la siguiente fase; el motor y la conexión al checador son reales."

## Épica D (formato backlog)

- [x] **D-01 · Tablas + constantes mínimas** — **cubierta por F1-01…F1-05.** Entregado por
  encima de lo pedido: `tablas_imss.py` y `ceav.py` con los ramos, la tabla CEAV y las primas
  medias; `subsidio.py` calcula el subsidio **desde el porcentaje del articulado** en vez de
  hardcodear el peso, y por eso da **$535.65** feb–dic y no $536.22 (§D15 y
  `knowledge_base/nomina/20_valores_referencia_2026.md` §4: el $536.22 sale de los
  considerandos y no reconcilia con la fórmula). Y `constants.py` **no** quedó con constantes
  simples: F0-02 ya hizo el refactor a vigencias, así que la UMA de enero es la de 2025.
- [x] **D-02 · `integracion.py` + `cuotas.py`** — **cubierta por F1-02 y F1-03.** El factor
  1.0493 y la tabla completa de PLAN_NOMINA §2.2 pasan; el SBC soporta fijo, **variable y
  mixto**; `DiasDelPeriodo` distingue ausentismo de incapacidad (§D3); Art. 36 y excedente de
  EyM implementados con sus consolidados. **Sin tolerancia**: el motor es exacto. Ver la nota
  de abajo sobre qué significa eso frente al caso real.
- [x] **D-03 · `isr_nomina.py` + `recibo.py`** — **cubierta por F1-04 y F1-05.** Mejor que lo
  pedido en dos puntos: el ISR usa las **tarifas del Anexo 8 por periodicidad** (§D1), no el
  prorrateo de la mensual; y sí hay XML — F1-05 entregó el CFDI 4.0 con complemento 1.2
  validado contra los XSD del SAT versionados. **Sin tolerancia**: el motor es exacto.
- [ ] **D-04 · Módulo `asistencia/` + endpoints** *(≈2 h)* —
  `schemas/asistencia.py`: `EventoChecada{empleado_no, timestamp, tipo: entrada|salida,
  fuente: hikvision|simulado|csv, raw?}`. `asistencia/hikvision.py`:
  `parse_acs_event(json) -> list[EventoChecada]` (lee `InfoList[].employeeNoString`,
  `time`, `attendanceStatus`; filtra `major==5 and minor==75`). `asistencia/incidencias.py`:
  `cerrar_periodo(eventos, empleados, horario, periodo) -> {empleado: dias_trabajados,
  faltas, retardos, dias_cotizados}` — regla simple hoy: día con ≥1 checada = trabajado;
  sin checada en día laborable = falta; entrada > hora_entrada + tolerancia = retardo.
  Endpoints: `POST /api/v1/asistencia/eventos` (recibe el JSON tal cual lo manda el
  Hikvision por HTTP listening **o** el simulador; guarda en memoria del proceso para la
  demo — dict por cliente); `GET /api/v1/asistencia/eventos?cliente=&desde=` (para el panel
  en vivo); `POST /api/v1/asistencia/cerrar-periodo`. *Listo cuando:* test con un payload
  AcsEvent real de la doc Hikvision produce las incidencias esperadas.
- [ ] **D-05 · Simulador de checador** *(≈45 min)* — `apps/api/scripts/simular_checador.py`:
  genera checadas de entrada/salida para los empleados de S-04 para toda la quincena (con 2
  faltas y 3 retardos sembrados) y las POSTea a `/asistencia/eventos` con el **mismo JSON
  que el dispositivo** (`{"AcsEvent": {"InfoList": [...]}}`). Modo `--en-vivo`: manda una
  checada cada 5 s para el efecto en pantalla. *Listo cuando:* corriéndolo, el panel del
  front se llena solo.
- [ ] **D-06 · Endpoint `POST /api/v1/nomina/calcular-periodo` + tool de agente** *(≈1 h)*
  — recibe `{cliente, empleados[], incidencias, periodo}` → `{recibos[], cuotas_consolidadas,
  explicacion?}`. **Es un orquestador, no un motor: llama directo a `recibo.py` y `cuotas.py`
  y NO reimplementa nada.** Un solo endpoint para la demo (los granulares son F1-07). Tool
  `calcular_nomina_periodo` en `agent_tools.py`. *Listo cuando:* `docs/api-contract.md` lo
  lista y el agente lo invoca desde el chat de texto.
- [ ] **D-07 · Pantalla demo en `apps/store`** *(≈3 h)* — ruta `/app/nomina-demo`
  (no tocar tabs existentes): cliente fijo + empleados de fixtures; panel checador con
  polling cada 3 s a `GET /asistencia/eventos`; botón "Cerrar quincena" → tabla incidencias;
  botón "Calcular nómina" → tabla recibos + tarjeta cuotas patronales por ramo; export PDF
  con `pdfExport*.ts`. *Listo cuando:* flujo completo se recorre sin tocar consola.
- [ ] **D-08 · (Si el dispositivo está físicamente mañana) Conectar el Hikvision real**
  *(≈30 min, ver "Configuración del dispositivo")* — opción push: configurar HTTP listening
  en el dispositivo apuntando a la laptop; opción poll: `asistencia/hikvision.py:
  sincronizar(host, user, pass, desde, hasta)` con `httpx` + Digest. Dar de alta 2–3 rostros
  con `employeeNo` = id de fixture. *Listo cuando:* una checada real aparece en el panel.

### ⚠️ Qué significa "el motor cuadra al centavo" — leer antes de la demo

El motor es **determinístico y exacto**: no hay tolerancias, y por eso se quitaron las de
D-02 y D-03. Pero eso **no** quiere decir que reproduzca los recibos históricos del caso real,
y la diferencia importa si alguien pone la salida al lado de un CFDI viejo:

| Concepto | Contra el caso real | Dónde está documentado |
|---|---|---|
| Totales del recibo y del CFDI | **70 de 70** | F1-05 |
| Exenciones del Art. 93 | **70 de 70** | F1-04 |
| ISR retenido, abril | **28 de 28** | §D15 |
| ISR retenido, marzo | 6 de 35 | §D15 |
| Cuota obrera IMSS | **5 de 70** | §D14 |

Las diferencias **no son del motor**: el CFDI timbrado trae números que no se derivan de sus
propios campos —tres empleados tienen una cuota obrera **por debajo del mínimo legal** que
impone el SBC que ellos mismos declaran (§D14)— y el patrón cambió de base del subsidio y de
orden de redondeo en el corte marzo→abril (§D15, §D2).

**Cómo decirlo si sale en la demo:** el motor calcula conforme a la ley y cuadra al centavo
consigo mismo; los recibos históricos del cliente traen inconsistencias que el motor detecta,
y eso es una función, no un defecto. **Lo que no conviene es prometer que reproduce el
histórico.**

**Orden del día:** ~~D-01 → D-02 → D-03~~ (motor: **ya está**, F1-01…F1-05) → D-04 → D-05 →
D-06 → D-07 → ensayo completo con simulador → D-08 solo si hay aparato. Si a las 6 pm D-07 no
está, la demo se hace con Swagger `/docs` + el simulador + el PDF; el motor es lo que vende.

## Referencia técnica: Hikvision DS-K1T321MFWX-B/S (MinMoe)

**Auth:** HTTP Digest con usuario admin del dispositivo. Puerto 80 (HTTP) por default.

**Poll de eventos (opción A):**
```
POST http://<ip>/ISAPI/AccessControl/AcsEvent?format=json
{
  "AcsEventCond": {
    "searchID": "fiscalito-<uuid>",
    "searchResultPosition": 0,
    "maxResults": 30,
    "major": 5,               // eventos de acceso
    "minor": 75,              // autenticación facial exitosa
    "startTime": "2026-09-01T00:00:00-06:00",
    "endTime":   "2026-09-01T23:59:59-06:00"
  }
}
```
Respuesta (campos que usamos):
```
{ "AcsEvent": { "responseStatusStrg": "OK|MORE", "numOfMatches": n, "totalMatches": N,
  "InfoList": [ { "major": 5, "minor": 75, "time": "2026-09-01T08:02:11-06:00",
                  "employeeNoString": "7", "name": "…", "attendanceStatus": "checkIn",
                  "currentVerifyMode": "face", "serialNo": 575 } ] } }
```
Paginar con `searchResultPosition` mientras `responseStatusStrg == "MORE"`. Guardar el
último `serialNo` procesado por dispositivo para no duplicar.

**Push de eventos (opción B, la que se ve mejor en demo):** en el dispositivo,
*Configuration → Network → Advanced → HTTP Listening* (ISAPI: `/ISAPI/Event/notification/httpHosts`):
host = IP de la laptop, puerto 8000, URL `/api/v1/asistencia/eventos`, protocolo HTTP,
formato JSON. El dispositivo hace `POST` con el mismo cuerpo `AcsEvent` (a veces
multipart con la foto; el endpoint debe aceptar `application/json` **y** `multipart/form-data`
y solo leer la parte JSON). Requiere laptop y checador en la misma red.

**Plan C (sin red):** exportar reporte de asistencia desde el dispositivo (USB) o desde
HikConnect Teams (Excel) → `fuente: csv` → mismo `cerrar_periodo`. No se implementa hoy;
se menciona como fallback comercial.

**Alta de empleados en el dispositivo:** `employeeNo` del Hikvision **=** `Empleado.id` de
Fiscalito. Es la única llave de mapeo. Se captura rostro en el propio panel (menú
Usuario → Agregar) o desde HikConnect Teams.

**Códigos de evento útiles:** major 5 = acceso; minor 75 = rostro OK; minor 1 = tarjeta OK;
minor 38 = huella OK; minor 21/22/76 = fallos (no cuentan como checada).

## Para `PLAN_NOMINA.md` (pegar como §2.9 y ampliar §3.1)

**§2.9 Asistencia e incidencias.** La puerta de entrada del flujo del despacho es la
asistencia: checador biométrico → eventos entrada/salida → incidencias del periodo
(faltas, retardos, permisos con/sin goce, vacaciones, incapacidades) → `dias_cotizados` y
`dias_pagados` → recibo y cuotas → si hay faltas que cambien el SBC o ausentismos
reportables, movimiento IMSS. Fuente de eventos: Hikvision ISAPI (poll o push), CSV/Excel
de otros checadores, captura manual. El módulo `asistencia/` es independiente del
fabricante: `hikvision.py` es un adaptador; otros checadores = otro adaptador con la misma
salida `EventoChecada`.

**§3.1 añadir a `app/`:** `routes/asistencia.py`, `schemas/asistencia.py`,
`asistencia/{hikvision.py, incidencias.py, csv_import.py}`. **Firestore (§3.3):**
`clientes/{id}/checadores/{deviceId}` `{marca, modelo, host, ultimo_serial}` y
`clientes/{id}/asistencia/{periodoId}` `{eventos[], incidencias, cerrado: bool}`.
**Backlog:** F1-09 `asistencia` productivo (persistencia Firestore, horarios por empleado,
permisos/vacaciones/incapacidades, dedupe por serialNo, worker de poll), F3 push con
autenticación del dispositivo y reintentos.

## Propiedad intelectual (nota para el acuerdo con el jefe)

El adaptador `asistencia/hikvision.py` y el módulo de incidencias son **extensiones de
Fiscalito desarrolladas por Ricardo** → mismo régimen que el núcleo: propiedad del autor,
licencia de uso/reventa para la empresa. El hardware (checador, red, instalación) lo aporta
la empresa y es suyo. Dejarlo escrito antes de la demo, no después.

## Ensayo de la demo, paso a paso (D-07)

> **Esto NO lo cubre CI.** Los tests del front corren en jsdom con `fetch`
> stubbeado: prueban qué pide la pantalla, qué manda y qué pinta, pero no que
> el flujo se recorra contra la API real en un navegador. Este runbook es la
> única verificación de eso, y se hace a mano.

### Antes de empezar, tres cosas que hacen fallar el ensayo

1. **La pantalla exige sesión.** `/app/nomina-demo` está detrás de
   `ProtectedRoute` **y** del gate `isOnboardingComplete()` de `AppLayout`. Con
   una cuenta sin onboarding terminado la app redirige al wizard y la pantalla
   no abre. Usa una cuenta que ya lo haya completado.
2. **El almacén de checadas es memoria del proceso.** Si reinicias la API
   después de sembrar, el panel queda vacío. Siembra **después** de levantar, y
   no uses `--reload` mientras demuestras: cualquier guardado reinicia el
   proceso y borra las 194 checadas.
3. **Siembra y demuestra el mismo día.** El simulador y la pantalla piden la
   **última quincena ya terminada**. Si siembras el día 15 y demuestras el 16,
   son dos quincenas distintas y el panel sale vacío o con faltas de todos.

### Los comandos

```bash
# 1. API (déjala corriendo, SIN --reload)
cd apps/api
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 2. Sembrar la quincena (en otra terminal)
cd apps/api
.venv/Scripts/python.exe scripts/simular_checador.py
#    → "9 empleados | 2026-08-16 a 2026-08-31 | 194 checadas | serial 900001"
#    → "recibidos=194 duplicados=0"

# 3. Front (en otra terminal, desde la raíz del repo)
npm run dev --workspace fiscalito-store
#    → http://localhost:3000

# 4. En el navegador: entrar, iniciar sesión, y abrir "Nómina (demo)" en el sidebar
#    (ruta directa: http://localhost:3000/app/nomina-demo)
```

**Para el efecto en vivo**, en vez del paso 2:

```bash
.venv/Scripts/python.exe scripts/simular_checador.py --en-vivo
#    Manda el periodo completo de golpe y el ÚLTIMO DÍA gota a gota, una
#    checada cada 5 s (~90 s). Con la pantalla abierta se ven llegar solas:
#    el panel pollea cada 3 s.
```

### Qué debe verse en cada paso

| Paso | Qué debe verse |
|---|---|
| Al abrir | "Checador en vivo" con **194 checadas**, nombres y horas |
| Fechas | Precargadas en **2026-08-16 → 2026-08-31** (16 días naturales) y la fecha de pago debajo |
| "Cerrar quincena" | Tabla de 9 empleados; **E-05 y E-08 con 1 falta**; **E-02, E-06 y E-09 con 1 retardo** |
| "Calcular nómina" | 9 recibos. E-05 y E-08 con **15 días pagados y $4,740.00**; los demás con 16 |
| Cuotas | Desglose por ramo, y la **advertencia** de que son la porción del periodo |
| "Exportar PDF" | PDF con la banda naranja **"DATOS DE DEMOSTRACIÓN"** |

### Si algo se ve raro y no es un bug

- **Tres empleados retienen ~$463 de ISR y los demás ~$91.** Es correcto:
  E-03, E-04 y E-07 rebasan el tope del subsidio al empleo. Es el hallazgo de
  §D11 apareciendo en pantalla, no un error.
- **El panel dice "0 checadas" después de re-correr el simulador.** El almacén
  deduplica por `(empleado, serialNo)`: la segunda corrida es un no-op. Corre
  con `--serial-base 5000000` para volver a sembrar sin reiniciar la API.
- **Las cuotas no son "lo que se paga al mes".** Son lo devengado en la
  quincena. Decirlo así si sale la pregunta.
