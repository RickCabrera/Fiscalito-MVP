/** Página principal del servicio Fiscalito — interfaz para usar el servicio */

import { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import PreDeclaracionTab from '../components/fiscalito/PreDeclaracionTab';
import DeduccionesPersonalesTab from '../components/fiscalito/DeduccionesPersonalesTab';
import CalendarioTab from '../components/fiscalito/CalendarioTab';
import CompararRegimenTab from '../components/fiscalito/CompararRegimenTab';
import DIOTTab from '../components/fiscalito/DIOTTab';
import RetencionesTab from '../components/fiscalito/RetencionesTab';
import MultiPeriodoTab from '../components/fiscalito/MultiPeriodoTab';
import EstadoCuentaTab from '../components/fiscalito/EstadoCuentaTab';
import { ArrowLeft, FileText, Calendar, BarChart3, FileSpreadsheet, Users, TrendingUp, Wallet, Calculator } from 'lucide-react';

type Tab = 'declaracion' | 'deducciones' | 'calendario' | 'comparar' | 'diot' | 'retenciones' | 'multiperiodo' | 'estado';

const ALL_TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'declaracion', label: 'Pre-declaración', icon: <FileText size={16} /> },
  { id: 'deducciones', label: 'Deducciones personales', icon: <Calculator size={16} /> },
  { id: 'calendario', label: 'Calendario fiscal', icon: <Calendar size={16} /> },
  { id: 'comparar', label: 'Comparar regímenes', icon: <BarChart3 size={16} /> },
  { id: 'diot', label: 'DIOT', icon: <FileSpreadsheet size={16} /> },
  { id: 'retenciones', label: 'Retenciones', icon: <Users size={16} /> },
  { id: 'multiperiodo', label: 'Multi-periodo', icon: <TrendingUp size={16} /> },
  { id: 'estado', label: 'Estado de cuenta', icon: <Wallet size={16} /> },
];

function getTabsForProfile(contributorType: string | null, regimen: string | null): Tab[] {
  // Asalariado: solo deducciones personales y calendario
  if (contributorType === 'asalariado' || regimen === '605') {
    return ['deducciones', 'calendario'];
  }

  // PYME: todo (tiene empleados, más obligaciones)
  if (contributorType === 'pyme') {
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  }

  // RESICO: simplificado, sin DIOT ni retenciones
  if (regimen === '626') {
    return ['declaracion', 'calendario', 'comparar', 'estado'];
  }

  // Act. Empresarial: todo menos deducciones personales
  if (regimen === '612') {
    return ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado'];
  }

  // Arrendamiento: sin DIOT ni retenciones
  if (contributorType === 'arrendamiento' || regimen === '606') {
    return ['declaracion', 'calendario', 'comparar', 'multiperiodo', 'estado'];
  }

  // Plataformas: básico
  if (contributorType === 'plataformas' || regimen === '625') {
    return ['declaracion', 'calendario', 'estado'];
  }

  // Default: pre-declaración + calendario + estado
  return ['declaracion', 'calendario', 'estado'];
}

const TAB_PARAM_MAP: Record<string, Tab> = {
  predeclaracion: 'declaracion',
  declaracion: 'declaracion',
  deducciones: 'deducciones',
  calendario: 'calendario',
  comparar: 'comparar',
  diot: 'diot',
  retenciones: 'retenciones',
  multiperiodo: 'multiperiodo',
  'estado-cuenta': 'estado',
  estado: 'estado',
};

export default function FiscalitoServicePage() {
  const { profile } = useProfile();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');

  // Memoize so the array reference is stable across renders — otherwise the
  // sync effect below would fire on every render and clobber manual tab clicks.
  const allowedTabIds = useMemo(
    () => getTabsForProfile(profile.contributorType, profile.regimen),
    [profile.contributorType, profile.regimen],
  );
  const tabs = ALL_TABS.filter(t => allowedTabIds.includes(t.id));
  const defaultTab = allowedTabIds[0];

  const initialTab = (tabParam && TAB_PARAM_MAP[tabParam] && allowedTabIds.includes(TAB_PARAM_MAP[tabParam]))
    ? TAB_PARAM_MAP[tabParam]
    : defaultTab;
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);

  // Sync tab when URL query param changes (e.g. voice chat navigation),
  // then clear the query param so it doesn't keep overriding manual clicks.
  useEffect(() => {
    if (tabParam && TAB_PARAM_MAP[tabParam] && allowedTabIds.includes(TAB_PARAM_MAP[tabParam])) {
      setActiveTab(TAB_PARAM_MAP[tabParam]);
      setSearchParams({}, { replace: true });
    }
  }, [tabParam, allowedTabIds, setSearchParams]);

  // Reset to default tab if current tab is no longer allowed (profile change)
  useEffect(() => {
    if (!allowedTabIds.includes(activeTab)) {
      setActiveTab(defaultTab);
    }
  }, [allowedTabIds, activeTab, defaultTab]);

  return (
    <div className="page-container">
      {/* Back link */}
      <Link to="/app/store/fiscalito" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 24 }}>
        <ArrowLeft size={16} /> Información
      </Link>

      {/* Header */}
      <div className="animate-in" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        <div style={{
          width: 52, height: 52, borderRadius: 'var(--radius-sm)',
          background: 'var(--accent-gradient)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', flexShrink: 0,
        }}>
          ⚖
        </div>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: -0.5 }}>Fiscalito</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {allowedTabIds.includes('deducciones') && !allowedTabIds.includes('declaracion')
              ? 'Calcula tus deducciones personales y saldo a favor'
              : 'Calcula tus pre-declaraciones ISR/IVA'}
          </p>
        </div>
      </div>

      {/* Tab selector — horizontal scroll */}
      <div className="animate-in" style={{
        animationDelay: '0.1s', overflowX: 'auto', marginBottom: 28,
        WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none',
      }}>
        <div style={{
          display: 'flex', gap: 6,
          padding: 4, background: 'var(--bg-surface)', borderRadius: 'var(--radius-full)',
          border: '1px solid var(--border)', width: 'fit-content', minWidth: '100%',
        }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 16px', borderRadius: 'var(--radius-full)',
                fontSize: '0.82rem', fontWeight: activeTab === tab.id ? 600 : 400,
                background: activeTab === tab.id ? 'var(--accent-gradient)' : 'transparent',
                color: activeTab === tab.id ? 'var(--text-on-accent)' : 'var(--text-secondary)',
                border: 'none', cursor: 'pointer', transition: 'all 0.2s',
                whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="animate-in" style={{ animationDelay: '0.15s' }}>
        {activeTab === 'declaracion' && <PreDeclaracionTab />}
        {activeTab === 'deducciones' && <DeduccionesPersonalesTab />}
        {activeTab === 'calendario' && <CalendarioTab />}
        {activeTab === 'comparar' && <CompararRegimenTab />}
        {activeTab === 'diot' && <DIOTTab />}
        {activeTab === 'retenciones' && <RetencionesTab />}
        {activeTab === 'multiperiodo' && <MultiPeriodoTab />}
        {activeTab === 'estado' && <EstadoCuentaTab />}
      </div>
    </div>
  );
}
