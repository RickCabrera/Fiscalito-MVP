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
    tagline: 'Tu asistente fiscal con IA',
    description:
      'Calcula tus declaraciones ISR/IVA automaticamente, clasifica facturas CFDI, detecta saldos a favor y te explica cada calculo en lenguaje natural. Compatible con RESICO, Actividad Empresarial, Honorarios y mas.',
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
    id: 'contabilito',
    name: 'Contabilito',
    tagline: 'Contabilidad electronica automatizada',
    description:
      'Genera polizas contables, balanzas de comprobacion y catalogo de cuentas alineado al SAT. Envia tu contabilidad electronica directo al buzon tributario.',
    icon: '📊',
    status: 'coming_soon',
    category: 'contable',
    appliesTo: ['pyme'],
    features: [
      'Polizas contables automaticas desde CFDIs',
      'Balanza de comprobacion mensual',
      'Catalogo de cuentas SAT',
      'Envio al buzon tributario',
      'Reportes para contador externo',
      'Conciliacion bancaria basica',
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
