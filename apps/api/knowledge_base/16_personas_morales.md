# 16 · Personas morales (601) y RESICO PM — pagos provisionales y anual (P3-01, P3-06)

Motor: `app/fiscal_engine/personas_morales.py`. Armado desde bóveda/contabilidad:
`app/impuestos/personas_morales.py`. Anual y papeles: `app/impuestos/anual.py`, `papeles.py`.

## Fuentes legales (texto vigente, Cámara de Diputados: diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf)

| Tema | Artículo | Lo que usa el motor |
|---|---|---|
| Tasa y utilidad fiscal | LISR Art. 9 | 30 % sobre el resultado fiscal; utilidad fiscal = ingresos acumulables − deducciones autorizadas − PTU pagada en el ejercicio (fr. I); menos pérdidas pendientes (fr. II); renta gravable de PTU sin disminuir PTU pagada ni pérdidas; anual dentro de los tres meses siguientes al cierre |
| Pagos provisionales | LISR Art. 14 | fr. I: coeficiente = utilidad fiscal del último ejercicio de 12 meses (+ anticipos Art. 94 fr. II) ÷ ingresos nominales del mismo ejercicio; si no hay, el último que lo tenga, no más de 5 años atrás. fr. II: coeficiente × ingresos nominales acumulados; PTU pagada en partes iguales de mayo a diciembre, sin exceder la utilidad; pérdidas. Ingresos nominales = acumulables sin el ajuste anual por inflación acumulable. fr. III: tasa Art. 9, menos pagos anteriores y retenciones del Art. 54 |
| Ajuste anual por inflación | LISR Arts. 44, 45, 46 | Saldo promedio = suma de saldos al último día de cada mes ÷ meses; deudas > créditos → acumulable; créditos > deudas → deducible; factor = INPC último mes del ejercicio ÷ INPC último mes del anterior − 1 |
| Pérdidas | LISR Art. 57 | 10 ejercicios; 1a actualización jul→dic del ejercicio de la pérdida; siguientes desde la última hasta junio del ejercicio en que se aplica; la pérdida se aumenta con la PTU pagada |
| RESICO PM | LISR Arts. 206-215 (Título VII, Cap. XII) | 206 sujetos (≤ 35 MDP); 207 ingresos efectivamente percibidos (incluye anticipos); 208 deducciones; 209 inversiones; 210 requisitos (efectivamente erogadas); **211 pagos provisionales** (percibido − erogado − PTU pagada − pérdidas, × Art. 9, − pagos anteriores − retenciones Art. 54); **212 anual** (Art. 9; pérdida = deducciones − ingresos + PTU) |
| Factores al diezmilésimo | CFF Art. 17-A último párrafo | Coeficiente, factores de actualización y factor de ajuste anual; corte según `modo_factor` del cliente (default truncar) |
| Pago en pesos | CFF Art. 20 | `a_pagar_pesos` |
| Anual PF | LISR Arts. 150, 152; 113-F (RESICO PF) | Tarifa anual (Anexo 8 RMF 2026); RESICO PF anual 1.00 %–2.50 % hasta 3.5 MDP |
| Calendario | LISR Arts. 9 y 76 fr. V; 150 | PM: 31 de marzo; PF: abril |
| INPC | INEGI, `app/fiscal_engine/datos/inpc.csv` | Serie versionada con trazabilidad por fila |

Páginas consultadas (secundarias, para los casos de prueba):

- siemprealdia.co, "Coeficiente de utilidad: ¿Cómo determinarlo y aplicarlo en pagos
  provisionales de ISR?" — coeficiente 2,700,000 / 12,150,000 = 0.2222; pago de marzo 65,330.
- contadormx.com, "Cálculo del ajuste anual por inflación acumulable o deducible" — 1,125 y 1,575.
- idconline.mx, "Actualización de pérdidas fiscales en la anual de personas morales 2022" —
  método dic/jul y jun/última actualización.
- mley.mx (LISR arts. 206-212) — contenido de cada artículo de RESICO PM.

## Decisiones (DECISIÓN PROVISIONAL) y FUENTE POR CONFIRMAR

1. **Pérdidas en pagos provisionales**: enero-junio con su última actualización; julio en
   adelante actualizadas a junio. La ley sólo regula la actualización para la anual.
   FUENTE POR CONFIRMAR (contadora / RLISR).
2. **PTU pagada después de mayo**: los octavos acumulados empiezan a restarse en el mes del pago.
3. **Lista de créditos y deudas por código agrupador** (Arts. 45-46): default documentado en
   `app/impuestos/personas_morales.py`, configurable por cliente. FUENTE POR CONFIRMAR contra
   las exclusiones exactas del texto vigente (caja, socios, empleados, anticipos, ISR propio).
4. **RESICO PM sin ajuste anual por inflación** salvo `aai_en_resico`: los Arts. 206-215 no
   remiten al Art. 44. FUENTE POR CONFIRMAR.
5. **PTU a repartir 10 %**: Resolución de la Comisión Nacional para la PTU (DOF 03/02/2009).
   FUENTE POR CONFIRMAR contra la resolución vigente. El tope individual (LFT Art. 127 fr. VIII)
   es de P4.
6. **Bóveda como fuente sin contabilidad**: ingresos por fecha de emisión (Art. 17), notas de
   crédito restan, nómina deducible = gravado + 47 % del exento (Art. 28 fr. XXX, configurable
   a 53 %), UsoCFDI D01-D10/S01/CN01 no deducible, I01-I08 a la deducción de inversiones
   capturada. No distingue costo de lo vendido (Art. 39) de compras.
7. **Contabilidad**: la depreciación contable (504.07-504.24, 613, 614), la PTU (607, 610), el
   ISR (611) y los no deducibles (612, x.83/x.81) no se deducen; la deducción fiscal de
   inversiones se captura. La cuenta 213 puede incluir ISR propio por pagar (no es deuda, Art. 46).
8. **Coeficiente de utilidad**: con la utilidad fiscal del Art. 9 (ya neta de PTU), como dice
   el Art. 14 fr. I; no se actualiza (el artículo no lo prevé).
9. Primer ejercicio sin coeficiente: no hay pagos provisionales (Art. 14 fr. I); el primer
   pago del segundo ejercicio (enero-marzo) no se modela aparte.
