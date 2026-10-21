/**
 * Régimen, fecha de baja y marca de consejero del empleado (P4-03, P4-04, P6-07).
 *
 * - `tipo_regimen`: '02' sueldos y salarios, o asimilado (Art. 94 LISR) —sin cuotas del
 *   IMSS ni subsidio—, con la clave de `c_TipoRegimen` que corresponde.
 * - `fecha_baja`: el periodo que la contiene se calcula PARCIAL con el criterio §D26 del
 *   cliente, y los posteriores ya no lo incluyen.
 * - `es_consejero` / `consejero_es_trabajador` (sólo asimilados): la retención mínima a la
 *   tasa máxima del Art. 152 aplica a consejeros, administradores, comisarios y gerentes
 *   generales, salvo que además sean trabajadores del retenedor (Art. 96 LISR, quinto
 *   párrafo). Se marca aquí; el motor ya no lo supone por el régimen 07.
 *
 * Vive aparte de `ModalEmpleado` para no engordar ese archivo (tope de 300 líneas).
 */

import type { EmpleadoCartera } from '../../services/carteraApi';
import Campo from './Campo';
import { campoInput as campo, etiquetaCampo } from './estilosCampo';

const casilla: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--space-xs)',
  alignItems: 'center',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
};

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
  const asimilado = (datos.tipo_regimen ?? '02') !== '02';
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
      {asimilado && (
        <div
          role="group"
          aria-label="Retención de consejeros"
          style={{ flex: '1 1 200px', minWidth: 0 }}
        >
          <span style={etiquetaCampo}>Retención de consejeros (Art. 96 LISR, 5o. párrafo)</span>
          <label style={casilla}>
            <input
              type="checkbox"
              checked={datos.es_consejero ?? false}
              onChange={(e) =>
                onCambiar({
                  es_consejero: e.target.checked,
                  ...(e.target.checked ? {} : { consejero_es_trabajador: false }),
                })
              }
            />
            Consejero, administrador, comisario o gerente general
          </label>
          {datos.es_consejero && (
            <label style={casilla}>
              <input
                type="checkbox"
                checked={datos.consejero_es_trabajador ?? false}
                onChange={(e) => onCambiar({ consejero_es_trabajador: e.target.checked })}
              />
              Además es trabajador del patrón (se retiene con tarifa)
            </label>
          )}
        </div>
      )}
    </div>
  );
}
