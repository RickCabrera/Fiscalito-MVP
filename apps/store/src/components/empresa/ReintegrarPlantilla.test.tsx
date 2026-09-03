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

  it('avisa que cada cambio es un movimiento ante el IMSS, suba o baje', () => {
    // Una BAJADA tambien es un 07, y es la direccion peligrosa. El copy no
    // puede encuadrar solo la subida.
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    expect(screen.getByText(/movimiento 07/)).toBeTruthy();
    expect(screen.getByText(/suba o baje/)).toBeTruthy();
  });

  it('y dice que la app NO puede generar ese aviso todavia', () => {
    // Es lo que convierte el segundo clic en una decision y no en un tramite.
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    expect(screen.getByText(/no lo puede generar/)).toBeTruthy();
  });
});

describe('son DOS pasos: calcular no escribe nada', () => {
  /**
   * La primera version decia en pantalla "aqui se ve quien cambia antes de
   * guardarlo" y guardaba en el mismo handler. El revisor de cierre cazo la
   * promesa incumplida.
   *
   * No es ceremonia: cada cambio de SBC es un movimiento 07 ante el IMSS que
   * esta app **no puede generar**, asi que quien pulsa Guardar adquiere un
   * tramite que va a presentar a mano. Tiene derecho a ver la lista primero.
   */
  const UNA_SUBIDA = {
    revisados: 2,
    cambios: [{ empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '524.65', nuevo: '540.00' }],
    bajarian: [],
    fallidos: [],
    empleados: [{ ...empleado('E-01'), salario_diario_integrado: '540.00' }, empleado('E-02')],
  };

  it('calcular ensena la lista y NO guarda', async () => {
    reintegrarPlantilla.mockResolvedValue(UNA_SUBIDA);
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/PERSONA E-01/);
    expect(reporte.textContent).toMatch(/no se ha guardado nada/);
    expect(guardarEmpleado).not.toHaveBeenCalled();
  });

  it('el boton de guardar aparece SOLO despues de calcular', async () => {
    reintegrarPlantilla.mockResolvedValue(UNA_SUBIDA);
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    expect(screen.queryByRole('button', { name: /Guardar/ })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    expect(await screen.findByRole('button', { name: /Guardar 1 cambio/ })).toBeTruthy();
  });

  it('el segundo clic guarda, y solo a quien cambio', async () => {
    reintegrarPlantilla.mockResolvedValue(UNA_SUBIDA);
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Guardar 1 cambio/ }));

    await waitFor(() => expect(guardarEmpleado).toHaveBeenCalledTimes(1));
    const [, guardado] = guardarEmpleado.mock.calls[0] as unknown as [string, EmpleadoCartera];
    expect(guardado).toMatchObject({ empleado_no: 'E-01', salario_diario_integrado: '540.00' });
  });

  it('sin nada que cambiar no ofrece guardar', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 2, cambios: [], bajarian: [], fallidos: [],
      empleados: [empleado('E-01'), empleado('E-02')],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01'), empleado('E-02')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/ninguno cambia/);
    expect(screen.queryByRole('button', { name: /Guardar/ })).toBeNull();
  });
});

describe('las bajadas se ensenan distinto, y no se pueden guardar', () => {
  /**
   * Una bajada tambien es un movimiento 07, y es **la direccion peligrosa**:
   * subintegra las cuotas. En una lista plana un 540.00 -> 524.65 se ve igual
   * que una subida.
   */
  const UNA_BAJADA = {
    revisados: 1, cambios: [],
    bajarian: [{ empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '540.00', nuevo: '524.65' }],
    fallidos: [],
    empleados: [empleado('E-01')],
  };

  it('se dicen aparte, con que NO se van a guardar', async () => {
    reintegrarPlantilla.mockResolvedValue(UNA_BAJADA);
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/NO se van a guardar/);
    expect(reporte.textContent).toMatch(/subintegra/);
  });

  it('no aparece boton de guardar cuando lo unico que hay son bajadas', async () => {
    reintegrarPlantilla.mockResolvedValue(UNA_BAJADA);
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await screen.findByRole('status');
    expect(screen.queryByRole('button', { name: /Guardar/ })).toBeNull();
  });
});

describe('los que el motor rechazo', () => {
  it('se nombran, y se dice que quedaron como estaban', async () => {
    reintegrarPlantilla.mockResolvedValue({
      revisados: 1, cambios: [], bajarian: [],
      fallidos: [{
        empleadoNo: 'E-01', nombre: 'PERSONA E-01', anterior: '524.65', nuevo: '524.65',
        fallo: 'Salario diario invalido',
      }],
      empleados: [empleado('E-01')],
    });
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));

    const reporte = await screen.findByRole('status');
    expect(reporte.textContent).toMatch(/quedaron como estaban/);
    expect(reporte.textContent).toMatch(/Salario diario invalido/);
  });
});

describe('las guardas del boton', () => {
  it('sin empleados no se puede calcular', () => {
    render(<ReintegrarPlantilla cartera={cartera([])} />);
    const boton = screen.getByRole('button', { name: /Calcular/ });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(boton);
    expect(reintegrarPlantilla).not.toHaveBeenCalled();
  });

  it('en solo lectura tampoco: la cartera no es de este usuario', () => {
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')], true)} />);
    const boton = screen.getByRole('button', { name: /Calcular/ });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(boton);
    expect(reintegrarPlantilla).not.toHaveBeenCalled();
  });

  it('un fallo del servicio se pinta como error y no se guarda nada', async () => {
    reintegrarPlantilla.mockRejectedValue(new Error('API caida'));
    render(<ReintegrarPlantilla cartera={cartera([empleado('E-01')])} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));

    const alerta = await screen.findByRole('alert');
    expect(alerta.textContent).toMatch(/API caida/);
    expect(guardarEmpleado).not.toHaveBeenCalled();
  });
});
