/**
 * Planes y suscripción del despacho — `/app/planes`. (T8, P5-08)
 *
 * DESDE P5-08 EL PLAN ES DEL BACKEND
 * ----------------------------------
 * El catálogo (límites, módulos, precio), el plan vigente, el estado de la suscripción y
 * los bloqueos salen de `GET /suscripcion`; suscribirse, cambiar y cancelar van por el
 * adaptador de pagos del backend. Esta pantalla no decide ningún límite: pinta lo que el
 * backend hace cumplir, con el motivo que el backend escribe.
 *
 * `users/{uid}.plan` (Firestore) queda como ESPEJO de lo que dice el backend, sólo para los
 * chips de uso de `ClientesPage`, `SelectorCliente` y `TarjetaPlan` del Perfil: se
 * actualiza aquí al cargar y tras cada cambio. Si el espejo se atrasa, el backend sigue
 * bloqueando con su propio dato.
 *
 * Bajar a un plan más chico NO borra nada: la tarjeta avisa antes qué se bloquearía.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader } from 'lucide-react';
import { useProfile } from '../context/ProfileContext';
import EstadoSuscripcionCard from '../components/planes/EstadoSuscripcionCard';
import HistorialPagos from '../components/planes/HistorialPagos';
import TarjetaPlanCatalogo, { type AccionPlan } from '../components/planes/TarjetaPlanCatalogo';
import { planPorId } from '../services/planes';
import {
  cambiarPlan, cancelarSuscripcion, fechaCorta, obtenerSuscripcion, suscribirse,
  type PlanCatalogo, type ResumenSuscripcion,
} from '../services/suscripcionApi';

export default function PlanesPage() {
  const { profile, setProfile } = useProfile();
  const [resumen, setResumen] = useState<ResumenSuscripcion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [urlPago, setUrlPago] = useState<string | null>(null);
  const [confirmarCancelar, setConfirmarCancelar] = useState(false);

  const cargar = useCallback(() => obtenerSuscripcion()
    .then((r) => { setResumen(r); setError(null); })
    .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar tu suscripción.'))
    .finally(() => setCargando(false)), []);

  useEffect(() => { void cargar(); }, [cargar]);

  // Espejo para los chips de uso; si falla, el backend sigue siendo el que manda.
  const planBackend = resumen?.suscripcion.plan;
  useEffect(() => {
    const espejo = planBackend ? planPorId(planBackend) : undefined;
    if (espejo && profile.plan !== espejo.id) {
      setProfile({ plan: espejo.id }).catch(() => undefined);
    }
  }, [planBackend, profile.plan, setProfile]);

  const accionDe = (p: PlanCatalogo): AccionPlan => {
    if (!resumen?.puede_gestionar) return null;
    const s = resumen.suscripcion;
    const conCobroVivo = s.con_cobro && (s.estado === 'activa' || s.estado === 'morosa');
    if (!conCobroVivo) return 'suscribirse';
    return p.id === s.plan ? null : 'cambiar';
  };

  const ejecutar = async (clave: string, fn: () => Promise<string | null>) => {
    setOcupado(clave);
    setError(null);
    setAviso(null);
    try {
      setAviso(await fn());
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar la operación.');
    } finally {
      setOcupado(null);
    }
  };

  const elegir = (p: PlanCatalogo) => void ejecutar(p.id, async () => {
    if (accionDe(p) === 'suscribirse') {
      const r = await suscribirse(p.id);
      setUrlPago(r.url_pago);
      return r.url_pago
        ? `Completa el pago para activar el plan ${p.nombre}.`
        : `Te suscribiste al plan ${p.nombre}.`;
    }
    await cambiarPlan(p.id);
    return `Cambiaste al plan ${p.nombre}.`;
  });

  const cancelar = () => void ejecutar('cancelar', async () => {
    const r = await cancelarSuscripcion();
    setConfirmarCancelar(false);
    return `Cancelaste tu suscripción. Conservas el acceso hasta el ${fechaCorta(r.acceso_hasta)}.`;
  });

  const s = resumen?.suscripcion;
  const puedeCancelar = Boolean(resumen?.puede_gestionar && s && s.estado !== 'cancelada'
    && s.estado !== 'vencida');

  return (
    <div className="page-container">
      <Link to="/app/profile" style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 'var(--space-md)',
      }}>
        <ArrowLeft size={16} /> Perfil
      </Link>

      <div className="page-header animate-in">
        <h1>Planes y suscripción</h1>
        <p>Tu plan decide cuántos clientes y usuarios caben y qué módulos tienes.</p>
      </div>

      {cargando && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" color="var(--accent-active)" />
          Cargando tu suscripción…
        </div>
      )}
      {error && <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.86rem' }}>{error}</p>}
      {aviso && !error && (
        <p role="status" style={{ color: 'var(--success)', fontSize: '0.86rem' }}>
          {aviso}{' '}
          {urlPago && <a href={urlPago} target="_blank" rel="noreferrer">Ir a pagar</a>}
        </p>
      )}

      {resumen && (
        <>
          <EstadoSuscripcionCard
            resumen={resumen}
            puedeCancelar={puedeCancelar && !confirmarCancelar}
            cancelando={ocupado === 'cancelar'}
            onCancelar={() => setConfirmarCancelar(true)}
          />
          {confirmarCancelar && s && (
            <div className="card" role="dialog" aria-label="Confirmar cancelación" style={{ marginTop: 'var(--space-sm)' }}>
              <p style={{ margin: 0, fontSize: '0.88rem' }}>
                Conservas el acceso completo hasta el {fechaCorta(s.fin_periodo)}. Después la
                cuenta queda en solo lectura: no se borra nada.
              </p>
              <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
                <button className="btn-primary" onClick={cancelar} disabled={ocupado === 'cancelar'}>
                  Sí, cancelar
                </button>
                <button className="btn-secondary" onClick={() => setConfirmarCancelar(false)}>
                  No, conservarla
                </button>
              </div>
            </div>
          )}
          {!resumen.puede_gestionar && (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Sólo el dueño del despacho puede cambiar el plan o la suscripción.
            </p>
          )}

          <div className="animate-in" style={{
            display: 'grid', gap: 'var(--space-md)', marginTop: 'var(--space-md)',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          }}>
            {resumen.planes.map((p) => (
              <TarjetaPlanCatalogo
                key={p.id}
                plan={p}
                actual={p.id === resumen.suscripcion.plan}
                accion={accionDe(p)}
                ocupado={ocupado === p.id}
                onElegir={() => elegir(p)}
              />
            ))}
          </div>

          <h2 style={{ fontSize: '1.05rem', marginTop: 'var(--space-lg)' }}>Pagos</h2>
          <HistorialPagos pagos={resumen.pagos} />
        </>
      )}
    </div>
  );
}
