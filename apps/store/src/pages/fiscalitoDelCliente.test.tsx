/**
 * Fiscalito calcula con el RFC y el régimen del CLIENTE ACTIVO (C-02).
 *
 * Antes de C-02 cada tab armaba su perfil desde el usuario: un contador —que
 * desde E-05 no tiene régimen— recibía "Completa tu RFC y régimen en tu perfil",
 * y si hubiera tenido RFC, el motor habría clasificado las facturas del cliente
 * con el del despacho.
 *
 * LO QUE ESTO PRUEBA Y LO QUE NO: se prueba el REQUEST que sale hacia el motor
 * (RFC, régimen, cliente del historial). La clasificación en sí la hace
 * `clasificar_facturas` en el backend, que aquí está doblado: que emitidas y
 * recibidas salgan bien se sigue de que el RFC que viaja es el del emisor de
 * las facturas de ingreso, no de haber corrido el motor.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { UserProfile } from '../context/ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';
import type { ClienteCartera } from '../services/carteraApi';
import { ClienteActivoContext, type ClienteActivoContextType } from '../context/clienteActivoStore';
import { CarteraContext, type CarteraContextType } from '../context/carteraStore';
import { modoDespacho } from '../test/modoDespacho';

modoDespacho();

const CONTADOR: UserProfile = {
  contributorType: 'contador', rfc: '', regimen: '', nombre: 'Contadora Demo',
  actividad: '', cp: '', telefono: '', nombreNegocio: '', numEmpleados: '',
  nombreDespacho: 'Despacho Demo', onboardingComplete: true,
};

/** Contribuyente con el RFC de pruebas del SAT: sintético. */
const CONTRIBUYENTE: UserProfile = {
  ...CONTADOR, contributorType: 'independiente', rfc: 'XIQB891116QE4', regimen: '612',
  nombre: 'Contribuyente Demo', nombreDespacho: '',
};

const perfilMock = { actual: CONTADOR };

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));
vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false }),
}));
vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));

const historial = vi.hoisted(() => ({
  guardarDeclaracion: vi.fn(async () => 'id'),
  obtenerHistorial: vi.fn(async () => []),
  obtenerAcumuladoAnterior: vi.fn(async () => ({
    ingresos_acumulados: 0, deducciones_acumuladas: 0, isr_pagado_anterior: 0,
    isr_retenido_acumulado: 0, meses_encontrados: [], meses_faltantes: [],
  })),
}));
vi.mock('../services/declaracionesHistory', async () => {
  const real = await vi.importActual<typeof import('../services/declaracionesHistory')>('../services/declaracionesHistory');
  return {
    ...real,
    guardarDeclaracion: historial.guardarDeclaracion,
    obtenerAcumuladoAnterior: historial.obtenerAcumuladoAnterior,
    obtenerHistorial: historial.obtenerHistorial,
  };
});

const DESGLOSE = {
  total_ingresos_facturados: 0, total_ingresos_gravados: 0, cantidad_facturas_ingreso: 0,
  total_egresos: 0, total_deducciones_autorizadas: 0, cantidad_facturas_egreso: 0,
  base_isr: 0, tasa_isr: 0, isr_causado: 0, isr_retenido: 0, isr_a_pagar: 0,
  iva_trasladado_cobrado: 0, iva_trasladado_pagado: 0, iva_retenido: 0, iva_a_pagar: 0, total_a_pagar: 0,
};
const api = vi.hoisted(() => ({
  calcularPreDeclaracion: vi.fn(),
  obtenerCalendario: vi.fn(async () => ({ obligaciones: [] })),
}));
vi.mock('../services/fiscalAgentApi', async () => {
  const real = await vi.importActual<typeof import('../services/fiscalAgentApi')>('../services/fiscalAgentApi');
  return {
    ...real,
    calcularPreDeclaracion: api.calcularPreDeclaracion,
    obtenerCalendario: api.obtenerCalendario,
  };
});
const pdf = vi.hoisted(() => ({ exportarDeclaracionPDF: vi.fn() }));
vi.mock('../services/pdfExport', () => pdf);

const { default: FiscalitoServicePage } = await import('./FiscalitoServicePage');
const { default: ContabilitoPage } = await import('./ContabilitoPage');
const { AgentProvider } = await import('../agent/AgentContext');

// ── Las demo-xmls, tal cual se sirven en `public/` ──

const DIR_DEMO = resolve(__dirname, '../../public/demo-xmls/2026/01');
const ARCHIVOS_DEMO = ['ingreso-001.xml', 'ingreso-002.xml', 'egreso-001.xml'];

function demoXmls(): File[] {
  return ARCHIVOS_DEMO.map((n) => new File([readFileSync(resolve(DIR_DEMO, n), 'utf8')], n, { type: 'text/xml' }));
}

/**
 * El RFC del emisor de las facturas de INGRESO de las demo-xmls, leído del XML
 * y no copiado aquí: es el contribuyente de esas facturas, y es el RFC que el
 * cliente tiene que tener capturado para que el motor las tome como emitidas.
 */
const RFC_DEMO = /<cfdi:Emisor Rfc="([^"]+)"/.exec(readFileSync(resolve(DIR_DEMO, 'ingreso-001.xml'), 'utf8'))![1];

const TALLER: ClienteResumen = {
  id: 'taller', nombre: 'Taller Nogal', giro: 'Reparación', origen: 'sintetico',
  num_empleados: 0, prima_riesgo: '0.0259840', clase_riesgo: 3,
  clave_periodicidad: '04', zona: 'general', regimen: '612', rfc: RFC_DEMO,
};
const OTRO: ClienteResumen = { ...TALLER, id: 'otro', nombre: 'Otro Cliente', rfc: 'XIQB891116QE4' };

function activo(cliente: ClienteResumen | null): ClienteActivoContextType {
  return {
    clientes: cliente ? [cliente] : [], clienteId: cliente?.id ?? null, cliente,
    loading: false, error: null, setClienteId: vi.fn(), recargar: vi.fn(),
  };
}

function arbol(
  valor: ClienteActivoContextType | null, pantalla: ReactNode, cartera?: CarteraContextType,
  ruta = '/app/store/fiscalito/use?tab=declaracion',
) {
  const conAgente = <AgentProvider>{pantalla}</AgentProvider>;
  const conActivo = valor
    ? <ClienteActivoContext.Provider value={valor}>{conAgente}</ClienteActivoContext.Provider>
    : conAgente;
  return (
    <MemoryRouter initialEntries={[ruta]}>
      {cartera ? <CarteraContext.Provider value={cartera}>{conActivo}</CarteraContext.Provider> : conActivo}
    </MemoryRouter>
  );
}

async function subirYCalcular() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: demoXmls() } });
  await screen.findByText(/DEMO0001|ingreso-001|15,000/i, undefined, { timeout: 3000 }).catch(() => null);
  await waitFor(() => expect(screen.getByRole('button', { name: /Calcular pre-declaración/ })).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: /Calcular pre-declaración/ }));
  await waitFor(() => expect(api.calcularPreDeclaracion).toHaveBeenCalled());
}

beforeEach(() => {
  api.calcularPreDeclaracion.mockReset();
  api.calcularPreDeclaracion.mockResolvedValue({
    tipo_declaracion: 'mensual', periodo: 'Enero 2026', regimen: '612', desglose: DESGLOSE,
    explicacion: null, advertencias: [], recomendaciones: [],
  });
  historial.guardarDeclaracion.mockClear();
  historial.obtenerAcumuladoAnterior.mockClear();
  pdf.exportarDeclaracionPDF.mockClear();
  api.obtenerCalendario.mockClear();
  historial.obtenerHistorial.mockClear();
});

afterEach(() => {
  perfilMock.actual = CONTADOR;
  cleanup();
});

describe('C-02 · contador con cliente activo', () => {
  it('la pre-declaración viaja con el RFC y el régimen del cliente, no con los del despacho', async () => {
    render(arbol(activo(TALLER), <FiscalitoServicePage />));
    await subirYCalcular();

    const req = api.calcularPreDeclaracion.mock.calls[0][0];
    expect(req.contribuyente).toEqual({ rfc: RFC_DEMO, regimen: '612', contributor_type: null });
    // Las facturas de ingreso de la demo las EMITIÓ ese RFC y la de egreso la
    // RECIBIÓ: con él, el motor tiene con qué separarlas.
    const facturas = req.facturas as { tipo: string; rfc_emisor: string; rfc_receptor: string }[];
    expect(facturas.filter((f) => f.rfc_emisor === RFC_DEMO).length).toBeGreaterThan(0);
    expect(facturas.filter((f) => f.rfc_receptor === RFC_DEMO).length).toBeGreaterThan(0);
  });

  it('el cálculo y el acumulado del Art. 106 quedan asociados al cliente', async () => {
    render(arbol(activo(TALLER), <FiscalitoServicePage />));
    await subirYCalcular();

    await waitFor(() => expect(historial.guardarDeclaracion).toHaveBeenCalled());
    const [, , categoria, clienteId] = historial.guardarDeclaracion.mock.calls[0] as unknown[];
    expect([categoria, clienteId]).toEqual(['predeclaracion', 'taller']);
    for (const llamada of historial.obtenerAcumuladoAnterior.mock.calls as unknown[][]) {
      expect(llamada[3]).toBe('taller');
    }
  });

  it('el PDF de la pre-declaración lleva al cliente, no al despacho', async () => {
    render(arbol(activo(TALLER), <FiscalitoServicePage />));
    await subirYCalcular();

    fireEvent.click(await screen.findByRole('button', { name: /Descargar PDF/ }));
    expect(pdf.exportarDeclaracionPDF.mock.calls[0][0].contribuyente)
      .toEqual({ nombre: 'Taller Nogal', rfc: RFC_DEMO });
  });

  it('al cambiar de cliente se tiran los XML del anterior y el cálculo usa el RFC del nuevo', async () => {
    const vista = render(arbol(activo(TALLER), <FiscalitoServicePage />));
    await subirYCalcular();
    expect(api.calcularPreDeclaracion.mock.calls[0][0].contribuyente.rfc).toBe(RFC_DEMO);

    vista.rerender(arbol(activo(OTRO), <FiscalitoServicePage />));
    // Ni el resultado ni las facturas del Taller sobreviven al cambio.
    expect(screen.queryByRole('button', { name: /Descargar PDF/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Calcular pre-declaración/ }));
    expect(screen.getByText('Sube al menos una factura XML.')).toBeTruthy();
    expect(api.calcularPreDeclaracion).toHaveBeenCalledTimes(1);

    await subirYCalcular();
    expect(api.calcularPreDeclaracion.mock.lastCall![0].contribuyente)
      .toEqual({ rfc: 'XIQB891116QE4', regimen: '612', contributor_type: null });
  });

  it('un cliente sin RFC ve "Captura el RFC de este cliente", no "Completa tu perfil"', () => {
    render(arbol(activo({ ...TALLER, rfc: undefined }), <FiscalitoServicePage />));

    expect(screen.getByText('Captura el RFC de este cliente.')).toBeTruthy();
    expect(screen.queryByText(/Completa tu RFC/)).toBeNull();
    // Sin cartera que escribir, el acceso lleva a la ficha del cliente.
    expect(screen.getByRole('link', { name: 'Ir a la ficha del cliente' }).getAttribute('href'))
      .toBe('/app/clientes/taller');
  });

  it('con la cartera escribible, el acceso abre la edición del cliente ahí mismo', () => {
    const completo: ClienteCartera = { ...TALLER, rfc: undefined, empleados: [] } as unknown as ClienteCartera;
    const cartera = {
      clientes: [completo], loading: false, origen: 'firestore', soloLectura: false, error: null,
      clientePorId: (id: string) => (id === 'taller' ? completo : null),
      guardarCliente: vi.fn(async () => {}),
    } as unknown as CarteraContextType;
    render(arbol(activo({ ...TALLER, rfc: undefined }), <FiscalitoServicePage />, cartera));

    fireEvent.click(screen.getByRole('button', { name: /Editar cliente/ }));
    expect(screen.getByRole('dialog', { name: 'Editar Taller Nogal' })).toBeTruthy();
  });

  it('un cliente sin régimen no calcula con el 612 supuesto: se le pide', () => {
    render(arbol(activo({ ...TALLER, regimen: undefined }), <FiscalitoServicePage />));
    expect(screen.getByText('Captura el régimen de este cliente.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Calcular pre-declaración/ })).toBeNull();
  });
});

describe('C-02 · calendario del cliente activo', () => {
  it('pide el calendario con el RFC y el régimen del cliente, y SU historial', async () => {
    const MORAL: ClienteResumen = { ...OTRO, id: 'moral', nombre: 'Moral SA', regimen: '601', rfc: 'EKU9003173C9' };
    render(arbol(activo(MORAL), <FiscalitoServicePage />, undefined, '/app/store/fiscalito/use?tab=calendario'));

    await waitFor(() => expect(api.obtenerCalendario).toHaveBeenCalled());
    // §D32 PROVISIONAL: una persona moral recibe el calendario de `pyme`, no el de un independiente.
    expect((api.obtenerCalendario.mock.calls[0] as unknown[])[0]).toMatchObject({
      rfc: 'EKU9003173C9', regimen: '601', contributor_type: 'pyme',
    });
    expect((historial.obtenerHistorial.mock.calls[0] as unknown[])[3]).toBe('moral');
  });

  it('un cliente sin RFC no pide calendario: se le pide el RFC', () => {
    render(arbol(activo({ ...TALLER, rfc: undefined }), <FiscalitoServicePage />, undefined, '/app/store/fiscalito/use?tab=calendario'));
    expect(screen.getByText('Captura el RFC de este cliente.')).toBeTruthy();
    expect(api.obtenerCalendario).not.toHaveBeenCalled();
  });
});

describe('C-02 · el contribuyente calcula exactamente igual que antes', () => {
  it('manda su RFC, su régimen y su tipo, y guarda sin cliente', async () => {
    perfilMock.actual = CONTRIBUYENTE;
    render(arbol(null, <FiscalitoServicePage />));
    await subirYCalcular();

    expect(api.calcularPreDeclaracion.mock.calls[0][0].contribuyente)
      .toEqual({ rfc: 'XIQB891116QE4', regimen: '612', contributor_type: 'independiente' });
    await waitFor(() => expect(historial.guardarDeclaracion).toHaveBeenCalled());
    expect((historial.guardarDeclaracion.mock.calls[0] as unknown[])[3]).toBeNull();
  });
});

describe('C-02 · Contabilito', () => {
  it('el RFC por default es el del cliente activo', () => {
    render(arbol(activo(TALLER), <ContabilitoPage />));
    expect((screen.getByLabelText('RFC del contribuyente') as HTMLInputElement).value).toBe(RFC_DEMO);
  });

  it('un RFC tecleado para un cliente no se hereda al siguiente', () => {
    const vista = render(arbol(activo(TALLER), <ContabilitoPage />));
    fireEvent.change(screen.getByLabelText('RFC del contribuyente'), { target: { value: 'AAA010101AAA' } });
    expect((screen.getByLabelText('RFC del contribuyente') as HTMLInputElement).value).toBe('AAA010101AAA');

    vista.rerender(arbol(activo(OTRO), <ContabilitoPage />));
    expect((screen.getByLabelText('RFC del contribuyente') as HTMLInputElement).value).toBe('XIQB891116QE4');
  });

  it('un cliente sin RFC cae al deducido de los comprobantes, como respaldo', () => {
    render(arbol(activo({ ...TALLER, rfc: undefined }), <ContabilitoPage />));
    expect((screen.getByLabelText('RFC del contribuyente') as HTMLInputElement).value).toBe('');
  });
});
