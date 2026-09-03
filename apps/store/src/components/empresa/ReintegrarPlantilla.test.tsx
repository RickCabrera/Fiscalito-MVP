/**
 * El aviso y la acción que cierran el hueco de O-03. (O-cierre)
 *
 * Lo que se mide aquí no es que un botón haga clic: es que el operador **se
 * entere** de que cambiar las prestaciones no toca a la plantilla que ya
 * existe, y que cuando la reintegra se le diga quién cambió — porque cada
 * cambio de SBC es un aviso de modificación de salario ante el IMSS.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { CarteraContextType } from '../../context/carteraStore';
import type { ClienteCartera, EmpleadoCartera } from '../../services/carteraApi';
import { PARAMETROS_DE_LEY } from '../../services/carteraApi';
import { EMPRESA_POR_DEFECTO } from '../../services/empresa';

const reintegrarPlantilla = vi.fn();
vi.mock('../../services/reintegrarPlantilla', () => ({
  reintegrarPlantilla: (...args: unknown[]) => reintegrarPlantilla(...args),
}));

const { default: ReintegrarPlantilla } = await import('./ReintegrarPlantilla');

function empleado(no: string): EmpleadoCartera {
  return {
    empleado_no: no,
    nombre: `PERSONA ${no}`,
    puesto: '',
    salario_diario: '500.00',
    salario_diario_integrado: '524.65',
    zona: 'general',
    fecha_alta: '2020-03-01',
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '01010101011',
    employee_no: no,
    enrolamiento: 'enrolado',
  };
}

const guardarEmpleado = vi.fn(async () => {});

function cartera(empleados: EmpleadoCartera[], soloLectura = false): CarteraContextType {
  const cliente = { id: 'empresa', empleados } as unknown as ClienteCartera;
  return {
    clientes: [cliente],
    loading: false,
    origen: 'firestore',
    soloLectura,
    error: null,
    clientePorId: (id: string) => (id === 'empresa' ? cliente : null),
    guardarCliente: vi.fn(),
    borrarCliente: vi.fn(),
    guardarEmpleado,
    borrarEmpleado: vi.fn(),
    sembrar: vi.fn(),
    recargar: vi.fn(),
    empresa: { ...EMPRESA_POR_DEFECTO, parametros: { ...PARAMETROS_DE_LEY, dias_aguinaldo: 30 } },
    guardarEmpresa: vi.fn(),
  } as unknown as CarteraContextType;
}

beforeEach(() => {
  reintegrarPlantilla.mockReset();
  guardarEmpleado.mockClear();
});
afterEach(cleanup);

describe('el aviso está SIEMPRE, no sólo cuando se detecta el desfase', () => {
  /**
   * Detectar el desfase exige preguntarle al motor por cada empleado, y hacerlo
   * al montar Perfil dispararía N llamadas cada vez que alguien entra. El aviso
   * es barato; la comprobación la pide el operador.
   */
  it('dice que cambiar las prestaciones no recalcula el SBC existente', () => {
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    expect(screen.getByText(/no recalcula el SBC de quien ya está dado de alta/)).toBeTruthy();
  });

  it('y dice hacia dónde falla: las cuotas salen POR DEBAJO', () => {
    // La dirección importa. Subintegrar es la mala, y es la que ocurría.
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    expect(screen.getByText(/por debajo/)).toBeTruthy();
  });

  it('avisa que cada cambio es un movimiento ante el IMSS', () => {
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    expect(screen.getByText(/movimiento 07/)).toBeTruthy();
  });
});

describe('reintegrar guarda sólo a quien cambió', () => {
  it('escribe al que cambió y NO al que ya estaba integrado', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 2,
      cambios: [{ empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '524.65', nuevo: '540.00' }],
      fallidos: [],
      empleados: [
        { ...empleado('E-01'), salario_diario_integrado: '540.00' },
        empleado('E-02'),
      ],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Reintegrar la plantilla/ }));

    await waitFor(() => expect(guardarEmpleado).toHaveBeenCalledTimes(1));
    // `guardarEmpleado(clienteId, empleado)`: el segundo argumento.
    const [, guardado] = guardarEmpleado.mock.calls[0] as unknown as [string, EmpleadoCartera];
    expect(guardado).toMatchObject({
      empleado_no: 'E-01',
      salario_diario_integrado: '540.00',
    });
  });

  it('el reporte nombra a quien cambió, con el antes y el después', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 1,
      cambios: [{ empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '524.65', nuevo: '540.00' }],
      fallidos: [],
      empleados: [{ ...empleado('E-01'), salario_diario_integrado: '540.00' }],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Reintegrar la plantilla/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/PERSONA E-01/);
    expect(reporte.textContent).toMatch(/524\.65/);
    expect(reporte.textContent).toMatch(/540\.00/);
  });

  it('sin cambios lo dice, en vez de dejar la pantalla igual', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 2, cambios: [], fallidos: [],
      empleados: [empleado('E-01'), empleado('E-02')],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Reintegrar la plantilla/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/ninguno cambió/);
    expect(guardarEmpleado).not.toHaveBeenCalled();
  });

  it('los que fallaron se nombran, y se dice que quedaron como estaban', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 1, cambios: [],
      fallidos: [{
        empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '524.65', nuevo: '524.65',
        fallo: 'Salario diario inválido',
      }],
      empleados: [empleado('E-01')],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Reintegrar la plantilla/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/quedaron como estaban/);
    expect(reporte.textContent).toMatch(/Salario diario inválido/);
  });
});

describe('las guardas del botón', () => {
  it('sin empleados no se puede reintegrar', () => {
    render(<ReintegrarPlantilla cartera={cartera([])} />);
    const boton = screen.getByRole('button', { name: /Reintegrar la plantilla/ });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(boton);
    expect(reintegrarPlantilla).not.toHaveBeenCalled();
  });

  it('en sólo lectura tampoco: la cartera no es de este usuario', () => {
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')], true)} />);
    const boton = screen.getByRole('button', { name: /Reintegrar la plantilla/ });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(boton);
    expect(reintegrarPlantilla).not.toHaveBeenCalled();
  });

  it('un fallo del servicio se pinta como error y no se guarda nada', async () => {
    reintegrarPlantilla.mockRejectedValue(new Error('API caída'));
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Reintegrar la plantilla/ }));

    const alerta = await screen.findByRole('alert');
    expect(alerta.textContent).toMatch(/API caída/);
    expect(guardarEmpleado).not.toHaveBeenCalled();
  });
});
