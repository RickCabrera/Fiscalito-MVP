/**
 * Página principal del servicio Fiscalito — interfaz para usar el servicio.
 *
 * DOS SUJETOS, UNA PANTALLA (T1)
 * ------------------------------
 * Un CONTRIBUYENTE entra aquí a ver lo suyo, y el régimen que manda es el de su
 * perfil. Un CONTADOR entra a ver lo de UN CLIENTE, y el régimen que manda es el
 * de ese cliente — el suyo propio ni siquiera existe desde E-05, que dejó de
 * pedírselo. Todo lo que cambia entre los dos casos sale de esa sola frase: de
 * dónde se lee el régimen, qué dice el encabezado, y qué se pinta cuando no hay
 * cliente que mirar.
 */

import { useContext, useEffect, useMemo } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import { ClienteActivoContext } from '../context/clienteActivoStore';
import { REGIMEN_CLIENTE_POR_DEFECTO } from '../services/carteraApi';
import { modoEmpresaUnica } from '../services/modoEmpresa';
import { getTabsForProfile, esContador, type TabFiscalito } from '../services/navigation';
import PreDeclaracionTab from '../components/fiscalito/PreDeclaracionTab';
import DeduccionesPersonalesTab from '../components/fiscalito/DeduccionesPersonalesTab';
import CalendarioTab from '../components/fiscalito/CalendarioTab';
import CompararRegimenTab from '../components/fiscalito/CompararRegimenTab';
import DIOTTab from '../components/fiscalito/DIOTTab';
import RetencionesTab from '../components/fiscalito/RetencionesTab';
import MultiPeriodoTab from '../components/fiscalito/MultiPeriodoTab';
import EstadoCuentaTab from '../components/fiscalito/EstadoCuentaTab';
import { ArrowLeft, Building2, FileText, Calendar, BarChart3, FileSpreadsheet, Users, TrendingUp, Wallet, Calculator } from 'lucide-react';
import { MARCA_CORTA } from '../services/marca';

type Tab = TabFiscalito;

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

/** Cabecera compartida entre el estado vacío del despacho y la pantalla llena. */
const ICONO_CABECERA: React.CSSProperties = {
  width: 52, height: 52, borderRadius: 'var(--radius-sm)',
  background: 'var(--accent-gradient)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', flexShrink: 0,
};

const TITULO_CABECERA: React.CSSProperties = {
  fontSize: '1.6rem', fontWeight: 800, letterSpacing: -0.5,
};

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

  const esContadorActual = esContador(profile.contributorType);

  /**
   * El cliente activo, **sin exigir el proveedor**.
   *
   * `useClienteActivo()` lanza si no lo encuentra, y con razón: las pantallas
   * del despacho no tienen nada que hacer sin cartera. Ésta sí — es la pantalla
   * de un contribuyente desde antes de que el despacho existiera— así que lee el
   * contexto de frente y aguanta el `null`.
   */
  const clienteActivo = useContext(ClienteActivoContext);
  const cliente = esContadorActual ? clienteActivo?.cliente ?? null : null;
  /** `true` si el régimen que se está aplicando salió del default, no del alta. */
  const regimenSupuesto = esContadorActual && cliente !== null && !cliente.regimen;
  const regimenEnUso = esContadorActual
    ? cliente && (cliente.regimen || REGIMEN_CLIENTE_POR_DEFECTO)
    : profile.regimen;

  // Memoize so the array reference is stable across renders — otherwise the
  // sync effect below would fire on every render and clobber manual tab clicks.
  const allowedTabIds = useMemo(
    () => getTabsForProfile(profile.contributorType, regimenEnUso ?? null),
    [profile.contributorType, regimenEnUso],
  );
  const tabs = ALL_TABS.filter(t => allowedTabIds.includes(t.id));
  // `Tab | undefined`, no `Tab`: la lista puede venir vacía —un despacho sin
  // cliente elegido (T1); antes, un despacho a secas (E-07)— y tipar
  // `allowedTabIds[0]` como `Tab` sería mentirle al compilador.
  const defaultTab: Tab | undefined = allowedTabIds[0];

  // Tab activo derivado de la URL: ?tab=xxx es la fuente de verdad.
  // Así, reload o deep-link siempre restauran el tab correcto.
  const activeTab: Tab | undefined = useMemo(() => {
    if (tabParam) {
      const mapped = TAB_PARAM_MAP[tabParam];
      if (mapped && allowedTabIds.includes(mapped)) return mapped;
    }
    return defaultTab;
  }, [tabParam, allowedTabIds, defaultTab]);

  // Limpia el query param si trae un tab inválido o no permitido por el
  // perfil actual (ej. cambio de perfil que deshabilita el tab en uso).
  useEffect(() => {
    // T1: el despacho YA se queda en esta pantalla, así que el efecto le
    // aplica igual que a un contribuyente... salvo mientras no tenga cliente
    // elegido. Ahí `allowedTabIds` está vacío por falta de dato, no porque el
    // tab no aplique, y limpiar el query borraría el deep-link que el contador
    // quiere ver en cuanto elija cliente.
    if (esContadorActual && !cliente) return;
    if (!tabParam) return;
    const mapped = TAB_PARAM_MAP[tabParam];
    if (!mapped || !allowedTabIds.includes(mapped)) {
      setSearchParams({}, { replace: true });
    }
  }, [esContadorActual, cliente, tabParam, allowedTabIds, setSearchParams]);

  // MODO EMPRESA ÚNICA: el redirect de E-07 se queda exactamente como estaba.
  //
  // Ahí el perfil operador no lleva clientes, lleva UNA empresa: no hay cartera,
  // no hay cliente activo y no hay régimen de cliente que leer, así que T1 no
  // tiene sujeto que ofrecerle. Dejarlo caer al estado vacío de abajo sería
  // mandarlo a elegir un cliente en una app que no tiene clientes.
  //
  // Va DESPUÉS de los hooks (no antes) para no romper su orden entre renders —
  // mismo patrón que `DashboardPage`.
  if (esContadorActual && modoEmpresaUnica()) {
    return <Navigate to="/app/calendario" replace />;
  }

  // T1: despacho sin cliente elegido. El selector vive en la barra de arriba
  // (`SelectorCliente`, que se pinta aquí desde que esta ruta entró a
  // `RUTAS_CON_CLIENTE`), así que lo que falta abajo es decir qué se espera y
  // dar la salida a la cartera cuando ni siquiera hay clientes que elegir.
  if (esContadorActual && !cliente) {
    const sinCartera = (clienteActivo?.clientes.length ?? 0) === 0;
    return (
      <div className="page-container">
        <div className="animate-in" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
          <div style={ICONO_CABECERA}>⚖</div>
          <div>
            <h1 style={TITULO_CABECERA}>{MARCA_CORTA}</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Las declaraciones de tus clientes
            </p>
          </div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
          <Building2 size={28} color="var(--text-muted)" />
          <p style={{ margin: '12px 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            {sinCartera
              ? 'Todavía no tienes clientes en tu cartera.'
              : 'Elige un cliente en la barra de arriba para ver sus declaraciones.'}
          </p>
          {/* La pantalla NO enseña una regla fiscal. Decía "un RESICO no
              presenta DIOT ni retiene a terceros", que es un criterio heredado
              de E-01 sin fuente verificada y, en su mitad de Retenciones,
              probablemente falso (§D30). Un texto así, en la pantalla que lee un
              contador, se toma como afirmación del producto. */}
          <p style={{ margin: '6px 0 16px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Los tabs que se le pueden trabajar dependen del régimen de cada cliente.
          </p>
          <Link className="btn-primary" to="/app/clientes" style={{ display: 'inline-block' }}>
            {sinCartera ? 'Dar de alta un cliente' : 'Ir a mis clientes'}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back link */}
      <Link to={esContadorActual ? '/app/clientes' : '/app/store/fiscalito'} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 24 }}>
        <ArrowLeft size={16} /> {esContadorActual ? 'Clientes' : 'Información'}
      </Link>

      {/* Header */}
      <div className="animate-in" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        <div style={ICONO_CABECERA}>⚖</div>
        <div>
          <h1 style={TITULO_CABECERA}>{MARCA_CORTA}</h1>
          {/* T1: para el despacho el subtítulo NOMBRA al cliente y su régimen.
              Sin eso, la pantalla se ve idéntica para dos clientes con tabs
              distintos y el contador no tiene cómo saber sobre cuál trabaja —
              que es el mismo modo de falla que E-03 cerró en la nómina. */}
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {esContadorActual
              ? `${cliente?.nombre} · régimen ${regimenEnUso}`
              : allowedTabIds.includes('deducciones') && !allowedTabIds.includes('declaracion')
                ? 'Calcula tus deducciones personales y saldo a favor'
                : 'Calcula tus pre-declaraciones ISR/IVA'}
          </p>
        </div>
      </div>

      {/* El régimen que se está aplicando salió del default, no del alta: se
          dice, en vez de filtrar los tabs en silencio con un dato inventado.
          Sólo lo ven los clientes capturados antes de que T1 abriera el campo. */}
      {regimenSupuesto && (
        <p
          role="status"
          className="animate-in"
          style={{
            margin: '-12px 0 20px', fontSize: '0.8rem', color: 'var(--warning)',
          }}
        >
          Este cliente no tiene régimen capturado: se están mostrando los tabs del{' '}
          {REGIMEN_CLIENTE_POR_DEFECTO}. Captúralo en su ficha para ajustarlos.
        </p>
      )}

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
              onClick={() => setSearchParams({ tab: tab.id }, { replace: true })}
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
