/**
 * Indicadores SAT de un renglón de la cartera (P1-05 / P1-04): un punto con el semáforo de
 * la opinión de cumplimiento y, si hay, cuántas alertas 69-B abiertas tiene el cliente.
 * Sin dato del servidor no pinta nada (la cartera puede venir de Firestore y el cliente
 * no existir todavía en la base).
 */

import { AlertTriangle } from 'lucide-react';
import {
  COLOR_SEMAFORO, etiquetaSemaforo, type SemaforoCliente,
} from '../../services/semaforoSat';

export default function IndicadoresSat({ dato }: { dato?: SemaforoCliente }) {
  if (!dato) return null;
  const s = dato.opinion.semaforo;
  const etiqueta = etiquetaSemaforo(s, dato.opinion.origen);
  const simulado = dato.opinion.origen === 'falso';
  const marca = dato.opinion.marca ? ` · ${dato.opinion.marca}` : '';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-xs)', fontSize: '0.72rem' }}>
      <span
        data-semaforo={s}
        data-origen={dato.opinion.origen ?? undefined}
        title={`Opinión de cumplimiento: ${etiqueta}${dato.opinion.fecha ? ` (${dato.opinion.fecha})` : ''}${marca}`}
        aria-label={`Opinión ${etiqueta}`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: COLOR_SEMAFORO[s], fontWeight: 600 }}
      >
        <span aria-hidden style={{ width: 9, height: 9, borderRadius: '50%', background: COLOR_SEMAFORO[s] }} />
        32-D{simulado ? ' · simulado' : dato.opinion.origen === 'manual' ? ' · no verificado' : ''}
      </span>
      {dato.riesgos_69b > 0 && (
        <span
          title={`${dato.riesgos_69b} contraparte(s) en listas del SAT sin atender`}
          aria-label={`${dato.riesgos_69b} riesgos 69-B`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 3, color: 'var(--danger)', fontWeight: 600,
            padding: '1px 6px', borderRadius: 'var(--radius-full)', background: 'var(--danger-bg)',
          }}
        >
          <AlertTriangle size={11} /> 69-B · {dato.riesgos_69b}
        </span>
      )}
    </span>
  );
}
