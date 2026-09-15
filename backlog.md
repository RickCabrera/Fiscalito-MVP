# BACKLOG — Fiscalito (prioridad: Nómina)

Reglas: una tarea = una rama = un PR. `[x]` solo tras merge a main confirmado por
Ricardo. Cada tarea tiene su "Listo cuando" — el plan y el revisor se miden contra eso.
El detalle de dominio (valores 2026, fórmulas, fuentes) está en `docs/PLAN_NOMINA.md`.

## Cola nocturna

Orden exacto que toma el **modo autonomo** (ver `CLAUDE.md`): la primera que no este
`[x]` ni marcada SALTADA en `docs/nocturno-log.md`. Una tarea por sesion. **Si no queda
ninguna pendiente, no se inventa: se crea el archivo `COLA_VACIA.txt` en la raiz y la
sesion termina** (el protocolo completo esta en `CLAUDE.md`, Modo autonomo; aqui solo se
recuerda). El detalle de cada una vive en su seccion de abajo. **S-00 no esta aqui a
proposito:** su criterio de cierre exige probar el chat de voz con microfono, asi que es
diurna.

**CAMBIO DE PRIORIDAD (2026-09-01, demo del 2026-09-02): la Épica E va al frente.**
D-04…D-07 ya están cerradas; S-03 y lo que sigue quedan en pausa hasta que E-04 cierre.

1. E-01
2. E-02
3. E-03
4. E-04
5. S-03
6. F1-07
7. F1-08
8. F1-06
9. S-02
10. S-01b

**D-08 no está en la cola**, igual que S-00: necesita el checador físico enfrente, así que es
diurna. F0-01, F0-02, F1-01…F1-05 y D-04…D-07 ya están cerradas.

## E — Épica de despacho (para la demo del 2026-09-02)

**El porqué.** Nómina quedó como una pestaña dentro de la app del CONTRIBUYENTE, pero el
producto es para un CONTADOR que lleva la nómina de varios clientes. **No se crea
`apps/despacho`** (PLAN_NOMINA §0 lo proponía; no cabe antes de la demo): se adapta
`apps/store`, que ya tiene auth, tema, PDF y componentes. Prioridad sobre todo lo demás.

- [x] **E-01 · Perfil de contador** — tipo "Despacho / Contador" en `OnboardingWizard` y
  `ProfileContext`, con sus campos (nombre del despacho, RFC). `getTabsForProfile`: si es
  contador, el sidebar muestra **Clientes / Nómina / Calendario / Perfil** y OCULTA los tabs
  de contribuyente — **no se borran, solo no se muestran**. *Listo cuando:* creo cuenta como
  contador y veo el sidebar correcto.
- [x] **E-02 · Clientes** — Backend: `GET /api/v1/despacho/clientes` y `/clientes/{id}` con 3
  clientes demo — uno es el de las fixtures S-04 con sus 9 empleados, dos sintéticos con
  distinto giro y número de empleados. Front: pantalla de lista + selector de cliente activo
  en el header, y ficha `/clientes/:id` con sus empleados (SBC, salario diario, alta, factor).
  *Listo cuando:* cambio de cliente y todo lo demás cambia con él.
- [x] **E-03 · Nómina dentro del cliente** — mover el flujo de `/app/nomina-demo` al contexto
  del cliente seleccionado: checador en vivo, cerrar quincena, calcular nómina, cuotas por
  ramo, PDF. **Mismo motor, misma API.** *Listo cuando:* el flujo completo corre para el
  cliente de fixtures y para uno sintético.
- [x] **E-04 · Pulido visual** — los inputs de fecha y los botones de la pantalla actual se ven
  crudos: jerarquía tipográfica, espaciado, estados de carga y vacío, tabla de recibos
  legible. *Listo cuando:* se proyecta en pantalla grande sin verse a medio hacer.

**Segunda tanda (2026-09-02, MODO RÁPIDO autorizado por Ricardo):** E-06 → E-07 → E-05, las tres
en una rama, un plan, un revisor de plan, un revisor de entregable y un PR. El motor de E-07
llevó **revisor aparte**, que es la excepción que Ricardo dejó en pie.

- [x] **E-05 · Onboarding y perfil del despacho** — cuando el tipo es "Despacho / Contador", el
  wizard pide SOLO: nombre del contador, nombre del despacho y teléfono. Nada de RFC, régimen
  fiscal, actividad económica ni código postal — esos son del contribuyente y a un despacho no le
  calculamos su declaración. En Perfil, si el tipo es despacho, no mostrar el selector de los
  otros 5 tipos de cuenta. *Listo cuando:* creo cuenta de despacho y sólo me piden esos tres
  datos, y en Perfil no hay dónde cambiarme de tipo.
- [x] **E-06 · La pantalla de nómina se explica sola** — convertir el flujo en 4 pasos numerados y
  visibles ("1. Checadas recibidas · 2. Cerrar quincena · 3. Calcular nómina · 4. Exportar"), cada
  uno con una línea de qué hace. Los pasos 2-4 se habilitan en orden. Además: en la nómina de un
  cliente, el sidebar y el título dejan claro en qué cliente estoy, y **"Nómina" queda resaltado,
  no "Clientes"**. *Listo cuando:* se proyecta y se entiende el orden sin que nadie lo explique.
- [x] **E-07 · Calendario patronal** — "Calendario" mostraba declaraciones ISR+IVA del
  contribuyente, que no aplican a un despacho de nómina. Se conecta al calendario laboral de
  F1-06: obligaciones patronales por cliente (entero mensual IMSS día 17, bimestral
  RCV/Infonavit, avisos de variables), agrupadas por fecha con el nombre del cliente, con
  endpoint nuevo. *Listo cuando:* el contador abre Calendario y ve vencimientos patronales de sus
  clientes, no sus propias declaraciones.

## X — Arreglos de la demo (2026-09-02, MODO RÁPIDO)

Dos arreglos pedidos por Ricardo la mañana de la demo. Una rama, un plan, un revisor de
plan, un revisor de entregable, un PR. **PR #25, mergeada.**

- [x] **X-01 · El calendario patronal daba 404 en el navegador** — **no era un bug de path.**
  La ruta existía y respondía 200; el uvicorn que estaba corriendo se había levantado antes
  del merge de E-07 (PR #24), así que servía los endpoints viejos con 200 y el nuevo con 404
  `{"detail":"Not Found"}`. Entregado: paso 0 de pre-flight en el runbook (**sin** `--reload`,
  que habría borrado las checadas sembradas), un 404/405 que se explica solo en `errorApi.ts`,
  y el test que faltaba — `exportar_rutas.py` + `rutasBackend.json` + `test_rutas_publicadas.py`
  del lado del backend, y `contratoRutas.test.ts` del lado del front, que llama a las 18
  funciones de verdad. *Listo cuando:* la ruta responde 200 con la API corriendo — **verificado**.
- [x] **X-02 · La columna "días cotizados" se leía al revés** — "el ausentismo no reduce EyM"
  se entendía como *EyM no se toma en cuenta*. Reescrito en positivo y acotado a ausencias de
  hasta 7 días al mes (la fr. II del Art. 31 no está implementada, §D3), con la lista **cerrada**
  de los seis ramos que sí descuentan — incluye Cesantía y Vejez, que vive en `ceav.py` y se
  había omitido. Solo texto: `git diff -- apps/api/app/` vacío.

## G — Épica de cartera (2026-09-02, MODO RÁPIDO)

**PR #26, mergeada.** Pedida por Ricardo la mañana de la demo, **no venía del backlog**. Una rama, un plan, un
revisor de plan, un revisor de entregable, un PR. El endpoint de SBC llevó **revisor aparte**,
que es la excepción que Ricardo dejó en pie. Regla del día: **la demo funciona en TODO
momento**; los 3 clientes demo y sus empleados se mantienen como semilla y no hay migraciones
destructivas.

- [x] **G-01 · Empleados por cliente** — *Listo cuando:* doy de alta un empleado nuevo y aparece
  en el cálculo de nómina de ese cliente.
- [x] **G-02 · Vinculación con el checador** — *Listo cuando:* un empleado sin `employeeNo` se
  marca visiblemente como "no vinculado al checador" y sus checadas no se pierden en silencio.
  **Entregada a medias a propósito:** la pantalla de dispositivos por cliente (marca, modelo,
  IP, puerto, último serial) **se recortó** — es colección nueva, CRUD nuevo y pantalla nueva,
  no cambia ningún número, y los datos del Hikvision ya están en `docs/D-DEMO-CHECADOR.md`.
  Se prefirió entregar dos tareas completas a tres a medias.
- [x] **G-03 · Multi-tenant real** — *Listo cuando:* dos cuentas distintas ven carteras
  distintas. **Su criterio está condicionado a que `firestore.rules` esté desplegado**, y
  desplegarlo es acción de Ricardo: mientras no lo esté, la app cae al catálogo del backend
  para que la demo no se rompa, y las dos cuentas ven los mismos tres clientes. El archivo
  está versionado en la raíz del repo, **y `firebase.json` se dejó intacto a propósito** para
  no cambiar la semántica de `firebase deploy`.

**Dos cosas que quedaron abiertas y son acción de Ricardo, no de código:**

1. **La receta para desplegar `firestore.rules` no funciona como está escrita.** El encabezado
   del archivo dice `firebase deploy --only firestore:rules`, pero `firebase.json` vive en
   `apps/store/` y las reglas en la raíz, y ese `firebase.json` **no tiene bloque `firestore`**
   (se dejó intacto a propósito: agregárselo haría que un `firebase deploy` pelado publicara
   también las reglas y pudiera romper producción). Para desplegarlas hace falta decidir entre
   agregar ese bloque —asumiendo el riesgo— o poner un `firebase.json` en la raíz.
   **G-03 entero cuelga de ese despliegue**: sin reglas, la app cae al catálogo del backend y
   dos cuentas ven los mismos tres clientes.
2. **Colisión de nomenclatura con F1-09.** Está referenciada en `api-contract.md`,
   `D-DEMO-CHECADOR.md`, `decisiones-nomina.md` y `nocturno-log.md` como dueña de "persistencia
   Firestore / alta de clientes". **G-01 y G-03 se comieron esa parte.** No aparece en
   `backlog.md`, así que es deuda de nomenclatura y no de código; hay que decidir si F1-09 se
   redefine o se cierra.

3. **La periodicidad de pago quedó fija en quincenal, y es un número mal que ya venía de
   antes.** El periodo que la app propone es siempre `quincena(hoy)`, y **nadie valida que la
   duración del periodo case con la `clave_periodicidad` del cliente**: `periodo.py` sólo
   comprueba que todas las incidencias midan lo mismo. Un cliente marcado **Mensual (05)**
   recibiría la tarifa mensual del Art. 96 sobre una base de 15-16 días —**ISR subestimado en
   silencio**, con recibo creíble— y uno **Semanal (02)**, la semanal sobre 16 días.
   **Catorcenal (03)** ni siquiera puede calcular: no hay tarifa publicada (§D10) y el motor
   levanta. Por eso el selector del alta de cliente ofrece **sólo quincenal**, deshabilitado y
   con la razón en pantalla. Abrir las otras tres exige que el motor rechace un periodo cuya
   duración no case con la clave — es tarea propia, y toca a la contadora.

4. **Deuda declarada: dos archivos rebasan el tope de 300 líneas** de
   `apps/store/CLAUDE.md`, que está en la sección NUNCA. `ModalEmpleado.tsx` nació por encima
   (no creció hasta ahí) y `useNominaCliente.ts` pasó de 226 a ~420. **No se extrajeron a
   propósito y con el visto bueno del revisor:** el archivo a partir es justo el que contiene
   las guardas del cierre, y hacerlo a las puertas del merge podía borrarlas con la suite en
   verde — que es exactamente lo que pasó dos veces en esta corrida. Se difiere **con las
   guardas ya pinneadas por tests**, no antes. Tarea propia.

5. **¿Cómo se calcula un cliente mensual con un periodo PARCIAL** (alta o baja a mitad de
   mes)? Tabla mensual del Art. 96 sobre base parcial, o prorrateo. No está en
   `docs/decisiones-nomina.md` —D10 cubre las claves sin tarifa y D11 el tope del subsidio— y
   roza lo que `PLAN_NOMINA.md` §5 dejó para la contadora. Hoy la guarda lo **bloquea**, que
   es lo conservador, y el mensaje lo dice explícitamente en vez de culpar a la periodicidad.

6. **Hueco preexistente que sigue abierto:** nadie detecta el caso simétrico —cliente
   quincenal al que el operador le arrastra las fechas a un mes completo—, que aplicaría la
   tarifa quincenal sobre base mensual. Los dos inputs de fecha son libres y `periodo.py` sólo
   compara las incidencias entre sí. La guarda de G-03 cubre una sola dirección y lo dice.

**Decisión de arquitectura que necesita la firma de Ricardo:** G-01 pedía CRUD de empleados en
el backend y G-03 pedía la cartera en Firestore. Eso son dos dueños del mismo dato. Se
construyó el modelo, la semilla y el cálculo en el backend, y el CRUD contra Firestore desde el
front. **No se construyeron POST/PUT/DELETE de empleados en el backend**, porque `apps/api`
está declarado *stateless* y no tiene `firebase-admin`: la única persistencia posible hoy sería
otro almacén en RAM, que haría literalmente falso el criterio de G-01 después de cualquier
reinicio — o sea, a media demo.

## O — Pivote a nómina interna de Orca Ordorica (2026-09-03, MODO AUTÓNOMO + RÁPIDO)

**El porqué.** El producto deja de ser la herramienta de un DESPACHO que lleva la nómina de
varios clientes y pasa a ser la nómina interna de **una** empresa: *Orca Ordorica Cristal
Templado*. Mismo repo. **El modo despacho no se borra: se apaga tras un flag**
(`VITE_MODO_EMPRESA_UNICA=0`) y se retomará en otro repo. Régimen de la corrida: sin paradas
de autorización, revisor 1× al plan, 1× a mitad y 1× al cierre, más revisor de motor aparte en
O-03 y en el cuadre de O-04. Tests por área durante la corrida, suite completa una vez al
final. **Prohibido borrar o desactivar tests, y prohibido recortar alcance**: lo que no salga
como está escrito se deja ABIERTO y anotado en `docs/nocturno-log.md`.

- [x] **O-01 · Modo empresa única** — **PR #32.** — flag `MODO_EMPRESA_UNICA`: Clientes fuera del menú y sus
  rutas redirigen; UN cliente implícito configurable una vez en "Configuración de empresa"
  (razón social, RFC, registro patronal, prima RT, clase de riesgo), dentro de Perfil;
  Empleados, Dispositivos, Nómina y Calendario operan directo, sin selector de cliente activo.
  Flag apagado = modo despacho intacto. *Listo cuando:* flag encendido → alta de empleado →
  nómina → exportar, sin que exista el concepto de cartera — **verificado con un test de
  integración que recorre la secuencia**, no por partes. El flag viene **encendido por
  default**: con el default apagado el pivote colgaría de un `.env` gitignoreado. La cartera
  desaparece de la **interfaz**, no del almacén: los empleados siguen en
  `users/{uid}/clientes/empresa/empleados/{id}`, que es lo que permite encender R-07 sin
  migrar un documento. **Tres decisiones abiertas para Ricardo** (zona salarial y periodicidad
  de Orca — preguntas para la contadora — y que el periodo todavía sale del catálogo de
  demostración, que cierra O-03): ver `docs/nocturno-log.md`.
- [x] **O-02 · Rebrand** — **PR #32.** — todo texto visible pasa de "Fiscalito Store" a "Orca Ordorica —
  Nómina", centralizado en una constante para re-rebrandear en un solo cambio. Los nombres
  internos del repo no se tocan. *Listo cuando:* ninguna pantalla dice Fiscalito — lo vigila
  `marca.test.ts`, que **se equivocó dos veces antes de servir** (pasaba en vacío por una ruta
  mal resuelta en Windows, y su lista de permitidos perdonaba la línea entera, lo que dejó
  pasar la etiqueta del sidebar del contribuyente). Declara su propio límite: mide la forma,
  no los píxeles.
- [x] **O-03 · Parámetros salariales editables** — **PR #33.** (REVISOR DE MOTOR: toca SBC) — en
  Configuración de empresa: días de aguinaldo (mín. 15, Art. 87 LFT), prima vacacional (mín.
  25%, Art. 80 LFT), vacaciones por antigüedad (mínimos de la tabla LFT vigente, superiores
  permitidos), horario laboral y tolerancia del checador (08:00-17:00, 15 min, L-V, editable)
  y periodicidad de pago (semanal/quincenal/mensual). Alimentan factor de integración y SBC.
  **Las tablas de ISR, cuotas IMSS y UMA/SM NO son editables** — son de ley y siguen en el
  motor con su fuente. *Listo cuando:* cambiar aguinaldo 15→30 cambia el factor y el SBC con
  test que lo demuestra (delta exacto 15/365 = 0.0411), y los mínimos de ley rechazan valores
  por debajo — **en el motor y en la pantalla**, que es donde el enunciado los pide y donde no
  había nada hasta que el revisor de motor lo midió.
  **Lo que la tarea obligó a construir de más, y no era opcional:** abrir la periodicidad sin
  una guarda de duración habría dejado vivo el agujero de §G puntos 3 y 6 (tarifa mensual sobre
  base de quincena = ISR subestimado con recibo creíble). La guarda vive en el motor, no en el
  navegador. Y `GET /nomina/periodo-sugerido`, sin el cual elegir Mensual dejaba a la empresa
  con una quincena propuesta y el motor rechazando: el selector habría roto la app en dos de
  sus tres opciones.
  **Dos decisiones ABIERTAS para Ricardo, las dos para la contadora:** §D26 (¿cómo se retiene
  el ISR de un periodo PARCIAL de un alta o una baja? — hoy se bloquea, que es una regresión
  funcional declarada) y §D27 (del 16 al 28 de febrero se pagan 13 días contra una tarifa
  derivada a 15; en la práctica la quincena se paga siempre 15).
- [ ] **O-04 · Exportador TXT multi-formato** (REVISOR DE MOTOR en el cuadre) — módulo con
  formatos intercambiables y selector en el paso 4, junto al PDF (el PDF se queda):
  movimientos afiliatorios del IMSS según el layout oficial, dispersión bancaria (BBVA,
  Banamex, Banorte — marcadas "por validar contra el manual vigente del banco") y un genérico
  pipe-delimited con todos los conceptos del recibo. Punto de extensión documentado.
  **Cuadre obligatorio:** los importes de cada TXT cuadran al centavo con el PDF del mismo
  periodo, con test que exporta ambos del mismo cálculo. *Listo cuando:* un mismo periodo
  exporta PDF + los TXT con totales idénticos, y cada formato declara su fuente o su estado
  "por validar".
  > **PR #34, mergeada — y la tarea SIGUE ABIERTA a propósito.** Entregado y medido: el
  > módulo con su punto de extensión, el selector del paso 4, el TXT de movimientos
  > afiliatorios del IMSS (layout oficial de 168 posiciones), el genérico con todos los
  > conceptos, y el cuadre al centavo de tres puntos —bytes del TXT, renglones del PDF y los
  > totales del **motor**, que ahora viajan en la respuesta— con las mutaciones que lo
  > prueban. Cada formato declara su fuente.
  >
  > **Lo que NO cumple el criterio, y por eso no va `[x]`:** la **dispersión bancaria no
  > exporta a nadie en un periodo real**, porque `cuenta_bancaria` (CLABE) no existe en el
  > modelo —ni en la ficha, ni en el backend, ni en ninguna pantalla—. Hoy el generador
  > **levanta** diciendo por qué, en vez de descargar el archivo de cero bytes que emitía
  > antes de que lo cazara el revisor del cuadre. Su cuadre está medido sobre datos
  > fabricados: vale el día que el dato exista.
  >
  > También quedan fuera las **bajas (02) y las modificaciones de salario (07)**: los tres
  > layouts están transcritos y probados, pero el modelo no guarda fecha de baja, causa ni
  > historial de SBC. Falta el dato, no el código.
  >
  > Las dos cosas se cierran capturando datos en la ficha del empleado — es tarea de modelo,
  > no de exportador. Detalle en `docs/nocturno-log.md`.

- [x] **O-cierre · Los tres bloqueos del revisor de cierre** — **PR #35.** No venía del backlog:
  salió de la revisión de cierre de la corrida O, que **bloqueó**. (1) El asistente de voz
  seguía siendo el del despacho: flota sobre todas las pantallas y su prompt hablaba de "tus
  clientes" sobre la nómina propia, además de prohibirle pedir el RFC —instrucción falsa en
  este modo, donde sí se captura—. (2) El exportador de O-04 en modo despacho leía el registro
  patronal de un documento que ahí no existe, levantaba, y mandaba a una pantalla que con el
  flag apagado no se renderiza: callejón sin salida. Ahora sale de la ficha del cliente y se
  captura en `ModalCliente`, porque el registro patronal es **de cada patrón**. (3) Cambiar las
  prestaciones no reintegraba a quien ya estaba de alta: la nómina salía con el SBC viejo,
  **subintegrada en silencio**. Se agregó `reintegrarPlantilla` con aviso permanente y dos
  pasos —calcular no escribe; guardar es un segundo clic—, porque cada cambio de SBC es un
  movimiento 07 que esta app no puede generar.
  > **El parámetro del patrón es un PISO, no un reemplazo** (`docs/decisiones-nomina.md` §D28,
  > **ABIERTA para la contadora**): `max(patrón, ficha)`, y una bajada de SBC no se escribe. La
  > primera versión ignoraba las prestaciones por empleado y le **bajaba** el SBC al trabajador
  > con prestaciones negociadas — escribiendo la subintegración que venía a cerrar.
  >
  > **Queda abierto:** el guardado es en serie y un fallo a la mitad deja la plantilla a medias
  > sin decir hasta dónde llegó. Y los días de vacaciones por empleado son **inertes** cuando
  > el patrón tiene tabla (hueco de O-03, ver §D28).

## R — Reparaciones para que la app sea usable (2026-09-02, MODO RÁPIDO)

Pedidas por Ricardo el 2026-09-02, **no venían del backlog**, en orden estricto de lo más
vital a lo menos. Régimen de la corrida: revisor 1× al plan y 1× al cierre, más revisor de
motor obligatorio en lo que toque cálculo (R-03, R-06 y R-07). Tests por área durante la
corrida, suite completa una vez al final. **Prohibido borrar o desactivar tests.**

- [x] **R-01 · Desbloquear Firestore** — **PR #27.** Las reglas vivas cubrían `users/{uid}`
  y `declaraciones` y **nada más**; como las reglas de Firestore no heredan hacia
  subcolecciones, toda `users/{uid}/clientes/**` estaba **denegada**. Ésa era la causa raíz
  del banner de permisos y de que G-03 nunca cumpliera su criterio. `firestore.rules` se
  movió a `apps/store/` (el CLI rechaza rutas fuera del directorio del proyecto — el motivo
  concreto de que la receta de la sección G no funcionara). Reglas sin cambios, validadas
  con 10 casos contra el evaluador oficial, desplegadas y verificadas contra el proyecto
  vivo. *Verificado en navegador:* crear cliente → alta de empleado → relectura con
  `origen=firestore` → borrado en cascada, cero rastros. **Salvedad:** se ejercitó el camino
  de código de producción, no el clic, porque la única sesión disponible es de perfil
  contribuyente y no pinta el sidebar del despacho.
- [x] **R-02 · Siembra automática** — **PR #27.** `apps/api/scripts/levantar_demo.py`:
  un comando levanta uvicorn y siembra los tres clientes. Reproduce **194 / 86 / 260**
  checadas, los mismos números del camino manual, verificado end-to-end. El manual queda
  intacto y este script reusa su `enviar()`. Elimina de raíz el modo de falla del uvicorn
  viejo: el proceso nace del commit actual.
- [x] **R-03 · Campo NSS en el modal de empleado** — **PR #28.** Validación con Luhn en
  `services/nss.ts`. **Desviación consciente del enunciado, pendiente de tu firma:** el
  formato (11 dígitos, numéricos) **bloquea**, pero el dígito verificador **advierte y
  guarda**, con insignia "Por verificar" en la tabla. Bloquearlo empujaría al contador a
  teclear un NSS que pase Luhn — un número inventado junto a datos reales, que es lo que
  `routes/despacho.py` argumenta que nunca debe pasar. Además no hay norma primaria del
  IMSS publicada y el XSD del SAT timbra con `[0-9]{1,15}` sin exigir verificador.
  Decisión **ABIERTA** en `docs/decisiones-nomina.md` §D25 con dos preguntas para la
  contadora; se revierte con la constante `BLOQUEA_VERIFICADOR`.
- [x] **R-04 · Pantalla de dispositivos biométricos** — recortada en G-02, se restaura.
  Listar, agregar/editar (nombre, IP, serial) y enrolamiento de empleados por dispositivo
  usando la vinculación por `employeeNo` de G-02. *Listo cuando:* doy de alta un
  dispositivo y veo qué empleados están enrolados. **PR abierta.** Cierra el tercer lado
  del triángulo de G-02 (enrolado-fantasma) y un cuarto que nadie cubría: el vinculado
  que no está en ningún aparato, que entra al cálculo y saldría con falta en todos los
  días laborables. **La pantalla no afirma cuántas checadas mandó cada aparato** porque
  `EventoChecada` no identifica el dispositivo; lo dice al pie. **PR #29.** Decisión ABIERTA
  para ti: el almacén de checadas es memoria del proceso, así que "sin checadas" significa
  "no hay checadas en la memoria del backend, que se borra al reiniciar". Acotar la insignia
  a un periodo, relativizar el copy o esperar a F1-09 es decisión de producto.
- [x] **R-05 · Empleados y Dispositivos en la navegación lateral** — entradas propias junto
  a Clientes/Nómina/Calendario/Perfil, operando sobre el cliente activo. *Listo cuando:*
  llego a empleados y dispositivos del cliente activo en un clic. **PR #29.** Las
  pestañas dentro de la ficha se quedan, como autorizaste. `EmpleadosPage` **reusa**
  `EmpleadosTab`, no lo copia.
- [x] **R-06 · Sacar el mock del flujo de producción** — la pestaña Plantilla tras flag de
  desarrollo (sin borrar fixtures ni sus tests), los clientes de demostración sólo en
  cuentas de desarrollo, y el catálogo de sólo-lectura deja de hacerse pasar por la
  cartera. *Listo cuando:* una cuenta nueva ve una app vacía y funcional, sin datos que no
  sean suyos. **PR #30.** Cerró **cuatro** costuras, no tres: la que faltaba era
  `ClienteActivoContext`, que alimentaba el selector superior desde el catálogo del
  backend — sin tocarla, una cuenta nueva habría visto su lista vacía **y el selector
  mostrando los tres clientes de demostración**. Lleva revisor de motor: quitar el fallback
  podía cambiar quién entra a `POST /nomina/calcular-periodo`. **Dos decisiones abiertas
  para ti:** (i) las cuentas donde ya se clickeó "Guardar esta cartera en mi cuenta"
  **siguen teniendo los tres clientes demo escritos en su Firestore** — el filtro los oculta
  pero no los borra, y borrar es irreversible; (ii) el flag es **sólo del cliente**: el
  backend sigue sirviendo la ficha del caso real a cualquiera, así que R-06 esconde el mock
  de la UI pero no lo saca del flujo. Eso último lo cierra R-07.
- [ ] **R-07 · Backend dueño del dato** — `firebase-admin` en `apps/api`; el CRUD de
  clientes y empleados pasa a endpoints del backend. Decisión tomada por Ricardo: el
  servicio deja de ser stateless. *Listo cuando:* alta/edición/baja de empleado pasa por el
  backend, sobrevive reinicio de la API, y el cálculo de nómina lee la misma fuente.
  **PR #31 mergeada, y la tarea sigue ABIERTA — le falta código Y credenciales.**

  **(a) Falta código: el TERCER criterio no está construido.** "El cálculo de nómina lee la
  misma fuente" **no se cumple**, ni con el interruptor apagado ni encendido.
  `routes/nomina.py` no se tocó: `POST /nomina/calcular-periodo` sigue recibiendo
  `empleados` en el cuerpo y el front sigue armándolo con `plantillaDeNomina`. Encender el
  flag sólo cambia de dónde saca el navegador la plantilla que sigue mandando. Una versión
  anterior de esta entrada decía "lo que falta NO es código"; **era falso**, y lo encontró el
  revisor de motor. Cablear el cálculo a `listar_empleados` es **tarea propia**.

  **(b) Faltan credenciales para lo que SÍ está construido.** El CRUD y su dueño están
  hechos y probados —45 tests, de los cuales 5 corren contra el **emulador de Firestore**,
  incluido el de "sobrevive reinicio" que contra un doble en memoria sería tautológico—, con
  su contrato en `docs/api-contract.md`. Lo que falta son **credenciales**
  (`GOOGLE_APPLICATION_CREDENTIALS` o `gcloud auth application-default login`): en esta
  máquina no había ninguna, y crear una llave de service account está prohibido en modo
  autónomo. Encender el front sin ellas daría **503 en todo el CRUD**, o sea una app rota a
  sabiendas. Para cerrarla: (1) credenciales en `apps/api`; (2) comprobar que
  `GET /api/v1/cartera/clientes` responde 200; (3) `VITE_CARTERA_BACKEND=1` en
  `apps/store/.env`. **No hay migración de datos** — las rutas de Firestore son las mismas
  de los dos lados. Los **dispositivos** de R-04 no se movieron: hacerlo en la misma corrida
  habría hecho nacer esa colección con dos dueños, que es el problema que R-07 cierra.

- [ ] **R-08 · El cálculo de nómina lee la cartera, no el cuerpo del request** — es el
  tercer criterio de R-07, que **no se construyó**. Hoy `POST /nomina/calcular-periodo`
  recibe `empleados` en el cuerpo y el front lo arma con `plantillaDeNomina`, así que
  "afirmar un cliente y calcular otro" cabe en un JSON y el guard del backend no puede
  atraparlo. Con `GET /cartera/clientes/{id}/empleados` ya construido, el cálculo puede leer
  la plantilla él mismo y dejar de creerle al navegador. **Depende de que R-07 se encienda**
  (credenciales). *Listo cuando:* el request de cálculo no lleva plantilla y el resultado es
  el mismo, con test de que mandar una plantilla ajena no cambia nada.
- [ ] **R-09 · Los dispositivos pasan al backend** — R-04 los dejó en Firestore escritos por
  el front. Se dejaron fuera de R-07 a propósito para no hacer nacer esa colección con dos
  dueños el mismo día. Cuando el interruptor de R-07 se encienda, migrarlos. *Listo cuando:*
  el alta de dispositivo pasa por el backend, igual que la de empleado.
- [ ] **R-10 · Los `ilegibles` de la cartera llegan a la pantalla** — el backend ya reporta
  los empleados guardados que no pasan la validación actual (`ilegibles[]`), pero **el front
  los tira**. Desde donde está sentado el contador, ese empleado sigue quedando fuera del
  cálculo sin verlo — la mitad de arriba de lo que `sin_vincular` hace bien. *Listo cuando:*
  un empleado ilegible se ve en la ficha con su razón, como el "no vinculado".
- [ ] **R-11 · (Decisión de Ricardo) ¿El emulador de Firestore entra al CI?** — los 9 tests
  marcados `emulador` **no corren en CI**: el job hereda `-m "not emulador"`. Entre ellos, el
  único que caza el borrado en cascada y el único que mide "sobrevive reinicio". **Verde en
  CI ya no significa "toda la suite corrió"**, y el `CLAUDE.md` que define el gate ("cero
  skips") todavía no lo dice. La reparación es un job con `firebase-tools`; la alternativa es
  aceptar explícitamente que esos dos criterios viven fuera del gate.

## S — Saneamiento (deuda que estorba al bucle)

- [x] **S-01 · Lint backend a cero y al CI** — `ruff check --fix` (43 auto) + limpiar el
  resto (111 total: E501, I001, F401, F541). Descomentar el paso `ruff check .` en
  `ci.yml`. *Listo cuando:* `ruff check .` sale limpio en local y corre en CI.
- [ ] **S-00 · Sacar la API key de OpenAI del frontend (SEGURIDAD — bloquea todo lo demas)**
  — `VITE_OPENAI_API_KEY` se inyecta en el bundle de Vite y viaja al navegador. Verificado
  el 2026-08-31: la key (prefijo `sk-proj-`) esta en texto plano en el bundle **en vivo**
  de `https://fiscalito-mvp.web.app/assets/index-DQ99Y4ao.js`, deployado el 2026-04-09 y
  servido con `Cache-Control: immutable`. El historial de git esta limpio (nunca se
  commiteo una key real): la fuga es solo por bundle y runtime.
  **Qué se mueve del front al back:** las 4 llamadas de
  `apps/store/src/services/voiceChatService.ts` a `api.openai.com` — `transcribeAudio`
  (Whisper), `sendMessage` (legacy, se elimina), `sendMessageWithTools` (gpt-4o-mini con
  tools) y `speakText` (tts-1 "nova"). El loop agentico (`src/agent/agentLoop.ts` +
  `tools.ts`) SE QUEDA en el cliente: sus tools operan el router y el estado de React.
  Solo se mueve la llamada al proveedor.
  **Endpoints nuevos** (bajo `/api/v1`, contrato en `docs/api-contract.md`):
  (1) `POST /voz/transcribir` — multipart `file` (webm/ogg, tope de tamaño y duracion) →
  `{"texto": str}`; (2) `POST /voz/hablar` — `{"texto": str}` (tope de caracteres) →
  `audio/mpeg` en streaming; (3) `POST /agente/turno` — `{mensaje, historial, perfil}` →
  `{"type":"text"|"tool_calls", ...}` con la MISMA forma que hoy devuelve
  `sendMessageWithTools`, para no reescribir `agentLoop.ts`. El schema de tools y el
  system prompt viven en el SERVIDOR (whitelist: `navegar`, `cargar_xmls_demo`,
  `calcular_predeclaracion`); el cliente no manda schemas.
  **Auth y CORS** (dentro del alcance: sin esto solo se traslada el agujero): dependencia
  `verify_firebase_token` sobre los 3 endpoints nuevos (valida el ID token de Firebase del
  header `Authorization: Bearer`; el front ya lo tiene en `useAuth()`) y `CORS_ORIGINS`
  explicito en produccion, nunca `*`. El **rate limit sale a S-00b**.
  **Qué se elimina de apps/store:** `VITE_OPENAI_API_KEY` de `.env` y `.env.example`; la
  constante `OPENAI_API_KEY` y los 4 `fetch` a `api.openai.com` de `voiceChatService.ts`
  (pasan por `fiscalAgentApi.ts` con el ID token); `sendMessage()` (muerta desde
  `agentLoop`); la nota de `apps/store/CLAUDE.md` que declara la key de cliente como
  "aceptable para demo"; y `apps/store/dist/` se borra y se reconstruye (el artefacto
  actual esta contaminado).
  **Rotacion (la hace Ricardo):** revocar la key `sk-proj-...` en OpenAI, emitir una nueva
  solo en `apps/api/.env`, y restringir la key de Firebase (`AIzaSy...`) por HTTP referrer.
  *Listo cuando:* (a) cero variables secretas en `apps/store/.env` y `.env.example` — solo
  quedan las de Firebase y la URL del agente; (b) `grep -rn "api.openai.com" apps/store/src`
  → cero resultados; (c) build nuevo y `grep -roE "sk-[A-Za-z0-9_-]{8,}" apps/store/dist/`
  → cero resultados; (d) la key vieja esta REVOCADA en OpenAI y la nueva vive solo en
  `apps/api/.env` — **confirmado por Ricardo el 2026-09-01**; falta la restriccion
  por HTTP referrer de la key de Firebase; (e) los 3 endpoints nuevos responden 401 sin ID token
  valido de Firebase; (f) `pytest -q` verde incluyendo tests nuevos de los 3 endpoints (401
  sin token + happy path con el cliente OpenAI mockeado; los tests nunca pegan a la API
  real); (g) `ruff check .` limpio, `npm run build` y `npm run lint` sin errores nuevos;
  (h) el chat de voz funciona end-to-end (grabar → transcribir → tool call → responder →
  TTS) sin ninguna key en el cliente; (i) `docs/api-contract.md` actualizado con los 3
  endpoints y el esquema de auth.
- [x] **S-05 · Runner de tests en el frontend** — instalar Vitest + Testing Library,
  script `test`, red cerrada por default en setup, pruebas semilla de `cfdiParser` (con
  los demo-xmls) **y de la lógica pura de `agentLoop.ts` y `tools.ts`**. Descomentar
  `npm test` en `ci.yml`. Va **antes de S-02**: sin esta red, tocar `AgentContext` para
  limpiar eslint es a ciegas. *Listo cuando:* `npm test` verde en local y en CI, y las
  semillas cubren cfdiParser + la lógica pura de agentLoop y tools.
- [ ] **S-02 · Lint frontend a cero y al CI** — corregir 20 errores + 8 warnings de
  eslint (concentrados en voiceChatService, AgentContext, tools). Descomentar `npm run
  lint` en `ci.yml`. *Listo cuando:* `npm run lint` exit 0 en local y corre en CI.
- [ ] **S-01b · Alinear `target-version` de ruff con el Python del CI** —
  `pyproject.toml` declara `target-version = "py311"` pero el job backend de `ci.yml` corre
  en Python 3.12: ruff aplica reglas de una version que no es la que ejecuta los tests.
  *Listo cuando:* las dos versiones coinciden (o la discrepancia queda justificada por
  escrito en `pyproject.toml`) y `ruff check .` sigue limpio.
- [ ] **S-03 · `docs/api-contract.md` como fuente única** — exportar el OpenAPI de
  FastAPI a un contrato versionado (endpoints, request/response). Los dos CLAUDE.md de
  apps dejan de duplicarlo y lo referencian. *Listo cuando:* el archivo existe, cubre
  los 11 endpoints, y las secciones duplicadas de los CLAUDE.md se reemplazan por la
  referencia.
- [x] **S-04 · Caso real de nómina anonimizado** — tomar 1 bimestre de
  `03. CFDI DE NOMINA/` (p. ej. marzo–abril: 9→7 empleados, con INFONAVIT, prima
  dominical y subsidio), generar fixtures XML con RFC/nombres/CURP sintéticos y montos
  reales, en `apps/api/tests/fixtures/nomina/`. *Listo cuando:* fixtures versionadas
  sin ningún dato identificable real (verificación explícita del revisor) y un
  `conftest` que las cargue. Es el equivalente nómina del CADG620317EE0.
## D — Demo 2026-09-02: nómina + checador Hikvision

Rama **vertical de demo**, no sustituye a F0/F1: cuando la demo pase, lo demo-only se borra y
el motor se queda. El detalle completo —alcance, referencia ISAPI del Hikvision, configuración
del dispositivo— vive en `docs/D-DEMO-CHECADOR.md`. Reglas del día: salario **fijo**, **1
cliente**, **quincenal**, sin IDSE, sin `apps/despacho`.

- [x] **D-01 · Tablas + constantes mínimas** — cubierta por F1-01…F1-05.
- [x] **D-02 · `integracion.py` + `cuotas.py`** — cubierta por F1-02 y F1-03.
- [x] **D-03 · `isr_nomina.py` + `recibo.py`** — cubierta por F1-04 y F1-05.
- [x] **D-04 · Módulo `asistencia/` + endpoints** — `schemas/asistencia.py` con
  `EventoChecada{empleado_no, timestamp, tipo, fuente, raw?}`; `asistencia/hikvision.py`
  con `parse_acs_event()` (lee `InfoList[].employeeNoString`, `time`, `attendanceStatus`;
  filtra `major==5 and minor==75`); `asistencia/incidencias.py` con `cerrar_periodo()`
  → días trabajados, faltas, retardos, `dias_cotizados`. Endpoints
  `POST /asistencia/eventos`, `GET /asistencia/eventos`, `POST /asistencia/cerrar-periodo`;
  almacenamiento **en memoria del proceso**, solo para la demo. *Listo cuando:* un payload
  `AcsEvent` real de la doc Hikvision produce las incidencias esperadas.
- [x] **D-05 · Simulador de checador** — `scripts/simular_checador.py` genera la quincena
  completa de los empleados de S-04 (con 2 faltas y 3 retardos sembrados) y la POSTea con el
  **mismo JSON que el dispositivo**. Modo `--en-vivo`, una checada cada 5 s. *Listo cuando:*
  corriéndolo, el panel se llena solo.
  **Criterio cumplido a medias, a propósito (PR #17):** el panel es D-07 y no existía al cerrar
  esta tarea. Lo verificado end-to-end contra los tres endpoints es que el simulador alimenta
  `POST /asistencia/eventos`, que `GET /asistencia/eventos` devuelve lo que el panel va a
  consumir —194 checadas en orden, cada una con el nombre que le toca— y que `cerrar-periodo`
  da las 2 faltas y los 3 retardos. **"El panel se llena solo" lo cierra D-07.** La lógica pura
  vive en `scripts/checador_sintetico.py`.
- [x] **D-06 · `POST /api/v1/nomina/calcular-periodo` + tool de agente** — recibe
  `{cliente, empleados[], incidencias, periodo}` → `{recibos[], cuotas_consolidadas,
  explicacion?}`. **Orquestador, no motor: llama directo a `recibo.py` y `cuotas.py` y no
  reimplementa nada.** Tool `calcular_nomina_periodo` en `agent_tools.py`. *Listo cuando:*
  `docs/api-contract.md` lo lista y el agente lo invoca desde el chat de texto.
  **Cerrada con PR #18, con dos precisiones que hay que leer antes de la demo:**
  (1) `cuotas_consolidadas` se llama `porcion_mensual` / `porcion_bimestral` porque **no es
  el entero del Art. 39 LSS**: es lo devengado en el periodo, y una quincena trae media
  mensualidad de EyM/IyV. La respuesta lo advierte. (2) Del "el agente lo invoca" está
  probado el registro, el despacho y que **los system prompts lo enumeran** —que era el
  hueco real—, pero **que un LLM decida llamarlo no se verifica en CI**: no hay key y
  ningún test pega a un proveedor. Decisiones nuevas en §D17–§D20.
- [x] **D-07 · Pantalla demo en `apps/store`** — ruta `/app/nomina-demo`, sin tocar los tabs
  existentes: panel de checador con polling cada 3 s, botón "Cerrar quincena" → tabla de
  incidencias, botón "Calcular nómina" → recibos + cuotas patronales por ramo, export PDF con
  `pdfExport*.ts`. *Listo cuando:* el flujo completo se recorre sin tocar consola.
  **Criterio cumplido a medias (PR #19).** *Verificado:* la secuencia completa de llamadas
  contra la API viva —plantilla → 194 checadas → cierre con 2 faltas y 3 retardos → 9 recibos
  con E-05 y E-08 en 15 días pagados— y los tests de jsdom con `fetch` stubbeado.
  *No verificado:* que la pantalla se pinte y los botones respondan **en un navegador** contra
  la API real; la ruta está detrás de Firebase Auth y del gate de onboarding. Para eso está el
  **runbook en `docs/D-DEMO-CHECADOR.md`**, que además lista los tres modos de falla que no son
  bugs: sembrar y demostrar el mismo día, no reiniciar la API, y la cuenta con onboarding
  completo. Endpoint nuevo `GET /nomina/demo/plantilla` para que el front no hardcodee ninguna
  constante fiscal.
- [ ] **D-08 · (Solo con el dispositivo enfrente) Conectar el Hikvision real** — push por
  HTTP listening o poll con Digest; alta de 2–3 rostros con `employeeNo` = id de fixture.
  **Fuera de la cola nocturna**: necesita hardware. *Listo cuando:* una checada real aparece
  en el panel.

> **El motor no lleva tolerancias**: es exacto. Lo que **no** hace es reproducir los recibos
> históricos del caso real, y la diferencia es del CFDI timbrado, no del motor — ver el
> recuadro "Qué significa *el motor cuadra al centavo*" en `docs/D-DEMO-CHECADOR.md` antes de
> decir nada de esto en la demo.

## F0 — Fundamentos de nómina (sin código de producto)

- [x] **F0-01 · `knowledge_base/nomina/`** — docs 20–26 con los valores de
  PLAN_NOMINA §2 (UMA por vigencia, SM, tope/piso SBC, subsidio 2026, factor de
  integración, ramos IMSS, CEAV) y sus fuentes. *Listo cuando:* cada valor tiene fuente
  y fecha de vigencia.
- [x] **F0-02 · Refactor `constants.py` a vigencias** — `uma_vigente(fecha)` y
  `salario_minimo_vigente(fecha, zona)`; migrar usos existentes; tests que cubran el
  corte enero/febrero 2026 (UMA 2025 en enero). *Listo cuando:* 93 tests previos
  siguen verdes + tests nuevos de vigencia.
- [x] **F0-03 · Checklist contadora** — documentar en `docs/decisiones-nomina.md` las 8
  preguntas abiertas de PLAN_NOMINA §5 con las respuestas obtenidas (tablas ISR
  periódicas vs prorrateo, redondeo, ausentismos por ramo, quirk CEAV, EMA/EBA, PAC,
  ISN Veracruz). *Listo cuando:* las que bloquean F1 tienen respuesta o decisión
  provisional explícita.

## F1 — Motor `nomina_engine`

- [x] **F1-01 · `tablas_imss.py` + `tablas_isr_periodicas.py` + `subsidio_empleo()`** —
  tablas 2026 versionadas con fuente; subsidio con transitorio de enero. *Listo cuando:*
  tests unitarios por tabla contra valores publicados.
- [x] **F1-02 · `integracion.py`** — factor de integración calculado desde
  (aguinaldo, vacaciones, prima), SBC fijo/variable/mixto, clamp 1 SM–25 UMA,
  `ConceptoIntegrable`, `requiere_aviso` con fecha límite (Art. 34). *Listo cuando:*
  la tabla de factores mínimos de ley de PLAN_NOMINA §2.2 pasa como test.
- [x] **F1-03 · `cuotas.py`** — cuotas por ramo, por empleado, consolidado
  mensual/bimestral; SM absorbe cuota obrera; EyM excedente 3 UMA. *Listo cuando:*
  tests unitarios por ramo + cuadre contra el caso real S-04.
  **Criterio ajustado en F1-03 (ver `docs/decisiones-nomina.md` §D14):** el cuadre contra el
  caso real **no es alcanzable con el dato timbrado**. Solo **5 de los 70 recibos** se
  reproducen: un empleado, y solo desde abril, porque el software del patrón cambió de orden de
  redondeo en el corte marzo→abril. De los demás, tres tienen una deducción **menor que el
  mínimo legal** que impone su propio `SalarioBaseCotApor`, cosa que ninguna fórmula puede
  producir. Se entregó el cuadre de esos 5 recibos contra el importe timbrado y la
  caracterización ejecutable del resto. **El cuadre completo queda pendiente de la contadora**,
  no del código.
- [x] **F1-04 · `isr_nomina.py`** — exenciones Art. 93, ISR Art. 96 periódico, subsidio
  con vigencia. *Listo cuando:* el ISR retenido de las fixtures S-04 cuadra al centavo
  (o con la regla de redondeo decidida en F0-03).
  **Resultado (ver `docs/decisiones-nomina.md` §D15):** el motor reproduce **al centavo los 28
  recibos de abril, completos**, y la exención cuadra en el 100 % de los recibos que la
  ejercitan. Marzo cuadra 6 de 35 porque el subsidio que declara el CFDI ahí es **$123.47**
  —compatible con dos bases distintas que no se pueden distinguir al centavo, ver §D15— y
  porque el tope de ingresos todavía no mordía; **desde abril el declarado es $123.34, que es
  lo que calcula el motor**. Los
  7 recibos de mayo llevan lo que parece un ajuste mensual de ISR, fuera del alcance de esta
  tarea.
  **Huecos que le deja F1-01:** `tarifa_por_periodicidad()` levanta error para la
  **catorcenal** (nadie la publica) y para la **decenal** (el Anexo 8 sí la publica, pero sus
  11 renglones no se pudieron verificar contra fuente publicada — agregarla es transcribir sus
  22 celdas con su cita). Ver `docs/decisiones-nomina.md` D10. Y **D11 sigue abierta**: el tope
  del subsidio es mensual y el caso real es semanal; `subsidio_empleo()` recibe el ingreso
  mensual ya resuelto y no decide si se proyecta o se acumula.
- [x] **F1-05 · `recibo.py` + `cfdi_nomina_xml.py`** — recibo completo
  (percepciones/deducciones/otros pagos) y XML complemento nómina 1.2 **sin timbrar**,
  validado contra XSD. Las fixtures de S-04 son estructuralmente correctas pero
  **criptográficamente inverificables** (sellos sintéticos): la validación XSD es de
  estructura, no de sello. *Listo cuando:* los XSD de complemento nómina 1.2 y CFDI 4.0
  están **versionados offline en `apps/api/tests/xsd/`** para validar en CI sin red, el
  XML generado del caso real valida contra ellos, y sus totales cuadran con el timbrado
  original.
  **Resultado:** los 6 XSD quedan versionados **byte-idénticos** a lo publicado por el SAT
  (6.1 MB, de los cuales `catCFDI.xsd` son 5.98 MB) y la resolución offline la hace un resolver
  de lxml, no una reescritura — así el SHA-256 de cada uno sigue verificando contra la fuente
  oficial, y un test lo recalcula. **Los 70 recibos del caso real se vuelven a emitir con el generador** y los
  totales que escribe en el XML cuadran contra el timbrado en los 70, **los 70 emitidos validan
  sin red**, y un test de ida y vuelta compara atributo por atributo todo lo que el generador
  emite contra el original, excluyendo los de sello. Se lee del documento emitido, no del objeto de dominio: comparar propiedades del recibo
  contra el fixture deja pasar un generador que escriba el atributo equivocado. El
  camino de **cálculo** (ISR y cuota obrera) sigue midiéndose donde lo dejaron §D14 y §D15;
  F1-05 no lo re-litiga.
- [ ] **F1-06 · `calendario_laboral.py`** — obligaciones patronales (pago mensual día
  17, bimestral, avisos de variables) fusionables con el calendario SAT existente.
  **PARCIALMENTE ENTREGADA POR E-07, y por eso NO se marca.** Ya existen
  `app/nomina_engine/calendario_laboral.py` (catálogo de obligaciones) y `plazos_patronales.py`
  (las cinco reglas de plazo), con las 12 fechas de 2026 contrastadas contra la tabla publicada
  del doc 25 §3. **Lo que falta y por qué:** la parte de "fusionables con el calendario SAT"
  choca de frente con la advertencia de `dias_habiles.py:8-14` —el del SAT corre por sexto dígito
  del RFC y el del IMSS por viernes o inhábil, y el doc 25 §4 dice que juntarlos sin distinguir
  "es un bug esperando"—. E-07 los mantuvo separados y etiquetó cada obligación con su
  `regimen_de_plazo`. **Decisión para Ricardo:** si "fusionable" significaba una sola vista, ya
  está; si significaba un solo generador, hay que reabrir la advertencia. Faltan además: ISN
  (sin fuente estatal en el repo, §D24) y el ajuste por sexto dígito (el modelo de cliente no
  guarda RFC).
  **Defecto preexistente detectado y NO arreglado aquí:** `fiscal_engine/calendario.py`
  `_fecha_limite_dia_17()` con `dias_extra=0` devuelve el día 17 crudo, domingos incluidos,
  porque sólo suma días hábiles hacia adelante y nunca corrige el día de partida. Afecta al
  calendario del CONTRIBUYENTE. Fuera del alcance de E-07; que lo recoja F1-07 o S-03.
- [ ] **F1-07 · Routes + schemas nómina** — `app/routes/nomina/` y
  `app/schemas/nomina/` (sbc, cuotas, recibo, calendario), errores con
  `FiscalAgentError`, explicación LLM con fallback. *Listo cuando:* `docs/api-contract.md`
  actualizado en el mismo PR.
  **OJO — E-07 se comió su parte de "calendario":** ya existen `GET /api/v1/despacho/calendario`
  y `app/schemas/calendario_laboral.py`, documentados en el contrato. **F1-07 no debe crear un
  segundo endpoint de calendario**; si acaso, mover el existente a `routes/nomina/` cuando esa
  carpeta exista. La cola decía S-03 → F1-07 → F1-08 → F1-06 y esta corrida se saltó ese orden
  por instrucción directa de Ricardo (demo del 2026-09-02), no por la regla de la cola.
- [ ] **F1-08 · Tools de agente + `POST /agente/nomina`** — extender `agent_tools.py`
  (calcular_sbc, calcular_cuotas, generar_recibo) con RequestContext.

## F2+ — Épicas (se desglosan al llegar)

- [ ] **F2 · Frontend `apps/despacho`** (scaffold, contador→clientes→empleados, pantallas
  cuotas/nómina, dashboard, Fiscalito voz, preview fiscal) — ver PLAN_NOMINA §3.3/§4.
- [ ] **F3 · Integraciones** (conciliación EMA/EBA, PAC sandbox, IDSE/SUA, alertas).
- [ ] **F4 · Escala** (módulo fiscal por cliente, multi-usuario, ISN, PTU, MCP).

## Diferido (despues de nomina)

Nada de esto entra a la cola nocturna. Se retoma cuando nomina este cerrada.

- [ ] **S-00b · Auth en todo `/api/v1` + rate limit por uid + tope de gasto** — va
  inmediatamente despues de S-00. S-00 pone auth solo en los 3 endpoints nuevos porque el
  backend de produccion esta caido y la ventana de exposicion es cero; S-00b cierra el
  resto.
  (1) **Auth en todos los endpoints `/api/v1`** (`/health` queda publico) — la forma barata
  es `include_router(..., dependencies=[Depends(verify_firebase_token)])` en `main.py`, una
  linea por router. Importa porque los 7 endpoints de calculo aceptan
  `incluir_explicacion: true` y **tambien queman tokens de LLM**: el front lo manda en 8
  lugares.
  (2) **Rate limit por uid de Firebase** sobre todo lo que gasta LLM (`/voz/transcribir`,
  `/voz/hablar`, `/agente/turno`, `/agente/predeclaracion` y los 7 de calculo con
  explicacion), con 429 y `Retry-After`.
  (3) **Tope de gasto**: limite duro en el dashboard de OpenAI + corte propio por ventana.
  Nota: la auth identifica, no frena — el alta de usuarios es abierta
  (`createUserWithEmailAndPassword`), asi que cualquiera obtiene un token valido en 10
  segundos. El uid sirve para rate-limitar, y ese es el control real.
  **El backend no se despliega publico hasta cerrar S-00b.**
  *Listo cuando:* tests que prueban 401 sin token en los endpoints de calculo, 429 al
  exceder el limite y 200 dentro del limite; el limite es configurable por env;
  `docs/api-contract.md` documenta la auth generica y el 429; y el tope duro esta puesto en
  el dashboard de OpenAI (confirmado por Ricardo).
- [ ] **S-06 · (Opcional, prioridad baja) Reescribir historial para purgar
  `apps/api/pfebrero/`** — 12 XML de CFDI con RFC de terceros identificables
  (CADG620317EE0, NIGE780321TK2, MCP2404207Q2, BMS170308GT7...) siguen alcanzables en los
  commits `29245f6` y `29313de` aunque ya no existan en el arbol. **Prioridad baja a
  proposito:** el repo es privado y el historial no tiene ninguna API key (verificado el
  2026-08-31 blob por blob). Reescribir historial rompe clones y forks, asi que solo vale
  la pena si el repo se hace publico. *Listo cuando:* si se decide hacerlo, `git filter-repo`
  purga la ruta, se fuerza el push y se avisa de la reescritura; si no, esta tarea se cierra
  con una nota de decision explicita.
- [ ] **S-08 · Deploy backend a Cloud Run + front apuntando a el** (cuando haya razon para
  produccion) — hoy produccion esta APAGADA por decision de Ricardo (2026-09-01): el sitio
  no tiene usuarios y la prioridad es nomina. El bundle publicado en
  `fiscalito-mvp.web.app` apunta a `fiscal-agent-api-production.up.railway.app`, que
  responde 404 (Railway lo dio de baja), asi que ningun calculo fiscal funciona en vivo.
  Mientras tanto `VITE_FISCAL_AGENT_URL` apunta a localhost en dev y punto. No redesplegar
  Railway. *Listo cuando:* haya una razon de producto para tener produccion; entonces se
  desglosa (Cloud Run, CORS_ORIGINS explicito, build del front con la URL real, redeploy de
  Hosting). Bloqueada por S-00b.
- [ ] **S-07 · Anonimizar las demo-xmls y el caso real CADG620317EE0** — las tres
  fixtures de `apps/store/public/demo-xmls/2026/01/` llevan RFC y nombre reales, y
  `vite build` las copia tal cual a `dist/`, asi que viajan al bundle desplegado. Mismo
  tratamiento para el caso real del backend. RFC/nombre sinteticos, montos reales.
  **Ojo:** desde S-05 la suite depende de esas fixtures, asi que este cambio toca tambien
  `apps/store/src/services/cfdiParser.test.ts` y `apps/store/src/agent/tools.test.ts`.
  *Listo cuando:* ningun dato identificable real queda en `public/` ni en `dist/`, y
  `npm test` sigue verde con las fixtures nuevas.
- [ ] **B-01 · (Bug, prioridad baja) La demo siempre reporta "0 egreso(s)"** —
  `ejecutarCargarXmlsDemo` cuenta `f.tipo === 'E'` para su resumen, pero las tres
  demo-xmls son `TipoDeComprobante="I"` (una factura de compra lo es). El conteo nunca
  es distinto de cero. Es un bug de datos demo, no del parser. *Listo cuando:* el resumen
  refleja la realidad (o distingue emitidas de recibidas por RFC en vez de por tipo).
