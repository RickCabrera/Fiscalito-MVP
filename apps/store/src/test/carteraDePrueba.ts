/**
 * Contexto de cartera por default para los tests de pantalla (G-03).
 *
 * POR QUÉ EXISTE Y POR QUÉ VIENE VACÍO
 * ------------------------------------
 * `CarteraProvider` habla con Firestore, y las pantallas que ya existían
 * (E-02…E-07) no saben nada de eso. Sin este doble tendrían que montar el
 * proveedor real, o sea abrir la red en tests que la tienen cerrada por default.
 *
 * Viene **vacío a propósito**: con la cartera sin ese cliente,
 * `useNominaCliente` cae a los empleados de la ficha del backend, que es
 * exactamente el camino que esas pantallas probaban antes de G-01. Así el doble
 * no las cambia de significado — siguen midiendo lo mismo.
 *
 * Un test que quiera ejercitar la cartera pasa su propio `override`.
 */

import { vi } from 'vitest';
import type { CarteraContextType } from '../context/carteraStore';
import { EMPRESA_POR_DEFECTO } from '../services/empresa';

export function carteraDePrueba(
  override: Partial<CarteraContextType> = {},
): CarteraContextType {
  return {
    clientes: [],
    loading: false,
    // R-06: el default del doble sigue siendo el catálogo de sólo lectura para
    // no cambiar de significado los tests de pantalla que ya existían. Un test
    // que quiera la cartera del usuario pasa `origen: 'firestore'`.
    origen: 'backend',
    soloLectura: true,
    error: null,
    clientePorId: () => null,
    guardarCliente: vi.fn().mockResolvedValue(undefined),
    borrarCliente: vi.fn().mockResolvedValue(undefined),
    guardarEmpleado: vi.fn().mockResolvedValue(undefined),
    borrarEmpleado: vi.fn().mockResolvedValue(undefined),
    sembrar: vi.fn().mockResolvedValue(undefined),
    recargar: vi.fn(),
    // O-01: el doble arranca con la empresa SIN configurar, que es lo que ve
    // una cuenta nueva. Un test que necesite una empresa configurada la pasa en
    // el `override` — igual que con los clientes.
    empresa: EMPRESA_POR_DEFECTO,
    guardarEmpresa: vi.fn().mockResolvedValue(undefined),
    ...override,
  };
}
