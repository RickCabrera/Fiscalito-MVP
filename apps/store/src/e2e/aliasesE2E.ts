/**
 * Modo de pruebas de punta a punta del front (P6-04).
 *
 * Con `VITE_E2E=1` Vite sustituye el SDK de Firebase (`firebase/app`, `firebase/auth`,
 * `firebase/firestore`) por los dobles de esta carpeta: sesión por correo sin red y
 * Firestore en `localStorage`. **Sin la variable no hay alias**, y entonces nada de esta
 * carpeta es alcanzable desde `main.tsx`: ningún módulo de la app la importa (lo vigila
 * `aliasesE2E.test.ts`) y `e2e/verificar-build.mjs` revisa en CI que el `dist/` normal no
 * traiga la marca de los dobles.
 *
 * Aunque alguien compilara producción con el flag, el token que entrega el doble es el uid
 * literal, y el backend de producción lo rechaza: su atajo sin verificar está vetado con
 * `FISCALITO_ENTORNO=produccion` (`app/auth_firebase.sin_verificar_activo`).
 */

export interface AliasVite {
  find: RegExp;
  replacement: string;
}

/** Módulo del SDK → archivo del doble (relativo a esta carpeta). */
export const DOBLES_E2E: Record<string, string> = {
  'firebase/app': 'firebaseAppFalso.ts',
  'firebase/auth': 'firebaseAuthFalso.ts',
  'firebase/firestore': 'firestoreFalso.ts',
};

/** Si la variable pide el modo e2e. Sólo el valor exacto `1` lo enciende. */
export function modoE2E(valor: string | undefined): boolean {
  return valor === '1';
}

/** Alias de Vite para el modo e2e; vacío fuera de él. `carpeta` termina en `/`. */
export function aliasesE2E(valor: string | undefined, carpeta: string): AliasVite[] {
  if (!modoE2E(valor)) return [];
  return Object.entries(DOBLES_E2E).map(([modulo, archivo]) => ({
    find: new RegExp(`^${modulo.replace('/', '\\/')}$`),
    replacement: `${carpeta}${archivo}`,
  }));
}
