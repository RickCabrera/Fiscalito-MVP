/**
 * Filtros de la tabla de la bóveda (P0-03): periodo, tipo, emitido/recibido y
 * estatus SAT. Controlado: el estado vive en la página, que es quien pide.
 */

import type { FiltrosBoveda as Filtros } from '../../services/bovedaApi';
import { labelStyle } from '../../utils/styles';

interface Props {
  valor: Filtros;
  onCambio: (f: Filtros) => void;
}

const TIPOS: [string, string][] = [
  ['', 'Todos'], ['I', 'Ingreso'], ['E', 'Egreso'], ['P', 'Pago'], ['N', 'Nómina'], ['T', 'Traslado'],
];

export default function FiltrosBoveda({ valor, onCambio }: Props) {
  const cambiar = (parcial: Partial<Filtros>) => onCambio({ ...valor, ...parcial, pagina: 1 });
  const campo: React.CSSProperties = { minWidth: 140 };

  return (
    <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label style={campo}>
        <span style={labelStyle}>Desde</span>
        <input className="input-field" type="date" value={valor.desde ?? ''}
          onChange={(e) => cambiar({ desde: e.target.value })} />
      </label>
      <label style={campo}>
        <span style={labelStyle}>Hasta</span>
        <input className="input-field" type="date" value={valor.hasta ?? ''}
          onChange={(e) => cambiar({ hasta: e.target.value })} />
      </label>
      <label style={campo}>
        <span style={labelStyle}>Tipo</span>
        <select className="input-field" value={valor.tipo ?? ''}
          onChange={(e) => cambiar({ tipo: e.target.value as Filtros['tipo'] })}>
          {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </label>
      <label style={campo}>
        <span style={labelStyle}>Dirección</span>
        <select className="input-field" value={valor.direccion ?? ''}
          onChange={(e) => cambiar({ direccion: e.target.value as Filtros['direccion'] })}>
          <option value="">Emitidos y recibidos</option>
          <option value="emitido">Emitidos</option>
          <option value="recibido">Recibidos</option>
        </select>
      </label>
      <label style={campo}>
        <span style={labelStyle}>Estatus SAT</span>
        <select className="input-field" value={valor.estatus ?? ''}
          onChange={(e) => cambiar({ estatus: e.target.value as Filtros['estatus'] })}>
          <option value="">Todos</option>
          <option value="vigente">Vigente</option>
          <option value="cancelado">Cancelado</option>
          <option value="desconocido">Sin verificar</option>
        </select>
      </label>
    </div>
  );
}
