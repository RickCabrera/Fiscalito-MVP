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
 * Navegación del despacho.
 *
 * E-07: `calendario` dejó de apuntar al tab de Fiscalito. Ese tab muestra las
 * declaraciones ISR/IVA de un CONTRIBUYENTE, que a un despacho de nómina no le
 * aplican; ahora lleva al calendario **patronal** de sus clientes.
 */
const LINKS_CONTADOR: SidebarLink[] = [
  { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
  { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
  { id: 'calendario', to: '/app/calendario', label: 'Calendario' },
  { id: 'perfil', to: '/app/profile', label: 'Perfil' },
];

export function esContador(tipo: ContributorType | null): boolean {
  return tipo === 'contador';
}

// ────────────────────────────────────────────────────────────
// Qué entrada del sidebar va resaltada (E-06)
// ────────────────────────────────────────────────────────────

/** `/app/clientes/{id}/nomina`, la ruta real de la pantalla desde E-03. */
const RE_NOMINA_DE_CLIENTE = /^\/app\/clientes\/[^/]+\/nomina\/?$/;

/**
 * Si la ruta ES la nómina, viva donde viva.
 *
 * `/app/nomina` sólo resuelve el cliente activo y redirige, así que las dos
 * formas tienen que contar. `/app/nomina-demo` NO está aquí y no es un olvido:
 * es un `<Navigate>` (`AppRoutes.tsx`), nunca se pinta un sidebar sobre esa
 * ruta, y un caso de prueba inalcanzable no prueba nada.
 */
export function esRutaDeNomina(pathname: string): boolean {
  return pathname === '/app/nomina' || RE_NOMINA_DE_CLIENTE.test(pathname);
}

function bajoLaRuta(pathname: string, destino: string): boolean {
  return pathname === destino || pathname.startsWith(`${destino}/`);
}

/**
 * Si un enlace del sidebar debe verse activo en esta ruta.
 *
 * POR QUÉ NO LO DECIDE `NavLink`
 * ------------------------------
 * La nómina cuelga de `/app/clientes/{id}/nomina`, así que el `isActive` de
 * `NavLink` marcaba **Clientes** —su `to` es prefijo de la ruta— y dejaba
 * **Nómina** apagado: el sidebar señalaba la sección equivocada justo en la
 * pantalla de la demo. Aquí la nómina se queda la ruta y Clientes la suelta.
 *
 * Es función pura del par (enlace, pathname): se prueba sin jsdom, y
 * `AppLayout` la usa también para el `aria-current`, que si no seguiría
 * anunciando "Clientes" aunque el color cambiara.
 */
export function navActivo(link: SidebarLink, pathname: string): boolean {
  if (link.id === 'nomina') return esRutaDeNomina(pathname);
  // Clientes cubre la cartera y la ficha, pero NO la nómina del cliente: dos
  // entradas encendidas a la vez no señalan nada.
  if (link.id === 'clientes') {
    return bajoLaRuta(pathname, '/app/clientes') && !esRutaDeNomina(pathname);
  }
  // El resto conserva la semántica de `NavLink`: `end` compara exacto y el
  // query string del destino no participa (el tab lo resuelve la pantalla).
  const destino = link.to.split('?')[0];
  return link.end ? pathname === destino : bajoLaRuta(pathname, destino);
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
 * Calendario y Perfil quedan fuera a propósito. Perfil es del DESPACHO. Y
 * Calendario, desde E-07, **sí** es patronal —§D21 quedó resuelta— pero es el de
 * TODA la cartera: un selector de "cliente activo" encima de una lista que
 * mezcla los tres clientes afirmaría un alcance que la pantalla no tiene. La
 * regla de admisión no cambia: entra la ruta que LEE un cliente y le pide sus
 * datos, no la que habla de clientes.
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
  // Contador: NINGÚN tab de Fiscalito.
  //
  // Hasta E-06 veía el de calendario, con sus propias obligaciones como persona
  // física (§D21). E-05 deja de pedirle RFC y régimen —y quita del perfil el
  // único lugar donde capturarlos—, así que ese tab quedaba muerto: `CalendarioTab`
  // corta en seco sin esos dos campos. Antes que dejar un callejón con letrero,
  // se decide de frente: una cuenta de despacho no tiene calendario de
  // contribuyente, y `FiscalitoServicePage` la manda a `/app/calendario`, que es
  // el patronal de sus clientes. Consecuencia declarada en §D21: la app ya no
  // calcula las obligaciones propias del despacho.
  if (contributorType === 'contador')
    return [];

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
