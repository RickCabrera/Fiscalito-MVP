# 21 · SBC / SDI y factor de integración

> **Documento de referencia, no fuente de cálculo.** El motor calcula desde
> `app/nomina_engine/integracion.py` y `app/constants.py`. Este archivo no es fuente de
> cálculo ni de tool calling.

**Alcance:** cómo se construye el Salario Base de Cotización (SBC), también llamado Salario
Diario Integrado (SDI), que es la base de casi todas las cuotas de
`22_cuotas_imss_infonavit_2026.md`.

---

## 1. Qué integra el SBC (Art. 27 LSS)

> "El salario base de cotización se integra con los pagos hechos en efectivo por cuota diaria,
> gratificaciones, percepciones, alimentación, habitación, primas, comisiones, prestaciones en
> especie y cualquiera otra cantidad o prestación que se entregue al trabajador por su
> trabajo." — Art. 27 LSS

El mismo artículo lista las **exclusiones** (con sus condiciones y topes): instrumentos de
trabajo, ahorro constituido por aportación igual de ambas partes, aportaciones patronales de
previsión social, cuotas del IMSS a cargo del patrón, PTU, alimentación y habitación cobradas
al trabajador, despensas hasta el **40 % de la UMA**, premios de asistencia y puntualidad
hasta el **10 % del SBC** cada uno, tiempo extra dentro de los límites de la LFT.

**Consecuencia de diseño:** el motor **no** decide por su cuenta qué integra. Cada percepción
adicional se modela como `ConceptoIntegrable{monto_diario, integra: bool}` y el catálogo de
qué integra vive en datos, no en `if`s.

---

## 2. Fórmula

```
SBC = salario_diario × factor_integracion
      + Σ conceptos_integrables_fijos (diarios)
      + promedio de percepciones variables (si aplica)

SBC = clamp(SBC, piso, tope)
```

**Piso = 1 salario mínimo de la zona; tope = 25 UMA (Art. 28 LSS).** Los importes y las
cuatro combinaciones vigentes (enero vs feb–dic × general vs ZLFN) están en
`20_valores_referencia_2026.md` §3 — **este archivo no los duplica** a propósito: un solo
lugar con los números es lo que evita que se desincronicen.

---

## 3. Factor de integración

```
factor = 1 + (dias_aguinaldo / 365) + (dias_vacaciones × prima_vacacional / 365)
```

Con **prestaciones mínimas de ley** (aguinaldo 15 días, LFT Art. 87; vacaciones LFT Art. 76
reformado; prima vacacional 25 %, LFT Art. 80):

| Años de servicio | Aguinaldo | Vacaciones | Prima vac. | Factor |
|---|---|---|---|---|
| 1 | 15 | 12 | 25 % | **1.0493** |
| 2 | 15 | 14 | 25 % | 1.0507 |
| 3 | 15 | 16 | 25 % | 1.0521 |
| 4 | 15 | 18 | 25 % | 1.0534 |
| 5 | 15 | 20 | 25 % | 1.0548 |
| 6–10 | 15 | 22 | 25 % | 1.0562 |
| 11–15 | 15 | 24 | 25 % | 1.0575 |
| 16–20 | 15 | 26 | 25 % | 1.0589 |
| 21–25 | 15 | 28 | 25 % | 1.0603 |
| 26–30 | 15 | 30 | 25 % | 1.0616 |
| 31–35 | 15 | 32 | 25 % | 1.0630 |

Vigencia de la tabla: escala de vacaciones vigente desde el **1-ene-2023** (reforma
"vacaciones dignas", DOF 27-12-2022). Fuente de los días: LFT Arts. 76, 80 y 87. Los factores
son aritmética directa de la fórmula, verificable con `1 + 15/365 + dias×0.25/365`.

> ⚠️ **La tabla es material de test, no de producción.** El motor calcula el factor desde
> `(dias_aguinaldo, dias_vacaciones, prima_vacacional)` porque muchas empresas otorgan
> prestaciones superiores a la ley (30 días de aguinaldo, prima del 50 %, vales, fondo de
> ahorro). La tabla sirve para que F1-02 verifique el caso "mínimo de ley".

> ⚠️ **El caso real no es mínimo de ley.** Ver `docs/decisiones-nomina.md` §D9: en las
> fixtures de S-04 los factores implícitos son superiores a los de ley, distintos entre
> empleados y no derivables de la antigüedad. Por eso el `SalarioDiarioIntegrado` **se toma
> como dato de entrada** cuando viene del CFDI; recomputarlo desde la antigüedad diverge del
> caso real.

---

## 4. Tipos de salario (Art. 30 LSS)

| Tipo | Cómo se determina el SBC | Fundamento |
|---|---|---|
| **Fijo** | Conocido por adelantado: `salario_diario × factor + percepciones fijas integrables` | Art. 30 fr. I LSS |
| **Variable** | Promedio: `Σ percepciones variables del bimestre anterior ÷ días de salario devengado en ese bimestre`. En alta nueva se estima | Art. 30 fr. II LSS |
| **Mixto** | `parte fija × factor + promedio de la parte variable del bimestre anterior` | Art. 30 fr. III LSS |

---

## 5. Avisos de modificación de salario (Art. 34 LSS)

| Caso | Plazo | Fundamento |
|---|---|---|
| Salario fijo que cambia | **5 días hábiles** siguientes al cambio | Art. 34 fr. I |
| Parte variable | Primeros **5 días hábiles de enero, marzo, mayo, julio, septiembre y noviembre** (bimestral) | Art. 34 fr. II |
| Salario mixto | La parte fija al cambiar; la variable, bimestral | Art. 34 fr. III |

Altas, bajas y reingresos: **≤ 5 días hábiles** (Art. 15 fr. I LSS). Multas por
extemporaneidad: **20 a 350 UMA** (Art. 304-B LSS). Ver
`26_flujo_despacho_idse_sua_ema.md`.

> El aviso bimestral de variables es trabajo recurrente y automatizable: en cada bimestre par
> el sistema debe poder listar, por cliente, los empleados variables/mixtos con su SBC nuevo.
> `requiere_aviso(...)` con su fecha límite es parte de F1-02.

---

## 6. Días cotizados

El periodo **no** son siempre 30 o 31 días. Los ausentismos e incapacidades reducen los días
cotizados, y el efecto **difiere por ramo**. El tratamiento adoptado (Art. 31 LSS, marcado
**PROVISIONAL** hasta confirmar con la contadora) está en `docs/decisiones-nomina.md` §D3.
`dias_cotizados` es siempre **input** del motor, nunca un supuesto.

---

## Fuentes

- Ley del Seguro Social: Arts. 15, 27, 28, 30, 31, 34, 304-B.
- Ley Federal del Trabajo: Arts. 76, 80, 87 (escala de vacaciones vigente desde 1-ene-2023,
  reforma DOF 27-12-2022).
- `docs/PLAN_NOMINA.md` §2.2 y §2.3; `docs/decisiones-nomina.md` §D3, §D5, §D9.
