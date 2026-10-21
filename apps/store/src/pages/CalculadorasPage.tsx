/**
 * Calculadoras fiscales del despacho (P3-08): herramientas sueltas, sin cliente.
 *
 * No va en `RUTAS_CON_CLIENTE`: no lee el cliente activo, así que un selector
 * encima afirmaría un alcance que la pantalla no tiene. Cada tarjeta llama al
 * mismo motor que el módulo que la respalda (ver `apps/api/app/routes/calculadoras.py`).
 */

import { Calculator } from 'lucide-react';
import TarjetaCalculadora from '../components/calculadoras/TarjetaCalculadora';
import { CALCULADORAS } from '../components/calculadoras/definiciones';

export default function CalculadorasPage() {
  return (
    <div className="page-container">
      <div className="animate-in" style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Calculator size={28} color="var(--teal-light)" />
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Calculadoras fiscales</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
            El mismo motor que usan los módulos, para consultas rápidas del despacho.
          </p>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
        {CALCULADORAS.map((def) => <TarjetaCalculadora key={def.id} def={def} />)}
      </div>
    </div>
  );
}
