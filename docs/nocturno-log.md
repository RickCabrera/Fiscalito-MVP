# Log del modo autónomo (nocturno)

Una entrada por tarea que una sesión autónoma cierre o salte. Formato: tarea, PR, hora, y
toda decisión tomada sin Ricardo. Las tareas anotadas como **SALTADA** no se vuelven a tomar
hasta que Ricardo las desbloquee.

---

## F0-01 · `knowledge_base/nomina/` (2026-09-01, sesión nocturna)

**Estado:** entregable construido en `feat/F0-01`. PR y merge se anotan abajo al cerrarse.

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
   (afecta el tope de deducciones personales). Cae dentro de **F0-02**, la siguiente de la cola.

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
