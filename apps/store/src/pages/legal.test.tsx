/** P6-01: aviso de privacidad y términos, públicos, con placeholders y banda de abogado. */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AvisoPrivacidadPage from './AvisoPrivacidadPage';
import TerminosPage from './TerminosPage';

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

function montar(elemento: React.ReactElement) {
  return render(<MemoryRouter>{elemento}</MemoryRouter>);
}

describe('páginas legales', () => {
  it('el aviso no inventa al responsable: sin variables pinta POR DEFINIR', () => {
    vi.stubEnv('VITE_RESPONSABLE_NOMBRE', '');
    montar(<AvisoPrivacidadPage />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Aviso de privacidad');
    expect(screen.getByRole('note').textContent).toContain('REVISAR CON ABOGADO');
    expect(screen.getAllByText(/POR DEFINIR: nombre o razón social/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Derechos ARCO/)).toBeTruthy();
  });

  it('con las variables, usa los datos del responsable', () => {
    vi.stubEnv('VITE_RESPONSABLE_NOMBRE', 'Ejemplo Sintético S.A. de C.V.');
    vi.stubEnv('VITE_RESPONSABLE_CORREO', 'privacidad@ejemplo.mx');
    montar(<AvisoPrivacidadPage />);
    expect(screen.getAllByText(/Ejemplo Sintético S\.A\. de C\.V\./).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/privacidad@ejemplo\.mx/).length).toBeGreaterThan(0);
  });

  it('los términos llevan la banda y enlazan al aviso', () => {
    montar(<TerminosPage />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Términos');
    expect(screen.getByRole('note').textContent).toContain('REVISAR CON ABOGADO');
    const enlaces = screen.getAllByRole('link', { name: /aviso de privacidad/i });
    expect(enlaces.some((a) => a.getAttribute('href') === '/privacidad')).toBe(true);
  });
});
