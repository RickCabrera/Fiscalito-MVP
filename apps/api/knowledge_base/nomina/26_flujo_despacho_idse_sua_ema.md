# 26 · El flujo real de un despacho: IDSE, SUA, EMA/EBA

> **Documento de referencia, no fuente de cálculo.** Describe el proceso que el producto
> automatiza. No es fuente de cálculo ni de tool calling.

**Alcance:** el ciclo operativo que hoy hace a mano un despacho contable, con los plazos
legales de cada paso. Cada paso es un candidato a feature o a tool del agente.

---

## 1. El ciclo

1. **Alta patronal del cliente** — registro patronal, clase y prima de RT, entidad federativa,
   e.firma vinculada en el Escritorio Virtual del IMSS.
2. **Movimientos afiliatorios** — altas, bajas, reingresos y modificaciones de salario, por
   **IDSE**. Hoy: captura manual o archivo de movimientos.
3. **Correr la nómina** (semanal/quincenal) — percepciones, SBC, ISR + subsidio, cuota obrera,
   neto; y **timbrar** cada recibo.
4. **Precálculo de cuotas** del mes y del bimestre, por empleado y consolidado por cliente.
5. **Conciliar** el precálculo contra la **EMA** (Emisión Mensual Anticipada) y la **EBA**
   (Emisión Bimestral Anticipada) que publica el IMSS en IDSE. Diferencias típicas:
   movimientos no reconocidos, SBC distinto, días de incapacidad, ausentismos. Aquí el
   contador detecta errores **antes de pagar**.
6. **Pagar** por SUA, con línea de captura SIPARE, el día 17
   (`25_calendario_laboral_2026.md`). El ISR retenido se entera aparte, en la declaración
   mensual del patrón ante el SAT.
7. **Bimestres pares** — recalcular la parte variable del SBC y presentar las modificaciones.
8. **Febrero** prima de RT; **mayo/junio** PTU; **diciembre** aguinaldo.

> El paso 5 es el de mayor valor del producto: hoy se hace en Excel o con herramientas de
> confronta SUA vs IDSE. Está fuera de alcance hasta **F3**
> (`docs/decisiones-nomina.md` §D6), pero el motor de cuotas (F1-03) debe producir el desglose
> **por empleado y por ramo** precisamente para que esa conciliación sea posible después.

---

## 2. Plazos de los movimientos afiliatorios

| Movimiento | Plazo | Fundamento |
|---|---|---|
| Alta / reingreso | **5 días hábiles** | Art. 15 fr. I LSS |
| Baja | **5 días hábiles** | ídem |
| Modificación de salario fijo | **5 días hábiles** siguientes al cambio | Art. 34 fr. I LSS |
| Modificación de la parte variable | primeros **5 días hábiles** de enero, marzo, mayo, julio, septiembre y noviembre | Art. 34 fr. II LSS |

**Multa por extemporaneidad: 20 a 350 UMA** (Art. 304-B LSS). Convertido con la UMA vigente
(`20_valores_referencia_2026.md` §1), en feb–dic de 2026 eso es **$2,346.20 a $41,058.50** por
infracción; en enero, con la UMA 2025, $2,262.80 a $39,599.00. Es importe **derivado**, no un
valor propio de este archivo.

> La prórroga del "viernes o día inhábil" del Art. 3 del RACERF **no aplica a los avisos
> afiliatorios**, solo al pago de cuotas. Ver `25_calendario_laboral_2026.md` §2.

---

## 3. Cambio regulatorio vigente: e.firma como único certificado

| Dato | Valor |
|---|---|
| Acuerdo | **ACDO.AS2.HCT.290626/176.P.DIR** del Consejo Técnico del IMSS (aprobado 29-jun-2026) |
| Publicación | **DOF 16-jul-2026** |
| Entrada en vigor | **17-jul-2026** |
| Qué hace | Reconoce la **e.firma del SAT** como **único** certificado digital válido para movimientos afiliatorios y para la vinculación de representantes legales; deja sin efectos el **NPIE** y el certificado digital expedido por el propio IMSS, y los acuerdos 43/2004 y 533/2006 |
| Transición | **90 días naturales**, hasta el **13-oct-2026** |

**Estado a la fecha de redacción (1-sep-2026): la transición está corriendo.**

> **Revisar después del 13-oct-2026.** Al vencer el periodo, el NPIE deja de funcionar sin red
> de seguridad. Cualquier feature de "presentar movimientos" asume e.firma vigente del patrón,
> con el contador operando como representante legal vinculado en el Escritorio Virtual. Si el
> IMSS prorroga el plazo, actualizar este renglón con el acuerdo nuevo.

---

## 4. Qué significa para el producto

- **Nada de esto requiere que el motor sea stateful.** El despacho manda empleados, cliente y
  periodo; la API devuelve desgloses. Igual que hoy manda `facturas[]`.
- **La chamba recurrente es el producto**: los pasos 3–5 y 7 son mensuales o bimestrales y hoy
  cuestan horas por cliente. La métrica de éxito es que un contador lleve N clientes con el
  tiempo que hoy le toma uno.
- **Presentar movimientos ante el IMSS (IDSE) y timbrar con PAC están fuera de alcance** hasta
  F3 (`docs/decisiones-nomina.md` §D6 y §D7). Lo que sí entra antes es **generar** los
  archivos y los cálculos que hoy se capturan a mano.

---

## Fuentes

- Ley del Seguro Social: Arts. 15, 34, 39, 304-B.
- RACERF: Art. 3.
- Acuerdo ACDO.AS2.HCT.290626/176.P.DIR del Consejo Técnico del IMSS — DOF 16-07-2026.
- `docs/PLAN_NOMINA.md` §2.3 y §2.8; `docs/decisiones-nomina.md` §D6, §D7.
