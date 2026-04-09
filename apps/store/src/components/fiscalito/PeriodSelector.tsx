/** Selector reutilizable de periodo (año + mes) */

import { labelStyle } from '../../utils/styles';

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];
const YEARS = [2026, 2025, 2024, 2023];

interface Props {
  year: number;
  month: number;
  onYearChange: (y: number) => void;
  onMonthChange: (m: number) => void;
}

export default function PeriodSelector({ year, month, onYearChange, onMonthChange }: Props) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div>
        <label style={labelStyle}>Año</label>
        <select className="input-field" value={year} onChange={(e) => onYearChange(Number(e.target.value))}
          style={{ width: 120, cursor: 'pointer' }}>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
      <div>
        <label style={labelStyle}>Mes</label>
        <select className="input-field" value={month} onChange={(e) => onMonthChange(Number(e.target.value))}
          style={{ width: 160, cursor: 'pointer' }}>
          {MESES.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
      </div>
    </div>
  );
}
