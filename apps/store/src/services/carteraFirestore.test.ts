/**
 * La cartera nunca deja la pantalla vacía (G-03).
 *
 * LO QUE ESTOS TESTS CUIDAN
 * -------------------------
 * Regla de Ricardo: la demo funciona en TODO momento. El modo de falla
 * peligroso NO es que Firestore truene —eso se atrapa— sino que **devuelva
 * vacío**: con unas reglas que permitan leer y nieguen escribir, la siembra
 * nunca se escribe, la lectura no lanza, y queda una app que se ve bien y no
 * tiene clientes. Cada test de abajo es uno de esos caminos.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

const getDocs = vi.fn();
const setDoc = vi.fn();
const deleteDoc = vi.fn();
const commit = vi.fn();
const loteSet = vi.fn();
const loteDelete = vi.fn();

vi.mock('firebase/firestore', () => ({
  collection: (...args: unknown[]) => ({ path: args.slice(1).join('/') }),
  doc: (...args: unknown[]) => ({ path: args.slice(1).join('/') }),
  getDocs: (...args: unknown[]) => getDocs(...args),
  setDoc: (...args: unknown[]) => setDoc(...args),
  deleteDoc: (...args: unknown[]) => deleteDoc(...args),
  writeBatch: () => ({ set: loteSet, delete: loteDelete, commit }),
}));

vi.mock('./firebase', () => ({ db: {} }));

const obtenerClientes = vi.fn();
const obtenerCliente = vi.fn();
vi.mock('./despachoApi', () => ({
  obtenerClientes: () => obtenerClientes(),
  obtenerCliente: (id: string) => obtenerCliente(id),
}));

const obtenerEmpleadosSemilla = vi.fn();
vi.mock('./carteraApi', () => ({
  obtenerEmpleadosSemilla: (id: string) => obtenerEmpleadosSemilla(id),
}));

import { cargarCartera, sembrarDemo } from './carteraFirestore';

const RESUMEN = {
  id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'fixtures-s04',
  num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null,
  clave_periodicidad: '04', zona: 'general',
};

const EMPLEADO = {
  empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: '', salario_diario: '316.00',
  salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
  tipo_contrato: 'indeterminado' as const,
  prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
  nss: '', employee_no: 'E-01', enrolamiento: 'enrolado' as const,
};

function backendResponde() {
  obtenerClientes.mockResolvedValue([RESUMEN]);
  obtenerCliente.mockResolvedValue({
    ...RESUMEN,
    empleados: [],
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
    fecha_referencia: '2026-09-01',
  });
  obtenerEmpleadosSemilla.mockResolvedValue({
    cliente_id: 'demo', origen: 'fixtures-s04', total: 1, sin_vincular: 0,
    empleados: [EMPLEADO],
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  backendResponde();
});

describe('cargarCartera', () => {
  it('sin sesión cae al catálogo del backend y lo dice', async () => {
    const r = await cargarCartera(null);
    expect(r.origen).toBe('backend');
    expect(r.clientes).toHaveLength(1);
    expect(r.motivoFallback).toContain('demostración');
  });

  it('con datos en Firestore usa los del usuario', async () => {
    getDocs
      .mockResolvedValueOnce({ docs: [{ id: 'mio', data: () => ({ nombre: 'Mi Cliente' }) }] })
      .mockResolvedValueOnce({ docs: [{ data: () => EMPLEADO }] });

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('firestore');
    expect(r.clientes[0].id).toBe('mio');
    expect(r.clientes[0].empleados).toHaveLength(1);
    expect(r.motivoFallback).toBeNull();
    // No se pidió el catálogo: la cartera del usuario ganó.
    expect(obtenerClientes).not.toHaveBeenCalled();
  });

  it('UNA CARTERA VACÍA se trata igual que un error', async () => {
    // El caso peligroso. Unas reglas que permitan leer y nieguen escribir dejan
    // la cartera vacía SIN lanzar nada: si esto no cayera al backend, quedaría
    // una app que se ve bien y no tiene clientes, que es peor que un error.
    getDocs.mockResolvedValue({ docs: [] });

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('backend');
    expect(r.clientes).toHaveLength(1);
    expect(r.motivoFallback).toContain('vacía');
  });

  it('si Firestore lanza, cae al backend y explica por qué', async () => {
    getDocs.mockRejectedValue(new Error('Missing or insufficient permissions.'));

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('backend');
    expect(r.motivoFallback).toContain('insufficient permissions');
  });

  it('si Firestore se cuelga, el timeout la rescata', async () => {
    // Ningún `await` sin cota en el camino de la demo: una promesa que nunca
    // resuelve dejaría la pantalla en "Cargando" para siempre.
    vi.useFakeTimers();
    getDocs.mockReturnValue(new Promise(() => {}));

    const promesa = cargarCartera('uid-1');
    await vi.advanceTimersByTimeAsync(3000);
    const r = await promesa;

    expect(r.origen).toBe('backend');
    expect(r.motivoFallback).toContain('tardó');
    vi.useRealTimers();
  });

  it('nunca lanza, pase lo que pase en Firestore', async () => {
    getDocs.mockRejectedValue(new Error('lo que sea'));
    await expect(cargarCartera('uid-1')).resolves.toBeDefined();
  });
});

describe('sembrarDemo', () => {
  it('no hace nada si el usuario ya tiene cartera', async () => {
    // Idempotente: sembrar dos veces no duplica ni pisa lo que el contador editó.
    getDocs.mockResolvedValue({ empty: false, docs: [] });

    expect(await sembrarDemo('uid-1')).toBe(false);
    expect(commit).not.toHaveBeenCalled();
  });

  it('escribe los clientes y sus empleados en un solo lote', async () => {
    getDocs.mockResolvedValue({ empty: true, docs: [] });

    expect(await sembrarDemo('uid-1')).toBe(true);
    expect(commit).toHaveBeenCalledTimes(1);
    // Un documento de cliente + un documento de empleado.
    expect(loteSet).toHaveBeenCalledTimes(2);
  });

  it('el cliente que escribe NO lleva el arreglo de empleados dentro', async () => {
    // Los empleados son una subcolección. Guardarlos también embebidos daría
    // dos verdades sobre la plantilla, y la de adentro nunca se actualizaría.
    getDocs.mockResolvedValue({ empty: true, docs: [] });
    await sembrarDemo('uid-1');

    const datosDelCliente = loteSet.mock.calls[0][1];
    expect(datosDelCliente).not.toHaveProperty('empleados');
    expect(datosDelCliente.nombre).toBe('Cliente Demo');
  });
});
