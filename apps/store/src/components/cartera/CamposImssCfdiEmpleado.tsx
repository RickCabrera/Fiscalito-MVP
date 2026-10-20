/**
 * Datos del empleado para el IMSS y el CFDI de nómina (P4-09, P4-11).
 *
 * - `causa_baja`: catálogo del IMSS (posición 149 del layout de bajas). Sin ella, la baja no
 *   sale en el archivo de IDSE y el exportador lo dice.
 * - `tipo_salario`: 0 fijo, 1 variable, 2 mixto (posición 117 del layout; el bimestre variable
 *   del Art. 30 LSS sólo promedia a los variables y mixtos).
 * - RFC, CURP y CP del domicilio fiscal: obligatorios para timbrar en CFDI 4.0. Vacíos cuando no
 *   se conocen; **nunca se inventan**.
 *
 * Vive aparte de `ModalEmpleado` por el tope de 300 líneas.
 */

import type { EmpleadoCartera } from '../../services/carteraApi';
import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';

const CAUSAS: [string, string][] = [
  ['', '— (sin baja)'], ['1', '1 · Término de contrato'], ['2', '2 · Separación voluntaria'],
  ['3', '3 · Abandono de empleo'], ['4', '4 · Defunción'], ['5', '5 · Clausura'], ['6', '6 · Otras'],
  ['7', '7 · Ausentismo'], ['8', '8 · Rescisión de contrato'], ['9', '9 · Jubilación'], ['A', 'A · Pensión'],
];
const SALARIOS: [string, string][] = [['0', 'Fijo'], ['1', 'Variable'], ['2', 'Mixto']];

export default function CamposImssCfdiEmpleado({
  datos,
  onCambiar,
}: {
  datos: EmpleadoCartera;
  onCambiar: (cambio: Partial<EmpleadoCartera>) => void;
}) {
  const texto = (k: 'rfc' | 'curp' | 'codigo_postal', valor: string) =>
    onCambiar({ [k]: valor.trim().toUpperCase() } as Partial<EmpleadoCartera>);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
      <Campo label="Causa de baja (IMSS)">
        <select style={campo} value={datos.causa_baja ?? ''} onChange={(e) => onCambiar({ causa_baja: e.target.value })}>
          {CAUSAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </Campo>
      <Campo label="Tipo de salario (IMSS)">
        <select style={campo} value={datos.tipo_salario ?? '0'} onChange={(e) => onCambiar({ tipo_salario: e.target.value })}>
          {SALARIOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </Campo>
      <Campo label="RFC del trabajador">
        <input style={campo} maxLength={13} value={datos.rfc ?? ''} placeholder="Vacío si no se conoce" onChange={(e) => texto('rfc', e.target.value)} />
      </Campo>
      <Campo label="CURP">
        <input style={campo} maxLength={18} value={datos.curp ?? ''} placeholder="Vacío si no se conoce" onChange={(e) => texto('curp', e.target.value)} />
      </Campo>
      <Campo label="CP del domicilio fiscal">
        <input style={campo} maxLength={5} inputMode="numeric" value={datos.codigo_postal ?? ''} onChange={(e) => texto('codigo_postal', e.target.value)} />
      </Campo>
    </div>
  );
}
