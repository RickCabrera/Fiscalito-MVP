/**
 * P4-12 y P4-13 en pantalla: dispersión (excluidos y POR CONFIRMAR antes de descargar) y
 * envío de recibos (estado por recibo, omitidos, reenviar). El backend se dobla en
 * `services/dispersionApi` y `services/conciliacionApi`: aquí se mide lo que se pinta y
 * lo que se manda.
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  listarLayouts: vi.fn(),
  generarDispersion: vi.fn(),
  bytesDeBase64: vi.fn(() => new Uint8Array([65])),
  enviarRecibos: vi.fn(),
  estadoEnvios: vi.fn(),
  reenviarRecibo: vi.fn(),
  listarPlantillasRecibo: vi.fn(),
  guardarPlantillaRecibo: vi.fn(),
}));
const conc = vi.hoisted(() => ({ listarCuentasBancarias: vi.fn() }));
vi.mock('../../services/dispersionApi', () => api);
vi.mock('../../services/conciliacionApi', () => conc);

import PanelDispersion from './PanelDispersion';
import PanelEnvioRecibos from './PanelEnvioRecibos';

afterEach(cleanup);

const BANAMEX = {
  id: 'banamex', nombre: 'Banamex', banco: '002', estado: 'verificado', fuente: 'LayOut D', interbancario: true,
  datos_requeridos: [{ clave: 'numero_cliente', etiqueta: 'Número de cliente Banamex', patron: '', obligatorio: true, default: '' }],
};
const BBVA = { ...BANAMEX, id: 'bbva', nombre: 'BBVA', banco: '012', estado: 'por_confirmar', fuente: 'POR CONFIRMAR', datos_requeridos: [] };
const GENERICO = { ...BANAMEX, id: 'generico', nombre: 'Genérico', banco: null, datos_requeridos: [] };

describe('PanelDispersion', () => {
  it('manda banco, cuenta de cargo y datos; pinta el cuadre y los excluidos', async () => {
    api.listarLayouts.mockResolvedValue({
      layouts: [GENERICO, BANAMEX, BBVA], columnas_genericas: {}, columnas_default: [], bancos: {},
      datos_guardados: { banamex: { numero_cliente: '123' } },
    });
    conc.listarCuentasBancarias.mockResolvedValue({
      cuentas: [{ id: 7, banco: '002', nombre: 'Nómina', numero: '70001234567', activa: true },
        { id: 8, banco: '012', nombre: 'Otra', numero: '1', activa: true }],
    });
    api.generarDispersion.mockResolvedValue({
      layout: BANAMEX, archivo: { nombre: 'Dispersion_banamex_20260831.txt', mime: 'text/plain', base64: 'QQ==', sha256: 'x' },
      incluidos: [{ empleado_no: 'E1' }], total_nomina: '300.00', total_archivo: '200.00', total_excluidos: '100.00',
      cuadra: true, advertencias: [],
      excluidos: [{ empleado_no: 'E4', nombre: 'PERSONA E4', neto: '100.00', causa: 'sin_cuenta', motivo: 'Sin CLABE ni cuenta capturada en su ficha.' }],
    });
    render(<PanelDispersion clienteId="taller" periodoId={5} />);
    fireEvent.change(await screen.findByLabelText('Banco / layout'), { target: { value: 'banamex' } });
    const cargo = screen.getByLabelText('Cuenta de cargo');
    expect(screen.queryByText(/Otra/)).toBeNull(); // sólo las cuentas del banco del layout
    fireEvent.change(cargo, { target: { value: '7' } });
    expect((screen.getByLabelText(/Número de cliente Banamex/) as HTMLInputElement).value).toBe('123');
    fireEvent.click(screen.getByRole('button', { name: 'Generar archivo' }));
    await waitFor(() =>
      expect(api.generarDispersion).toHaveBeenCalledWith('taller', 5, {
        layout: 'banamex', cuenta_cargo_id: 7, datos_banco: { numero_cliente: '123' },
      }),
    );
    expect(await screen.findByText('Cuadra al centavo.')).toBeTruthy();
    expect(screen.getByText('Sin CLABE ni cuenta capturada en su ficha.')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Descargar Dispersion_banamex/ })).toBeTruthy();
  });

  it('un layout por confirmar lo dice antes de generar', async () => {
    api.listarLayouts.mockResolvedValue({ layouts: [GENERICO, BBVA], columnas_genericas: {}, columnas_default: [], bancos: {}, datos_guardados: {} });
    conc.listarCuentasBancarias.mockResolvedValue({ cuentas: [] });
    render(<PanelDispersion clienteId="taller" periodoId={5} />);
    fireEvent.change(await screen.findByLabelText('Banco / layout'), { target: { value: 'bbva' } });
    expect(screen.getByText(/POR CONFIRMAR CON MANUAL DEL BANCO/)).toBeTruthy();
    expect(screen.getByText(/no tiene cuentas BBVA activas/)).toBeTruthy();
  });
});

describe('PanelEnvioRecibos', () => {
  const ESTADO = {
    canal: 'correo', resumen: { pendiente: 0, enviado: 1, fallido: 1, rebotado: 0 }, trabajo: { id: 1, estado: 'hecho', error: null },
    envios: [
      { id: 10, empleado_no: 'E1', destino: 'ana@ejemplo.mx', estado: 'enviado', intentos: 1, error: '', timbrado: false, enviado_en: null },
      { id: 11, empleado_no: 'E2', destino: 'luis@ejemplo.mx', estado: 'fallido', intentos: 3, error: 'SMTP caído', timbrado: false, enviado_en: null },
    ],
    omitidos: [{ empleado_no: 'E4', nombre: 'PERSONA E4', motivo: 'Sin correo capturado en su ficha.' }],
  };

  it('envía por el canal elegido, pinta el estado por recibo y reenvía uno', async () => {
    api.estadoEnvios.mockResolvedValue({ ...ESTADO, envios: [], omitidos: [], resumen: { pendiente: 0, enviado: 0, fallido: 0, rebotado: 0 }, trabajo: null });
    api.enviarRecibos.mockResolvedValue(ESTADO);
    api.reenviarRecibo.mockResolvedValue(ESTADO);
    render(<PanelEnvioRecibos clienteId="taller" periodoId={5} />);
    await waitFor(() => expect(api.estadoEnvios).toHaveBeenCalledWith('taller', 5, 'correo'));
    fireEvent.click(screen.getByRole('button', { name: 'Enviar recibos' }));
    await waitFor(() => expect(api.enviarRecibos).toHaveBeenCalledWith('taller', 5, 'correo'));
    expect(await screen.findByText(/SMTP caído/)).toBeTruthy();
    expect(screen.getByText(/Sin correo capturado/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole('button', { name: 'Reenviar' })[1]);
    await waitFor(() => expect(api.reenviarRecibo).toHaveBeenCalledWith('taller', 5, 11));
  });

  it('cambiar a WhatsApp pide el estado de ese canal', async () => {
    api.estadoEnvios.mockResolvedValue({ ...ESTADO, canal: 'whatsapp' });
    render(<PanelEnvioRecibos clienteId="taller" periodoId={5} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'whatsapp' } });
    await waitFor(() => expect(api.estadoEnvios).toHaveBeenCalledWith('taller', 5, 'whatsapp'));
  });
});
