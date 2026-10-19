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
  origen: 'automatica' | 'manual';
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
