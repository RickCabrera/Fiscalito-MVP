/**
 * Navegación por perfil — fuente única de qué ve cada tipo de cuenta.
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
import { modoEmpresaUnica } from './modoEmpresa';
import { MARCA_CORTA } from './marca';

// ────────────────────────────────────────────────────────────
// Sidebar
// ────────────────────────────────────────────────────────────

/** Id estable de cada entrada del sidebar. AppLayout lo mapea a su icono. */
export type NavId =
  | 'dashboard' | 'fiscalito' | 'historial' | 'nomina' | 'perfil'
  | 'clientes' | 'empleados' | 'dispositivos' | 'calendario';

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
  // O-02: la RUTA se queda literal —es interna y vive en enlaces guardados— y
  // la ETIQUETA sale de la marca, porque es lo que el contribuyente lee en el
  // sidebar. Que las dos vivan en la misma línea fue lo que dejó pasar esta
  // etiqueta la primera vez: el guardián de marca perdonaba la línea entera por
  // la ruta, y ahora tacha los nombres internos en vez de perdonarla.
  { id: 'fiscalito', to: '/app/store/fiscalito/use', label: MARCA_CORTA },
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
  // R-05: Empleados y Dispositivos son entradas propias, no pestañas escondidas
  // dentro de la ficha. Operan sobre el cliente activo, igual que Nómina.
  { id: 'empleados', to: '/app/empleados', label: 'Empleados' },
  { id: 'dispositivos', to: '/app/dispositivos', label: 'Dispositivos' },
  { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
  { id: 'calendario', to: '/app/calendario', label: 'Calendario' },
  // T1: el despacho recupera el servicio fiscal, pero **el del CLIENTE ACTIVO**,
  // no el suyo propio. E-07 lo había quitado porque el único tab que le quedaba
  // —su calendario como persona física— dependía de un RFC y un régimen que E-05
  // dejó de pedirle; ése sigue sin aplicar, y por eso `calendario` de arriba
  // sigue apuntando al PATRONAL de sus clientes y no a un tab de Fiscalito.
  // Va después de Calendario y antes de Perfil: es herramienta, no ajuste.
  { id: 'fiscalito', to: '/app/store/fiscalito/use', label: MARCA_CORTA },
  { id: 'perfil', to: '/app/profile', label: 'Perfil' },
];

/**
 * Navegación de la EMPRESA ÚNICA (O-01).
 *
 * Es la del despacho **menos Clientes**: no hay cartera que listar, hay una
 * empresa implícita. Empleados, Dispositivos, Nómina y Calendario apuntan a las
 * mismas rutas y a las mismas pantallas — lo que cambia es que resuelven la
 * empresa en vez de un cliente activo elegido en una barra superior.
 *
 * `nomina` apunta a `/app/nomina`, que en este modo **es** la pantalla de
 * nómina, no la redirección de E-03. Ver `AppRoutes.tsx`.
 */
const LINKS_EMPRESA: SidebarLink[] = [
  { id: 'empleados', to: '/app/empleados', label: 'Empleados' },
  { id: 'dispositivos', to: '/app/dispositivos', label: 'Dispositivos' },
  { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
  { id: 'calendario', to: '/app/calendario', label: 'Calendario' },
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
 * Cómo se le llama en pantalla al perfil que opera la nómina.
 *
 * En modo empresa única, "Despacho / Contador" es falso: no hay despacho ni
 * cartera. La etiqueta cambia; el id guardado, no.
 */
export function etiquetaDelPerfilOperador(): string {
  return modoEmpresaUnica() ? 'Empresa' : 'Despacho / Contador';
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

/**
 * Links del sidebar para el perfil dado. `null` (perfil sin tipo) ve el de
 * contribuyente.
 *
 * O-01: en modo empresa única el perfil operador ve la navegación de la
 * empresa. **Los perfiles de contribuyente no cambian en ningún modo**: el
 * pivote es sobre la nómina, no sobre la app fiscal, y sus pantallas siguen
 * enteras.
 */
export function getSidebarLinks(tipo: ContributorType | null): SidebarLink[] {
  if (!esContador(tipo)) return LINKS_CONTRIBUYENTE;
  return modoEmpresaUnica() ? LINKS_EMPRESA : LINKS_CONTADOR;
}

/**
 * Ruta a la que entra cada perfil al terminar el onboarding o al pedir `/app`.
 *
 * En modo empresa única no hay `/app/clientes` a dónde llegar: la entrada es la
 * nómina, que es para lo que se abre la app.
 */
export function rutaInicial(tipo: ContributorType | null): string {
  if (!esContador(tipo)) return '/app';
  return modoEmpresaUnica() ? '/app/nomina' : '/app/clientes';
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
const RUTAS_CON_CLIENTE = [
  '/app/clientes', '/app/empleados', '/app/dispositivos',
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
  // O-01: sin cartera no hay cliente que elegir. Se corta aquí, en la función
  // que ya decide dónde se pinta el selector, y no en `AppLayout`: así el
  // selector desaparece de TODAS las rutas de una vez y no queda una pantalla
  // olvidada mostrando una barra que afirma un alcance que no existe.
  if (modoEmpresaUnica()) return false;
  return RUTAS_CON_CLIENTE.some((r) => pathname === r || pathname.startsWith(`${r}/`));
}

// ────────────────────────────────────────────────────────────
// Tabs del servicio Fiscalito
// ────────────────────────────────────────────────────────────

export type TabFiscalito =
  | 'declaracion' | 'anual' | 'deducciones' | 'calendario' | 'comparar'
  | 'diot' | 'retenciones' | 'multiperiodo' | 'estado' | 'pagospm';

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
  'pagospm', 'calendario', 'declaracion',
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
]);

/** Copia fresca del set completo, para no repartir la misma referencia. */
function tabsCompletos(): TabFiscalito[] {
  return [...TABS_COMPLETOS];
}

/**
 * Tabs de Fiscalito que aplican al perfil. La usan `FiscalitoServicePage`
 * (para los tabs) y `DashboardPage` (para las cards de servicio): antes eran
 * dos copias idénticas y divergibles.
 *
 * QUÉ ES `regimen` CUANDO EL TIPO ES `contador` (T1)
 * -------------------------------------------------
 * **El régimen del CLIENTE ACTIVO, no el del despacho.** Un despacho no
 * presenta las declaraciones de su cliente desde su propio régimen; presenta
 * las del cliente. Y desde E-05 el perfil del despacho ni siquiera tiene dónde
 * capturar un régimen propio: `profile.regimen` viene vacío, así que pasarlo
 * aquí no sólo sería incorrecto, sería inútil.
 *
 * Quien resuelve ese régimen es `FiscalitoServicePage` leyendo
 * `ClienteActivoContext`. Esta función sigue siendo pura y no sabe de contextos.
 *
 * OJO CON EL ORDEN: la rama de contador va PRIMERO, y ahora importa MÁS que
 * antes. Si se evaluara después, un contador cuyo cliente es RESICO caería en
 * `regimen === '626'` y saldría igual por casualidad — pero uno sin cliente
 * elegido caería hasta el `return` final y vería tres tabs sin que nada
 * explicara de dónde salen.
 */
export function getTabsForProfile(
  contributorType: string | null,
  regimen: string | null,
): TabFiscalito[] {
  // Contador: los tabs del CLIENTE que tiene activo.
  //
  // E-01 no le daba ninguno y E-07 lo quitó de la pantalla entera, con razones
  // que siguen en pie para lo que medían: el único tab que le quedaba era su
  // calendario como persona física (§D21), y E-05 le quitó el RFC y el régimen
  // de los que ese tab depende. **T1 no lo deshace: lo cambia de sujeto.** Lo
  // que el despacho recupera no es su Fiscalito, es el de su cliente, y por eso
  // el calendario que ve aquí también es el del cliente y `/app/calendario`
  // sigue siendo el patronal de toda la cartera.
  if (contributorType === 'contador') {
    // Sin cliente elegido no hay régimen que aplicar. La pantalla pinta un
    // estado vacío con el selector; devolver tabs aquí los pintaría sobre un
    // cliente inexistente.
    if (!regimen) return [];
    return tabsPorRegimenDeCliente(regimen);
  }

  if (contributorType === 'asalariado' || regimen === '605')
    return ['deducciones', 'calendario'];
  // T6: el 601 va ANTES de `pyme`, y no es cosmético. Una persona moral se da
  // de alta como `pyme` —es el único tipo que la ofrece—, así que evaluar el
  // tipo primero la mandaría al set completo de persona física y le pintaría
  // pre-declaración, DIOT y comparador de regímenes como si el motor los
  // supiera calcular para ella.
  if (regimen === '601')
    return [...TABS_601];
  if (contributorType === 'pyme')
    return tabsCompletos();
  if (regimen === '626')
    return ['declaracion', 'anual', 'calendario', 'comparar', 'estado'];
  if (regimen === '612')
    return tabsCompletos();
  if (contributorType === 'arrendamiento' || regimen === '606')
    return ['declaracion', 'anual', 'calendario', 'comparar', 'multiperiodo', 'estado'];
  if (contributorType === 'plataformas' || regimen === '625')
    return ['declaracion', 'anual', 'calendario', 'estado'];
  return ['declaracion', 'anual', 'calendario', 'estado'];
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
  if (regimen === '626') return ['declaracion', 'anual', 'calendario', 'comparar', 'estado'];
  if (regimen === '606') return ['declaracion', 'anual', 'calendario', 'comparar', 'multiperiodo', 'estado'];
  if (regimen === '625') return ['declaracion', 'anual', 'calendario', 'estado'];
  // 612 y cualquier otro: el set completo, que es el de `pyme`.
  return tabsCompletos();
}
