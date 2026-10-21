/** P6-01: exportar (con sondeo hasta el enlace) y borrar con frase de confirmación. */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const api = vi.hoisted(() => ({
  solicitarExportacion: vi.fn(),
  estadoExportacion: vi.fn(),
  borrarDespacho: vi.fn(),
}));

vi.mock('../../services/cuentaDespachoApi', () => ({
  FRASE_BORRADO: 'BORRAR MI DESPACHO',
  ...api,
}));

import CuentaDatos from './CuentaDatos';

const base = {
  error: null, creado_en: null, bytes: null, tablas: null, archivos: null, url: null,
  vence_en: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('CuentaDatos', () => {
  it('exporta en segundo plano y muestra el enlace cuando está listo', async () => {
    api.solicitarExportacion.mockResolvedValue({ ...base, id: 5, estado: 'pendiente' });
    api.estadoExportacion
      .mockResolvedValueOnce({ ...base, id: 5, estado: 'corriendo' })
      .mockResolvedValueOnce({ ...base, id: 5, estado: 'hecho', url: 'https://api/x.zip' });
    render(<CuentaDatos sondeoMs={1} />);
    fireEvent.click(screen.getByRole('button', { name: /exportar mis datos/i }));
    const enlace = await screen.findByRole('link', { name: /descargar zip/i });
    expect(enlace.getAttribute('href')).toBe('https://api/x.zip');
    expect(api.estadoExportacion).toHaveBeenCalledWith(5);
  });

  it('pinta el motivo cuando el backend la rechaza (no es dueño)', async () => {
    api.solicitarExportacion.mockRejectedValue(new Error('Tu rol no permite esta acción.'));
    render(<CuentaDatos />);
    fireEvent.click(screen.getByRole('button', { name: /exportar mis datos/i }));
    expect((await screen.findByRole('alert')).textContent).toContain('Tu rol no permite');
  });

  it('borrar sólo se habilita con la frase exacta', async () => {
    api.borrarDespacho.mockResolvedValue({ clientes: 2 });
    const alBorrar = vi.fn();
    render(<CuentaDatos alBorrar={alBorrar} />);
    const boton = screen.getByRole('button', { name: /borrar todo/i });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/frase de confirmación/i),
      { target: { value: 'borrar mi despacho' } });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/frase de confirmación/i),
      { target: { value: 'BORRAR MI DESPACHO' } });
    expect((boton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(boton);
    await waitFor(() => expect(alBorrar).toHaveBeenCalled());
    expect(api.borrarDespacho).toHaveBeenCalledWith('BORRAR MI DESPACHO');
    expect(screen.getByText(/se borró/i)).toBeTruthy();
  });
});
