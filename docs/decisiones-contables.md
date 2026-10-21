# Decisiones contables (Contabilito, plan P)

Criterios de contabilidad que no son cálculo de impuesto pero sí cambian lo que dice la
balanza. Numeración `§D-Cn`. Las de nómina viven en `decisiones-nomina.md`.

## §D-C1 · La fecha de un complemento de pago es su `FechaPago` — TOMADA (revisión P2)

**Problema.** Un cobro del 31 de octubre cuyo complemento de pago (CFDI tipo P) se timbra el 3
de noviembre se registraba en noviembre: la póliza del P llevaba la fecha de emisión y el
filtro del periodo (pólizas y `facturas-calculo`) también. Octubre quedaba con el IVA en 209
(no cobrado) y la conciliación bancaria de octubre dejaba el depósito del 31 como partida en
tránsito.

**Regla.** En flujo de efectivo el ingreso y el IVA se causan cuando se cobran:

- Art. 1-B LIVA: se consideran efectivamente cobradas las contraprestaciones cuando se reciban
  en efectivo, en bienes o en servicios.
- Art. 102 LISR (personas físicas con actividad empresarial y profesional): los ingresos se
  consideran acumulables en el momento en que sean efectivamente percibidos.

La fecha en que eso pasó es la del pago (`FechaPago` de cada nodo `Pago` del complemento), no
la de emisión del comprobante que lo documenta.

**Decisión.**

1. La póliza del CFDI P lleva la fecha `FechaPago` y entra al periodo por esa fecha
   (`app/contabilidad/generador.py`). Si el complemento trae pagos de días distintos, se genera
   una póliza por día (`clave_origen = "cfdi:<UUID>@AAAA-MM-DD"`); con un solo día, la clave de
   siempre (`cfdi:<UUID>`). Cancelar el CFDI cancela (o revierte) todas.
2. `GET /boveda/clientes/{clave}/facturas-calculo` (`app/boveda_cfdi/calculo.py`) da a cada
   documento pagado la fecha de su pago y lo incluye en el periodo de su pago.
3. Para encontrar los P de un periodo se buscan los emitidos desde 31 días antes del inicio
   hasta 400 días después del fin (`app/boveda_cfdi/fechas_pago.py`) y se filtra por pago.
   Un complemento timbrado más de 400 días después de su pago no aparece: es un caso que el
   SAT no debería aceptar (regla 2.7.1.35 RMF: a más tardar el día 5 del mes siguiente).
4. La póliza dice en sus advertencias la fecha de emisión cuando difiere de la de pago.

**Consecuencia.** Un mes que ya se generó con la regla anterior conserva sus pólizas (son
idempotentes por clave); para corregirlo se cancela la póliza del P y se vuelve a generar el
mes del pago.

## §D-C2 · Retenciones de facturas PPD: al pago — TOMADA, configurable (revisión P2)

La obligación de retener (art. 1-A LIVA, art. 106 último párrafo LISR) y el derecho del
retenido a acreditar nacen con el pago. `ConfigContable.retenciones_al_pago` (default
**true**): las retenciones de una factura PPD van a cuentas de "retenido pendiente"
(113.08.01/02 para lo que nos retienen los clientes; 216.12.01/02/03 para lo que retenemos a
proveedores) y cada complemento de pago las traspasa a 113.01/113.02 y 216.10/216.04/216.03 en
proporción a lo pagado. Con `false`, comportamiento anterior (directo a 113.xx / 216.xx).

DECISIÓN PROVISIONAL: el código agrupador de esas cuentas pendientes (113.08 "Otros impuestos
a favor" y 216.12 "Otros impuestos retenidos") porque el Anexo 24 no tiene uno de "retención
pendiente". Confirmar con la contadora.

## §D-C3 · Notas de crédito sobre PPD con saldo y últimas parcialidades — TOMADA (revisión P2)

- Una nota de crédito (E) relacionada (TipoRelacion 01 o 03) con una factura PPD que aún tiene
  impuestos pendientes los revierte contra las cuentas PENDIENTES de esa factura (209.01,
  209.02, 119.01, retenciones pendientes), con el UUID de la factura, hasta lo que le quede; el
  excedente va a cobrado/pagado.
- La parcialidad que deja `ImpSaldoInsoluto = 0` traspasa todo lo que quede pendiente del
  documento (no la proporción), para que no queden centavos de redondeo en 209/119.

## §D-C4 · Póliza de nómina desde el CFDI — TOMADA (revisión P2)

- Cuota obrera IMSS (TipoDeduccion 001) → 216.11 "Retenciones de IMSS a los trabajadores"
  (así se llama esa cuenta en el código agrupador); las demás deducciones (préstamos,
  Infonavit, pensión…) → 205.06 "Otros acreedores diversos".
- Otros pagos por TipoOtroPago: 002/007/008 subsidio → 110.01; 003 viáticos → 107.01; 001/004/005
  reintegro o compensación de ISR → 216.01 (cargo: reduce el ISR por enterar); el resto →
  601.84. Todas son roles configurables por cliente.
- **Alcance conocido:** las cuotas patronales (IMSS, RCV, Infonavit) y el impuesto sobre nómina
  no vienen en el CFDI de nómina; su póliza (provisión 211.xx / 212.01 contra gasto) la hará P4
  desde el cálculo de la nómina.

## §D-C5 · Balanza de cierre (mes 13 del Anexo 24) — PROVISIONAL (revisión P2)

Saldo inicial = saldos al 31 de diciembre antes del cierre; movimientos = la póliza de cierre de
resultados de P2-08 (`cierre:<año>:resultados`); saldo final = resultados en cero y el
resultado del ejercicio en capital. La póliza `cierre:<año>:balance` no entra: es el artificio
interno para reabrir el 1 de enero y dejaría toda la balanza en cero. Confirmar con la
contadora que es lo que espera el SAT en el mes 13.

## Facturación y suscripciones (P5) — abiertas tras el revisor (2026-10-21)

Corregido: el borrador RESICO PF → PM retiene IVA 2/3 además del ISR 1.25 %; IVA trasladado sólo
0/8/16 % (c_TasaOCuota); la factura se bloquea al registrar un pago (dos pagos simultáneos no
rebasan el saldo); `falso` de pagos y WhatsApp vetado en producción; alta con Mercado Pago → 503
hasta que su webhook consulte `/preapproval`.

Para Ricardo y la contadora:
1. Nota de crédito contra una PPD: ¿baja el `ImpSaldoAnt` de los pagos siguientes? Hoy no, y no
   se valida que el egreso no exceda el saldo.
2. Pago cancelado: ¿se reusa su número de parcialidad? Hoy el siguiente toma el mismo.
3. Igualas de cobranza: ¿antes de IVA, PPD y forma 99? (provisional en `facturacion/servicio.py`).
4. Política comercial: 14 días de prueba y 3 de gracia.
5. Solo lectura por suscripción vencida: también bloquea POST de lectura (asistente, calculadoras).
6. Pendientes menores: firmar también los argumentos de herramientas del asistente; ObjetoImp 03
   en el pago para conceptos "sí objeto, no obligado al desglose"; citar el apartado de límites
   de la Guía del Anexo 20; partir los servicios de P5 que rebasan 300 líneas.
