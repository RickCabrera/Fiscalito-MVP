/**
 * Contabilito — cascarón de contabilidad electrónica (T7).
 *
 * QUÉ HACE: toma los CFDI que ya sabe leer `cfdiParser.ts`, los convierte en
 * pólizas de partida doble contra el código agrupador del SAT y suma la
 * balanza. Todo en el navegador: **no llama al API**, y no tiene por qué —
 * ningún importe se calcula aquí, se acomodan los que el XML ya trae.
 *
 * QUÉ NO HACE: no guarda nada. Los comprobantes viven en el estado de esta
 * pantalla y se van al salir, igual que en los tabs de Fiscalito. Persistir la
 * contabilidad de un cliente es tarea propia, no un efecto secundario de un
 * cascarón.
 *
 * DE QUIÉN ES LA CONTABILIDAD QUE SE ESTÁ VIENDO
 * ---------------------------------------------
 * De quien diga el RFC de arriba, y esa pregunta no es cosmética: el mismo CFDI
 * es un ingreso para quien lo emitió y un gasto para quien lo recibió, así que
 * **el RFC decide de qué lado de la póliza cae cada cuenta**. Se resuelve en
 * este orden: lo tecleado a mano, el RFC del contribuyente —que **no aplica a
 * un despacho**, ver abajo— y, si no hay ninguno, el que más se repite entre
 * los comprobantes cargados. Se enseña y se puede corregir a mano: una
 * suposición que no se ve es una suposición que nadie desmiente.
 */

import { useContext, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, FileStack, Scale, Inbox } from 'lucide-react';
import { useProfile } from '../context/ProfileContext';
import { ClienteActivoContext } from '../context/clienteActivoStore';
import { esContador } from '../services/navigation';
import XMLUploader from '../components/fiscalito/XMLUploader';
import CatalogoTab from '../components/contabilidad/CatalogoTab';
import PolizasTab from '../components/contabilidad/PolizasTab';
import BalanzaTab from '../components/contabilidad/BalanzaTab';
import BuzonTab from '../components/contabilidad/BuzonTab';
import { generarPolizas, inferirRfcPropio } from '../services/contabilidad/polizas';
import { generarBalanza } from '../services/contabilidad/balanza';
import type { CFDI } from '../services/fiscalAgentApi';
import { labelStyle } from '../utils/styles';

type TabContabilito = 'catalogo' | 'polizas' | 'balanza' | 'buzon';

const TABS: { id: TabContabilito; label: string; icon: React.ReactNode }[] = [
  { id: 'catalogo', label: 'Catálogo', icon: <BookOpen size={16} /> },
  { id: 'polizas', label: 'Pólizas', icon: <FileStack size={16} /> },
  { id: 'balanza', label: 'Balanza', icon: <Scale size={16} /> },
  { id: 'buzon', label: 'Buzón', icon: <Inbox size={16} /> },
];

const IDS_TAB = TABS.map((t) => t.id);

export default function ContabilitoPage() {
  const { profile } = useProfile();
  const clienteActivo = useContext(ClienteActivoContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const [facturas, setFacturas] = useState<CFDI[]>([]);
  /** RFC tecleado a mano. Vacío = manda el resuelto. */
  const [rfcManual, setRfcManual] = useState('');

  const esDespacho = esContador(profile.contributorType);
  const cliente = esDespacho ? clienteActivo?.cliente ?? null : null;

  const rfcInferido = useMemo(() => inferirRfcPropio(facturas), [facturas]);
  /**
   * El RFC capturado que sirve para ESTA pantalla.
   *
   * Para un contador **no hay ninguno**, y eso es deliberado: `profile.rfc` es
   * el del DESPACHO, no el del cliente cuya contabilidad se está armando, y
   * `ClienteResumen` no trae RFC —el catálogo del despacho nunca lo expuso—.
   * Usar el del despacho clasificaría todas las facturas del cliente como
   * ajenas y voltearía cada póliza. Es la misma trampa que T6 documentó con
   * `profile.regimen`.
   */
  const rfcDeLaFicha = esDespacho ? '' : (profile.rfc || '').toUpperCase();
  const rfcPropio = (rfcManual || rfcDeLaFicha || rfcInferido).toUpperCase();
  /** El RFC en uso no salió de una ficha: se dedujo de los comprobantes. */
  const rfcDeducido = !rfcManual && !rfcDeLaFicha && rfcInferido !== '';

  const { polizas, recibosNomina, sinEfecto } = useMemo(
    () => generarPolizas(facturas, rfcPropio),
    [facturas, rfcPropio],
  );
  const balanza = useMemo(() => generarBalanza(polizas), [polizas]);

  const tabParam = searchParams.get('tab') as TabContabilito | null;
  const activeTab: TabContabilito =
    tabParam && IDS_TAB.includes(tabParam) ? tabParam : 'polizas';

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
            {cliente
              ? `Pólizas y balanza de ${cliente.nombre}`
              : 'Pólizas y balanza desde tus CFDI'}
          </p>
        </div>
      </div>

      {/* Carga de comprobantes + de quién son. Va arriba de los tabs porque los
          tres primeros dependen de esto y el cuarto no depende de nada. */}
      <div className="card animate-in" style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <XMLUploader facturas={facturas} onChange={setFacturas} />

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12 }}>
          <div style={{ minWidth: 220 }}>
            <label style={labelStyle} htmlFor="rfc-contabilito">
              RFC del contribuyente
            </label>
            <input
              id="rfc-contabilito"
              className="input-field"
              value={rfcManual || rfcPropio}
              placeholder="Sin RFC"
              onChange={(e) => setRfcManual(e.target.value.toUpperCase().trim())}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
          </div>
          <p style={{ margin: 0, flex: 1, minWidth: 260, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {rfcPropio === ''
              ? 'Sin RFC, cada comprobante se clasifica por su tipo: los de Ingreso se toman como emitidos. Captúralo para que sea el RFC quien decida.'
              : rfcDeducido
                ? 'Deducido de los comprobantes cargados: es el RFC que aparece en todos. Corrígelo si no es el tuyo.'
                : 'Decide de qué lado cae cada póliza: lo que emitiste es ingreso, lo que recibiste es gasto.'}
          </p>
        </div>
      </div>

      <div className="animate-in" style={{
        animationDelay: '0.1s', overflowX: 'auto', marginBottom: 28,
        WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none',
      }}>
        <div style={{
          display: 'flex', gap: 6, padding: 4, background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-full)', border: '1px solid var(--border)',
          width: 'fit-content', minWidth: '100%',
        }}>
          {TABS.map((tab) => (
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

      <div className="animate-in" style={{ animationDelay: '0.15s' }}>
        {activeTab === 'catalogo' && <CatalogoTab />}
        {activeTab === 'polizas' && (
          <PolizasTab polizas={polizas} recibosNomina={recibosNomina} sinEfecto={sinEfecto} />
        )}
        {activeTab === 'balanza' && <BalanzaTab balanza={balanza} />}
        {activeTab === 'buzon' && <BuzonTab />}
      </div>
    </div>
  );
}
