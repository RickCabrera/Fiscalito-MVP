/**
 * "Verificar estatus" de la bóveda (P1-03).
 *
 * Encola en el servidor la consulta al SAT de los CFDI del periodo filtrado (o del mes en
 * curso si no hay filtro) y muestra el proceso con `EstadoTrabajos`. `EstadoTrabajos` no
 * avisa cuando termina, así que "Actualizar tabla" vuelve a pedir la página para ver los
 * cancelados.
 */

import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import ErrorAlert from '../common/ErrorAlert';
import EstadoTrabajos from '../common/EstadoTrabajos';
import { verificarEstatus } from '../../services/satVerificacionApi';
import { periodoAVerificar } from './periodo';

interface Props {
  clave: string;
  desde?: string;
  hasta?: string;
  onActualizar: () => void;
}

export default function VerificarEstatus({ clave, desde, hasta, onActualizar }: Props) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [recarga, setRecarga] = useState(0);
  const periodo = periodoAVerificar(desde, hasta);

  const verificar = async () => {
    setEnviando(true);
    setError(null);
    setAviso(null);
    try {
      const r = await verificarEstatus(clave, periodo.desde, periodo.hasta);
      setAviso(`Se consultarán ${r.comprobantes} comprobante${r.comprobantes === 1 ? '' : 's'} ante el SAT.`);
      setRecarga((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo pedir la verificación.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="card" style={{ padding: 'var(--space-md)', display: 'grid', gap: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <button type="button" className="btn-secondary" onClick={() => void verificar()} disabled={enviando}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ShieldCheck size={15} /> {enviando ? 'Pidiendo…' : 'Verificar estatus'}
        </button>
        <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
          Consulta al SAT si los CFDI del {periodo.desde} al {periodo.hasta} siguen vigentes. Los
          cancelados se marcan y dejan de contar en los cálculos.
        </span>
      </div>
      {aviso && <div role="status" style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>{aviso}</div>}
      {error && <ErrorAlert message={error} />}
      {recarga > 0 && (
        <>
          <EstadoTrabajos cliente={clave} tipo="sat.verificar_estatus" limite={3} recarga={recarga} />
          <button type="button" className="btn-secondary" style={{ justifySelf: 'start' }} onClick={onActualizar}>
            Actualizar tabla
          </button>
        </>
      )}
    </div>
  );
}
