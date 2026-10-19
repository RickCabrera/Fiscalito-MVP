/**
 * Celdas "Estatus SAT" y "Art. 69-B" de la tabla de la bóveda (P1-03/04).
 *
 * El estatus distingue lo verificado (Vigente / Cancelado) de lo que todavía no se
 * consulta (—). La marca 69-B va en rojo sólo cuando la situación de la contraparte es de
 * riesgo (definitivo o presunto); desvirtuados y sentencias favorables se ven en gris.
 */

import type { ComprobanteBoveda } from '../../services/bovedaApi';

const pastilla: React.CSSProperties = {
  display: 'inline-block', padding: '2px 8px', borderRadius: 'var(--radius-full)',
  fontSize: '0.74rem', fontWeight: 600, whiteSpace: 'nowrap',
};

export function CeldaEstatusSat({ c }: { c: ComprobanteBoveda }) {
  if (c.estatus_sat === 'cancelado') {
    return (
      <span style={{ ...pastilla, background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger-border)' }}
        title={c.fecha_estatus ? `Verificado ${c.fecha_estatus.slice(0, 10)}` : undefined}>
        Cancelado
      </span>
    );
  }
  if (c.estatus_sat === 'vigente') {
    const enProceso = c.estatus_cancelacion === 'En proceso';
    return (
      <span style={{ ...pastilla, background: enProceso ? 'var(--warning-bg)' : 'var(--success-bg)', color: enProceso ? 'var(--warning)' : 'var(--success)' }}
        title={c.fecha_estatus ? `Verificado ${c.fecha_estatus.slice(0, 10)}` : undefined}>
        {enProceso ? 'Vigente · cancelación en proceso' : 'Vigente'}
      </span>
    );
  }
  return <span title="Sin verificar" style={{ color: 'var(--text-muted)' }}>—</span>;
}

const SITUACION: Record<string, string> = {
  definitivo: 'Definitivo', presunto: 'Presunto', desvirtuado: 'Desvirtuado',
  sentencia_favorable: 'Sentencia favorable',
};

export function CeldaArt69b({ c }: { c: ComprobanteBoveda }) {
  const m = c.art_69b;
  if (!m) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  const rojo = m.nivel !== 'info';
  const texto = m.lista === '69b' ? `69-B ${SITUACION[m.situacion] ?? m.situacion}` : `Art. 69 ${m.situacion.replace(/_/g, ' ')}`;
  return (
    <span
      data-riesgo={rojo ? 'rojo' : 'info'}
      title="La contraparte aparece en un listado público del SAT"
      style={{
        ...pastilla,
        background: rojo ? 'var(--danger-bg)' : 'transparent',
        color: rojo ? 'var(--danger)' : 'var(--text-secondary)',
        border: `1px solid ${rojo ? 'var(--danger-border)' : 'var(--border)'}`,
      }}
    >
      {texto}
    </span>
  );
}
