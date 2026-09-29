/**
 * RFC, código postal y entidad en la ficha del cliente, con "Editar datos" (C-01).
 *
 * Vive aparte porque `ClienteDetallePage` ya pasaba del tope de 300 líneas.
 *
 * Los datos salen de la CARTERA, no de la ficha del backend: es lo que el alta y
 * la edición escriben, y lo que se relee al recargar. Un cliente que sólo existe
 * en el catálogo de demostración del backend no está en la cartera y por eso no
 * se puede editar aquí — no hay dónde guardarlo.
 */

import { useState } from 'react';
import { Pencil } from 'lucide-react';
import { useCartera } from '../../context/carteraStore';
import { sinEmpleados, type ClienteCartera } from '../../services/carteraApi';
import ModalCliente from './ModalCliente';
import { ENTIDADES_FEDERATIVAS } from './datosFiscalesCliente';

const SIN_CAPTURAR = 'Sin capturar';

function nombreEntidad(clave: string | undefined): string {
  if (!clave) return SIN_CAPTURAR;
  const e = ENTIDADES_FEDERATIVAS.find((x) => x.clave === clave);
  return e ? `${e.nombre} (${e.clave})` : clave;
}

function Renglon({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  const falta = valor === SIN_CAPTURAR;
  return (
    <div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 2 }}>{etiqueta}</div>
      <div
        style={{
          fontSize: '0.95rem', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
          color: falta ? 'var(--text-muted)' : 'var(--text-primary)',
        }}
      >
        {valor}
      </div>
    </div>
  );
}

export default function DatosFiscalesFicha({ cliente }: { cliente: ClienteCartera }) {
  const cartera = useCartera();
  const [editando, setEditando] = useState(false);

  return (
    <div
      className="card animate-in"
      style={{
        animationDelay: '0.07s', marginBottom: 'var(--space-lg)',
        display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'center',
      }}
    >
      <Renglon etiqueta="RFC" valor={cliente.rfc || SIN_CAPTURAR} />
      <Renglon etiqueta="Código postal" valor={cliente.codigo_postal || SIN_CAPTURAR} />
      <Renglon etiqueta="Entidad federativa" valor={nombreEntidad(cliente.clave_entidad)} />
      {!cartera.soloLectura && (
        <button
          className="btn-secondary"
          onClick={() => setEditando(true)}
          style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6, alignItems: 'center' }}
        >
          <Pencil size={14} /> Editar datos
        </button>
      )}
      {editando && (
        <ModalCliente
          cliente={sinEmpleados(cliente)}
          idsExistentes={cartera.clientes.map((c) => c.id)}
          onGuardar={cartera.guardarCliente}
          onCerrar={() => setEditando(false)}
        />
      )}
    </div>
  );
}
