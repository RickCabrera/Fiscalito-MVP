/**
 * P5-04: "Facturación" de la ficha del cliente. Red cerrada: `fetch` responde por URL.
 * Se mide lo que la pantalla pide y pinta: lista, aviso de PAC de pruebas, emisión con el
 * cuerpo correcto (impuestos de los presets, PPD → forma 99), cancelación con motivo y marcar
 * el cliente como el propio despacho.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Catalogos, Factura } from '../../services/facturacionApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

const { default: FacturacionCliente } = await import('./FacturacionCliente');

const CATALOGOS: Catalogos = {
  forma_pago: [{ clave: '03', descripcion: 'Transferencia' }, { clave: '99', descripcion: 'Por definir' }],
  metodo_pago: [{ clave: 'PUE', descripcion: 'Una exhibición' }, { clave: 'PPD', descripcion: 'Parcialidades' }],
  uso_cfdi: [{ clave: 'G03', descripcion: 'Gastos en general' }],
  regimen_fiscal: [{ clave: '601', descripcion: 'General' }],
  objeto_imp: [], tipo_relacion: [{ clave: '01', descripcion: 'Nota de crédito' }],
  clave_unidad: [{ clave: 'E48', descripcion: 'Unidad de servicio' }],
  clave_prod_serv: [{ clave: '84111500', descripcion: 'Servicios contables' }],
  motivo_cancelacion: [{ clave: '02', descripcion: 'Con errores sin relación' }, { clave: '01', descripcion: 'Con relación' }],
  presets: {
    traslados: [{ clave: 'iva16', impuesto: '002', tipo_factor: 'Tasa', tasa: '0.160000', nombre: 'IVA 16 %' }],
    retenciones: [{ clave: 'ret_isr10', impuesto: '001', tasa: '0.100000', nombre: 'Retención ISR 10 %' }],
  },
};

function factura(extra: Partial<Factura> = {}): Factura {
  return {
    id: 7, tipo: 'I', serie: 'F', folio: '1', uuid: 'AAAA-UUID', rfc_receptor: 'XIA190128J61',
    nombre_receptor: 'XENON', metodo_pago: 'PUE', forma_pago: '03', uso_cfdi: 'G03',
    subtotal: '5000.00', descuento: '0.00', traslados: '800.00', retenciones: '0.00', total: '5800.00',
    saldo: null, estado: 'timbrado', es_prueba: true, fecha_emision: '2026-10-19T10:00:00',
    cargo_id: null, motivo_cancelacion: '', folio_sustitucion: '', relacionados: [], ...extra,
  };
}

type Llamada = { url: string; method: string; body: unknown };

function servidor(facturas: Factura[]) {
  const llamadas: Llamada[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    llamadas.push({ url, method, body: init.body ? JSON.parse(String(init.body)) : null });
    let cuerpo: unknown = { exito: true };
    if (url.endsWith('/facturacion/catalogos')) cuerpo = CATALOGOS;
    else if (url.endsWith('/facturacion/config')) cuerpo = { cliente_propio: method === 'PUT' ? 'taller' : null };
    else if (url.endsWith('/facturas') && method === 'GET') cuerpo = { es_propio: false, facturas };
    else if (url.endsWith('/facturas') || url.endsWith('/cancelar')) cuerpo = { factura: factura() };
    return new Response(JSON.stringify(cuerpo), { headers: { 'Content-Type': 'application/json' } });
  }));
  return llamadas;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('FacturacionCliente', () => {
  it('lista las facturas y avisa que el PAC es de pruebas', async () => {
    servidor([factura()]);
    render(<FacturacionCliente clave="taller" receptores={[{ id: 'tienda', nombre: 'Tienda' }]} />);
    expect(await screen.findByText('F-1')).toBeTruthy();
    expect(screen.getByText(/NO tienen validez fiscal/)).toBeTruthy();
    expect(screen.getByText('XENON')).toBeTruthy();
  });

  it('emite una factura PPD con IVA y retención; la forma va 99', async () => {
    const llamadas = servidor([]);
    render(<FacturacionCliente clave="taller" receptores={[{ id: 'tienda', nombre: 'Tienda' }]} />);
    await screen.findByText(/aún no ha emitido/);
    await waitFor(() => expect((screen.getByText('Nueva factura') as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByText('Nueva factura'));
    fireEvent.change(screen.getByLabelText('Descripción 1'), { target: { value: 'Honorarios' } });
    fireEvent.change(screen.getByLabelText('Valor unitario 1'), { target: { value: '5000' } });
    fireEvent.click(screen.getByLabelText('Retención ISR 10 %'));
    fireEvent.change(screen.getByDisplayValue('PUE Una exhibición'), { target: { value: 'PPD' } });
    fireEvent.click(screen.getByText('Timbrar'));
    await screen.findByText('Factura timbrada.');
    const post = llamadas.find((l) => l.method === 'POST' && l.url.endsWith('/clientes/taller/facturas'));
    expect(post?.body).toMatchObject({
      tipo: 'I', metodo_pago: 'PPD', forma_pago: '99',
      receptor: { clave_cliente: 'tienda', uso_cfdi: 'G03' },
      conceptos: [{ descripcion: 'Honorarios', valor_unitario: '5000', objeto_imp: '02', impuestos: [
        { tipo: 'traslado', impuesto: '002', tasa: '0.160000' },
        { tipo: 'retencion', impuesto: '001', tasa: '0.100000' }] }],
    });
  });

  it('cancela con el motivo elegido y marca al cliente como el propio despacho', async () => {
    const llamadas = servidor([factura()]);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<FacturacionCliente clave="taller" receptores={[]} />);
    fireEvent.click(await screen.findByLabelText('Cancelar F-1'));
    await screen.findByText('Factura cancelada.');
    const c = llamadas.find((l) => l.url.endsWith('/facturas/7/cancelar'));
    expect(c?.body).toEqual({ motivo: '02', folio_sustitucion: null });
    fireEvent.click(screen.getByLabelText(/propio despacho/));
    await waitFor(() => expect(llamadas.some((l) => l.method === 'PUT' && l.url.endsWith('/facturacion/config'))).toBe(true));
    const put = llamadas.find((l) => l.method === 'PUT');
    expect(put?.body).toEqual({ cliente_propio: 'taller' });
  });
});
