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
// Alcance de cliente (E-02)
// ────────────────────────────────────────────────────────────

/**
 * Rutas cuyo contenido depende del cliente activo del despacho.
 *
 * REGLA PARA AGREGAR UNA: no basta con que la pantalla HABLE de clientes; tiene
 * que LEER `useClienteActivo` y pedirle los datos a ese cliente. Si no, el
 * selector afirma un cliente y la pantalla enseña otro.
 *
 * `/app/nomina-demo` NO está aquí a propósito: hoy esa pantalla cae en los
 * defaults de `nominaDemoApi` (el cliente `demo`) y no mira el cliente activo.
 * Con el selector encima diría "Taller Nogal · 12 empleados" sobre los nueve
 * empleados del caso real, sus salarios y su PDF — y el guard del backend
 * (`routes/nomina.py`, que rechaza calcularle a un cliente la plantilla de
 * otro) nunca se dispararía, porque el front seguiría mandando `demo`.
 * **E-03 la cablea al cliente activo y entonces entra a esta lista** — y si
 * E-03 mueve la nómina a `/app/clientes/:id/nomina`, esta constante se mueve
 * con ella o el selector desaparece justo donde más se necesita.
 */
const RUTAS_CON_CLIENTE = ['/app/clientes'];

/**
 * Si la ruta habla de UN cliente. Decide dónde se muestra el selector de
 * cliente activo.
 *
 * Calendario y Perfil quedan fuera a propósito: son del DESPACHO. §D21 fija que
 * el calendario de una cuenta de despacho muestra sus obligaciones propias y
 * nada patronal, así que un selector de cliente ahí le mentiría al contador
 * sobre lo que está viendo.
 */
export function rutaTieneAlcanceDeCliente(pathname: string): boolean {
  return RUTAS_CON_CLIENTE.some((r) => pathname === r || pathname.startsWith(`${r}/`));
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
