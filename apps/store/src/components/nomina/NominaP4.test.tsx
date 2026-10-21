/**
 * Pantallas de nómina de P4: historial, captura de variables, finiquito y criterios.
 * El backend se dobla en `services/nominaApi`: aquí se mide lo que la pantalla pinta y
 * lo que manda, no la aritmética (que es del motor).
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  listarHistorial: vi.fn(),
  abrirPeriodo: vi.fn(),
  cerrarPeriodoNomina: vi.fn(),
  compararPeriodos: vi.fn(),
  calcularFiniquito: vi.fn(),
  calcularAguinaldo: vi.fn(),
  calcularPTU: vi.fn(),
  calcularAjusteAnual: vi.fn(),
  obtenerCriterios: vi.fn(),
}));
vi.mock('../../services/nominaApi', () => api);

import HistorialNominas from './HistorialNominas';
import CapturaVariables from './CapturaVariables';
import NominaExtraordinaria from './NominaExtraordinaria';
import CriteriosNominaCliente from '../cartera/CriteriosNominaCliente';
import type { ClienteCartera, EmpleadoCartera } from '../../services/carteraApi';

const periodo = (id: number, inicio: string, neto: string) => ({
  id, tipo: 'ordinaria', periodicidad: '04', inicio, fin: inicio, fecha_pago: inicio,
  estado: 'calculada', empleados: 1, total_percepciones: '8000', total_deducciones: '900',
  total_isr: '500', total_neto: neto,
});

const EMPLEADO = { empleado_no: 'E-1', nombre: 'ANA PRUEBA' } as EmpleadoCartera;

describe('HistorialNominas', () => {
  it('lista, abre lo guardado tal cual y compara dos periodos', async () => {
    api.listarHistorial.mockResolvedValue({ periodos: [periodo(1, '2026-08-16', '7000'), periodo(2, '2026-09-01', '6500')] });
    api.abrirPeriodo.mockResolvedValue({
      periodo: periodo(1, '2026-08-16', '7000'),
      criterios: { febrero: 'quince_siempre' },
      parametros: { uma_diaria: '117.31' },
      resultado: { recibos: [{ empleado_no: 'E-1', nombre: 'ANA PRUEBA', neto: '7000', dias_pagados: 15, percepciones: [], deducciones: [], otros_pagos: [] }] },
    });
    api.compararPeriodos.mockResolvedValue({
      a: periodo(1, '2026-08-16', '7000'), b: periodo(2, '2026-09-01', '6500'),
      diferencia_neto: '-500', diferencia_isr: '0', diferencia_percepciones: '-500', por_empleado: [],
    });
    render(<HistorialNominas clienteId="taller" />);
    expect(await screen.findByText('2026-08-16 a 2026-08-16')).toBeTruthy();

    fireEvent.click(screen.getAllByRole('button', { name: 'Abrir' })[0]);
    expect(await screen.findByText(/UMA 117.31/)).toBeTruthy();
    expect(api.abrirPeriodo).toHaveBeenCalledWith('taller', 1);

    fireEvent.click(screen.getByLabelText('Comparar periodo 1'));
    fireEvent.click(screen.getByLabelText('Comparar periodo 2'));
    fireEvent.click(screen.getByRole('button', { name: /Comparar los dos/ }));
    await waitFor(() => expect(api.compararPeriodos).toHaveBeenCalledWith('taller', 1, 2));
  });

  it('dice cuando no hay nóminas guardadas', async () => {
    api.listarHistorial.mockResolvedValue({ periodos: [] });
    render(<HistorialNominas clienteId="taller" />);
    expect(await screen.findByText(/Aún no hay nóminas guardadas/)).toBeTruthy();
  });
});

describe('CapturaVariables', () => {
  it('manda lo capturado tal cual, sin calcular', () => {
    const onCambiar = vi.fn();
    render(<CapturaVariables empleados={[EMPLEADO]} variables={{}} onCambiar={onCambiar} />);
    fireEvent.change(screen.getByLabelText('Horas dobles de ANA PRUEBA'), { target: { value: '4.5' } });
    expect(onCambiar).toHaveBeenLastCalledWith({ empleado_no: 'E-1', horas_dobles: '4.5' });
    fireEvent.change(screen.getByLabelText('Incapacidad (días) de ANA PRUEBA'), { target: { value: '2' } });
    expect(onCambiar).toHaveBeenLastCalledWith({ empleado_no: 'E-1', incapacidades: [{ tipo: '02', dias: 2 }] });
  });
});

describe('NominaExtraordinaria — finiquito', () => {
  it('manda empleado, baja y causa, y pinta el desglose del motor', async () => {
    api.calcularFiniquito.mockResolvedValue({
      tipo: 'finiquito', periodo_id: 9, advertencias: ['Causa: Despido injustificado.'],
      resultado: {
        conceptos: [{ concepto: 'PRIMA DE ANTIGÜEDAD', importe: '39008.22', exento: '39008.22', gravado: '0', fundamento: 'Art. 162 LFT' }],
        total: '39008.22', isr_ordinario: '0', isr_separacion: '0', neto: '39008.22',
      },
    });
    render(<NominaExtraordinaria tipo="finiquito" clienteId="taller" empleados={[EMPLEADO]} />);
    fireEvent.change(screen.getByLabelText('Fecha de baja'), { target: { value: '2026-06-30' } });
    fireEvent.change(screen.getByLabelText('Causa'), { target: { value: 'despido_injustificado' } });
    fireEvent.click(screen.getByRole('button', { name: /Calcular finiquito/ }));
    expect(await screen.findByText('PRIMA DE ANTIGÜEDAD')).toBeTruthy();
    expect(api.calcularFiniquito).toHaveBeenCalledWith('taller', {
      empleado_no: 'E-1', fecha_baja: '2026-06-30', causa: 'despido_injustificado',
    });
    expect(screen.getByText(/Guardado en el historial/)).toBeTruthy();
  });
});

describe('CriteriosNominaCliente', () => {
  it('pinta cada opción con su explicación y guarda los criterios con los defaults', async () => {
    api.obtenerCriterios.mockResolvedValue({
      defaults: { parcial: 'tarifa_proporcional', febrero: 'quince_siempre' },
      opciones: {
        parcial: { tarifa_proporcional: 'La conservadora.', tarifa_periodo: 'Retiene menos.' },
        febrero: { quince_siempre: 'Siempre 15.', dias_calendario: 'Días naturales.' },
      },
    });
    const onGuardar = vi.fn(async () => undefined);
    const cliente = { id: 'taller', nombre: 'Taller' } as ClienteCartera;
    render(<CriteriosNominaCliente cliente={cliente} soloLectura={false} onGuardar={onGuardar} />);
    expect(await screen.findByText('La conservadora.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Quincenas de 13/), { target: { value: 'dias_calendario' } });
    expect(screen.getByText('Días naturales.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar criterios' }));
    await waitFor(() =>
      expect(onGuardar).toHaveBeenCalledWith({
        ...cliente,
        criterios_nomina: { parcial: 'tarifa_proporcional', febrero: 'dias_calendario' },
      }),
    );
  });
});
