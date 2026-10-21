/**
 * Empleados guardados que el backend no pudo leer, con su razón. (R-10, P0-01)
 *
 * El backend no tumba la plantilla por un documento legado —un NSS de una versión
 * anterior, un campo que falta—: lo deja fuera de `empleados` y lo reporta en
 * `ilegibles`. Hasta P0-01 el front tiraba esa lista, así que ese empleado quedaba
 * **fuera del cálculo sin que el contador lo viera**. Aquí se pinta junto al aviso de
 * "no vinculados", que es la otra forma de quedar fuera de la nómina.
 */

import type { EmpleadoIlegible } from '../../services/carteraApi';

export default function EmpleadosIlegibles({ ilegibles }: { ilegibles: EmpleadoIlegible[] }) {
  if (ilegibles.length === 0) return null;
  const uno = ilegibles.length === 1;
  return (
    <div
      role="alert"
      aria-label="Empleados que no se pudieron leer"
      style={{
        background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
        borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm) var(--space-md)',
        fontSize: '0.88rem', color: 'var(--text-primary)',
      }}
    >
      <strong>
        {ilegibles.length} {uno ? 'empleado guardado no se pudo leer' : 'empleados guardados no se pudieron leer'}
      </strong>{' '}
      y {uno ? 'no entra' : 'no entran'} al cálculo de nómina hasta que se corrija. Edítalo
      desde la captura de empleados con el mismo número para reemplazarlo.
      <ul style={{ margin: 'var(--space-xs) 0 0', paddingLeft: 'var(--space-lg)' }}>
        {ilegibles.map((i) => (
          <li key={i.empleado_no}>
            <code>{i.empleado_no}</code>
            {i.nombre ? ` · ${i.nombre}` : ''} — {i.razon}
          </li>
        ))}
      </ul>
    </div>
  );
}
