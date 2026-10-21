/**
 * P6-07: la marca de consejero (Art. 96 LISR, quinto párrafo) se captura en la ficha y
 * sólo se ofrece a asimilados.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { EmpleadoCartera } from '../../services/carteraApi';
import CamposNominaEmpleado from './CamposNominaEmpleado';

afterEach(cleanup);

function pintar(extra: Partial<EmpleadoCartera>) {
  const onCambiar = vi.fn();
  const datos = { empleado_no: 'C-1', nombre: 'PERSONA', ...extra } as EmpleadoCartera;
  render(<CamposNominaEmpleado datos={datos} onCambiar={onCambiar} />);
  return onCambiar;
}

describe('CamposNominaEmpleado — consejero', () => {
  it('no se ofrece a sueldos y salarios', () => {
    pintar({ tipo_regimen: '02' });
    expect(screen.queryByRole('group', { name: 'Retención de consejeros' })).toBeNull();
  });

  it('marca al asimilado como consejero', () => {
    const onCambiar = pintar({ tipo_regimen: '09' });
    fireEvent.click(screen.getByLabelText(/Consejero, administrador/));
    expect(onCambiar).toHaveBeenCalledWith({ es_consejero: true });
    expect(screen.queryByLabelText(/Además es trabajador/)).toBeNull();
  });

  it('el consejero puede marcarse además como trabajador, y desmarcarlo limpia esa marca', () => {
    const onCambiar = pintar({ tipo_regimen: '07', es_consejero: true });
    fireEvent.click(screen.getByLabelText(/Además es trabajador/));
    expect(onCambiar).toHaveBeenCalledWith({ consejero_es_trabajador: true });
    fireEvent.click(screen.getByLabelText(/Consejero, administrador/));
    expect(onCambiar).toHaveBeenCalledWith({
      es_consejero: false,
      consejero_es_trabajador: false,
    });
  });
});
