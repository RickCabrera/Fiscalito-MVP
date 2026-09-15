/** Perfiles de contribuyente — mapea tipo → regímenes, obligaciones, servicios */

export type ContributorType = 'contador' | 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme';

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
  // E-01: va primero porque es el perfil del producto (un despacho que lleva la
  // nomina de varios clientes), no un contribuyente mas de la lista.
  contador: {
    id: 'contador',
    label: 'Despacho / Contador',
    description: 'Despacho o contador que lleva la contabilidad y la nomina de varios clientes.',
    icon: '🧾',
    // El regimen PROPIO del despacho, que desde E-05 ya no se le pide. Los
    // regimenes que puede llevarle a sus CLIENTES viven en
    // `REGIMENES_DE_CLIENTE` (`carteraApi.ts`), y ahi si entro el 601 con T6.
    allowedRegimens: [
      { code: '612', name: 'Actividad Empresarial y Profesional' },
      { code: '626', name: 'RESICO (Regimen Simplificado de Confianza)' },
    ],
    obligations: [
      'Nomina y cuotas obrero-patronales de sus clientes',
      'Declaracion mensual o bimestral de ISR e IVA propios',
      'Declaracion anual propia',
    ],
    applicableServices: ['fiscalito'],
    extraFields: ['nombreDespacho'],
  },
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
    // T6: el 601 entra como CASCARON. Es el unico perfil que lo ofrece porque
    // es el unico que puede ser persona moral, y lo que ve al elegirlo NO es la
    // app de persona fisica: `getTabsForProfile` le da el tab de pagos
    // provisionales PM y le quita la pre-declaracion, y el API la rechaza con
    // un 400 antes de llegar a `calculadora.py`.
    allowedRegimens: [
      { code: '612', name: 'Actividad Empresarial y Profesional' },
      { code: '626', name: 'RESICO (Regimen Simplificado de Confianza)' },
      { code: '621', name: 'Incorporacion Fiscal (RIF)' },
      { code: '601', name: 'General de Ley Personas Morales' },
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
