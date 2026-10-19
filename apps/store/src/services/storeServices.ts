import type { ContributorType } from './contributorProfiles';
import { MARCA_CORTA } from './marca';

export interface StoreService {
  id: string;
  name: string;
  tagline: string;
  description: string;
  icon: string;
  status: 'active' | 'coming_soon' | 'beta';
  features: string[];
  /**
   * Lo que el servicio TODAVÍA no hace, listado aparte. (T8)
   *
   * Existe porque `beta` sin esta lista miente por omisión: un servicio en beta
   * con seis funcionalidades a palomita afirma que las seis operan. Se pinta
   * atenuado y con la marca de "Próximamente", junto a lo que sí funciona, que
   * es donde alguien lo lee antes de prometérselo a un cliente.
   */
  features_proximamente?: string[];
  category: 'fiscal' | 'laboral' | 'contable';
  appliesTo: ContributorType[];
  externalUrl?: string;
  apiEndpoint?: string;
}

export const SERVICES: StoreService[] = [
  {
    // El `id` es interno —vive en la ruta `/app/store/fiscalito/use` y en
    // enlaces guardados— y por eso no se toca (O-02). El `name` sí se ve.
    id: 'fiscalito',
    name: MARCA_CORTA,
    tagline: 'Asistente fiscal',
    description:
      'Calcula las declaraciones ISR/IVA de cada cliente del despacho, clasifica facturas CFDI, detecta saldos a favor y explica cada calculo en lenguaje natural. Compatible con RESICO, Actividad Empresarial, Honorarios y mas.',
    icon: '⚖',
    status: 'active',
    category: 'fiscal',
    appliesTo: ['contador', 'asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme'],
    features: [
      'Pre-declaracion mensual, bimestral y anual',
      'Parseo automatico de XML CFDI',
      'Tablas ISR oficiales 2025 (RESICO + Art. 96)',
      'Calculo de IVA: cobrado - acreditable - retenido',
      'Deteccion automatica de saldos a favor',
      'Explicaciones en lenguaje natural con IA',
      'Recomendaciones de regimen fiscal',
      'Advertencias de riesgo (tope RESICO, facturas faltantes)',
    ],
    externalUrl: undefined, // Se llenara cuando la app del servicio este integrada
    apiEndpoint: import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000',
  },
  {
    // T8: pasa a BETA. Lo que estaba mal no era el estado del código, era la
    // etiqueta: las altas, el SDI, las cuotas obrero-patronales por ramo y el
    // archivo de movimientos afiliatorios YA funcionan y están probados
    // (`nomina_engine`, `exportadores/imss.ts`), y la tarjeta seguía diciendo
    // "Proximamente". Lo que falta —bajas y modificaciones de salario— se
    // enumera aparte, en `features_proximamente`, en vez de mezclarse con lo
    // que sí opera.
    id: 'imss-manager',
    name: 'IMSS Manager',
    tagline: 'Gestion de empleados ante el IMSS',
    description:
      'Calcula el SDI y las cuotas obrero-patronales por ramo, da de alta trabajadores y genera el archivo de movimientos afiliatorios para IDSE/SUA. Las bajas y las modificaciones de salario todavia no: el modelo no guarda fecha de baja ni historial de SBC.',
    icon: '🛡',
    status: 'beta',
    category: 'laboral',
    // El despacho entra por aqui: lleva el IMSS de sus clientes, y hasta T8 la
    // tarjeta le salia como "No disponible".
    appliesTo: ['pyme', 'contador'],
    features: [
      'Alta de trabajadores y plantilla',
      'Calculo de SDI (fijo y variable)',
      'Cuotas obrero-patronales por ramo',
      'Archivo de movimientos afiliatorios (IDSE / SUA)',
      'Calendario de vencimientos patronales',
    ],
    features_proximamente: [
      'Baja de trabajadores',
      'Modificaciones de salario',
      'Reportes para auditorias IMSS',
    ],
  },
  {
    // P2: el backend lleva catalogo, polizas automaticas desde la boveda,
    // polizas manuales y balanza con saldos. Lo que NO, en
    // `features_proximamente`: el envio al buzon necesita e.firma (P2-07).
    id: 'contabilito',
    name: 'Contabilito',
    tagline: 'Contabilidad electronica automatizada',
    description:
      'Genera las polizas de cada cliente desde su boveda de CFDI con reglas configurables, contra un catalogo ligado al codigo agrupador del SAT, y saca la balanza de comprobacion con saldos, mayor y auxiliares. El envio al buzon tributario necesita e.firma y todavia no.',
    icon: '📊',
    status: 'beta',
    category: 'contable',
    // El despacho lleva la contabilidad de sus clientes: sin `contador` la
    // tarjeta le salia "No disponible", igual que le pasaba a IMSS Manager.
    appliesTo: ['pyme', 'contador'],
    features: [
      'Polizas automaticas desde la boveda de CFDI (ingresos, egresos, pagos y nomina)',
      'Reglas de asignacion de cuentas por proveedor, ClaveProdServ y uso',
      'Catalogo de cuentas por cliente con el codigo agrupador SAT completo',
      'Balanza de comprobacion con saldos, mayor y auxiliares',
      'Polizas manuales y cierre de periodo',
    ],
    features_proximamente: [
      'Envio al buzon tributario (requiere e.firma)',
      'Conciliacion bancaria',
      'Reportes contables y export a Excel/PDF',
      'Export a Aspel COI / CONTPAQi',
    ],
  },
];

export function getServiceById(id: string): StoreService | undefined {
  return SERVICES.find((s) => s.id === id);
}

/**
 * Si el servicio se puede USAR hoy. (T8)
 *
 * `beta` cuenta como usable, y ése es el cambio: hasta T8 las dos pantallas del
 * marketplace preguntaban `status === 'active'` y todo lo demás caía en
 * "Proximamente" con el botón muerto. El estado `beta` existía en el tipo desde
 * el principio **y no significaba nada** — un servicio en beta se veía
 * exactamente igual que uno que no existe.
 *
 * Las dos pantallas preguntan aquí para que no vuelvan a divergir.
 */
export function servicioDisponible(servicio: StoreService): boolean {
  return servicio.status === 'active' || servicio.status === 'beta';
}

/** La etiqueta del badge. Un servicio en beta lo dice, no se disfraza. */
export function etiquetaDeEstado(servicio: StoreService): string {
  if (servicio.status === 'active') return 'Disponible';
  if (servicio.status === 'beta') return 'Beta';
  return 'Proximamente';
}

/**
 * A qué pantalla entra el servicio, o `null` si no se puede entrar todavía.
 *
 * Existe porque la Landing necesitaba la misma respuesta que ya daban a mano
 * los botones de `ServiceDetailPage`: Contabilito estaba anunciado en BETA en la
 * portada y la tarjeta no llevaba a ningún lado, así que la única puerta era el
 * rodeo por Marketplace → detalle del servicio.
 *
 * **IMSS Manager no tiene pantalla propia** —lo que hace vive en Empleados
 * (altas y plantilla) y en Nómina (SDI, cuotas por ramo, archivo afiliatorio)—
 * y por eso apunta a Empleados, que es donde empieza el trabajo. El detalle del
 * servicio conserva sus DOS botones (Empleados y Nómina) y no consume esta
 * función: ahí hay espacio para nombrar las dos mitades y aquí no, porque una
 * tarjeta es un solo destino.
 *
 * Un servicio no disponible devuelve `null` en vez de una ruta muerta: la
 * tarjeta se pinta atenuada y sin enlace, que es lo que ya dice su badge.
 */
export function rutaDeUso(servicio: StoreService): string | null {
  if (!servicioDisponible(servicio)) return null;
  if (servicio.id === 'fiscalito') return '/app/store/fiscalito/use';
  if (servicio.id === 'contabilito') return '/app/store/contabilito/use';
  if (servicio.id === 'imss-manager') return '/app/empleados';
  // Un servicio nuevo sin ruta declarada cae en su ficha del catálogo, que
  // siempre existe (`/app/store/:serviceId`). Es preferible a un enlace muerto
  // y a que la tarjeta deje de responder sin que nadie se entere.
  return `/app/store/${servicio.id}`;
}
