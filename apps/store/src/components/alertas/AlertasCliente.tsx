/** Sección de alertas fiscales abiertas en la ficha del cliente (P3-09). */

import { Bell } from 'lucide-react';
import ListaAlertas from './ListaAlertas';

export default function AlertasCliente({ clave }: { clave: string }) {
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <h2 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Bell size={16} /> Alertas fiscales
      </h2>
      <ListaAlertas filtros={{ cliente: clave }} sinCliente />
    </section>
  );
}
