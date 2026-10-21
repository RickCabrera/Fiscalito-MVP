/**
 * `firebase/auth` de las pruebas de punta a punta (P6-04).
 *
 * SÓLO entra al bundle con `VITE_E2E=1` (alias de `aliasesE2E.ts`). El build de producción
 * no lo incluye — lo vigilan `aliasesE2E.test.ts` y `e2e/verificar-build.mjs` en CI.
 *
 * El ID token que entrega es el **uid literal**. El backend sólo lo acepta con su atajo de
 * pruebas encendido (`PERMITIR_TOKEN_SIN_VERIFICAR=1` + `FIRESTORE_EMULATOR_HOST`, vetado
 * en `FISCALITO_ENTORNO=produccion`; ver `app/auth_firebase.sin_verificar_activo`). Contra
 * una API de verdad este token es un 401: no abre nada.
 */

const LLAVE_SESION = 'fiscalito_e2e_sesion';

export interface UsuarioFalso {
  uid: string;
  email: string | null;
  displayName: string | null;
  getIdToken: () => Promise<string>;
}

type Oyente = (u: UsuarioFalso | null) => void;

interface AuthFalsa {
  currentUser: UsuarioFalso | null;
  oyentes: Set<Oyente>;
}

/** uid estable por correo: `e2e-<correo sin símbolos>`. */
export function uidDeCorreo(correo: string): string {
  return `e2e-${correo.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
}

function usuario(correo: string): UsuarioFalso {
  const uid = uidDeCorreo(correo);
  return { uid, email: correo, displayName: null, getIdToken: async () => uid };
}

function leerSesion(): UsuarioFalso | null {
  try {
    const correo = localStorage.getItem(LLAVE_SESION);
    return correo ? usuario(correo) : null;
  } catch {
    return null;
  }
}

const AUTH: AuthFalsa = { currentUser: leerSesion(), oyentes: new Set() };

function avisar(): void {
  for (const o of AUTH.oyentes) o(AUTH.currentUser);
}

function entrar(correo: string): void {
  if (!correo.includes('@')) throw new Error('auth/invalid-email');
  localStorage.setItem(LLAVE_SESION, correo);
  AUTH.currentUser = usuario(correo);
  avisar();
}

export function getAuth(_app?: unknown): AuthFalsa {
  void _app;
  return AUTH;
}

export function onAuthStateChanged(auth: AuthFalsa, oyente: Oyente): () => void {
  auth.oyentes.add(oyente);
  // Firebase avisa el estado inicial de forma asíncrona.
  setTimeout(() => oyente(auth.currentUser), 0);
  return () => { auth.oyentes.delete(oyente); };
}

export async function signInWithEmailAndPassword(_a: AuthFalsa, correo: string, _p: string) {
  void _p;
  entrar(correo);
  return { user: AUTH.currentUser };
}

export async function createUserWithEmailAndPassword(a: AuthFalsa, correo: string, p: string) {
  return signInWithEmailAndPassword(a, correo, p);
}

export class GoogleAuthProvider {}

export async function signInWithPopup(_a: AuthFalsa, _p: GoogleAuthProvider) {
  void _p;
  entrar('google-e2e@fiscalito.test');
  return { user: AUTH.currentUser };
}

export async function signOut(_a: AuthFalsa): Promise<void> {
  void _a;
  localStorage.removeItem(LLAVE_SESION);
  AUTH.currentUser = null;
  avisar();
}

export type User = UsuarioFalso;
