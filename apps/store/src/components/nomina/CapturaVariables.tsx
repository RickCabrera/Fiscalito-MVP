/**
 * Captura de incidencias y variables por empleado para el periodo (P4-05).
 *
 * Se suma a lo que dice el checador: horas extra, domingos, vacaciones, incapacidades,
 * faltas que el aparato no vio y descuentos (Infonavit, Fonacot, préstamos). **Aquí no se
 * calcula nada**: cada valor viaja tal cual y el motor aplica exenciones, topes y su
 * efecto en el SBC. Lo que no se toca viaja vacío y el motor lo toma como cero.
 */

import type { EmpleadoCartera } from '../../services/carteraApi';
import type { VariablesEmpleado } from '../../services/nominaApi';
import { envoltura, fila, tabla, td, th, thNum, tituloSeccion } from './estilosTabla';

type CampoNumero = 'horas_dobles' | 'horas_triples' | 'fonacot' | 'prestamo';
type CampoEntero = 'domingos_trabajados' | 'dias_vacaciones' | 'faltas_adicionales';

const COLUMNAS: { campo: CampoNumero | CampoEntero | 'incapacidad' | 'infonavit'; texto: string; ayuda: string }[] = [
  { campo: 'horas_dobles', texto: 'Horas dobles', ayuda: 'Art. 66 LFT; 50 % exento hasta 5 UMA por semana' },
  { campo: 'horas_triples', texto: 'Horas triples', ayuda: 'Art. 68 LFT; gravadas e integran al SBC' },
  { campo: 'domingos_trabajados', texto: 'Domingos', ayuda: 'Prima dominical 25 %; 1 UMA exenta por domingo' },
  { campo: 'dias_vacaciones', texto: 'Días de vacaciones', ayuda: 'Genera la prima vacacional (15 UMA exentas al año)' },
  { campo: 'incapacidad', texto: 'Incapacidad (días)', ayuda: 'Enfermedad general: la paga el IMSS, no el patrón' },
  { campo: 'faltas_adicionales', texto: 'Faltas extra', ayuda: 'Faltas que no registró el checador' },
  { campo: 'infonavit', texto: 'Infonavit %', ayuda: 'Porcentaje del SBC (0.20 = 20 %)' },
  { campo: 'fonacot', texto: 'Fonacot', ayuda: 'Topado a 20 % del salario (Art. 110 fr. VII LFT)' },
  { campo: 'prestamo', texto: 'Préstamo', ayuda: 'Descuento de un préstamo del patrón' },
];

const input: React.CSSProperties = { width: 80, textAlign: 'right' };

function valorDe(v: VariablesEmpleado | undefined, campo: (typeof COLUMNAS)[number]['campo']): string {
  if (!v) return '';
  if (campo === 'incapacidad') return v.incapacidades?.[0] ? String(v.incapacidades[0].dias) : '';
  if (campo === 'infonavit') return v.infonavit?.valor ?? '';
  const valor = v[campo];
  return valor === undefined || valor === null ? '' : String(valor);
}

function conValor(
  base: VariablesEmpleado,
  campo: (typeof COLUMNAS)[number]['campo'],
  texto: string,
): VariablesEmpleado {
  const vacio = texto.trim() === '';
  if (campo === 'incapacidad') {
    return { ...base, incapacidades: vacio ? [] : [{ tipo: '02', dias: Number(texto) }] };
  }
  if (campo === 'infonavit') {
    return { ...base, infonavit: vacio ? null : { tipo: 'porcentaje', valor: texto } };
  }
  if (campo === 'domingos_trabajados' || campo === 'dias_vacaciones' || campo === 'faltas_adicionales') {
    return { ...base, [campo]: vacio ? 0 : Number(texto) };
  }
  return { ...base, [campo]: vacio ? '0' : texto };
}

export default function CapturaVariables({
  empleados,
  variables,
  onCambiar,
  deshabilitado,
}: {
  empleados: EmpleadoCartera[];
  variables: Record<string, VariablesEmpleado>;
  onCambiar: (v: VariablesEmpleado) => void;
  deshabilitado?: boolean;
}) {
  if (empleados.length === 0) return null;
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h2 style={tituloSeccion}>Incidencias y variables del periodo</h2>
      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Se suman a lo que registró el checador. El motor aplica las exenciones del Art. 93 LISR y el
        efecto en el SBC (Art. 27 LSS); aquí no se calcula nada.
      </p>
      <div style={envoltura}>
        <table style={tabla(980)}>
          <thead>
            <tr>
              <th style={th}>Empleado</th>
              {COLUMNAS.map((c) => (
                <th key={c.campo} style={thNum} title={c.ayuda}>
                  {c.texto}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {empleados.map((e, i) => {
              const actual = variables[e.empleado_no] ?? { empleado_no: e.empleado_no };
              return (
                <tr key={e.empleado_no} style={fila(i)}>
                  <td style={td}>{`${e.empleado_no} · ${e.nombre}`}</td>
                  {COLUMNAS.map((c) => (
                    <td key={c.campo} style={td}>
                      <input
                        className="input-field"
                        style={input}
                        inputMode="decimal"
                        aria-label={`${c.texto} de ${e.nombre}`}
                        disabled={deshabilitado}
                        value={valorDe(variables[e.empleado_no], c.campo)}
                        onChange={(ev) => onCambiar(conValor(actual, c.campo, ev.target.value))}
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
