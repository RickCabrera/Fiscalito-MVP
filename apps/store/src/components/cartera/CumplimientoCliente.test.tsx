/**
 * P1-05 / P1-04: "Cumplimiento ante el SAT" de la ficha del cliente.
 *
 * Red cerrada: `fetch` stubbeado responde por URL. Se mide lo que la pantalla pide y pinta:
 * semáforo, "Obtener ahora", subida del PDF, descarga, vía manual y riesgos 69-B en rojo.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { DocumentoCumplimiento, HistorialCumplimiento } from '../../services/satVerificacionApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

const { default: CumplimientoCliente } = await import('./CumplimientoCliente');

function doc(extra: Partial<DocumentoCumplimiento> = {}): DocumentoCumplimiento {
  return {
    id: 4, tipo: 'opinion', fecha: '2026-10-03', resultado: 'positiva', folio: '26NA1',
    origen: 'falso', lectura: 'pdf', tamano: 900, creado_en: null, aviso: null, ...extra,
  };
}

function historial(extra: Partial<HistorialCumplimiento> = {}): HistorialCumplimiento {
  return {
    exito: true, tipo: 'opinion', ultimo: doc(), semaforo: 'verde', historial: [doc()],
    via: 'falso', dias_vigencia: 30,
    config: { automatico: true, dia_del_mes: 1, constancia: true }, ...extra,
  };
}

type Llamada = { url: string; method: string; body?: BodyInit | null };

function servidor(opinion: HistorialCumplimiento, riesgos: unknown = { riesgos: [], listas: [] }) {
  const llamadas: Llamada[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    llamadas.push({ url, method, body: init.body });
    let cuerpo: unknown = { exito: true };
    if (url.endsWith('/opinion') && method === 'GET') cuerpo = opinion;
    else if (url.endsWith('/constancia')) cuerpo = historial({ tipo: 'constancia', ultimo: null, semaforo: 'gris', historial: [], via: opinion.via });
    else if (url.endsWith('/riesgos-69b')) cuerpo = riesgos;
    else if (url.includes('/opinion/obtener')) cuerpo = { exito: true, trabajo: { id: 1, tipo: 'sat.cumplimiento_obtener', estado: 'pendiente' } };
    else if (url.includes('/trabajos')) cuerpo = { trabajos: [] };
    else if (url.endsWith('/opinion/pdf')) cuerpo = { exito: true, documento: doc({ origen: 'manual' }), semaforo: 'verde' };
    else if (url.includes('/pdf')) return new Response('%PDF-1.4', { headers: { 'Content-Type': 'application/pdf' } });
    return new Response(JSON.stringify(cuerpo), { headers: { 'Content-Type': 'application/json' } });
  }));
  return llamadas;
}

afterEach(() => cleanup());

describe('CumplimientoCliente', () => {
  it('pinta el semáforo verde, la última fecha y el historial', async () => {
    const llamadas = servidor(historial());
    render(<CumplimientoCliente clave="taller" />);
    const opinion = await screen.findByLabelText('Opinión de cumplimiento (32-D)');
    await waitFor(() => expect(opinion.querySelector('[data-semaforo="verde"]')).toBeTruthy());
    expect(opinion.textContent).toMatch(/Última: 2026-10-03 · folio 26NA1/);
    expect(screen.getByLabelText('Historial de Opinión de cumplimiento (32-D)').textContent).toMatch(/Positiva/);
    expect(llamadas.some((l) => l.url.endsWith('/api/v1/sat/clientes/taller/opinion'))).toBe(true);
    expect(llamadas.some((l) => l.url.endsWith('/api/v1/sat/clientes/taller/constancia'))).toBe(true);
  });

  it('semáforo rojo con una opinión negativa', async () => {
    servidor(historial({ semaforo: 'rojo', ultimo: doc({ resultado: 'negativa' }), historial: [doc({ resultado: 'negativa' })] }));
    render(<CumplimientoCliente clave="taller" />);
    const opinion = await screen.findByLabelText('Opinión de cumplimiento (32-D)');
    await waitFor(() => expect(opinion.querySelector('[data-semaforo="rojo"]')?.textContent).toMatch(/Negativa/));
  });

  it('"Obtener ahora" encola la opinión y muestra el proceso', async () => {
    const llamadas = servidor(historial());
    render(<CumplimientoCliente clave="taller" />);
    const opinion = await screen.findByLabelText('Opinión de cumplimiento (32-D)');
    await waitFor(() => expect(opinion.querySelector('[data-semaforo]')).toBeTruthy());
    fireEvent.click(opinion.querySelector('button')!);
    await waitFor(() => expect(llamadas.some((l) => l.method === 'POST' && l.url.includes('/opinion/obtener?tipo=opinion'))).toBe(true));
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('/trabajos?cliente=taller&tipo=sat.cumplimiento_obtener'))).toBe(true));
  });

  it('sube el PDF en multipart con el tipo', async () => {
    const llamadas = servidor(historial());
    render(<CumplimientoCliente clave="taller" />);
    const input = await screen.findByLabelText('Subir PDF de Opinión de cumplimiento (32-D)');
    fireEvent.change(input, { target: { files: [new File(['%PDF-1.4'], 'op.pdf', { type: 'application/pdf' })] } });
    await waitFor(() => expect(llamadas.some((l) => l.method === 'POST' && l.url.endsWith('/opinion/pdf'))).toBe(true));
    const subida = llamadas.find((l) => l.url.endsWith('/opinion/pdf'))!;
    expect(subida.body instanceof FormData).toBe(true);
    expect((subida.body as FormData).get('tipo')).toBe('opinion');
  });

  it('descarga el PDF del historial', async () => {
    const llamadas = servidor(historial());
    const crear = vi.fn(() => 'blob:x');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: crear, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    render(<CumplimientoCliente clave="taller" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Descargar PDF del 2026-10-03' }));
    await waitFor(() => expect(crear).toHaveBeenCalled());
    expect(llamadas.some((l) => l.url.endsWith('/sat/clientes/taller/opinion/4/pdf'))).toBe(true);
  });

  it('con la vía manual no ofrece "Obtener ahora"', async () => {
    servidor(historial({ via: 'manual', ultimo: null, semaforo: 'gris', historial: [] }));
    render(<CumplimientoCliente clave="taller" />);
    const opinion = await screen.findByLabelText('Opinión de cumplimiento (32-D)');
    await waitFor(() => expect(opinion.textContent).toMatch(/vía configurada es manual/));
    expect(screen.queryByRole('button', { name: /Obtener ahora/ })).toBeNull();
    expect(opinion.querySelector('[data-semaforo="gris"]')?.textContent).toMatch(/Sin dato/);
  });

  it('un proveedor en la lista 69-B se pinta en rojo', async () => {
    servidor(historial(), {
      exito: true, en_rojo: 1, alertas: [],
      listas: [{ lista: '69b', descripcion: '', registros: 4, cargada_en: '2026-10-19T06:30:00+00:00', revisada_en: null, url: '', error: null }],
      riesgos: [{
        rfc: 'EFO010101AA1', nombre: 'EMPRESA FACTURADORA SINTETICA', lista: '69b', situacion: 'definitivo',
        situacion_texto: 'Definitivo', relacion: 'proveedor', nivel: 'alto', rojo: true, comprobantes: 2,
        total: '2320.00', fecha_publicacion_sat: null, fecha_publicacion_dof: null,
      }],
    });
    render(<CumplimientoCliente clave="taller" />);
    const riesgos = await screen.findByLabelText('Riesgos 69-B');
    await waitFor(() => expect(riesgos.querySelector('[data-riesgo="rojo"]')?.textContent).toMatch(/EFO010101AA1.*Proveedor.*Definitivo/));
    expect(riesgos.textContent).toMatch(/Lista cargada 2026-10-19 · 4 contribuyentes/);
  });
});
