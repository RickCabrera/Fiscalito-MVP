/**
 * Captura de deducciones personales — campos, topes por nivel y clasificación
 * de CFDI por ClaveProdServ.
 *
 * T3: vivía entero dentro de `DeduccionesPersonalesTab.tsx`, que es el tab del
 * ASALARIADO. La declaración anual de una persona física de 612/626/606 pide
 * exactamente la misma captura, así que se extrajo tal cual —sin cambiar una
 * clave ni un tope— para que los dos tabs compartan una sola lista. Duplicarla
 * habría dejado dos catálogos de claves del SAT divergiendo en silencio.
 *
 * **Aquí no se calcula nada fiscal.** Los topes los aplica el motor
 * (`POST /api/v1/deducciones-personales`); esto sólo decide en qué casilla cae
 * cada factura y qué etiquetas se pintan.
 */

export const NIVELES_EDUCATIVOS = [
  'Preescolar', 'Primaria', 'Secundaria', 'Profesional técnico',
  'Bachillerato o equivalente',
];

export interface DeduccionField { key: string; label: string; placeholder: string }

export const CAMPOS: DeduccionField[] = [
  { key: 'gastos_medicos', label: 'Gastos médicos y dentales', placeholder: '0.00' },
  { key: 'colegiaturas', label: 'Colegiaturas', placeholder: '0.00' },
  { key: 'intereses_hipotecarios', label: 'Intereses hipotecarios reales', placeholder: '0.00' },
  { key: 'seguros_gastos_medicos', label: 'Primas de seguros de gastos médicos', placeholder: '0.00' },
  { key: 'donativos', label: 'Donativos', placeholder: '0.00' },
  { key: 'aportaciones_voluntarias_retiro', label: 'Aportaciones voluntarias al retiro', placeholder: '0.00' },
  { key: 'funeral', label: 'Gastos funerarios', placeholder: '0.00' },
  { key: 'transporte_escolar', label: 'Transporte escolar obligatorio', placeholder: '0.00' },
];

const DIVISION_A_CAMPO: Record<string, string> = { '85': 'gastos_medicos', '42': 'gastos_medicos', '86': 'colegiaturas', '78': 'transporte_escolar' };
const CLAVE_ESPECIFICA_A_CAMPO: Record<string, string> = { '85171500': 'funeral', '84131500': 'seguros_gastos_medicos', '84131600': 'intereses_hipotecarios', '84121500': 'donativos' };

/** Campo de deducción personal al que pertenece un CFDI, o `null` si no es una. */
export function clasificarFacturaDeduccion(claveProdServ: string, descripcion?: string): string | null {
  if (!claveProdServ) return null;
  if (claveProdServ === '84131500' && descripcion) {
    const desc = descripcion.toUpperCase();
    const esRetiro = ['RETIRO', 'AFORE', 'APORTACION VOLUNTARIA', 'AHORRO', 'PPR', 'PLAN PERSONAL', 'PREVISION'].some(kw => desc.includes(kw));
    if (esRetiro) return 'aportaciones_voluntarias_retiro';
    return 'seguros_gastos_medicos';
  }
  if (CLAVE_ESPECIFICA_A_CAMPO[claveProdServ]) return CLAVE_ESPECIFICA_A_CAMPO[claveProdServ];
  const clase6 = claveProdServ.substring(0, 6);
  if (CLAVE_ESPECIFICA_A_CAMPO[clase6]) return CLAVE_ESPECIFICA_A_CAMPO[clase6];
  const division = claveProdServ.substring(0, 2);
  if (DIVISION_A_CAMPO[division]) return DIVISION_A_CAMPO[division];
  return null;
}

/** Los campos con monto > 0, listos para el request. Devuelve `{}` si no hay ninguno. */
export function montosCapturados(values: Record<string, string>): Record<string, number> {
  const fields: Record<string, number> = {};
  for (const campo of CAMPOS) {
    const val = parseFloat(values[campo.key] || '0');
    if (val > 0) fields[campo.key] = val;
  }
  return fields;
}
