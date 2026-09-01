import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { CFDI } from '../services/fiscalAgentApi';
import ingreso001 from '../../public/demo-xmls/2026/01/ingreso-001.xml?raw';

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
