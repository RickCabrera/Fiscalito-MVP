/** Historial filters — category and year selectors */

import { type HistorialCategoria } from '../../services/declaracionesHistory';

const YEARS = [2026, 2025, 2024, 2023];

const CATEGORIAS: { value: HistorialCategoria | ''; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'predeclaracion', label: 'Pre-declaraciones' },
  { value: 'diot', label: 'DIOT' },
  { value: 'retenciones', label: 'Retenciones' },
  { value: 'multiperiodo', label: 'Multi-periodo' },
  { value: 'estado_cuenta', label: 'Estado de cuenta' },
  { value: 'deducciones', label: 'Deducciones' },
];

interface HistorialFiltersProps {
  filtroCat: HistorialCategoria | '';
  filtroAnio: string;
  onCatChange: (cat: HistorialCategoria | '') => void;
  onAnioChange: (anio: string) => void;
}

export default function HistorialFilters({ filtroCat, filtroAnio, onCatChange, onAnioChange }: HistorialFiltersProps) {
  return (
    <div className="animate-in" style={{ animationDelay: '0.1s', display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
      <select className="input-field" value={filtroCat} onChange={(e) => onCatChange(e.target.value as HistorialCategoria | '')} style={{ width: 180, cursor: 'pointer' }}>
        {CATEGORIAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
      <select className="input-field" value={filtroAnio} onChange={(e) => onAnioChange(e.target.value)} style={{ width: 140, cursor: 'pointer' }}>
        <option value="">Todos los años</option>
        {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  );
}
