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

LIVA Arts. 1o.-A, 1o.-B, 5o. fr. III, IV y V c), 5o.-B, 5o.-C, 6o. (mley.mx/LIVA/articulo/6,
sdv.com.mx/compendio/ley-iva/articulo-5). Estímulo región fronteriza (8 %) prorrogado al
31-dic-2026 por decreto DOF 31-dic-2025 (tradelawcollege.edu.mx). La lista de conceptos que
el Art. 5o.-C excluye del valor de actos NO se consultó: no se aplica (FUENTE POR CONFIRMAR).

## ISN (`fiscal_engine/isn.py`, `datos/isn.csv`)

Veracruz verificado: Código Financiero arts. 98-103 (tasa 3 %, art. 101) y adicional para el
fomento de la educación 15 % (arts. 134-135), texto en leyes-mx.com; Congreso mantiene el 3 %
en 2026 (elcongresista.mx). Otras 13 entidades con artículo citado por satfacil.com.mx; las 18
restantes sólo con tablas secundarias coincidentes → FUENTE POR CONFIRMAR (ver CSV).

## Calculadoras laborales (`fiscal_engine/calculadoras_laborales.py`)

LFT 50, 76, 79, 80, 87, 123, 127 fr. IX, 162, 486; LISR 93 fr. XIII y XIV, 95, 96, 113-E,
113-J (mley.mx). Versión mínima: P4 la reemplaza. El Art. 174 RLISR no se pudo consultar.
