/**
 * Una tarjeta de dispositivo, con su cruce contra la cartera. (R-04)
 *
 * Se extrajo de `DispositivosPage` cuando ese archivo llegó a 400 líneas contra
 * el tope de 300 de `apps/store/CLAUDE.md`. El corte es por responsabilidad, no
 * por número de líneas: la página resuelve el cliente activo, carga y ordena;
 * esto pinta un aparato y dice qué le falta.
 *
 * `Aviso` se recibe por prop en vez de duplicarse: es el mismo aspecto que usan
 * `EmpleadosTab` y la página, y una segunda copia sería la que alguien olvide
 * actualizar.
 */

import { AlertTriangle } from 'lucide-react';
import { Pencil, Trash2 } from 'lucide-react';
import type { EmpleadoCartera } from '../../services/carteraApi';
import { cruzarEnrolamiento, type DispositivoChecador } from '../../services/dispositivosApi';

export default function TarjetaDispositivo({
  dispositivo: d,
  empleados,
  /** `null` = no se pudo preguntar al checador. **No es un conjunto vacío.** */
  checando,
  soloLectura,
  onEditar,
  onBorrar,
  Aviso,
}: {
  dispositivo: DispositivoChecador;
  empleados: EmpleadoCartera[];
  checando: Set<string> | null;
  soloLectura: boolean;
  onEditar: () => void;
  onBorrar: () => void;
  Aviso: (props: { children: React.ReactNode }) => React.ReactElement;
}) {
  const { enrolados, fantasmas } = cruzarEnrolamiento(d, empleados);

  return (
      <div key={d.id} className="card" style={{ padding: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '1rem' }}>{d.nombre}</div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              {[d.marca, d.modelo].filter(Boolean).join(' ') || 'Sin modelo'}
              {d.ip && (
                <>
                  {' · '}
                  <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {d.ip}:{d.puerto}
                  </span>
                </>
              )}
              {d.serial && <> · serie {d.serial}</>}
            </div>
          </div>
          {!soloLectura && (
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                aria-label={`Editar ${d.nombre}`}
                onClick={onEditar}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <Pencil size={15} />
              </button>
              <button
                aria-label={`Dar de baja ${d.nombre}`}
                onClick={onBorrar}
                style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}
              >
                <Trash2 size={15} />
              </button>
            </div>
          )}
        </div>

        <div style={{ marginTop: 'var(--space-md)' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Enrolados · {enrolados.length}
          </div>
          {enrolados.length === 0 && (
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Nadie enrolado todavía. Edítalo para marcar quién está dado de alta en el aparato.
            </p>
          )}
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
            {enrolados.map((e) => (
              <li
                key={e.empleado_no}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-full)',
                  padding: '3px 10px',
                }}
              >
                <span>{e.nombre}</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-muted)' }}>
                  #{e.employee_no}
                </span>
                {/* Del endpoint real del adaptador, no de la cartera.
                    Con `checando === null` NO se pinta nada: no saber no
                    es lo mismo que saber que no. */}
                {checando !== null && !checando.has(e.employee_no as string) && (
                  <span style={{ color: 'var(--warning)', fontSize: '0.72rem' }}>sin checadas</span>
                )}
              </li>
            ))}
          </ul>
        </div>

        {fantasmas.length > 0 && (
          <div style={{ marginTop: 'var(--space-md)' }}>
            <Aviso>
              <AlertTriangle size={14} color="var(--warning)" style={{ verticalAlign: 'middle' }} />{' '}
              <strong>
                {fantasmas.length === 1
                  ? 'Un número enrolado en este aparato no está en la cartera'
                  : `${fantasmas.length} números enrolados en este aparato no están en la cartera`}
                :
              </strong>{' '}
              <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {fantasmas.join(', ')}
              </span>
              . Sus checadas van a llegar y <strong>no habrá a quién atribuirlas</strong>:
              es de donde salen los "empleados desconocidos" al cerrar el periodo.
            </Aviso>
          </div>
        )}
      </div>
  );
}
