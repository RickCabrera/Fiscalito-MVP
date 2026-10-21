/**
 * Régimen y fecha de baja del empleado (P4-03, P4-04).
 *
 * - `tipo_regimen`: '02' sueldos y salarios, o asimilado (Art. 94 LISR) —sin cuotas del
 *   IMSS ni subsidio—, con la clave de `c_TipoRegimen` que corresponde.
 * - `fecha_baja`: el periodo que la contiene se calcula PARCIAL con el criterio §D26 del
 *   cliente, y los posteriores ya no lo incluyen.
 *
 * Vive aparte de `ModalEmpleado` para no engordar ese archivo (tope de 300 líneas).
 */

import type { EmpleadoCartera } from '../../services/carteraApi';
import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';

const REGIMENES_EMPLEADO: [string, string][] = [
  ['02', 'Sueldos y salarios'],
  ['09', 'Asimilado — honorarios (Art. 94 fr. IV y V)'],
  ['07', 'Asimilado — miembros de consejos (fr. III)'],
  ['08', 'Asimilado — comisionistas (fr. VI)'],
  ['05', 'Asimilado — cooperativas de producción (fr. II)'],
  ['06', 'Asimilado — sociedades y asociaciones civiles (fr. II)'],
  ['10', 'Asimilado — acciones (fr. VII)'],
  ['11', 'Asimilado — otros'],
];

export default function CamposNominaEmpleado({
  datos,
  onCambiar,
}: {
  datos: EmpleadoCartera;
  onCambiar: (cambio: Partial<EmpleadoCartera>) => void;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
      <Campo label="Régimen de contratación">
        <select
          style={campo}
          value={datos.tipo_regimen ?? '02'}
          onChange={(e) => onCambiar({ tipo_regimen: e.target.value })}
        >
          {REGIMENES_EMPLEADO.map(([valor, texto]) => (
            <option key={valor} value={valor}>
              {texto}
            </option>
          ))}
        </select>
      </Campo>
      <Campo label="Fecha de baja (opcional)">
        <input
          type="date"
          style={campo}
          value={datos.fecha_baja ?? ''}
          onChange={(e) => onCambiar({ fecha_baja: e.target.value || null })}
        />
      </Campo>
    </div>
  );
}
