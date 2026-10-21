/**
 * `firebase/app` de las pruebas de punta a punta (P6-04). SÓLO existe en el bundle cuando
 * se compila con `VITE_E2E=1` (ver `aliasesE2E.ts`); el build normal usa el SDK real.
 *
 * No hay red a Firebase en e2e: la app se inicializa contra nada.
 */

export const MARCA_FIREBASE_FALSO = 'FISCALITO_E2E_FIREBASE_FALSO';

export interface AppFalsa {
  name: string;
  marca: string;
}

export function initializeApp(_config?: unknown): AppFalsa {
  void _config;
  return { name: '[e2e]', marca: MARCA_FIREBASE_FALSO };
}

export default { initializeApp };
