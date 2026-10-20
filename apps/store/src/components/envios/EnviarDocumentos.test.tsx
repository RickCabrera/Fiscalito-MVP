/**
 * P5-05: "Enviar documentos" de la ficha del cliente. Red cerrada: `fetch` responde por URL.
 * Se mide: contactos con su consentimiento, el cuerpo del envío (documentos, canales y
 * contactos elegidos), el aviso de omitidos, el estado por envío y el reenvío.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Contacto, DocumentoEnviable, EstadoEnvios } from '../../services/enviosDocumentosApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

const { default: EnviarDocumentos } = await import('./EnviarDocumentos');

const CONTACTOS: Contacto[] = [
  { id: 1, nombre: 'Ana Ruiz', puesto: '', correo: 'ana@taller.mx', telefono: '5215512345678', consentimiento_whatsapp: true, consentimiento_en: '2026-10-19', activo: true },
  { id: 2, nombre: 'Luis Paz', puesto: '', correo: 'luis@taller.mx', telefono: '5215598765432', consentimiento_whatsapp: false, consentimiento_en: null, activo: true },
];
const DOCS: DocumentoEnviable[] = [
  { tipo: 'factura', ref: '7', nombre_tipo: 'Factura', descripcion: 'Factura F-1', fecha: '2026-10-19', estado: 'timbrado' },
  { tipo: 'opinion', ref: '3', nombre_tipo: 'Opinión de cumplimiento', descripcion: 'positiva', fecha: '2026-10-01', estado: '' },
];
const ENVIADO: EstadoEnvios = {
  envios: [{ id: 9, contacto_id: 1, canal: 'whatsapp', destino: '5215512345678', tipo_documento: 'factura', ref: '7', descripcion: 'Envío de F-1', estado: 'fallido', intentos: 3, error: 'caído', enviado_en: null }],
  resumen: { fallido: 1 }, trabajo: { id: 1, estado: 'hecho', error: null },
};

type Llamada = { url: string; method: string; body: unknown };

function servidor() {
  const llamadas: Llamada[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : null;
    llamadas.push({ url, method, body });
    let cuerpo: unknown = { exito: true };
    if (url.endsWith('/contactos') && method === 'GET') cuerpo = { contactos: CONTACTOS };
    else if (url.endsWith('/documentos-enviables')) cuerpo = { documentos: DOCS };
    else if (url.endsWith('/envios') && method === 'POST') {
      cuerpo = { ...ENVIADO, omitidos: [{ contacto: 'Luis Paz', canal: 'whatsapp', motivo: 'Sin consentimiento.' }] };
    } else if (url.includes('/envios')) cuerpo = ENVIADO;
    else if (url.endsWith('/contactos')) cuerpo = { contacto: CONTACTOS[0] };
    return new Response(JSON.stringify(cuerpo), { headers: { 'Content-Type': 'application/json' } });
  }));
  return llamadas;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('EnviarDocumentos', () => {
  it('envía los documentos elegidos por los dos canales y avisa a quién no', async () => {
    const llamadas = servidor();
    render(<EnviarDocumentos clave="taller" />);
    fireEvent.click(await screen.findByText('Factura F-1'));
    fireEvent.click(screen.getByLabelText('Enviar a Ana Ruiz'));
    fireEvent.click(screen.getByLabelText('Enviar a Luis Paz'));
    fireEvent.click(screen.getByLabelText('Canal whatsapp'));
    fireEvent.click(screen.getByText('Enviar'));
    expect(await screen.findByText(/Luis Paz por whatsapp/)).toBeTruthy();
    const post = llamadas.find((l) => l.method === 'POST' && l.url.endsWith('/clientes/taller/envios'));
    expect(post?.body).toEqual({
      documentos: [{ tipo: 'factura', ref: '7' }], canales: ['correo', 'whatsapp'],
      contactos: [1, 2], mensaje: '',
    });
    expect(screen.getByText(/Falló — caído/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Reenviar 9'));
    await waitFor(() => expect(llamadas.some((l) => l.url.endsWith('/envios/9/reenviar'))).toBe(true));
  });

  it('pinta el consentimiento de WhatsApp de cada contacto y da de alta uno nuevo', async () => {
    const llamadas = servidor();
    render(<EnviarDocumentos clave="taller" />);
    const ana = await screen.findByLabelText('Consentimiento WhatsApp de Ana Ruiz') as HTMLInputElement;
    expect(ana.checked).toBe(true);
    expect((screen.getByLabelText('Consentimiento WhatsApp de Luis Paz') as HTMLInputElement).checked).toBe(false);
    fireEvent.change(screen.getByLabelText('Nombre del contacto'), { target: { value: 'Eva' } });
    fireEvent.change(screen.getByLabelText('Correo del contacto'), { target: { value: 'eva@taller.mx' } });
    fireEvent.click(screen.getByText('Agregar'));
    await waitFor(() => expect(llamadas.some((l) => l.method === 'POST' && l.url.endsWith('/contactos'))).toBe(true));
    const alta = llamadas.find((l) => l.method === 'POST' && l.url.endsWith('/contactos'));
    expect(alta?.body).toMatchObject({ nombre: 'Eva', correo: 'eva@taller.mx', consentimiento_whatsapp: false });
  });
});
