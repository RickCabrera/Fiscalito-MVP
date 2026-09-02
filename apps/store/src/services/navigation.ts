/**
 * Navegación por perfil — fuente única de qué ve cada tipo de cuenta.
 *
 * Módulo PURO a propósito (sin JSX, sin React): así se prueba sin jsdom y
 * las dos pantallas que dependían de copias divergentes de
 * `getTabsForProfile` importan la misma función.
 *
 * E-01: un CONTADOR no es un contribuyente. Lleva la nómina de sus clientes,
 * así que no ve pre-declaración, DIOT, retenciones ni historial propio.
 * Los tabs de contribuyente NO se borran: dejan de mostrarse.
 */

import type { ContributorType } from './contributorProfiles';

// ────────────────────────────────────────────────────────────
// Sidebar
// ────────────────────────────────────────────────────────────

/** Id estable de cada entrada del sidebar. AppLayout lo mapea a su icono. */
export type NavId = 'dashboard' | 'fiscalito' | 'historial' | 'nomina' | 'perfil' | 'clientes' | 'calendario';

export interface SidebarLink {
  id: NavId;
  to: string;
  label: string;
  /** `end` de NavLink: solo marca activo en coincidencia exacta. */
  end?: boolean;
}

/** Navegación del contribuyente — la de siempre, intacta. */
const LINKS_CONTRIBUYENTE: SidebarLink[] = [
  { id: 'dashboard', to: '/app', label: 'Dashboard', end: true },
  { id: 'fiscalito', to: '/app/store/fiscalito/use', label: 'Fiscalito' },
  { id: 'historial', to: '/app/historial', label: 'Historial' },
  // DEMO D-07: se borra en F2. Va en el sidebar y no sólo por URL porque el
  // criterio de la tarea es recorrer el flujo sin tocar consola, y teclear
  // una ruta a mano enfrente del cliente es justo lo que falla en vivo.
  { id: 'nomina', to: '/app/nomina-demo', label: 'Nómina (demo)' },
  { id: 'perfil', to: '/app/profile', label: 'Perfil' },
];

/**
 * Navegación del despacho. `calendario` apunta al tab de Fiscalito porque es
 * la única pantalla de ese servicio que le aplica (ver `getTabsForProfile`).
 */
const LINKS_CONTADOR: SidebarLink[] = [
  { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
  { id: 'nomina', to: '/app/nomina-demo', label: 'Nómina' },
  { id: 'calendario', to: '/app/store/fiscalito/use?tab=calendario', label: 'Calendario' },
  { id: 'perfil', to: '/app/profile', label: 'Perfil' },
];

export function esContador(tipo: ContributorType | null): boolean {
  return tipo === 'contador';
}

/** Links del sidebar para el perfil dado. `null` (perfil sin tipo) ve el de contribuyente. */
export function getSidebarLinks(tipo: ContributorType | null): SidebarLink[] {
  return esContador(tipo) ? LINKS_CONTADOR : LINKS_CONTRIBUYENTE;
}

/** Ruta a la que entra cada perfil al terminar el onboarding o al pedir `/app`. */
export function rutaInicial(tipo: ContributorType | null): string {
  return esContador(tipo) ? '/app/clientes' : '/app';
}

// ────────────────────────────────────────────────────────────
// Tabs del servicio Fiscalito
// ────────────────────────────────────────────────────────────

export type TabFiscalito =
  | 'declaracion' | 'deducciones' | 'calendario' | 'comparar'
  | 'diot' | 'retenciones' | 'multiperiodo' | 'estado';

/**
 * Tabs de Fiscalito que aplican al perfil. La usan `FiscalitoServicePage`
 * (para los tabs) y `DashboardPage` (para las cards de servicio): antes eran
 * dos copias idénticas y divergibles.
 *
 * OJO CON EL ORDEN: la rama de contador va PRIMERO. Un despacho tiene régimen
 * 612 o 626, así que si se evaluara después caería en la rama de RESICO o de
 * Actividad Empresarial y vería pre-declaración, DIOT y retenciones.
 */
export function getTabsForProfile(
  contributorType: string | null,
  regimen: string | null,
): TabFiscalito[] {
  // Contador: solo el calendario de sus propias obligaciones como despacho.
  if (contributorType === 'contador')
    return ['calendario'];

  if (contributorType === 'asalariado' || regimen === '605')
    return ['deducciones', 'calendario'];
  if (contributorType === 'pyme')
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  if (regimen === '626')
    return ['declaracion', 'calendario', 'comparar', 'estado'];
  if (regimen === '612')
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  if (contributorType === 'arrendamiento' || regimen === '606')
    return ['declaracion', 'calendario', 'comparar', 'multiperiodo', 'estado'];
  if (contributorType === 'plataformas' || regimen === '625')
    return ['declaracion', 'calendario', 'estado'];
  return ['declaracion', 'calendario', 'estado'];
}
