/** Tabla de incidencias del periodo (D-07). DEMO: se borra en F2. */

import type { CierrePeriodo, EmpleadoDemo } from '../../services/nominaDemoApi';
import { envoltura, fila, tabla, td, th, thNum, tituloSeccion } from './estilosTabla';

const num: React.CSSProperties = {
  ...td,
  textAlign: 'right',
  fontFamily: "'JetBrains Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
};
const numMarcado: React.CSSProperties = {
  ...num,
  fontWeight: 700,
  color: 'var(--warning)',
};

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
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <h2 style={tituloSeccion}>
        Incidencias{' '}
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          · {cierre.periodo.inicio} a {cierre.periodo.fin}
        </span>
      </h2>

      {/* Herencia de D-04: si esto no se pinta, un alta con el employeeNo
          equivocado en el dispositivo se ve como "faltaron todos" y nadie
          sabe por qué. */}
      {cierre.empleados_desconocidos.length > 0 && (
        <p
          role="alert"
          style={{
            margin: 0,
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)',
            fontSize: '0.88rem',
            color: 'var(--text-primary)',
          }}
        >
          <strong>Checadas de empleados que no están en la plantilla:</strong>{' '}
          {cierre.empleados_desconocidos.join(', ')}. No entraron al cálculo. Suele ser un
          alta con el número equivocado en el checador.
        </p>
      )}

      <div style={envoltura}>
        <table style={tabla(720)}>
          <thead>
            <tr>
              <th style={th}>Empleado</th>
              <th style={thNum}>Días del periodo</th>
              <th style={thNum}>Laborables</th>
              <th style={thNum}>Trabajados</th>
              <th style={thNum}>Faltas</th>
              <th style={thNum}>Retardos</th>
              <th
                style={thNum}
                title="Informativo. Cada ramo del IMSS usa su propia base de días: Enfermedades y Maternidad se cobra íntegro aunque haya faltas (Art. 31 LSS)."
              >
                Días cotizados*
              </th>
            </tr>
          </thead>
          <tbody>
            {cierre.incidencias.map((i, idx) => (
              <tr key={i.empleado_no} style={fila(idx)}>
                <td style={td}>{nombre(i.empleado_no)}</td>
                <td style={num}>{i.dias_periodo}</td>
                <td style={num}>{i.dias_laborables}</td>
                <td style={num}>{i.dias_trabajados}</td>
                {/* Falta y retardo son el dato que se busca en esta tabla: se
                    marcan con color semántico además del peso, para que salten
                    a la vista en un proyector. */}
                <td style={i.faltas > 0 ? numMarcado : num}>{i.faltas}</td>
                <td style={i.retardos > 0 ? numMarcado : num}>{i.retardos}</td>
                <td style={{ ...num, color: 'var(--text-muted)' }}>{i.dias_cotizados}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* El texto va en POSITIVO y ACOTADO, y las dos cosas son deliberadas.
          En positivo: "el ausentismo no reduce EyM" se leía como "EyM no se
          toma en cuenta", que es lo contrario de la verdad.
          Acotado a 7 días: la fr. II del Art. 31 libera al patrón de TODAS las
          cuotas cuando la ausencia excede ese plazo, y el motor no lo
          implementa (`docs/decisiones-nomina.md` §D3: con 20 días de ausencia
          sigue cobrando 30 de EyM, de más y a propósito). Una frase
          incondicional sería clara y falsa, que en un proyector es peor que
          confusa y falsa. */}
      <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: 0 }}>
        * <strong>Informativo:</strong> no alimenta ningún cálculo de esta pantalla. Cada
        ramo del IMSS cobra sobre su propia base de días. Con ausencias de hasta 7 días al
        mes, <strong>Enfermedades y Maternidad se cobra íntegro</strong> — las faltas no lo
        reducen (Art. 31 LSS). Todos los demás ramos —Invalidez y Vida, Guarderías, Retiro,
        Cesantía y Vejez, Infonavit y Riesgos de Trabajo— sí descuentan esos días.
      </p>
    </section>
  );
}
