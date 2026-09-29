/**
 * Las validaciones del alta de cliente (G-03).
 *
 * Las tres deciden si se guarda, y ninguna tenía cobertura: el archivo nació en
 * esta rama y ningún test lo importaba.
 *
 * La que más pesa es la de la prima de Riesgos de Trabajo. Los límites del
 * Art. 72 LSS los sirve el motor (`GET /despacho/primas-de-riesgo`) **con su
 * fecha de vigencia**, y por eso no viven en TypeScript. Si esa llamada falla,
 * el formulario no puede validar nada: dejar guardar entonces permitiría
 * `5.4355` en vez de `0.0054355` — la prima multiplicada por mil, sin que nada
 * lo detecte después.
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ModalCliente from './ModalCliente';

const obtenerPrimasDeRiesgo = vi.fn();
vi.mock('../../services/carteraApi', async () => {
  const real = await vi.importActual<typeof import('../../services/carteraApi')>(
    '../../services/carteraApi',
  );
  return { ...real, obtenerPrimasDeRiesgo: (f: string) => obtenerPrimasDeRiesgo(f) };
});

const PRIMAS = {
  fecha: '2026-09-01',
  minima: '0.005',
  maxima: '0.15',
  medias_por_clase: {
    '1': '0.0054355', '2': '0.0113065', '3': '0.0259840',
    '4': '0.0465325', '5': '0.0758875',
  },
  fundamento: 'Arts. 72 y 73 LSS.',
};

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

function pintar(idsExistentes: string[] = [], cliente: Parameters<typeof ModalCliente>[0]['cliente'] = null) {
  const onGuardar = vi.fn().mockResolvedValue(undefined);
  render(
    <ModalCliente
      cliente={cliente}
      idsExistentes={idsExistentes}
      onGuardar={onGuardar}
      onCerrar={vi.fn()}
    />,
  );
  return onGuardar;
}

const campo = (etiqueta: RegExp) => screen.getByLabelText(etiqueta);
const botonAlta = () => screen.getByRole('button', { name: /Dar de alta/ });

function llenarBasico() {
  fireEvent.change(campo(/Identificador/), { target: { value: 'tortilleria-lopez' } });
  fireEvent.change(campo(/Razón social/), { target: { value: 'Tortillería López' } });
  // C-01: RFC, CP y entidad son obligatorios en el alta. RFC de persona física
  // (13), que casa con el 612 del default y con el 626.
  fireEvent.change(campo(/^RFC/), { target: { value: 'LOPT800101AB1' } });
  fireEvent.change(campo(/Código postal/), { target: { value: '91000' } });
  fireEvent.change(campo(/Entidad federativa/), { target: { value: 'VER' } });
}

describe('ModalCliente · la prima de RT se acota contra el Art. 72', () => {
  it('una prima mil veces mayor no se puede guardar', async () => {
    // 5.4355 en vez de 0.0054355. Es el error de dedo que multiplica Riesgos de
    // Trabajo por mil, y ninguna tabla de referencia lo detecta después.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '5.4355' } });

    expect(screen.getByRole('alert').textContent).toContain('Art. 72');
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('una prima por debajo del mínimo tampoco', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0001' } });

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('una prima dentro del rango sí', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0113065' } });

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));
  });

  it('elegir clase propone la prima media que da el MOTOR', async () => {
    // No hay tabla de primas en TypeScript: la del Art. 73 es por año y aquí
    // quedaría sin vigencia, sin fuente y sin test.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    fireEvent.change(campo(/Clase de riesgo/), { target: { value: '3' } });

    await waitFor(() => expect(campo(/Prima de RT/)).toHaveProperty('value', '0.0259840'));
  });
});

describe('ModalCliente · los campos obligatorios', () => {
  it('sin prima de RT no se guarda', async () => {
    // `primaFueraDeRango` excluye la cadena vacía a propósito, así que lo único
    // que impide guardar un cliente SIN prima es la cláusula de `puedeGuardar`.
    // Un cliente sin prima es un cliente al que no se le puede calcular Riesgos
    // de Trabajo, y hasta ahora nada lo fijaba.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();

    expect(campo(/Prima de RT/)).toHaveProperty('value', '');
    expect(botonAlta()).toHaveProperty('disabled', true);
  });

  it('sin razón social no se guarda', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    fireEvent.change(campo(/Identificador/), { target: { value: 'tortilleria-lopez' } });
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0113065' } });

    expect(botonAlta()).toHaveProperty('disabled', true);
  });

  it('el handler tampoco guarda si la validación no pasa', async () => {
    // Simetría con `useNominaCliente`: la guarda vive en el handler, no sólo en
    // el atributo del botón.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    const onGuardar = pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '5.4355' } });

    fireEvent.click(botonAlta());
    await new Promise((r) => setTimeout(r, 30));
    expect(onGuardar).not.toHaveBeenCalled();
  });
});

describe('ModalCliente · sin los límites no se guarda', () => {
  it('si el endpoint de primas falla, lo dice y bloquea el alta', async () => {
    // La validación no se evapora en silencio: sin límites no hay con qué
    // acotar, y guardar a ciegas es lo que deja pasar el error de dedo.
    obtenerPrimasDeRiesgo.mockRejectedValue(new Error('API caída'));
    pintar();

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain('Art. 72 LSS'),
    );
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0113065' } });
    expect(botonAlta()).toHaveProperty('disabled', true);
  });
});

describe('ModalCliente · el identificador no se repite', () => {
  it('avisa y bloquea si ya existe', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar(['tortilleria-lopez']);
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0113065' } });

    expect(screen.getByRole('alert').textContent).toContain('Ya tienes un cliente');
    expect(botonAlta()).toHaveProperty('disabled', true);
  });
});

describe('ModalCliente · la periodicidad', () => {
  it('sólo ofrece quincenal, y está deshabilitada', async () => {
    // El periodo que la app propone es siempre una quincena y nadie valida que
    // la duración case con la clave: un cliente Mensual recibiría la tarifa
    // mensual del Art. 96 sobre 15-16 días, con ISR subestimado y recibo
    // creíble. Abrir las otras exige que el motor rechace la discrepancia.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());

    const select = campo(/Periodicidad/) as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(Array.from(select.options).map((o) => o.value)).toEqual(['04']);
  });
});

describe('ModalCliente · el régimen del cliente (T1)', () => {
  /**
   * ES EL ORIGEN DEL DATO DEL QUE CUELGA T1 ENTERA. Si esto guarda mal, la
   * pantalla de Fiscalito filtra sus tabs con el régimen equivocado y se ve
   * perfectamente bien haciéndolo.
   *
   * El corte fiscal 612/626 NO se mide aquí —ése vive en `navigation.ts` y está
   * pendiente de confirmar (§D30)—: aquí sólo se mide que el valor que el
   * contador elige sea el que sale por `onGuardar`.
   */
  it('nace con 612 y guarda lo que el contador elija', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    const onGuardar = pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());

    const select = campo(/Régimen fiscal/) as HTMLSelectElement;
    expect(select.value).toBe('612');
    // T6 agrego el 601 (personas morales) a `REGIMENES_DE_CLIENTE`. La lista se
    // sigue comparando ENTERA y en orden a proposito: si manana entra otro
    // regimen sin que nadie lo piense, este test lo caza igual que cazo este.
    expect(Array.from(select.options).map((o) => o.value)).toEqual(['612', '626', '601']);

    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0054355' } });
    fireEvent.change(select, { target: { value: '626' } });
    fireEvent.click(botonAlta());

    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].regimen).toBe('626');
  });

  it('un cliente ANTERIOR a T1 deja de arrastrar el campo vacío al reguardarse', async () => {
    /**
     * LA RAMA QUE NO SE VE. Un cliente guardado antes de T1 llega sin la llave,
     * y el `select` pinta el default **sin disparar `onChange`**: sin el
     * `regimen: datos.regimen || REGIMEN_CLIENTE_POR_DEFECTO` del handler se
     * guardaría igual de vacío, y la pantalla de Fiscalito seguiría avisando
     * "régimen supuesto" después de que el contador ya lo dio por bueno.
     */
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    const onGuardar = pintar([], {
      id: 'viejo', nombre: 'Cliente Viejo', giro: 'Servicios', origen: 'propio',
      prima_riesgo: '0.0054355', clase_riesgo: 1, clave_periodicidad: '04',
      zona: 'general', periodo_sugerido: { inicio: '', fin: '', fecha_pago: null },
    });
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());

    expect((campo(/Régimen fiscal/) as HTMLSelectElement).value).toBe('612');

    fireEvent.click(screen.getByRole('button', { name: /^Guardar$/ }));
    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].regimen).toBe('612');
  });
});

describe('ModalCliente · RFC, código postal y entidad (C-01)', () => {
  const VIEJO = {
    id: 'viejo', nombre: 'Cliente Viejo', giro: 'Servicios', origen: 'propio',
    prima_riesgo: '0.0054355', clase_riesgo: 1, clave_periodicidad: '04',
    zona: 'general', periodo_sugerido: { inicio: '', fin: '', fecha_pago: null },
  };

  async function alta() {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    const onGuardar = pintar();
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    llenarBasico();
    fireEvent.change(campo(/Prima de RT/), { target: { value: '0.0054355' } });
    return onGuardar;
  }

  it('un alta completa manda RFC en mayúsculas, CP y entidad', async () => {
    const onGuardar = await alta();
    fireEvent.change(campo(/^RFC/), { target: { value: 'lopt800101ab1' } });
    expect((campo(/^RFC/) as HTMLInputElement).value).toBe('LOPT800101AB1');
    fireEvent.click(botonAlta());

    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    const guardado = onGuardar.mock.calls[0][0];
    expect(guardado.rfc).toBe('LOPT800101AB1');
    expect(guardado.codigo_postal).toBe('91000');
    expect(guardado.clave_entidad).toBe('VER');
  });

  it.each([
    [/^RFC/, ''],
    [/Código postal/, ''],
    [/Entidad federativa/, ''],
  ])('en un alta, %s vacío no se puede guardar', async (etiqueta, valor) => {
    const onGuardar = await alta();
    fireEvent.change(campo(etiqueta), { target: { value: valor } });
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
    fireEvent.click(botonAlta());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('un RFC de persona moral con régimen 612 se rechaza con mensaje', async () => {
    const onGuardar = await alta();
    fireEvent.change(campo(/^RFC/), { target: { value: 'LOP800101AB1' } });

    expect(screen.getByRole('alert').textContent).toMatch(/persona física.*13 caracteres/);
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
    fireEvent.click(botonAlta());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('cambiar a 601 con un RFC de 13 también se rechaza', async () => {
    await alta();
    fireEvent.change(campo(/Régimen fiscal/), { target: { value: '601' } });
    expect(screen.getByRole('alert').textContent).toMatch(/persona moral.*12 caracteres/);
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('un RFC mal formado se rechaza con mensaje', async () => {
    await alta();
    fireEvent.change(campo(/^RFC/), { target: { value: 'LOPT80A101AB1' } });
    expect(screen.getByRole('alert').textContent).toMatch(/formato válido/);
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('un CP de 4 dígitos se rechaza con mensaje', async () => {
    await alta();
    fireEvent.change(campo(/Código postal/), { target: { value: '9100' } });
    expect(screen.getByRole('alert').textContent).toMatch(/5 dígitos/);
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('editar un cliente existente SIN RFC y agregárselo lo guarda', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    const onGuardar = pintar(['viejo'], VIEJO);
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    // En la edición no son obligatorios: sin asterisco.
    expect(screen.getByLabelText(/^RFC$/)).toBeTruthy();

    fireEvent.change(campo(/^RFC/), { target: { value: 'VIEJ700101XY9' } });
    fireEvent.change(campo(/Entidad federativa/), { target: { value: 'CMX' } });
    fireEvent.click(screen.getByRole('button', { name: /^Guardar$/ }));

    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0]).toMatchObject({
      id: 'viejo', rfc: 'VIEJ700101XY9', clave_entidad: 'CMX', codigo_postal: '',
    });
  });

  it('en la edición un RFC mal formado también bloquea', async () => {
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar(['viejo'], { ...VIEJO, rfc: 'VIEJ700101XY9' });
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    fireEvent.change(campo(/^RFC/), { target: { value: 'VIEJ70' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^Guardar$/ })).toHaveProperty('disabled', true),
    );
  });

  it('un cliente sin régimen capturado se valida contra el 612 que la pantalla enseña', async () => {
    // El select pinta 612 y eso es lo que se guarda (T1): un RFC de 12 choca
    // contra ESE régimen, visible, no contra uno escondido.
    obtenerPrimasDeRiesgo.mockResolvedValue(PRIMAS);
    pintar(['viejo'], { ...VIEJO, rfc: 'VIE700101XY9' });
    await waitFor(() => expect(obtenerPrimasDeRiesgo).toHaveBeenCalled());
    expect((campo(/Régimen fiscal/) as HTMLSelectElement).value).toBe('612');
    expect(screen.getByRole('alert').textContent).toMatch(/612.*13 caracteres/);
  });
});
