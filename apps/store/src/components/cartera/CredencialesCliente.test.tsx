/**
 * P0-05: sección "e.firma y sello digital (CSD)" de la ficha del cliente.
 *
 * Se stubbea `fetch` (red cerrada) y se mide lo que la pantalla pide y pinta: la lista de
 * credenciales, la alerta de vencimiento, el envío multipart y el borrado.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Credencial } from '../../services/credencialesApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

const { default: CredencialesCliente } = await import('./CredencialesCliente');

function credencial(extra: Partial<Credencial> = {}): Credencial {
  return {
    id: 7, tipo: 'efirma', rfc: 'XAXX010101AB1', numero_certificado: '30001000000500003416',
    valido_desde: '2026-01-01T00:00:00+00:00', valido_hasta: '2030-01-01T00:00:00+00:00',
    dias_para_vencer: 1200, vencida: false, por_vencer: false,
    creado_por: 'uid-1', creado_en: null, ...extra,
  };
}

type Llamada = { url: string; init?: RequestInit };

function servidor(respuestas: Array<{ status?: number; json: unknown }>) {
  const llamadas: Llamada[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    llamadas.push({ url, init });
    const r = respuestas.shift() ?? { json: { exito: true } };
    return new Response(JSON.stringify(r.json), {
      status: r.status ?? 200, headers: { 'Content-Type': 'application/json' },
    });
  }));
  return llamadas;
}

afterEach(() => cleanup());

describe('CredencialesCliente', () => {
  it('pinta la e.firma cargada y el formulario del CSD que falta', async () => {
    const llamadas = servidor([{ json: { exito: true, credenciales: [credencial()] } }]);
    render(<CredencialesCliente clave="taller" />);
    expect(await screen.findByText('30001000000500003416')).toBeTruthy();
    expect(llamadas[0].url).toMatch(/\/api\/v1\/clientes\/taller\/credenciales$/);
    expect(screen.getByRole('form', { name: 'Subir csd' })).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('avisa cuando vence en menos de 30 días', async () => {
    servidor([{ json: { credenciales: [credencial({ dias_para_vencer: 12, por_vencer: true })] } }]);
    render(<CredencialesCliente clave="taller" />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/Vence en 12 días/);
  });

  it('avisa cuando ya venció', async () => {
    servidor([{ json: { credenciales: [credencial({ dias_para_vencer: -3, vencida: true })] } }]);
    render(<CredencialesCliente clave="taller" />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/Venció el 2030-01-01/);
  });

  it('sube .cer, .key y contraseña en multipart y muestra el resultado', async () => {
    const llamadas = servidor([
      { json: { credenciales: [] } },
      { json: { exito: true, credencial: credencial() } },
    ]);
    render(<CredencialesCliente clave="taller" />);
    const form = await screen.findByRole('form', { name: 'Subir efirma' });
    const [cer, key] = Array.from(form.querySelectorAll('input[type="file"]'));
    fireEvent.change(cer, { target: { files: [new File(['c'], 'a.cer')] } });
    fireEvent.change(key, { target: { files: [new File(['k'], 'a.key')] } });
    fireEvent.change(form.querySelector('input[type="password"]')!, { target: { value: 'secreta' } });
    fireEvent.submit(form);

    expect(await screen.findByText('30001000000500003416')).toBeTruthy();
    const envio = llamadas[1];
    expect(envio.init?.method).toBe('POST');
    const cuerpo = envio.init?.body as FormData;
    expect(cuerpo.get('tipo')).toBe('efirma');
    expect(cuerpo.get('password')).toBe('secreta');
    expect((cuerpo.get('cer') as File).name).toBe('a.cer');
  });

  it('muestra el error del backend en español', async () => {
    servidor([
      { json: { credenciales: [] } },
      { status: 422, json: { exito: false, error: 'La contraseña no abre la llave privada (.key).' } },
    ]);
    render(<CredencialesCliente clave="taller" />);
    const form = await screen.findByRole('form', { name: 'Subir efirma' });
    const [cer, key] = Array.from(form.querySelectorAll('input[type="file"]'));
    fireEvent.change(cer, { target: { files: [new File(['c'], 'a.cer')] } });
    fireEvent.change(key, { target: { files: [new File(['k'], 'a.key')] } });
    fireEvent.change(form.querySelector('input[type="password"]')!, { target: { value: 'mala' } });
    fireEvent.submit(form);
    expect(await screen.findByText(/contraseña no abre/)).toBeTruthy();
    expect((form.querySelector('input[type="password"]') as HTMLInputElement).value).toBe('');
  });

  it('borra con confirmación', async () => {
    const llamadas = servidor([
      { json: { credenciales: [credencial()] } },
      { json: { exito: true } },
    ]);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<CredencialesCliente clave="taller" />);
    fireEvent.click(await screen.findByRole('button', { name: /Borrar/ }));
    await waitFor(() => expect(screen.getByRole('form', { name: 'Subir efirma' })).toBeTruthy());
    expect(llamadas[1].init?.method).toBe('DELETE');
    expect(llamadas[1].url).toMatch(/\/credenciales\/7$/);
  });

  it('enseña el error si no se pueden cargar', async () => {
    servidor([{ status: 500, json: { exito: false, error: 'Se cayó la base.' } }]);
    render(<CredencialesCliente clave="taller" />);
    expect(await screen.findByText(/Se cayó la base/)).toBeTruthy();
  });
});
