/**
 * TIPOS GENERADOS — NO EDITAR A MANO (P0-08).
 *
 * Salen de `app.main:app.openapi()` por `apps/api/scripts/exportar_openapi.py`:
 *   cd apps/api && PYTHONPATH=. python scripts/exportar_openapi.py
 * `apps/api/tests/test_contrato_openapi.py` falla si este archivo quedó viejo.
 */

/** `POST /calculadoras/actualizacion-recargos`. */
export interface ActualizacionRequest {
  monto: number | string;
  fecha_limite: string;
  fecha_pago: string;
  tipo_recargo?: "mora" | "prorroga" | "parcialidades_12" | "parcialidades_24" | "parcialidades_mas_24";
  modo_factor?: "truncar" | "redondear" | "sin_redondeo";
  tope_meses?: number;
}

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

export interface AjusteAnualRequest {
  ejercicio: number;
  trabajadores?: AjusteAnualTrabajador[];
}

export interface AjusteAnualTrabajador {
  empleado_no: string;
  ingresos_gravados: number | string;
  ingresos_exentos?: number | string;
  isr_retenido: number | string;
  subsidio_correspondido?: number | string;
  comunico_que_declara?: boolean;
  impuesto_local_retenido?: number | string;
  tasa_impuesto_local?: number | string | null;
}

/** `POST /impuestos/clientes/{clave}/anual` y `.../anual/papeles`. */
export interface AnualRequest {
  anio: number;
  pagos_provisionales?: Record<string, number | string>;
}

export interface ArchivoSchema {
  nombre: string;
  mime: string;
  base64: string;
  sha256: string;
}

export interface BimestreVariable {
  ejercicio: number;
  bimestre: number;
  aplicar?: boolean;
}

export interface Body_importar_api_v1_nomina_clientes__clave__cedulas_post {
  archivo: string;
  tipo: "EMA" | "EBA";
  ejercicio: number;
  periodo: number;
  configuracion?: string;
}

export interface Body_importar_cfdi_api_v1_boveda_clientes__clave__cfdi_post {
  archivos: string[];
}

export interface Body_importar_estado_api_v1_conciliacion_clientes__clave__cuentas__cuenta_id__estados_post {
  archivo: string;
  formato?: "csv" | "xlsx" | "ofx" | "pdf" | null;
  plantilla_id?: number | null;
  mapeo?: string | null;
}

export interface Body_subir_credencial_api_v1_clientes__clave__credenciales_post {
  tipo: string;
  password: string;
  cer: string;
  key: string;
}

export interface Body_subir_pdf_api_v1_sat_clientes__clave__opinion_pdf_post {
  archivo: string;
  tipo?: "opinion" | "constancia";
  resultado?: "positiva" | "negativa" | "sin_obligaciones" | "desconocido" | null;
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
  parametros?: ParametrosPatron;
  empleados?: EmpleadoNominaSchema[] | null;
  tipo?: "ordinaria" | "extraordinaria" | "asimilados";
  variables?: VariablesEmpleadoSchema[];
  guardar?: boolean;
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
  tipo?: string;
  periodo_id?: number | null;
  criterios?: Record<string, string>;
  clave_periodicidad?: string;
}

/** Respuesta genérica de las calculadoras: el resultado con su desglose. */
export interface CalculoResponse {
  exito?: boolean;
  tipo: string;
  periodo_id?: number | null;
  resultado: Record<string, unknown>;
  advertencias?: string[];
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

export interface CambioSBC {
  fecha: string;
  sbc: number | string;
  tipo_salario?: "0" | "1" | "2" | null;
  motivo?: "aumento" | "prestaciones" | "correccion";
  nota?: string;
  actualizar_ficha?: boolean;
}

export interface Cancelacion {
  motivo?: string;
}

export interface CancelarCfdi {
  motivo: string;
  folio_sustitucion?: string | null;
}

export interface CancelarRetencion {
  motivo: string;
  folio_sustitucion?: string | null;
}

/** Captura del contador en un renglón del resumen. */
export interface CapturaRenglon {
  importe_a_pagar?: number | string | null;
  subsidio?: number | string;
  compensaciones?: number | string;
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

export interface Cierre {
  forzar?: boolean;
  motivo?: string;
}

export interface CierreAnual {
  traspasar_resultado?: boolean;
  forzar?: boolean;
  motivo?: string;
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
  criterios_nomina?: CriteriosNominaSchema;
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

export interface ComparacionResponse {
  exito?: boolean;
  a: ResumenPeriodoSchema;
  b: ResumenPeriodoSchema;
  diferencia_neto: string;
  diferencia_isr: string;
  diferencia_percepciones: string;
  por_empleado: DiferenciaEmpleado[];
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

export interface ConciliacionManual {
  banco: string[];
  libros: string[];
  motivo?: string;
}

/** Criterio del despacho por cliente (DP-3). Cada default está documentado. */
export interface ConfigImpuestosSchema {
  modo_factor?: "truncar" | "redondear" | "sin_redondeo";
  tipo_recargo?: "mora" | "prorroga" | "parcialidades_12" | "parcialidades_24" | "parcialidades_mas_24";
  tope_meses_recargos?: number;
  region_fronteriza?: boolean;
  proporcion_iva_modo?: "calculada" | "fija";
  proporcion_iva_fija?: number | string | null;
  asignacion_iva?: Record<string, "gravado" | "exento" | "indistinto">;
  isn_aplicar_adicional?: boolean;
  isn_claves_excluidas?: string[];
  isn_claves_incluidas?: string[];
  saldo_favor_iva_inicial?: number | string;
  iva_no_objeto_excluidos?: string[];
}

/** Clasificación de un proveedor en la DIOT. `None` = se deduce de los CFDI. */
export interface ConfigProveedorDiotSchema {
  tipo_tercero?: "04" | "05" | "15" | null;
  tipo_operacion?: "02" | "03" | "06" | "07" | "08" | "85" | "87" | null;
  region_8?: "norte" | "sur";
  importacion?: "tangibles" | "intangibles";
  asignacion_iva?: "gravadas" | "proporcion";
  iva_no_acreditable?: "" | "proporcion" | "requisitos" | "exentas" | "no_objeto";
  id_fiscal?: string;
  nombre_extranjero?: string;
  pais?: string;
  jurisdiccion?: string;
  efectos_fiscales?: "01" | "02";
}

export interface Contrapartida {
  cuenta_id: number;
  importe: number | string;
}

/** Tipo de contribuyente en el ecosistema Fiscalito. */
export type ContributorType = "asalariado" | "independiente" | "arrendamiento" | "plataformas" | "pyme";

/** Criterios de nómina del cliente (P4, DP-3). Opciones y explicación en */
export interface CriteriosNominaSchema {
  parcial?: "tarifa_proporcional" | "tarifa_periodo";
  febrero?: "quince_siempre" | "dias_calendario";
  prestaciones?: "mayor" | "ficha";
  isr_extraordinario?: "art_96" | "art_174";
  ptu_remanente?: "no_se_reparte" | "redistribuir" | "sumar_siguiente_ejercicio";
}

export interface CriteriosResponse {
  exito?: boolean;
  defaults: Record<string, string>;
  opciones: Record<string, Record<string, string>>;
}

export interface CuentaBancariaCambio {
  banco?: string | null;
  nombre?: string | null;
  numero?: string | null;
  clabe?: string | null;
  cuenta_contable_id?: number | null;
  ventana_dias?: number | null;
  umbral?: number | null;
  activa?: boolean | null;
}

export interface CuentaBancariaEntrada {
  banco: string;
  nombre?: string;
  numero?: string;
  clabe?: string;
  moneda?: string;
  cuenta_contable_id: number;
  ventana_dias?: number;
  umbral?: number;
  activa?: boolean;
}

export interface CuentaCambio {
  numero?: string | null;
  nombre?: string | null;
  codigo_agrupador?: string | null;
  naturaleza?: "deudora" | "acreedora" | null;
  tipo?: "activo" | "pasivo" | "capital" | "ingreso" | "costo" | "gasto" | "orden" | null;
}

export interface CuentaEntrada {
  numero: string;
  nombre: string;
  codigo_agrupador: string;
  padre_id?: number | null;
  nivel?: number | null;
  naturaleza?: "deudora" | "acreedora" | null;
  tipo?: "activo" | "pasivo" | "capital" | "ingreso" | "costo" | "gasto" | "orden" | null;
}

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

export interface DIOTCliente {
  periodo_year: number;
  incluir_explicacion?: boolean;
  periodo_month: number;
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

export interface DatoBancoSchema {
  clave: string;
  etiqueta: string;
  patron: string;
  obligatorio: boolean;
  default: string;
}

/** Datos de un cliente persona moral para un ejercicio (P3-01). */
export interface DatosAnualesPMSchema {
  coeficiente_utilidad?: number | string | null;
  utilidad_fiscal_base?: number | string | null;
  ingresos_nominales_base?: number | string | null;
  anticipos_miembros_base?: number | string;
  ptu_pagada?: number | string;
  mes_pago_ptu?: number;
  perdidas?: PerdidaSchema[];
  retenciones_bancarias?: Record<string, number | string>;
  pagos_efectuados?: Record<string, number | string>;
  saldos_creditos?: (number | string)[];
  saldos_deudas?: (number | string)[];
  cuentas_creditos?: string[];
  cuentas_deudas?: string[];
  cuentas_no_deducibles?: string[];
  deduccion_inversiones?: number | string;
  deducciones_adicionales?: number | string;
  no_deducibles_adicionales?: number | string;
  ingresos_adicionales?: number | string;
  estimulos?: EstimuloSchema[];
  fuente?: "auto" | "contabilidad" | "boveda";
  factor_exentos_nomina?: number | string;
  aai_en_resico?: boolean;
  no_deducibles_art28_xxx?: number | string | null;
  cuentas_art28_xxx?: string[];
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

export interface DiferenciaEmpleado {
  empleado_no: string;
  nombre: string;
  neto_a: string | null;
  neto_b: string | null;
  diferencia: string;
}

export interface DispersionRequest {
  layout: string;
  cuenta_cargo_id?: number | null;
  fecha_aplicacion?: string | null;
  datos_banco?: Record<string, string>;
  columnas?: string[] | null;
  separador?: string;
  formato?: string;
  encabezado?: boolean;
}

export interface DispersionResponse {
  exito?: boolean;
  layout: LayoutSchema;
  archivo: ArchivoSchema | null;
  incluidos: IncluidoSchema[];
  excluidos: ExcluidoSchema[];
  total_nomina: string;
  total_archivo: string;
  total_excluidos: string;
  cuadra: boolean;
  advertencias: string[];
}

export interface DispositivoGuardadoResponse {
  exito?: boolean;
  id: string;
  mensaje: string;
}

/** Un checador tal como lo captura el despacho. El `id` va en la URL, no aquí. */
export interface DispositivoSchema {
  nombre: string;
  ip?: string;
  puerto?: number;
  marca?: string;
  modelo?: string;
  serial?: string;
  employee_nos?: string[];
  notas?: string;
}

export interface DispositivosResponse {
  exito?: boolean;
  cliente_id: string;
  total: number;
  dispositivos: Record<string, unknown>[];
}

export interface EmitirRetencion {
  rfc_tercero: string;
  ejercicio: number;
  mes_ini: number;
  mes_fin: number;
  cve_retenc?: string | null;
  desc_retenc?: string;
  domicilio_fiscal?: string | null;
  nombre?: string | null;
}

export interface EmitirTokenRequest {
  cliente: string;
  etiqueta?: string;
  dispositivo?: string | null;
}

/** Un empleado tal como lo guarda el despacho. */
export interface EmpleadoCarteraSchemaInput {
  forma_pago?: FormaPagoEmpleado;
  banco?: string;
  clabe?: string;
  numero_cuenta?: string;
  correo?: string;
  celular?: string;
  consentimiento_whatsapp?: boolean;
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
  fecha_baja?: string | null;
  tipo_regimen?: string;
  causa_baja?: string;
  tipo_salario?: string;
  tipo_trabajador?: string;
  jornada?: string;
  umf?: string;
  rfc?: string;
  curp?: string;
  codigo_postal?: string;
  departamento?: string;
  sindicalizado?: boolean;
  tipo_contrato?: TipoContrato;
  prestaciones?: PrestacionesSchemaInput;
  nss?: string;
  employee_no?: string | null;
  enrolamiento?: EstatusEnrolamiento;
}

/** Un empleado tal como lo guarda el despacho. */
export interface EmpleadoCarteraSchemaOutput {
  forma_pago?: FormaPagoEmpleado;
  banco?: string;
  clabe?: string;
  numero_cuenta?: string;
  correo?: string;
  celular?: string;
  consentimiento_whatsapp?: boolean;
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
  fecha_baja?: string | null;
  tipo_regimen?: string;
  causa_baja?: string;
  tipo_salario?: string;
  tipo_trabajador?: string;
  jornada?: string;
  umf?: string;
  rfc?: string;
  curp?: string;
  codigo_postal?: string;
  departamento?: string;
  sindicalizado?: boolean;
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

/** Un empleado guardado que no pasa la validación actual, y por qué (R-10). */
export interface EmpleadoIlegible {
  empleado_no: string;
  nombre?: string;
  razon: string;
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
  ilegibles_detalle?: EmpleadoIlegible[];
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

export interface EnviarRequest {
  canal: "correo" | "whatsapp";
}

export interface EnvioSchema {
  id: number;
  empleado_no: string;
  destino: string;
  estado: string;
  intentos: number;
  error: string;
  timbrado: boolean;
  enviado_en: string | null;
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

export interface EstadoEnviosResponse {
  exito?: boolean;
  canal: "correo" | "whatsapp";
  envios: EnvioSchema[];
  omitidos: OmitidoSchema[];
  resumen: Record<string, number>;
  trabajo: Record<string, string | number | null> | null;
}

/** Si la persona ya tiene su rostro dado de alta en el checador. */
export type EstatusEnrolamiento = "pendiente" | "enrolado";

/** Disminución configurable de la utilidad (estímulo), con fundamento. */
export interface EstimuloSchema {
  concepto: string;
  importe: number | string;
  fundamento?: string;
  desde_mes?: number;
  en_provisionales?: boolean;
}

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

export interface ExcluidoSchema {
  empleado_no: string;
  nombre: string;
  neto: string;
  causa: string;
  motivo: string;
}

/** Cómo se le paga el neto. Sólo `transferencia` entra a la dispersión. */
export type FormaPagoEmpleado = "transferencia" | "efectivo" | "cheque";

/** De donde vino el evento. `csv` queda para el plan C (import manual). */
export type FuenteChecada = "hikvision" | "simulado" | "csv";

export interface GenerarArchivo {
  destino: "idse_08" | "idse_07" | "idse_02" | "sua_trabajadores" | "sua_movimientos";
  ids?: number[] | null;
  al?: string | null;
  desde?: string | null;
  hasta?: string | null;
}

export interface GenerarTareas {
  desde: string;
  hasta: string;
  cliente?: string;
  responsable_uid?: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** Modelo de respuesta del endpoint de salud. */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface HistorialResponse {
  exito?: boolean;
  cliente: string;
  periodos: ResumenPeriodoSchema[];
}

export interface HistoricaEntrada {
  desde: string;
  hasta?: string | null;
  seleccion?: Seleccion | null;
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

export interface IncapacidadSchema {
  tipo: "01" | "02" | "03";
  dias: number;
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

export interface IncluidoSchema {
  empleado_no: string;
  nombre: string;
  importe: string;
  banco: string;
  banco_nombre: string;
  tipo_cuenta: string;
  cuenta: string;
  interbancario: boolean;
}

export interface InfonavitSchema {
  tipo: "porcentaje" | "cuota_fija" | "factor";
  valor: number | string;
  valor_unidad_diario?: number | string | null;
}

/** `POST /calculadoras/isn`. */
export interface IsnRequest {
  cliente?: string | null;
  anio?: number | null;
  mes?: number | null;
  entidad?: string | null;
  fecha?: string | null;
  percepciones?: PercepcionEntrada[];
  total_erogaciones?: number | string | null;
  aplicar_adicional?: boolean;
  claves_excluidas?: string[];
}

/** `POST /calculadoras/isr-resico`. */
export interface IsrResicoRequest {
  ingresos_cobrados: number | string;
  isr_retenido?: number | string;
}

/** `POST /calculadoras/isr-sueldos`. */
export interface IsrSueldosRequest {
  base_gravable: number | string;
  clave_periodicidad?: string;
  fecha_pago: string;
  ingreso_gravado_mensual?: number | string | null;
  dias_periodo?: number;
  es_trabajador_de_salario_minimo?: boolean;
}

/** `POST /impuestos/clientes/{clave}/iva`. */
export interface IvaPeriodoRequest {
  anio: number;
  meses: number[];
  saldo_favor_inicial?: number | string | null;
  opciones_saldo?: Record<string, "acreditar" | "devolucion" | "compensacion">;
}

export interface LayoutSchema {
  id: string;
  nombre: string;
  banco: string | null;
  estado: string;
  fuente: string;
  interbancario: boolean;
  datos_requeridos: DatoBancoSchema[];
}

export interface LayoutsResponse {
  exito?: boolean;
  layouts: LayoutSchema[];
  columnas_genericas: Record<string, string>;
  columnas_default: string[];
  bancos: Record<string, string>;
  datos_guardados?: Record<string, Record<string, string>>;
}

export interface ListaTrabajos {
  exito?: boolean;
  trabajos: TrabajoSalida[];
}

export interface MarcarMovimientos {
  ids: number[];
  estado: "enviado" | "acuse" | "cancelado";
  acuse?: string;
}

export interface MarcarObligacion {
  clave: string;
  estado: "presentada" | "pendiente";
  fecha_presentacion?: string | null;
  responsable_uid?: string | null;
  nota?: string;
}

export interface MovimientoEntrada {
  cuenta_id: number;
  cargo?: number | string;
  abono?: number | string;
  concepto?: string;
  uuid?: string;
  rfc?: string;
}

export interface MultiPeriodoCliente {
  periodo_year: number;
  incluir_explicacion?: boolean;
  periodos: number[];
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

export interface OmitidoSchema {
  empleado_no: string;
  nombre: string;
  motivo: string;
}

export interface OperacionResponse {
  exito?: boolean;
  mensaje: string;
}

export interface PTURequest {
  ejercicio: number;
  renta_gravable: number | string;
  fecha_pago: string;
  trabajadores: PTUTrabajadorSchema[];
  guardar?: boolean;
}

export interface PTUTrabajadorSchema {
  empleado_no: string;
  dias_trabajados: number;
  salarios_devengados: number | string;
  tipo?: "planta" | "sindicalizado" | "eventual" | "confianza" | "director";
  promedio_ptu_3_anios?: number | string;
}

export interface PaginaAuditoria {
  exito?: boolean;
  eventos: EventoSalida[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** `POST /impuestos/clientes/{clave}/pm/pagos-provisionales`. */
export interface PagosProvisionalesPMRequest {
  anio: number;
  mes: number;
}

/** Parámetros de la empresa. P4-01: si no vienen, se toman de la ficha del cliente. */
export interface ParametrosPatron {
  prima_riesgo?: number | string | null;
  clave_periodicidad?: string | null;
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

export interface PensionSchema {
  tipo: "porcentaje" | "monto";
  valor: number | string;
  base?: "neto" | "bruto";
}

export interface PercepcionCapturadaSchema {
  clave: "002" | "010" | "038" | "049";
  importe: number | string;
  concepto?: string;
}

/** Una percepción (clave c_TipoPercepcion) para el ISN. */
export interface PercepcionEntrada {
  clave: string;
  importe: number | string;
  descripcion?: string;
}

/** Pérdida fiscal pendiente (Art. 57). `actualizada_a` 'AAAA-MM' o vacío si es histórica. */
export interface PerdidaSchema {
  ejercicio: number;
  remanente: number | string;
  actualizada_a?: string | null;
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

export interface PeriodoGuardadoResponse {
  exito?: boolean;
  periodo: ResumenPeriodoSchema;
  criterios: Record<string, unknown>;
  parametros: Record<string, unknown>;
  resultado: Record<string, unknown>;
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

export interface PlantillaSchema {
  canal: "correo" | "whatsapp";
  asunto?: string;
  cuerpo?: string;
  plantilla_whatsapp?: string;
  idioma?: string;
  personalizada?: boolean;
}

export interface PlantillasResponse {
  exito?: boolean;
  variables: string[];
  plantillas: PlantillaSchema[];
}

export interface PolizaCambio {
  fecha?: string | null;
  concepto?: string | null;
  movimientos?: MovimientoEntrada[] | null;
}

export interface PolizaDesdeBanco {
  contrapartidas: Contrapartida[];
  concepto?: string;
}

export interface PolizaEntrada {
  tipo: "ingreso" | "egreso" | "diario";
  fecha: string;
  concepto?: string;
  movimientos: MovimientoEntrada[];
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

export interface PreDeclaracionCliente {
  periodo_year: number;
  incluir_explicacion?: boolean;
  periodo_month?: number | null;
  periodo_bimestre?: number | null;
  pagos_provisionales_anteriores?: number;
  ingresos_acumulados_anteriores?: number;
  deducciones_acumuladas_anteriores?: number;
  predial_pagado?: number;
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

/** `POST /calculadoras/ptu`. */
export interface PtuRequest {
  utilidad_repartible: number | string;
  dias_trabajador: number;
  salario_trabajador: number | string;
  total_dias_todos: number;
  total_salarios_todos: number | string;
  salario_diario: number | string;
  promedio_ptu_3_anios?: number | string;
  fecha_pago: string;
}

export interface RangoEntrada {
  desde: string;
  hasta: string;
  seleccion?: Seleccion | null;
}

export interface RangoEstatus {
  desde: string;
  hasta: string;
}

export interface Reapertura {
  motivo: string;
}

export interface ReboteRequest {
  canal: "correo" | "whatsapp";
  id_mensaje: string;
  motivo?: string;
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
  tipo_regimen?: string;
  dias_en_periodo?: number | null;
  dias_incapacidad?: number;
  parcial?: boolean;
  tarifa?: string;
  isr_causado?: string | null;
  subsidio_causado?: string;
  sbc_variable_integrable?: string;
}

/** Qué regla de cómputo produjo la fecha límite. */
export type RegimenDePlazo = "imss" | "imss_sin_prorroga" | "imss_aviso" | "sat" | "lft";

export interface RegistrarDeclaracion {
  tipo: "mensual" | "diot" | "balanza" | "anual";
  periodo: string;
  fecha_presentacion?: string | null;
  ingresos_declarados?: number | string | null;
  importe_pagado?: number | string | null;
  numero_operacion?: string;
}

export interface ReglaCambio {
  criterio?: "rfc" | "clave" | "prefijo" | "uso" | "descripcion" | null;
  valor?: string | null;
  cuenta_numero?: string | null;
  prioridad?: number | null;
  activa?: boolean | null;
}

export interface ReglaEntrada {
  criterio: "rfc" | "clave" | "prefijo" | "uso" | "descripcion";
  valor: string;
  cuenta_numero: string;
  prioridad?: number;
  activa?: boolean;
}

/** Resultado ISR estimado para un regimen fiscal especifico. */
export interface ResultadoRegimen {
  regimen: string;
  nombre: string;
  isr_anual: number;
  isr_mensual: number;
  disponible: boolean;
  notas?: string[];
}

export interface ResumenPeriodoSchema {
  id: number;
  tipo: string;
  periodicidad: string;
  inicio: string;
  fin: string;
  fecha_pago: string;
  estado: string;
  empleados: number;
  total_percepciones: string;
  total_deducciones: string;
  total_isr: string;
  total_neto: string;
}

/** `POST /impuestos/clientes/{clave}/resumen`. */
export interface ResumenRequest {
  anio: number;
  mes: number;
  fecha_pago: string;
  fecha_limite?: string | null;
  capturas?: Record<string, CapturaRenglon>;
  formato?: "json" | "xlsx" | "csv";
}

export interface RetencionesCliente {
  periodo_year: number;
  incluir_explicacion?: boolean;
  periodo_month?: number | null;
  periodo_bimestre?: number | null;
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

export interface SaldoEntrada {
  cuenta_id: number;
  deudor?: number | string;
  acreedor?: number | string;
}

export interface SaldosEntrada {
  saldos: SaldoEntrada[];
}

export interface Seleccion {
  emitidos?: boolean;
  recibidos?: boolean;
  metadata?: boolean;
  cancelados?: boolean;
}

export interface SolicitudEntrada {
  documento: "catalogo" | "balanza" | "polizas" | "auxiliar_cuentas" | "auxiliar_folios";
  anio: number;
  mes: number;
  tipo_envio?: "N" | "C";
  fecha_mod_bal?: string | null;
  tipo_solicitud?: "" | "AF" | "FC" | "DE" | "CO";
  num_orden?: string;
  num_tramite?: string;
  sellar?: boolean;
}

export interface TareaCambio {
  titulo?: string | null;
  fecha?: string | null;
  responsable_uid?: string | null;
  descripcion?: string | null;
  estado?: "pendiente" | "en_proceso" | "hecha" | null;
}

export interface TareaNueva {
  titulo: string;
  fecha: string;
  cliente?: string | null;
  responsable_uid?: string;
  descripcion?: string;
  estado?: "pendiente" | "en_proceso" | "hecha";
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

/** Incidencias y variables capturadas por periodo (P4-05). */
export interface VariablesEmpleadoSchema {
  empleado_no: string;
  horas_dobles?: number | string;
  horas_triples?: number | string;
  horas_jornada?: number | string;
  domingos_trabajados?: number;
  prima_dominical?: number | string;
  dias_vacaciones?: number;
  prima_vacacional?: number | string;
  incapacidades?: IncapacidadSchema[];
  faltas_adicionales?: number;
  percepciones?: PercepcionCapturadaSchema[];
  infonavit?: InfonavitSchema | null;
  fonacot?: number | string;
  prestamo?: number | string;
  pension?: PensionSchema | null;
  viaticos_comprobados?: number | string;
  prima_vacacional_exenta_previa?: number | string;
}

/** Zona geografica que determina el salario minimo aplicable. */
export type ZonaSalarioMinimo = "general" | "zlfn";

export interface _ConExplicacion {
  periodo_year: number;
  incluir_explicacion?: boolean;
}

export interface app__routes__conciliacion__PlantillaEntrada {
  nombre: string;
  banco?: string;
  formato?: "csv" | "xlsx";
  mapeo: Record<string, unknown>;
}

export interface app__routes__conciliacion__Rango {
  desde?: string | null;
  hasta?: string | null;
  incluir_cfdi?: boolean;
}

export interface app__routes__contabilidad__ConfigEntrada {
  automatica_ingresos?: boolean | null;
  automatica_egresos?: boolean | null;
  automatica_pagos?: boolean | null;
  automatica_nomina?: boolean | null;
  pue_registra_cobro?: boolean | null;
  uso_s01_no_deducible?: boolean | null;
  efectivo_no_deducible?: boolean | null;
  retenciones_al_pago?: boolean | null;
  tope_activo?: number | string | null;
  plantilla_concepto?: string | null;
  cuentas?: Record<string, string> | null;
  formas_pago?: Record<string, string> | null;
  fecha_saldos_iniciales?: string | null;
}

export interface app__routes__contabilidad__Rango {
  desde: string;
  hasta: string;
  segundo_plano?: boolean | null;
}

export interface app__routes__nomina_envio__PlantillaEntrada {
  asunto?: string;
  cuerpo?: string;
  plantilla_whatsapp?: string;
  idioma?: string;
}

export interface app__routes__sat_descarga__ConfigEntrada {
  activa?: boolean | null;
  emitidos?: boolean | null;
  recibidos?: boolean | null;
  metadata?: boolean | null;
  cancelados?: boolean | null;
  desde?: string | null;
  hora?: string | null;
}

export interface app__routes__sat_verificacion__ConfigEntrada {
  automatico?: boolean;
  dia_del_mes?: number;
  constancia?: boolean;
}

/** `POST /calculadoras/aguinaldo`. */
export interface app__schemas__impuestos__AguinaldoRequest {
  salario_diario: number | string;
  dias_aguinaldo?: number;
  dias_trabajados_en_el_anio?: number;
  fecha_pago: string;
  zona?: "general" | "zlfn";
}

/** `POST /calculadoras/finiquito`. */
export interface app__schemas__impuestos__FiniquitoRequest {
  salario_diario: number | string;
  fecha_ingreso: string;
  fecha_baja: string;
  dias_aguinaldo?: number;
  prima_vacacional?: number | string;
  dias_vacaciones_pendientes?: number | string;
  dias_pendientes_de_pago?: number | string;
  tipo?: "renuncia" | "despido_justificado" | "despido_injustificado" | "muerte" | "termino_contrato";
  zona?: "general" | "zlfn";
  salario_diario_integrado?: number | string | null;
  incluir_20_dias?: boolean;
}

export interface app__schemas__nomina_p4__AguinaldoRequest {
  ejercicio: number;
  fecha_pago: string;
  empleados?: string[];
  exento_ya_aplicado?: Record<string, number | string>;
  guardar?: boolean;
}

export interface app__schemas__nomina_p4__FiniquitoRequest {
  empleado_no: string;
  fecha_baja: string;
  causa: "renuncia" | "despido_justificado" | "despido_injustificado" | "muerte" | "termino_contrato";
  dias_salario_pendientes?: number;
  dias_vacaciones_pendientes?: number | string;
  aguinaldo_ya_pagado?: number | string;
  incluir_20_dias?: boolean;
  guardar?: boolean;
}

/** Toda ruta que publica la API. */
export type RutaApi =
  | "/api/v1/agenda/tareas"
  | "/api/v1/agenda/tareas/desde-obligaciones"
  | "/api/v1/agenda/tareas/{tarea_id}"
  | "/api/v1/agenda/usuarios"
  | "/api/v1/agente/predeclaracion"
  | "/api/v1/alertas"
  | "/api/v1/alertas/conteo"
  | "/api/v1/alertas/evaluar"
  | "/api/v1/alertas/{alerta_id}/resolver"
  | "/api/v1/asistencia/cerrar-periodo"
  | "/api/v1/asistencia/eventos"
  | "/api/v1/asistencia/tokens"
  | "/api/v1/asistencia/tokens/{token_id}"
  | "/api/v1/auditoria"
  | "/api/v1/boveda/clientes/{clave}/cfdi"
  | "/api/v1/boveda/clientes/{clave}/cfdi/{uuid}"
  | "/api/v1/boveda/clientes/{clave}/cfdi/{uuid}/xml"
  | "/api/v1/boveda/clientes/{clave}/facturas-calculo"
  | "/api/v1/boveda/clientes/{clave}/resumen"
  | "/api/v1/calculadoras/actualizacion-recargos"
  | "/api/v1/calculadoras/aguinaldo"
  | "/api/v1/calculadoras/fecha-limite"
  | "/api/v1/calculadoras/finiquito"
  | "/api/v1/calculadoras/isn"
  | "/api/v1/calculadoras/isn/tasas"
  | "/api/v1/calculadoras/isr-resico"
  | "/api/v1/calculadoras/isr-sueldos"
  | "/api/v1/calculadoras/ptu"
  | "/api/v1/calendario"
  | "/api/v1/calendario/cartera"
  | "/api/v1/cartera/clientes"
  | "/api/v1/cartera/clientes/{cliente_id}"
  | "/api/v1/cartera/clientes/{cliente_id}/dispositivos"
  | "/api/v1/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}"
  | "/api/v1/cartera/clientes/{cliente_id}/empleados"
  | "/api/v1/cartera/clientes/{cliente_id}/empleados/{empleado_no}"
  | "/api/v1/clientes/{clave}/calculos/diot"
  | "/api/v1/clientes/{clave}/calculos/estado-cuenta"
  | "/api/v1/clientes/{clave}/calculos/multi-periodo"
  | "/api/v1/clientes/{clave}/calculos/pre-declaracion"
  | "/api/v1/clientes/{clave}/calculos/pre-declaracion-anual"
  | "/api/v1/clientes/{clave}/calculos/retenciones-terceros"
  | "/api/v1/clientes/{clave}/credenciales"
  | "/api/v1/clientes/{clave}/credenciales/{credencial_id}"
  | "/api/v1/clientes/{clave}/declaraciones"
  | "/api/v1/clientes/{clave}/diot/proveedores"
  | "/api/v1/clientes/{clave}/diot/proveedores/{rfc}"
  | "/api/v1/clientes/{clave}/diot/{anio}/{mes}"
  | "/api/v1/clientes/{clave}/diot/{anio}/{mes}/txt"
  | "/api/v1/clientes/{clave}/obligaciones/estado"
  | "/api/v1/clientes/{clave}/retenciones-cfdi"
  | "/api/v1/clientes/{clave}/retenciones-cfdi/terceros"
  | "/api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/cancelar"
  | "/api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/pdf"
  | "/api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/xml"
  | "/api/v1/comparar-regimenes"
  | "/api/v1/conciliacion/bancos"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones/{conciliacion_id}"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliar"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/estados"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/poliza"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/sugerencia"
  | "/api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/reporte"
  | "/api/v1/conciliacion/clientes/{clave}/plantillas"
  | "/api/v1/conciliacion/clientes/{clave}/plantillas/{plantilla_id}"
  | "/api/v1/contabilidad-electronica/clientes/{clave}/enviar"
  | "/api/v1/contabilidad-electronica/clientes/{clave}/validar"
  | "/api/v1/contabilidad-electronica/clientes/{clave}/zip"
  | "/api/v1/contabilidad-electronica/documentos"
  | "/api/v1/contabilidad/clientes/{clave}/balanza"
  | "/api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}"
  | "/api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}/deshacer"
  | "/api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}/validacion"
  | "/api/v1/contabilidad/clientes/{clave}/config"
  | "/api/v1/contabilidad/clientes/{clave}/cuentas"
  | "/api/v1/contabilidad/clientes/{clave}/cuentas/sembrar"
  | "/api/v1/contabilidad/clientes/{clave}/cuentas/{cuenta_id}"
  | "/api/v1/contabilidad/clientes/{clave}/cuentas/{cuenta_id}/auxiliar"
  | "/api/v1/contabilidad/clientes/{clave}/periodos-cerrados"
  | "/api/v1/contabilidad/clientes/{clave}/periodos/{anio}"
  | "/api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/cerrar"
  | "/api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/reabrir"
  | "/api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/validacion"
  | "/api/v1/contabilidad/clientes/{clave}/polizas"
  | "/api/v1/contabilidad/clientes/{clave}/polizas/generar"
  | "/api/v1/contabilidad/clientes/{clave}/polizas/{poliza_id}"
  | "/api/v1/contabilidad/clientes/{clave}/polizas/{poliza_id}/cancelar"
  | "/api/v1/contabilidad/clientes/{clave}/reglas"
  | "/api/v1/contabilidad/clientes/{clave}/reglas/{regla_id}"
  | "/api/v1/contabilidad/clientes/{clave}/reportes/balance-general"
  | "/api/v1/contabilidad/clientes/{clave}/reportes/estado-resultados"
  | "/api/v1/contabilidad/clientes/{clave}/reportes/excel"
  | "/api/v1/contabilidad/clientes/{clave}/reportes/polizas"
  | "/api/v1/contabilidad/clientes/{clave}/saldos-iniciales"
  | "/api/v1/contabilidad/codigo-agrupador"
  | "/api/v1/deducciones-personales"
  | "/api/v1/despacho/calendario"
  | "/api/v1/despacho/clientes"
  | "/api/v1/despacho/clientes/{cliente_id}"
  | "/api/v1/despacho/clientes/{cliente_id}/empleados"
  | "/api/v1/despacho/primas-de-riesgo"
  | "/api/v1/diot"
  | "/api/v1/estado-cuenta"
  | "/api/v1/impuestos/clientes/{clave}/anual"
  | "/api/v1/impuestos/clientes/{clave}/anual/papeles"
  | "/api/v1/impuestos/clientes/{clave}/config"
  | "/api/v1/impuestos/clientes/{clave}/isn"
  | "/api/v1/impuestos/clientes/{clave}/iva"
  | "/api/v1/impuestos/clientes/{clave}/pm/datos/{anio}"
  | "/api/v1/impuestos/clientes/{clave}/pm/pagos-provisionales"
  | "/api/v1/impuestos/clientes/{clave}/resumen"
  | "/api/v1/multi-periodo"
  | "/api/v1/nomina/calcular-periodo"
  | "/api/v1/nomina/cfdi"
  | "/api/v1/nomina/clientes/{clave}/cedulas"
  | "/api/v1/nomina/clientes/{clave}/cedulas/plantilla"
  | "/api/v1/nomina/clientes/{clave}/cedulas/{cedula_id}"
  | "/api/v1/nomina/clientes/{clave}/cedulas/{cedula_id}/reporte"
  | "/api/v1/nomina/clientes/{clave}/cuotas-imss"
  | "/api/v1/nomina/clientes/{clave}/empleados/{empleado_no}/historial-sbc"
  | "/api/v1/nomina/clientes/{clave}/empleados/{empleado_no}/sbc"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss/archivo"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss/bimestre-variable"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss/lotes"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss/lotes/{lote_id}/archivo"
  | "/api/v1/nomina/clientes/{clave}/movimientos-imss/marcar"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi.zip"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/cancelar"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/pdf"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/xml"
  | "/api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/timbrar"
  | "/api/v1/nomina/clientes/{cliente_id}/aguinaldo"
  | "/api/v1/nomina/clientes/{cliente_id}/ajuste-anual"
  | "/api/v1/nomina/clientes/{cliente_id}/comparar"
  | "/api/v1/nomina/clientes/{cliente_id}/finiquito"
  | "/api/v1/nomina/clientes/{cliente_id}/historial"
  | "/api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}"
  | "/api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/cerrar"
  | "/api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/dispersion"
  | "/api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios"
  | "/api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios/{envio_id}/reenviar"
  | "/api/v1/nomina/clientes/{cliente_id}/ptu"
  | "/api/v1/nomina/criterios"
  | "/api/v1/nomina/demo/plantilla"
  | "/api/v1/nomina/dispersion/layouts"
  | "/api/v1/nomina/periodo-sugerido"
  | "/api/v1/nomina/recibos/envios/rebote"
  | "/api/v1/nomina/recibos/plantillas"
  | "/api/v1/nomina/recibos/plantillas/{canal}"
  | "/api/v1/nomina/sbc"
  | "/api/v1/pre-declaracion"
  | "/api/v1/pre-declaracion-anual"
  | "/api/v1/recibos/descarga/{envio_id}/{archivo}"
  | "/api/v1/retenciones-terceros"
  | "/api/v1/sat/cartera/semaforo"
  | "/api/v1/sat/clientes/{clave}/alertas/{alerta_id}/atender"
  | "/api/v1/sat/clientes/{clave}/bitacora"
  | "/api/v1/sat/clientes/{clave}/config"
  | "/api/v1/sat/clientes/{clave}/constancia"
  | "/api/v1/sat/clientes/{clave}/descargar"
  | "/api/v1/sat/clientes/{clave}/historica"
  | "/api/v1/sat/clientes/{clave}/opinion"
  | "/api/v1/sat/clientes/{clave}/opinion/config"
  | "/api/v1/sat/clientes/{clave}/opinion/obtener"
  | "/api/v1/sat/clientes/{clave}/opinion/pdf"
  | "/api/v1/sat/clientes/{clave}/opinion/{doc_id}/pdf"
  | "/api/v1/sat/clientes/{clave}/riesgos-69b"
  | "/api/v1/sat/clientes/{clave}/solicitudes"
  | "/api/v1/sat/clientes/{clave}/verificar-estatus"
  | "/api/v1/sat/listas/estado"
  | "/api/v1/trabajos"
  | "/api/v1/trabajos/clientes/{clave}/diagnostico"
  | "/api/v1/trabajos/{trabajo_id}"
  | "/api/v1/trabajos/{trabajo_id}/cancelar"
  | "/api/v1/trabajos/{trabajo_id}/reintentar"
  | "/health"
  | "/health/integraciones";

/** Cuerpo y respuesta (2xx) de cada operación, por `MÉTODO /ruta`. */
export interface OperacionesApi {
  "GET /api/v1/agenda/tareas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/agenda/tareas": {
    cuerpo: TareaNueva;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/agenda/tareas/desde-obligaciones": {
    cuerpo: GenerarTareas;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/agenda/tareas/{tarea_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/agenda/tareas/{tarea_id}": {
    cuerpo: TareaCambio;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/agenda/usuarios": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/agente/predeclaracion": {
    cuerpo: AgentePreDeclaracionRequest;
    respuesta: AgentePreDeclaracionResponse;
  };
  "GET /api/v1/alertas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/alertas/conteo": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/alertas/evaluar": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/alertas/{alerta_id}/resolver": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
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
  "GET /api/v1/boveda/clientes/{clave}/facturas-calculo": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/boveda/clientes/{clave}/resumen": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/actualizacion-recargos": {
    cuerpo: ActualizacionRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/aguinaldo": {
    cuerpo: app__schemas__impuestos__AguinaldoRequest;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/calculadoras/fecha-limite": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/finiquito": {
    cuerpo: app__schemas__impuestos__FiniquitoRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/isn": {
    cuerpo: IsnRequest;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/calculadoras/isn/tasas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/isr-resico": {
    cuerpo: IsrResicoRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/isr-sueldos": {
    cuerpo: IsrSueldosRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calculadoras/ptu": {
    cuerpo: PtuRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/calendario": {
    cuerpo: CalendarioRequest;
    respuesta: CalendarioResponse;
  };
  "GET /api/v1/calendario/cartera": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
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
  "GET /api/v1/cartera/clientes/{cliente_id}/dispositivos": {
    cuerpo: never;
    respuesta: DispositivosResponse;
  };
  "POST /api/v1/cartera/clientes/{cliente_id}/dispositivos": {
    cuerpo: DispositivoSchema;
    respuesta: DispositivoGuardadoResponse;
  };
  "DELETE /api/v1/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}": {
    cuerpo: never;
    respuesta: OperacionResponse;
  };
  "PUT /api/v1/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}": {
    cuerpo: DispositivoSchema;
    respuesta: DispositivoGuardadoResponse;
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
  "POST /api/v1/clientes/{clave}/calculos/diot": {
    cuerpo: DIOTCliente;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/calculos/estado-cuenta": {
    cuerpo: _ConExplicacion;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/calculos/multi-periodo": {
    cuerpo: MultiPeriodoCliente;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/calculos/pre-declaracion": {
    cuerpo: PreDeclaracionCliente;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/calculos/pre-declaracion-anual": {
    cuerpo: _ConExplicacion;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/calculos/retenciones-terceros": {
    cuerpo: RetencionesCliente;
    respuesta: Record<string, unknown>;
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
  "POST /api/v1/clientes/{clave}/declaraciones": {
    cuerpo: RegistrarDeclaracion;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/diot/proveedores": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/clientes/{clave}/diot/proveedores/{rfc}": {
    cuerpo: ConfigProveedorDiotSchema;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/diot/{anio}/{mes}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/diot/{anio}/{mes}/txt": {
    cuerpo: never;
    respuesta: unknown;
  };
  "PUT /api/v1/clientes/{clave}/obligaciones/estado": {
    cuerpo: MarcarObligacion;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/retenciones-cfdi": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/retenciones-cfdi": {
    cuerpo: EmitirRetencion;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/retenciones-cfdi/terceros": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/cancelar": {
    cuerpo: CancelarRetencion;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/pdf": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/clientes/{clave}/retenciones-cfdi/{uuid}/xml": {
    cuerpo: never;
    respuesta: unknown;
  };
  "POST /api/v1/comparar-regimenes": {
    cuerpo: CompararRegimenRequest;
    respuesta: CompararRegimenResponse;
  };
  "GET /api/v1/conciliacion/bancos": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/cuentas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/conciliacion/clientes/{clave}/cuentas": {
    cuerpo: CuentaBancariaEntrada;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PATCH /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}": {
    cuerpo: CuentaBancariaCambio;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones": {
    cuerpo: ConciliacionManual;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones/{conciliacion_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/conciliar": {
    cuerpo: app__routes__conciliacion__Rango;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/estados": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/estados": {
    cuerpo: Body_importar_estado_api_v1_conciliacion_clientes__clave__cuentas__cuenta_id__estados_post;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/poliza": {
    cuerpo: PolizaDesdeBanco;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/sugerencia": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/cuentas/{cuenta_id}/reporte": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/conciliacion/clientes/{clave}/plantillas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/conciliacion/clientes/{clave}/plantillas": {
    cuerpo: app__routes__conciliacion__PlantillaEntrada;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/conciliacion/clientes/{clave}/plantillas/{plantilla_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad-electronica/clientes/{clave}/enviar": {
    cuerpo: SolicitudEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad-electronica/clientes/{clave}/validar": {
    cuerpo: SolicitudEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad-electronica/clientes/{clave}/zip": {
    cuerpo: SolicitudEntrada;
    respuesta: unknown;
  };
  "GET /api/v1/contabilidad-electronica/documentos": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/balanza": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}": {
    cuerpo: CierreAnual;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}/deshacer": {
    cuerpo: Reapertura;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/cierre-anual/{anio}/validacion": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/config": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/contabilidad/clientes/{clave}/config": {
    cuerpo: app__routes__contabilidad__ConfigEntrada;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/cuentas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/cuentas": {
    cuerpo: CuentaEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/cuentas/sembrar": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/contabilidad/clientes/{clave}/cuentas/{cuenta_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PATCH /api/v1/contabilidad/clientes/{clave}/cuentas/{cuenta_id}": {
    cuerpo: CuentaCambio;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/cuentas/{cuenta_id}/auxiliar": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/periodos-cerrados": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/periodos/{anio}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/cerrar": {
    cuerpo: Cierre;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/reabrir": {
    cuerpo: Reapertura;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/periodos/{anio}/{mes}/validacion": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/polizas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/polizas": {
    cuerpo: PolizaEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/polizas/generar": {
    cuerpo: app__routes__contabilidad__Rango;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/polizas/{poliza_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PATCH /api/v1/contabilidad/clientes/{clave}/polizas/{poliza_id}": {
    cuerpo: PolizaCambio;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/polizas/{poliza_id}/cancelar": {
    cuerpo: Cancelacion;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/contabilidad/clientes/{clave}/reglas": {
    cuerpo: ReglaEntrada;
    respuesta: Record<string, unknown>;
  };
  "DELETE /api/v1/contabilidad/clientes/{clave}/reglas/{regla_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PATCH /api/v1/contabilidad/clientes/{clave}/reglas/{regla_id}": {
    cuerpo: ReglaCambio;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/reportes/balance-general": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/reportes/estado-resultados": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/reportes/excel": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/reportes/polizas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/clientes/{clave}/saldos-iniciales": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/contabilidad/clientes/{clave}/saldos-iniciales": {
    cuerpo: SaldosEntrada;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/contabilidad/codigo-agrupador": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
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
  "POST /api/v1/impuestos/clientes/{clave}/anual": {
    cuerpo: AnualRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/impuestos/clientes/{clave}/anual/papeles": {
    cuerpo: AnualRequest;
    respuesta: unknown;
  };
  "GET /api/v1/impuestos/clientes/{clave}/config": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/impuestos/clientes/{clave}/config": {
    cuerpo: ConfigImpuestosSchema;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/impuestos/clientes/{clave}/isn": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/impuestos/clientes/{clave}/iva": {
    cuerpo: IvaPeriodoRequest;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/impuestos/clientes/{clave}/pm/datos/{anio}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/impuestos/clientes/{clave}/pm/datos/{anio}": {
    cuerpo: DatosAnualesPMSchema;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/impuestos/clientes/{clave}/pm/pagos-provisionales": {
    cuerpo: PagosProvisionalesPMRequest;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/impuestos/clientes/{clave}/resumen": {
    cuerpo: ResumenRequest;
    respuesta: unknown;
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
  "GET /api/v1/nomina/clientes/{clave}/cedulas": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/nomina/clientes/{clave}/cedulas": {
    cuerpo: Body_importar_api_v1_nomina_clientes__clave__cedulas_post;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/cedulas/plantilla": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/nomina/clientes/{clave}/cedulas/{cedula_id}": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/cedulas/{cedula_id}/reporte": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/nomina/clientes/{clave}/cuotas-imss": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/nomina/clientes/{clave}/empleados/{empleado_no}/historial-sbc": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/nomina/clientes/{clave}/empleados/{empleado_no}/sbc": {
    cuerpo: CambioSBC;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/movimientos-imss": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/nomina/clientes/{clave}/movimientos-imss/archivo": {
    cuerpo: GenerarArchivo;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/nomina/clientes/{clave}/movimientos-imss/bimestre-variable": {
    cuerpo: BimestreVariable;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/movimientos-imss/lotes": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/movimientos-imss/lotes/{lote_id}/archivo": {
    cuerpo: never;
    respuesta: unknown;
  };
  "POST /api/v1/nomina/clientes/{clave}/movimientos-imss/marcar": {
    cuerpo: MarcarMovimientos;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi.zip": {
    cuerpo: never;
    respuesta: unknown;
  };
  "POST /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/cancelar": {
    cuerpo: CancelarCfdi;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/pdf": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/cfdi/{cfdi_id}/xml": {
    cuerpo: never;
    respuesta: unknown;
  };
  "POST /api/v1/nomina/clientes/{clave}/periodos/{periodo_id}/timbrar": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/aguinaldo": {
    cuerpo: app__schemas__nomina_p4__AguinaldoRequest;
    respuesta: CalculoResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/ajuste-anual": {
    cuerpo: AjusteAnualRequest;
    respuesta: CalculoResponse;
  };
  "GET /api/v1/nomina/clientes/{cliente_id}/comparar": {
    cuerpo: never;
    respuesta: ComparacionResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/finiquito": {
    cuerpo: app__schemas__nomina_p4__FiniquitoRequest;
    respuesta: CalculoResponse;
  };
  "GET /api/v1/nomina/clientes/{cliente_id}/historial": {
    cuerpo: never;
    respuesta: HistorialResponse;
  };
  "GET /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}": {
    cuerpo: never;
    respuesta: PeriodoGuardadoResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/cerrar": {
    cuerpo: never;
    respuesta: PeriodoGuardadoResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/dispersion": {
    cuerpo: DispersionRequest;
    respuesta: DispersionResponse;
  };
  "GET /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios": {
    cuerpo: never;
    respuesta: EstadoEnviosResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios": {
    cuerpo: EnviarRequest;
    respuesta: EstadoEnviosResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios/{envio_id}/reenviar": {
    cuerpo: never;
    respuesta: EstadoEnviosResponse;
  };
  "POST /api/v1/nomina/clientes/{cliente_id}/ptu": {
    cuerpo: PTURequest;
    respuesta: CalculoResponse;
  };
  "GET /api/v1/nomina/criterios": {
    cuerpo: never;
    respuesta: CriteriosResponse;
  };
  "GET /api/v1/nomina/demo/plantilla": {
    cuerpo: never;
    respuesta: PlantillaDemoResponse;
  };
  "GET /api/v1/nomina/dispersion/layouts": {
    cuerpo: never;
    respuesta: LayoutsResponse;
  };
  "GET /api/v1/nomina/periodo-sugerido": {
    cuerpo: never;
    respuesta: PeriodoSugeridoResponse;
  };
  "POST /api/v1/nomina/recibos/envios/rebote": {
    cuerpo: ReboteRequest;
    respuesta: EnvioSchema;
  };
  "GET /api/v1/nomina/recibos/plantillas": {
    cuerpo: never;
    respuesta: PlantillasResponse;
  };
  "PUT /api/v1/nomina/recibos/plantillas/{canal}": {
    cuerpo: app__routes__nomina_envio__PlantillaEntrada;
    respuesta: PlantillaSchema;
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
  "GET /api/v1/recibos/descarga/{envio_id}/{archivo}": {
    cuerpo: never;
    respuesta: unknown;
  };
  "POST /api/v1/retenciones-terceros": {
    cuerpo: RetencionesRequest;
    respuesta: RetencionesResponse;
  };
  "GET /api/v1/sat/cartera/semaforo": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/alertas/{alerta_id}/atender": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/bitacora": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/config": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/sat/clientes/{clave}/config": {
    cuerpo: app__routes__sat_descarga__ConfigEntrada;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/constancia": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/descargar": {
    cuerpo: RangoEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/historica": {
    cuerpo: HistoricaEntrada;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/opinion": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "PUT /api/v1/sat/clientes/{clave}/opinion/config": {
    cuerpo: app__routes__sat_verificacion__ConfigEntrada;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/opinion/obtener": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/opinion/pdf": {
    cuerpo: Body_subir_pdf_api_v1_sat_clientes__clave__opinion_pdf_post;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/opinion/{doc_id}/pdf": {
    cuerpo: never;
    respuesta: unknown;
  };
  "GET /api/v1/sat/clientes/{clave}/riesgos-69b": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/clientes/{clave}/solicitudes": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
  };
  "POST /api/v1/sat/clientes/{clave}/verificar-estatus": {
    cuerpo: RangoEstatus;
    respuesta: Record<string, unknown>;
  };
  "GET /api/v1/sat/listas/estado": {
    cuerpo: never;
    respuesta: Record<string, unknown>;
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
