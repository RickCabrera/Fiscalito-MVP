/**
 * Reportes contables (P2-05) y periodos (P2-08) con `fetch` stubbeado: qué se le
 * pide al backend y qué se pinta con su respuesta. Ningún importe se calcula
 * aquí: el cuadre y los totales los dice el backend.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { rangoDePeriodo } from './comun';
import { importePdf } from '../../services/pdfExportContabilidad';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const { default: ReportesContables } = await import('./ReportesContables');
const { default: PeriodosContables } = await import('./PeriodosContables');

const ER = {
  exito: true, reporte: 'estado_resultados', titulo: 'Estado de resultados',
  cliente: { clave: 'taller', nombre: 'Taller', rfc: 'XAXX010101000' }, desde: '2026-03-01', hasta: '2026-03-31',
  moneda: 'MXN', tipo_cambio: null, idioma: 'es', comparativo: null,
  columnas: [{ clave: 'importe', etiqueta: 'Periodo' }, { clave: 'acumulado', etiqueta: 'Acumulado del ejercicio' }],
  lineas: [
    { tipo: 'encabezado', clave: 'ingresos', etiqueta: 'Ingresos', nivel: 0 },
    { tipo: 'cuenta', clave: 'c:1', etiqueta: 'Ventas', numero: '401.01', nivel: 2, cuenta_id: 1, valores: { importe: '1000.00', acumulado: '1000.00' } },
    { tipo: 'total', clave: 'utilidad_neta', etiqueta: 'Utilidad neta del ejercicio', nivel: 0, valores: { importe: '1000.00', acumulado: '1000.00' } },
  ],
  resumen: { utilidad_neta: '1000.00' },
};
const BG = { ...ER, reporte: 'balance_general', titulo: 'Balance general', cuadra: false, diferencia: '5.00', columnas: [{ clave: 'importe', etiqueta: 'Saldo' }] };

const MESES = Array.from({ length: 12 }, (_, i) => ({
  mes: i + 1, estado: i === 1 ? 'cerrado' : 'abierto', cerrado_en: i === 1 ? '2026-03-02T10:00:00' : null,
  cerrado_por: null, polizas: i === 2 ? 4 : 0,
}));
const VALIDACION = {
  exito: true, desde: '2026-03-01', hasta: '2026-03-31', balanza_cuadra: true,
  diferencias: { saldo_inicial: '0.00', movimientos: '0.00', saldo_final: '0.00' },
  cfdi_sin_poliza: [{ uuid: 'UUID-SIN-POLIZA', fecha: '2026-03-10', tipo: 'I', direccion: 'emitido', rfc: 'COM010101AAA', total: '1160.00', moneda: 'MXN' }],
  total_cfdi_sin_poliza: 1, se_puede_cerrar: false,
};

let peticiones: { url: string; method: string; body: string }[] = [];

beforeEach(() => {
  cleanup();
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: String(init.body ?? '') });
    const ruta = new URL(url).pathname;
    if (ruta.endsWith('/reportes/estado-resultados')) return Response.json(ER);
    if (ruta.endsWith('/reportes/balance-general')) return Response.json(BG);
    if (ruta.endsWith('/reportes/excel')) return new Response(new Blob(['xlsx']), { status: 200 });
    if (ruta.endsWith('/cuentas')) return Response.json({ exito: true, cuentas: [] });
    if (ruta.endsWith('/validacion')) return Response.json(VALIDACION);
    if (ruta.endsWith('/cerrar') || ruta.endsWith('/reabrir')) return Response.json({ exito: true });
    if (/\/periodos\/\d+$/.test(ruta)) {
      return Response.json({ exito: true, anio: 2026, meses: MESES, cierre_anual: { hecho: false, polizas: [] },
        historial: [{ mes: 2, accion: 'cerrar', motivo: '', uid: 'u', fecha: '2026-03-02T10:00:00' }] });
    }
    return Response.json({ exito: true });
  }));
});

describe('utilidades', () => {
  it('periodos e importes', () => {
    expect(rangoDePeriodo(2026, 2)).toEqual({ desde: '2026-02-01', hasta: '2026-02-28' });
    expect(rangoDePeriodo(2026, 0)).toEqual({ desde: '2026-01-01', hasta: '2026-12-31' });
    expect(importePdf('1234.5')).toBe('1,234.50');
    expect(importePdf('0.00')).toBe('—');
  });
});

describe('P2-05 · Reportes', () => {
  it('genera el estado de resultados con los filtros y lo pinta como lo manda el backend', async () => {
    render(<ReportesContables clave="taller" nombre="Taller" rfc="XAXX010101000" onVerBalanza={() => undefined} />);
    fireEvent.change(screen.getByLabelText('Periodo'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar reporte/ }));
    const tabla = await screen.findByRole('region', { name: 'Estado de resultados' });
    expect(within(tabla).getByText('Utilidad neta del ejercicio')).toBeTruthy();
    expect(within(tabla).getByText('401.01')).toBeTruthy();
    const pedido = peticiones.find((p) => p.url.includes('/reportes/estado-resultados'))!;
    expect(pedido.url).toContain('desde=');
    expect(pedido.url).toContain('-03-01');
    expect(pedido.url).toContain('agrupar=cuenta');
    expect(pedido.url).not.toContain('tipo_cambio');
  });

  it('otra moneda exige tipo de cambio y lo manda; el balance enseña el descuadre del backend', async () => {
    render(<ReportesContables clave="taller" nombre="Taller" rfc="X" onVerBalanza={() => undefined} />);
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'balance_general' } });
    fireEvent.change(screen.getByDisplayValue('MXN'), { target: { value: 'USD' } });
    const generar = screen.getByRole('button', { name: /Generar reporte/ }) as HTMLButtonElement;
    expect(generar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Tipo de cambio'), { target: { value: '18.5' } });
    expect(generar.disabled).toBe(false);
    fireEvent.click(generar);
    expect(await screen.findByText(/No cuadra: diferencia 5.00/)).toBeTruthy();
    const pedido = peticiones.find((p) => p.url.includes('/reportes/balance-general'))!;
    expect(pedido.url).toContain('moneda=USD');
    expect(pedido.url).toContain('tipo_cambio=18.5');
  });

  it('descarga el Excel del backend', async () => {
    render(<ReportesContables clave="taller" nombre="Taller" rfc="X" onVerBalanza={() => undefined} />);
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
    fireEvent.click(screen.getByRole('button', { name: /Excel/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.includes('/reportes/excel?reporte=estado_resultados'))).toBe(true));
  });
});

describe('P2-08 · Periodos', () => {
  it('pinta el estado por mes y no cierra con CFDI sin póliza salvo con motivo', async () => {
    render(<PeriodosContables clave="taller" />);
    expect(await screen.findByRole('button', { name: 'Reabrir Febrero' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar Marzo' }));
    const aviso = await screen.findByRole('region', { name: /Validación de Marzo/ });
    expect(within(aviso).getByText('UUID-SIN-POLIZA')).toBeTruthy();
    expect(peticiones.some((p) => p.url.endsWith('/cerrar'))).toBe(false);
    const forzar = within(aviso).getByRole('button', { name: 'Cerrar de todos modos' }) as HTMLButtonElement;
    expect(forzar.disabled).toBe(true);
    fireEvent.change(within(aviso).getByLabelText('Motivo para cerrar sin pólizas'), { target: { value: 'Se registra en abril' } });
    fireEvent.click(forzar);
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/periodos/2026/3/cerrar'))).toBe(true));
    const cierre = peticiones.find((p) => p.url.endsWith('/cerrar'))!;
    expect(JSON.parse(cierre.body)).toEqual({ forzar: true, motivo: 'Se registra en abril' });
  });

  it('reabrir pide motivo', async () => {
    render(<PeriodosContables clave="taller" />);
    const reabrir = await screen.findByRole('button', { name: 'Reabrir Febrero' });
    vi.spyOn(window, 'prompt').mockReturnValueOnce(null).mockReturnValueOnce('Falta una factura');
    fireEvent.click(reabrir);
    expect(peticiones.some((p) => p.url.endsWith('/reabrir'))).toBe(false);
    fireEvent.click(reabrir);
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/periodos/2026/2/reabrir'))).toBe(true));
    expect(JSON.parse(peticiones.find((p) => p.url.endsWith('/reabrir'))!.body)).toEqual({ motivo: 'Falta una factura' });
  });
});
