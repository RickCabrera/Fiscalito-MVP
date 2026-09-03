/**
 * La Configuración de empresa, montada como la monta Perfil. (O-01)
 *
 * EL DEFECTO QUE ESTE ARCHIVO FIJA
 * --------------------------------
 * Un revisor lo midió con una sonda: la tarjeta siembra sus cinco campos del
 * prop con `useState`, que **sólo lee el primer render**, y la cartera resuelve
 * siempre después (lectura de Firestore, hasta 2500 ms). Con Orca ya capturada,
 * el operador veía los campos en blanco, el banner *"Falta la razón social y la
 * prima de riesgos de trabajo"* y la lista de errores en rojo.
 *
 * Y lo caro venía después: retecleaba lo que veía faltando, guardaba, y
 * `onGuardar` mandaba el RFC y el registro patronal desde el estado local
 * —vacíos—. Se perdían dos datos que nunca tocó, y el registro patronal es lo
 * único con lo que O-04 puede emitir un movimiento afiliatorio.
 *
 * Nadie lo cazaba porque `ProfilePage.test.tsx` declara `modoDespacho()` para
 * todo el archivo: la tarjeta no se renderiza en ninguna de sus pruebas.
 */

import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { carteraDePrueba } from '../../test/carteraDePrueba';
import type { CarteraContextType } from '../../context/carteraStore';
import { EMPRESA_POR_DEFECTO, type ConfigEmpresa } from '../../services/empresa';
import { PARAMETROS_DE_LEY } from '../../services/carteraApi';
import TarjetaEmpresa from './TarjetaEmpresa';

const ORCA: ConfigEmpresa = {
  razonSocial: 'Orca Ordorica Cristal Templado',
  rfc: 'OOC010101AAA',
  registroPatronal: 'A1234567890',
  primaRiesgo: '0.0113065',
  claseRiesgo: 3,
  zona: 'general',
  clavePeriodicidad: '04',
  parametros: PARAMETROS_DE_LEY,
};

function contexto(over: Partial<CarteraContextType> = {}): CarteraContextType {
  return carteraDePrueba({ origen: 'firestore', soloLectura: false, ...over });
}

describe('mientras la cartera carga, no se pinta la tarjeta', () => {
  it('enseña que está cargando, no cinco campos vacíos', () => {
    render(<TarjetaEmpresa cartera={contexto({ loading: true })} />);
    expect(screen.getByRole('status').textContent).toMatch(/Cargando la configuración/);
    expect(screen.queryByLabelText('Razón social')).toBeNull();
    cleanup();
  });
});

describe('cuando la empresa llega DESPUÉS del primer render', () => {
  it('los campos quedan con lo guardado, no en blanco', async () => {
    // Exactamente la secuencia real: monta cargando y resuelve con Orca.
    const { rerender } = render(<TarjetaEmpresa cartera={contexto({ loading: true })} />);
    rerender(<TarjetaEmpresa cartera={contexto({ empresa: ORCA })} />);

    await waitFor(() =>
      expect((screen.getByLabelText('Razón social') as HTMLInputElement).value).toBe(
        'Orca Ordorica Cristal Templado',
      ),
    );
    expect((screen.getByLabelText('RFC del patrón') as HTMLInputElement).value).toBe(
      'OOC010101AAA',
    );
    expect((screen.getByLabelText('Registro patronal (11)') as HTMLInputElement).value).toBe(
      'A1234567890',
    );
    // La prima se pinta en PORCENTAJE aunque se guarde en fracción.
    expect((screen.getByLabelText('Prima de riesgo (%)') as HTMLInputElement).value).toBe(
      '1.13065',
    );
    cleanup();
  });

  it('y NO afirma que falten datos que sí están', async () => {
    const { rerender } = render(<TarjetaEmpresa cartera={contexto({ loading: true })} />);
    rerender(<TarjetaEmpresa cartera={contexto({ empresa: ORCA })} />);

    await waitFor(() => expect(screen.getByLabelText('Razón social')).toBeTruthy());
    expect(screen.queryByText(/Falta la razón social/)).toBeNull();
    expect(screen.queryByText(/La razón social es obligatoria/)).toBeNull();
    cleanup();
  });
});

describe('la relectura DESPUÉS de guardar re-siembra los campos', () => {
  /**
   * EL CASO QUE EJERCITA EL `key`, Y EL ÚNICO QUE MUERE SI SE QUITA.
   *
   * Al guardar, `CarteraProvider` dispara una relectura **sin volver a
   * `loading`**: `alDia` sigue en `true` porque el uid no cambió. Así que la
   * tarjeta se queda MONTADA mientras los valores nuevos llegan, y `useState`
   * ya no los va a leer — sus inicializadores corrieron una sola vez.
   *
   * Sin el `key`, la pantalla se queda mostrando lo viejo después de guardar:
   * el operador corrige un dato, ve "Guardado", y el campo sigue diciendo lo
   * anterior. Con dos pestañas o dos correcciones seguidas, guarda lo viejo
   * encima de lo nuevo.
   */
  it('los valores nuevos reemplazan a los viejos sin desmontar por `loading`', async () => {
    const { rerender } = render(
      <TarjetaEmpresa cartera={contexto({ empresa: EMPRESA_POR_DEFECTO })} />,
    );
    // Estaba montada y vacía, sin pasar por el esqueleto de carga.
    expect((screen.getByLabelText('Razón social') as HTMLInputElement).value).toBe('');

    rerender(<TarjetaEmpresa cartera={contexto({ empresa: ORCA })} />);

    await waitFor(() =>
      expect((screen.getByLabelText('Razón social') as HTMLInputElement).value).toBe(
        'Orca Ordorica Cristal Templado',
      ),
    );
    expect((screen.getByLabelText('Registro patronal (11)') as HTMLInputElement).value).toBe(
      'A1234567890',
    );
    cleanup();
  });
});

describe('guardar no pierde lo que el operador no tocó', () => {
  it('el RFC y el registro patronal viajan tal como estaban guardados', async () => {
    const guardarEmpresa = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<TarjetaEmpresa cartera={contexto({ loading: true })} />);
    rerender(<TarjetaEmpresa cartera={contexto({ empresa: ORCA, guardarEmpresa })} />);

    await waitFor(() => expect(screen.getByLabelText('Razón social')).toBeTruthy());

    // El operador cambia SÓLO la razón social y guarda.
    fireEvent.change(screen.getByLabelText('Razón social'), {
      target: { value: 'Orca Ordorica S.A. de C.V.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Guardar empresa/ }));

    await waitFor(() => expect(guardarEmpresa).toHaveBeenCalled());
    const enviado = guardarEmpresa.mock.calls[0][0] as ConfigEmpresa;
    expect(enviado.razonSocial).toBe('Orca Ordorica S.A. de C.V.');
    // LO QUE VALE EL TEST: estos dos no se tocaron y no pueden llegar vacíos.
    expect(enviado.rfc).toBe('OOC010101AAA');
    expect(enviado.registroPatronal).toBe('A1234567890');
    expect(enviado.primaRiesgo).toBe('0.0113065');
    // Y la periodicidad, que ni siquiera se pinta en esta tarjeta.
    expect(enviado.clavePeriodicidad).toBe('04');
    cleanup();
  });
});

describe('la empresa sin configurar dice qué falta', () => {
  it('lo enumera en vez de dejar el formulario mudo', () => {
    render(<TarjetaEmpresa cartera={contexto({ empresa: EMPRESA_POR_DEFECTO })} />);
    expect(screen.getByRole('status').textContent).toMatch(/Falta la razón social/);
    expect(screen.getByRole('status').textContent).toMatch(/prima de riesgos de trabajo/);
    cleanup();
  });

  it('y no deja guardar hasta que estén', () => {
    render(<TarjetaEmpresa cartera={contexto({ empresa: EMPRESA_POR_DEFECTO })} />);
    const boton = screen.getByRole('button', { name: /Guardar empresa/ }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    cleanup();
  });
});
