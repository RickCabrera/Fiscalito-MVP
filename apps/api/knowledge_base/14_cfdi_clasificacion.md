# CFDI — Clasificación y Tipos Relevantes para el Cálculo Fiscal

**Versión vigente:** CFDI 4.0 (obligatorio desde 1 abril 2023)
**Fundamento:** Art. 29 y 29-A CFF, Anexo 20 RMF

---

## Tipos de CFDI por Propósito

| Tipo | Clave | Descripción | Uso en Fiscalito |
|------|-------|-------------|-----------------|
| Ingreso | `I` | Factura por venta o servicio | Ingresos gravables del contribuyente |
| Egreso | `E` | Nota de crédito, devolución, descuento | Reduce ingresos acumulables |
| Traslado | `T` | Ampara el traslado de mercancías | No fiscal (solo logístico) |
| Nómina | `N` | Recibo de nómina electrónico | No aplica (para patrones) |
| Pago | `P` | Complemento de recepción de pagos | Confirma cobro en pagos diferidos |

---

## Clasificación para Pre-declaración ISR/IVA

### CFDIs de Ingreso (tipo `I`) donde el contribuyente es **EMISOR**

→ Son los **ingresos gravables** del contribuyente

| Campo CFDI | Campo en Sistema |
|-----------|-----------------|
| Total (sin IVA) | `subtotal` |
| IVA Trasladado | `iva_trasladado` |
| ISR Retenido por cliente | `isr_retenido` |
| IVA Retenido por cliente | se captura del CFDI |

### CFDIs de Ingreso (tipo `I`) donde el contribuyente es **RECEPTOR**

→ Son los **gastos/compras** del contribuyente (egresos deducibles)

| Campo CFDI | Uso |
|-----------|-----|
| Total | Monto del gasto |
| IVA Trasladado | IVA acreditable |
| ISR Retenido | No aplica para el receptor |

### CFDIs de Egreso (tipo `E`) donde el contribuyente es **EMISOR**

→ **Reducen** los ingresos acumulables (devoluciones, descuentos)

---

## Campos Clave del CFDI 4.0 para Cálculo Fiscal

```xml
<cfdi:Comprobante
  Fecha="2026-01-15T10:00:00"
  Sello="..."
  FormaPago="03"         <!-- 03=Transferencia, 01=Efectivo, 04=Tarjeta crédito -->
  SubTotal="10000.00"    <!-- Base antes de IVA -->
  Descuento="0.00"
  Moneda="MXN"
  TipoCambio="1.00"
  Total="11600.00"       <!-- SubTotal + IVA -->
  TipoDeComprobante="I"  <!-- I=Ingreso, E=Egreso, T=Traslado, P=Pago, N=Nómina -->
  Exportacion="01"       <!-- 01=No aplica, 02=Definitiva, 03=Temporal -->
  MetodoPago="PUE"       <!-- PUE=Pago en Una Exhibición, PPD=Pago en Parcialidades -->
>
  <cfdi:Emisor
    Rfc="XAXX010101000"
    Nombre="Contribuyente Ejemplo"
    RegimenFiscal="626"   <!-- Código SAT del régimen fiscal -->
  />
  <cfdi:Receptor
    Rfc="AAA010101AAA"
    Nombre="Cliente SA de CV"
    DomicilioFiscalReceptor="06600"
    RegimenFiscalReceptor="601"  <!-- Código régimen del receptor -->
    UsoCFDI="G03"          <!-- G03=Gastos en general, P01=Por definir -->
  />
  <cfdi:Impuestos TotalImpuestosTrasladados="1600.00" TotalImpuestosRetenidos="1000.00">
    <cfdi:Traslados>
      <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
    </cfdi:Traslados>
    <cfdi:Retenciones>
      <cfdi:Retencion Impuesto="001" Importe="1000.00"/>  <!-- 001=ISR -->
    </cfdi:Retenciones>
  </cfdi:Impuestos>
</cfdi:Comprobante>
```

---

## Claves de Régimen Fiscal (RegimenFiscal en CFDI)

| Código | Régimen |
|--------|---------|
| 601 | General de Ley Personas Morales |
| 603 | Personas Morales con Fines no Lucrativos |
| 605 | Sueldos y Salarios e Ingresos Asimilados a Salarios |
| 606 | Arrendamiento |
| 607 | Régimen de Enajenación o Adquisición de Bienes |
| 608 | Demás Ingresos |
| 610 | Residentes en el Extranjero |
| 611 | Ingresos por Dividendos (socios y accionistas) |
| 612 | Personas Físicas con Actividades Empresariales y Profesionales |
| 614 | Ingresos por Intereses |
| 616 | Sin obligaciones fiscales |
| 621 | Incorporación Fiscal (RIF — histórico) |
| 622 | Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras |
| 623 | Opcional para Grupos de Sociedades |
| 624 | Coordinados |
| 625 | Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas |
| 626 | Régimen Simplificado de Confianza (RESICO) |

---

## Códigos de Uso del CFDI (UsoCFDI) más Comunes

| Clave | Descripción |
|-------|-------------|
| G01 | Adquisición de mercancias |
| G02 | Devoluciones, descuentos o bonificaciones |
| G03 | Gastos en general |
| I01 | Construcciones |
| I03 | Equipo de transporte |
| I04 | Equipo de computo y accesorios |
| D01 | Honorarios médicos, dentales y gastos hospitalarios |
| D02 | Gastos médicos por incapacidad o discapacidad |
| D03 | Gastos funerales |
| D04 | Donativos |
| D05 | Intereses reales por créditos hipotecarios |
| D06 | Aportaciones voluntarias al SAR |
| D07 | Primas por seguros de gastos médicos |
| D08 | Gastos de transportación escolar obligatoria |
| D09 | Depósitos en cuentas para el ahorro |
| D10 | Pagos por servicios educativos (colegiaturas) |
| S01 | Sin efectos fiscales |
| CP01 | Pagos |
| CN01 | Nómina |

**Nota para deducciones personales:** Solo los CFDIs con uso `D01` a `D10` son deducibles personalmente en declaración anual.

---

## Claves de Impuesto en CFDI

| Clave | Impuesto |
|-------|---------|
| 001 | ISR |
| 002 | IVA |
| 003 | IEPS |

---

## Formas de Pago Relevantes

| Clave | Forma de Pago |
|-------|--------------|
| 01 | Efectivo |
| 02 | Cheque nominativo |
| 03 | Transferencia electrónica de fondos |
| 04 | Tarjeta de crédito |
| 05 | Monedero electrónico |
| 06 | Dinero electrónico |
| 28 | Tarjeta de débito |
| 29 | Tarjeta de servicios |
| 99 | Por definir |

---

## Validación de CFDI para el Cálculo

Al procesar XMLs, el sistema debe verificar:

1. **Versión:** Solo procesar CFDI versión 4.0 (o 3.3 para CFDIs históricos)
2. **Estado en SAT:** Verificar que el CFDI no esté cancelado
3. **RFC del contribuyente:** El RFC del emisor o receptor debe coincidir con el perfil
4. **Fecha del CFDI:** Debe estar en el periodo declarado
5. **Tipo de comprobante:** Clasificar `I` (ingreso) vs `E` (egreso) vs `P` (pago)
6. **Método de pago:** `PUE` (ya pagado) vs `PPD` (pendiente de pago)
7. **IVA:** Verificar que esté correctamente trasladado o sea acto exento
