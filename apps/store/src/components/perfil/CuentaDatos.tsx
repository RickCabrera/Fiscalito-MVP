/**
 * Datos de la cuenta (P6-01): exportar todo lo del despacho y borrar la cuenta.
 *
 * Sólo el dueño puede (el backend responde 403 a los demás y aquí se pinta el motivo). La
 * exportación corre en segundo plano: se pide, se consulta cada pocos segundos y, ya lista,
 * aparece el enlace firmado de descarga. El borrado pide escribir la frase exacta.
 */

import { useEffect, useRef, useState } from 'react';
import { Download, Trash2 } from 'lucide-react';
import {
  FRASE_BORRADO, borrarDespacho, estadoExportacion, solicitarExportacion,
  type Exportacion,
} from '../../services/cuentaDespachoApi';

const SONDEO_MS = 3000;

interface Props {
  /** Qué hacer tras borrar (cerrar sesión). */
  alBorrar?: () => void;
  sondeoMs?: number;
}

function mensaje(e: unknown): string {
  return e instanceof Error ? e.message : 'Ocurrió un error.';
}

export default function CuentaDatos({ alBorrar, sondeoMs = SONDEO_MS }: Props) {
  const [exp, setExp] = useState<Exportacion | null>(null);
  const [exportando, setExportando] = useState(false);
  const [errorExp, setErrorExp] = useState('');
  const [frase, setFrase] = useState('');
  const [borrando, setBorrando] = useState(false);
  const [errorBorrar, setErrorBorrar] = useState('');
  const [borrado, setBorrado] = useState(false);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (temporizador.current) clearTimeout(temporizador.current);
  }, []);

  const sondear = (id: number) => {
    temporizador.current = setTimeout(async () => {
      try {
        const actual = await estadoExportacion(id);
        setExp(actual);
        if (actual.estado === 'pendiente' || actual.estado === 'corriendo') sondear(id);
        else setExportando(false);
      } catch (e) {
        setErrorExp(mensaje(e));
        setExportando(false);
      }
    }, sondeoMs);
  };

  const exportar = async () => {
    setErrorExp('');
    setExportando(true);
    try {
      const t = await solicitarExportacion();
      setExp(t);
      if (t.estado === 'hecho' || t.estado === 'fallido') setExportando(false);
      else sondear(t.id);
    } catch (e) {
      setErrorExp(mensaje(e));
      setExportando(false);
    }
  };

  const borrar = async () => {
    setErrorBorrar('');
    setBorrando(true);
    try {
      await borrarDespacho(frase.trim());
      setBorrado(true);
      alBorrar?.();
    } catch (e) {
      setErrorBorrar(mensaje(e));
    } finally {
      setBorrando(false);
    }
  };

  return (
    <div className="card animate-in" style={{ marginTop: 24 }}>
      <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>Datos de la cuenta</h3>
      <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
        Sólo el dueño del despacho. La exportación es un ZIP con un JSON por tabla y los XML y
        PDF guardados; el enlace vale 7 días.
      </p>

      <button className="btn-secondary" onClick={exportar} disabled={exportando}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <Download size={16} /> {exportando ? 'Preparando exportación…' : 'Exportar mis datos'}
      </button>
      {exp?.estado === 'hecho' && exp.url && (
        <p style={{ marginTop: 8, fontSize: '0.85rem' }}>
          Lista. <a href={exp.url} rel="noopener">Descargar ZIP</a>
        </p>
      )}
      {exp?.estado === 'fallido' && (
        <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: 8 }}>
          La exportación falló: {exp.error ?? 'sin detalle'}
        </p>
      )}
      {errorExp && (
        <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: 8 }}>{errorExp}</p>
      )}

      <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 16 }}>
        <p style={{ fontSize: '0.85rem', color: 'var(--danger)', fontWeight: 600, marginBottom: 8 }}>
          Borrar la cuenta del despacho
        </p>
        <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
          Se borran para siempre todos los clientes, CFDI, pólizas, nóminas, credenciales, la
          bitácora y los respaldos. Exporta antes si quieres conservarlos. Para confirmar
          escribe <strong>{FRASE_BORRADO}</strong>.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input className="input-field" aria-label="Frase de confirmación" value={frase}
            onChange={(e) => setFrase(e.target.value)} placeholder={FRASE_BORRADO}
            style={{ maxWidth: 280 }} />
          <button className="btn-secondary" onClick={borrar}
            disabled={borrando || frase.trim() !== FRASE_BORRADO || borrado}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--danger)' }}>
            <Trash2 size={16} /> {borrando ? 'Borrando…' : 'Borrar todo'}
          </button>
        </div>
        {borrado && (
          <p style={{ color: 'var(--success)', fontSize: '0.85rem', marginTop: 8 }}>
            La cuenta del despacho se borró.
          </p>
        )}
        {errorBorrar && (
          <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: 8 }}>{errorBorrar}</p>
        )}
      </div>
    </div>
  );
}
