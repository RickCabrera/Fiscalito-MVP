# Decisiones de nómina

Cierra **F0-03**. Cada entrada es una decisión tomada para desbloquear F1. Las marcadas
**PROVISIONAL** están pendientes de confirmación con la contadora: si su respuesta difiere,
se corrige aquí y en el código que la cite.

En modo autónomo este archivo es la fuente de verdad para decisiones que dependen del mundo.
Si una decisión no está cubierta aquí, se toma la opción más conservadora y se marca en el
código con `# DECISIÓN PROVISIONAL (nocturno):`.

## D1 · ISR periódico

Usar las tablas del **Anexo 8 de la RMF 2026** según la periodicidad del CFDI (en el caso
real, semanal). Validar contra el ISR retenido de las fixtures de S-04; si no cuadra, probar
el prorrateo de la tabla mensual y documentar aquí cuál de los dos cuadró.

## D2 · Redondeo

Por concepto y por empleado, a **2 decimales**, al estilo SUA. Validar contra las fixtures.

## D3 · Ausentismos e incapacidades — PROVISIONAL

Aplicar el **Art. 31 LSS** literal: las ausencias de hasta 7 días al mes descuentan días en
todos los ramos **excepto Enfermedades y Maternidad**; durante una incapacidad solo se cotiza
EyM. Confirmar con la contadora.

## D4 · Quirk CEAV 2026 — PROVISIONAL

Aplicar la tabla literal por rango de UMA. El salario mínimo exacto cae en **3.150%**. Los
renglones inalcanzables se dejan en la tabla, sin lógica especial que los excluya.

## D5 · Prestaciones superiores a las de ley

Modelar vía `ConceptoIntegrable`. El default es el **mínimo de ley**.

## D6 · EMA / EBA

**Fuera de alcance hasta F3.**

## D7 · Timbrado con PAC

**Fuera de alcance hasta F3.**

## D8 · Entidad federativa

El patrón del caso real es de **Veracruz**: `ClaveEntFed=VER` en el CFDI. El **ISN del 3% es
solo informativo** — no se calcula en F1.
