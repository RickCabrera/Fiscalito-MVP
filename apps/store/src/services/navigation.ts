/**
 * Navegación — fuente única de qué ve la cuenta.
 *
 * Desde K (2026-10-19) el sistema es SOLO para despachos y contadores: no hay
 * navegación de contribuyente ni modo empresa única. Toda cuenta que entra es un
 * despacho y opera sobre el cliente activo.
 *
 * Módulo PURO a propósito (sin JSX, sin React): así se prueba sin jsdom y
 * las dos pantallas que dependían de copias divergentes de
 * `getTabsForProfile` importan la misma función.
 *
 * E-01: un CONTADOR no es un contribuyente. Lleva la nómina de sus clientes,
 * así que no ve pre-declaración, DIOT, retenciones ni historial propio. Los tabs
 * de contribuyente NO se borran: dejan de mostrarse.
 *
 * T1: el despacho sí ve pre-declaración, DIOT y retenciones — pero **las del
 * cliente que tenga activo**, filtradas por el régimen de ESE cliente. No
 * contradice a E-01: la extiende por el otro lado. Lo que E-01 le negó fue lo
 * SUYO, y eso sigue negado —su historial y su dashboard de contribuyente no
 * existen, y desde E-05 ni siquiera se le pide régimen propio.
 */

import type { ContributorType } from './contributorProfiles';
import { MARCA_CORTA } from './marca';

// ────────────────────────────────────────────────────────────
// Sidebar
// ────────────────────────────────────────────────────────────

/** Id estable de cada entrada del sidebar. AppLayout lo mapea a su icono. */
export type NavId =
  | 'fiscalito' | 'contabilito' | 'nomina' | 'perfil'
  | 'clientes' | 'empleados' | 'dispositivos' | 'boveda' | 'sat' | 'calendario'
  | 'calculadoras';

export interface SidebarLink {
  id: NavId;
  to: string;
  label: string;
  /** `end` de NavLink: solo marca activo en coincidencia exacta. */
  end?: boolean;
}

/**
 * Navegación del despacho.
 *
 * E-07: `calendario` dejó de apuntar al tab de Fiscalito. Ese tab muestra las
 * declaraciones ISR/IVA de un CONTRIBUYENTE, que a un despacho de nómina no le
 * aplican; ahora lleva al calendario **patronal** de sus clientes.
 */
const LINKS_CONTADOR: SidebarLink[] = [
  { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
  // R-05: Empleados y Dispositivos son entradas propias, no pestañas escondidas
  // dentro de la ficha. Operan sobre el cliente activo, igual que Nómina.
  { id: 'empleados', to: '/app/empleados', label: 'Empleados' },
  { id: 'dispositivos', to: '/app/dispositivos', label: 'Dispositivos' },
  // P0-03: la bóveda de CFDI del cliente activo. Va antes de Nómina porque es
  // de donde todo lo demás leerá sus comprobantes (P1-06).
  { id: 'boveda', to: '/app/boveda', label: 'Bóveda' },
  // P1-02: la descarga masiva del SAT llena la bóveda del cliente activo; va
  // justo después de ella porque es de donde salen sus comprobantes.
  { id: 'sat', to: '/app/sat', label: 'Descarga SAT' },
  { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
  { id: 'calendario', to: '/app/calendario', label: 'Calendario' },
  // T1: el despacho recupera el servicio fiscal, pero **el del CLIENTE ACTIVO**,
  // no el suyo propio. E-07 lo había quitado porque el único tab que le quedaba
  // —su calendario como persona física— dependía de un RFC y un régimen que E-05
  // dejó de pedirle; ése sigue sin aplicar, y por eso `calendario` de arriba
  // sigue apuntando al PATRONAL de sus clientes y no a un tab de Fiscalito.
  // Va después de Calendario y antes de Perfil: es herramienta, no ajuste.
  { id: 'fiscalito', to: '/app/store/fiscalito/use', label: MARCA_CORTA },
  // Contabilito estaba en BETA en la landing y **no tenía puerta**: la pantalla
  // de T7 existía y se routeaba, pero al contador sólo se llegaba tecleando la
  // URL o dando el rodeo por Marketplace → detalle del servicio → "Usar
  // Contabilito". Va justo debajo de Fiscalito porque es la otra herramienta
  // que opera sobre el CLIENTE ACTIVO, y la ruta es la misma que ya usaba el
  // botón del detalle: no hay una segunda forma de entrar que mantener.
  { id: 'contabilito', to: '/app/store/contabilito/use', label: 'Contabilito' },
  // P3-08: herramientas sueltas del despacho. SIN alcance de cliente (no lee el
  // cliente activo), por eso no está en `RUTAS_CON_CLIENTE`. Va antes de Perfil:
  // es herramienta, no ajuste.
  { id: 'calculadoras', to: '/app/calculadoras', label: 'Calculadoras' },
  { id: 'perfil', to: '/app/profile', label: 'Perfil' },
];

/**
 * Si este perfil es el que OPERA la nómina.
 *
 * El nombre se queda —`contributorType: 'contador'` es la llave guardada en
 * Firestore de todas las cuentas que ya existen, y renombrarla sería una
 * migración de datos a cambio de nada— pero lo que significa depende del modo:
 * en modo despacho es el contador que lleva varios clientes; en modo empresa
 * única es quien lleva la nómina de la empresa. Ver `etiquetaDelPerfilOperador`.
 */
export function esContador(tipo: ContributorType | null): boolean {
  return tipo === 'contador';
}

/**
 * Si la cuenta ya puede usar la app (K).
 *
 * El sistema es solo para despachos: una cuenta vieja de contribuyente cuenta
 * como onboarding SIN terminar, así que `AppLayout` la manda al wizard, que sólo
 * ofrece despacho, y al terminarlo queda convertida.
 */
export function cuentaLista(p: {
  onboardingComplete: boolean;
  contributorType: ContributorType | null;
}): boolean {
  return p.onboardingComplete && esContador(p.contributorType);
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
  // R-05: Empleados y Dispositivos son rutas HERMANAS de `/app/clientes`
  // (`/app/empleados`), no hijas (`/app/clientes/x/empleados`), así que
  // `bajoLaRuta` no las confunde y no hace falta restarlas como se restó la
  // nómina. Se fija con test: si alguien las moviera a colgar de `/app/clientes`
  // volvería el bug de E-06 —dos entradas encendidas— sin que nada avise.
  //
  // Del resto se conserva la semántica de `NavLink`: `end` compara exacto y el
  // query string del destino no participa (el tab lo resuelve la pantalla).
  const destino = link.to.split('?')[0];
  return link.end ? pathname === destino : bajoLaRuta(pathname, destino);
}

/** Links del sidebar. Desde K sólo existe la navegación del despacho. */
export function getSidebarLinks(): SidebarLink[] {
  return LINKS_CONTADOR;
}

/** Ruta a la que entra la cuenta al terminar el onboarding o al pedir `/app`. */
export function rutaInicial(): string {
  return '/app/clientes';
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
 */
const RUTAS_CON_CLIENTE = [
  '/app/clientes', '/app/empleados', '/app/dispositivos',
  // P0-03: CUMPLE la regla — `BovedaPage` lee `useClienteActivo` y pide la
  // bóveda de ESE cliente (`/boveda/clientes/{clave}/cfdi`).
  '/app/boveda',
  // P1-02: CUMPLE la regla — `DescargaSatPage` lee `useClienteActivo` y pide
  // config, bitácora y solicitudes de ESE cliente (`/sat/clientes/{clave}/...`).
  '/app/sat',
  // K: `/app/nomina` sin cliente activo pinta "Elige un cliente primero"; con el
  // selector encima se elige ahí mismo y `NominaDelClienteActivo` redirige a la
  // nómina de ese cliente. Con cliente, la nómina vive en
  // `/app/clientes/{id}/nomina`, que ya cae bajo `/app/clientes`.
  '/app/nomina',
  // T1: entra porque CUMPLE la regla de admisión de arriba, no porque hable de
  // clientes. `FiscalitoServicePage` lee `useClienteActivo` y filtra sus tabs
  // con el régimen de ese cliente; sin el selector encima, el contador no
  // tendría cómo cambiar de cliente sin salirse de la pantalla, y la pantalla
  // estaría afirmando un régimen que él no eligió.
  //
  // `/use` y no `/app/store/fiscalito` a secas: la ficha del servicio es texto
  // de catálogo, no lee cliente alguno, y el prefijo corto la habría metido de
  // contrabando junto con la pantalla que sí lo lee.
  '/app/store/fiscalito/use',
  // Contabilito CUMPLE la regla de admisión, igual que Fiscalito: lee
  // `ClienteActivoContext` y titula "Pólizas y balanza de {cliente}". Sin el
  // selector encima, el contador entraría desde el sidebar a la contabilidad
  // de un cliente que no eligió en esta pantalla y sin forma de cambiarlo.
  //
  // `/use` y no `/app/store/contabilito` a secas: la ficha del servicio es
  // texto de catálogo y no lee cliente alguno.
  '/app/store/contabilito/use',
];

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
  | 'declaracion' | 'anual' | 'deducciones' | 'calendario' | 'comparar'
  | 'diot' | 'retenciones' | 'multiperiodo' | 'estado' | 'pagospm' | 'resumen';

/**
 * Los tabs de una PERSONA MORAL (601) — T6, cascarón.
 *
 * `pagospm` primero **porque es el tab por defecto**: `allowedTabIds[0]` es lo
 * que la pantalla abre, y abrir en `declaracion` sería recibir a la PM con la
 * única pantalla que no le sirve.
 *
 * `declaracion` entra a propósito aunque el motor no la soporte: la tarea pide
 * que quede **deshabilitada con mensaje**, no escondida. Escondida, el contador
 * no tiene cómo saber si es que la PM no declara o es que el producto todavía
 * no puede; `FiscalitoServicePage` la reemplaza por el aviso. El resto —anual,
 * comparar, DIOT, retenciones, multi-periodo, estado de cuenta— sí se queda
 * fuera: todas salen del mismo motor de persona física y no hay nada honesto
 * que pintar en ellas para una moral.
 */
const TABS_601: readonly TabFiscalito[] = Object.freeze<TabFiscalito[]>([
  // P3-01/P3-06: con el motor PM, `pagospm` ya calcula en el backend y la moral
  // tiene su anual (ajuste por inflación, PTU, pérdidas, papeles de trabajo).
  'pagospm', 'anual', 'calendario', 'declaracion',
  // P3-02: el resumen de impuestos; su ISR propio sale del motor PM (P3-01).
  'resumen',
]);

/**
 * El set completo: el de `pyme` y el de un 612.
 *
 * Congelado, y **se devuelve copiado** (`tabsCompletos()`), no por referencia.
 * Antes cada rama de `getTabsForProfile` construía su propio literal, así que
 * extraer la constante introdujo un arreglo compartido entre cuatro ramas: un
 * `.sort()` o un `.push()` de un consumidor futuro le habría cambiado los tabs a
 * todos los perfiles a la vez, y eso se ve bien hasta que no. Hoy nadie lo muta
 * —los dos consumidores sólo hacen `.includes()` y `[0]`— pero la trampa era
 * nueva y la cerró el revisor de T1.
 */
const TABS_COMPLETOS: readonly TabFiscalito[] = Object.freeze<TabFiscalito[]>([
  'declaracion', 'anual', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado',
  'resumen',
]);

/** Copia fresca del set completo, para no repartir la misma referencia. */
function tabsCompletos(): TabFiscalito[] {
  return [...TABS_COMPLETOS];
}

/**
 * Tabs de Fiscalito para el CLIENTE ACTIVO del despacho, por su régimen.
 *
 * Desde K no hay contribuyentes: el sujeto del cálculo siempre es un cliente.
 * Sin cliente elegido (`regimen` vacío) no hay tabs: la pantalla pinta el estado
 * vacío con el selector en vez de tabs sobre un cliente inexistente.
 */
export function getTabsForProfile(regimen: string | null, rfc?: string | null): TabFiscalito[] {
  if (!regimen) return [];
  // P3-01: un 626 con RFC de persona moral (12 caracteres) es RESICO PM (Arts. 206-215
  // LISR): su ISR es el del motor de morales, no el RESICO de personas físicas.
  if (regimen === '626' && (rfc ?? '').trim().length === 12) {
    return ['pagospm', 'anual', 'calendario', 'resumen'];
  }
  return tabsPorRegimenDeCliente(regimen);
}

/**
 * Tabs que se le pueden trabajar a un cliente del despacho, por su régimen.
 *
 * Los dos regímenes que `contributorProfiles.ts` declara para el perfil
 * `contador` —y los dos únicos que el alta de cliente ofrece— son 612 y 626, y
 * son los que deciden el caso que importa: a un 626 no se le ofrecen DIOT ni
 * Retenciones.
 *
 * **ESE CORTE ES HEREDADO, NO VERIFICADO.** La rama `regimen === '626'` de abajo
 * existe desde E-01 y T1 no la inventó: lo que T1 cambió es a quién se le aplica
 * (el cliente del despacho, no el contribuyente). **Pendiente de confirmar con
 * la contadora: `docs/decisiones-nomina.md` §D30**, donde queda escrito por qué
 * DIOT y Retenciones son dos preguntas separadas y por qué la de Retenciones
 * probablemente no se contesta con el régimen.
 *
 * El resto de los regímenes no se inventa: si algún día el alta de cliente
 * abriera 605, 606 o 625, esto ya responde lo mismo que responde para un
 * contribuyente de ese régimen, en vez de degradar al set completo en silencio.
 */
function tabsPorRegimenDeCliente(regimen: string): TabFiscalito[] {
  // T6: un cliente persona moral ve lo mismo que una PM que entra por su
  // cuenta. El alta de cliente ya ofrece 601 (`REGIMENES_DE_CLIENTE`), así que
  // esta rama no es hipotética como las de 605/606/625.
  if (regimen === '601') return [...TABS_601];
  if (regimen === '605') return ['deducciones', 'calendario'];
  // P3-02: `resumen` (resumen y actualización de impuestos) al final de cada régimen
  // que declara mensualmente; no cambia el tab por defecto. El 605 no declara mensual.
  if (regimen === '626') return ['declaracion', 'anual', 'calendario', 'comparar', 'estado', 'resumen'];
  if (regimen === '606') return ['declaracion', 'anual', 'calendario', 'comparar', 'multiperiodo', 'estado', 'resumen'];
  if (regimen === '625') return ['declaracion', 'anual', 'calendario', 'estado', 'resumen'];
  // 612 y cualquier otro: el set completo, que es el de `pyme`.
  return tabsCompletos();
}
