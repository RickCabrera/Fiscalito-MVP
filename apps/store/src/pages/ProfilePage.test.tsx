/**
 * Perfil del despacho (E-01).
 *
 * POR QUÉ EXISTE: quitar `nombreDespacho` del `handleSave` no rompe nada de
 * forma visible — `setProfile` hace `{...profile, ...data}`, así que el valor
 * viejo sobrevive, el formulario sigue mostrando lo que el usuario tecleó y la
 * pantalla dice "Guardado correctamente". Es una pérdida silenciosa con mensaje
 * de éxito, en la pantalla donde un contador corrige el nombre de su despacho.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { CarteraContext } from '../context/carteraStore';
import { carteraDePrueba } from '../test/carteraDePrueba';


const perfilContador: UserProfile = {
  contributorType: 'contador',
  rfc: 'XAXX010101000',
  regimen: '612',
  nombre: 'Contadora Demo',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  nombreDespacho: 'Despacho Demo',
  onboardingComplete: true,
};

const perfilMock = { actual: perfilContador };
const setProfile = vi.fn<(data: Partial<UserProfile>) => Promise<void>>(async () => {});

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false, setProfile }),
}));

const { default: ProfilePage } = await import('./ProfilePage');

/**
 * O-01: `ProfilePage` lee la cartera para la Configuración de empresa.
 *
 * El hook es incondicional —no se pueden llamar hooks dentro de un `if`— así
 * que el proveedor hace falta en los dos modos, aunque la sección sólo se pinte
 * en empresa única. Se usa el mismo doble que el resto de las pantallas en vez
 * de montar el proveedor real, que hablaría con Firestore: la red está cerrada
 * por default en estos tests.
 *
 * T8: y el `MemoryRouter`, porque la tarjeta de plan enlaza a `/app/planes`.
 * **Ninguna aserción de este archivo cambia** — lo que cambia es el entorno que
 * el componente necesita para montarse, igual que el proveedor de cartera de
 * arriba. Sin router, `<Link>` lanza y las nueve pruebas se caen juntas por una
 * razón que no tiene nada que ver con lo que miden.
 */
function pintar() {
  return render(
    <MemoryRouter>
      <CarteraContext.Provider value={carteraDePrueba()}>
        <ProfilePage />
      </CarteraContext.Provider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilContador;
  setProfile.mockClear();
  cleanup();
});

describe('ProfilePage — perfil de despacho', () => {
  it('muestra el nombre del despacho y no los campos de PYME', () => {
    pintar();

    const input = screen.getByPlaceholderText('Despacho Contable Ejemplo') as HTMLInputElement;
    expect(input.value).toBe('Despacho Demo');
    expect(screen.queryByPlaceholderText('Mi Empresa S.A. de C.V.')).toBeNull();
  });

  it('guarda el nombre del despacho editado', async () => {
    pintar();

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo y Asociados' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    expect(setProfile.mock.calls[0][0]).toMatchObject({
      nombreDespacho: 'Despacho Demo y Asociados',
    });
  });

  /** K: no hay tipos de cuenta a los que cambiarse; el sistema es solo para despachos. */
  it('no ofrece cambiarse a otro tipo de cuenta', () => {
    pintar();

    for (const otro of ['Asalariado', 'Independiente / Freelancer', 'Arrendamiento',
      'Plataformas digitales', 'Negocio / PYME']) {
      expect(screen.queryByText(otro)).toBeNull();
    }
    expect(screen.getByRole('heading', { name: 'Perfil del despacho' })).toBeTruthy();
  });

  it('no le pide RFC, régimen, actividad ni código postal', () => {
    pintar();

    expect(screen.queryByPlaceholderText('XAXX010101000')).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByText('Actividad economica')).toBeNull();
    expect(screen.queryByText(/Codigo postal/)).toBeNull();
  });

  it('guardar sólo manda los datos del despacho: no toca el tipo de cuenta ni datos fiscales', async () => {
    // `setProfile` hace merge: lo que no viaja se conserva tal cual.
    pintar();
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    const guardado = setProfile.mock.calls[0][0];
    expect(Object.keys(guardado).sort()).toEqual(['nombre', 'nombreDespacho', 'telefono']);
  });
});
