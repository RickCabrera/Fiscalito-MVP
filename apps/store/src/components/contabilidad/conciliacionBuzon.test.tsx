/**
 * Conciliación bancaria (P2-06) y Buzón / Anexo 24 (P2-07) con `fetch`
 * stubbeado: se mide qué se le pide al backend y qué se pinta con su respuesta.
 * Ningún cuadre se decide en el navegador.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const { default: ConciliacionBancaria } = await import('./ConciliacionBancaria');
const { default: BuzonTab } = await import('./BuzonTab');

const CUENTA = { id: 7, banco: '012', nombre: 'BBVA', numero: '0123', clabe: '', moneda: 'MXN', cuenta_contable_id: 3, cuenta_contable: '102.01.01', ventana_dias: 3, umbral: 60, activa: true };

const VISTA = {
  cuenta: CUENTA, pendientes_banco: 1, pendientes_libros: 1,
  banco: [
    { clave: 'b:1', id: 1, fecha: '2026-03-02', concepto: 'SPEI RECIBIDO', referencia: 'R1', cargo: '0.00', abono: '1160.00', saldo: '11160.00', conciliacion_id: 9 },
    { clave: 'b:2', id: 2, fecha: '2026-03-15', concepto: 'COMISION', referencia: '', cargo: '116.00', abono: '0.00', saldo: null, conciliacion_id: null },
  ],
  libros: [
    { clave: 'p:5', id: 5, origen: 'poliza', poliza_id: 1, folio: 'I-2026-03-0001', fecha: '2026-03-01', concepto: 'Cobro F-1', cargo: '1160.00', abono: '0.00', uuid: '', rfc: '', conciliacion_id: 9 },
    { clave: 'p:6', id: 6, origen: 'poliza', poliza_id: 2, folio: 'E-2026-03-0001', fecha: '2026-03-15', concepto: 'Gasto', cargo: '0.00', abono: '116.00', uuid: '', rfc: '', conciliacion_id: null },
  ],
};

let peticiones: { ruta: string; method: string; body: string }[] = [];

beforeEach(() => {
  cleanup();
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    const ruta = new URL(url).pathname;
    peticiones.push({ ruta, method, body: typeof init.body === 'string' ? init.body : '' });
    if (ruta.endsWith('/conciliacion/clientes/taller/cuentas') && method === 'GET') return Response.json({ exito: true, cuentas: [CUENTA] });
    if (ruta.endsWith('/plantillas')) return Response.json({ exito: true, plantillas: [] });
    if (ruta.endsWith('/movimientos')) return Response.json({ exito: true, ...VISTA });
    if (ruta.endsWith('/conciliar')) return Response.json({ exito: true, resultado: { conciliados: 1, uno_a_varios: 0, ambiguos: [], pendientes_banco: 1, pendientes_libros: 1 } });
    if (ruta.endsWith('/conciliaciones') && method === 'POST') return Response.json({ exito: true, conciliacion_id: 10 }, { status: 201 });
    if (ruta.includes('/conciliaciones/')) return Response.json({ exito: true });
    if (ruta.endsWith('/contabilidad-electronica/documentos')) {
      return Response.json({ exito: true, instrucciones_portal: ['Sube el ZIP en el portal del SAT.'], documentos: [
        { clave: 'catalogo', nombre: 'Catálogo de cuentas', sufijo: 'CT', a_solicitud: false },
        { clave: 'balanza', nombre: 'Balanza de comprobación', sufijo: 'B', a_solicitud: false },
        { clave: 'polizas', nombre: 'Pólizas del periodo', sufijo: 'PL', a_solicitud: true },
      ] });
    }
    if (ruta.endsWith('/validar')) {
      const b = JSON.parse(String(init.body));
      return b.documento === 'catalogo'
        ? Response.json({ exito: true, nombre: 'XAXX010101AB1202603CT', valido: false, errores: ["línea 1: Element 'Ctas': missing"], advertencias: [], sellado: false, xml: '<x/>' })
        : Response.json({ exito: true, nombre: 'XAXX010101AB1202603BN', valido: true, errores: [], advertencias: [], sellado: false, xml: '<x/>' });
    }
    return Response.json({ exito: true });
  }));
});

describe('Conciliación bancaria', () => {
  it('pinta las dos tablas con sus marcas y concilia en el backend', async () => {
    render(<ConciliacionBancaria clave="taller" />);
    const banco = await screen.findByRole('table', { name: 'Estado de cuenta' });
    const libros = screen.getByRole('table', { name: 'Movimientos de pólizas' });
    expect(within(banco).getByText('SPEI RECIBIDO').closest('tr')?.textContent).toContain('Conciliado');
    expect(within(banco).getByText('COMISION').closest('tr')?.textContent).toContain('Pendiente');
    expect(within(libros).getByText('Gasto').closest('tr')?.textContent).toContain('Pendiente');

    fireEvent.click(screen.getByRole('button', { name: /^Conciliar$/ }));
    await screen.findByText(/1 conciliaciones/);
    expect(peticiones.some((p) => p.ruta.endsWith('/cuentas/7/conciliar') && p.method === 'POST')).toBe(true);
  });

  it('concilia a mano lo seleccionado y deshace', async () => {
    render(<ConciliacionBancaria clave="taller" />);
    await screen.findByRole('table', { name: 'Estado de cuenta' });
    const manual = screen.getByRole('button', { name: /Conciliar selección/ });
    fireEvent.click(screen.getByLabelText('Seleccionar COMISION'));
    expect((manual as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('Seleccionar Gasto'));
    expect((manual as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(manual);
    await waitFor(() => expect(peticiones.find((p) => p.ruta.endsWith('/cuentas/7/conciliaciones'))?.body)
      .toBe(JSON.stringify({ banco: ['b:2'], libros: ['p:6'], motivo: '' })));

    fireEvent.click(within(screen.getByRole('table', { name: 'Estado de cuenta' })).getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(peticiones.some((p) => p.ruta.endsWith('/cuentas/7/conciliaciones/9') && p.method === 'DELETE')).toBe(true));
  });
});

describe('Buzón (Anexo 24)', () => {
  it('muestra los errores del XSD, no deja bajar un XML inválido, y dice cómo subirlo', async () => {
    render(<BuzonTab clave="taller" />);
    await screen.findByText('Sube el ZIP en el portal del SAT.');
    fireEvent.change(screen.getByLabelText('Documento'), { target: { value: 'catalogo' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar y validar/ }));
    await screen.findByText(/NO valida/);
    expect(screen.getByText("línea 1: Element 'Ctas': missing")).toBeTruthy();
    expect((screen.getByRole('button', { name: /Descargar ZIP/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /Enviar/ })).toBeNull();
  });

  it('pólizas pide tipo de solicitud y número de orden', async () => {
    render(<BuzonTab clave="taller" />);
    await screen.findByText('Sube el ZIP en el portal del SAT.');
    fireEvent.change(screen.getByLabelText('Documento'), { target: { value: 'polizas' } });
    fireEvent.change(screen.getByLabelText('Tipo de solicitud'), { target: { value: 'AF' } });
    fireEvent.change(screen.getByPlaceholderText('ABC1234567/26'), { target: { value: 'abc1234567/26' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar y validar/ }));
    await screen.findByText(/valida contra el XSD oficial/);
    const body = JSON.parse(peticiones.find((p) => p.ruta.endsWith('/validar'))!.body);
    expect(body).toMatchObject({ documento: 'polizas', tipo_solicitud: 'AF', num_orden: 'ABC1234567/26' });
    expect((screen.getByRole('button', { name: /Descargar ZIP/ }) as HTMLButtonElement).disabled).toBe(false);
  });
});
