import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { CFDI } from '../services/fiscalAgentApi';
import ingreso001 from '../../public/demo-xmls/2026/01/ingreso-001.xml?raw';
import { modoDespacho } from '../test/modoDespacho';

// firebase.ts corre initializeApp() en el import y tools.ts lo arrastra via
// declaracionesHistory. Sin este mock los tests explotan al importar.
vi.mock('../services/firebase', () => ({
  auth: {},
  db: {},
  default: {},
}));
vi.mock('../services/declaracionesHistory', () => ({
  guardarDeclaracion: vi.fn(),
}));

const setFacturas = vi.fn();
const setPeriodo = vi.fn();
const setResultado = vi.fn();
let facturasEnEstado: CFDI[] = [];

vi.mock('./AgentContext', () => ({
  getAgentActions: () => ({
    setFacturas,
    setPeriodo,
    setResultado,
    pushToolCall: vi.fn(),
    updateToolCall: vi.fn(),
  }),
  getAgentSnapshot: () => ({
    facturas: facturasEnEstado,
    resultado: null,
    periodoYear: 2026,
    periodoMonth: 1,
  }),
}));

/**
 * O-cierre: este archivo mide la semántica del MODO DESPACHO —el prompt que
 * habla de clientes, la ruta de la cartera, la pre-declaración que no aplica—.
 * Desde el pivote el modo por default es empresa única, así que sin declararlo
 * estos casos medían otra app. Es el hueco que el revisor de cierre encontró:
 * sólo 22 de 57 archivos de prueba declaraban modo.
 */
modoDespacho();


const { TOOL_EXECUTORS } = await import('./tools');

function hacerDeps(profile: Partial<UserProfile> = {}) {
  const navigate = vi.fn() as unknown as NavigateFunction;
  return {
    navigate,
    profile: { rfc: 'AAA010101AAA', regimen: '612', ...profile } as UserProfile,
    uid: null,
  };
}

beforeEach(() => {
  facturasEnEstado = [];
  setFacturas.mockClear();
  setPeriodo.mockClear();
});

describe('tool navegar', () => {
  it('rechaza una ruta fuera de la lista blanca sin navegar', async () => {
    const deps = hacerDeps();
    const res = await TOOL_EXECUTORS.navegar({ ruta: '/app/inventada' }, deps);

    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/no está en la lista de rutas válidas/i);
    expect(deps.navigate).not.toHaveBeenCalled();
  });

  // E-01: la lista de clientes del despacho es ruta nueva; si no está en la
  // whitelist, el agente no puede llevar al contador a su propia pantalla.
  it('acepta la pantalla de clientes del despacho', async () => {
    const deps = hacerDeps({ contributorType: 'contador' });
    const res = await TOOL_EXECUTORS.navegar({ ruta: '/app/clientes' }, deps);

    expect(res.ok).toBe(true);
    expect(deps.navigate).toHaveBeenCalledWith('/app/clientes');
  });

  /**
   * E-07: sin estas dos en la whitelist, "llévame al calendario" mandaba al
   * contador al tab de contribuyente —que desde E-05 ni siquiera puede cargar,
   * porque su perfil ya no tiene RFC ni régimen— y "llévame a la nómina" era
   * imposible. El enum es cerrado: lo que no está aquí, el ejecutor lo rechaza.
   */
  it.each(['/app/calendario', '/app/nomina'])('acepta la ruta %s del despacho', async (ruta) => {
    const deps = hacerDeps({ contributorType: 'contador' });
    const res = await TOOL_EXECUTORS.navegar({ ruta }, deps);

    expect(res.ok).toBe(true);
    expect(deps.navigate).toHaveBeenCalledWith(ruta);
  });

  it('navega cuando la ruta es válida', async () => {
    const deps = hacerDeps();
    const res = await TOOL_EXECUTORS.navegar(
      { ruta: '/app/store/fiscalito/use?tab=declaracion' },
      deps,
    );

    expect(res.ok).toBe(true);
    expect(deps.navigate).toHaveBeenCalledTimes(1);
    expect(deps.navigate).toHaveBeenCalledWith('/app/store/fiscalito/use?tab=declaracion');
  });
});

describe('tool calcular_predeclaracion', () => {
  /**
   * E-01. El chat de voz flota sobre TODAS las pantallas, incluidas las del
   * despacho, y esta tool no pasa por el filtro de tabs: sin la guarda, pedirle
   * "calcula la predeclaración" a una cuenta de contador la calcularía sobre el
   * RFC del despacho como si fuera el del cliente del que se está hablando.
   */
  it('se niega en una cuenta de despacho', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion(
      { año: 2026, mes: 1 },
      hacerDeps({ contributorType: 'contador', rfc: 'AAA010101AAA', regimen: '612' }),
    );

    expect(res.ok).toBe(false);
    expect(res.summary).toMatch(/despacho/i);
  });

  // La guarda va ANTES de la de RFC: a un contador el mensaje correcto es "no
  // calculo la predeclaración de un despacho", no "completa tu RFC".
  it('el mensaje del despacho gana al de perfil incompleto', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion(
      { año: 2026, mes: 1 },
      hacerDeps({ contributorType: 'contador', rfc: '', regimen: '' }),
    );

    expect(res.ok).toBe(false);
    expect(res.summary).toMatch(/despacho/i);
    expect(res.summary).not.toMatch(/falta rfc/i);
  });

  it('se detiene si el perfil no tiene RFC, sin llamar a la red', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion(
      { año: 2026, mes: 1 },
      hacerDeps({ rfc: '' }),
    );

    expect(res.ok).toBe(false);
    expect(res.summary).toMatch(/falta rfc o régimen/i);
  });

  it('se detiene si no hay facturas cargadas, sin llamar a la red', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion(
      { año: 2026, mes: 1 },
      hacerDeps(),
    );

    expect(res.ok).toBe(false);
    expect(res.summary).toMatch(/no hay facturas/i);
  });
});

describe('tool cargar_xmls_demo', () => {
  it('acepta index.json en forma de objeto y no duplica facturas ya cargadas', async () => {
    // El uuid de ingreso-001 ya está en el estado: debe ignorarse en la carga.
    const yaCargada = { uuid: '11111111-1111-1111-1111-111111110001' } as CFDI;
    facturasEnEstado = [yaCargada];

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.endsWith('index.json')
          ? { ok: true, json: async () => ({ files: ['ingreso-001.xml'] }) }
          : { ok: true, text: async () => ingreso001 },
      ),
    );

    const res = await TOOL_EXECUTORS.cargar_xmls_demo({ año: 2026, mes: 1 }, hacerDeps());

    expect(res.ok).toBe(true);
    expect(res.data?.cargadas).toBe(0);
    expect(res.data?.total_acumulado).toBe(1);
    expect(setFacturas).toHaveBeenCalledWith([yaCargada]);
  });

  it('acepta index.json en forma de arreglo plano', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.endsWith('index.json')
          ? { ok: true, json: async () => ['ingreso-001.xml'] }
          : { ok: true, text: async () => ingreso001 },
      ),
    );

    const res = await TOOL_EXECUTORS.cargar_xmls_demo({ año: 2026, mes: 1 }, hacerDeps());

    expect(res.ok).toBe(true);
    expect(res.data?.cargadas).toBe(1);
    expect(setPeriodo).toHaveBeenCalledWith(2026, 1);
  });
});
