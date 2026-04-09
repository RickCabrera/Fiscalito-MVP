/** Perfiles de contribuyente — mapea tipo → regímenes, obligaciones, servicios */

export type ContributorType = 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme';

export interface ContributorProfile {
  id: ContributorType;
  label: string;
  description: string;
  icon: string;
  allowedRegimens: { code: string; name: string }[];
  obligations: string[];
  applicableServices: string[];
  extraFields: string[];
}

export const CONTRIBUTOR_PROFILES: Record<ContributorType, ContributorProfile> = {
  asalariado: {
    id: 'asalariado',
    label: 'Asalariado',
    description: 'Trabajador con sueldo fijo que recibe nomina de un patron.',
    icon: '💼',
    allowedRegimens: [
      { code: '605', name: 'Sueldos y Salarios' },
    ],
    obligations: [
      'Declaracion anual (abril)',
      'Deducciones personales (gastos medicos, colegiaturas, etc.)',
    ],
    applicableServices: ['fiscalito'],
    extraFields: [],
  },
  independiente: {
    id: 'independiente',
    label: 'Independiente / Freelancer',
    description: 'Profesionista o freelancer que emite facturas por honorarios o servicios.',
    icon: '💻',
    allowedRegimens: [
      { code: '626', name: 'RESICO (Regimen Simplificado de Confianza)' },
      { code: '612', name: 'Actividad Empresarial y Profesional' },
    ],
    obligations: [
      'Declaracion mensual o bimestral de ISR e IVA',
      'Declaracion anual',
      'Emision de CFDI por ingresos',
    ],
    applicableServices: ['fiscalito'],
    extraFields: [],
  },
  arrendamiento: {
    id: 'arrendamiento',
    label: 'Arrendamiento',
    description: 'Persona que obtiene ingresos por renta de inmuebles.',
    icon: '🏠',
    allowedRegimens: [
      { code: '606', name: 'Arrendamiento' },
    ],
    obligations: [
      'Declaracion mensual de ISR e IVA',
      'Declaracion anual',
      'Emision de CFDI por rentas cobradas',
    ],
    applicableServices: ['fiscalito'],
    extraFields: [],
  },
  plataformas: {
    id: 'plataformas',
    label: 'Plataformas digitales',
    description: 'Genera ingresos a traves de apps como Uber, Rappi, Airbnb, etc.',
    icon: '📱',
    allowedRegimens: [
      { code: '625', name: 'Plataformas Tecnologicas' },
    ],
    obligations: [
      'Declaracion mensual de ISR e IVA',
      'Declaracion anual',
      'Retenciones aplicadas por la plataforma',
    ],
    applicableServices: ['fiscalito'],
    extraFields: [],
  },
  pyme: {
    id: 'pyme',
    label: 'Negocio / PYME',
    description: 'Empresa o negocio con empleados y multiples obligaciones fiscales y laborales.',
    icon: '🏢',
    allowedRegimens: [
      { code: '612', name: 'Actividad Empresarial y Profesional' },
      { code: '626', name: 'RESICO (Regimen Simplificado de Confianza)' },
      { code: '621', name: 'Incorporacion Fiscal (RIF)' },
    ],
    obligations: [
      'Declaracion mensual o bimestral de ISR e IVA',
      'Declaracion anual',
      'Cuotas obrero-patronales IMSS',
      'Contabilidad electronica',
      'Nomina y retenciones de empleados',
    ],
    applicableServices: ['fiscalito', 'imss-manager', 'contabilito'],
    extraFields: ['nombreNegocio', 'numEmpleados'],
  },
};

export const CONTRIBUTOR_TYPES = Object.values(CONTRIBUTOR_PROFILES);

export function getProfileByType(type: ContributorType): ContributorProfile {
  return CONTRIBUTOR_PROFILES[type];
}
