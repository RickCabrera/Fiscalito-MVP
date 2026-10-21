/**
 * Cliente de la bóveda (P0-03), medido por lo que le llega al servidor: URL,
 * método, token y cuerpo. `fetch` stubbeado; nada sale a la red.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-de-prueba' } },
  db: {},
  default: {},
}));

const {
  borrarCfdi, consultaDeFiltros, descargarXml, importarCfdi, listarCfdi, resumenBoveda,
} = await import('./bovedaApi');

interface Peticion { url: string; init: RequestInit }
let peticiones: Peticion[] = [];

function responder(cuerpo: BodyInit, tipo = 'application/json', status = 200) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    peticiones.push({ url, init });
    return new Response(cuerpo, { status, headers: { 'Content-Type': tipo } });
  }));
}

beforeEach(() => { peticiones = []; });

describe('bovedaApi', () => {
  it('sube varios archivos en un multipart con el campo `archivos` y el token', async () => {
    responder(JSON.stringify({ exito: true, importados: 2, duplicados: 0, rechazados: [] }));
    const a = new File(['<a/>'], 'a.xml', { type: 'text/xml' });
    const b = new File(['PK'], 'lote.zip', { type: 'application/zip' });
    const r = await importarCfdi('taller', [a, b]);
    expect(r.importados).toBe(2);
    const { url, init } = peticiones[0];
    expect(url).toMatch(/\/api\/v1\/boveda\/clientes\/taller\/cfdi$/);
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer token-de-prueba');
    // Sin Content-Type a mano: el navegador pone el boundary del multipart.
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
    const datos = init.body as FormData;
    expect(datos.getAll('archivos').map((f) => (f as File).name)).toEqual(['a.xml', 'lote.zip']);
  });

  it('lista con filtros y sin mandar los vacíos', async () => {
    responder(JSON.stringify({ exito: true, total: 0, pagina: 2, por_pagina: 50, comprobantes: [] }));
    await listarCfdi('mi cliente', { tipo: 'I', direccion: '', estatus: undefined, desde: '2026-01-01', pagina: 2 });
    const u = new URL(peticiones[0].url);
    expect(u.pathname).toBe('/api/v1/boveda/clientes/mi%20cliente/cfdi');
    expect(Object.fromEntries(u.searchParams)).toEqual({ tipo: 'I', desde: '2026-01-01', pagina: '2' });
  });

  it('consultaDeFiltros sin filtros no agrega `?`', () => {
    expect(consultaDeFiltros({})).toBe('');
    expect(consultaDeFiltros({ rfc: '', tipo: '' })).toBe('');
  });

  it('descarga el XML como Blob con los mismos bytes', async () => {
    const xml = '<?xml version="1.0"?>\r\n<cfdi:Comprobante>ñ</cfdi:Comprobante>';
    responder(xml, 'application/xml');
    const blob = await descargarXml('taller', 'AAA-111');
    expect(new URL(peticiones[0].url).pathname).toBe('/api/v1/boveda/clientes/taller/cfdi/AAA-111/xml');
    // Como arreglos planos: jsdom y Node tienen cada uno su `Uint8Array`, y
    // `toEqual` entre reinos distintos falla aunque los bytes sean idénticos.
    expect(Array.from(new Uint8Array(await blob.arrayBuffer())))
      .toEqual(Array.from(new TextEncoder().encode(xml)));
  });

  it('borra con DELETE y pide el resumen', async () => {
    responder(JSON.stringify({ exito: true, uuid: 'X', renglones: [] }));
    await borrarCfdi('taller', 'X');
    await resumenBoveda('taller', { desde: '2026-01-01' });
    expect(peticiones[0].init.method).toBe('DELETE');
    expect(new URL(peticiones[0].url).pathname).toBe('/api/v1/boveda/clientes/taller/cfdi/X');
    expect(peticiones[1].url).toMatch(/\/boveda\/clientes\/taller\/resumen\?desde=2026-01-01$/);
  });

  it('un 404 de dominio llega como mensaje legible', async () => {
    responder(JSON.stringify({ exito: false, error: "No existe el cliente 'x' en tu despacho." }),
      'application/json', 404);
    await expect(listarCfdi('x')).rejects.toThrow(/No existe el cliente/);
  });
});
