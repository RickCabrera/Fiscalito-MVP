/**
 * Filtros de "Reportes contables" (P2-05), al estilo de Contadigital: reporte,
 * ejercicio y periodo (o fechas libres), cuentas, nivel, agrupación, moneda con
 * su tipo de cambio, idioma de las etiquetas y comparativo. Componente
 * controlado: el estado vive en `ReportesContables`.
 */

import type { Comparativo, Cuenta, FiltroBalanza, FiltrosReporte, TipoReporte } from '../../services/contabilidadApi';
import { labelStyle } from '../../utils/styles';
import { MESES, REPORTES } from './comun';

interface Props {
  reporte: TipoReporte;
  onReporte: (r: TipoReporte) => void;
  anio: number;
  periodo: number;
  onPeriodo: (anio: number, periodo: number) => void;
  filtros: FiltrosReporte;
  onFiltros: (f: FiltrosReporte) => void;
  cuentas: Cuenta[];
  cuentaId: number | null;
  onCuenta: (id: number | null) => void;
}

export default function FiltrosReportes(p: Props) {
  const f = p.filtros;
  const set = (cambio: Partial<FiltrosReporte>) => p.onFiltros({ ...f, ...cambio });
  const estados = p.reporte === 'estado_resultados' || p.reporte === 'balance_general';
  const anioActual = new Date().getFullYear();
  const anios = Array.from({ length: 8 }, (_, i) => anioActual + 1 - i);

  return (
    <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label><span style={labelStyle}>Reporte</span>
        <select className="input-field" value={p.reporte} onChange={(e) => p.onReporte(e.target.value as TipoReporte)}>
          {REPORTES.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
        </select></label>
      <label><span style={labelStyle}>Ejercicio</span>
        <select className="input-field" value={p.anio} onChange={(e) => p.onPeriodo(Number(e.target.value), p.periodo)}>
          {anios.map((a) => <option key={a} value={a}>{a}</option>)}
        </select></label>
      <label><span style={labelStyle}>Periodo</span>
        <select className="input-field" aria-label="Periodo" value={p.periodo} onChange={(e) => p.onPeriodo(p.anio, Number(e.target.value))}>
          {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          <option value={0}>Ejercicio completo</option>
          <option value={-1}>Fechas libres</option>
        </select></label>
      <label><span style={labelStyle}>Desde</span>
        <input className="input-field" type="date" value={f.desde} disabled={p.periodo !== -1}
          onChange={(e) => set({ desde: e.target.value })} /></label>
      <label><span style={labelStyle}>Hasta</span>
        <input className="input-field" type="date" value={f.hasta} disabled={p.periodo !== -1}
          onChange={(e) => set({ hasta: e.target.value })} /></label>
      {p.reporte === 'auxiliar' && (
        <label><span style={labelStyle}>Cuenta</span>
          <select className="input-field" aria-label="Cuenta del auxiliar" value={p.cuentaId ?? ''}
            onChange={(e) => p.onCuenta(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Elige una cuenta</option>
            {p.cuentas.map((c) => <option key={c.id} value={c.id}>{c.numero} {c.nombre}</option>)}
          </select></label>
      )}
      {(estados || p.reporte === 'balanza') && (
        <>
          <label><span style={labelStyle}>Cuentas</span>
            <select className="input-field" value={f.solo} onChange={(e) => set({ solo: e.target.value as FiltroBalanza })}>
              <option value="con_saldo_o_movimiento">Con saldo o movimiento</option>
              <option value="con_movimiento">Sólo con movimiento</option>
              <option value="todas">Todas</option>
            </select></label>
          <label><span style={labelStyle}>Nivel</span>
            <select className="input-field" value={f.nivel ?? ''} onChange={(e) => set({ nivel: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Todos</option><option value="1">1 (mayor)</option><option value="2">2</option><option value="3">3</option>
            </select></label>
        </>
      )}
      {estados && (
        <>
          <label><span style={labelStyle}>Agrupar por</span>
            <select className="input-field" value={f.agrupar} onChange={(e) => set({ agrupar: e.target.value as 'cuenta' | 'agrupador' })}>
              <option value="cuenta">Cuenta del catálogo</option>
              <option value="agrupador">Código agrupador SAT</option>
            </select></label>
          <label><span style={labelStyle}>Comparar con</span>
            <select className="input-field" value={f.comparar} onChange={(e) => set({ comparar: e.target.value as Comparativo })}>
              <option value="ninguno">Sin comparativo</option>
              <option value="periodo_anterior">Periodo anterior</option>
              <option value="anio_anterior">Mismo periodo del año anterior</option>
            </select></label>
          <label><span style={labelStyle}>Moneda</span>
            <select className="input-field" value={f.moneda} onChange={(e) => set({ moneda: e.target.value })}>
              <option value="MXN">MXN</option><option value="USD">USD</option><option value="EUR">EUR</option>
            </select></label>
          {f.moneda !== 'MXN' && (
            <label><span style={labelStyle}>Tipo de cambio (MXN por 1 {f.moneda})</span>
              <input className="input-field" inputMode="decimal" aria-label="Tipo de cambio" value={f.tipo_cambio ?? ''}
                placeholder="p. ej. FIX del DOF" onChange={(e) => set({ tipo_cambio: e.target.value })} /></label>
          )}
          <label><span style={labelStyle}>Idioma</span>
            <select className="input-field" value={f.idioma} onChange={(e) => set({ idioma: e.target.value as 'es' | 'en' })}>
              <option value="es">Español</option><option value="en">English</option>
            </select></label>
        </>
      )}
      {p.reporte !== 'polizas' && (
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <input type="checkbox" checked={!!f.incluir_cierre} onChange={(e) => set({ incluir_cierre: e.target.checked })} />
          Incluir pólizas de cierre
        </label>
      )}
    </div>
  );
}
