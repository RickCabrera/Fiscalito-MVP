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

**`c_TipoPercepcion`** — cada percepción se parte en `ImporteGravado` / `ImporteExento` según
las exenciones del Art. 93 LISR (`23_isr_nomina_subsidio.md`):

| Clave | Percepción |
|---|---|
| 001 | Sueldos, salarios, rayas y jornales |
| 002 | Gratificación anual (aguinaldo) |
| 003 | Participación de los trabajadores en las utilidades (PTU) |
| 019 | Horas extra |
| 020 | Prima dominical |
| 021 | Prima vacacional |
| 029 | Vales de despensa |
| 049 | Ajuste al neto (cuando aplica) |

**`c_TipoDeduccion`:**

| Clave | Deducción |
|---|---|
| 001 | Seguridad social (cuota obrera IMSS) |
| 002 | ISR |
| 004 | Aportaciones a fondo de ahorro |
| 010 | Pago de crédito de vivienda (Infonavit) |
| 006 | Descuento por incapacidad |
| 020 | Ausencia (ausentismo) |

**`c_TipoOtroPago`:**

| Clave | Otro pago |
|---|---|
| **002** | **Subsidio para el empleo** (efectivamente entregado al trabajador) |
| 004 | Aplicación de saldo a favor por compensación anual |
| 999 | Pagos distintos a los listados |

> El subsidio va en **OtrosPagos**, con el nodo hijo `SubsidioAlEmpleo` y su atributo
> `SubsidioCausado`. Desde 2024, con el subsidio acreditándose solo hasta agotar el ISR, el
> importe entregado suele ser $0.00 mientras el `SubsidioCausado` sí lleva monto. Es una
> fuente clásica de rechazo en el timbrado.

---

## 4. Periodicidades (`c_PeriodicidadPago`)

| Clave | Periodicidad | Días base |
|---|---|---|
| 01 | Diaria | 1 |
| 02 | Semanal | 7 |
| 03 | Catorcenal | 14 |
| 04 | Quincenal | 15 |
| 05 | Mensual | 30 |
| 06 | Bimestral | 60 |
| 99 | Otra periodicidad | — |

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
- Anexo 20 de la RMF — estándar del CFDI 4.0 y catálogos (`catCFDI`).
- LISR Arts. 93 y 96 para el gravado/exento de cada percepción.
- `docs/PLAN_NOMINA.md` §2.7; `docs/decisiones-nomina.md` §D7, §D8, §D9.
