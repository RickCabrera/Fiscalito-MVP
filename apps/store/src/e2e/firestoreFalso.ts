/**
 * `firebase/firestore` de las pruebas de punta a punta (P6-04).
 *
 * SÓLO entra al bundle con `VITE_E2E=1` (alias de `aliasesE2E.ts`). Cubre lo que usan
 * `ProfileContext` (perfil en `users/{uid}`) y `declaracionesHistory` (historial): rutas
 * de documento, `setDoc` con `merge`, consultas con `where('==')`, `orderBy` y `limit`.
 * Guarda en `localStorage`, así que el perfil sobrevive a recargar la página igual que en
 * Firestore, y cada prueba de Playwright empieza con un navegador limpio.
 */

const LLAVE = 'fiscalito_e2e_firestore';

export type DocumentData = Record<string, unknown>;

export class Timestamp {
  constructor(public seconds: number, public nanoseconds: number) {}
  static now(): Timestamp { return Timestamp.fromMillis(Date.now()); }
  static fromMillis(ms: number): Timestamp {
    return new Timestamp(Math.floor(ms / 1000), (ms % 1000) * 1e6);
  }
  static fromDate(d: Date): Timestamp { return Timestamp.fromMillis(d.getTime()); }
  toMillis(): number { return this.seconds * 1000 + Math.floor(this.nanoseconds / 1e6); }
  toDate(): Date { return new Date(this.toMillis()); }
  toJSON() { return { __ts: this.toMillis() }; }
}

type Tabla = Record<string, DocumentData>;

function revivir(_k: string, v: unknown): unknown {
  if (v && typeof v === 'object' && '__ts' in v) return Timestamp.fromMillis((v as { __ts: number }).__ts);
  return v;
}

function leer(): Tabla {
  try { return JSON.parse(localStorage.getItem(LLAVE) ?? '{}', revivir) as Tabla; } catch { return {}; }
}

function escribir(t: Tabla): void {
  localStorage.setItem(LLAVE, JSON.stringify(t));
}

export interface FirestoreFalso { tipo: 'firestore' }
export interface DocRef { tipo: 'doc'; path: string; id: string }
export interface ColRef { tipo: 'col'; path: string }
interface Restriccion { campo?: string; valor?: unknown; orden?: 'asc' | 'desc'; limite?: number; clase: string }
export interface Consulta { tipo: 'query'; col: ColRef; restricciones: Restriccion[] }

const DB: FirestoreFalso = { tipo: 'firestore' };

export function getFirestore(_app?: unknown): FirestoreFalso { void _app; return DB; }

function unir(base: { path?: string } | FirestoreFalso, partes: string[]): string {
  const raiz = 'path' in base && base.path ? [base.path] : [];
  return [...raiz, ...partes].join('/');
}

export function collection(base: FirestoreFalso | DocRef | ColRef, ...partes: string[]): ColRef {
  return { tipo: 'col', path: unir(base, partes) };
}

let contador = 0;
export function doc(base: FirestoreFalso | ColRef | DocRef, ...partes: string[]): DocRef {
  const extra = partes.length ? partes : [`auto${Date.now()}${contador++}`];
  const path = unir(base, extra);
  return { tipo: 'doc', path, id: path.split('/').pop() ?? '' };
}

function snapshotDoc(path: string, datos: DocumentData | undefined) {
  return { id: path.split('/').pop() ?? '', exists: () => datos !== undefined, data: () => datos };
}

export async function getDoc(ref: DocRef) {
  return snapshotDoc(ref.path, leer()[ref.path]);
}

export async function setDoc(ref: DocRef, datos: DocumentData, opciones?: { merge?: boolean }) {
  const t = leer();
  t[ref.path] = opciones?.merge ? { ...(t[ref.path] ?? {}), ...datos } : { ...datos };
  escribir(t);
}

export async function deleteDoc(ref: DocRef) {
  const t = leer();
  delete t[ref.path];
  escribir(t);
}

export function serverTimestamp(): Timestamp { return Timestamp.now(); }

export function where(campo: string, _op: '==', valor: unknown): Restriccion {
  void _op;
  return { clase: 'where', campo, valor };
}
export function orderBy(campo: string, orden: 'asc' | 'desc' = 'asc'): Restriccion {
  return { clase: 'orderBy', campo, orden };
}
export function limit(n: number): Restriccion { return { clase: 'limit', limite: n }; }

export function query(col: ColRef, ...restricciones: Restriccion[]): Consulta {
  return { tipo: 'query', col, restricciones };
}

function comparable(v: unknown): number | string {
  if (v instanceof Timestamp) return v.toMillis();
  return typeof v === 'number' ? v : String(v ?? '');
}

export async function getDocs(q: Consulta | ColRef) {
  const consulta: Consulta = q.tipo === 'query' ? q : { tipo: 'query', col: q, restricciones: [] };
  const prefijo = `${consulta.col.path}/`;
  let filas = Object.entries(leer())
    .filter(([p]) => p.startsWith(prefijo) && !p.slice(prefijo.length).includes('/'));
  for (const r of consulta.restricciones) {
    if (r.clase === 'where') filas = filas.filter(([, d]) => d[r.campo!] === r.valor);
    if (r.clase === 'orderBy') {
      const s = r.orden === 'desc' ? -1 : 1;
      filas = [...filas].sort(([, a], [, b]) =>
        comparable(a[r.campo!]) > comparable(b[r.campo!]) ? s : -s);
    }
    if (r.clase === 'limit') filas = filas.slice(0, r.limite);
  }
  const docs = filas.map(([p, d]) => snapshotDoc(p, d) as { id: string; data: () => DocumentData });
  return { docs, empty: docs.length === 0, size: docs.length };
}
