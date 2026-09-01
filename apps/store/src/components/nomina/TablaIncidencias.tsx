/** Tabla de incidencias del periodo (D-07). DEMO: se borra en F2. */

import type { CierrePeriodo, EmpleadoDemo } from '../../services/nominaDemoApi';

export default function TablaIncidencias({
  cierre,
  empleados,
}: {
  cierre: CierrePeriodo;
  empleados: EmpleadoDemo[];
}) {
  const nombre = (numero: string) =>
    empleados.find((e) => e.empleado_no === numero)?.nombre ?? numero;

  return (
    <section
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <h2 style={{ fontSize: '1rem', marginTop: 0 }}>
        Incidencias · {cierre.periodo.inicio} a {cierre.periodo.fin}
      </h2>

      {/* Herencia de D-04: si esto no se pinta, un alta con el employeeNo
          equivocado en el dispositivo se ve como "faltaron todos" y nadie
          sabe por qué. */}
      {cierre.empleados_desconocidos.length > 0 && (
        <p
          role="alert"
          style={{
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: '0.9rem',
          }}
        >
          <strong>Checadas de empleados que no están en la plantilla:</strong>{' '}
          {cierre.empleados_desconocidos.join(', ')}. No entraron al cálculo. Suele ser un
          alta con el número equivocado en el checador.
        </p>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
            <th style={{ padding: '4px 0' }}>Empleado</th>
            <th>Días del periodo</th>
            <th>Laborables</th>
            <th>Trabajados</th>
            <th>Faltas</th>
            <th>Retardos</th>
            <th title="Informativo. La base de cuotas la decide el motor por ramo (Art. 31 LSS).">
              Días cotizados*
            </th>
          </tr>
        </thead>
        <tbody>
          {cierre.incidencias.map((i) => (
            <tr key={i.empleado_no}>
              <td style={{ padding: '4px 0' }}>{nombre(i.empleado_no)}</td>
              <td>{i.dias_periodo}</td>
              <td>{i.dias_laborables}</td>
              <td>{i.dias_trabajados}</td>
              <td style={{ fontWeight: i.faltas > 0 ? 700 : 400 }}>{i.faltas}</td>
              <td style={{ fontWeight: i.retardos > 0 ? 700 : 400 }}>{i.retardos}</td>
              <td style={{ color: 'var(--text-muted)' }}>{i.dias_cotizados}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: 0 }}>
        * <strong>Informativo.</strong> La base de las cuotas del IMSS la determina el motor
        por ramo: el ausentismo no reduce Enfermedades y Maternidad (Art. 31 LSS). Este
        número no alimenta ningún cálculo de esta pantalla.
      </p>
    </section>
  );
}
