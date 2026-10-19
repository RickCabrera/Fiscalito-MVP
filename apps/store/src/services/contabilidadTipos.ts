/**
 * Tipos del contrato de contabilidad (P2-01 a P2-04). Espejo de las respuestas
 * de `/api/v1/contabilidad/...` (`docs/api-contract.md` §Contabilidad). Los
 * importes viajan como texto con dos decimales.
 */

import type { Trabajo } from './trabajosApi';

export type Naturaleza = 'deudora' | 'acreedora';
export type TipoCuenta = 'activo' | 'pasivo' | 'capital' | 'ingreso' | 'costo' | 'gasto' | 'orden';
export type TipoPoliza = 'ingreso' | 'egreso' | 'diario';

export interface Cuenta {
  id: number;
  numero: string;
  nombre: string;
  nivel: number;
  naturaleza: Naturaleza;
  tipo: TipoCuenta;
  padre_id: number | null;
  codigo_agrupador: string;
  afectable: boolean;
}

export interface CodigoAgrupador {
  codigo: string;
  nivel: number;
  nombre: string;
  naturaleza: Naturaleza;
  tipo: TipoCuenta;
  nota: string;
}

export interface NuevaCuenta {
  numero: string;
  nombre: string;
  codigo_agrupador: string;
  padre_id?: number | null;
}

export interface Regla {
  id: number;
  prioridad: number;
  criterio: 'rfc' | 'clave' | 'prefijo' | 'uso' | 'descripcion';
  valor: string;
  cuenta_numero: string;
  activa: boolean;
}

export interface ConfigContable {
  automatica_ingresos: boolean;
  automatica_egresos: boolean;
  automatica_pagos: boolean;
  automatica_nomina: boolean;
  pue_registra_cobro: boolean;
  uso_s01_no_deducible: boolean;
  efectivo_no_deducible: boolean;
  /** Retenciones de PPD en cuentas pendientes hasta el pago (default true, revisión P2). */
  retenciones_al_pago: boolean;
  tope_activo: string;
  plantilla_concepto: string;
  fecha_saldos_iniciales: string | null;
  cuentas: Record<string, string>;
  cuentas_personalizadas: Record<string, string>;
  roles: { rol: string; default: string; descripcion: string }[];
  formas_pago: Record<string, string>;
  reglas: Regla[];
}

export interface MovimientoPoliza {
  id?: number;
  cuenta_id: number;
  cuenta?: string;
  nombre_cuenta?: string;
  concepto: string;
  cargo: string;
  abono: string;
  uuid: string;
  rfc: string;
}

export interface Poliza {
  id: number;
  folio: string;
  tipo: TipoPoliza;
  numero: number;
  fecha: string;
  concepto: string;
  origen: 'automatica' | 'manual' | 'cierre' | 'apertura';
  estado: 'activa' | 'cancelada';
  uuid_cfdi: string | null;
  tipo_cfdi: string;
  total_cargos: string;
  total_abonos: string;
  diferencia: string;
  advertencias: string[];
  editada: boolean;
  reversa_de_id: number | null;
  motivo_cancelacion: string;
  cancelada_en: string | null;
  movimientos?: MovimientoPoliza[];
}

export interface ResultadoGeneracion {
  generadas: number;
  ya_existian: number;
  omitidas: number;
  canceladas: number;
  revertidas: number;
  errores: { uuid: string; error: string }[];
}

export interface RespuestaGenerar {
  exito: boolean;
  en_segundo_plano: boolean;
  resultado?: ResultadoGeneracion;
  trabajo?: Pick<Trabajo, 'id' | 'tipo' | 'estado'>;
}

export interface FiltrosPolizas {
  desde?: string;
  hasta?: string;
  tipo?: TipoPoliza | '';
  origen?: 'automatica' | 'manual' | '';
  estado?: 'activa' | 'cancelada' | '';
  uuid?: string;
  texto?: string;
  pagina?: number;
  por_pagina?: number;
}

export interface RenglonBalanza {
  cuenta_id: number;
  numero: string;
  nombre: string;
  nivel: number;
  naturaleza: Naturaleza;
  afectable: boolean;
  codigo_agrupador: string;
  saldo_inicial: string;
  saldo_final: string;
  inicial_deudor: string;
  inicial_acreedor: string;
  cargos: string;
  abonos: string;
  final_deudor: string;
  final_acreedor: string;
}

export interface Balanza {
  desde: string;
  hasta: string;
  renglones: RenglonBalanza[];
  totales: Record<'inicial_deudor' | 'inicial_acreedor' | 'cargos' | 'abonos' | 'final_deudor' | 'final_acreedor', string>;
  cuadra: boolean;
  diferencias: { saldo_inicial: string; movimientos: string; saldo_final: string };
}

export interface MovimientoAuxiliar {
  poliza_id: number;
  folio: string;
  fecha: string;
  tipo_poliza: TipoPoliza;
  concepto: string;
  cuenta: string;
  cargo: string;
  abono: string;
  saldo: string;
  uuid: string;
  rfc: string;
  xml_disponible: boolean;
}

export interface Auxiliar {
  cuenta: Cuenta;
  saldo_inicial: string;
  cargos: string;
  abonos: string;
  saldo_final: string;
  movimientos: MovimientoAuxiliar[];
  truncado: boolean;
}

export type FiltroBalanza = 'con_movimiento' | 'con_saldo_o_movimiento' | 'todas';

export interface NuevaPoliza {
  tipo: TipoPoliza;
  fecha: string;
  concepto: string;
  movimientos: Pick<MovimientoPoliza, 'cuenta_id' | 'cargo' | 'abono' | 'concepto' | 'uuid' | 'rfc'>[];
}

// ── P2-05: reportes contables ──

export type TipoReporte = 'estado_resultados' | 'balance_general' | 'balanza' | 'auxiliar' | 'polizas';
export type Comparativo = 'ninguno' | 'periodo_anterior' | 'anio_anterior';

export interface FiltrosReporte {
  desde: string;
  hasta: string;
  nivel?: number | null;
  solo?: FiltroBalanza;
  agrupar?: 'cuenta' | 'agrupador';
  moneda?: string;
  tipo_cambio?: string | null;
  idioma?: 'es' | 'en';
  comparar?: Comparativo;
  incluir_cierre?: boolean;
}

export interface LineaReporte {
  tipo: 'encabezado' | 'cuenta' | 'subtotal' | 'total';
  clave: string;
  etiqueta: string;
  nivel: number;
  numero?: string;
  cuenta_id?: number | null;
  valores?: Record<string, string>;
}

export interface EstadoFinanciero {
  reporte: 'estado_resultados' | 'balance_general';
  titulo: string;
  cliente: { clave: string; nombre: string; rfc: string };
  desde: string;
  hasta: string;
  moneda: string;
  tipo_cambio: string | null;
  idioma: 'es' | 'en';
  comparativo: { tipo: Comparativo; desde: string; hasta: string } | null;
  columnas: { clave: string; etiqueta: string }[];
  lineas: LineaReporte[];
  resumen: Record<string, string>;
  cuadra?: boolean;
  diferencia?: string;
}

// ── P2-08: periodos y cierre ──

export interface CfdiSinPoliza {
  uuid: string;
  fecha: string;
  tipo: string;
  direccion: string;
  rfc: string;
  total: string;
  moneda: string;
}

export interface ValidacionCierre {
  desde: string;
  hasta: string;
  balanza_cuadra: boolean;
  diferencias: { saldo_inicial: string; movimientos: string; saldo_final: string };
  cfdi_sin_poliza: CfdiSinPoliza[];
  total_cfdi_sin_poliza: number;
  se_puede_cerrar: boolean;
}

export interface MesContable {
  mes: number;
  estado: 'abierto' | 'cerrado';
  cerrado_en: string | null;
  cerrado_por: string | null;
  polizas: number;
}

export interface EjercicioContable {
  anio: number;
  meses: MesContable[];
  historial: { mes: number; accion: string; motivo: string; uid: string; fecha: string }[];
  cierre_anual: { hecho: boolean; polizas: Poliza[] };
}
