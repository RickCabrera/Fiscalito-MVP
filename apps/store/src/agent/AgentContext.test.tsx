import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import type { CFDI } from '../services/fiscalAgentApi';
import { AgentProvider, getAgentActions, getAgentSnapshot } from './AgentContext';

afterEach(cleanup);

/**
 * Estos dos tests protegen el invariante de los dos useEffect que sincronizan
 * stateRef y actionsRef: son lo unico que conecta las tools (que no son
 * componentes) con el estado de React.
 *
 * Por que importa para S-02: este archivo no tiene errores de eslint, tiene 3
 * warnings de react-refresh/only-export-components. La forma canonica de
 * callarlos es mover getAgentSnapshot/getAgentActions/useAgent a otro archivo,
 * y ese refactor es justo el que puede dejar colgado el cableado de las refs.
 */
describe('AgentContext', () => {
  it('getAgentActions lanza si no hay provider montado', async () => {
    // Modulo fresco: actionsRef arranca en null, sin importar el orden de tests.
    vi.resetModules();
    const fresco = await import('./AgentContext');

    expect(() => fresco.getAgentActions()).toThrow(/no está montado/i);
  });

  it('deja vivas las refs de las tools despues del montaje', () => {
    render(<AgentProvider><div /></AgentProvider>);

    // Antes del montaje esto lanzaba; despues debe existir.
    const actions = getAgentActions();
    expect(actions.setFacturas).toBeTypeOf('function');

    const factura = { uuid: 'uuid-1', tipo: 'I' } as CFDI;
    act(() => actions.setFacturas([factura]));

    // El snapshot que leen las tools refleja el estado de React.
    expect(getAgentSnapshot().facturas).toEqual([factura]);

    act(() => actions.setPeriodo(2025, 7));
    expect(getAgentSnapshot().periodoYear).toBe(2025);
    expect(getAgentSnapshot().periodoMonth).toBe(7);
  });
});
