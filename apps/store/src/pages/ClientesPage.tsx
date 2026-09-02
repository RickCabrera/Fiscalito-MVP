/**
 * Cartera de clientes del despacho (E-02).
 *
 * Reemplaza el stub de E-01. La lista sale de `GET /despacho/clientes`: ni los
 * empleados ni la prima de riesgo se escriben en TypeScript.
 *
 * DEMO — se borra en F2.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ModalCliente from '../components/cartera/ModalCliente';
import { useCartera } from '../context/carteraStore';
import type { ClienteCartera } from '../services/carteraApi';
import { Building2, ChevronRight, Loader, Plus, RefreshCw, Users } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import { etiquetaOrigen, primaComoPorcentaje } from '../services/despachoApi';
import ErrorAlert from '../components/common/ErrorAlert';

function TarjetaCliente({
  cliente, activo, onAbrir,
}: { cliente: ClienteCartera; activo: boolean; onAbrir: () => void }) {
  return (
    <button
      onClick={onAbrir}
      className="card"
      style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-md)', width: '100%',
        padding: 'var(--space-md) var(--space-lg)', textAlign: 'left', cursor: 'pointer',
        border: `1.5px solid ${activo ? 'var(--accent-active)' : 'var(--border)'}`,
        background: activo ? 'var(--accent-active-bg)' : 'var(--bg-card)',
        color: 'var(--text-primary)',
      }}
    >
      <div
        style={{
          width: 44, height: 44, borderRadius: 'var(--radius-sm)', flexShrink: 0,
          background: 'var(--accent-gradient)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <Building2 size={20} color="var(--text-on-accent)" />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>{cliente.nombre}</span>
          {activo && (
            <span
              style={{
                fontSize: '0.7rem', fontWeight: 600, letterSpacing: 0.3,
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                background: 'var(--accent-active)', color: 'var(--text-on-accent)',
              }}
            >
              ACTIVO
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          {cliente.giro} · {etiquetaOrigen(cliente.origen)}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-lg)', flexShrink: 0 }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
            <Users size={14} color="var(--text-muted)" />
            <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
              {cliente.empleados.length}
            </span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>empleados</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
            {primaComoPorcentaje(cliente.prima_riesgo)}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>prima de RT</div>
        </div>
        <ChevronRight size={18} color="var(--text-muted)" />
      </div>
    </button>
  );
}

export default function ClientesPage() {
  // El cliente ACTIVO sigue saliendo del contexto de E-02 (es lo que lee el
  // selector del header). La LISTA sale de la cartera, que es donde el alta
  // escribe: pintarla desde el backend hacía que un cliente recién capturado
  // no apareciera nunca, sin error y sin mensaje.
  const { clienteId, error, setClienteId, recargar } = useClienteActivo();
  const cartera = useCartera();
  const clientes = cartera.clientes;
  const loading = cartera.loading;
  const [modalAbierto, setModalAbierto] = useState(false);
  const [errorSembrar, setErrorSembrar] = useState<string | null>(null);
  const [editando, setEditando] = useState<Omit<ClienteCartera, 'empleados'> | null>(null);
  const navigate = useNavigate();

  const abrir = (id: string) => {
    setClienteId(id);
    navigate(`/app/clientes/${id}`);
  };

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Clientes</h1>
        <p>La cartera del despacho. Elige uno para ver su plantilla y calcular su nómina.</p>
      </div>

      {/* G-03: el origen se DICE, no se esconde. Con el catálogo del backend en
          pantalla no hay escritura, y el contador tiene que saber por qué. */}
      {cartera.motivoFallback && (
        <div
          style={{
            marginBottom: 'var(--space-md)', background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)', fontSize: '0.86rem',
          }}
        >
          <div>
            {cartera.motivoFallback} Las altas y ediciones están deshabilitadas hasta que tu
            cartera viva en tu cuenta.
          </div>
          <button
            className="btn-primary"
            style={{ marginTop: 'var(--space-sm)' }}
            onClick={() => {
              cartera.sembrar().catch((e: unknown) =>
                setErrorSembrar(e instanceof Error ? e.message : 'No se pudo guardar la cartera'),
              );
            }}
          >
            Guardar esta cartera en mi cuenta
          </button>
          {errorSembrar && (
            <div role="alert" style={{ marginTop: 'var(--space-xs)', color: 'var(--danger)' }}>
              {errorSembrar}
            </div>
          )}
        </div>
      )}

      {!cartera.soloLectura && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          <button
            className="btn-primary"
            onClick={() => { setEditando(null); setModalAbierto(true); }}
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}
          >
            <Plus size={16} /> Nuevo cliente
          </button>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start' }}>
          <ErrorAlert message={error} />
          <button
            onClick={recargar}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', background: 'transparent',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)', fontSize: '0.83rem', cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', padding: '32px 0' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando la cartera...
        </div>
      )}

      {!loading && !error && clientes.length === 0 && (
        <div className="card" style={{ padding: 'var(--space-2xl) var(--space-lg)', textAlign: 'center' }}>
          <div style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 'var(--space-xs)' }}>
            La cartera está vacía
          </div>
          <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)' }}>
            El servicio respondió sin clientes. Revisa que la API esté corriendo.
          </p>
        </div>
      )}

      <div className="animate-in" style={{ animationDelay: '0.1s', display: 'grid', gap: 'var(--space-sm)' }}>
        {clientes.map((c) => (
          <TarjetaCliente
            key={c.id}
            cliente={c}
            activo={c.id === clienteId}
            onAbrir={() => abrir(c.id)}
          />
        ))}
      </div>

      {modalAbierto && (
        <ModalCliente
          cliente={editando}
          idsExistentes={cartera.clientes.map((c) => c.id)}
          onGuardar={cartera.guardarCliente}
          onCerrar={() => setModalAbierto(false)}
        />
      )}
    </div>
  );
}
