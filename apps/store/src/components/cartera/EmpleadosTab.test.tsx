/**
 * El criterio de G-02, medido: un empleado sin `employee_no` se ve, y sus
 * checadas no se pierden en silencio.
 *
 * LOS DOS AVISOS SON DISTINTOS Y HACEN FALTA LOS DOS
 * --------------------------------------------------
 * - **No vinculado** (aquí): un empleado de la CARTERA sin `employee_no`.
 * - **Desconocido** (`TablaIncidencias`): un `employeeNo` que SÍ checó y no está
 *   en la plantilla.
 *
 * Son conjuntos que no se tocan. El primero se cuenta desde la cartera; el
 * segundo, desde el flujo de eventos. Con sólo uno de los dos hay gente que
 * desaparece del cálculo sin que nadie lo note.
 */

import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import EmpleadosTab from './EmpleadosTab';
import type { EmpleadoCartera } from '../../services/carteraApi';

afterEach(cleanup);

function emp(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01',
    nombre: 'ANA LOPEZ',
    puesto: 'Cajera',
    salario_diario: '316.00',
    salario_diario_integrado: '331.58',
    zona: 'general',
    fecha_alta: '2024-01-15',
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '',
    employee_no: 'E-01',
    enrolamiento: 'enrolado',
    ...over,
  };
}

function pintar(empleados: EmpleadoCartera[], soloLectura = false) {
  return render(
    <EmpleadosTab
      empleados={empleados}
      soloLectura={soloLectura}
      onGuardar={vi.fn()}
      onBorrar={vi.fn()}
    />,
  );
}

describe('EmpleadosTab · vinculación con el checador (G-02)', () => {
  it('un empleado sin employee_no se marca como NO VINCULADO', () => {
    pintar([emp({ empleado_no: 'N-01', nombre: 'NUEVO', employee_no: null })]);
    expect(screen.getByText('No vinculado')).toBeTruthy();
  });

  it('un empleado vinculado muestra su número del aparato y no la insignia', () => {
    pintar([emp({ employee_no: '7' })]);
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.queryByText('No vinculado')).toBeNull();
  });

  it('avisa cuántos no están vinculados y que NO entran al cálculo', () => {
    // Lo importante no es la insignia sino la consecuencia: si el aviso no
    // dijera que quedan fuera del cálculo, "no se pierden en silencio" sería
    // falso — se verían en la tabla y desaparecerían de los recibos.
    pintar([
      emp({ empleado_no: 'E-01', employee_no: 'E-01' }),
      emp({ empleado_no: 'N-01', nombre: 'NUEVO UNO', employee_no: null }),
      emp({ empleado_no: 'N-02', nombre: 'NUEVO DOS', employee_no: null }),
    ]);
    const aviso = screen.getByRole('alert');
    expect(aviso.textContent).toContain('2 empleados no están vinculados');
    expect(aviso.textContent).toContain('no entran al cálculo');
  });

  it('con un solo empleado sin vincular el aviso va en singular', () => {
    pintar([emp({ employee_no: null })]);
    const aviso = screen.getByRole('alert');
    expect(aviso.textContent).toContain('1 empleado no está vinculado');
    expect(aviso.textContent).toContain('no entra al cálculo');
  });

  it('sin empleados sin vincular no hay aviso', () => {
    // Un aviso que sale siempre es un aviso que nadie lee.
    pintar([emp()]);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('un empleado vinculado pero sin rostro se distingue del no vinculado', () => {
    // Son dos estados distintos: tiene llave (sus checadas se atribuyen) pero
    // todavía no le han capturado el rostro en el aparato.
    pintar([emp({ employee_no: '7', enrolamiento: 'pendiente' })]);
    expect(screen.getByText('Sin rostro')).toBeTruthy();
    expect(screen.queryByText('No vinculado')).toBeNull();
  });
});

describe('EmpleadosTab · tabla', () => {
  it('pinta el salario y el SBC de cada empleado', () => {
    pintar([emp()]);
    expect(screen.getByText('$316.00')).toBeTruthy();
    expect(screen.getByText('$331.58')).toBeTruthy();
  });

  it('en sólo lectura no ofrece alta ni edición', () => {
    // Cuando la cartera viene del backend no se puede escribir: ofrecer el
    // botón sería prometer algo que va a fallar al guardar.
    pintar([emp()], true);
    expect(screen.queryByText('Nuevo empleado')).toBeNull();
    expect(screen.queryByLabelText(/Editar/)).toBeNull();
  });

  it('en modo escritura ofrece editar y dar de baja a cada empleado', () => {
    pintar([emp()]);
    expect(screen.getByText('Nuevo empleado')).toBeTruthy();
    expect(screen.getByLabelText('Editar ANA LOPEZ')).toBeTruthy();
    expect(screen.getByLabelText('Dar de baja a ANA LOPEZ')).toBeTruthy();
  });

  it('una cartera sin empleados lo dice en vez de mostrar una tabla vacía', () => {
    pintar([]);
    expect(screen.getByText(/no tiene empleados/)).toBeTruthy();
  });

  it('el número de empleado se pinta y es la llave del cálculo', () => {
    const { container } = pintar([emp({ empleado_no: 'E-42' })]);
    const primeraFila = within(container).getAllByRole('row')[1];
    expect(primeraFila.textContent).toContain('E-42');
  });
});
