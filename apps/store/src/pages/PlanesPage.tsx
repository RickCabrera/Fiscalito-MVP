/**
 * Planes de la cuenta — `/app/planes`. (T8)
 *
 * Tres tarjetas y un botón que guarda `users/{uid}.plan`. **No cobra nada**: no
 * hay pasarela, ni suscripción, ni precio publicado. Lo que el botón cambia es
 * el límite de clientes que `ClientesPage` hace cumplir, y eso es todo lo que
 * la pantalla promete. El porqué de cada número vive en `services/planes.ts`.
 *
 * ELEGIR UN PLAN MÁS CHICO QUE LA CARTERA NO BORRA NADA
 * ----------------------------------------------------
 * Un despacho con 30 clientes que se pasa al plan Contador (25) **conserva sus
 * 30**: lo único que pierde es poder dar de alta el 31. Borrar clientes para
 * que quepan sería destruir datos del usuario por un cambio de etiqueta
 * comercial, así que el plan chico se acepta y la pantalla dice, antes de
 * guardar, que va a quedar por encima del tope.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Check, Loader } from 'lucide-react';
import { useProfile } from '../context/ProfileContext';
import { useCartera } from '../context/carteraStore';
import { modoEmpresaUnica } from '../services/modoEmpresa';
import { PLANES, planDelPerfil, usoDeClientes, type IdPlan, type Plan } from '../services/planes';

function TarjetaDePlan({
  plan, actual, clientes, guardando, onElegir,
}: {
  plan: Plan;
  actual: boolean;
  clientes: number;
  guardando: boolean;
  onElegir: () => void;
}) {
  // Se avisa ANTES de guardar, no después: el usuario decide con el dato
  // enfrente en vez de descubrirlo cuando el alta deje de funcionar.
  const quedaCorto = clientes > plan.maxClientes;

  return (
    <div
      className="card"
      style={{
        display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
        border: `1.5px solid ${actual ? 'var(--accent-active)' : 'var(--border)'}`,
        background: actual ? 'var(--accent-active-bg)' : 'var(--bg-card)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{plan.nombre}</h3>
        {actual && (
          <span
            style={{
              fontSize: '0.7rem', fontWeight: 600, letterSpacing: 0.3,
              padding: '2px 8px', borderRadius: 'var(--radius-full)',
              background: 'var(--accent-active)', color: 'var(--text-on-accent)',
            }}
          >
            TU PLAN
          </span>
        )}
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
        {plan.descripcion}
      </p>

      <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
        {plan.precio}
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
        {plan.incluye.map((linea) => (
          <li key={linea} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: '0.85rem' }}>
            <Check size={14} color="var(--teal-light)" style={{ flexShrink: 0, marginTop: 3 }} />
            <span style={{ color: 'var(--text-secondary)' }}>{linea}</span>
          </li>
        ))}
      </ul>

      {quedaCorto && (
        <p role="status" style={{ fontSize: '0.78rem', color: 'var(--warning)', margin: 0 }}>
          Ya llevas {clientes} clientes. Con este plan los conservas todos, pero no vas a
          poder dar de alta otro.
        </p>
      )}

      <button
        className={actual ? 'btn-secondary' : 'btn-primary'}
        onClick={onElegir}
        disabled={actual || guardando}
        style={{ marginTop: 'auto' }}
      >
        {actual ? 'Plan actual' : guardando ? 'Guardando…' : 'Seleccionar'}
      </button>
    </div>
  );
}

export default function PlanesPage() {
  const { profile, setProfile, loading } = useProfile();
  const cartera = useCartera();
  const [guardando, setGuardando] = useState<IdPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);

  const plan = planDelPerfil(profile.plan);
  const uso = usoDeClientes(plan, cartera.clientes.length);
  const conCartera = !modoEmpresaUnica();

  const elegir = async (id: IdPlan) => {
    setGuardando(id);
    setError(null);
    setGuardado(false);
    try {
      await setProfile({ plan: id });
      setGuardado(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el plan.');
    } finally {
      setGuardando(null);
    }
  };

  return (
    <div className="page-container">
      <Link
        to="/app/profile"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 'var(--space-md)',
        }}
      >
        <ArrowLeft size={16} /> Perfil
      </Link>

      <div className="page-header animate-in">
        <h1>Planes</h1>
        {/* En modo empresa única no hay cartera, y "1 / 1 clientes" sería el
            mismo lenguaje de despacho que `TarjetaPlan` evita. Lo señaló el
            revisor de T8: esta pantalla SÍ es alcanzable en ese modo, desde la
            tarjeta del Perfil. */}
        <p>
          {conCartera ? (
            <>
              Tu plan decide cuántos clientes puedes llevar. Hoy llevas{' '}
              <strong>{uso.texto}</strong>.
            </>
          ) : (
            'Esta instalación lleva la nómina de una sola empresa. El plan describe su alcance.'
          )}
        </p>
      </div>

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" color="var(--accent-active)" />
          Cargando tu plan…
        </div>
      )}

      {error && (
        <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.86rem' }}>
          {error}
        </p>
      )}

      {guardado && !error && (
        <p role="status" style={{ color: 'var(--success)', fontSize: '0.86rem' }}>
          Plan actualizado.
        </p>
      )}

      <div
        className="animate-in"
        style={{
          display: 'grid', gap: 'var(--space-md)', marginTop: 'var(--space-md)',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        }}
      >
        {PLANES.map((p) => (
          <TarjetaDePlan
            key={p.id}
            plan={p}
            actual={p.id === plan.id}
            clientes={conCartera ? cartera.clientes.length : 0}
            guardando={guardando === p.id}
            onElegir={() => void elegir(p.id)}
          />
        ))}
      </div>

      {/* Que no haya cobro se dice en la pantalla, no sólo en el código: quien
          la ve en una demo tiene que saber qué acaba de pasar al dar clic. */}
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 'var(--space-lg)' }}>
        Seleccionar un plan no genera ningún cobro: ajusta el límite de clientes de tu
        cuenta. Los precios se acuerdan por separado.
      </p>
    </div>
  );
}
