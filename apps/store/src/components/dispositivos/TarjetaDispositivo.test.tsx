/**
 * La tarjeta de un dispositivo. (R-04)
 *
 * POR QUÉ TIENE ARCHIVO PROPIO
 * ----------------------------
 * Nació como código **movido**: se extrajo de `DispositivosPage` para bajar del
 * tope de 300 líneas. El corte fue por responsabilidad y es el correcto, pero
 * dejó la responsabilidad **sin medir**: un revisor demostró que seis
 * mutaciones sobrevivían las 421 pruebas. Código movido es código que nadie ha
 * vuelto a mirar.
 *
 * LA MUTACIÓN QUE MÁS IMPORTA NO CAMBIA NINGÚN NÚMERO
 * ---------------------------------------------------
 * Cambiar `#{employee_no}` por `#{empleado_no}` en el chip no rompe ningún
 * cálculo y no lo nota ninguna suite. Pero **este chip es el único lugar de la
 * app donde un humano lee la llave del checador para teclearla en el
 * Hikvision**. Imprimir ahí la llave del cálculo manda al técnico a enrolar
 * `E-01` donde va `7`, y eso produce exactamente el "empleado desconocido" y la
 * falta en todos los días laborables que esta misma pantalla advierte.
 *
 * Es el mejor ejemplo de la corrida de que "no toca cálculo" no es lo mismo que
 * "no tiene consecuencia fiscal".
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import TarjetaDispositivo from './TarjetaDispositivo';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { DispositivoChecador } from '../../services/dispositivosApi';

afterEach(cleanup);

function Aviso({ children }: { children: React.ReactNode }) {
  return <p role="alert">{children}</p>;
}

function emp(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: '', salario_diario: '316.00',
    salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: '7', enrolamiento: 'enrolado', ...over,
  };
}

function disp(over: Partial<DispositivoChecador> = {}): DispositivoChecador {
  return {
    id: 'd1', nombre: 'Entrada planta', ip: '192.168.1.64', puerto: 80,
    marca: 'Hikvision', modelo: 'DS-K1T321MFWX', serial: 'ABC123',
    employee_nos: ['7'], notas: '', ...over,
  };
}

function pintar(opciones: {
  dispositivo?: DispositivoChecador;
  empleados?: EmpleadoCartera[];
  checando?: Set<string> | null;
  soloLectura?: boolean;
} = {}) {
  const onEditar = vi.fn();
  const onBorrar = vi.fn();
  render(
    <TarjetaDispositivo
      dispositivo={opciones.dispositivo ?? disp()}
      empleados={opciones.empleados ?? [emp()]}
      checando={opciones.checando === undefined ? new Set(['7']) : opciones.checando}
      soloLectura={opciones.soloLectura ?? false}
      onEditar={onEditar}
      onBorrar={onBorrar}
      Aviso={Aviso}
    />,
  );
  return { onEditar, onBorrar };
}

describe('TarjetaDispositivo · el chip imprime la llave del CHECADOR', () => {
  it('imprime employee_no, no empleado_no', () => {
    // `E-01` es la llave del CÁLCULO y `7` la del CHECADOR. El técnico teclea
    // en el aparato lo que lee aquí: imprimir la equivocada lo manda a enrolar
    // un número que el checador no va a reportar nunca.
    pintar({ empleados: [emp({ empleado_no: 'E-01', employee_no: '7' })] });

    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).getByText('#7')).toBeTruthy();
    expect(within(chip).queryByText('#E-01')).toBeNull();
  });
});

describe('TarjetaDispositivo · lo que R-04 pide que se vea', () => {
  it('muestra nombre, IP con puerto y número de serie', () => {
    // El enunciado dice "listar, agregar/editar (nombre, IP, serial)". Sin esto,
    // que la celda dejara de pintar la IP y la serie pasaba desapercibido.
    pintar();
    expect(screen.getByText('Entrada planta')).toBeTruthy();
    expect(screen.getByText(/192\.168\.1\.64:80/)).toBeTruthy();
    expect(screen.getByText(/ABC123/)).toBeTruthy();
  });

  it('cuenta los ENROLADOS, no los fantasmas', () => {
    pintar({
      dispositivo: disp({ employee_nos: ['7', '98', '99'] }),
      empleados: [emp({ employee_no: '7' })],
    });
    // Uno enrolado y dos fantasmas: si el contador leyera el otro conjunto
    // diría 2 y nadie lo notaría.
    expect(screen.getByText(/Enrolados · 1/)).toBeTruthy();
  });
});

describe('TarjetaDispositivo · acciones', () => {
  it('editar y dar de baja son botones distintos', () => {
    // Intercambiar los dos handlers deja el botón de baja abriendo el modal de
    // edición, que se ve inofensivo hasta que alguien confía en él.
    const { onEditar, onBorrar } = pintar();

    screen.getByLabelText(/Editar Entrada planta/).click();
    expect(onEditar).toHaveBeenCalledTimes(1);
    expect(onBorrar).not.toHaveBeenCalled();

    screen.getByLabelText(/Dar de baja Entrada planta/).click();
    expect(onBorrar).toHaveBeenCalledTimes(1);
    expect(onEditar).toHaveBeenCalledTimes(1);
  });

  it('una cartera de sólo lectura no ofrece editar ni dar de baja', () => {
    // `soloLectura` significa que la cartera no es del usuario. Ofrecer los
    // botones ahí promete una escritura que va a fallar.
    pintar({ soloLectura: true });
    expect(screen.queryByLabelText(/Editar/)).toBeNull();
    expect(screen.queryByLabelText(/Dar de baja/)).toBeNull();
  });
});

describe('TarjetaDispositivo · "sin checadas" sólo cuando se pudo preguntar', () => {
  it('con checando null no marca a nadie', () => {
    pintar({ checando: null });
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).queryByText(/sin checadas/)).toBeNull();
  });

  it('con checando vacío sí marca: eso es saber que no ha checado', () => {
    pintar({ checando: new Set() });
    const chip = screen.getByText('ANA LOPEZ').closest('li') as HTMLElement;
    expect(within(chip).getByText(/sin checadas/)).toBeTruthy();
  });
});
