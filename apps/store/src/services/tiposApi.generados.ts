/**
 * TIPOS GENERADOS — NO EDITAR A MANO (P0-08).
 *
 * Salen de `app.main:app.openapi()` por `apps/api/scripts/exportar_openapi.py`:
 *   cd apps/api && PYTHONPATH=. python scripts/exportar_openapi.py
 * `apps/api/tests/test_contrato_openapi.py` falla si este archivo quedó viejo.
 */

/** Resumen acumulado de todos los periodos. */
export interface AcumuladoMultiPeriodo {
  total_isr_pagado: number;
  total_iva_pagado: number;
  total_general_pagado: number;
  promedio_mensual: number;
  tendencia: string;
}

/** Request para el agente conversacional de pre-declaraciones. */
export interface AgentePreDeclaracionRequest {
  mensaje: string;
  contribuyente: PerfilContribuyente;
  facturas?: CFDI[];
  historial?: DeclaracionHistorialItem[];
  periodo_year: number;
  periodo_month?: number | null;
}

/** Respuesta del agente de pre-declaraciones. */
export interface AgentePreDeclaracionResponse {
  respuesta: string;
  predeclaracion?: PreDeclaracionResponse | null;
  herramientas_usadas?: string[];
}

export interface Body_importar_cfdi_api_v1_boveda_clientes__clave__cfdi_post {
  archivos: string[];
}

export interface Body_subir_credencial_api_v1_clientes__clave__credenciales_post {
  tipo: string;
  password: string;
  cer: string;
  key: string;
}

/** Datos de una factura CFDI necesarios para calculos fiscales. */
export interface CFDI {
  uuid: string;
  fecha: string;
  tipo: TipoFactura;
  rfc_emisor: string;
  rfc_receptor: string;
  subtotal: number;
  total: number;
  iva_trasladado?: number;
  iva_retenido?: number;
  isr_retenido?: number;
  descuento?: number;
  uso_cfdi?: string;
  descripcion?: string;
  clave_prod_serv?: string;
  metodo_pago?: string;
  uuid_relacionado?: string | null;
  monto_pago?: number | null;
}

/** Todo lo que hace falta para serializar un pre-recibo. Ver `CFDINominaResponse`. */
export interface CFDINominaRequest {
  recibo: ReciboCFDISchema;
  patron: DatosPatronCFDI;
  trabajador: DatosTrabajadorCFDI;
  periodo: PeriodoNomina;
  tipo_nomina?: string;
  serie?: string;
  folio?: string;
}

/** El XML del pre-recibo. **`timbrado` es siempre `False` y no es decorativo.** */
export interface CFDINominaResponse {
  exito?: boolean;
  xml: string;
  timbrado?: boolean;
  nombre_archivo: string;
  advertencia: string;
}

export interface CalcularPeriodoRequest {
  cliente: string;
  periodo: PeriodoNomina;
  incidencias: IncidenciasEmpleadoSchema[];
  parametros: ParametrosPatron;
  empleados?: EmpleadoNominaSchema[] | null;
  incluir_explicacion?: boolean;
}

/** El resultado del periodo. */
export interface CalcularPeriodoResponse {
  exito?: boolean;
  cliente: string;
  periodo: PeriodoNomina;
  origen_plantilla: string;
  fecha_pago_efectiva: string;
  recibos: ReciboSchema[];
  porcion_mensual: PorcionConsolidada;
  porcion_bimestral: PorcionConsolidada;
  total_percepciones: string;
  total_neto: string;
  total_isr: string;
  advertencias?: string[];
  explicacion?: string | null;
}

/** Calendario patronal de toda la cartera, ordenado por fecha límite. */
export interface CalendarioPatronalResponse {
  exito?: boolean;
  anio_de_las_cuotas: number;
  cubre_desde?: string | null;
  cubre_hasta?: string | null;
  total_obligaciones: number;
  obligaciones: ObligacionPatronalSchema[];
  advertencias: string[];
}

/** Request para generar calendario fiscal personalizado. */
export interface CalendarioRequest {
  contributor_type: string;
  regimen: string;
  rfc: string;
  year?: number;
}

/** Respuesta con el calendario de obligaciones fiscales. */
export interface CalendarioResponse {
  exito?: boolean;
  contributor_type: string;
  total_obligaciones: number;
  obligaciones: ObligacionFiscalSchema[];
}

export interface CerrarPeriodoRequest {
  cliente: string;
  empleados: string[];
  periodo: Periodo;
  horario?: HorarioLaboral;
}

export interface CerrarPeriodoResponse {
  exito?: boolean;
  cliente: string;
  periodo: Periodo;
  incidencias: IncidenciasEmpleado[];
  empleados_desconocidos?: string[];
}

/** Un cliente tal como lo captura el despacho. */
export interface ClienteCarteraSchema {
  id: string;
  nombre: string;
  giro?: string;
  origen?: string;
  regimen?: string;
  rfc?: string;
  codigo_postal?: string;
  clave_entidad?: string;
  guia_subdelegacion?: string;
  registro_patronal?: string;
  prima_riesgo: number | string;
  clase_riesgo?: number | null;
  clave_periodicidad?: string;
  zona?: ZonaSalarioMinimo;
  parametros?: ParametrosSalarialesSchema;
  periodo_sugerido?: PeriodoNomina | null;
}

/** La ficha del cliente. */
export interface ClienteDetalle {
  id: string;
  nombre: string;
  giro: string;
  origen: string;
  num_empleados: number;
  prima_riesgo: string;
  clase_riesgo?: number | null;
  clave_periodicidad: string;
  zona: ZonaSalarioMinimo;
  exito?: boolean;
  empleados: EmpleadoClienteSchema[];
  periodo_sugerido: PeriodoNomina;
  fecha_referencia: string;
}

/** Lo que necesita la lista de clientes y el selector del header. */
export interface ClienteResumen {
  id: string;
  nombre: string;
  giro: string;
  origen: string;
  num_empleados: number;
  prima_riesgo: string;
  clase_riesgo?: number | null;
  clave_periodicidad: string;
  zona: ZonaSalarioMinimo;
}

export interface ClientesCarteraResponse {
  exito?: boolean;
  total: number;
  clientes: Record<string, unknown>[];
}

export interface ClientesResponse {
  exito?: boolean;
  clientes: ClienteResumen[];
}

/** Request para comparar todos los regimenes fiscales entre si. */
export interface CompararRegimenRequest {
  ingresos_mensuales_estimados: number;
  gastos_mensuales_estimados: number;
  predial_mensual?: number;
  tipo_actividad?: string;
  incluir_explicacion?: boolean;
}

/** Respuesta con ISR estimado para cada regimen fiscal, ordenado de menor a mayor. */
export interface CompararRegimenResponse {
  exito?: boolean;
  resultados: ResultadoRegimen[];
  regimen_recomendado: string;
  nombre_recomendado: string;
  ahorro_maximo: number;
  recomendacion: string;
  explicacion?: string | null;
}

/** Tipo de contribuyente en el ecosistema Fiscalito. */
export type ContributorType = "asalariado" | "independiente" | "arrendamiento" | "plataformas" | "pyme";

/** Un ramo calculado, con lo necesario para conciliarlo contra la EMA. */
export interface CuotaRamoSchema {
  clave: string;
  nombre: string;
  base_diaria: string;
  dias: number;
  patron: string;
  obrero: string;
  fundamento: string;
}

/** Request para generar DIOT. */
export interface DIOTRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
  periodo_year: number;
  periodo_month: number;
  incluir_explicacion?: boolean;
}

/** Respuesta del endpoint DIOT. */
export interface DIOTResponse {
  exito: boolean;
  periodo: string;
  proveedores: ProveedorDIOT[];
  total_proveedores: number;
  total_operaciones: number;
  total_iva: number;
  explicacion?: string | null;
}

/** El emisor. Ver `24_cfdi_nomina_12.md` §2. */
export interface DatosPatronCFDI {
  rfc: string;
  nombre: string;
  regimen_fiscal: string;
  registro_patronal: string;
  codigo_postal: string;
  clave_entidad: string;
}

/** El receptor. Ver `24_cfdi_nomina_12.md` §2. */
export interface DatosTrabajadorCFDI {
  rfc: string;
  nombre: string;
  curp: string;
  numero_seguridad_social: string;
  codigo_postal: string;
  fecha_inicio_relacion_laboral: string;
  tipo_contrato: string;
  numero_empleado: string;
  puesto: string;
  riesgo_puesto: string;
  periodicidad_pago: string;
  salario_base_cotizacion: number | string;
  salario_diario_integrado: number | string;
  antiguedad?: string;
  departamento?: string;
  sindicalizado?: string;
  tipo_jornada?: string;
  tipo_regimen?: string;
}

/** Resumen de una declaracion existente (viene de Firestore via frontend). */
export interface DeclaracionHistorialItem {
  periodo: string;
  tipo: string;
  fecha_calculo?: string;
  total_a_pagar?: number;
  isr_a_pagar?: number;
  iva_a_pagar?: number;
  regimen?: string;
}

/** Detalle de una deduccion individual. */
export interface DeduccionDetalle {
  concepto: string;
  monto_solicitado: number;
  tope_aplicable?: number | null;
  monto_aceptado: number;
}

/** Request para calcular deducciones personales (declaracion anual). */
export interface DeduccionesPersonalesRequest {
  ingresos_anuales: number;
  gastos_medicos?: number;
  colegiaturas?: number;
  nivel_educativo?: string;
  intereses_hipotecarios?: number;
  donativos?: number;
  aportaciones_voluntarias_retiro?: number;
  seguros_gastos_medicos?: number;
  transporte_escolar?: number;
  funeral?: number;
  incluir_explicacion?: boolean;
}

/** Respuesta del calculo de deducciones personales. */
export interface DeduccionesPersonalesResponse {
  exito?: boolean;
  desglose: DeduccionDetalle[];
  total_solicitado: number;
  total_antes_tope: number;
  tope_global: number;
  tope_tipo: string;
  total_deducible: number;
  excedente_no_aprovechado: number;
  saldo_a_favor_estimado: number;
  explicacion?: string | null;
}

/** Desglose numerico de una declaracion. */
export interface DesgloseFiscal {
  total_ingresos_facturados: number;
  total_ingresos_gravados: number;
  cantidad_facturas_ingreso?: number;
  total_egresos?: number;
  total_deducciones_autorizadas?: number;
  cantidad_facturas_egreso?: number;
  base_isr: number;
  tasa_isr: number;
  isr_causado: number;
  isr_retenido?: number;
  isr_a_pagar: number;
  iva_trasladado_cobrado?: number;
  iva_trasladado_pagado?: number;
  iva_retenido?: number;
  iva_a_pagar: number;
  deduccion_ciega_aplicada?: boolean;
  comparacion_deduccion?: string | null;
  pagos_provisionales_anteriores?: number;
  ingresos_acumulados?: number;
  deducciones_acumuladas?: number;
  gastos_personales_excluidos?: number;
  cantidad_gastos_personales?: number;
  retenciones_definitivas?: boolean;
  ingreso_anualizado_estimado?: number;
  total_a_pagar: number;
}

/** Detalle de un dia del periodo, para que la pantalla pueda explicarlo. */
export interface DiaTrabajado {
  dia: string;
  laborable: boolean;
  checadas: number;
  trabajado: boolean;
  falta: boolean;
  retardo: boolean;
  primera_entrada?: string | null;
}

export interface EmitirTokenRequest {
  cliente: string;
  etiqueta?: string;
  dispositivo?: string | null;
}

/** Un empleado tal como lo guarda el despacho. */
export interface EmpleadoCarteraSchemaInput {
  empleado_no: string;
  nombre: string;
  apellido_paterno?: string;
  apellido_materno?: string;
  nombres?: string;
  puesto?: string;
  salario_diario: number | string;
  salario_diario_integrado: number | string;
  zona?: ZonaSalarioMinimo;
  fecha_alta?: string | null;
  tipo_contrato?: TipoContrato;
  prestaciones?: PrestacionesSchemaInput;
  nss?: string;
  employee_no?: string | null;
  enrolamiento?: EstatusEnrolamiento;
}

/** Un empleado tal como lo guarda el despacho. */
export interface EmpleadoCarteraSchemaOutput {
  empleado_no: string;
  nombre: string;
  apellido_paterno?: string;
  apellido_materno?: string;
  nombres?: string;
  puesto?: string;
  salario_diario: string;
  salario_diario_integrado: string;
  zona?: ZonaSalarioMinimo;
  fecha_alta?: string | null;
  tipo_contrato?: TipoContrato;
  prestaciones?: PrestacionesSchemaOutput;
  nss?: string;
  employee_no?: string | null;
  enrolamiento?: EstatusEnrolamiento;
}

/** Un empleado en la ficha del cliente. */
export interface EmpleadoClienteSchema {
  empleado_no: string;
  nombre: string;
  salario_diario: string;
  salario_diario_integrado: string;
  zona: ZonaSalarioMinimo;
  puesto?: string;
  fecha_alta?: string | null;
  antiguedad_anios?: number | null;
  factor: string;
  factor_implicito: boolean;
}

/** Un empleado de la plantilla de demostración, **sin salarios**. */
export interface EmpleadoDemoSchema {
  empleado_no: string;
  nombre: string;
}

/** Un empleado de la plantilla. El SDI es dato de entrada (§D9). */
export interface EmpleadoNominaSchema {
  empleado_no: string;
  nombre?: string;
  salario_diario: number | string;
  salario_diario_integrado: number | string;
  zona?: ZonaSalarioMinimo;
}

export interface EmpleadosCarteraResponse {
  exito?: boolean;
  cliente_id: string;
  total: number;
  sin_vincular: number;
  ilegibles?: string[];
  empleados: EmpleadoCarteraSchemaOutput[];
}

/** La semilla de empleados de un cliente. */
export interface EmpleadosClienteResponse {
  cliente_id: string;
  origen: string;
  total: number;
  sin_vincular: number;
  empleados: EmpleadoCarteraSchemaOutput[];
}

/** Cuerpo de `POST /trabajos/clientes/{clave}/diagnostico`. */
export interface EncolarDiagnostico {
  fallar_intentos?: number;
}

/** Respuesta de error estandar. */
export interface ErrorResponse {
  exito?: boolean;
  error: string;
  detalle?: string | null;
}

/** Request para generar estado de cuenta fiscal. */
export interface EstadoCuentaRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
  periodo_year: number;
  incluir_explicacion?: boolean;
}

/** Respuesta del endpoint de estado de cuenta. */
export interface EstadoCuentaResponse {
  exito: boolean;
  year: number;
  ingresos_acumulados: number;
  egresos_acumulados: number;
  isr_retenido_acumulado: number;
  isr_anual_estimado: number;
  isr_faltante: number;
  iva_cobrado_acumulado: number;
  iva_pagado_acumulado: number;
  iva_retenido_acumulado: number;
  proyeccion_ingresos_anuales: number;
  proporcion_gastos_ingresos: number;
  mes_mayor_ingreso: string;
  mes_mayor_gasto: string;
  advertencias: string[];
  explicacion?: string | null;
}

/** Si la persona ya tiene su rostro dado de alta en el checador. */
export type EstatusEnrolamiento = "pendiente" | "enrolado";

/** Una checada normalizada. */
export interface EventoChecada {
  empleado_no: string;
  timestamp: string;
  tipo: TipoChecada;
  fuente: FuenteChecada;
  serial_no?: number | null;
  raw?: Record<string, unknown> | null;
}

export interface EventoSalida {
  id: number;
  fecha: string;
  uid: string;
  cliente: string | null;
  accion: string;
  entidad: string;
  entidad_id: string;
  detalle: Record<string, unknown>;
  ip: string;
}

export interface EventosRecibidosResponse {
  exito?: boolean;
  cliente: string;
  recibidos: number;
  duplicados: number;
  total_en_memoria: number;
}

export interface EventosResponse {
  exito?: boolean;
  cliente: string;
  eventos: EventoChecada[];
}

/** De donde vino el evento. `csv` queda para el plan C (import manual). */
export type FuenteChecada = "hikvision" | "simulado" | "csv";

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** Modelo de respuesta del endpoint de salud. */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

/** Horario contra el que se miden retardos y faltas. */
export interface HorarioLaboral {
  hora_entrada?: string;
  hora_salida?: string;
  tolerancia_minutos?: number;
  dias_laborables?: number[];
}

/** El horario contra el que el checador mide retardos y faltas. (O-03) */
export interface HorarioSchema {
  hora_entrada?: string;
  hora_salida?: string;
  tolerancia_minutos?: number;
  dias_laborables?: number[];
}

/** Incidencias de un empleado en el periodo. */
export interface IncidenciasEmpleado {
  empleado_no: string;
  dias_periodo: number;
  dias_laborables: number;
  dias_trabajados: number;
  faltas: number;
  dias_ausentismo: number;
  retardos: number;
  dias_cotizados: number;
  detalle?: DiaTrabajado[];
}

/** Incidencias de un empleado, tal como las devuelve `cerrar-periodo`. */
export interface IncidenciasEmpleadoSchema {
  empleado_no: string;
  dias_periodo: number;
  faltas: number;
  dias_ausentismo: number;
  dias_incapacidad?: number;
}

export interface ListaTrabajos {
  exito?: boolean;
  trabajos: TrabajoSalida[];
}

/** Request para calcular multiples periodos a la vez. */
export interface MultiPeriodoRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
  periodo_year: number;
  periodos: number[];
  incluir_explicacion?: boolean;
}

/** Respuesta del endpoint multi-periodo. */
export interface MultiPeriodoResponse {
  exito: boolean;
  year: number;
  resultados: PeriodoResultado[];
  acumulado: AcumuladoMultiPeriodo;
  explicacion?: string | null;
}

/** Una obligacion fiscal con fecha limite. */
export interface ObligacionFiscalSchema {
  nombre: string;
  descripcion: string;
  fecha_limite: string;
  periodicidad: string;
  completada?: boolean;
}

/** Una obligación del patrón, ya etiquetada con el cliente al que pertenece. */
export interface ObligacionPatronalSchema {
  cliente_id: string;
  cliente_nombre: string;
  clave: string;
  nombre: string;
  descripcion: string;
  fecha_limite: string;
  periodicidad: string;
  periodo_cubierto: string;
  fundamento: string;
  regimen_de_plazo: RegimenDePlazo;
  condicional: boolean;
  nota?: string;
}

export interface OperacionResponse {
  exito?: boolean;
  mensaje: string;
}

export interface PaginaAuditoria {
  exito?: boolean;
  eventos: EventoSalida[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** Parámetros de la empresa que el motor necesita y no puede adivinar. */
export interface ParametrosPatron {
  prima_riesgo: number | string;
  clave_periodicidad?: string;
  dias_pagados?: number | null;
}

/** Las prestaciones del patrón, que alimentan el factor de integración. (O-03) */
export interface ParametrosSalarialesSchema {
  dias_aguinaldo?: number;
  prima_vacacional?: number | string;
  tabla_vacaciones?: [number, number][];
  horario?: HorarioSchema;
}

export interface PartidaSchemaInput {
  tipo: string;
  clave: string;
  concepto: string;
  importe: number | string;
  gravado?: number | string | null;
  exento?: number | string | null;
  subsidio_causado?: number | string | null;
}

export interface PartidaSchemaOutput {
  tipo: string;
  clave: string;
  concepto: string;
  importe: string;
  gravado?: string | null;
  exento?: string | null;
  subsidio_causado?: string | null;
}

/** Datos del contribuyente necesarios para calcular declaraciones. */
export interface PerfilContribuyente {
  rfc: string;
  regimen: string;
  nombre?: string;
  tipo_persona?: string;
  actividad_economica?: string;
  periodicidad?: PeriodicidadDeclaracion;
  tiene_empleados?: boolean;
  retenedor_iva?: boolean;
  fecha_inicio_actividades?: string | null;
  contributor_type?: ContributorType | null;
}

export type PeriodicidadDeclaracion = "mensual" | "bimestral" | "anual";

/** Periodo cerrado, inclusivo en los dos extremos. */
export interface Periodo {
  inicio: string;
  fin: string;
}

/** Periodo de nómina, inclusivo en los dos extremos. */
export interface PeriodoNomina {
  inicio: string;
  fin: string;
  fecha_pago?: string | null;
}

/** Resultado de un periodo individual. */
export interface PeriodoResultado {
  periodo: string;
  desglose: DesgloseFiscal;
}

/** El último periodo terminado para una periodicidad. (O-03) */
export interface PeriodoSugeridoResponse {
  exito?: boolean;
  clave_periodicidad: string;
  periodo: PeriodoNomina;
  dias_naturales: number;
}

/** Todo lo que la pantalla de la demo necesita y **no puede inventarse**. */
export interface PlantillaDemoResponse {
  exito?: boolean;
  cliente: string;
  origen?: string;
  empleados: EmpleadoDemoSchema[];
  prima_riesgo: string;
  clave_periodicidad: string;
  zona: ZonaSalarioMinimo;
  periodo_sugerido: PeriodoNomina;
}

/** Lo devengado en ESTE periodo por los ramos de una periodicidad de entero. */
export interface PorcionConsolidada {
  periodicidad: string;
  por_ramo: Record<string, string>;
  total_patron: string;
  total_obrero: string;
  total: string;
  empleados: number;
}

/** Request para generar una pre-declaracion (mensual, bimestral o anual). */
export interface PreDeclaracionRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
  periodo_year: number;
  periodo_month?: number | null;
  periodo_bimestre?: number | null;
  pagos_provisionales_anteriores?: number;
  ingresos_acumulados_anteriores?: number;
  deducciones_acumuladas_anteriores?: number;
  predial_pagado?: number;
  incluir_explicacion?: boolean;
}

/** Respuesta completa de una pre-declaracion. */
export interface PreDeclaracionResponse {
  exito?: boolean;
  tipo_declaracion: string;
  periodo: string;
  regimen: string;
  desglose: DesgloseFiscal;
  explicacion?: string | null;
  advertencias?: string[];
  recomendaciones?: string[];
}

/** Las prestaciones con las que se integra el SBC (Art. 27 LSS). */
export interface PrestacionesSchemaInput {
  dias_aguinaldo?: number;
  dias_vacaciones?: number;
  prima_vacacional?: number | string;
}

/** Las prestaciones con las que se integra el SBC (Art. 27 LSS). */
export interface PrestacionesSchemaOutput {
  dias_aguinaldo?: number;
  dias_vacaciones?: number;
  prima_vacacional?: string;
}

/** Primas medias por clase, **con su fecha de vigencia**. */
export interface PrimasDeRiesgoResponse {
  fecha: string;
  minima: string;
  maxima: string;
  medias_por_clase: Record<string, string>;
  fundamento: string;
}

/** Detalle de un proveedor en el DIOT. */
export interface ProveedorDIOT {
  rfc: string;
  nombre: string;
  total_operaciones: number;
  iva_pagado: number;
  cantidad_facturas: number;
}

/** Lo que el CFDI necesita de un recibo, y nada más. */
export interface ReciboCFDISchema {
  empleado_no: string;
  nombre?: string;
  dias_pagados: number;
  percepciones: PartidaSchemaInput[];
  deducciones?: PartidaSchemaInput[];
  otros_pagos?: PartidaSchemaInput[];
}

export interface ReciboSchema {
  empleado_no: string;
  nombre: string;
  sbc: string;
  sbc_piso_aplicado: boolean;
  sbc_tope_aplicado: boolean;
  es_salario_minimo: boolean;
  dias_periodo: number;
  dias_ausentismo: number;
  dias_pagados: number;
  percepciones: PartidaSchemaOutput[];
  deducciones: PartidaSchemaOutput[];
  otros_pagos: PartidaSchemaOutput[];
  total_percepciones: string;
  total_deducciones: string;
  neto: string;
  cuota_obrera: string;
  cuota_patronal: string;
  absorbio_cuota_obrera: boolean;
  ramos: CuotaRamoSchema[];
}

/** Qué regla de cómputo produjo la fecha límite. */
export type RegimenDePlazo = "imss" | "imss_sin_prorroga" | "imss_aviso" | "sat" | "lft";

/** Resultado ISR estimado para un regimen fiscal especifico. */
export interface ResultadoRegimen {
  regimen: string;
  nombre: string;
  isr_anual: number;
  isr_mensual: number;
  disponible: boolean;
  notas?: string[];
}

/** Request para generar resumen de retenciones. */
export interface RetencionesRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
  periodo_year: number;
  periodo_month?: number | null;
  periodo_bimestre?: number | null;
  incluir_explicacion?: boolean;
}

/** Respuesta del endpoint de retenciones. */
export interface RetencionesResponse {
  exito: boolean;
  periodo: string;
  terceros: TerceroRetencion[];
  total_isr_retenido: number;
  total_iva_retenido: number;
  explicacion?: string | null;
}

/** Lo que se necesita para integrar un salario fijo (Art. 27 y 30 fr. I LSS). */
export interface SBCRequest {
  salario_diario: number | string;
  fecha: string;
  zona?: ZonaSalarioMinimo;
  anios_servicio_cumplidos?: number;
  dias_aguinaldo?: number;
  dias_vacaciones?: number;
  prima_vacacional?: number | string;
  tabla_vacaciones?: [number, number][];
}

/** El SBC integrado, con todo lo que la pantalla necesita para explicarlo. */
export interface SBCResponse {
  factor: string;
  dias_vacaciones_aplicados: number;
  sbc_sin_acotar: string;
  sbc: string;
  piso_aplicado: boolean;
  tope_aplicado: boolean;
  piso: string;
  tope: string;
  fundamento: string;
}

/** Detalle de retenciones a un tercero. */
export interface TerceroRetencion {
  rfc: string;
  nombre: string;
  total_pagado: number;
  isr_retenido: number;
  iva_retenido: number;
  cantidad_facturas: number;
}

/** Entrada o salida. Sale de `attendanceStatus` del dispositivo. */
export type TipoChecada = "entrada" | "salida";

/** Tipo de relación de trabajo (Art. 35 LFT). */
export type TipoContrato = "indeterminado" | "determinado" | "obra_determinada" | "prueba";

export type TipoFactura = "I" | "E" | "T" | "P";

export interface TokenDispositivoSchema {
  id: number;
  cliente: string;
  dispositivo_id?: number | null;
  etiqueta: string;
  prefijo: string;
  creado_en?: string | null;
  ultimo_uso?: string | null;
}

export interface TokenEmitidoResponse {
  exito?: boolean;
  token: string;
  registro: TokenDispositivoSchema;
}

export interface TokenRevocadoResponse {
  exito?: boolean;
  registro: TokenDispositivoSchema;
}

export interface TokensResponse {
  exito?: boolean;
  tokens: TokenDispositivoSchema[];
}

/** Un trabajo tal como lo ve el despacho. `cliente` es la clave pública, no el id. */
export interface TrabajoSalida {
  id: number;
  tipo: string;
  estado: string;
  cliente: string | null;
  intentos: number;
  max_intentos: number;
  ejecutar_en: string;
  iniciado_en: string | null;
  terminado_en: string | null;
  creado_en: string;
  error: string | null;
  resultado: Record<string, unknown> | null;
  carga: Record<string, unknown>;
}

export interface UnTrabajo {
  exito?: boolean;
  trabajo: TrabajoSalida;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

/** Zona geografica que determina el salario minimo aplicable. */
export type ZonaSalarioMinimo = "general" | "zlfn";

/** Toda ruta que publica la API. */
export type RutaApi =
  | "/api/v1/agente/predeclaracion"
  | "/api/v1/asistencia/cerrar-periodo"
  | "/api/v1/asistencia/eventos"
  | "/api/v1/asistencia/tokens"
  | "/api/v1/asistencia/tokens/{token_id}"
  | "/api/v1/auditoria"
  | "/api/v1/boveda/clientes/{clave}/cfdi"
  | "/api/v1/boveda/clientes/{clave}/cfdi/{uuid}"
  | "/api/v1/boveda/clientes/{clave}/cfdi/{uuid}/xml"
  | "/api/v1/boveda/clientes/{clave}/resumen"
  | "/api/v1/calendario"
  | "/api/v1/cartera/clientes"
  | "/api/v1/cartera/clientes/{cliente_id}"
  | "/api/v1/cartera/clientes/{cliente_id}/empleados"
  | "/api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}"
  | "/api/v1/clientes/{clave}/credenciales"
  | "/api/v1/clientes/{clave}/credenciales/{credencial_id}"
  | "/api/v1/comparar-regimenes"
  | "/api/v1/deducciones-personales"
  | "/api/v1/despacho/calendario"
  | "/api/v1/despacho/clientes"
  | "/api/v1/despacho/clientes/{cliente_id}"
  | "/api/v1/despacho/clientes/{cliente_id}/empleados"
  | "/api/v1/despacho/primas-de-riesgo"
  | "/api/v1/diot"
  | "/api/v1/estado-cuenta"
  | "/api/v1/multi-periodo"
  | "/api/v1/nomina/calcular-periodo"
  | "/api/v1/nomina/cfdi"
  | "/api/v1/nomina/demo/plantilla"
  | "/api/v1/nomina/periodo-sugerido"
  | "/api/v1/nomina/sbc"
  | "/api/v1/pre-declaracion"
  | "/api/v1/pre-declaracion-anual"
  | "/api/v1/retenciones-terceros"
  | "/api/v1/trabajos"
  | "/api/v1/trabajos/clientes/{clave}/diagnostico"
  | "/api/v1/trabajos/{trabajo_id}"
  | "/api/v1/trabajos/{trabajo_id}/cancelar"
  | "/api/v1/trabajos/{trabajo_id}/reintentar"
  | "/health"
  | "/health/integraciones";

/** Cuerpo y respuesta (2xx) de cada operación, por `MÉTODO /ruta`. */
export interface OperacionesApi {
  "POST /api/v1/agente/predeclaracion": {
    cuerpo: AgentePreDeclaracionRequest;
    respuesta: AgentePreDeclaracionResponse;
  };
  "POST /api/v1/asistencia/cerrar-periodo": {
    cuerpo: CerrarPeriodoRequest;
    respuesta: CerrarPeriodoResponse;
  };
  "GET /api/v1/asistencia/eventos": {
    cuerpo: never;
    respuesta: EventosResponse;
  };
  "POST /api/v1/asistencia/eventos": {
    cuerpo: never;
    respuesta: EventosRecibidosResponse;
  };
  "GET /api/v1/asistencia/tokens": {
    cuerpo: never;
    respuesta: TokensResponse;
  };
  "POST /api/v1/asistencia/tokens": {
    cuerpo: EmitirTokenRequest;
    respuesta: TokenEmitidoResponse;
  };
  "DELETE /api/v1/asistencia/tokens/{token_id}": {
    cuerpo: never;
    respuesta: TokenRevocadoResponse;
  };
  "GET /api/v1/auditoria": {
    cuerpo: never;
    respuesta: PaginaAuditoria;
  };
  "GET /api/v1/boveda/clientes/{clave}/cfdi": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/boveda/clientes/{clave}/cfdi": {
    cuerpo: Body_importar_cfdi_api_v1_boveda_clientes__clave__cfdi_post;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/boveda/clientes/{clave}/cfdi/{uuid}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/boveda/clientes/{clave}/cfdi/{uuid}/xml": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/boveda/clientes/{clave}/resumen": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calendario": {
    cuerpo: CalendarioRequest;
    respuesta: CalendarioResponse;
  };
  "GET /api/v1/cartera/clientes": {
    cuerpo: never;
    respuesta: ClientesCarteraResponse;
  };
  "DELETE /api/v1/cartera/clientes/{cliente_id}": {
    cuerpo: never;
    respuesta: OperacionResponse;
  };
  "PUT /api/v1/cartera/clientes/{cliente_id}": {
    cuerpo: ClienteCarteraSchema;
    respuesta: OperacionResponse;
  };
  "GET /api/v1/cartera/clientes/{cliente_id}/empleados": {
    cuerpo: never;
    respuesta: EmpleadosCarteraResponse;
  };
  "DELETE /api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}": {
    cuerpo: never;
    respuesta: OperacionResponse;
  };
  "PUT /api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}": {
    cuerpo: EmpleadoCarteraSchemaInput;
    respuesta: OperacionResponse;
  };
  "GET /api/v1/clientes/{clave}/credenciales": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/credenciales": {
    cuerpo: Body_subir_credencial_api_v1_clientes__clave__credenciales_post;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/clientes/{clave}/credenciales/{credencial_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/comparar-regimenes": {
    cuerpo: CompararRegimenRequest;
    respuesta: CompararRegimenResponse;
  };
  "POST /api/v1/deducciones-personales": {
    cuerpo: DeduccionesPersonalesRequest;
    respuesta: DeduccionesPersonalesResponse;
  };
  "GET /api/v1/despacho/calendario": {
    cuerpo: never;
    respuesta: CalendarioPatronalResponse;
  };
  "GET /api/v1/despacho/clientes": {
    cuerpo: never;
    respuesta: ClientesResponse;
  };
  "GET /api/v1/despacho/clientes/{cliente_id}": {
    cuerpo: never;
    respuesta: ClienteDetalle;
  };
  "GET /api/v1/despacho/clientes/{cliente_id}/empleados": {
    cuerpo: never;
    respuesta: EmpleadosClienteResponse;
  };
  "GET /api/v1/despacho/primas-de-riesgo": {
    cuerpo: never;
    respuesta: PrimasDeRiesgoResponse;
  };
  "POST /api/v1/diot": {
    cuerpo: DIOTRequest;
    respuesta: DIOTResponse;
  };
  "POST /api/v1/estado-cuenta": {
    cuerpo: EstadoCuentaRequest;
    respuesta: EstadoCuentaResponse;
  };
  "POST /api/v1/multi-periodo": {
    cuerpo: MultiPeriodoRequest;
    respuesta: MultiPeriodoResponse;
  };
  "POST /api/v1/nomina/calcular-periodo": {
    cuerpo: CalcularPeriodoRequest;
    respuesta: CalcularPeriodoResponse;
  };
  "POST /api/v1/nomina/cfdi": {
    cuerpo: CFDINominaRequest;
    respuesta: CFDINominaResponse;
  };
  "GET /api/v1/nomina/demo/plantilla": {
    cuerpo: never;
    respuesta: PlantillaDemoResponse;
  };
  "GET /api/v1/nomina/periodo-sugerido": {
    cuerpo: never;
    respuesta: PeriodoSugeridoResponse;
  };
  "POST /api/v1/nomina/sbc": {
    cuerpo: SBCRequest;
    respuesta: SBCResponse;
  };
  "POST /api/v1/pre-declaracion": {
    cuerpo: PreDeclaracionRequest;
    respuesta: PreDeclaracionResponse;
  };
  "POST /api/v1/pre-declaracion-anual": {
    cuerpo: PreDeclaracionRequest;
    respuesta: PreDeclaracionResponse;
  };
  "POST /api/v1/retenciones-terceros": {
    cuerpo: RetencionesRequest;
    respuesta: RetencionesResponse;
  };
  "GET /api/v1/trabajos": {
    cuerpo: never;
    respuesta: ListaTrabajos;
  };
  "POST /api/v1/trabajos/clientes/{clave}/diagnostico": {
    cuerpo: EncolarDiagnostico | null;
    respuesta: UnTrabajo;
  };
  "GET /api/v1/trabajos/{trabajo_id}": {
    cuerpo: never;
    respuesta: UnTrabajo;
  };
  "POST /api/v1/trabajos/{trabajo_id}/cancelar": {
    cuerpo: never;
    respuesta: UnTrabajo;
  };
  "POST /api/v1/trabajos/{trabajo_id}/reintentar": {
    cuerpo: never;
    respuesta: UnTrabajo;
  };
  "GET /health": {
    cuerpo: never;
    respuesta: HealthResponse;
  };
  "GET /health/integraciones": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
}
