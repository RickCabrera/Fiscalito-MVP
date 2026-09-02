/**
 * Lista de clientes del despacho (E-02).
 *
 * Cubre los tres estados que la pantalla tiene que saber pintar —cargando,
 * error, vacío— porque los tres se ven igual de mal si se dejan sin manejar: un
 * área en blanco enfrente de alguien.
 *
 * Y cubre que la lista **distinga el caso real del sintético**: enseñar los tres
 * clientes como si fueran iguales presentaría datos inventados con el mismo peso
 * que los reales.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ClienteCartera, EmpleadoCartera } from '../services/carteraApi';

// R-06: las pantallas leen la cuenta para decidir si ven los datos de
// demostración. En jsdom `import.meta.env.DEV` es `true`, así que el doble
// basta con existir: la cuenta cuenta como de desarrollo y los tests de la
// demo siguen midiendo lo mismo que medían.
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

/**
 * G-03: **la LISTA sale de la cartera**, no del contexto del cliente activo.
 * Pintarla desde el backend hacía que un cliente recién capturado no apareciera
 * nunca, sin error y sin mensaje — por eso este doble trae clientes de verdad y
 * no el vacío por default.
 */
function emp(n: string): EmpleadoCartera {
  return {
    empleado_no: n, nombre: `EMPLEADO ${n}`, puesto: '', salario_diario: '316.00',
    salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: n, enrolamiento: 'enrolado',
  };
}

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null };

const CARTERA: ClienteCartera[] = [
  {
    id: 'demo', nombre: 'Servicios Administrativos Integrales',
    giro: 'Servicios administrativos', origen: 'fixtures-s04',
    prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04',
    zona: 'general', periodo_sugerido: PERIODO,
    empleados: Array.from({ length: 9 }, (_, i) => emp(`E-0${i + 1}`)),
  },
  {
    id: 'cafeteria', nombre: 'Cafeteria La Estacion', giro: 'Alimentos y bebidas',
    origen: 'sintetico', prima_riesgo: '0.0113065', clase_riesgo: 2,
    clave_periodicidad: '04', zona: 'general', periodo_sugerido: PERIODO,
    empleados: Array.from({ length: 4 }, (_, i) => emp(`C-0${i + 1}`)),
  },
];

const navigate = vi.fn();
const setClienteId = vi.fn();
const recargar = vi.fn();
const estado = {
  clientes: CARTERA,
  clienteId: 'demo' as string | null,
  loading: false,
  error: null as string | null,
};

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes: estado.clientes,
        loading: estado.loading,
        // El error y el reintento son de la CARTERA, que es la fuente de lo que
        // se pinta. Antes colgaban del cliente activo, así que `cartera.error`
        // no se renderizaba en ningún lado y un fallo del proveedor se veía
        // como "la cartera está vacía — revisa que la API esté corriendo".
        error: estado.error,
        recargar,
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) => estado.clientes.find((c) => c.id === id) ?? null,
      }),
  };
});

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [],
    clienteId: estado.clienteId,
    cliente: null,
    loading: estado.loading,
    error: estado.error,
    setClienteId,
    recargar,
  }),
}));

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...real, useNavigate: () => navigate };
});

const { default: ClientesPage } = await import('./ClientesPage');

function montar() {
  return render(<MemoryRouter><ClientesPage /></MemoryRouter>);
}

afterEach(() => {
  // En `afterEach` y no al final del cuerpo: si una aserción revienta antes,
  // `DEV=false` se filtra a los tests siguientes del archivo.
  vi.unstubAllEnvs();
  estado.clientes = CARTERA;
  estado.clienteId = 'demo';
  estado.loading = false;
  estado.error = null;
  navigate.mockClear();
  setClienteId.mockClear();
  recargar.mockClear();
  cleanup();
});

describe('lista de clientes', () => {
  it('pinta la cartera con giro, empleados y prima', () => {
    montar();

    expect(screen.getByText('Servicios Administrativos Integrales')).toBeTruthy();
    expect(screen.getByText('Cafeteria La Estacion')).toBeTruthy();
    expect(screen.getByText('9')).toBeTruthy();
    expect(screen.getByText('4')).toBeTruthy();
    // La prima viaja como fracción y se muestra como porcentaje.
    expect(screen.getByText('0.54355 %')).toBeTruthy();
    expect(screen.getByText('1.13065 %')).toBeTruthy();
  });

  it('distingue el caso real anonimizado de los datos sintéticos', () => {
    montar();
    expect(screen.getByText(/Caso real anonimizado/)).toBeTruthy();
    expect(screen.getByText(/Datos sintéticos/)).toBeTruthy();
  });

  it('marca cuál es el cliente activo', () => {
    estado.clienteId = 'cafeteria';
    montar();
    expect(screen.getByText('ACTIVO')).toBeTruthy();
  });

  it('abrir un cliente lo activa y navega a su ficha', () => {
    montar();
    fireEvent.click(screen.getByText('Cafeteria La Estacion'));

    expect(setClienteId).toHaveBeenCalledWith('cafeteria');
    expect(navigate).toHaveBeenCalledWith('/app/clientes/cafeteria');
  });
});

describe('estados que no son la lista feliz', () => {
  it('mientras carga lo dice, en vez de enseñar una lista vacía', () => {
    estado.loading = true;
    estado.clientes = [];
    montar();

    expect(screen.getByText(/Cargando la cartera/)).toBeTruthy();
    expect(screen.queryByText(/La cartera está vacía/)).toBeNull();
  });

  it('con error lo enseña y ofrece reintentar', () => {
    estado.error = 'No se pudo cargar la cartera: HTTP 500';
    estado.clientes = [];
    montar();

    expect(screen.getByText(/No se pudo cargar la cartera/)).toBeTruthy();
    fireEvent.click(screen.getByText('Reintentar'));
    expect(recargar).toHaveBeenCalledTimes(1);
  });

  it('una cartera vacía OFRECE crear el primer cliente', () => {
    // R-06 cambió el copy y la salida. Antes decía "La cartera está vacía · el
    // servicio respondió sin clientes, revisa que la API esté corriendo": un
    // diagnóstico equivocado —lo único que pasa es que la cuenta es nueva— y
    // sin ninguna acción. Ahora dice lo que hay y da el botón.
    estado.clientes = [];
    montar();

    expect(screen.getByText(/Aún no tienes clientes/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Crear el primer cliente/ })).toBeTruthy();
    // Y NO culpa a la API de algo que no pasó.
    expect(screen.queryByText(/Revisa que la API esté corriendo/)).toBeNull();
  });

  it('con error no dice además que la cartera está vacía', () => {
    estado.error = 'No se pudo leer tu cartera: Missing or insufficient permissions.';
    estado.clientes = [];
    montar();
    expect(screen.queryByText(/Aún no tienes clientes/)).toBeNull();
  });

  it('una cuenta NORMAL no tiene el botón de sembrar la demostración', () => {
    /**
     * La mutación que sobrevivía: quitar el gate `cuentaDeDesarrollo` del botón
     * dejaba las 442 pruebas en verde. La causa está en el doble de este mismo
     * archivo — en jsdom `import.meta.env.DEV` es `true`, así que **todos** los
     * tests de esta pantalla corren como cuenta de desarrollo y la rama de
     * producción no se ejercía en ningún lado.
     *
     * Sin el gate, una cuenta cualquiera puede copiarse a su Firestore el
     * salario de nueve trabajadores de un tercero con un clic.
     */
    vi.stubEnv('DEV', false);
    estado.clientes = [];
    montar();

    expect(screen.queryByRole('button', { name: /clientes de demostración/i })).toBeNull();
    // Pero sí puede crear el suyo: el vacío no es un callejón.
    expect(screen.getByRole('button', { name: /Crear el primer cliente/ })).toBeTruthy();
  });

  it('una cuenta de desarrollo SÍ lo tiene', () => {
    // La mitad simétrica: sin ella, un gate que bloqueara siempre pasaría el
    // test de arriba y dejaría la demo sin forma de sembrarse.
    estado.clientes = [];
    montar();
    expect(screen.getByRole('button', { name: /clientes de demostración/i })).toBeTruthy();
  });

  it('un fallo de lectura NO enseña clientes de demostración', () => {
    // La aserción que mata la regresión de R-06: antes, un fallo al leer la
    // cartera se sustituía por el catálogo del backend, y el contador veía
    // tres clientes que no son suyos con aspecto de serlo.
    estado.error = 'No se pudo leer tu cartera: Missing or insufficient permissions.';
    estado.clientes = [];
    montar();

    expect(screen.getByText(/No se pudo leer tu cartera/)).toBeTruthy();
    for (const ajeno of ['Servicios Administrativos Integrales', 'Cafetería La Estación', 'Taller Mecánico Nogal']) {
      expect(screen.queryByText(ajeno), `apareció ${ajeno}`).toBeNull();
    }
  });
});
