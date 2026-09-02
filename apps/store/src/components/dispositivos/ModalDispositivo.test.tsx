/**
 * El modal de dispositivo. (R-04)
 *
 * POR QUÉ ESTE ARCHIVO EXISTE, DICHO SIN ADORNO
 * ---------------------------------------------
 * En la primera entrega de R-04 este modal **no tenía un solo test**, y un
 * revisor demostró que cuatro mutaciones sobrevivían las 405 pruebas:
 *
 *   1. `puedeGuardar = !guardando` — desconecta `validarDispositivo` de la UI,
 *      y toda la validación probada en `dispositivosApi.test.ts` queda de
 *      adorno sin que nada avise.
 *   2. Borrar `disabled={!vinculado}` del checkbox — `alternar(null)` escribe
 *      **`null` dentro de `employee_nos`** en Firestore: un fantasma permanente
 *      en el cruce, envenenando la llave del checador que G-02 construyó.
 *   3. `alternar` que sólo agrega — no se puede desenrolar a nadie.
 *   4. Borrar la llamada a `onGuardar` — **el botón "Dar de alta" no hace
 *      nada**, que es el criterio de aceptación completo de R-04.
 *
 * La lección es la que ya cazó la corrida G: probar el modelo con rigor y dejar
 * sin tocar la pantalla que el enunciado pide deja el criterio sin cubrir. La
 * cobertura estaba donde era cómoda, no donde importaba.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ModalDispositivo from './ModalDispositivo';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { DispositivoChecador } from '../../services/dispositivosApi';

afterEach(cleanup);

function emp(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: '', salario_diario: '316.00',
    salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: '7', enrolamiento: 'enrolado', ...over,
  };
}

function pintar(opciones: {
  dispositivo?: DispositivoChecador | null;
  empleados?: EmpleadoCartera[];
  serialesEnUso?: string[];
} = {}) {
  const onGuardar = vi.fn().mockResolvedValue(undefined);
  render(
    <ModalDispositivo
      dispositivo={opciones.dispositivo ?? null}
      empleados={opciones.empleados ?? []}
      serialesEnUso={opciones.serialesEnUso ?? []}
      onGuardar={onGuardar}
      onCerrar={vi.fn()}
    />,
  );
  return onGuardar;
}

const boton = () => screen.getByRole('button', { name: /Dar de alta|^Guardar$/ });
const capturar = (campo: RegExp, valor: string) =>
  fireEvent.change(screen.getByLabelText(campo), { target: { value: valor } });

describe('ModalDispositivo · el alta funciona (el criterio de R-04)', () => {
  it('da de alta el dispositivo con lo capturado', async () => {
    // Sin este test, borrar la llamada a `onGuardar` deja el botón inerte y las
    // 405 pruebas en verde: el "Listo cuando" de R-04 sin cubrir.
    const onGuardar = pintar();
    capturar(/Nombre/, 'Entrada planta');
    capturar(/IP en la red/, '192.168.1.64');
    capturar(/Número de serie/, 'ABC123');

    expect(boton()).toHaveProperty('disabled', false);
    fireEvent.click(boton());

    await vi.waitFor(() => expect(onGuardar).toHaveBeenCalled());
    const guardado = onGuardar.mock.calls[0][0];
    expect(guardado.nombre).toBe('Entrada planta');
    expect(guardado.ip).toBe('192.168.1.64');
    expect(guardado.serial).toBe('ABC123');
  });

  it('recorta los espacios del nombre y del serial', () => {
    const onGuardar = pintar();
    capturar(/Nombre/, '  Entrada planta  ');
    capturar(/Número de serie/, '  ABC123  ');
    fireEvent.click(boton());

    return vi.waitFor(() => {
      expect(onGuardar.mock.calls[0][0].nombre).toBe('Entrada planta');
      expect(onGuardar.mock.calls[0][0].serial).toBe('ABC123');
    });
  });
});

describe('ModalDispositivo · la validación está CONECTADA a la UI', () => {
  it('sin nombre no guarda, y no sólo por el atributo `disabled`', () => {
    // `fireEvent.click` sobre un botón deshabilitado no despacha `onClick`, así
    // que afirmar el atributo solo es teatro. Se afirman las dos cosas.
    const onGuardar = pintar();
    expect(boton()).toHaveProperty('disabled', true);
    fireEvent.click(boton());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('una IP mal formada bloquea y lo dice', () => {
    const onGuardar = pintar();
    capturar(/Nombre/, 'Entrada');
    capturar(/IP en la red/, '999.1.1.1');

    expect(screen.getByRole('alert').textContent).toContain('no es una dirección IPv4');
    expect(boton()).toHaveProperty('disabled', true);
    fireEvent.click(boton());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('un serial ya usado por otro aparato bloquea', () => {
    const onGuardar = pintar({ serialesEnUso: ['ABC123'] });
    capturar(/Nombre/, 'Entrada');
    capturar(/Número de serie/, 'ABC123');

    expect(screen.getByRole('alert').textContent).toContain('Ya hay otro dispositivo');
    fireEvent.click(boton());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('la IP vacía NO bloquea: un aparato puede registrarse antes de instalarse', () => {
    const onGuardar = pintar();
    capturar(/Nombre/, 'Entrada');
    expect(boton()).toHaveProperty('disabled', false);
    fireEvent.click(boton());
    return vi.waitFor(() => expect(onGuardar).toHaveBeenCalled());
  });
});

describe('ModalDispositivo · enrolamiento', () => {
  it('marcar a un empleado lo mete a employee_nos con la llave del CHECADOR', () => {
    // `E-01` es su llave de CÁLCULO y `7` la del checador. Lo que se enrola es
    // la del checador: guardar la otra reintroduciría el defecto de G-02.
    const onGuardar = pintar({ empleados: [emp({ empleado_no: 'E-01', employee_no: '7' })] });
    capturar(/Nombre/, 'Entrada');
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(boton());

    return vi.waitFor(() =>
      expect(onGuardar.mock.calls[0][0].employee_nos).toEqual(['7']),
    );
  });

  it('desmarcar lo saca: alternar es simétrico', () => {
    // Sin esto, un `alternar` que sólo agregue deja al operador sin poder
    // desenrolar a nadie, y mete duplicados en el array.
    const onGuardar = pintar({
      dispositivo: {
        id: 'd1', nombre: 'Entrada', ip: '', puerto: 80, marca: '', modelo: '',
        serial: '', employee_nos: ['7'], notas: '',
      },
      empleados: [emp({ employee_no: '7' })],
    });

    const casilla = screen.getByRole('checkbox') as HTMLInputElement;
    expect(casilla.checked).toBe(true);
    fireEvent.click(casilla);
    fireEvent.click(boton());

    return vi.waitFor(() => expect(onGuardar.mock.calls[0][0].employee_nos).toEqual([]));
  });

  it('el empleado SIN employee_no no se puede enrolar, y se ve por qué', () => {
    // Es la mutación más cara de las cuatro: sin `disabled`, marcarlo escribe
    // `null` dentro de `employee_nos` y crea un fantasma permanente en el cruce.
    pintar({ empleados: [emp({ nombre: 'SIN LLAVE', employee_no: null })] });

    const casilla = screen.getByRole('checkbox') as HTMLInputElement;
    expect(casilla.disabled).toBe(true);
    // Y no se esconde: si faltara de la lista, el operador lo buscaría creyendo
    // que se borró de la cartera.
    expect(screen.getByText('SIN LLAVE')).toBeTruthy();
    expect(screen.getByText(/sin número de checador/)).toBeTruthy();
  });

  it('ni siquiera forzando el clic entra un null a employee_nos', () => {
    // Red por si alguien quita el `disabled` sin quitar la guarda: jsdom sí
    // despacha el change de un checkbox deshabilitado con `fireEvent.click`
    // cuando el elemento no está realmente deshabilitado, así que se afirma el
    // RESULTADO y no sólo el atributo.
    const onGuardar = pintar({ empleados: [emp({ employee_no: null })] });
    capturar(/Nombre/, 'Entrada');
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(boton());

    return vi.waitFor(() => {
      const guardado = onGuardar.mock.calls[0][0];
      expect(guardado.employee_nos).not.toContain(null);
      expect(guardado.employee_nos).toEqual([]);
    });
  });
});
