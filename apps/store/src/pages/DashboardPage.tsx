/** Dashboard principal — muestra herramientas activas de Fiscalito con últimos datos */

import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import {
  obtenerEstadisticas, obtenerHistorial,
  type DashboardStats, type DeclaracionRecord, type HistorialCategoria,
} from '../services/declaracionesHistory';
import { Timestamp } from 'firebase/firestore';
import { Link } from 'react-router-dom';
import { formatMoney } from '../utils/format';
import {
  ArrowRight, FileText, Calculator, Calendar, BarChart3,
  FileSpreadsheet, Users, TrendingUp, Wallet, Clock, Zap, Loader,
} from 'lucide-react';

// ── Tipos ──

type TabId = 'declaracion' | 'deducciones' | 'calendario' | 'comparar' | 'diot' | 'retenciones' | 'multiperiodo' | 'estado';

interface ServiceDef {
  id: TabId;
  label: string;
  icon: React.ReactNode;
  color: string;
  categoria?: HistorialCategoria;
  tabParam: string;
  descripcion: string;
}

const SERVICES: ServiceDef[] = [
  { id: 'declaracion',  label: 'Pre-declaración',      icon: <FileText size={20} />,      color: 'var(--teal-light)',    categoria: 'predeclaracion', tabParam: 'declaracion',  descripcion: 'ISR/IVA mensual o bimestral' },
  { id: 'deducciones',  label: 'Deducciones',          icon: <Calculator size={20} />,    color: 'var(--success)',       categoria: 'deducciones',    tabParam: 'deducciones',  descripcion: 'Deducciones personales anuales' },
  { id: 'calendario',   label: 'Calendario fiscal',    icon: <Calendar size={20} />,      color: 'var(--warning)',       tabParam: 'calendario',   descripcion: 'Obligaciones y fechas límite' },
  { id: 'comparar',     label: 'Comparar regímenes',   icon: <BarChart3 size={20} />,     color: 'var(--purple-light)',  tabParam: 'comparar',     descripcion: 'RESICO vs Actividad Empresarial' },
  { id: 'diot',         label: 'DIOT',                 icon: <FileSpreadsheet size={20} />, color: 'var(--teal-light)',  categoria: 'diot',           tabParam: 'diot',         descripcion: 'Declaración de proveedores' },
  { id: 'retenciones',  label: 'Retenciones',          icon: <Users size={20} />,         color: 'var(--warning)',       categoria: 'retenciones',    tabParam: 'retenciones',  descripcion: 'ISR/IVA retenido a terceros' },
  { id: 'multiperiodo', label: 'Multi-periodo',        icon: <TrendingUp size={20} />,    color: 'var(--success)',       categoria: 'multiperiodo',   tabParam: 'multiperiodo', descripcion: 'Análisis anual por mes' },
  { id: 'estado',       label: 'Estado de cuenta',     icon: <Wallet size={20} />,        color: 'var(--teal-light)',    categoria: 'estado_cuenta',  tabParam: 'estado-cuenta',descripcion: 'Proyección e ISR faltante' },
];

function getTabsForProfile(contributorType: string | null, regimen: string | null): TabId[] {
  if (contributorType === 'asalariado' || regimen === '605')
    return ['deducciones', 'calendario'];
  if (contributorType === 'pyme')
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  if (regimen === '626')
    return ['declaracion', 'calendario', 'comparar', 'estado'];
  if (regimen === '612')
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  if (contributorType === 'arrendamiento' || regimen === '606')
    return ['declaracion', 'calendario', 'comparar', 'multiperiodo', 'estado'];
  if (contributorType === 'plataformas' || regimen === '625')
    return ['declaracion', 'calendario', 'estado'];
  return ['declaracion', 'calendario', 'estado'];
}

function formatFecha(fecha: Timestamp | Date): string {
  const d = fecha instanceof Timestamp ? fecha.toDate() : new Date(fecha);
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Sublínea de último dato por categoría ──

function UltimosDatos({ def, record }: { def: ServiceDef; record: DeclaracionRecord | null }) {
  if (!record) {
    return (
      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Sin cálculos aún</span>
    );
  }

  const fecha = <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{record.periodo} · {formatFecha(record.fecha_calculo)}</span>;

  if (def.categoria === 'predeclaracion' || def.categoria === 'deducciones') {
    const total = record.desglose?.total_a_pagar ?? 0;
    const aFavor = total <= 0;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.95rem', fontWeight: 700, color: aFavor ? 'var(--success)' : 'var(--text-primary)' }}>
          {aFavor ? `${formatMoney(Math.abs(total))} a favor` : formatMoney(total)}
        </span>
        {fecha}
      </div>
    );
  }

  if (def.categoria === 'diot') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem', fontWeight: 600, color: def.color }}>
          {record.proveedores?.length ?? 0} proveedores · {formatMoney(record.total_iva ?? 0)} IVA
        </span>
        {fecha}
      </div>
    );
  }

  if (def.categoria === 'retenciones') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem', fontWeight: 600, color: def.color }}>
          ISR {formatMoney(record.total_isr_retenido ?? 0)} · IVA {formatMoney(record.total_iva_retenido ?? 0)}
        </span>
        {fecha}
      </div>
    );
  }

  if (def.categoria === 'multiperiodo') {
    const ac = record.acumulado;
    const tendIcon = ac?.tendencia === 'subiendo' ? '📈' : ac?.tendencia === 'bajando' ? '📉' : '➡️';
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem', fontWeight: 600, color: def.color }}>
          {tendIcon} {formatMoney(ac?.total_general ?? 0)} total año
        </span>
        {fecha}
      </div>
    );
  }

  if (def.categoria === 'estado_cuenta') {
    const ec = record.estado_cuenta;
    const faltante = ec?.isr_faltante ?? 0;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem', fontWeight: 600, color: faltante <= 0 ? 'var(--success)' : 'var(--warning)' }}>
          {formatMoney(ec?.ingresos_acumulados ?? 0)} ingresos · ISR {faltante <= 0 ? `${formatMoney(Math.abs(faltante))} a favor` : `${formatMoney(faltante)} faltante`}
        </span>
        {fecha}
      </div>
    );
  }

  return fecha;
}

// ── Dashboard ──

export default function DashboardPage() {
  const { user } = useAuth();
  const { profile } = useProfile();
  const tipo = profile.contributorType;
  const name = profile.nombre || user?.displayName || user?.email?.split('@')[0] || 'Usuario';

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [ultimosPorCategoria, setUltimosPorCategoria] = useState<Partial<Record<HistorialCategoria, DeclaracionRecord>>>({});
  const [loadingStats, setLoadingStats] = useState(true);

  const allowedTabs = getTabsForProfile(tipo, profile.regimen);
  const visibleServices = SERVICES.filter((s) => allowedTabs.includes(s.id));

  useEffect(() => {
    if (!user?.uid) return;
    Promise.all([
      obtenerEstadisticas(user.uid),
      obtenerHistorial(user.uid, 50),
    ])
      .then(([s, h]) => {
        setStats(s);
        const map: Partial<Record<HistorialCategoria, DeclaracionRecord>> = {};
        for (const record of h) {
          if (!map[record.categoria]) map[record.categoria] = record;
        }
        setUltimosPorCategoria(map);
      })
      .catch(() => {})
      .finally(() => setLoadingStats(false));
  }, [user?.uid]);

  return (
    <div className="page-container">
      {/* Welcome */}
      <div className="page-header animate-in">
        <h1>Bienvenido, <span className="gradient-text">{name}</span></h1>
        <p>Aquí están tus herramientas fiscales y el último estado de cada una.</p>
      </div>

      {/* Quick stats */}
      <div className="animate-in responsive-grid-3" style={{ animationDelay: '0.05s', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 36 }}>
        {getStatsForType(tipo, stats, loadingStats).map((stat, i) => (
          <div key={i} className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 'var(--radius-sm)', background: `${stat.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: stat.color, flexShrink: 0 }}>
              {stat.loading && loadingStats ? <Loader size={18} className="spin" /> : stat.icon}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: stat.color }}>
                {stat.loading && loadingStats
                  ? <div className="skeleton" style={{ height: 24, width: 68, borderRadius: 4 }} />
                  : stat.value}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Service cards */}
      <div className="animate-in" style={{ animationDelay: '0.1s', marginBottom: 8 }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 16 }}>Tus herramientas</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
          {visibleServices.map((def) => {
            const record = def.categoria ? (ultimosPorCategoria[def.categoria] ?? null) : null;
            return (
              <Link key={def.id} to={`/app/store/fiscalito/use?tab=${def.tabParam}`} style={{ textDecoration: 'none' }}>
                <div
                  className="card"
                  style={{ padding: '16px 18px', cursor: 'pointer', transition: 'all 0.2s' }}
                  onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = 'var(--shadow-md)'; }}
                  onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = ''; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 34, height: 34, borderRadius: 8, background: 'var(--purple-bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
                        {def.icon}
                      </div>
                      <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>{def.label}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{def.descripcion}</div>
                      </div>
                    </div>
                    <ArrowRight size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                  </div>
                  <div style={{ paddingLeft: 44 }}>
                    {loadingStats && def.categoria
                      ? <div className="skeleton" style={{ height: 16, width: 140, borderRadius: 4 }} />
                      : <UltimosDatos def={def} record={record} />}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Stats por tipo de contribuyente ──

interface StatItem { icon: React.ReactNode; label: string; value: string; color: string; loading?: boolean }

function getStatsForType(tipo: string | null, stats: DashboardStats | null, _loading: boolean): StatItem[] {
  if (tipo === 'asalariado') {
    return [
      { icon: <FileText size={18} />, label: 'Próxima declaración anual', value: 'Abr 2026', color: 'var(--teal-light)' },
      { icon: <TrendingUp size={18} />, label: 'Declaraciones calculadas', value: stats ? stats.totalDeclaraciones.toString() : '—', color: 'var(--purple-light)', loading: true },
      { icon: <Zap size={18} />, label: 'Saldo a favor estimado', value: stats ? formatMoney(stats.saldoFavorAcumulado) : '—', color: 'var(--success)', loading: true },
    ];
  }
  if (tipo === 'pyme') {
    return [
      { icon: <Clock size={18} />, label: 'Declaraciones este mes', value: stats ? stats.declaracionesEsteMes.toString() : '—', color: 'var(--teal-light)', loading: true },
      { icon: <Users size={18} />, label: 'Total declaraciones', value: stats ? stats.totalDeclaraciones.toString() : '—', color: 'var(--purple-light)', loading: true },
      { icon: <TrendingUp size={18} />, label: 'ISR último periodo', value: stats ? formatMoney(stats.ultimoISR) : '—', color: 'var(--warning)', loading: true },
    ];
  }
  return [
    { icon: <Clock size={18} />, label: 'Declaraciones este mes', value: stats ? stats.declaracionesEsteMes.toString() : '—', color: 'var(--teal-light)', loading: true },
    { icon: <TrendingUp size={18} />, label: 'ISR último periodo', value: stats ? formatMoney(stats.ultimoISR) : '—', color: 'var(--purple-light)', loading: true },
    { icon: <Zap size={18} />, label: 'Saldo a favor acumulado', value: stats ? formatMoney(stats.saldoFavorAcumulado) : '—', color: 'var(--success)', loading: true },
  ];
}
