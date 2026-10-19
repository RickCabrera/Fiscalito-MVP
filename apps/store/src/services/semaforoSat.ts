/**
 * Semáforo de la opinión de cumplimiento (P1-05): tipos y etiquetas puros, sin red.
 *
 * Vive aparte de `satVerificacionApi.ts` para que los componentes que sólo PINTAN (la fila
 * de la cartera) no importen `api.ts` → `firebase.ts`, que lanza sin llaves en CI
 * (ver `sinLlavesDeFirebase.test.ts`).
 */

export type Semaforo = 'verde' | 'amarillo' | 'rojo' | 'gris';
export type ResultadoOpinion = 'positiva' | 'negativa' | 'sin_obligaciones' | 'desconocido';

export interface SemaforoCliente {
  clave: string;
  opinion: { semaforo: Semaforo; resultado: ResultadoOpinion | null; fecha: string | null };
  riesgos_69b: number;
}

export const ETIQUETA_SEMAFORO: Record<Semaforo, string> = {
  verde: 'Positiva',
  amarillo: 'Por actualizar',
  rojo: 'Negativa',
  gris: 'Sin dato',
};

export const COLOR_SEMAFORO: Record<Semaforo, string> = {
  verde: 'var(--success)',
  amarillo: 'var(--warning)',
  rojo: 'var(--danger)',
  gris: 'var(--text-muted)',
};
