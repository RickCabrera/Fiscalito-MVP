/**
 * Tab Pólizas de Contabilito (P2-03): generar las pólizas automáticas del
 * periodo desde la bóveda, lista filtrable, detalle y captura manual.
 *
 * Generar es idempotente (una póliza por UUID), así que el botón se puede
 * apretar las veces que sea. Un rango de más de dos meses se manda a la cola de
 * trabajos y se avisa; "en segundo plano" lo fuerza para cualquier rango.
 */

import { useEffect, useState } from 'react';
import { FilePlus2, Loader, Wand2 } from 'lucide-react';
import {
  generarPolizas, listarPolizas, type FiltrosPolizas, type Poliza, type RespuestaGenerar,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import DetallePoliza from './DetallePoliza';
import FormPoliza from './FormPoliza';
import { ETIQUETA_TIPO_POLIZA, dinero, mensaje, mesDe } from './comun';
import { labelStyle, tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

interface Props {
  clave: string;
  /** Abrir directo esta póliza (viene del auxiliar de la balanza). */
  polizaInicial?: number | null;
}

const POR_PAGINA = 50;

function resumen(r: RespuestaGenerar): string {
  if (r.en_segundo_plano) return `Generación encolada (trabajo #${r.trabajo?.id}). Revisa en unos minutos.`;
  const g = r.resultado;
  if (!g) return 'Listo.';
  const partes = [`${g.generadas} generadas`, `${g.ya_existian} ya existían`];
  if (g.omitidas) partes.push(`${g.omitidas} omitidas por configuración`);
  if (g.canceladas || g.revertidas) partes.push(`${g.canceladas + g.revertidas} canceladas por CFDI cancelado`);
  return partes.join(' · ');
}

export default function PolizasCliente({ clave, polizaInicial = null }: Props) {
  const [filtros, setFiltros] = useState<FiltrosPolizas>({ ...mesDe(), pagina: 1, por_pagina: POR_PAGINA });
  const [lista, setLista] = useState<{ total: number; polizas: Poliza[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [erroresGen, setErroresGen] = useState<{ uuid: string; error: string }[]>([]);
  const [generando, setGenerando] = useState(false);
  const [segundoPlano, setSegundoPlano] = useState(false);
  const [abierta, setAbierta] = useState<number | null>(polizaInicial);
  const [capturando, setCapturando] = useState(false);

  const [recarga, setRecarga] = useState(0);
  const cargar = () => setRecarga((n) => n + 1);

  useEffect(() => {
    let vivo = true;
    listarPolizas(clave, filtros)
      .then((r) => { if (vivo) { setLista({ total: r.total, polizas: r.polizas }); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar las pólizas.')); });
    return () => { vivo = false; };
  }, [clave, filtros, recarga]);

  async function generar() {
    if (!filtros.desde || !filtros.hasta) {
      setError('Elige el periodo (desde y hasta) para generar.');
      return;
    }
    setGenerando(true);
    setError(null);
    setAviso(null);
    try {
      const r = await generarPolizas(clave, filtros.desde, filtros.hasta, segundoPlano || undefined);
      setAviso(resumen(r));
      setErroresGen(r.resultado?.errores ?? []);
      cargar();
    } catch (e) {
      setError(mensaje(e, 'No se pudieron generar las pólizas.'));
    } finally {
      setGenerando(false);
    }
  }

  const cambiar = (p: Partial<FiltrosPolizas>) => setFiltros({ ...filtros, ...p, pagina: 1 });
  const pagina = filtros.pagina ?? 1;
  const paginas = Math.max(1, Math.ceil((lista?.total ?? 0) / POR_PAGINA));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Desde</span>
          <input className="input-field" type="date" value={filtros.desde ?? ''} onChange={(e) => cambiar({ desde: e.target.value })} /></label>
        <label><span style={labelStyle}>Hasta</span>
          <input className="input-field" type="date" value={filtros.hasta ?? ''} onChange={(e) => cambiar({ hasta: e.target.value })} /></label>
        <label><span style={labelStyle}>Tipo</span>
          <select className="input-field" value={filtros.tipo ?? ''} onChange={(e) => cambiar({ tipo: e.target.value as FiltrosPolizas['tipo'] })}>
            <option value="">Todas</option><option value="ingreso">Ingreso</option>
            <option value="egreso">Egreso</option><option value="diario">Diario</option>
          </select></label>
        <label><span style={labelStyle}>Origen</span>
          <select className="input-field" value={filtros.origen ?? ''} onChange={(e) => cambiar({ origen: e.target.value as FiltrosPolizas['origen'] })}>
            <option value="">Todos</option><option value="automatica">Automática</option><option value="manual">Manual</option>
          </select></label>
        <label><span style={labelStyle}>Estado</span>
          <select className="input-field" value={filtros.estado ?? ''} onChange={(e) => cambiar({ estado: e.target.value as FiltrosPolizas['estado'] })}>
            <option value="">Todos</option><option value="activa">Activas</option><option value="cancelada">Canceladas</option>
          </select></label>
        <label style={{ minWidth: 180 }}><span style={labelStyle}>Concepto o UUID</span>
          <input className="input-field" value={filtros.texto ?? ''} onChange={(e) => cambiar({ texto: e.target.value })} /></label>
      </div>

      <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" className="btn-primary" disabled={generando} onClick={() => void generar()}>
          {generando ? <Loader size={14} className="spin" /> : <Wand2 size={14} />} Generar pólizas del periodo
        </button>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.82rem' }}>
          <input type="checkbox" checked={segundoPlano} onChange={(e) => setSegundoPlano(e.target.checked)} />
          En segundo plano
        </label>
        <button type="button" className="btn-secondary" onClick={() => setCapturando(true)}>
          <FilePlus2 size={14} /> Nueva póliza manual
        </button>
      </div>

      {error && <ErrorAlert message={error} />}
      {aviso && <SuccessNotice message={aviso} />}
      {erroresGen.length > 0 && (
        <ErrorAlert message={`${erroresGen.length} CFDI sin póliza: ${erroresGen.slice(0, 3).map((e) => `${e.uuid.slice(0, 8)} (${e.error})`).join('; ')}`} />
      )}

      {capturando && (
        <FormPoliza clave={clave} onListo={(p) => { setCapturando(false); setAbierta(p.id); cargar(); }}
          onCancelar={() => setCapturando(false)} />
      )}
      {abierta !== null && (
        <DetallePoliza clave={clave} polizaId={abierta} onCerrar={() => setAbierta(null)} onCambio={cargar} />
      )}

      {lista === null ? (
        <div className="card"><Loader size={16} className="spin" /> Cargando pólizas…</div>
      ) : lista.polizas.length === 0 ? (
        <div className="card" style={{ color: 'var(--text-secondary)' }}>
          No hay pólizas en este filtro. Genera las del periodo desde la bóveda o captura una manual.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={thStyle}>Folio</th><th style={thStyle}>Fecha</th><th style={thStyle}>Tipo</th>
                <th style={thStyle}>Concepto</th><th style={{ ...thStyle, textAlign: 'right' }}>Cargos</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Abonos</th><th style={thStyle}>Origen</th>
              </tr>
            </thead>
            <tbody>
              {lista.polizas.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border)', opacity: p.estado === 'cancelada' ? 0.55 : 1, cursor: 'pointer' }}
                  onClick={() => setAbierta(p.id)}>
                  <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>
                    <button type="button" onClick={() => setAbierta(p.id)} style={{ background: 'none', border: 'none', color: 'var(--teal-light)', font: 'inherit', cursor: 'pointer', padding: 0 }}>
                      {p.folio}
                    </button>
                  </td>
                  <td style={tdStyle}>{p.fecha}</td>
                  <td style={tdStyle}>{ETIQUETA_TIPO_POLIZA[p.tipo]}</td>
                  <td style={tdStyle}>
                    {p.concepto}
                    {p.estado === 'cancelada' && <span style={{ color: 'var(--danger)', marginLeft: 6 }}>(cancelada)</span>}
                    {Number(p.diferencia) !== 0 && <span style={{ color: 'var(--warning)', marginLeft: 6 }} title="Diferencia contra el total del CFDI">Δ {p.diferencia}</span>}
                  </td>
                  <td style={tdMonoStyle}>{dinero(p.total_cargos)}</td>
                  <td style={tdMonoStyle}>{dinero(p.total_abonos)}</td>
                  <td style={tdStyle}>{p.origen === 'automatica' ? `CFDI ${p.tipo_cfdi}` : 'Manual'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <nav aria-label="Paginación" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-sm) var(--space-md)', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
            <span>{lista.total} póliza{lista.total === 1 ? '' : 's'} · página {pagina} de {paginas}</span>
            <span style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn-secondary" disabled={pagina <= 1} onClick={() => setFiltros({ ...filtros, pagina: pagina - 1 })}>Anterior</button>
              <button type="button" className="btn-secondary" disabled={pagina >= paginas} onClick={() => setFiltros({ ...filtros, pagina: pagina + 1 })}>Siguiente</button>
            </span>
          </nav>
        </div>
      )}
    </div>
  );
}
