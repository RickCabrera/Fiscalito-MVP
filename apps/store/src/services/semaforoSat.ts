/**
 * Semáforo de la opinión de cumplimiento (P1-05): tipos y etiquetas puros, sin red.
 *
 * Vive aparte de `satVerificacionApi.ts` para que los componentes que sólo PINTAN (la fila
 * de la cartera) no importen `api.ts` → `firebase.ts`, que lanza sin llaves en CI
 * (ver `sinLlavesDeFirebase.test.ts`).
 */

export type Semaforo = 'verde' | 'amarillo' | 'rojo' | 'gris';
export type ResultadoOpinion = 'positiva' | 'negativa' | 'sin_obligaciones' | 'desconocido';

/** De dónde salió la última opinión: `falso` es simulada; `manual` la subió el despacho. */
export type OrigenOpinion = 'falso' | 'portal_sat' | 'proveedor' | 'manual';

export interface SemaforoCliente {
  clave: string;
  opinion: {
    semaforo: Semaforo;
    resultado: ResultadoOpinion | null;
    fecha: string | null;
    origen: OrigenOpinion | null;
    /** Advertencia honesta del servidor (simulada / no verificada); null si no aplica. */
    marca: string | null;
  };
  riesgos_69b: number;
  /** Pólizas de CFDI cancelados que no se pudieron cancelar ni revertir. */
  alertas_contables?: number;
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

/**
 * Etiqueta del semáforo que no engaña: una opinión simulada (adaptador `falso`) dice
 * "Simulado" aunque el PDF diga positiva, y una subida a mano lo aclara.
 */
export function etiquetaSemaforo(s: Semaforo, origen?: OrigenOpinion | null): string {
  if (origen === 'falso') return 'Simulado';
  if (origen === 'manual' && s !== 'gris') return `${ETIQUETA_SEMAFORO[s]} (según PDF subido, no verificado)`;
  return ETIQUETA_SEMAFORO[s];
}
