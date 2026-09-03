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
import { modoDespacho } from '../../test/modoDespacho';

/**
 * MODO DESPACHO (O-01).
 *
 * Este archivo mide la tabla de empleados **con la redacción del despacho**:
 * "Este cliente no tiene empleados", "Estás viendo el catálogo de
 * demostración". En modo empresa única esos textos nombran cosas que no
 * existen y el componente escribe otros. Los dos juegos son producto, y cada
 * uno se mide en su modo.
 */
modoDespacho();

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

describe('EmpleadosTab · el NSS por verificar se VE (R-03)', () => {
  /**
   * ESTOS DOS TESTS SON EL PRECIO DE UNA DECISIÓN, NO UN ADORNO.
   *
   * `nss.ts` deja guardar un NSS cuyo dígito verificador no casa, en vez de
   * bloquearlo, porque bloquearlo empujaría al contador a teclear uno que sí
   * pase Luhn — un número inventado junto a datos reales. Toda esa defensa
   * descansa en una sola frase: *"advertir no es callar: el empleado lleva
   * insignia Por verificar en la tabla"*.
   *
   * Sin estos tests esa frase no la sostiene nada: borrar la insignia dejaba la
   * suite entera en verde, y "advierte y guarda" se convertía en "guarda
   * callado" — que es exactamente la conducta que la desviación NO quiso
   * autorizar. Un revisor lo mutó y sobrevivió.
   */

  it('marca el NSS cuyo dígito verificador no coincide', () => {
    // 12345678900: los 10 de payload dan verificador 3, no 0.
    pintar([emp({ nss: '12345678900' })]);

    const fila = screen.getByText('12345678900').closest('tr') as HTMLElement;
    expect(within(fila).getByText(/Por verificar/i)).toBeTruthy();
  });

  it('NO marca un NSS bien formado', () => {
    // La mitad simétrica: sin ella, una insignia que se pintara SIEMPRE pasaría
    // el test de arriba y volvería inútil el aviso por saturación.
    pintar([emp({ nss: '12345678903' })]);

    const fila = screen.getByText('12345678903').closest('tr') as HTMLElement;
    expect(within(fila).queryByText(/Por verificar/i)).toBeNull();
  });

  it('pinta el NSS que tiene el empleado, no un guion', () => {
    // Mata la mutación de una columna que nunca muestra el valor: sin esto, un
    // `{false ? (...)}` en la celda dejaba la suite verde.
    pintar([emp({ nss: '12345678903' })]);
    expect(screen.getByText('12345678903')).toBeTruthy();
  });

  it('sin NSS no inventa insignia ni valor', () => {
    // La semilla del backend llega con `nss: ''` y así se queda: "vacío cuando
    // no se conoce, y nunca inventado".
    pintar([emp({ nss: '' })]);
    expect(screen.queryByText(/Por verificar/i)).toBeNull();
  });
});
