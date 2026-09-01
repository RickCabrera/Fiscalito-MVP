# 24 · CFDI de nómina — complemento 1.2 sobre CFDI 4.0

> **Documento de referencia, no fuente de cálculo.** El XML lo genera
> `app/nomina_engine/cfdi_nomina_xml.py` (tarea F1-05). Este archivo no es fuente de cálculo
> ni de tool calling.

> 🔒 **Todos los identificadores de este archivo son sintéticos.** RFC genérico
> `XAXX010101000`, CURP de ejemplo `AAAA010101HDFXXX01`, NSS `00000000000`, registro
> patronal `X0000000000`. Nunca se copian datos de `03. CFDI DE NOMINA/` ni de las fixtures
> reales, aunque estén anonimizadas.

**Alcance:** qué nodos y catálogos componen un recibo timbrable, para que el XML generado sea
estructuralmente válido. **En el MVP no se timbra** (`docs/decisiones-nomina.md` §D7: PAC
fuera de alcance hasta F3); se genera el "pre-recibo" y se valida contra XSD.

---

## 1. Vigencia de la versión

| Elemento | Versión | Vigencia | Fuente |
|---|---|---|---|
| Comprobante | CFDI **4.0** | obligatoria desde 1-abr-2023 | Anexo 20 RMF |
| Complemento de nómina | **1.2**, revisión C | vigente | Guía de llenado del complemento de nómina 1.2 (SAT) |
| Catálogos (`c_TipoPercepcion`, etc.) | catálogos del Anexo 20 | se actualizan sin cambiar la versión | Portal del SAT, `catCFDI` |

`TipoDeComprobante = N` (nómina). El nodo `Nomina` cuelga de `Complemento`.

---

## 2. Nodos que el generador debe llenar

**Comprobante:** `Fecha`, `FormaPago = 99`, `MetodoPago = PUE`, `Moneda = MXN`,
`TipoDeComprobante = N`, `LugarExpedicion` (CP del patrón), `Exportacion = 01`,
`SubTotal` (= total de percepciones + otros pagos), `Descuento` (= total de deducciones),
`Total` (= neto pagado).

**Emisor (patrón):** `Rfc`, `Nombre`, `RegimenFiscal`, y en el nodo `Nomina/Emisor` el
`RegistroPatronal` (y `RfcPatronOrigen` si hay subcontratación o sustitución patronal).

**Receptor (trabajador):** `Rfc`, `Nombre`, `DomicilioFiscalReceptor` (CP),
`RegimenFiscalReceptor = 605`, `UsoCFDI = CN01`. En `Nomina/Receptor`:
`Curp`, `NumSeguridadSocial`, `FechaInicioRelLaboral`, `Antigüedad` (formato ISO 8601
`P##W` o `P##D`), `TipoContrato`, `TipoRegimen = 02` (sueldos y salarios), `NumEmpleado`,
`Departamento`, `Puesto`, `RiesgoPuesto` (clase I–V del patrón), `PeriodicidadPago`,
`SalarioBaseCotApor` (SBC), `SalarioDiarioIntegrado` (SDI), `ClaveEntFed`.

**Nomina:** `TipoNomina` (`O` ordinaria / `E` extraordinaria), `FechaPago`,
`FechaInicialPago`, `FechaFinalPago`, `NumDiasPagados` (fraccionable por faltas o
incapacidades), `TotalPercepciones`, `TotalDeducciones`, `TotalOtrosPagos`.

> `ClaveEntFed = VER` para el patrón del caso real (`docs/decisiones-nomina.md` §D8).
> `SalarioBaseCotApor` y `SalarioDiarioIntegrado` salen del motor de
> `21_sbc_integracion.md`; para el caso real el SDI es **dato de entrada** (§D9).

---

## 3. Catálogos: las claves que este dominio usa

**Fuente de las tres tablas:** catálogos del complemento de nómina publicados por el SAT
(`catNomina` del Anexo 20), consultados en septiembre de 2026. Son **catálogos vivos**: el SAT
agrega claves sin cambiar la versión 1.2 del complemento — en 2026 se incorporaron claves de
percepción y deducción para días de descanso laborados. El generador debe validar contra el
catálogo descargado, no contra esta lista.

**`c_TipoPercepcion`** — cada percepción se parte en `ImporteGravado` / `ImporteExento` según
las exenciones del Art. 93 LISR (`23_isr_nomina_subsidio.md`):

| Clave | Percepción | Nota |
|---|---|---|
| 001 | Sueldos, salarios, rayas y jornales | base del recibo ordinario |
| 002 | Gratificación anual (aguinaldo) | exento hasta 30 UMA |
| 003 | Participación de los trabajadores en las utilidades (PTU) | exento hasta 15 UMA |
| 005 | Fondo de ahorro | integra o no al SBC según Art. 27 fr. II LSS |
| 010 | Premios por puntualidad | **100 % gravado** |
| 019 | Horas extra | ver el desdoble del Art. 93 fr. I |
| 020 | Prima dominical | exento hasta 1 UMA por domingo |
| 021 | Prima vacacional | exento hasta 15 UMA |
| 029 | Vales de despensa | previsión social, con tope propio |
| 038 | Otros ingresos por salarios | cajón de sastre; evitarlo si hay clave específica |
| 049 | Premios por asistencia | **100 % gravado** |

**`c_TipoDeduccion`:**

| Clave | Deducción | Nota |
|---|---|---|
| 001 | Seguridad social | cuota obrera del IMSS |
| 002 | ISR | la retención del recibo |
| 004 | **Otros** | es literalmente "Otros"; el fondo de ahorro se reporta aquí **porque** no tiene clave propia de deducción, no porque la clave se llame fondo de ahorro |
| 006 | Descuento por incapacidad | |
| 010 | Pago de crédito de vivienda | amortización Infonavit |
| 020 | Ausencia (ausentismo) | se refleja también en `dias_cotizados` |

**`c_TipoOtroPago`:**

| Clave | Otro pago |
|---|---|
| 001 | Reintegro de ISR pagado en exceso |
| **002** | **Subsidio para el empleo** |
| 003 | Viáticos (entregados al trabajador) |
| 004 | Aplicación de saldo a favor por compensación anual |
| 007 | ISR ajustado por subsidio |
| 999 | Pagos distintos a los listados |

> ⚠️ **El subsidio y su clave 002.** Va en **OtrosPagos**, con el nodo hijo
> `SubsidioAlEmpleo` y su atributo `SubsidioCausado`. Desde 2024, con el subsidio
> acreditándose solo hasta agotar el ISR, el importe entregado suele ser **$0.00** mientras el
> `SubsidioCausado` sí lleva monto. La descripción de la clave habla del subsidio
> *efectivamente entregado*, lo que choca con un esquema donde ya no se entrega nada: **cómo
> timbrarlo sin rechazo es pregunta para la Guía de llenado vigente y para la contadora**,
> anotada como decisión abierta en `docs/nocturno-log.md`. No es una decisión del código.

## 4. Periodicidades (`c_PeriodicidadPago`)

**Fuente:** catálogo `c_PeriodicidadPago` del SAT.

| Clave | Periodicidad | Días base |
|---|---|---|
| 01 | Diaria | 1 |
| 02 | Semanal | 7 |
| 03 | Catorcenal | 14 |
| 04 | Quincenal | 15 |
| 05 | Mensual | 30 |
| 06 | Bimestral | 60 |
| 07 | Unidad de obra | — |
| 10 | Decenal | 10 |
| 99 | Otra periodicidad | — |

> Las claves **no son los días**. `07` es *unidad de obra*, no "semanal de 7 días": ese error
> produce un XML que timbra con la periodicidad equivocada. La clave de semanal es **02**.

La periodicidad determina qué tarifa de ISR aplica (`23_isr_nomina_subsidio.md` §3) y cómo se
prorratea el subsidio. El caso real de S-04 es **semanal**.

---

## 5. Validación sin timbrar

- El XSD del complemento nómina 1.2 y el de CFDI 4.0 se versionan **offline** en
  `apps/api/tests/xsd/` para que el CI valide sin red (tarea **F1-05**).
- La validación XSD es de **estructura**, no de sello: las fixtures de S-04 llevan sellos
  sintéticos y son criptográficamente inverificables por diseño. Un XML que valida contra el
  XSD no está timbrado ni es fiscalmente válido.
- El criterio de aceptación de F1-05 es doble: valida contra el XSD **y** sus totales cuadran
  con el timbrado original del caso real.

---

## Fuentes

- Guía de llenado del comprobante del recibo de pago de nómina, complemento 1.2 (SAT).
- Catálogos del complemento de nómina (`catNomina`, Anexo 20) — SAT, consultados sep-2026.
- Anexo 20 de la RMF — estándar del CFDI 4.0 y catálogos (`catCFDI`).
- LISR Arts. 93 y 96 para el gravado/exento de cada percepción.
- `docs/PLAN_NOMINA.md` §2.7; `docs/decisiones-nomina.md` §D7, §D8, §D9.
