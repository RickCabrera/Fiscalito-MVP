/**
 * El modo e2e (P6-04) no se cuela al build normal.
 *
 * Los dobles de Firebase de `src/e2e/` sólo entran al bundle por los alias de Vite, y esos
 * alias sólo existen con `VITE_E2E=1`. Aquí se fija: (1) sin la variable no hay alias,
 * (2) con ella se sustituyen exactamente los tres módulos del SDK, y (3) ningún módulo de
 * la app importa `src/e2e/` directamente (un import así metería los dobles a producción
 * sin pasar por el alias). `e2e/verificar-build.mjs` lo comprueba además sobre el `dist/`.
 */
// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { aliasesE2E, modoE2E } from './aliasesE2E';

const SRC = fileURLToPath(new URL('..', import.meta.url));

function archivos(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

describe('modo e2e del front', () => {
  it('sólo el valor exacto 1 lo enciende', () => {
    expect(modoE2E('1')).toBe(true);
    for (const v of [undefined, '', '0', 'true', ' 1']) expect(modoE2E(v)).toBe(false);
  });

  it('sin VITE_E2E no hay ningún alias', () => {
    expect(aliasesE2E(undefined, '/x/')).toEqual([]);
    expect(aliasesE2E('0', '/x/')).toEqual([]);
  });

  it('con VITE_E2E=1 sustituye exactamente los tres módulos del SDK', () => {
    const alias = aliasesE2E('1', '/x/');
    expect(alias.map((a) => a.replacement)).toEqual([
      '/x/firebaseAppFalso.ts', '/x/firebaseAuthFalso.ts', '/x/firestoreFalso.ts',
    ]);
    const [app, auth] = alias;
    expect(app.find.test('firebase/app')).toBe(true);
    expect(auth.find.test('firebase/auth')).toBe(true);
    // Coincidencia exacta: no se traga subrutas ni otros paquetes.
    expect(auth.find.test('firebase/auth/web-extension')).toBe(false);
    expect(app.find.test('xfirebase/app')).toBe(false);
  });

  it('ningún módulo de la app importa src/e2e', () => {
    const culpables = archivos(SRC)
      .filter((f) => /\.(ts|tsx)$/.test(f) && !relative(SRC, f).startsWith('e2e'))
      .filter((f) => /from\s+['"][./]*(?:\.\.\/)*e2e\//.test(readFileSync(f, 'utf8')));
    expect(culpables).toEqual([]);
  });
});
