import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { CFDI } from '../services/fiscalAgentApi';
import ingreso001 from '../../public/demo-xmls/2026/01/ingreso-001.xml?raw';
import egreso001 from '../../public/demo-xmls/2026/01/egreso-001.xml?raw';
import { resolverPerfilFiscal } from '../context/perfilFiscal';
import type { ClienteResumen } from '../services/despachoApi';

// firebase.ts corre initializeApp() en el import y tools.ts lo arrastra via
// declaracionesHistory. Sin este mock los tests explotan al importar.
vi.mock('../services/firebase', () => ({
  auth: {},
  db: {},
  default: {},
}));
const { guardarDeclaracion, calcularPreDeclaracion } = vi.hoisted(() => ({
  // Los argumentos se tipan para que `toHaveBeenCalledWith` los acepte.
  guardarDeclaracion: vi.fn(async (...args: unknown[]) => {
    void args;
    return 'id';
  }),
  calcularPreDeclaracion: vi.fn(),
}));
vi.mock('../services/declaracionesHistory', () => ({ guardarDeclaracion }));
vi.mock('../services/fiscalAgentApi', async (original) => ({
  ...(await original<typeof import('../services/fiscalAgentApi')>()),
  calcularPreDeclaracion,
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

const CLIENTE: ClienteResumen = {
  id: 'taller', nombre: 'Taller Nogal', rfc: 'TNO010101AB1', regimen: '612',
} as ClienteResumen;

/** K: toda cuenta es un despacho; lo que cambia es el cliente activo. */
function hacerDeps(cliente: Partial<ClienteResumen> | null = {}, uid: string | null = null) {
  const navigate = vi.fn() as unknown as NavigateFunction;
  const profile = { contributorType: 'contador', rfc: '', regimen: '', nombre: 'Ana' } as unknown as UserProfile;
  return {
    navigate,
    profile,
    perfilFiscal: resolverPerfilFiscal(profile, cliente ? { ...CLIENTE, ...cliente } : null),
    uid,
  };
}

beforeEach(() => {
  facturasEnEstado = [];
  calcularPreDeclaracion.mockReset();
  guardarDeclaracion.mockClear();
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
    const deps = hacerDeps();
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
    const deps = hacerDeps();
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
   * K: el chat de voz calcula sobre el CLIENTE ACTIVO del despacho. Antes se
   * negaba en toda cuenta de despacho, y desde K todas las cuentas lo son.
   */
  it('sin cliente activo se detiene sin llamar a la red', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion({ año: 2026, mes: 1 }, hacerDeps(null));

    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/elige un cliente/i);
    expect(calcularPreDeclaracion).not.toHaveBeenCalled();
  });

  it('con un cliente sin RFC pide capturarlo, sin llamar a la red', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion({ año: 2026, mes: 1 }, hacerDeps({ rfc: '' }));

    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/captura el rfc de este cliente/i);
    expect(calcularPreDeclaracion).not.toHaveBeenCalled();
  });

  it('se detiene si no hay facturas cargadas, sin llamar a la red', async () => {
    const res = await TOOL_EXECUTORS.calcular_predeclaracion({ año: 2026, mes: 1 }, hacerDeps());

    expect(res.ok).toBe(false);
    expect(res.summary).toMatch(/no hay facturas/i);
    expect(calcularPreDeclaracion).not.toHaveBeenCalled();
  });

  it('calcula con el RFC y el régimen del CLIENTE y guarda con su cliente_id', async () => {
    facturasEnEstado = [{ uuid: 'u1', tipo: 'I' } as CFDI];
    calcularPreDeclaracion.mockResolvedValueOnce({
      exito: true, periodo: 'Enero 2026', regimen: '612', advertencias: [], recomendaciones: [],
      desglose: { total_ingresos_facturados: 1, total_ingresos_gravados: 1, base_isr: 1, tasa_isr: 0,
        isr_causado: 0, isr_a_pagar: 10, iva_a_pagar: 5, total_a_pagar: 15 },
    });

    const res = await TOOL_EXECUTORS.calcular_predeclaracion({ año: 2026, mes: 1 }, hacerDeps({}, 'uid-1'));

    expect(res.ok).toBe(true);
    const req = calcularPreDeclaracion.mock.calls[0][0];
    expect(req.contribuyente).toMatchObject({ rfc: 'TNO010101AB1', regimen: '612', nombre: 'Taller Nogal' });
    expect(guardarDeclaracion).toHaveBeenCalledWith('uid-1', expect.anything(), 'predeclaracion', 'taller');
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

  it('B-01: distingue emitidas de recibidas por el RFC del cliente, no por el tipo', async () => {
    // egreso-001 es una factura de compra: TipoDeComprobante="I" emitida por el
    // proveedor. Contar por tipo daba siempre "0 egreso(s)".
    const rfcDemo = /<cfdi:Emisor Rfc="([^"]+)"/.exec(ingreso001)![1];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.endsWith('index.json')
          ? { ok: true, json: async () => ['ingreso-001.xml', 'egreso-001.xml'] }
          : { ok: true, text: async () => (url.endsWith('egreso-001.xml') ? egreso001 : ingreso001) },
      ),
    );

    const res = await TOOL_EXECUTORS.cargar_xmls_demo({ año: 2026, mes: 1 }, hacerDeps({ rfc: rfcDemo }));

    expect(res.ok).toBe(true);
    expect(res.data?.cargadas).toBe(2);
    expect(res.data?.ingresos).toBe(1);
    expect(res.data?.egresos).toBe(1);
    expect(res.summary).toContain('1 emitida(s), 1 recibida(s)');
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
