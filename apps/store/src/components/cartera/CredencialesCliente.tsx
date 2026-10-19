/**
 * "e.firma y sello digital (CSD)" en la ficha del cliente (P0-05).
 *
 * Por cada tipo: si hay una cargada, su RFC, número de certificado y vigencia (con alerta
 * si vence en menos de 30 días o ya venció) y un botón para borrarla o reemplazarla; si no,
 * el formulario para subir .cer, .key y contraseña. El backend valida y guarda cifrado; aquí
 * nunca se vuelve a ver la llave privada.
 */

import { useEffect, useState } from 'react';
import { AlertTriangle, KeyRound, Loader, Trash2 } from 'lucide-react';
import ErrorAlert from '../common/ErrorAlert';
import FormCredencial from './FormCredencial';
import {
  NOMBRE_TIPO, borrarCredencial, listarCredenciales,
  type Credencial, type TipoCredencial,
} from '../../services/credencialesApi';

const TIPOS: TipoCredencial[] = ['efirma', 'csd'];

function fecha(iso: string): string {
  return iso.slice(0, 10);
}

function AvisoVigencia({ c }: { c: Credencial }) {
  if (!c.vencida && !c.por_vencer) return null;
  const texto = c.vencida
    ? `Venció el ${fecha(c.valido_hasta)}. Renuévala en el SAT y sube la nueva.`
    : `Vence en ${c.dias_para_vencer} ${c.dias_para_vencer === 1 ? 'día' : 'días'} (${fecha(c.valido_hasta)}).`;
  return (
    <div
      role="alert"
      style={{
        display: 'flex', alignItems: 'center', gap: 6, marginTop: 'var(--space-xs)',
        padding: '6px 10px', borderRadius: 'var(--radius-xs)', fontSize: '0.8rem',
        background: c.vencida ? 'var(--danger-bg)' : 'var(--warning-bg)',
        border: `1px solid ${c.vencida ? 'var(--danger-border)' : 'var(--warning-border)'}`,
        color: c.vencida ? 'var(--danger)' : 'var(--warning)',
      }}
    >
      <AlertTriangle size={14} /> {texto}
    </div>
  );
}

interface BloqueProps {
  clave: string;
  tipo: TipoCredencial;
  credencial: Credencial | undefined;
  onCambio: (tipo: TipoCredencial, c: Credencial | undefined) => void;
}

function BloqueTipo({ clave, tipo, credencial, onCambio }: BloqueProps) {
  const [reemplazando, setReemplazando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function borrar() {
    if (!credencial) return;
    if (!window.confirm(`¿Borrar la ${NOMBRE_TIPO[tipo]} de este cliente?`)) return;
    setBorrando(true);
    setError(null);
    try {
      await borrarCredencial(clave, credencial.id);
      onCambio(tipo, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo borrar.');
    } finally {
      setBorrando(false);
    }
  }

  const guardada = (c: Credencial) => {
    setReemplazando(false);
    onCambio(tipo, c);
  };

  return (
    <section aria-label={NOMBRE_TIPO[tipo]} style={{ paddingTop: 'var(--space-sm)' }}>
      <h3 style={{ fontSize: '0.92rem', margin: 0 }}>{NOMBRE_TIPO[tipo]}</h3>
      {credencial && !reemplazando ? (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)', marginTop: 6, fontSize: '0.85rem' }}>
            <span>RFC <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{credencial.rfc}</strong></span>
            <span>Certificado <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{credencial.numero_certificado}</strong></span>
            <span>Vigente del {fecha(credencial.valido_desde)} al {fecha(credencial.valido_hasta)}</span>
          </div>
          <AvisoVigencia c={credencial} />
          <div style={{ display: 'flex', gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
            <button className="btn-secondary" onClick={() => setReemplazando(true)}>Reemplazar</button>
            <button
              className="btn-secondary" onClick={borrar} disabled={borrando}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Trash2 size={14} /> {borrando ? 'Borrando…' : 'Borrar'}
            </button>
          </div>
          {error && <ErrorAlert message={error} />}
        </>
      ) : (
        <FormCredencial
          clave={clave}
          tipo={tipo}
          onGuardada={guardada}
          onCancelar={credencial ? () => setReemplazando(false) : undefined}
        />
      )}
    </section>
  );
}

export default function CredencialesCliente({ clave }: { clave: string }) {
  const [porTipo, setPorTipo] = useState<Partial<Record<TipoCredencial, Credencial>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    listarCredenciales(clave)
      .then((lista) => {
        if (cancelado) return;
        const mapa: Partial<Record<TipoCredencial, Credencial>> = {};
        for (const c of lista) mapa[c.tipo] = mapa[c.tipo] ?? c;
        setPorTipo(mapa);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(e instanceof Error ? e.message : 'No se pudieron cargar las credenciales.');
      });
    return () => { cancelado = true; };
  }, [clave]);

  const cambio = (tipo: TipoCredencial, c: Credencial | undefined) =>
    setPorTipo((previo) => ({ ...(previo ?? {}), [tipo]: c }));

  return (
    <div className="card animate-in" style={{ marginBottom: 'var(--space-lg)', padding: 'var(--space-lg)' }}>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', margin: 0 }}>
        <KeyRound size={18} /> e.firma y sello digital (CSD)
      </h2>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '6px 0 0' }}>
        Se guardan cifradas. La e.firma descarga los CFDI del SAT; el CSD timbra nómina y facturas.
      </p>
      {error && <ErrorAlert message={error} />}
      {!error && porTipo === null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 'var(--space-sm)', color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" /> Cargando credenciales…
        </div>
      )}
      {porTipo !== null && TIPOS.map((t) => (
        <BloqueTipo key={t} clave={clave} tipo={t} credencial={porTipo[t]} onCambio={cambio} />
      ))}
    </div>
  );
}
