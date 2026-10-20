/**
 * Calendario mensual de la descarga del SAT (P1-02), como el de Contadigital:
 * un ícono por día. Palomita verde = completo, reloj = en proceso, X = fallido,
 * guion = sin movimientos, vacío = no solicitado.
 */

import { CheckCircle2, ChevronLeft, ChevronRight, Clock, Minus, XCircle } from 'lucide-react';
import type { DiaBitacora, EstadoDia } from '../../services/satDescargaApi';

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
  'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const SEMANA = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do'];

const ETIQUETA_ESTADO: Record<EstadoDia, string> = {
  completo: 'Completo',
  en_proceso: 'En proceso',
  fallido: 'Fallido',
  sin_movimientos: 'Sin movimientos',
  no_solicitado: 'No solicitado',
};

function Icono({ estado }: { estado: EstadoDia }) {
  if (estado === 'completo') return <CheckCircle2 size={18} color="var(--success)" aria-hidden />;
  if (estado === 'en_proceso') return <Clock size={18} color="var(--warning)" aria-hidden />;
  if (estado === 'fallido') return <XCircle size={18} color="var(--danger)" aria-hidden />;
  if (estado === 'sin_movimientos') return <Minus size={18} color="var(--text-muted)" aria-hidden />;
  return <span style={{ height: 18 }} aria-hidden />;
}

interface Props {
  anio: number;
  mes: number;
  dias: DiaBitacora[];
  onMes: (anio: number, mes: number) => void;
}

export default function CalendarioSat({ anio, mes, dias, onMes }: Props) {
  // Lunes = 0. `getDay` da domingo = 0.
  const primero = (new Date(anio, mes - 1, 1).getDay() + 6) % 7;
  const anterior = mes === 1 ? [anio - 1, 12] : [anio, mes - 1];
  const siguiente = mes === 12 ? [anio + 1, 1] : [anio, mes + 1];

  return (
    <div className="card" style={{ padding: 'var(--space-md)', display: 'grid', gap: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button type="button" className="btn-secondary" aria-label="Mes anterior"
          onClick={() => onMes(anterior[0], anterior[1])}>
          <ChevronLeft size={16} />
        </button>
        <strong>{MESES[mes - 1]} {anio}</strong>
        <button type="button" className="btn-secondary" aria-label="Mes siguiente"
          onClick={() => onMes(siguiente[0], siguiente[1])}>
          <ChevronRight size={16} />
        </button>
      </div>
      <div role="grid" aria-label={`Descarga del SAT de ${MESES[mes - 1]} ${anio}`}
        style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
        {SEMANA.map((d) => (
          <div key={d} style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{d}</div>
        ))}
        {Array.from({ length: primero }, (_, i) => <div key={`v${i}`} />)}
        {dias.map((d) => {
          const n = Number(d.fecha.slice(8, 10));
          const titulo = [
            `${d.fecha}: ${ETIQUETA_ESTADO[d.estado]}`,
            d.emitidos || d.recibidos ? `${d.emitidos} emitidos, ${d.recibidos} recibidos` : '',
            d.cancelados ? `${d.cancelados} cancelados` : '',
            d.mensaje,
          ].filter(Boolean).join(' · ');
          return (
            <div key={d.fecha} role="gridcell" title={titulo} aria-label={titulo}
              data-estado={d.estado}
              style={{
                border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)',
                padding: '6px 4px', display: 'grid', justifyItems: 'center', gap: 2,
                background: d.estado === 'fallido' ? 'var(--danger-bg)' : 'transparent',
              }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{n}</span>
              <Icono estado={d.estado} />
              {d.emitidos + d.recibidos > 0 && (
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                  {d.emitidos + d.recibidos}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        {(['completo', 'en_proceso', 'fallido', 'sin_movimientos'] as EstadoDia[]).map((e) => (
          <span key={e} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <Icono estado={e} /> {ETIQUETA_ESTADO[e]}
          </span>
        ))}
      </div>
    </div>
  );
}
