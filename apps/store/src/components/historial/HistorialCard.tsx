/** Historial card — single declaration row with expandable detail */

import { ChevronDown, ChevronUp, FileText, FileSpreadsheet, Users, TrendingUp, Wallet, Calculator } from 'lucide-react';
import { Timestamp } from 'firebase/firestore';
import { type DeclaracionRecord, type HistorialCategoria } from '../../services/declaracionesHistory';
import ExpandedDetail from './ExpandedDetail';

interface BadgeConfig {
  label: string;
  bg: string;
  color: string;
  icon: React.ReactNode;
}

function getBadge(cat: HistorialCategoria): BadgeConfig {
  switch (cat) {
    case 'predeclaracion': return { label: 'Pre-declaración', bg: 'var(--purple-bg)', color: 'var(--purple-light)', icon: <FileText size={12} /> };
    case 'diot': return { label: 'DIOT', bg: 'var(--teal-bg)', color: 'var(--teal-light)', icon: <FileSpreadsheet size={12} /> };
    case 'retenciones': return { label: 'Retenciones', bg: 'var(--warning-bg)', color: 'var(--warning)', icon: <Users size={12} /> };
    case 'multiperiodo': return { label: 'Multi-periodo', bg: 'var(--teal-bg)', color: 'var(--teal-light)', icon: <TrendingUp size={12} /> };
    case 'estado_cuenta': return { label: 'Estado cuenta', bg: 'var(--success-bg)', color: 'var(--success)', icon: <Wallet size={12} /> };
    case 'deducciones': return { label: 'Deducciones', bg: 'var(--purple-bg)', color: '#a06cb8', icon: <Calculator size={12} /> };
    default: return { label: 'Cálculo', bg: 'var(--teal-bg)', color: 'var(--teal-light)', icon: <FileText size={12} /> };
  }
}

function fmtFecha(fecha: Timestamp | Date): string {
  const d = fecha instanceof Timestamp ? fecha.toDate() : new Date(fecha);
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

interface HistorialCardProps {
  record: DeclaracionRecord;
  isExpanded: boolean;
  onToggle: () => void;
  resumen: string;
  profile: { nombre: string; rfc: string };
  fmtMoney: (n: number) => string;
}

export default function HistorialCard({ record, isExpanded, onToggle, resumen, profile, fmtMoney }: HistorialCardProps) {
  const badge = getBadge(record.categoria);

  return (
    <div className="card" style={{ marginBottom: 8, padding: 0 }}>
      <div
        style={{
          display: 'grid', gridTemplateColumns: '0.8fr 1fr 1fr 1.5fr 60px',
          gap: 8, padding: '14px 20px', alignItems: 'center', cursor: 'pointer',
        }}
        onClick={onToggle}
      >
        <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
          {fmtFecha(record.fecha_calculo)}
        </span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 10px', borderRadius: 'var(--radius-full)',
          fontSize: '0.7rem', fontWeight: 600, background: badge.bg, color: badge.color, width: 'fit-content',
        }}>
          {badge.icon} {badge.label}
        </span>
        <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{record.periodo}</span>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
          {resumen}
        </span>
        <span style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </div>

      {isExpanded && (
        <div style={{ padding: '0 20px 20px', borderTop: '1px solid var(--border)' }}>
          <ExpandedDetail record={record} profile={profile} fmtMoney={fmtMoney} />
        </div>
      )}
    </div>
  );
}
