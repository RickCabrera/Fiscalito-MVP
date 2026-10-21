# Actualización, recargos, IVA completo e ISN (P3-02, P3-03, P3-07, P3-08)

Referencia de las fuentes consultadas al construir los motores. Los valores que calculan
viven en `app/fiscal_engine/datos/*.csv` y en los docstrings; esto es la bitácora.

## Actualización y recargos (`fiscal_engine/actualizacion.py`)

- **Art. 17-A CFF**: factor = INPC del mes anterior al más reciente / INPC del mes anterior
  al más antiguo; < 1 → 1; INPC no publicado → último publicado; factores "hasta el
  diezmilésimo" (último párrafo). Consultado en mley.mx/CFF/articulo/17-a y sdv.com.mx.
- **Art. 21 CFF**: recargos por cada mes o fracción, sobre el monto actualizado, tasa de mora =
  prórroga de la LIF + 50 %, hasta cinco años. mley.mx/CFF/articulo/21.
- **Art. 20 CFF**: INPC del INEGI publicado en el DOF; pago ajustado a pesos (1-50 ¢ baja,
  51-99 ¢ sube).
- **Art. 44 RCFF**: contribución actualizada "hasta centavos".
- **Art. 12 CFF**: días inhábiles y prórroga al siguiente hábil.
- **LIF 2026 art. 11**: prórroga 1.38 %, plazos ≤ 12 m 1.42 %, 12-24 m 1.63 %, > 24 m o
  diferido 1.97 % (mley.mx/LIF_2026/articulo/11; resumen AMCP). Mora 2026 = 2.07 %.
- **2020-2025**: prórroga 0.98 % (mora 1.47 %) — fuente secundaria (sdv.com.mx,
  elcontribuyente.mx); el texto de la LIF de cada año NO se consultó → FUENTE POR CONFIRMAR.
- **Ejemplo de referencia**: sdv.com.mx/herramientas/calculadora-recargos — $25,000,
  INPC 145.169 / 143.588 → $25,275.27 (cociente sin cortar). Con el factor truncado 1.0110 el
  motor da $25,275.00. **Truncar vs redondear el factor** es criterio del despacho (DP-3),
  default `truncar`, FUENTE POR CONFIRMAR.

## INPC (`datos/inpc.csv`)

Serie ene-2020 a sep-2026, base 2Q jul-2018 = 100. Nueve meses cotejados contra boletines del
INEGI (dic-2024, jun-2025, dic-2025, ene, mar, jun, jul, ago y sep 2026); el resto de dos
tablas secundarias que coinciden al milésimo (elcontribuyente.mx, idconline.mx) → FUENTE POR
CONFIRMAR contra el DOF/BIE.

## IVA (`fiscal_engine/iva.py`)

LIVA Arts. 1o.-A, 1o.-B, 4o.-A, 5o. fr. III, IV y V c), 5o.-B, 5o.-C, 6o. (mley.mx/LIVA/articulo/6,
sdv.com.mx/compendio/ley-iva/articulo-5; texto vigente en
diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf). Estímulo región fronteriza (8 %) prorrogado al
31-dic-2026 por decreto DOF 31-dic-2025 (tradelawcollege.edu.mx).

- **Proporción (B4 del revisor de motor)**: desde 2022 el Art. 5o. fr. V c) incluye en el
  valor total "los actos o actividades a que se refiere el artículo 4o.-A" (no objeto: no
  realizados en territorio nacional y distintos del Art. 1o. realizados en él). El motor los
  suma al denominador (`valor_no_objeto_en_proporcion`).
- **Art. 5o.-C** (consultado): no entran al valor de los actos I importaciones; II activo fijo,
  cargos diferidos y terrenos; III dividendos (salvo actividad preponderante); IV acciones,
  partes sociales y títulos de crédito; V moneda y piezas de oro o plata; VI intereses y
  ganancia cambiaria; VII arrendamiento financiero; VIII bienes adjudicados; IX derivados;
  X certificados de participación inmobiliaria no amortizables. El CFDI no distingue estos
  conceptos: el despacho excluye por UUID (`iva_no_objeto_excluidos`). Default: todo el no
  objeto cobrado entra (conservador: acredita menos).
- **Art. 5o.-B** es la opción de la proporción del año anterior (antes se citaba como 5o.-C
  por error; corregido).

## ISN (`fiscal_engine/isn.py`, `datos/isn.csv`)

Veracruz verificado: Código Financiero arts. 98-103 (tasa 3 %, art. 101) y adicional para el
fomento de la educación 15 % (arts. 134-135), texto en leyes-mx.com. **Premios de puntualidad
(010) y asistencia (049)**: el art. 103 fr. I inciso n) sólo exenta los que se pagan en forma
ANUAL; el CFDI no lo dice → gravan por default (B1 del revisor de motor). Si al despacho le
consta que son anuales, los excluye por cliente (`isn_claves_excluidas` = 010, 049); Congreso mantiene el 3 %
en 2026 (elcongresista.mx). Otras 13 entidades con artículo citado por satfacil.com.mx; las 18
restantes sólo con tablas secundarias coincidentes → FUENTE POR CONFIRMAR (ver CSV).

## Calculadoras laborales (`fiscal_engine/calculadoras_laborales.py`)

LFT 50, 76, 79, 80, 87, 123, 127 fr. IX, 162, 486; LISR 93 fr. XIII y XIV, 95, 96, 113-E,
113-J (mley.mx). Versión mínima: P4 la reemplaza. El Art. 174 RLISR no se pudo consultar.

## Verificación de índices y tasas (O12)

La columna `verificacion` de cada CSV dice qué está verificado:

| CSV | Verificado | Por confirmar |
|---|---|---|
| `datos/inpc.csv` | `boletin_inegi` | `secundaria_coincidente` |
| `datos/recargos.csv` | `ley` (LIF citada) | `secundaria` (2020-2025) |
| `datos/isn.csv` | `ley_citada` | `secundaria` |

Todo resultado que usa un valor no verificado lo dice: `por_confirmar: true` y
`fuentes_por_confirmar` (una línea por índice o tasa) en la calculadora de actualización, en
cada renglón y en el total del resumen de impuestos, en los pagos provisionales y la anual de
personas morales (factores INPC de pérdidas y ajuste por inflación) y en el ISN. La pantalla
lo pinta con `AvisoPorConfirmar`.

## Decisiones provisionales (O10)

1. **Actualización y recargos sobre el NETO después de compensaciones y subsidio**
   (`resumen_impuestos.py`). Lectura: el Art. 23 CFF extingue la contribución hasta por el
   monto compensado, y el Art. 21 causa recargos sobre "las contribuciones omitidas"
   actualizadas. Si la contadora compensa después de actualizar, se ajusta (DP-3).
   DECISIÓN PROVISIONAL.
2. **El saldo a favor de IVA arrastrado no se actualiza por inflación** (`iva.py`). El Art. 6o.
   LIVA no lo prohíbe y el Art. 17-A CFF permite actualizarlo; no hacerlo acredita de menos
   (conservador). DECISIÓN PROVISIONAL.
3. **"Compensación" del saldo a favor de IVA se trata como devolución** (`iva.py`): el saldo
   deja de arrastrarse completo. Desde 2019 no existe la compensación universal (LIF 2019
   art. 25 fr. VI y la reforma al Art. 6o. LIVA: el saldo sólo se acredita contra el IVA a
   cargo de meses siguientes o se pide en devolución); compensar contra otras contribuciones
   ya no procede salvo los casos del Art. 23 CFF (mismo impuesto, adeudo propio). Se ofrece la
   opción porque hay despachos que la usan para saldos anteriores; el motor nunca la aplica
   contra otro impuesto. DECISIÓN PROVISIONAL, FUENTE POR CONFIRMAR con la contadora.
