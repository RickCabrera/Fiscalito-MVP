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
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
const escrituras = { guardados: [] as DispositivoChecador[], borrados: [] as string[] };
vi.mock('../services/dispositivosFirestore', () => ({
  listarDispositivos: async () => dispositivosGuardados.actual,
  // El doble ESCRIBE en el mismo almacén que lee: así "guardar y ver" se puede
  // medir de verdad. Con un doble que sólo dice que sí, borrar el `recargar()`
  // de la página dejaba las pruebas en verde y el criterio de R-04 —"doy de
  // alta un dispositivo y VEO qué empleados están enrolados"— sin cubrir.
  guardarDispositivo: async (_uid: string, _cliente: string, d: DispositivoChecador) => {
    escrituras.guardados.push(d);
    dispositivosGuardados.actual = [...dispositivosGuardados.actual, { ...d, id: 'nuevo-id' }];
    return 'nuevo-id';
  },
  borrarDispositivo: async (_uid: string, _cliente: string, id: string) => {
    escrituras.borrados.push(id);
    dispositivosGuardados.actual = dispositivosGuardados.actual.filter((x) => x.id !== id);
  },
}));

// El endpoint REAL del adaptador. Se stubbea la red, no la lógica del cruce.
const cruceFalla = { actual: false };
/** Deja la consulta del checador colgada, para poder mirar la ventana intermedia. */
const cruceColgado = { actual: false };
vi.mock('../services/nominaDemoApi', () => ({
  CLIENTE_DEMO: 'demo',
  obtenerEventos: async () => {
    if (cruceColgado.actual) return new Promise(() => {});
    if (cruceFalla.actual) throw new Error('API caída');
    return { eventos: eventos.actual };
  },
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
  cruceFalla.actual = false;
  cruceColgado.actual = false;
  escrituras.guardados = [];
  escrituras.borrados = [];
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

describe('DispositivosPage · "no pude preguntar" no es "no ha checado"', () => {
  it('con el checador incontactable NO marca a nadie sin checadas', async () => {
    // El defecto que un revisor encontró: `.catch(() => setChecando(new Set()))`
    // convertía una API caída en la afirmación, en ámbar, de que nadie está
    // checando — sobre gente que sí lo está. Es el MISMO defecto que ya se
    // arregló para el aviso de "sin aparato" y que aquí quedó abierto.
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7'] })];
    cruceFalla.actual = true;
    pintar();

    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).queryByText(/sin checadas/)).toBeNull();
  });

  it('y lo DICE, en vez de callar que el cruce no se pudo hacer', async () => {
    // Callarlo dejaría una pantalla que se ve completa y omite la mitad de su
    // información sin señal alguna.
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7'] })];
    cruceFalla.actual = true;
    pintar();

    const aviso = await waitFor(() =>
      screen.getAllByRole('alert').find((a) => a.textContent?.includes('No se pudo consultar')),
    );
    expect(aviso, 'no salió el aviso de cruce fallido').toBeTruthy();
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

describe('DispositivosPage · el cableado con el modal (el "veo" de R-04)', () => {
  it('dar de alta un dispositivo lo hace APARECER en la lista', async () => {
    // El criterio literal de R-04 es "doy de alta un dispositivo y VEO qué
    // empleados están enrolados". El test del modal prueba que `onGuardar` se
    // llama; sin éste, nada probaba que la página hiciera algo con eso —borrar
    // el `recargar()` dejaba las 421 en verde y la lista sin refrescar.
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    pintar();
    await waitFor(() => expect(screen.getByText(/no tiene dispositivos/)).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /Nuevo dispositivo/ }));
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: 'Entrada planta' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /Dar de alta/ }));

    // Y aparece en la LISTA, no sólo en el almacén.
    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());
    expect(escrituras.guardados[0].employee_nos).toEqual(['7']);
    // "veo qué empleados están enrolados": el nombre de la persona, ahí.
    expect(screen.getByText('ANA LOPEZ')).toBeTruthy();
  });

  it('dar de baja lo hace DESAPARECER de la lista', async () => {
    dispositivosGuardados.actual = [disp()];
    pintar();
    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());

    fireEvent.click(screen.getByLabelText(/Dar de baja/));
    fireEvent.click(screen.getByRole('button', { name: /Sí, dar de baja/ }));

    await waitFor(() => expect(screen.queryByText('Entrada planta')).toBeNull());
    expect(escrituras.borrados).toEqual(['d1']);
  });

  it('editar un aparato con serie NO choca consigo mismo', async () => {
    // `serialesEnUso` excluye al que se edita. Sin esa exclusión, editar
    // cualquier aparato que tenga serie es imposible: el botón nunca se
    // habilita porque el serial "ya está en uso"... por él mismo. El docstring
    // de `validarDispositivo` explica la exclusión; quien la implementa es el
    // llamador, y el llamador no tenía prueba.
    dispositivosGuardados.actual = [disp({ serial: 'ABC123' })];
    pintar();
    await waitFor(() => expect(screen.getByText('Entrada planta')).toBeTruthy());

    fireEvent.click(screen.getByLabelText(/Editar/));
    expect(screen.getByRole('button', { name: /^Guardar$/ })).toHaveProperty('disabled', false);
  });
});

describe('DispositivosPage · cambiar de cliente no arrastra el cruce anterior', () => {
  it('el cruce del cliente anterior NO se pinta sobre el nuevo', async () => {
    // TERCERA aparición del mismo defecto en este archivo. Los dos efectos
    // corren en paralelo y Firestore suele contestar antes que la red, así que
    // sin la compuerta `para` las tarjetas del cliente nuevo se pintan contra
    // el `checando` del anterior.
    //
    // EL MONTAJE IMPORTA: para que el arrastre se VEA, el cruce viejo tiene que
    // afirmar algo FALSO del cliente nuevo. Cliente A: nadie está checando
    // (conjunto vacío). Cliente B: su gente sí checa. Si el conjunto vacío de A
    // sobrevive al cambio, la pantalla marca "sin checadas" a quien sí checa.
    empleadosDelCliente.actual = [emp({ employee_no: '7' })];
    dispositivosGuardados.actual = [disp({ employee_nos: ['7'] })];
    eventos.actual = []; // en el cliente A nadie ha checado
    const { rerender } = pintar();

    await waitFor(() => {
      const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
      expect(within(chip).getByText(/sin checadas/)).toBeTruthy();
    });

    // Cambia el cliente activo, y el checador del nuevo todavía no contesta:
    // ésa es exactamente la ventana donde vivía el bug.
    clienteActivo.actual = { clienteId: 'taller', cliente: { nombre: 'Taller' } };
    cruceColgado.actual = true;
    rerender(
      <MemoryRouter>
        <DispositivosPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Taller')).toBeTruthy());
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(
      within(chip).queryByText(/sin checadas/),
      'se está afirmando "sin checadas" del cliente nuevo con el cruce del anterior',
    ).toBeNull();
  });
});
