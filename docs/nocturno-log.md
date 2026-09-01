# Log del modo autónomo (nocturno)

Una entrada por tarea que una sesión autónoma cierre o salte. Formato: tarea, PR, hora, y
toda decisión tomada sin Ricardo. Las tareas anotadas como **SALTADA** no se vuelven a tomar
hasta que Ricardo las desbloquee.

---

## F0-01 · `knowledge_base/nomina/` (2026-09-01, sesión nocturna)

**Estado:** CERRADA. PR #8, mergeada a main el 2026-09-01 a las 11:37 UTC (05:37 hora local).
CI verde en el primer intento (Backend 25 s, Frontend 45 s).

### Decisiones tomadas sin Ricardo

1. **Rama huérfana preservada, no reutilizada ni borrada.** Existía una `feat/F0-01` local con
   un commit de las 04:51 de una sesión nocturna interrumpida, nunca pusheada ni revisada. El
   protocolo prohíbe reusar ramas viejas y prohíbe borrar ramas ajenas no mergeadas, así que la
   renombré a `abandonada/F0-01-sesion-0451` y construí desde main limpio.
2. **Corregí cuatro valores de `01_valores_referencia.md`** (dominio fiscal), en vez de dejar
   dos verdades conviviendo en la misma `knowledge_base/`: SM general y ZLFN 2026 (traían los
   de 2025) y UMA 2025 mensual/anual (error de centavos). Solo esos cuatro, con cita.
3. **Corregí `PLAN_NOMINA.md`** en tres puntos: el importe del subsidio (§2.1 y §2.6) y las
   claves del enum `Periodicidad` de §3.2, que eran días (`"07"`) y no claves de
   `c_PeriodicidadPago` (`"07"` es *unidad de obra*: habría producido XML mal timbrado en
   F1-05).
4. **Las tarifas del Anexo 8 no entran a `knowledge_base/nomina/`.** Son código versionado con
   fuente y pertenecen a F1-01; transcribirlas aquí crearía una copia sin tests. El doc 23 lo
   declara de frente.
5. **ISN estatal marcado `PENDIENTE VERIFICAR`** en vez de citar una fuente que no confirmé.
   Hoy no hay ningún cálculo que dependa de ese número (§D8).

### Decisiones abiertas para Ricardo

1. **Subsidio al empleo: $535.65, no $536.22.** El articulado del Decreto DOF 31-12-2025 fija
   el **porcentaje** (15.02 % de la UMA mensual; 15.59 % en el transitorio de enero), no un
   monto en pesos; el $536.22 aparece solo en los considerandos y no reconcilia con la fórmula
   (15.02 % × $3,566.22 = $535.65). El transitorio de enero sí cuadra al centavo. El motor
   calculará desde el porcentaje.
   **Riesgo residual:** la lectura del articulado la hice yo contra el DOF; si algún artículo
   que se me pasó fijara un monto en pesos, la conclusión cambia. **F1-01 debe confirmarlo y
   F1-04 cuadrarlo contra el subsidio acreditado en las fixtures de S-04.**
2. **Timbrado del subsidio en `OtrosPagos` clave 002.** Bajo el esquema post-2024 el importe
   entregado suele ser $0.00 mientras `SubsidioCausado` sí lleva monto, contra una clave cuya
   descripción habla del subsidio "efectivamente entregado". Cómo timbrarlo sin rechazo es
   pregunta para la Guía de llenado vigente y para la contadora, no para el código.
3. **Inconsistencia preexistente en `01_valores_referencia.md`, dominio fiscal, NO tocada:**
   la línea de deducciones personales calcula 5 UMA anuales con el valor **2026**
   ($213,973.20) bajo una etiqueta que dice "usando UMA 2025". Es anterior a esta tarea y cae
   fuera de F0-01, pero quedó más visible al corregir los valores de arriba.
4. **`UMA_DIARIA_2026 = 117.22` en `app/fiscal_engine/tablas_isr.py`** cuando el valor oficial
   es **$117.31** (INEGI / DOF 09-01-2026). Es un error de cálculo real en el dominio fiscal
   (se propaga a `TOPE_5_UMAS_ANUALES` y `TOPE_FUNERAL` de `deducciones_personales.py`). Cae
   dentro de **F0-02**, la siguiente de la cola.
   **Segunda cara del mismo bug, detectada por el revisor:** conviven **dos convenciones de
   UMA anual**. El código usa `diaria × 365`; INEGI y el doc 20 usan `diaria × 30.4 × 12`
   ($42,794.64). Con la UMA correcta, 5 UMA anuales dan $214,090.75 por la vía del código y
   $213,973.20 por la oficial: el número no cuadra ni corrigiendo el centavo. **F0-02 tiene
   que resolver las dos cosas**, el valor y la convención.

### Revisor

Bloqueó dos veces. Primera pasada (plan): exigió fuente primaria por valor en vez de copiar
`PLAN_NOMINA`, corregir `01_valores_referencia.md` en vez de documentar la contradicción, y
deduplicar los importes entre documentos. Segunda pasada (entregable): detectó que un heredoc
del doc 20 había fallado en silencio dejando la versión previa en disco, un conteo mal de las
fechas corridas del calendario (son cinco, no cuatro), el piso del SBC descrito como "SM
general" en vez de "SM del área geográfica" (Art. 28 LSS), y dos claves de catálogo del CFDI
heredadas de `PLAN_NOMINA` sin verificar — `c_TipoPercepcion` 049 es *Premios por asistencia*,
no "ajuste al neto", y `c_TipoDeduccion` 004 es *Otros*, no "fondo de ahorro". Todo corregido
contra el catálogo del SAT.

### Lección de proceso (para futuras sesiones)

Un `cat > archivo <<'EOF'` con contenido largo puede **fallar por truncamiento y no escribir
nada**, dejando en disco la versión anterior. `wc -l` sobre esa versión previa devolvió un
conteo parecido al esperado y dio falsa confianza: reporté al revisor un contenido que nunca
tocó el disco. **Verificar leyendo el archivo, no contando sus líneas.** Para archivos largos,
usar la herramienta de escritura en vez del heredoc.

---

## F0-02 · `constants.py` a vigencias (2026-09-01, sesión nocturna)

**Estado:** CERRADA. PR #9, mergeada a main el 2026-09-01 a las 11:54 UTC (05:54 hora local).
CI verde al primer intento. Tests: 450 → 477.

### Cambia el output de un endpoint ya desplegado

`POST /api/v1/deducciones-personales` devuelve un `tope_global` distinto. **Dos causas
independientes**, ninguna colateral del refactor:

1. `UMA_DIARIA_2026` estaba en **117.22**; el valor oficial es **117.31** (INEGI, Comunicado
   1/26; DOF 09-01-2026).
2. El tope global se calculaba como `UMA diaria × 365`. El Art. 151 último párrafo LISR dice
   "cinco veces el **valor anual** de la UMA", y ese valor anual es la magnitud que publica el
   INEGI (Art. 4 fr. III de la Ley UMA), no una derivación por 365. La `knowledge_base` ya lo
   tenía bien desde antes; el código no.

**Efecto: $213,926.50 → $213,973.20.** La firma del endpoint no cambia. El campo `ejercicio`
existe en el motor pero **no** se agregó al request: eso espera a `docs/api-contract.md` (S-03).

### Decisiones abiertas para Ricardo

1. **Tope de gastos funerarios — DECISIÓN PROVISIONAL.** El Art. 151 **fr. II** dice "elevado
   al año", no "el valor anual de la UMA" como el último párrafo. Dos lecturas defendibles: el
   valor anual publicado ($42,794.64 en 2026) o `diaria × 365` ($42,818.15). **Se tomó la
   conservadora** (tope menor), que además es la que ya usaba
   `knowledge_base/11_deducciones_personales.md`. Diferencia: **$23.51**. Marcado en el
   docstring de `tope_gastos_funerarios()`. Pregunta para la contadora.
2. **2024 quedó fuera** de las tablas de vigencia por falta de fuente verificada en el repo.
   La declaración anual del ejercicio 2024 todavía es presentable, así que puede hacer falta.
   Agregar un año es una línea con su cita del DOF; no se hizo de memoria a propósito.
3. **Deuda documental no tocada:** el árbol de archivos de `apps/api/CLAUDE.md` no lista
   `knowledge_base/nomina/` (F0-01) ni `tests/test_fixtures_nomina.py` (S-04). Sí actualicé el
   renglón que mi propio diff volvió falso.

### HALLAZGO DE PRIVACIDAD — no es de esta tarea, requiere decisión de Ricardo

El revisor encontró, auditando archivos vecinos, que hay **un RFC de persona física real
versionado en main**, en archivos trackeados y etiquetado como "caso real verificado con
contador": `CADG620317EE0` (4 letras + fecha de nacimiento + homoclave), junto a RFC de
contrapartes reales (`RIX150930NF1`, `MCP2404207Q2`, `BMS170308GT7`) ligados a montos de
facturas reales.

Aparece en `README.md` (líneas 144 y 275), `apps/api/CLAUDE.md` (110),
`apps/api/tests/test_calculadora.py` (~1410–1482) y `apps/api/tests/test_caso_real_enero2026.py`
(desde la línea 2).

Contraste: las fixtures de nómina de S-04 **sí** están anonimizadas. El trabajo se hizo para
nómina y nunca se hizo para el caso fiscal viejo. Contradice de frente la regla de `CLAUDE.md`
sobre datos personales, y el `README.md` es el archivo más visible del repo.

**No se tocó esta noche, a propósito:** limpiarlo de verdad implica reescribir historia, y el
modo autónomo prohíbe `filter-repo` y force push. **Tarea propuesta para el backlog** (la
decide Ricardo, no la agrego yo):

> **S-09 · Anonimizar el caso real CADG620317EE0** — mismo tratamiento que S-04: RFC, nombres
> y homoclaves sintéticos, montos reales, en `README.md`, `apps/api/CLAUDE.md` y los dos
> archivos de tests. Decisión de Ricardo si basta con limpiar HEAD o hay que reescribir
> historia (ver S-06, que ya plantea lo mismo para `apps/api/pfebrero/`). Nota: S-07 ya cubre
> las demo-xmls del frontend y menciona "el caso real del backend" — puede que S-09 sea parte
> de S-07 en vez de una tarea nueva.
