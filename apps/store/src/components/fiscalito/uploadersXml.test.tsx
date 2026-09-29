/**
 * C-03 · Un `.XML` entra igual que un `.xml` en los TRES uploaders de CFDI, y lo
 * que no es XML se muestra rechazado con su nombre en vez de desaparecer.
 *
 * Los tres son todos los que hay: Contabilito, Declaración anual, DIOT,
 * Retenciones, Multi-periodo y Estado de cuenta montan `XMLUploader`, así que
 * no tienen filtro propio. CFDI sintéticos (`test/cfdiSintetico.ts`).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../../context/ProfileContext';
import type { CFDI } from '../../services/fiscalAgentApi';
import { MOTIVO_NO_XML } from '../../services/archivosXml';
import { archivo, cfdiSintetico, RFC_RECEPTOR_PRUEBA } from '../../test/cfdiSintetico';

const PERFIL: UserProfile = {
  contributorType: 'independiente', rfc: RFC_RECEPTOR_PRUEBA, regimen: '612', nombre: 'Contribuyente Demo',
  actividad: '', cp: '', telefono: '', nombreNegocio: '', numEmpleados: '', nombreDespacho: '',
  onboardingComplete: true,
};

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));
vi.mock('../../context/ProfileContext', () => ({
  useProfile: () => ({ profile: PERFIL, loading: false }),
}));
vi.mock('../../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('../../services/declaracionesHistory', async () => {
  const real = await vi.importActual<typeof import('../../services/declaracionesHistory')>('../../services/declaracionesHistory');
  return {
    ...real,
    guardarDeclaracion: vi.fn(async () => 'id'),
    obtenerAcumuladoAnterior: vi.fn(async () => ({
      ingresos_acumulados: 0, deducciones_acumuladas: 0, isr_pagado_anterior: 0,
      isr_retenido_acumulado: 0, meses_encontrados: [], meses_faltantes: [],
    })),
  };
});

const { default: XMLUploader } = await import('./XMLUploader');
const { default: PreDeclaracionTab } = await import('./PreDeclaracionTab');
const { default: DeduccionesPersonalesTab } = await import('./DeduccionesPersonalesTab');
const { AgentProvider } = await import('../../agent/AgentContext');

const UUID_1 = 'aaaaaaaa-0000-4000-8000-000000000001';
const UUID_2 = 'aaaaaaaa-0000-4000-8000-000000000002';
const UUID_N = 'aaaaaaaa-0000-4000-8000-00000000000e';

function inputArchivos(): HTMLInputElement {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

afterEach(() => cleanup());

describe('C-03 · XMLUploader (Contabilito, Anual, DIOT, Retenciones, Multi-periodo, Estado de cuenta)', () => {
  it('un .XML se carga exactamente igual que un .xml', async () => {
    const recibido: CFDI[][] = [];
    render(<XMLUploader facturas={[]} onChange={(f) => recibido.push(f)} />);
    fireEvent.change(inputArchivos(), {
      target: { files: [archivo('a.xml', cfdiSintetico({ uuid: UUID_1 })), archivo('B.XML', cfdiSintetico({ uuid: UUID_2 }))] },
    });
    await waitFor(() => expect(recibido.length).toBe(1));
    expect(recibido[0].map((f) => f.uuid)).toEqual([UUID_1, UUID_2]);
    expect(screen.queryByText(new RegExp(MOTIVO_NO_XML))).toBeNull();
  });

  it('un recibo de nómina NOMINA.XML entra y se cuenta como excluido, igual que uno .xml', async () => {
    let facturas: CFDI[] = [];
    const guardar = (f: CFDI[]) => { facturas = f; };
    const { rerender } = render(<XMLUploader facturas={facturas} onChange={guardar} />);
    fireEvent.change(inputArchivos(), {
      target: { files: [archivo('NOMINA.XML', cfdiSintetico({ uuid: UUID_N, tipo: 'N' }))] },
    });
    await waitFor(() => expect(facturas.length).toBe(1));
    rerender(<XMLUploader facturas={facturas} onChange={guardar} />);
    expect(facturas[0].tipo).toBe('NOMINA');
    expect(screen.getByText(/1 recibo de nómina detectado/)).toBeTruthy();
  });

  it('lo que no es XML, soltado por drag & drop, se muestra rechazado con su nombre', async () => {
    const onChange = vi.fn();
    render(<XMLUploader facturas={[]} onChange={onChange} />);
    fireEvent.drop(inputArchivos().parentElement!, { dataTransfer: { files: [archivo('notas.pdf', '%PDF-1.4')] } });
    expect(await screen.findByText(`notas.pdf: ${MOTIVO_NO_XML}`, { exact: false })).toBeTruthy();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('"Limpiar" también borra los rechazados', async () => {
    let facturas: CFDI[] = [];
    const guardar = (f: CFDI[]) => { facturas = f; };
    const { rerender } = render(<XMLUploader facturas={facturas} onChange={guardar} />);
    fireEvent.change(inputArchivos(), {
      target: { files: [archivo('A.XML', cfdiSintetico({ uuid: UUID_1 })), archivo('foto.jpg', 'x')] },
    });
    await waitFor(() => expect(facturas.length).toBe(1));
    rerender(<XMLUploader facturas={facturas} onChange={guardar} />);
    expect(screen.getByText(/foto\.jpg/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Limpiar/ }));
    expect(screen.queryByText(/foto\.jpg/)).toBeNull();
  });

  it('el input acepta .XML', () => {
    render(<XMLUploader facturas={[]} onChange={() => {}} />);
    expect(inputArchivos().accept.split(',')).toContain('.XML');
  });
});

describe('C-03 · PreDeclaracionTab', () => {
  function montar() {
    return render(<MemoryRouter><AgentProvider><PreDeclaracionTab /></AgentProvider></MemoryRouter>);
  }

  it('un .XML se carga a la tabla y un .pdf se muestra rechazado con su nombre', async () => {
    montar();
    fireEvent.change(inputArchivos(), {
      target: { files: [archivo('FACTURA.XML', cfdiSintetico({ uuid: UUID_1 })), archivo('notas.pdf', '%PDF')] },
    });
    expect(await screen.findByText(`notas.pdf: ${MOTIVO_NO_XML}`, { exact: false })).toBeTruthy();
    expect(await screen.findByText(/^1 factura$/)).toBeTruthy();
    expect(inputArchivos().accept.split(',')).toContain('.XML');
  });

  it('por drag & drop: sólo un no-XML deja el aviso y ninguna factura', async () => {
    montar();
    fireEvent.drop(inputArchivos().parentElement!, { dataTransfer: { files: [archivo('hoja.xlsx', 'x')] } });
    expect(await screen.findByText(`hoja.xlsx: ${MOTIVO_NO_XML}`, { exact: false })).toBeTruthy();
    expect(screen.queryByText(/^\d+ facturas?$/)).toBeNull();
  });
});

describe('C-03 · DeduccionesPersonalesTab', () => {
  it('un .XML se procesa y un archivo que no es XML se muestra rechazado con su nombre', async () => {
    render(<DeduccionesPersonalesTab />);
    fireEvent.change(inputArchivos(), {
      target: { files: [archivo('MEDICO.XML', cfdiSintetico({ uuid: UUID_1, claveProdServ: '85121600' })), archivo('receta.png', 'x')] },
    });
    expect(await screen.findByText(/1 facturas procesadas/)).toBeTruthy();
    expect(screen.getByText(`receta.png: ${MOTIVO_NO_XML}`, { exact: false })).toBeTruthy();
    expect(inputArchivos().accept.split(',')).toContain('.XML');
  });

  it('un XML que el parser no puede leer ya no se pierde en silencio', async () => {
    render(<DeduccionesPersonalesTab />);
    fireEvent.change(inputArchivos(), { target: { files: [archivo('ROTO.XML', '<cfdi:Comprobante><sin cerrar>')] } });
    expect(await screen.findByText(/ROTO\.XML:/)).toBeTruthy();
  });
});
