/**
 * P3-04 y P3-05: CFDI de retenciones timbrado y DIOT con el layout 2025, desde el backend.
 * El front no arma XML ni `.txt`: pide, descarga y corrige la clasificación del proveedor.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import RetencionesCfdiPanel from './RetencionesCfdiPanel';
import DiotOficialPanel from './DiotOficialPanel';

const TERCERO = {
  rfc: 'PERJ800101AB1', nombre: 'PERSONA SINTETICA', regimen: '612', domicilio_fiscal: '06700',
  monto_operacion: '10000.00', isr_retenido: '1000.00', iva_retenido: '1066.67', cantidad_cfdi: 1,
  cve_retenc_sugerida: '01', uuids: ['A'],
};
const EMITIDO = {
  uuid: '5E2D6AFF-2DD7-43D1-83D3-14C1ACA396D9', rfc_tercero: TERCERO.rfc,
  nombre_tercero: TERCERO.nombre, ejercicio: 2026, mes_ini: 3, mes_fin: 3, cve_retenc: '01',
  monto_operacion: '10000.00', isr_retenido: '1000.00', iva_retenido: '1066.67',
  estado: 'timbrado', pac: 'falso', es_prueba: true, fecha_timbrado: '2026-04-05T16:00:05+00:00',
  motivo_cancelacion: '',
};
const PROVEEDOR = {
  rfc: 'PRO010101AA1', nombre: 'PROVEEDOR SINTETICO', tipo_tercero: '04', tipo_operacion: '85',
  clasificacion_capturada: false,
  config: { tipo_tercero: null, tipo_operacion: null, region_8: 'norte', importacion: 'tangibles',
    asignacion_iva: 'gravadas', iva_no_acreditable: '', id_fiscal: '', nombre_extranjero: '',
    pais: '', jurisdiccion: '', efectos_fiscales: '01' },
  campos: { valor_tasa_16: 10000, acreditable_gravadas_tasa_16: 1600, tasa_0: 2000, iva_retenido: 0 },
  cantidad_cfdi: 1, advertencias: [], linea: '04|85|PRO010101AA1|...',
};

let emitidos: unknown[] = [];
let peticiones: { url: string; method: string; body?: string }[] = [];

beforeEach(() => {
  emitidos = [];
  peticiones = [];
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() }));
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: init.body as string | undefined });
    if (url.includes('/retenciones-cfdi/terceros')) return Response.json({ terceros: [TERCERO], emitidos });
    if (url.endsWith('/retenciones-cfdi') && method === 'POST') {
      emitidos = [EMITIDO];
      return Response.json({ cfdi: EMITIDO });
    }
    if (url.endsWith('/xml') || url.endsWith('/pdf') || url.endsWith('/txt')) return new Response('archivo');
    if (url.endsWith('/cancelar')) return Response.json({ cfdi: { ...EMITIDO, estado: 'cancelado' } });
    if (url.includes('/diot/proveedores/')) return Response.json({ exito: true });
    if (url.includes('/diot/2026/3')) {
      return Response.json({ anio: 2026, mes: 3, total_proveedores: 1, proveedores: [PROVEEDOR],
        advertencias: [], errores_layout: [], layout: 'DIOT carga masiva 2025 (54 campos, separador |, UTF-8)' });
    }
    return Response.json({ exito: false, error: `no stubbeado ${url}` }, { status: 500 });
  }));
});

afterEach(() => cleanup());

describe('CFDI de retenciones (P3-04)', () => {
  it('genera, avisa que el PAC es de pruebas, descarga XML y PDF y cancela', async () => {
    render(<RetencionesCfdiPanel clave="taller" anio={2026} mes={3} />);
    expect(await screen.findByText('PERSONA SINTETICA')).toBeTruthy();
    expect(screen.getByText('Sin emitir')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Generar CFDI' }));
    expect(await screen.findByText(/Timbrado · 5E2D6AFF/)).toBeTruthy();
    const alta = peticiones.find((p) => p.method === 'POST' && p.url.endsWith('/retenciones-cfdi'))!;
    expect(JSON.parse(alta.body!)).toEqual({ rfc_tercero: TERCERO.rfc, ejercicio: 2026, mes_ini: 3, mes_fin: 3 });
    expect(screen.getByRole('note').textContent).toMatch(/NO tienen validez fiscal/);

    fireEvent.click(screen.getByRole('button', { name: `XML de ${TERCERO.rfc}` }));
    fireEvent.click(screen.getByRole('button', { name: `PDF de ${TERCERO.rfc}` }));
    await waitFor(() => expect(peticiones.filter((p) => /\/(xml|pdf)$/.test(p.url))).toHaveLength(2));

    vi.spyOn(window, 'confirm').mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: `Cancelar CFDI de ${TERCERO.rfc}` }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/cancelar'))).toBe(true));
    const cancel = peticiones.find((p) => p.url.endsWith('/cancelar'))!;
    expect(JSON.parse(cancel.body!)).toEqual({ motivo: '02', folio_sustitucion: null });
  });
});

describe('DIOT layout 2025 (P3-05)', () => {
  it('pinta cortes por tasa, guarda la clasificación del proveedor y baja el .txt del backend', async () => {
    render(<DiotOficialPanel clave="taller" anio={2026} mes={3} />);
    expect(await screen.findByText('PROVEEDOR SINTETICO')).toBeTruthy();
    expect(screen.getByText(/54 campos/)).toBeTruthy();
    expect(screen.queryByText(/PORVALIDAR/)).toBeNull();
    fireEvent.change(screen.getByLabelText(`Tipo de operación de ${PROVEEDOR.rfc}`), { target: { value: '06' } });
    await waitFor(() => expect(peticiones.some((p) => p.method === 'PUT')).toBe(true));
    const put = peticiones.find((p) => p.method === 'PUT')!;
    expect(put.url).toContain(`/clientes/taller/diot/proveedores/${PROVEEDOR.rfc}`);
    expect(JSON.parse(put.body!)).toMatchObject({ tipo_operacion: '06', efectos_fiscales: '01' });

    fireEvent.click(screen.getByRole('button', { name: /Descargar DIOT/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/diot/2026/3/txt'))).toBe(true));
  });

  it('antes de 2025 no ofrece el archivo de 54 campos', () => {
    render(<DiotOficialPanel clave="taller" anio={2024} mes={3} />);
    expect(screen.getByText(/aplica desde el ejercicio 2025/)).toBeTruthy();
  });
});
