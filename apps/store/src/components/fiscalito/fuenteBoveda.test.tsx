/**
 * P1-06 · Los módulos leen la bóveda.
 *
 * "Listo cuando": con la bóveda cargada, la pre-declaración del mes sale SIN SUBIR
 * UN ARCHIVO, y cada tab de Fiscalito y Contabilito usa la bóveda por defecto.
 * `fetch` stubbeado: responde la bóveda (`/facturas-calculo`) y el cálculo
 * (`/pre-declaracion`); la autenticación es un doble. CFDI sintéticos.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { UserProfile } from '../../context/ProfileContext';
import type { ClienteResumen } from '../../services/despachoApi';
import type { FacturasDeBoveda } from '../../services/bovedaApi';
import { ClienteActivoContext, type ClienteActivoContextType } from '../../context/clienteActivoStore';

const CONTADOR: UserProfile = {
  contributorType: 'contador', rfc: '', regimen: '', nombre: 'Contadora Demo',
  actividad: '', cp: '', telefono: '', nombreNegocio: '', numEmpleados: '',
  nombreDespacho: 'Despacho Demo', onboardingComplete: true,
};

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));
vi.mock('../../context/ProfileContext', () => ({
  useProfile: () => ({ profile: CONTADOR, loading: false }),
}));
vi.mock('../../services/declaracionesHistory', async () => {
  const real = await vi.importActual<typeof import('../../services/declaracionesHistory')>('../../services/declaracionesHistory');
  const ok = async () => 'id';
  return {
    ...real,
    guardarDeclaracion: vi.fn(ok), guardarDIOT: vi.fn(ok), guardarRetenciones: vi.fn(ok),
    guardarMultiPeriodo: vi.fn(ok), guardarEstadoCuenta: vi.fn(ok),
    obtenerAcumuladoAnterior: vi.fn(async () => ({
      ingresos_acumulados: 0, deducciones_acumuladas: 0, isr_pagado_anterior: 0,
      isr_retenido_acumulado: 0, meses_encontrados: [], meses_faltantes: [],
    })),
  };
});
vi.mock('../../services/pdfExport', () => ({ exportarDeclaracionPDF: vi.fn() }));

const { default: PreDeclaracionTab } = await import('./PreDeclaracionTab');
const { default: DIOTTab } = await import('./DIOTTab');
const { default: RetencionesTab } = await import('./RetencionesTab');
const { default: MultiPeriodoTab } = await import('./MultiPeriodoTab');
const { default: EstadoCuentaTab } = await import('./EstadoCuentaTab');
const { default: DeclaracionAnualTab } = await import('./DeclaracionAnualTab');
const { default: ContabilitoPage } = await import('../../pages/ContabilitoPage');
const { AgentProvider } = await import('../../agent/AgentContext');

const RFC = 'XEXX010101AB1';
const TALLER: ClienteResumen = {
  id: 'taller', nombre: 'Taller Nogal', giro: 'Reparación', origen: 'sintetico',
  num_empleados: 0, prima_riesgo: '0.0259840', clase_riesgo: 3,
  clave_periodicidad: '04', zona: 'general', regimen: '612', rfc: RFC,
};
const ACTIVO: ClienteActivoContextType = {
  clientes: [TALLER], clienteId: 'taller', cliente: TALLER,
  loading: false, error: null, setClienteId: vi.fn(), recargar: vi.fn(),
};

const HOY = new Date();
const ANIO = HOY.getFullYear();
const MES = String(HOY.getMonth() + 1).padStart(2, '0');

function cfdi(uuid: string, extra: Record<string, unknown> = {}) {
  return {
    uuid, fecha: `${ANIO}-${MES}-05`, tipo: 'I', rfc_emisor: RFC, rfc_receptor: 'COM010101BB2',
    subtotal: 1000, total: 1160, iva_trasladado: 160, iva_retenido: 0, isr_retenido: 0,
    descuento: 0, uso_cfdi: 'G03', descripcion: 'Servicio', clave_prod_serv: '84111506',
    metodo_pago: 'PUE', uuid_relacionado: null, monto_pago: null, ...extra,
  };
}

interface RespuestaBoveda {
  exito: boolean;
  facturas: ReturnType<typeof cfdi>[];
  relacionados: ReturnType<typeof cfdi>[];
  resumen: FacturasDeBoveda['resumen'];
  advertencias: string[];
}

const BOVEDA_LLENA: RespuestaBoveda = {
  exito: true,
  facturas: [
    cfdi('U-VENTA'),
    cfdi('U-GASTO', { rfc_emisor: 'PRO010101AA1', rfc_receptor: RFC, subtotal: 500, total: 580, iva_trasladado: 80 }),
    cfdi('U-PAGO', { tipo: 'P', subtotal: 0, total: 0, iva_trasladado: 0, uuid_relacionado: 'U-PPD', monto_pago: 1160 }),
  ],
  relacionados: [cfdi('U-PPD', { fecha: `${ANIO - 1}-12-20`, metodo_pago: 'PPD' })],
  resumen: {
    comprobantes: 3, emitidos: 2, recibidos: 1, por_tipo: { I: 2, P: 1 },
    cancelados_excluidos: 1, nomina_excluidos: 2, relacionados_fuera_del_periodo: 1,
  },
  advertencias: [],
};
const BOVEDA_VACIA: RespuestaBoveda = {
  ...BOVEDA_LLENA, facturas: [], relacionados: [],
  resumen: { ...BOVEDA_LLENA.resumen, comprobantes: 0, emitidos: 0, recibidos: 0, por_tipo: {},
    cancelados_excluidos: 0, nomina_excluidos: 0, relacionados_fuera_del_periodo: 0 },
};
const DESGLOSE = {
  total_ingresos_facturados: 2000, total_ingresos_gravados: 2000, cantidad_facturas_ingreso: 2,
  total_egresos: 500, total_deducciones_autorizadas: 500, cantidad_facturas_egreso: 1,
  base_isr: 1500, tasa_isr: 0.0192, isr_causado: 28.8, isr_retenido: 0, isr_a_pagar: 28.8,
  iva_trasladado_cobrado: 320, iva_trasladado_pagado: 80, iva_retenido: 0, iva_a_pagar: 240, total_a_pagar: 268.8,
};

let boveda: RespuestaBoveda = BOVEDA_LLENA;
let peticiones: { url: string; method: string; body?: BodyInit | null }[] = [];

beforeEach(() => {
  boveda = BOVEDA_LLENA;
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: init.body });
    if (url.includes('/facturas-calculo')) return Response.json(boveda);
    if (url.endsWith('/boveda/clientes/taller/cfdi') && method === 'POST') {
      return Response.json({ exito: true, rfc_cliente: RFC, rfc_deducido: false, importados: 1,
        duplicados: 0, rechazados: [], importados_detalle: [], duplicados_detalle: [] });
    }
    if (url.endsWith('/api/v1/pre-declaracion')) {
      return Response.json({ tipo_declaracion: 'mensual', periodo: 'Mes', regimen: '612',
        desglose: DESGLOSE, explicacion: null, advertencias: [], recomendaciones: [] });
    }
    return Response.json({ detail: `no stubbeado: ${url}` }, { status: 500 });
  }));
});
afterEach(() => cleanup());

function montar(pantalla: ReactNode) {
  return render(
    <MemoryRouter>
      <ClienteActivoContext.Provider value={ACTIVO}>
        <AgentProvider>{pantalla}</AgentProvider>
      </ClienteActivoContext.Provider>
    </MemoryRouter>,
  );
}

const pedidasALaBoveda = () => peticiones.filter((p) => p.url.includes('/facturas-calculo'));

describe('P1-06 · Pre-declaración desde la bóveda', () => {
  it('sale sin subir un archivo: la bóveda del mes va directo al cálculo', async () => {
    montar(<PreDeclaracionTab />);

    expect(await screen.findByText(/3 CFDI de .* en la bóveda: 2 emitidos y 1 recibido/)).toBeTruthy();
    expect(screen.getByText(/No entran al cálculo: 1 cancelado y 2 de nómina/)).toBeTruthy();
    expect(screen.getByRole('radio', { name: /Bóveda del cliente/ }).getAttribute('aria-checked')).toBe('true');
    // Ni un input de archivo en pantalla: nadie subió nada.
    expect(document.querySelector('input[type="file"]')).toBeNull();

    const [pedida] = pedidasALaBoveda();
    expect(pedida.url).toContain('/api/v1/boveda/clientes/taller/facturas-calculo?');
    expect(pedida.url).toContain(`desde=${ANIO}-${MES}-01`);

    fireEvent.click(screen.getByRole('button', { name: /Calcular pre-declaración/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/api/v1/pre-declaracion'))).toBe(true));

    const calc = peticiones.find((p) => p.url.endsWith('/api/v1/pre-declaracion'))!;
    const req = JSON.parse(String(calc.body));
    expect(req.contribuyente).toEqual({ rfc: RFC, regimen: '612', contributor_type: null });
    expect(req.periodo_month).toBe(HOY.getMonth() + 1);
    // Las del periodo + el PPD de otro mes que el pago liquida; los `null` no viajan.
    expect(req.facturas.map((f: { uuid: string }) => f.uuid)).toEqual(['U-VENTA', 'U-GASTO', 'U-PAGO', 'U-PPD']);
    expect(req.facturas[2]).toMatchObject({ tipo: 'P', uuid_relacionado: 'U-PPD', monto_pago: 1160 });
    expect('uuid_relacionado' in req.facturas[0]).toBe(false);
    expect(req.facturas.every((f: { tipo: string }) => f.tipo !== 'NOMINA' && f.tipo !== 'N')).toBe(true);

    expect(await screen.findByRole('button', { name: /Descargar PDF/ })).toBeTruthy();
  });

  it('con la bóveda vacía lleva a la Bóveda y a la Descarga SAT, y no calcula', async () => {
    boveda = BOVEDA_VACIA;
    montar(<PreDeclaracionTab />);

    expect(await screen.findByText(/La bóveda no tiene CFDI vigentes de/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Bóveda' }).getAttribute('href')).toBe('/app/boveda');
    expect(screen.getByRole('link', { name: 'Descarga SAT' }).getAttribute('href')).toBe('/app/sat');

    fireEvent.click(screen.getByRole('button', { name: /Calcular pre-declaración/ }));
    expect(await screen.findByText(/no tiene CFDI vigentes de .*usa archivos sueltos/)).toBeTruthy();
    expect(peticiones.some((p) => p.url.endsWith('/api/v1/pre-declaracion'))).toBe(false);
  });

  it('lo subido a mano se manda a la bóveda con un clic', async () => {
    montar(<PreDeclaracionTab />);
    fireEvent.click(await screen.findByRole('radio', { name: /Usar archivos sueltos/ }));
    const xml = `<?xml version="1.0"?><cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
      Fecha="${ANIO}-${MES}-05T10:00:00" SubTotal="1000" Total="1160" TipoDeComprobante="I" MetodoPago="PUE">
      <cfdi:Emisor Rfc="${RFC}"/><cfdi:Receptor Rfc="COM010101BB2"/></cfdi:Comprobante>`;
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File([xml], 'a.xml', { type: 'text/xml' })] } });

    fireEvent.click(await screen.findByRole('button', { name: /Guardar en la bóveda \(1\)/ }));
    expect(await screen.findByText(/Guardados en la bóveda: 1/)).toBeTruthy();
    const subida = peticiones.find((p) => p.method === 'POST' && p.url.endsWith('/boveda/clientes/taller/cfdi'));
    expect((subida?.body as FormData).getAll('archivos')).toHaveLength(1);
  });
});

describe('P1-06 · Cada tab usa la bóveda por defecto', () => {
  const TABS: [string, ReactNode][] = [
    ['Declaración anual', <DeclaracionAnualTab key="a" />],
    ['DIOT', <DIOTTab key="d" />],
    ['Retenciones', <RetencionesTab key="r" />],
    ['Multi-periodo', <MultiPeriodoTab key="m" />],
    ['Estado de cuenta', <EstadoCuentaTab key="e" />],
  ];

  it.each(TABS)('%s', async (_nombre, tab) => {
    montar(tab);
    expect(await screen.findByText(/3 CFDI de .* en la bóveda/)).toBeTruthy();
    expect(screen.getByRole('radio', { name: /Bóveda del cliente/ }).getAttribute('aria-checked')).toBe('true');
    expect(pedidasALaBoveda()[0].url).toContain('/boveda/clientes/taller/facturas-calculo');
  });

  it('Contabilito contabiliza el mes de la bóveda sin subir archivos', async () => {
    montar(<ContabilitoPage />);
    expect(await screen.findByText(/3 CFDI de .* en la bóveda/)).toBeTruthy();
    // Una póliza por CFDI del periodo (venta, compra, cobro); el PPD de otro mes
    // no se contabiliza aquí: es la venta de ESE mes, no de éste.
    expect(await screen.findByText('Venta — Servicio')).toBeTruthy();
    expect(screen.getByText('Compra — Servicio')).toBeTruthy();
    expect(screen.getByText('Cobro de cliente — Servicio')).toBeTruthy();
    expect(screen.getAllByText(/^Venta/)).toHaveLength(1);
    expect(document.querySelector('input[type="file"]')).toBeNull();
  });
});
