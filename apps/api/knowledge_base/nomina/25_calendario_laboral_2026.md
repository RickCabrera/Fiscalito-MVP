# 25 · Calendario de obligaciones patronales 2026

> **Documento de referencia, no fuente de cálculo.** Las fechas las genera
> `app/nomina_engine/calendario_laboral.py` (tarea F1-06), fusionable con el calendario SAT
> de `app/fiscal_engine/calendario.py`. Este archivo no es fuente de cálculo ni de tool
> calling.

**Vigencia:** ejercicio **2026**. Las fechas se recalculan cada año; la regla que las produce
es permanente.

---

## 1. Qué se paga y cada cuándo

| Periodicidad | Ramos | Fundamento |
|---|---|---|
| **Mensual**, a más tardar el 17 del mes siguiente | Riesgos de Trabajo, Enfermedades y Maternidad, Invalidez y Vida, Guarderías y Prestaciones Sociales | Art. 39 LSS |
| **Bimestral**, a más tardar el 17 del mes siguiente al bimestre | Retiro, CEAV, Infonavit y amortizaciones de crédito Infonavit | Art. 39 LSS; Ley Infonavit Art. 35 |

Los porcentajes de cada ramo están en `22_cuotas_imss_infonavit_2026.md`.

**Medio de pago:** se autodetermina en el **SUA** (Sistema Único de Autodeterminación) y se
paga con la línea de captura de **SIPARE**, en portal bancario o ventanilla.

---

## 2. La regla del día límite (incluye el viernes)

> Cuando el último día del plazo sea **inhábil o viernes**, el plazo se prorroga al siguiente
> día hábil. **Esta prórroga NO aplica a la presentación de avisos afiliatorios**
> (altas, bajas, modificaciones de salario).
> — Art. 3 del RACERF (Reglamento de la LSS en materia de Afiliación, Clasificación de
> Empresas, Recaudación y Fiscalización).

Que el **viernes** también corra es específico del IMSS y distinto de la regla del SAT. Un
motor que solo mueva sábados y domingos produce **dos fechas mal en 2026**: las cuotas de
marzo y las de junio, que vencen en viernes y se corren al lunes.

> **Convención de este archivo:** cada obligación se nombra por el **mes de las cuotas**, no
> por el mes en que vence. "Las cuotas de marzo" vencen en abril. La tabla de §3 lleva las dos
> columnas para que no haya ambigüedad.

---

## 3. Fechas límite 2026

| Cuotas de | Día 17 cae en | Fecha límite | Tipo |
|---|---|---|---|
| Enero | martes 17-feb | **17-feb-2026** | Mensual |
| Febrero | martes 17-mar | **17-mar-2026** | Mensual + bimestral (ene-feb) |
| Marzo | **viernes** 17-abr | **20-abr-2026** (lunes) | Mensual |
| Abril | **domingo** 17-may | **18-may-2026** (lunes) | Mensual + bimestral (mar-abr) |
| Mayo | miércoles 17-jun | **17-jun-2026** | Mensual |
| Junio | **viernes** 17-jul | **20-jul-2026** (lunes) | Mensual + bimestral (may-jun) |
| Julio | lunes 17-ago | **17-ago-2026** | Mensual |
| Agosto | jueves 17-sep | **17-sep-2026** | Mensual + bimestral (jul-ago) |
| Septiembre | **sábado** 17-oct | **19-oct-2026** (lunes) | Mensual |
| Octubre | martes 17-nov | **17-nov-2026** | Mensual + bimestral (sep-oct) |
| Noviembre | jueves 17-dic | **17-dic-2026** | Mensual |
| Diciembre | **domingo** 17-ene-2027 | **18-ene-2027** (lunes) | Mensual + bimestral (nov-dic) |

**Cinco** de las doce fechas se corren, todas por la regla del §2 y ninguna por excepción
discrecional: las cuotas de **marzo** (viernes → lunes 20-abr), **abril** (domingo → lunes
18-may), **junio** (viernes → lunes 20-jul), **septiembre** (sábado → lunes 19-oct) y
**diciembre** (domingo → lunes 18-ene-2027). Los días de descanso obligatorio de la
LFT (Art. 74) pueden correr una fecha más — el generador debe considerarlos, no solo el día
de la semana.

---

## 4. Otras obligaciones fijas del año

| Obligación | Cuándo | Fundamento |
|---|---|---|
| **Declaración Anual de Prima de Riesgo de Trabajo** | durante **febrero** (a más tardar el último día) | Art. 74 LSS; Art. 32 RACERF |
| **Aviso de modificación de la parte variable del SBC** | primeros **5 días hábiles** de enero, marzo, mayo, julio, septiembre y noviembre | Art. 34 fr. II LSS |
| **PTU — personas morales** | dentro de los 60 días siguientes a la declaración anual, a más tardar el **30 de mayo** | LFT Art. 122 |
| **PTU — personas físicas** | mismo plazo desde su anual, a más tardar el **29 de junio** | LFT Art. 122 |
| **Aguinaldo** | antes del **20 de diciembre** | LFT Art. 87 |
| **Entero del ISR retenido de salarios** | día 17 del mes siguiente, con el ajuste del sexto dígito del RFC | LISR Art. 96; RMF |
| **ISN (Impuesto Sobre Nómina)** | estatal, típicamente mensual el día 10 o 17 según la entidad | Códigos financieros estatales |

**ISN:** es estatal y varía (aprox. 2–4 %; Veracruz 3 %, CDMX 4 %). Para el caso real es
**informativo, no se calcula en F1** (`docs/decisiones-nomina.md` §D8). En el calendario sí
aparece como vencimiento.

> El entero del ISR retenido cae el mismo día 17 que las cuotas mensuales del IMSS, **pero se
> rige por la regla del SAT** (sexto dígito del RFC, sin la prórroga del viernes). Son dos
> calendarios distintos que se ven iguales: fusionarlos en una sola vista por cliente sin
> distinguir su regla es un bug esperando.

---

## Fuentes

- Ley del Seguro Social: Arts. 34, 39, 74.
- RACERF: Arts. 3 (cómputo del plazo) y 32 (prima de RT).
- Ley del Infonavit: Art. 35.
- Ley Federal del Trabajo: Arts. 74, 87, 122.
- LISR Art. 96 (entero de retenciones).
- `docs/PLAN_NOMINA.md` §2.5; `docs/decisiones-nomina.md` §D8.
