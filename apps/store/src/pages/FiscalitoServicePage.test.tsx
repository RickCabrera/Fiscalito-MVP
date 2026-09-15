/**
 * Fiscalito y las cuentas de despacho (E-01 → E-07 → T1).
 *
 * LA HISTORIA, PORQUE ESTE ARCHIVO YA AFIRMÓ LO CONTRARIO DOS VECES
 * -----------------------------------------------------------------
 * E-01 le dejaba al contador UN tab: el calendario de sus propias obligaciones
 * como persona física (§D21, provisional). E-05 dejó de pedirle RFC y régimen
 * —y quitó del perfil el único lugar donde capturarlos—, así que ese tab quedó
 * muerto: `CalendarioTab` corta en seco sin esos dos campos. E-07 lo resolvió
 * de frente sacándolo de la pantalla: un despacho no tenía NINGUNA pantalla de
 * Fiscalito, y la que pedía por URL lo mandaba a `/app/calendario`.
 *
 * **T1 no revive lo que E-07 mató.** Lo que E-07 quitó —el Fiscalito PROPIO del
 * despacho, sin RFC ni régimen con qué calcularlo— sigue sin existir, y su
 * `/app/calendario` sigue siendo el patronal de la cartera. Lo que T1 agrega es
 * otro sujeto: el Fiscalito **del cliente activo**, con el régimen que ese
 * cliente sí tiene capturado.
 *
 * Lo que este archivo protege, entonces:
 *  1. Que el despacho llegue a la pantalla y vea los tabs de SU CLIENTE.
 *  2. Que un cliente 626 no reciba DIOT ni Retenciones.
 *  3. Que sin cliente elegido no haya pantalla en blanco.
 *  4. Que el contribuyente no haya perdido nada.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';
import { ClienteActivoContext } from '../context/clienteActivoStore';
import { modoDespacho } from '../test/modoDespacho';

/**
 * MODO DESPACHO. T1 lo dejó como default de la app, pero este archivo lo
 * declara igual: es donde vive la diferencia que mide —en modo empresa única el
 * redirect de E-07 se conserva— y heredarlo del ambiente es justo lo que O-01
 * vino a quitar.
 */
modoDespacho();

const perfilBase: UserProfile = {
  contributorType: 'contador',
  rfc: 'XAXX010101000',
  regimen: '612',
  nombre: 'Contadora Demo',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  nombreDespacho: 'Despacho Demo',
  onboardingComplete: true,
};

const perfilMock = { actual: perfilBase };

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false }),
}));

vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
// T1: el doble creció porque el DESPACHO ya no se sale por un redirect — ahora
// monta los tabs de verdad, y `PreDeclaracionTab` pide el acumulado del periodo
// anterior al montar. Hasta E-07 este archivo nunca llegaba a pintarlo.
vi.mock('../services/declaracionesHistory', () => ({
  guardarDeclaracion: vi.fn(),
  obtenerHistorial: vi.fn(async () => []),
  obtenerEstadisticas: vi.fn(),
  obtenerAcumuladoAnterior: vi.fn(async () => null),
  obtenerISRPagadoAnterior: vi.fn(async () => null),
}));

// El tab de calendario pega a la API al montar; aquí solo importa qué tabs se
// pintan. El resto del módulo (tipoParaCalendario incluido) queda real.
vi.mock('../services/fiscalAgentApi', async () => {
  const real = await vi.importActual<typeof import('../services/fiscalAgentApi')>('../services/fiscalAgentApi');
  return { ...real, obtenerCalendario: vi.fn(async () => ({ obligaciones: [] })) };
});

const { default: FiscalitoServicePage } = await import('./FiscalitoServicePage');
// El tab de pre-declaracion (el del contribuyente) usa useAgent.
const { AgentProvider } = await import('../agent/AgentContext');

/** Sonda del query string vivo. `window.location` no sirve con MemoryRouter. */
function SondaQuery() {
  return <span data-testid="query">{useLocation().search}</span>;
}

const CLIENTE_612: ClienteResumen = {
  id: 'taller', nombre: 'Taller Nogal', giro: 'Reparación', origen: 'sintetico',
  num_empleados: 12, prima_riesgo: '0.0259840', clase_riesgo: 3,
  clave_periodicidad: '04', zona: 'general', regimen: '612',
};

const CLIENTE_626: ClienteResumen = { ...CLIENTE_612, id: 'resico', nombre: 'Despacho Sur', regimen: '626' };

/** Cliente dado de alta ANTES de que T1 abriera el campo: sin régimen. */
const CLIENTE_SIN_REGIMEN: ClienteResumen = { ...CLIENTE_612, id: 'viejo', nombre: 'Cliente Viejo', regimen: undefined };

/**
 * Doble del contexto del cliente activo.
 *
 * `cliente: null` es el caso "el despacho todavía no elige", que no es lo mismo
 * que "no hay proveedor": esta pantalla también la monta un contribuyente, que
 * no tiene cartera ni proveedor, y ese caso se cubre montando SIN el wrapper.
 */
function conCliente(cliente: ClienteResumen | null, clientes: ClienteResumen[] = cliente ? [cliente] : []) {
  return {
    clientes, clienteId: cliente?.id ?? null, cliente,
    loading: false, error: null, setClienteId: vi.fn(), recargar: vi.fn(),
  };
}

function montar(ruta = '/app/store/fiscalito/use', cartera: ReturnType<typeof conCliente> | null = null) {
  const arbol = (
    <AgentProvider>
      <SondaQuery />
      <Routes>
        <Route path="/app/store/fiscalito/use" element={<FiscalitoServicePage />} />
        <Route path="/app/calendario" element={<div>calendario patronal</div>} />
        <Route path="/app/clientes" element={<div>cartera</div>} />
      </Routes>
    </AgentProvider>
  );
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      {cartera
        ? <ClienteActivoContext.Provider value={cartera}>{arbol}</ClienteActivoContext.Provider>
        : arbol}
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  cleanup();
});

describe('FiscalitoServicePage — cuenta de despacho (T1)', () => {
  it('con un cliente 612 activo ve TODOS los tabs', () => {
    montar('/app/store/fiscalito/use', conCliente(CLIENTE_612));

    for (const tab of ['Pre-declaración', 'Calendario fiscal', 'Comparar regímenes',
      'DIOT', 'Retenciones', 'Multi-periodo', 'Estado de cuenta']) {
      expect(screen.getByText(tab), tab).toBeTruthy();
    }
  });

  it('el encabezado NOMBRA al cliente y su régimen', () => {
    /**
     * Sin esto, dos clientes con los mismos tabs pintan pantallas idénticas y el
     * contador no tiene cómo saber sobre cuál está trabajando. Es el modo de
     * falla que E-03 cerró en la nómina, en la pantalla de al lado.
     */
    montar('/app/store/fiscalito/use', conCliente(CLIENTE_612));

    expect(screen.getByText('Taller Nogal · régimen 612')).toBeTruthy();
  });

  it('EL CASO QUE VALE LA TAREA: un cliente 626 no ve DIOT ni Retenciones', () => {
    // El corte lo heredó T1 de E-01 y está pendiente de confirmar con la
    // contadora (§D30). Lo que este test fija NO es la regla fiscal: es que el
    // régimen del cliente SE APLIQUE. Si mañana la contadora mueve el corte,
    // cambia el valor esperado; si alguien deja de filtrar, esto se cae.
    montar('/app/store/fiscalito/use', conCliente(CLIENTE_626));

    expect(screen.queryByText('DIOT')).toBeNull();
    expect(screen.queryByText('Retenciones')).toBeNull();
    // Y no es que se haya quedado sin pantalla: lo que sí le toca sigue ahí.
    expect(screen.getByText('Pre-declaración')).toBeTruthy();
    expect(screen.getByText('Comparar regímenes')).toBeTruthy();
  });

  it('sin cliente elegido no hay pantalla en blanco: hay estado vacío con salida', () => {
    montar('/app/store/fiscalito/use', conCliente(null, [CLIENTE_612]));

    expect(screen.getByText(/Elige un cliente en la barra de arriba/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Ir a mis clientes' }).getAttribute('href'))
      .toBe('/app/clientes');
    expect(screen.queryByText('Pre-declaración')).toBeNull();
  });

  it('con la cartera vacía el estado empuja a dar de alta, no a elegir', () => {
    montar('/app/store/fiscalito/use', conCliente(null, []));

    expect(screen.getByText(/Todavía no tienes clientes/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Dar de alta un cliente' })).toBeTruthy();
  });

  it('un cliente sin régimen capturado lo DICE, no lo supone en silencio', () => {
    /**
     * Los clientes dados de alta antes de T1 no traen el campo. Se les aplica
     * el 612 —el set completo— y la pantalla avisa de dónde salió, que es la
     * diferencia entre un default y una invención.
     */
    montar('/app/store/fiscalito/use', conCliente(CLIENTE_SIN_REGIMEN));

    expect(screen.getByRole('status').textContent).toMatch(/no tiene régimen capturado/);
    expect(screen.getByText('DIOT')).toBeTruthy();
  });

  it('un cliente CON régimen capturado no arrastra el aviso', () => {
    montar('/app/store/fiscalito/use', conCliente(CLIENTE_612));

    expect(screen.queryByRole('status')).toBeNull();
  });

  it('el deep-link a un tab concreto sobrevive al cliente activo', () => {
    montar('/app/store/fiscalito/use?tab=diot', conCliente(CLIENTE_612));

    expect(screen.getByTestId('query').textContent).toBe('?tab=diot');
  });

  it('un contribuyente con un ?tab= que no le toca queda con el query limpio', () => {
    /**
     * COBERTURA QUE SE PERDIÓ AL REESCRIBIR ESTE ARCHIVO. El efecto que limpia
     * el query lo recorría antes un contador con `?tab=declaracion`; desde E-07
     * el contador se sale por el `return` del propio efecto, así que el CUERPO
     * quedó sin ejercitar: sustituirlo por un no-op no rompía nada. Aquí lo
     * recorre quien de verdad lo usa hoy.
     */
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente', regimen: '626' };
    montar('/app/store/fiscalito/use?tab=diot');

    // DIOT no aplica a un RESICO: el tab degrada y el query se limpia.
    expect(screen.queryByText('DIOT')).toBeNull();
    // La sonda lee `useLocation`, no `window.location`: con `MemoryRouter` el
    // segundo está siempre vacío y la aserción no probaría nada.
    expect(screen.getByTestId('query').textContent).toBe('');
  });

  it('el contribuyente conserva sus tabs y su back-link', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente', regimen: '626' };
    montar();

    expect(screen.getByText('Pre-declaración')).toBeTruthy();
    expect(screen.getByText('Calcula tus pre-declaraciones ISR/IVA')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Información/ }).getAttribute('href')).toBe('/app/store/fiscalito');
  });

  it('el contribuyente NO necesita el proveedor de cliente activo', () => {
    /**
     * Esta pantalla es suya desde antes de que el despacho existiera, y en su
     * árbol no hay cartera. Si T1 hubiera usado `useClienteActivo()` —que lanza
     * cuando no encuentra el proveedor— la pantalla del contribuyente reventaría
     * en cualquier montaje sin `CarteraProvider`. Por eso lee el contexto de
     * frente y aguanta el `null`; `montar()` sin wrapper es ese caso.
     */
    perfilMock.actual = { ...perfilBase, contributorType: 'asalariado', regimen: '605' };
    montar();

    // Aparece dos veces —el botón del tab y el encabezado de su contenido—, y
    // lo que se afirma aquí es que la pantalla MONTÓ sin proveedor, no cuántas.
    expect(screen.getAllByText('Deducciones personales').length).toBeGreaterThan(0);
  });
});

describe('FiscalitoServicePage — modo empresa única', () => {
  it('conserva el redirect de E-07: ahí no hay cliente que elegir', () => {
    /**
     * T1 cambia el modo DESPACHO. En modo empresa única no hay cartera, así que
     * el estado vacío mandaría a elegir un cliente en una app que no tiene
     * clientes: el redirect de E-07 sigue siendo la respuesta correcta.
     */
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
    montar('/app/store/fiscalito/use', conCliente(null, []));

    expect(screen.getByText('calendario patronal')).toBeTruthy();
  });
});
