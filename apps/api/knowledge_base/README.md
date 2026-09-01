# Base de Conocimiento Fiscal — Fiscalito Store

**Última actualización:** Abril 2026
**Fuentes:** RMF 2026 (DOF 28/12/2025), LISR vigente, LIVA vigente, Anexo 8 RMF 2026, DOF 09/01/2026

---

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| `01_valores_referencia.md` | UMA 2026, salario mínimo, factores de actualización |
| `02_isr_tablas_tarifas.md` | Tablas ISR Art. 96 LISR + subsidio al empleo 2026 |
| `03_resico_626.md` | RESICO personas físicas — régimen 626, Art. 113-E LISR |
| `04_actividad_empresarial_612.md` | Régimen Act. Empresarial y Profesional — régimen 612 |
| `05_asalariados_605.md` | Salarios y prestación de servicios subordinados — régimen 605 |
| `06_arrendamiento_606.md` | Arrendamiento de inmuebles — régimen 606 |
| `07_plataformas_625.md` | Plataformas tecnológicas — régimen 625 |
| `08_iva.md` | IVA: tasa 16%, retenciones, acreditamiento, DIOT |
| `09_diot.md` | DIOT: obligados, estructura, plazos 2026 |
| `10_retenciones.md` | Retenciones ISR e IVA a terceros |
| `11_deducciones_personales.md` | Deducciones personales Art. 151 LISR — asalariados |
| `12_calendario_fiscal_2026.md` | Fechas límite de declaraciones por régimen |
| `13_rmf_2026_cambios.md` | Principales cambios RMF 2026 relevantes al sistema |
| `14_cfdi_clasificacion.md` | Tipos de CFDI, clasificación para cálculo fiscal |

---

## Nómina y seguridad social (`nomina/`)

Referencia del módulo de nómina / IMSS. El plan de dominio está en `docs/PLAN_NOMINA.md`; las
decisiones abiertas, en `docs/decisiones-nomina.md`.

| Archivo | Contenido |
|---------|-----------|
| `nomina/20_valores_referencia_2026.md` | UMA y SM por vigencia, piso/tope del SBC, subsidio al empleo 2026 |
| `nomina/21_sbc_integracion.md` | SBC/SDI, factor de integración, salario fijo/variable/mixto, avisos |
| `nomina/22_cuotas_imss_infonavit_2026.md` | Cuotas por ramo, tabla CEAV 2026, primas de RT, reglas especiales |
| `nomina/23_isr_nomina_subsidio.md` | Exenciones Art. 93, ISR Art. 96, aplicación del subsidio |
| `nomina/24_cfdi_nomina_12.md` | Complemento de nómina 1.2 sobre CFDI 4.0, catálogos, validación XSD |
| `nomina/25_calendario_laboral_2026.md` | Vencimientos IMSS/SUA 2026, prima de RT, PTU, aguinaldo, ISN |
| `nomina/26_flujo_despacho_idse_sua_ema.md` | Ciclo operativo del despacho, plazos afiliatorios, e.firma |

> **Los docs 20–26 son referencia, no fuente de cálculo.** El motor calcula desde
> `app/nomina_engine/` y `app/constants.py`; cada doc lo declara en su encabezado.
