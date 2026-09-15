/**
 * Balanza de comprobación a partir de las pólizas — T7, CASCARÓN.
 *
 * Suma cargos y abonos por cuenta y saca el saldo. No hay saldos iniciales: la
 * balanza arranca en ceros y sólo refleja los CFDI que se cargaron en esta
 * sesión, así que **no es la balanza del ejercicio**, es la del lote.
 *
 * EL CUADRE NO ES UNA PROMESA, ES UNA COMPROBACIÓN. `cuadra` se calcula
 * comparando las dos sumas y se pinta en pantalla. Las pólizas de `polizas.ts`
 * cuadran por construcción, así que un `false` aquí significa que algo se rompió
 * corriente arriba — que es exactamente lo que una balanza sirve para detectar,
 * y por eso se enseña en vez de asumirse.
 */

import { cuentaPorCodigo, nombreDeCuenta, type NaturalezaCuenta, type RubroCuenta } from './catalogoSAT';
import type { Poliza } from './polizas';

export interface RenglonBalanza {
  cuenta: string;
  nombre: string;
  rubro: RubroCuenta | null;
  naturaleza: NaturalezaCuenta | null;
  cargos: number;
  abonos: number;
  /** Saldo deudor (cargos > abonos). Cero si el saldo es acreedor. */
  saldoDeudor: number;
  /** Saldo acreedor (abonos > cargos). Cero si el saldo es deudor. */
  saldoAcreedor: number;
}

export interface Balanza {
  renglones: RenglonBalanza[];
  totalCargos: number;
  totalAbonos: number;
  totalSaldoDeudor: number;
  totalSaldoAcreedor: number;
  /** `true` si Σ cargos = Σ abonos dentro de medio centavo. */
  cuadra: boolean;
  /** Σ cargos − Σ abonos. Se enseña cuando no cuadra. */
  diferencia: number;
}

/** Tolerancia del cuadre: medio centavo, para no reprobar por ruido binario. */
const TOLERANCIA = 0.005;

function redondea(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

export function generarBalanza(polizas: Poliza[]): Balanza {
  const acumulado = new Map<string, { cargos: number; abonos: number }>();

  for (const poliza of polizas) {
    for (const m of poliza.movimientos) {
      const actual = acumulado.get(m.cuenta) ?? { cargos: 0, abonos: 0 };
      actual.cargos += m.cargo;
      actual.abonos += m.abono;
      acumulado.set(m.cuenta, actual);
    }
  }

  const renglones: RenglonBalanza[] = [...acumulado.entries()]
    // Por código: es el orden del código agrupador, activo antes que pasivo.
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([codigo, { cargos, abonos }]) => {
      const cuenta = cuentaPorCodigo(codigo);
      const saldo = redondea(cargos - abonos);
      return {
        cuenta: codigo,
        nombre: nombreDeCuenta(codigo),
        rubro: cuenta?.rubro ?? null,
        naturaleza: cuenta?.naturaleza ?? null,
        cargos: redondea(cargos),
        abonos: redondea(abonos),
        saldoDeudor: saldo > 0 ? saldo : 0,
        saldoAcreedor: saldo < 0 ? -saldo : 0,
      };
    });

  const totalCargos = redondea(renglones.reduce((s, r) => s + r.cargos, 0));
  const totalAbonos = redondea(renglones.reduce((s, r) => s + r.abonos, 0));

  return {
    renglones,
    totalCargos,
    totalAbonos,
    totalSaldoDeudor: redondea(renglones.reduce((s, r) => s + r.saldoDeudor, 0)),
    totalSaldoAcreedor: redondea(renglones.reduce((s, r) => s + r.saldoAcreedor, 0)),
    cuadra: Math.abs(totalCargos - totalAbonos) < TOLERANCIA,
    diferencia: redondea(totalCargos - totalAbonos),
  };
}
