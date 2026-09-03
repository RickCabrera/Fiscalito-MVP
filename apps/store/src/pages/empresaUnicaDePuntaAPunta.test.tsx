/**
 * El criterio de O-01, recorrido completo: **alta de empleado → nómina →
 * exportar, sin que exista el concepto de cartera.**
 *
 * POR QUÉ HACE FALTA UN TEST DE INTEGRACIÓN Y NO BASTAN LOS UNITARIOS
 * -------------------------------------------------------------------
 * Los demás archivos de O-01 miden piezas: que el sidebar no tenga Clientes,
 * que `/app/clientes` redirija, que el contexto proyecte una sola empresa. Los
 * tres pueden estar verdes con la cadena rota en medio — y el criterio de la
 * tarea no es ninguna de las tres piezas, es **la secuencia**.
 *
 * El eslabón que sólo se ve aquí: un empleado dado de alta tiene que llegar
 * hasta el cuerpo de `POST /nomina/calcular-periodo`. Entre el modal y el
 * request hay cuatro saltos —`CarteraProvider`, la proyección de la empresa,
 * `plantillaDeNomina` y el filtro de vinculados— y ninguno de los tests
 * unitarios los recorre juntos.
 *
 * SE USA EL `CarteraProvider` DE VERDAD
 * -------------------------------------
 * Lo único doblado es el almacén (`services/cartera`), con un diccionario en
 * memoria que se comporta como Firestore: guarda lo que le mandan y lo devuelve
 * al releer. Con un doble del contexto, la proyección de la empresa —que es lo
 * que O-01 construyó— no se ejercitaría en ningún lado.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { ClienteCartera, EmpleadoCartera } from '../services/carteraApi';

vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');

const perfil: UserProfile = {
  contributorType: 'contador',
  rfc: '', regimen: '', nombre: 'Operadora', actividad: '', cp: '',
  telefono: '', nombreNegocio: '', numEmpleados: '', nombreDespacho: '',
  onboardingComplete: true,
};

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-1', email: 'operadora@ejemplo.mx' }, loading: false }),
}));
vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfil, loading: false, setProfile: vi.fn() }),
}));

/**
 * El almacén: un Firestore de mentiras, con la misma forma.
 *
 * Guarda la ficha de la empresa y sus empleados por separado, igual que las
 * rutas reales (`users/{uid}/clientes/{id}` y `.../empleados/{id}`). Que sean
 * dos cosas separadas importa: es lo que hace visible el bug de "el documento
 * padre no existe y el empleado queda invisible".
 */
interface Almacen {
  ficha: Omit<ClienteCartera, 'empleados'> | null;
  empleados: EmpleadoCartera[];
}

const almacen: Almacen = { ficha: null, empleados: [] };

/** Lee la ficha sin que el estrechamiento del test la convierta en `never`. */
function fichaGuardada(): Almacen['ficha'] {
  return almacen.ficha;
}

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };

vi.mock('../services/cartera', () => ({
  cargarCartera: async () => ({
    clientes: almacen.ficha
      ? [{ ...almacen.ficha, empleados: [...almacen.empleados] } as ClienteCartera]
      : [],
    origen: 'firestore' as const,
    error: null,
  }),
  guardarCliente: vi.fn(async (_uid: string, c: Omit<ClienteCartera, 'empleados'>) => {
    almacen.ficha = { ...c };
  }),
  borrarCliente: vi.fn(),
  guardarEmpleado: vi.fn(async (_uid: string, _id: string, e: EmpleadoCartera) => {
    almacen.empleados = [...almacen.empleados.filter((x) => x.empleado_no !== e.empleado_no), e];
  }),
  borrarEmpleado: vi.fn(),
  sembrarDemo: vi.fn(),
}));

/** El motor del SBC vive en el backend; aquí sólo importa que el modal lo use. */
vi.mock('../services/carteraApi', async () => {
  const real = await vi.importActual<typeof import('../services/carteraApi')>(
    '../services/carteraApi',
  );
  return {
    ...real,
    integrarSBC: vi.fn(async () => ({
      factor: '1.0493',
      dias_vacaciones_aplicados: 12,
      sbc_sin_acotar: '524.65',
      sbc: '524.65',
      piso_aplicado: false,
      tope_aplicado: false,
      piso: '315.04',
      tope: '2932.75',
      fundamento: 'Arts. 27, 28 y 30 fr. I LSS',
    })),
  };
});

const cerrarPeriodo = vi.fn(async (...args: unknown[]) => ({
  llamada: args.length,
  exito: true,
  cliente: 'empresa',
  periodo: { inicio: PERIODO.inicio, fin: PERIODO.fin },
  incidencias: [
    {
      empleado_no: 'E-99', dias_periodo: 16, dias_laborables: 11, dias_trabajados: 11,
      faltas: 0, dias_ausentismo: 0, retardos: 0, dias_cotizados: 16, detalle: [],
    },
  ],
  empleados_desconocidos: [],
}));

const calcularNomina = vi.fn(async (...args: unknown[]) => ({
  llamada: args.length,
  cliente: 'empresa',
  periodo: PERIODO,
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'request',
  recibos: [
    {
      empleado_no: 'E-99', nombre: 'Persona De Prueba', sbc: '524.65',
      es_salario_minimo: false, dias_periodo: 16, dias_ausentismo: 0, dias_pagados: 16,
      percepciones: [], deducciones: [], otros_pagos: [],
      total_percepciones: '8000.00', total_deducciones: '900.00', neto: '7100.00',
      cuota_obrera: '200.00', cuota_patronal: '1500.00',
      absorbio_cuota_obrera: false, ramos: [],
    },
  ],
  porcion_mensual: {
    periodicidad: 'mensual', por_ramo: {}, total_patron: '1500.00',
    total_obrero: '200.00', total: '1700.00', empleados: 1,
  },
  porcion_bimestral: {
    periodicidad: 'bimestral', por_ramo: {}, total_patron: '0.00',
    total_obrero: '0.00', total: '0.00', empleados: 1,
  },
  advertencias: [],
}));

vi.mock('../services/nominaDemoApi', () => ({
  obtenerEventos: vi.fn(async () => ({ eventos: [] })),
  cerrarPeriodo: (...args: unknown[]) => cerrarPeriodo(...args),
  calcularNomina: (...args: unknown[]) => calcularNomina(...args),
  obtenerPlantillaDemo: vi.fn(),
}));

/** El PDF: interesa que se dispare con la nómina, no su contenido (eso es O-04). */
const guardarPDF = vi.fn((...args: unknown[]) => args.length);
vi.mock('../services/pdfExportNomina', () => ({
  exportarNominaPDF: (...args: unknown[]) => guardarPDF(...args),
}));

const { CarteraProvider } = await import('../context/CarteraContext');
const { default: EmpleadosPage } = await import('./EmpleadosPage');
const { default: NominaClientePage } = await import('./NominaClientePage');
const { ID_EMPRESA } = await import('../services/modoEmpresa');

/** `EmpleadosPage` y la nómina resuelven el cliente activo; aquí es la empresa. */
vi.mock('../context/clienteActivoStore', async () => {
  const { useCartera } = await import('../context/carteraStore');
  return {
    useClienteActivo: () => {
      const { clientes, loading } = useCartera();
      const c = clientes[0] ?? null;
      return {
        clientes: c ? [{ ...c, num_empleados: c.empleados.length }] : [],
        clienteId: c?.id ?? null,
        cliente: c ? { ...c, num_empleados: c.empleados.length } : null,
        loading, error: null, setClienteId: vi.fn(), recargar: vi.fn(),
      };
    },
  };
});

function conCartera(hijo: React.ReactNode) {
  return render(
    <MemoryRouter>
      <CarteraProvider>{hijo}</CarteraProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // La empresa YA está configurada: esta prueba mide el flujo de nómina, no la
  // captura de la ficha —eso lo mide `ConfiguracionEmpresa`—. Se escribe en el
  // almacén como si se hubiera guardado en Perfil.
  almacen.ficha = {
    id: ID_EMPRESA,
    nombre: 'Orca Ordorica Cristal Templado',
    giro: '',
    origen: 'propio',
    rfc: 'OOC010101AAA',
    registro_patronal: 'A1234567890',
    prima_riesgo: '0.0113065',
    clase_riesgo: 3,
    clave_periodicidad: '04',
    zona: 'general',
    periodo_sugerido: PERIODO,
  };
  almacen.empleados = [];
  guardarPDF.mockClear();
  cerrarPeriodo.mockClear();
  calcularNomina.mockClear();
});

afterEach(cleanup);

describe('O-01 de punta a punta · alta de empleado → nómina → exportar', () => {
  it('el empleado dado de alta llega al cuerpo del cálculo y sale en el PDF', async () => {
    // ── 1. Alta del empleado, por la pantalla ──────────────────────────────
    conCartera(<EmpleadosPage />);
    await waitFor(() => expect(screen.getByText('Nuevo empleado')).toBeTruthy());
    fireEvent.click(screen.getByText('Nuevo empleado'));

    fireEvent.change(screen.getByLabelText('Número de empleado *'), {
      target: { value: 'E-99' },
    });
    fireEvent.change(screen.getByLabelText('Nombre *'), {
      target: { value: 'Persona De Prueba' },
    });
    fireEvent.change(screen.getByLabelText('Salario diario *'), {
      target: { value: '500' },
    });
    // Sin `employeeNo` no entraría al cálculo (G-02), y este test mide que SÍ
    // entra: la exclusión de los no vinculados tiene sus propias pruebas.
    fireEvent.change(screen.getByLabelText('employeeNo del aparato'), {
      target: { value: 'E-99' },
    });

    // El botón dice "Dar de alta" cuando es un empleado nuevo, no "Guardar".
    const guardar = await screen.findByRole('button', { name: 'Dar de alta' });
    await waitFor(() => expect((guardar as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(guardar);

    await waitFor(() => expect(almacen.empleados).toHaveLength(1));
    expect(almacen.empleados[0].empleado_no).toBe('E-99');
    // El SDI guardado es el que devolvió el MOTOR, no uno calculado en el front.
    expect(almacen.empleados[0].salario_diario_integrado).toBe('524.65');

    // Y la ficha de la empresa sigue en pie: `asegurarEmpresa` no la pisó con
    // los defaults. Si lo hiciera, la prima de riesgo se habría perdido y el
    // cálculo saldría sin cuotas patronales.
    expect(almacen.ficha?.prima_riesgo).toBe('0.0113065');
    expect(almacen.ficha?.nombre).toBe('Orca Ordorica Cristal Templado');
    cleanup();

    // ── 2. La nómina, con ese empleado ─────────────────────────────────────
    conCartera(<NominaClientePage clienteId={ID_EMPRESA} />);
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());

    const cerrar = await screen.findByRole('button', { name: /Cerrar quincena/ });
    await waitFor(() => expect((cerrar as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(cerrar);

    /**
     * El periodo NO tiene checadas —`obtenerEventos` devuelve vacío— así que la
     * pantalla **pide confirmación** antes de cerrar (R-06): cerrar sin
     * checadas marca falta todo día laborable, y la nómina sale con sólo los
     * días de descanso pagados.
     *
     * Confirmarlo aquí, en vez de sembrar checadas para saltarse el diálogo, es
     * a propósito: deja medido que la guarda **sigue viva en modo empresa
     * única**. Si alguien la quitara, este `findByText` fallaría.
     */
    const confirmar = await screen.findByRole('button', { name: 'Cerrar de todos modos' });
    fireEvent.click(confirmar);

    await waitFor(() => expect(cerrarPeriodo).toHaveBeenCalled());
    // Al cierre viaja la llave del CHECADOR (G-02).
    expect(cerrarPeriodo.mock.calls[0][1]).toEqual(['E-99']);

    const calcular = await screen.findByRole('button', { name: /Calcular nómina/ });
    await waitFor(() => expect((calcular as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(calcular);

    await waitFor(() => expect(calcularNomina).toHaveBeenCalled());
    // EL ESLABÓN QUE SÓLO SE MIDE AQUÍ: la plantilla que viaja al motor es la
    // del empleado que se acaba de dar de alta, con su SDI y su zona.
    const plantilla = calcularNomina.mock.calls[0][4] as unknown as Array<Record<string, string>>;
    expect(plantilla).toHaveLength(1);
    expect(plantilla[0].empleado_no).toBe('E-99');
    expect(plantilla[0].salario_diario_integrado).toBe('524.65');
    // Y se le calcula a la EMPRESA, no a un cliente de demostración.
    expect(calcularNomina.mock.calls[0][0]).toBe(ID_EMPRESA);

    // ── 3. Exportar ────────────────────────────────────────────────────────
    const exportar = await screen.findByRole('button', { name: /Exportar PDF/ });
    await waitFor(() => expect((exportar as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(exportar);

    expect(guardarPDF).toHaveBeenCalledTimes(1);
    const [nomina, cliente] = guardarPDF.mock.calls[0];
    expect((nomina as { recibos: unknown[] }).recibos).toHaveLength(1);
    expect((cliente as { nombre: string }).nombre).toBe('Orca Ordorica Cristal Templado');
  });

  it('en TODO el recorrido no aparece la palabra cartera ni la lista de clientes', async () => {
    /**
     * El criterio dice "sin que exista el concepto de cartera". Esa mitad es
     * una afirmación negativa, y una afirmación negativa que nadie mide es la
     * que regresa por la puerta de atrás — es exactamente lo que pasó con la
     * migaja "Clientes" del encabezado de la nómina, que sobrevivió a todos los
     * unitarios de esta tarea y la cazó el test de rutas.
     */
    conCartera(<NominaClientePage clienteId={ID_EMPRESA} />);
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
    expect(document.body.textContent).not.toMatch(/cartera/i);
    expect(screen.queryByRole('link', { name: /Clientes/ })).toBeNull();
  });

  it('sin el documento de la empresa, el alta lo crea antes de escribir al empleado', async () => {
    /**
     * En Firestore un documento que sólo tiene subcolecciones **no aparece** al
     * listar la colección. Sin `asegurarEmpresa`, el primer empleado de una
     * cuenta nueva se guardaría bien y la cartera volvería vacía en la
     * siguiente lectura: el empleado existiría, invisible, y el operador lo
     * daría de alta otra vez.
     */
    almacen.ficha = null;
    almacen.empleados = [];

    conCartera(<EmpleadosPage />);
    await waitFor(() => expect(screen.getByText('Nuevo empleado')).toBeTruthy());
    fireEvent.click(screen.getByText('Nuevo empleado'));
    fireEvent.change(screen.getByLabelText('Número de empleado *'), { target: { value: 'E-01' } });
    fireEvent.change(screen.getByLabelText('Nombre *'), { target: { value: 'Primera Alta' } });
    fireEvent.change(screen.getByLabelText('Salario diario *'), { target: { value: '400' } });

    // El botón dice "Dar de alta" cuando es un empleado nuevo, no "Guardar".
    const guardar = await screen.findByRole('button', { name: 'Dar de alta' });
    await waitFor(() => expect((guardar as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(guardar);

    await waitFor(() => expect(almacen.empleados).toHaveLength(1));
    // Se lee por función: TypeScript estrechó `almacen.ficha` a `never` por el
    // `= null` de arriba y no sabe que un efecto de React la volvió a poblar.
    // Dentro de la función el flujo del test no la estrecha.
    const ficha = fichaGuardada();
    expect(ficha).not.toBeNull();
    expect(ficha?.id).toBe(ID_EMPRESA);
    // Y nace `propio`, no con un origen de demostración: si naciera `sintetico`
    // o `fixtures-s04`, el filtro de R-06 lo escondería y la cartera quedaría en
    // cero — con la nómina bloqueada por "cliente ajeno", que no es lo que pasó.
    expect(ficha?.origen).toBe('propio');
  });
});
