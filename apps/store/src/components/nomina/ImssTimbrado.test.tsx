/**
 * P4-09 y P4-11 en pantalla: Movimientos IMSS (pendientes, generar archivo por tipo, marcar
 * enviado / acuse) y Timbrado del periodo (timbrar, estado por recibo, descarga, cancelar).
 * Red cerrada: se stubbea `fetch` y se mide lo que se pide y lo que se pinta.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

const { default: MovimientosImss } = await import('../cartera/MovimientosImss');
const { default: TimbradoPeriodo } = await import('./TimbradoPeriodo');

type Llamada = { url: string; init?: RequestInit };

function servidor(respuestas: Array<{ status?: number; json?: unknown; texto?: string }>) {
  const llamadas: Llamada[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    llamadas.push({ url, init });
    const r = respuestas.shift() ?? { json: { exito: true } };
    if (r.texto !== undefined) return new Response(r.texto, { status: 200 });
    return new Response(JSON.stringify(r.json), {
      status: r.status ?? 200, headers: { 'Content-Type': 'application/json' },
    });
  }));
  return llamadas;
}

const MOV = {
  id: 3, empleado_no: 'E1', nombre: 'JOSE', tipo: '02', fecha: '2026-07-15', sbc: null,
  tipo_salario: '0', causa_baja: '2', estado: 'pendiente', lote_id: null, acuse: '', origen: 'baja',
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('MovimientosImss', () => {
  it('pinta los pendientes y genera el archivo IDSE de bajas', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
    const llamadas = servidor([
      { json: { movimientos: [MOV], pendientes: 1 } },
      { json: { lote: { id: 9, tipo: 'idse_02', nombre_archivo: 'IDSE_02.txt', registros: 2 },
        no_exportables: [], transliterados: [] } },
      { texto: 'X'.repeat(168) },
      { json: { movimientos: [{ ...MOV, estado: 'generado' }], pendientes: 0 } },
    ]);
    render(<MovimientosImss clienteId="taller" />);
    expect(await screen.findByText(/1 pendiente\(s\) por enviar/)).toBeTruthy();
    expect(screen.getByText('Causa 2')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /IDSE bajas \(02\)/ }));
    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/IDSE_02.txt: 2 registro/));
    expect(llamadas[1].url).toMatch(/\/nomina\/clientes\/taller\/movimientos-imss\/archivo$/);
    expect(JSON.parse(llamadas[1].init?.body as string)).toEqual({ destino: 'idse_02' });
    expect(llamadas[2].url).toMatch(/\/movimientos-imss\/lotes\/9\/archivo$/);
  });

  it('marca enviados y captura el acuse', async () => {
    const llamadas = servidor([
      { json: { movimientos: [MOV], pendientes: 1 } },
      { json: { movimientos: [{ ...MOV, estado: 'acuse' }] } },
      { json: { movimientos: [{ ...MOV, estado: 'acuse', acuse: 'L-1' }], pendientes: 0 } },
    ]);
    render(<MovimientosImss clienteId="taller" />);
    fireEvent.click(await screen.findByLabelText('Marcar movimiento 3'));
    fireEvent.change(screen.getByLabelText('Folio del acuse'), { target: { value: 'L-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Capturar acuse' }));
    await waitFor(() => expect(screen.getByText(/Con acuse · L-1/)).toBeTruthy());
    expect(JSON.parse(llamadas[1].init?.body as string)).toEqual({ ids: [3], estado: 'acuse', acuse: 'L-1' });
  });
});

const RECIBO = {
  id: 5, recibo_id: 1, empleado_no: 'E1', nombre: 'JOSE', estado: 'timbrado',
  uuid: 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE', error: '', es_prueba: true, total: '5000.00',
};

describe('TimbradoPeriodo', () => {
  it('timbra, pinta el estado por recibo y avisa que el PAC es de pruebas', async () => {
    const llamadas = servidor([
      { json: { estado_periodo: 'cerrada', por_estado: {}, trabajo: null, recibos: [] } },
      { json: { estado_periodo: 'cerrada', por_estado: { pendiente: 1 }, trabajo: { id: 1, estado: 'pendiente', error: null }, recibos: [] } },
      { json: { estado_periodo: 'timbrada', por_estado: { timbrado: 1 }, trabajo: { id: 1, estado: 'hecho', error: null }, recibos: [RECIBO] } },
    ]);
    render(<TimbradoPeriodo clienteId="taller" periodoId={4} />);
    expect(await screen.findByText(/Aún no se ha pedido el timbrado/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Timbrar/ }));
    expect(await screen.findByText(RECIBO.uuid)).toBeTruthy();
    expect(screen.getByRole('note').textContent).toMatch(/NO tienen validez fiscal/);
    expect(llamadas[1].url).toMatch(/\/nomina\/clientes\/taller\/periodos\/4\/timbrar$/);
    expect(llamadas[1].init?.method).toBe('POST');
  });

  it('cancela con el motivo elegido', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const llamadas = servidor([
      { json: { estado_periodo: 'timbrada', por_estado: { timbrado: 1 }, trabajo: null, recibos: [RECIBO] } },
      { json: { cfdi: { ...RECIBO, estado: 'cancelado' } } },
      { json: { estado_periodo: 'cerrada', por_estado: { cancelado: 1 }, trabajo: null, recibos: [{ ...RECIBO, estado: 'cancelado' }] } },
    ]);
    render(<TimbradoPeriodo clienteId="taller" periodoId={4} />);
    fireEvent.change(await screen.findByLabelText('Motivo de cancelación'), { target: { value: '03' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar E1' }));
    await waitFor(() => expect(screen.getByText('Cancelado')).toBeTruthy());
    expect(llamadas[1].url).toMatch(/\/periodos\/4\/cfdi\/5\/cancelar$/);
    expect(JSON.parse(llamadas[1].init?.body as string)).toEqual({ motivo: '03', folio_sustitucion: null });
  });

  it('muestra el error del servidor', async () => {
    servidor([{ status: 404, json: { exito: false, error: 'No existe el periodo 4 de este cliente.' } }]);
    render(<TimbradoPeriodo clienteId="otro" periodoId={4} />);
    expect(await screen.findByText(/No existe el periodo 4/)).toBeTruthy();
  });
});
