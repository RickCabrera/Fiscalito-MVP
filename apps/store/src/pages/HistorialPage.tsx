/** Página de historial — muestra todos los cálculos organizados por categoría */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { obtenerHistorial, type DeclaracionRecord, type HistorialCategoria } from '../services/declaracionesHistory';
import { Timestamp } from 'firebase/firestore';
import { History, Loader, FileText, ArrowRight } from 'lucide-react';
import HistorialFilters from '../components/historial/HistorialFilters';
import HistorialCard from '../components/historial/HistorialCard';
import { fmtMoney } from '../utils/format';

function getResumen(d: DeclaracionRecord): string {
  switch (d.categoria) {
    case 'diot': return `${d.proveedores?.length ?? 0} proveedores · IVA ${fmtMoney(d.total_iva ?? 0)}`;
    case 'retenciones': return `ISR ${fmtMoney(d.total_isr_retenido ?? 0)} · IVA ${fmtMoney(d.total_iva_retenido ?? 0)}`;
    case 'multiperiodo': return `${d.resultados?.length ?? 0} periodos · Total ${fmtMoney(d.acumulado?.total_general ?? 0)}`;
    case 'estado_cuenta': {
      const ec = d.estado_cuenta;
      return ec ? `Ingresos ${fmtMoney(ec.ingresos_acumulados)} · ISR faltante ${fmtMoney(ec.isr_faltante)}` : '';
    }
    default: {
      if (!d.desglose) return '';
      const t = d.desglose.total_a_pagar;
      return t <= 0 ? `${fmtMoney(Math.abs(t))} a favor` : fmtMoney(t);
    }
  }
}

export default function HistorialPage() {
  const { user } = useAuth();
  const { profile } = useProfile();
  const [declaraciones, setDeclaraciones] = useState<DeclaracionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filtroAnio, setFiltroAnio] = useState('');
  const [filtroCat, setFiltroCat] = useState<HistorialCategoria | ''>('');

  const recargar = useCallback(() => {
    if (!user?.uid) return;
    setLoading(true);
    const cat = filtroCat || undefined;
    obtenerHistorial(user.uid, 30, cat)
      .then(setDeclaraciones)
      .catch((err) => console.warn('Error cargando historial:', err))
      .finally(() => setLoading(false));
  }, [user?.uid, filtroCat]);

  useEffect(() => { recargar(); }, [recargar]);

  const filtered = declaraciones.filter((d) => {
    if (filtroAnio) {
      const fecha = d.fecha_calculo instanceof Timestamp
        ? d.fecha_calculo.toDate() : new Date(d.fecha_calculo);
      if (fecha.getFullYear() !== Number(filtroAnio)) return false;
    }
    return true;
  });

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <History size={28} color="var(--teal-light)" />
          Historial
        </h1>
        <p>Consulta todos tus cálculos fiscales.</p>
      </div>

      <HistorialFilters filtroCat={filtroCat} filtroAnio={filtroAnio} onCatChange={setFiltroCat} onAnioChange={setFiltroAnio} />

      {loading ? (
        <div className="animate-in" style={{ textAlign: 'center', padding: '60px 0' }}>
          <Loader size={28} className="spin" color="var(--teal-light)" />
          <p style={{ color: 'var(--text-muted)', marginTop: 12, fontSize: '0.9rem' }}>Cargando historial...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="animate-in card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <FileText size={40} color="var(--text-muted)" style={{ marginBottom: 16 }} />
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginBottom: 8 }}>
            {declaraciones.length === 0 ? 'Aún no has realizado cálculos.' : 'No hay resultados con estos filtros.'}
          </p>
          {declaraciones.length === 0 && (
            <Link to="/app/store/fiscalito/use">
              <button className="btn-primary" style={{ marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                Ir a Fiscalito <ArrowRight size={16} />
              </button>
            </Link>
          )}
        </div>
      ) : (
        <div className="animate-in" style={{ animationDelay: '0.15s' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '0.8fr 1fr 1fr 1.5fr 60px',
            gap: 8, padding: '10px 20px', fontSize: '0.75rem', fontWeight: 500,
            color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            <span>Fecha</span>
            <span>Categoría</span>
            <span>Periodo</span>
            <span>Resumen</span>
            <span />
          </div>

          {filtered.map((d) => (
            <HistorialCard
              key={d.id}
              record={d}
              isExpanded={expanded === d.id}
              onToggle={() => setExpanded(expanded === d.id ? null : (d.id ?? null))}
              resumen={getResumen(d)}
              profile={profile}
              fmtMoney={fmtMoney}
            />
          ))}
        </div>
      )}
    </div>
  );
}
