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

---

## F1-01 · tablas IMSS, tarifas ISR periódicas y subsidio (2026-09-01, sesión nocturna)

**Estado:** CERRADA. PR #10, mergeada a main. CI verde al primer intento. Tests: 477 → 564.

### Decisiones tomadas sin Ricardo

1. **Las tarifas periódicas del Anexo 8 se generan, no se transcriben.** Se construyen de la
   mensual (que ya estaba transcrita del PDF del DOF) con la regla `diaria = mensual / 30.4`
   redondeada, luego `× días`. Los valores **publicados** están como literales en el test —
   66 celdas de las tarifas diaria, semanal y quincenal, todas coinciden — y el docstring
   declara que si un ejercicio futuro divergiera, ganan los literales.
2. **Catorcenal y decenal levantan error en vez de entregar tabla.** La catorcenal no la
   publica nadie; la decenal sí está publicada pero no se pudo verificar contra fuente. Ver D10.
3. **RT y CEAV fuera de `CUOTAS_RAMOS`.** Su tasa patronal no es escalar, y meterlas con
   `None` habría permitido que un consumidor las saltara en silencio.
4. **`docs/nocturno-run.txt` sacado del control de versiones** y agregado al `.gitignore`. Se
   había colado en un commit por un `git add -A`. Es salida del runner nocturno: cambia en cada
   corrida y versionar el transcript de una sesión autónoma en este repo es un riesgo de
   privacidad estructural.

### Decisiones abiertas para Ricardo

1. **D4 quedó afinada y la pregunta cambió.** Lo implementado es `SBC == 1 SM`, pero el SBC de
   un trabajador de salario mínimo es `SM × factor de integración` ≈ 2.82 UMA, así que el
   renglón de 3.150 % es **casi inalcanzable en la práctica**. La pregunta correcta para la
   contadora: *¿el SUA lee "1.00 SM" como SBC igual al salario mínimo, o como trabajador que
   percibe el salario mínimo con SBC integrado por encima?* Son **3.150 % vs 6.026 % para todos
   los trabajadores de salario mínimo del país**. El código aplica la literal, la documenta y
   la prueba; no adivina.
2. **D10 · decenal y catorcenal** — la decenal se cierra transcribiendo sus 22 celdas del
   Anexo 8 con su cita. La catorcenal necesita respuesta de la contadora.
3. **D11 · base mensual del tope del subsidio** en nóminas semanales: ¿se proyecta o se acumula?
   Bloquea el cuadre del ISR del caso real en F1-04.
4. **Verificación de 30 segundos que vale la pena hacer:** los literales de la tarifa **diaria**
   los transcribí de una fuente secundaria, y el revisor señaló con razón que desde dentro no
   se puede distinguir una transcripción fiel de una copia de la salida del generador. Un
   renglón del Anexo 8 2026 contra `PUBLICADA_DIARIA` en
   `apps/api/tests/nomina/test_tablas_isr_periodicas.py` lo cierra. Sugerencia: el segundo
   (`27.79 / 235.81 / 0.53`), que es donde el redondeo pesa más.

---

## F1-02 · integración, SBC y avisos (2026-09-01, sesión nocturna)

**Estado:** CERRADA. PR #11, mergeada a main. CI verde al primer intento. Tests: 564 → 657.

### Bug que encontró el revisor y que valía la tarea entera

`avisos_requeridos` derivaba el año del bimestre de `fecha_cambio.year`. El promedio del
bimestre nov-dic solo se puede determinar cuando el bimestre cerró — o sea, capturando en
enero del año siguiente — así que el camino **normal** devolvía la fecha límite **un año
tarde, en silencio**, sobre un plazo cuya multa va de 20 a 350 UMA (Art. 304-B LSS):

```
bimestre 6 de 2026, capturado el 5-ene-2027  →  2028-01-07
fecha límite real                            →  2027-01-08
```

La raíz era de diseño: para un salario variable no existe una "fecha de cambio". Ahora
`anio_bimestre` es explícito y sin default, y la firma pasó a ser solo-por-nombre, de modo que
una llamada posicional vieja revienta con `TypeError` en vez de devolver un número plausible.
El test de la función suelta ya cubría el cruce de año y no detectó nada: la regresión nueva
atraviesa el compositor, que es donde vivía el defecto.

### Decisiones tomadas sin Ricardo

1. **D12 · el factor de integración se redondea a 4 decimales** y el SBC se calcula con ese
   factor ya redondeado, para que el número que el patrón declara sea reproducible a mano.
   Diferencia de hasta $0.14 de SBC cerca del tope. **Pregunta para la contadora:** ¿NOI /
   CONTPAQi usan el factor redondeado o el completo? Por §D9 esto **no afecta el cuadre de
   S-04**.
2. **D13 · qué es un "día hábil"** para los plazos del IMSS. Se usan los descansos del Art. 74
   LFT. El IMSS publica además su propio acuerdo anual de días inhábiles que **no coincide**;
   mientras no esté en el repo con su fuente, toda fecha de aviso es una **estimación
   conservadora, no una fecha legal cierta**, y así lo dice el código.
3. **Fuera la jornada electoral (Art. 74 fr. IX) y la transmisión sexenal (fr. VII).** La
   segunda por no poder citar el DOF de su texto vigente. En los dos casos el error tiene
   dirección: marcar de más un día como inhábil **corre el vencimiento hacia adelante**, y un
   aviso extemporáneo se multa. Contar de menos es lo conservador.
4. **Aguinaldo menor a 15 días levanta error** en vez de aceptarse: subintegrar el SBC y las
   cuotas es la dirección peligrosa.
5. **Los `sbc_*` devuelven el SBC sin acotar** y el llamador tiene que pasarlo por
   `clamp_sbc()`. Se eligió así porque el mixto debe acotar **una vez el total**, no cada
   componente. El camino silencioso no existe: `ceav_patronal` levanta si recibe un SBC bajo
   el piso, y hay tests de las dos costuras.

### Nota sobre D4

Esta tarea la roza: el `piso_aplicado` del clamp es el único camino práctico por el que un SBC
llega a ser exactamente 1 salario mínimo, y por tanto el único por el que el renglón de
3.150 % de CEAV es alcanzable. Ya hay un test que lo demuestra.

---

## F1-03 · cuotas obrero-patronales (2026-09-01, sesión nocturna)

**Estado:** CERRADA. PR #12, mergeada a main. CI verde al primer intento. Tests: 657 → 715.

### El criterio de cierre se ajustó, y esto es lo que Ricardo tiene que saber

El backlog pedía **cuadrar contra el caso real de S-04**. No es alcanzable con el dato
timbrado, y el criterio quedó ajustado **en el propio `backlog.md`** para que el `[x]` no se
lea como "cuadró". La evidencia completa está en **§D14**. En corto:

- Cuadran **5 de los 70 recibos**: un solo empleado, y solo desde abril.
- **Tres empleados tienen una deducción por debajo del mínimo legal** que impone su propio
  `SalarioBaseCotApor` (−2.49, −0.49, −2.55). Ninguna fórmula puede hacer que un número baje:
  la base con la que el patrón determinó la cuota **no es la que timbró**.
- **El cuadre completo depende de la contadora, no del código.**

### El hallazgo que sí valida D2

`XAHH010101AA8` tiene $55.13 en marzo y $55.12 desde abril, con el mismo SBC y los mismos 7
días. Son, al centavo, los **dos órdenes de redondeo admisibles** (agregado y por concepto): el
software del patrón cambió de criterio en el corte marzo→abril.

Y `XAAA010101AA1`, con **SBC idéntico**, no cuadra en ninguno de sus cuatro recibos porque
causó baja el 29 de marzo. Mismo salario, resultado opuesto según el mes: aísla la fecha como
causa. D2 deja de ser una suposición razonable y pasa a ser una decisión observada.

### Errores míos que el revisor cazó

1. **El test que llamé "cuadre estricto" comparaba el motor contra sí mismo.** Descartaba el
   importe del CFDI y afirmaba que el motor da 55.12. Pasaba dijera lo que dijera el dato real,
   y de ahí se propagó una afirmación falsa a D14 y al backlog — el texto que Ricardo iba a
   leer para decidir el cierre. Es exactamente la clase de validación-que-no-valida que este
   repo persigue. Corregido: ahora comparan contra el timbrado y afirman el **conjunto exacto**
   de los cinco que cuadran sobre los setenta.
2. **La tabla de mínimos legales de D14 omitía el excedente de EyM** que esos SBC sí causan, así
   que las brechas eran mayores de lo que escribí.
3. **El test de absorción del Art. 36 no probaba absorción**: usé un SBC que no dispara el
   supuesto. El caso real existe y es población de verdad — en la **ZLFN** el salario mínimo
   ($440.87) está por encima de 3 UMA, así que un trabajador de salario mínimo de frontera
   causa excedente y absorción a la vez.

### Decisiones tomadas sin Ricardo

1. **D14 nueva** con el hallazgo completo; **D2, D3 y D4 ampliadas** con lo que el caso real
   enseñó.
2. **Límite conocido declarado, no implementado:** la fr. II del Art. 31 (ausencia mayor a 7
   días libera de todas las cuotas) no está en el motor. Con 20 días de ausencia sigue cobrando
   30 de EyM. La dirección del error es la conservadora y quedó fijada por test en vez de
   adivinar.
3. **Un solo predicado** de "trabajador de salario mínimo" compartido por CEAV y el Art. 36: es
   una sola pregunta legal (D4) y no puede contestarse dos veces.
4. `tablas_imss.py` partido en `tablas_imss.py` + `ceav.py` para no pasar de 300 líneas sin
   recortar docstrings de fundamento.

### Nota para quien siga

`app/nomina_engine/cuotas.py` quedó en **300 líneas exactas**, sin margen. Lo primero que lo
toque (F1-07) debe **partir el archivo**, no recortar docstrings de fundamento.
