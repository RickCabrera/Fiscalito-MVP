/**
 * La pantalla de dispositivos, medida por lo que resuelve. (R-04, R-05)
 *
 * NO SE PRUEBA "QUE MONTE"
 * ------------------------
 * Un test que afirmara que `/app/dispositivos` renderiza pasaría con una página
 * que devuelve un `<div/>` vacío. Lo que hay que fijar es que **resuelve el
 * cliente activo**: o enseña los aparatos de ESE cliente, o pide que se elija
 * uno. Sin eso, la pantalla podría caer en un default silencioso y el selector
 * del header afirmaría un cliente mientras la pantalla enseña los aparatos de
 * otro — el bloqueante de E-02, otra vez.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { DispositivoChecador } from '../services/dispositivosApi';
import type { EmpleadoCartera } from '../services/carteraApi';

const clienteActivo = {
  actual: { clienteId: 'demo' as string | null, cliente: { nombre: 'Cliente Demo' } as { nombre: string } | null },
};
const dispositivosGuardados = { actual: [] as DispositivoChecador[] };
const empleadosDelCliente = { actual: [] as EmpleadoCartera[] };
const eventos = { actual: [] as { empleado_no: string }[] };

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [],
    clienteId: clienteActivo.actual.clienteId,
    cliente: clienteActivo.actual.cliente,
    loading: false,
    error: null,
    setClienteId: vi.fn(),
    recargar: vi.fn(),
  }),
}));

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        origen: 'firestore',
        soloLectura: false,
        // Cliente completo y no `{ empleados }` a secas: el tipo del contexto
        // es `ClienteCartera | null`, y un doble más flojo que el contrato deja
        // pasar una pantalla que lea un campo que en producción sí existe.
        clientePorId: () => ({
          id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'sintetico',
          prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04',
          zona: 'general',
          periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
          empleados: empleadosDelCliente.actual,
        }),
      }),
  };
});

// Funciones PLANAS, no `vi.fn(impl)`: `src/test/setup.ts` corre
// `vi.restoreAllMocks()` en cada `afterEach`, y eso le quita la implementación
// a un `vi.fn` de una factoría de `vi.mock`. El síntoma era desconcertante —los
// tres primeros tests pasaban y los de después veían la pantalla sin aparatos—
// porque el doble se vaciaba a mitad de la suite, no al principio.
vi.mock('../services/dispositivosFirestore', () => ({
  listarDispositivos: async () => dispositivosGuardados.actual,
  guardarDispositivo: async () => 'nuevo-id',
  borrarDispositivo: async () => undefined,
}));

// El endpoint REAL del adaptador. Se stubbea la red, no la lógica del cruce.
vi.mock('../services/nominaDemoApi', () => ({
  CLIENTE_DEMO: 'demo',
  obtenerEventos: async () => ({ eventos: eventos.actual }),
}));

const { default: DispositivosPage } = await import('./DispositivosPage');

function emp(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: '', salario_diario: '316.00',
    salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: 'E-01', enrolamiento: 'enrolado', ...over,
  };
}

function disp(over: Partial<DispositivoChecador> = {}): DispositivoChecador {
  return {
    id: 'd1', nombre: 'Entrada planta', ip: '192.168.1.64', puerto: 80,
    marca: 'Hikvision', modelo: 'DS-K1T321MFWX', serial: 'ABC123',
    employee_nos: [], notas: '', ...over,
  };
}

function pintar() {
  return render(
    <MemoryRouter>
      <DispositivosPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  clienteActivo.actual = { clienteId: 'demo', cliente: { nombre: 'Cliente Demo' } };
  dispositivosGuardados.actual = [];
  empleadosDelCliente.actual = [];
  eventos.actual = [];
});
afterEach(cleanup);

describe('DispositivosPage · resuelve el cliente activo (R-05)', () => {
  it('sin cliente activo PIDE uno, no cae en un default', () => {
    // Si aterrizara en `demo`, el selector del header diría un cliente y la
    // pantalla enseñaría los aparatos de otro.
    clienteActivo.actual = { clienteId: null, cliente: null };
    pintar();

    expect(screen.getByText(/Elige un cliente primero/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Nuevo dispositivo/ })).toBeNull();
  });

  it('con cliente activo enseña los aparatos DE ESE cliente, nombrándolo', () => {
    dispositivosGuardados.actual = [disp()];
    pintar();

    // El nombre del cliente en pantalla es lo que hace verificable que la
    // pantalla y el selector hablan del mismo.
    expect(screen.getByText('Cliente Demo')).toBeTruthy();
    return waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());
  });
});

describe('DispositivosPage · estado vacío', () => {
  it('un cliente sin aparatos lo dice y ofrece el alta', async () => {
    pintar();
    await waitFor(() =>
      expect(screen.getByText(/no tiene dispositivos registrados/)).toBeTruthy(),
    );
    expect(screen.getByRole('button', { name: /Nuevo dispositivo/ })).toBeTruthy();
  });
});

describe('DispositivosPage · los cruces, que son el valor de la pantalla', () => {
  it('marca al enrolado-fantasma: checará y no habrá a quién atribuirle', async () => {
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7', '99'] })];
    pintar();

    // Se espera a que los aparatos hayan CARGADO antes de mirar los avisos:
    // antes de eso la pantalla no tiene con qué cruzar y no afirma nada.
    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());
    const aviso = screen
      .getAllByRole('alert')
      .find((a) => a.textContent?.includes('no está en la cartera'));
    expect(aviso, 'no salió el aviso de enrolado-fantasma').toBeTruthy();
    expect(aviso?.textContent).toContain('99');
    // Y NO acusa al que sí existe: invertir el cruce lo delataría aquí.
    expect(aviso?.textContent).not.toContain('ANA LOPEZ');
  });

  it('marca al vinculado que no está en ningún aparato', async () => {
    // Entra al cálculo, no va a checar nunca, y sale con falta en todos los
    // días laborables: nómina completa y creíble con menos días pagados.
    empleadosDelCliente.actual = [emp({ nombre: 'BEATRIZ RUIZ', employee_no: '8' })];
    dispositivosGuardados.actual = [disp({ employee_nos: [] })];
    pintar();

    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());
    const aviso = screen
      .getAllByRole('alert')
      .find((a) => a.textContent?.includes('ningún aparato'));
    expect(aviso, 'no salió el aviso de vinculado sin aparato').toBeTruthy();
    expect(aviso?.textContent).toContain('BEATRIZ RUIZ');
  });

  it('no marca nada cuando todo cuadra', async () => {
    // La simétrica: sin ella, avisos que se pintaran siempre pasarían los dos
    // tests de arriba y volverían inútil la pantalla por saturación.
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7'] })];
    eventos.actual = [{ empleado_no: '7' }];
    pintar();

    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());

    // Se consultan los AVISOS (`role="alert"`), no el texto suelto de la
    // página. La nota al pie que explica la limitación del adaptador contiene
    // las mismas palabras —"en ningún aparato", "sin checadas"— y una búsqueda
    // por texto la capturaba: el test fallaba por su propio copy explicativo,
    // no por un aviso indebido.
    expect(screen.queryAllByRole('alert')).toEqual([]);

    // Y la insignia "sin checadas" vive en la ficha del enrolado, así que se
    // busca ahí y no en toda la página.
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).queryByText(/sin checadas/)).toBeNull();
  });

  it('dice quién no está checando, con el endpoint real del adaptador', async () => {
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7'] })];
    eventos.actual = []; // nadie ha checado
    pintar();

    // Dentro de la ficha del enrolado: `getByText` sobre toda la página
    // encontraba dos coincidencias —la insignia y la nota al pie— y reventaba
    // por ambigüedad, no por ausencia.
    await waitFor(() => expect(screen.getByText('ANA LOPEZ')).toBeTruthy());
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).getByText(/sin checadas/)).toBeTruthy();
  });
});

describe('DispositivosPage · no afirma lo que no puede saber', () => {
  it('avisa que las checadas no identifican el aparato', async () => {
    // `EventoChecada` no trae la identidad del dispositivo. Sin esta nota, "sin
    // checadas" se leería como "este equipo está apagado", que es una
    // conclusión que el dato no sostiene.
    dispositivosGuardados.actual = [disp()];
    pintar();

    await waitFor(() =>
      expect(screen.getByText(/no traen la identidad del dispositivo/)).toBeTruthy(),
    );
  });
});
