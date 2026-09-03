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
    id: 'imss-manager',
    name: 'IMSS Manager',
    tagline: 'Gestion de empleados ante el IMSS',
    description:
      'Automatiza altas, bajas y modificaciones de salario de tus empleados ante el IMSS. Calcula cuotas obrero-patronales y te avisa antes de cada vencimiento del SUA.',
    icon: '🛡',
    status: 'coming_soon',
    category: 'laboral',
    appliesTo: ['pyme'],
    features: [
      'Alta y baja de trabajadores',
      'Calculo de cuotas obrero-patronales',
      'Modificaciones de salario',
      'Alertas de vencimiento SUA',
      'Historial de movimientos',
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
