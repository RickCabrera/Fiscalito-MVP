/**
 * Calendario patronal (E-07).
 *
 * `hoy` SE INYECTA EN TODOS LOS CASOS. "Vencida" y "próxima" dependen de la
 * fecha del sistema, y un test que dependa del reloj pasa hoy y falla el mes
 * que viene sin que nadie toque una línea. Es la misma regla que
 * `despacho_demo.py` impuso al backend con `FECHA_REFERENCIA_DEMO`.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { ObligacionPatronal } from '../services/despachoApi';
import { modoDespacho } from '../test/modoDespacho';

/**
 * MODO DESPACHO (O-01).
 *
 * Este archivo mide el producto de las épicas E, G y R: cartera de clientes,
 * selector de cliente activo y rutas `/app/clientes`. Desde el pivote, el modo
 * por default de la app es **empresa única**, así que el modo en el que corre
 * se declara aquí en vez de heredarse del ambiente.
 *
 * No cambia ninguna aserción: cambia el mundo en el que se evalúan, que es
 * exactamente lo que el flag hace en producción.
 */
modoDespacho();

const perfilContador: UserProfile = {
  contributorType: 'contador',
  rfc: '', regimen: '', nombre: 'Contadora Demo', actividad: '', cp: '', telefono: '',
  nombreNegocio: '', numEmpleados: '', nombreDespacho: 'Despacho Demo',
  onboardingComplete: true,
};

const perfilMock = { actual: perfilContador };

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false }),
}));

const { default: CalendarioPatronalPage } = await import('./CalendarioPatronalPage');
// Puras y fuera de la pantalla: un módulo que mezcla componentes con otras
// exportaciones rompe el fast refresh de Vite, igual que `clienteActivoStore`.
const { agrupar, estadoDeFecha } = await import('../services/calendarioPatronal');

function obligacion(over: Partial<ObligacionPatronal> = {}): ObligacionPatronal {
  return {
    cliente_id: 'demo',
    cliente_nombre: 'Cliente Uno',
    clave: 'imss_mensual',
    nombre: 'Cuotas IMSS de marzo 2026',
    descripcion: 'Entero mensual.',
    fecha_limite: '2026-04-20',
    periodicidad: 'mensual',
    periodo_cubierto: 'marzo 2026',
    fundamento: 'Art. 39 LSS',
    regimen_de_plazo: 'imss',
    condicional: false,
    nota: '',
    ...over,
  };
}

const RESPUESTA = {
  exito: true,
  anio_de_las_cuotas: 2026,
  cubre_desde: '2026-02-17',
  cubre_hasta: '2027-01-18',
  total_obligaciones: 4,
  obligaciones: [
    obligacion(),
    obligacion({ cliente_id: 'taller', cliente_nombre: 'Cliente Dos' }),
    obligacion({
      clave: 'isr_retenido',
      nombre: 'Entero del ISR retenido de marzo 2026',
      fecha_limite: '2026-04-17',
      regimen_de_plazo: 'sat',
      fundamento: 'LISR Art. 96; CFF Art. 12',
    }),
    obligacion({
      clave: 'ptu_moral',
      nombre: 'Reparto de utilidades (PTU) — persona moral',
      fecha_limite: '2026-05-30',
      regimen_de_plazo: 'lft',
      condicional: true,
      nota: 'El modelo de cliente no registra la personalidad jurídica del patrón.',
    }),
  ],
  advertencias: ['No cubre el ISN (Impuesto Sobre Nóminas).'],
};

function stub(cuerpo: unknown = RESPUESTA, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok,
      status: ok ? 200 : 500,
      json: async () => cuerpo,
    })),
  );
}

/** 15 de abril de 2026: el ISR de marzo está próximo y las cuotas también. */
const HOY = new Date(2026, 3, 15);

function montar(hoy = HOY) {
  return render(
    <MemoryRouter initialEntries={['/app/calendario']}>
      <Routes>
        <Route path="/app/calendario" element={<CalendarioPatronalPage hoy={hoy} />} />
        <Route path="/app/store/fiscalito/use" element={<div>tab de contribuyente</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilContador;
  vi.unstubAllGlobals();
  cleanup();
});

describe('estadoDeFecha', () => {
  it('clasifica contra el `hoy` que recibe, no contra el reloj', () => {
    expect(estadoDeFecha('2026-04-20', HOY)).toBe('proxima');
    expect(estadoDeFecha('2026-03-17', HOY)).toBe('vencida');
    expect(estadoDeFecha('2026-12-19', HOY)).toBe('futura');
  });

  it('el mismo día NO está vencido', () => {
    /** Vence hoy: todavía se puede presentar. Marcarlo vencido es un error. */
    expect(estadoDeFecha('2026-04-15', HOY)).toBe('proxima');
  });
});

describe('agrupar', () => {
  it('junta la misma obligación de varios clientes en un renglón', () => {
    const grupos = agrupar([
      obligacion({ cliente_nombre: 'Uno' }),
      obligacion({ cliente_id: 'b', cliente_nombre: 'Dos' }),
    ]);
    expect(grupos).toHaveLength(1);
    const [[fecha, renglones]] = grupos;
    expect(fecha).toBe('2026-04-20');
    expect(renglones).toHaveLength(1);
    expect(renglones[0].clientes).toEqual(['Uno', 'Dos']);
  });

  it('NO junta dos que difieren en `condicional` o en `nota`', () => {
    /**
     * EL CASO QUE VALE ESTE TEST. Hoy los tres calendarios son idénticos, pero
     * `condicional` y `nota` dependen de datos por cliente en cuanto F1-09 los
     * registre. Sin ellos en la clave, dos clientes con distinta personalidad
     * jurídica se colapsarían en un renglón y uno de los dos textos
     * desaparecería sin que nada fallara.
     */
    const grupos = agrupar([
      obligacion({ clave: 'ptu_moral', condicional: true, nota: 'no consta' }),
      obligacion({ clave: 'ptu_moral', cliente_id: 'b', condicional: false, nota: '' }),
    ]);
    expect(grupos[0][1]).toHaveLength(2);
  });

  it('devuelve las fechas en orden ascendente', () => {
    const grupos = agrupar([
      obligacion({ fecha_limite: '2026-05-30' }),
      obligacion({ fecha_limite: '2026-04-17' }),
    ]);
    expect(grupos.map(([f]) => f)).toEqual(['2026-04-17', '2026-05-30']);
  });
});

describe('CalendarioPatronalPage', () => {
  it('agrupa por fecha y dice a qué clientes aplica cada obligación', async () => {
    stub();
    montar();
    const titulo = await screen.findByText(/Cuotas IMSS de marzo 2026/);
    const grupo = titulo.closest('section') as HTMLElement;
    expect(within(grupo).getByText(/Cliente Uno · Cliente Dos/)).toBeTruthy();
  });

  it('no funde la regla del IMSS con la del SAT', async () => {
    /**
     * El doc 25 §4 advierte que juntarlas sin distinguir "es un bug esperando":
     * las cuotas de marzo vencen el 20-abr y su ISR el 17-abr.
     */
    stub();
    montar();
    await screen.findByText(/Cuotas IMSS de marzo 2026/);
    expect(screen.getByText('2026-04-20')).toBeTruthy();
    expect(screen.getByText('2026-04-17')).toBeTruthy();
  });

  it('marca las condicionales y muestra su nota', async () => {
    stub();
    montar();
    expect(await screen.findByText('Verificar')).toBeTruthy();
    expect(screen.getByText(/no registra la personalidad jurídica/)).toBeTruthy();
  });

  it('dice qué rango cubre, para que enero vacío no sea un misterio', async () => {
    stub();
    montar();
    await waitFor(() => expect(screen.getByText('2026-02-17')).toBeTruthy());
    expect(screen.getByText('2027-01-18')).toBeTruthy();
  });

  it('imprime las advertencias que redactó el backend', async () => {
    stub();
    montar();
    expect(await screen.findByText(/No cubre el ISN/)).toBeTruthy();
  });

  it('declara al contador que este calendario es el de sus clientes', async () => {
    /**
     * §D21 resuelta: la app dejó de calcular las obligaciones propias del
     * despacho. Decirlo sólo en el registro de decisiones dejaría al contador
     * sin enterarse de por qué su calendario cambió de contenido.
     */
    stub();
    montar();
    expect(await screen.findByText(/no calcula las obligaciones fiscales propias/)).toBeTruthy();
  });

  it('un error de red se ve, no deja la pantalla en blanco', async () => {
    stub({ error: 'conexión rechazada' }, false);
    montar();
    expect(await screen.findByText(/conexión rechazada/)).toBeTruthy();
  });

  it('la lista vacía se dice, no se deja en blanco', async () => {
    stub({ ...RESPUESTA, obligaciones: [], total_obligaciones: 0 });
    montar();
    expect(await screen.findByText(/No hay obligaciones para este periodo/)).toBeTruthy();
  });

  it('un contribuyente no ve esta pantalla: va a la suya', async () => {
    perfilMock.actual = { ...perfilContador, contributorType: 'independiente', regimen: '626' };
    stub();
    montar();
    expect(await screen.findByText('tab de contribuyente')).toBeTruthy();
  });

  it('pide el año explícito, no lo deja al default del backend', async () => {
    stub();
    montar();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const url = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls[0][0];
    expect(url).toContain('anio_de_las_cuotas=2026');
  });
});
