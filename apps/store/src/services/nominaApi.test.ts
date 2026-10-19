/**
 * P4-01 desde el front: el cálculo va autenticado y SIN plantilla.
 */

import { describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-de-prueba' } },
  db: {},
  default: {},
}));

import { calcularNomina, compararPeriodos, listarHistorial } from './nominaApi';

function capturar() {
  const llamadas: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      llamadas.push({ url, init });
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    }),
  );
  return llamadas;
}

describe('calcularNomina', () => {
  it('no manda la plantilla y sí el token, el tipo y las variables', async () => {
    const llamadas = capturar();
    await calcularNomina(
      'taller',
      { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
      [{ empleado_no: 'E-1', dias_periodo: 16, dias_laborables: 11, dias_trabajados: 11, faltas: 0, dias_ausentismo: 0, retardos: 0, dias_cotizados: 16 }],
      { prima_riesgo: '0.0054355', clave_periodicidad: '04' },
      { tipo: 'asimilados', variables: [{ empleado_no: 'E-1', horas_dobles: '3' }] },
    );
    const { url, init } = llamadas[0];
    expect(url).toMatch(/\/api\/v1\/nomina\/calcular-periodo$/);
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer token-de-prueba');
    const cuerpo = JSON.parse(init.body as string);
    expect(cuerpo.empleados).toBeUndefined();
    expect(cuerpo.tipo).toBe('asimilados');
    expect(cuerpo.variables).toEqual([{ empleado_no: 'E-1', horas_dobles: '3' }]);
    // Sólo los cuatro campos del cierre que alimentan el cálculo, verbatim.
    expect(cuerpo.incidencias).toEqual([{ empleado_no: 'E-1', dias_periodo: 16, faltas: 0, dias_ausentismo: 0 }]);
  });
});

describe('historial', () => {
  it('lista por cliente y compara por query', async () => {
    const llamadas = capturar();
    await listarHistorial('mi cliente', 'ptu');
    await compararPeriodos('taller', 3, 5);
    expect(llamadas[0].url).toMatch(/\/nomina\/clientes\/mi%20cliente\/historial\?tipo=ptu$/);
    expect(llamadas[1].url).toMatch(/\/nomina\/clientes\/taller\/comparar\?a=3&b=5$/);
  });
});
