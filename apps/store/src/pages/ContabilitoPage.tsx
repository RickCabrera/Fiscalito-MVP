/**
 * Contabilito — la contabilidad del CLIENTE ACTIVO (plan P, P2-01 a P2-05 y P2-08:
 * reportes contables y cierre de periodo y de ejercicio).
 *
 * QUÉ CAMBIÓ CONTRA EL CASCARÓN DE T7: ya no se suben XML ni se arman pólizas
 * en el navegador. El backend es el dueño del catálogo, de la configuración de
 * pólizas automáticas, de las pólizas (generadas desde la bóveda de CFDI, una
 * por UUID) y de la balanza, que se agrega en SQL. Esta página sólo elige el
 * tab y le pasa la clave del cliente activo a cada uno.
 *
 * DE QUIÉN ES LA CONTABILIDAD: del cliente activo del selector superior. Ya no
 * hay RFC que teclear: la bóveda clasificó cada CFDI como emitido o recibido
 * con el RFC del cliente al importarlo. Al cambiar de cliente el contenido se
 * REMONTA (`key`), para que nada de un cliente se pinte sobre otro.
 *
 * P2-06: tab Conciliación (estado de cuenta vs pólizas). P2-07: el tab Buzón
 * genera y valida la contabilidad electrónica del Anexo 24.
 */

import { useContext, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, CalendarCheck, FileBarChart, FileStack, Inbox, Landmark, Scale, Settings2 } from 'lucide-react';
import { ClienteActivoContext } from '../context/clienteActivoStore';
import CatalogoCuentas from '../components/contabilidad/CatalogoCuentas';
import ConfigPolizas from '../components/contabilidad/ConfigPolizas';
import PolizasCliente from '../components/contabilidad/PolizasCliente';
import BalanzaCliente from '../components/contabilidad/BalanzaCliente';
import BuzonTab from '../components/contabilidad/BuzonTab';
import ReportesContables from '../components/contabilidad/ReportesContables';
import PeriodosContables from '../components/contabilidad/PeriodosContables';
import ConciliacionBancaria from '../components/contabilidad/ConciliacionBancaria';
import SinClienteActivo from '../components/common/SinClienteActivo';

type TabContabilito = 'catalogo' | 'config' | 'polizas' | 'balanza' | 'conciliacion' | 'reportes' | 'periodos' | 'buzon';

const TABS: { id: TabContabilito; label: string; icon: React.ReactNode }[] = [
  { id: 'catalogo', label: 'Catálogo', icon: <BookOpen size={16} /> },
  { id: 'config', label: 'Configuración', icon: <Settings2 size={16} /> },
  { id: 'polizas', label: 'Pólizas', icon: <FileStack size={16} /> },
  { id: 'balanza', label: 'Balanza', icon: <Scale size={16} /> },
  { id: 'conciliacion', label: 'Conciliación', icon: <Landmark size={16} /> },
  { id: 'reportes', label: 'Reportes', icon: <FileBarChart size={16} /> },
  { id: 'periodos', label: 'Periodos', icon: <CalendarCheck size={16} /> },
  { id: 'buzon', label: 'Buzón', icon: <Inbox size={16} /> },
];

const IDS_TAB = TABS.map((t) => t.id);

export default function ContabilitoPage() {
  const activo = useContext(ClienteActivoContext);
  const clave = activo?.clienteId ?? null;
  if (!clave) {
    return (
      <SinClienteActivo
        titulo="Contabilito"
        explicacion="La contabilidad es de un cliente: su catálogo, sus pólizas y su balanza. Elige uno en el selector de arriba."
      />
    );
  }
  return <ContabilidadDelCliente key={clave} clave={clave} nombre={activo?.cliente?.nombre ?? clave} rfc={activo?.cliente?.rfc ?? ''} />;
}

function ContabilidadDelCliente({ clave, nombre, rfc }: { clave: string; nombre: string; rfc: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [polizaAbierta, setPolizaAbierta] = useState<number | null>(null);

  const tabParam = searchParams.get('tab') as TabContabilito | null;
  const activeTab: TabContabilito = tabParam && IDS_TAB.includes(tabParam) ? tabParam : 'polizas';
  const irA = (tab: TabContabilito) => setSearchParams({ tab }, { replace: true });

  return (
    <div className="page-container">
      <Link
        to="/app/store/contabilito"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 24,
        }}
      >
        <ArrowLeft size={16} /> Información
      </Link>

      <div className="animate-in" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        <div style={{
          width: 52, height: 52, borderRadius: 'var(--radius-sm)',
          background: 'var(--accent-gradient)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', flexShrink: 0,
        }}>
          📊
        </div>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: -0.5 }}>Contabilito</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Catálogo, pólizas y balanza de {nombre}, desde su bóveda de CFDI
          </p>
        </div>
      </div>

      <div className="animate-in" style={{
        animationDelay: '0.1s', overflowX: 'auto', marginBottom: 28,
        WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none',
      }}>
        <div role="tablist" style={{
          display: 'flex', gap: 6, padding: 4, background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-full)', border: '1px solid var(--border)',
          width: 'fit-content', minWidth: '100%',
        }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => irA(tab.id)}
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

      <div className="animate-in" style={{ animationDelay: '0.15s' }}>
        {activeTab === 'catalogo' && <CatalogoCuentas clave={clave} />}
        {activeTab === 'config' && <ConfigPolizas clave={clave} />}
        {activeTab === 'polizas' && (
          <PolizasCliente key={polizaAbierta ?? 'lista'} clave={clave} polizaInicial={polizaAbierta} />
        )}
        {activeTab === 'balanza' && (
          <BalanzaCliente clave={clave} onAbrirPoliza={(id) => { setPolizaAbierta(id); irA('polizas'); }} />
        )}
        {activeTab === 'conciliacion' && <ConciliacionBancaria clave={clave} />}
        {activeTab === 'reportes' && <ReportesContables clave={clave} nombre={nombre} rfc={rfc} onVerBalanza={() => irA('balanza')} />}
        {activeTab === 'periodos' && <PeriodosContables clave={clave} />}
        {activeTab === 'buzon' && <BuzonTab clave={clave} />}
      </div>
    </div>
  );
}
