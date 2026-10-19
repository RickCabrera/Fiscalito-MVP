/**
 * Cierre anual (P2-08): valida el ejercicio en el backend, genera la póliza de
 * cierre de resultados, la de cierre de balance y la de apertura del siguiente
 * ejercicio, y cierra los doce meses. Se puede deshacer (dueño o contador, con
 * motivo) mientras enero del año siguiente siga abierto.
 */

import { useState } from 'react';
import { CalendarCheck, Undo2 } from 'lucide-react';
import {
  deshacerCierreAnual, hacerCierreAnual, validarCierreAnual,
  type EjercicioContable, type ValidacionCierre,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import ValidacionPeriodo from './ValidacionPeriodo';
import { dinero, mensaje } from './comun';

interface Props {
  clave: string;
  ejercicio: EjercicioContable;
  onCambio: () => void;
}

export default function CierreAnual({ clave, ejercicio, onCambio }: Props) {
  const anio = ejercicio.anio;
  const [traspasar, setTraspasar] = useState(false);
  const [validacion, setValidacion] = useState<ValidacionCierre | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function correr(fn: () => Promise<void>) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(mensaje(e, 'No se pudo completar el cierre anual.'));
    } finally {
      setOcupado(false);
    }
  }

  const cerrar = (forzar = false, motivo = '') => correr(async () => {
    if (!forzar) {
      const v = await validarCierreAnual(clave, anio);
      if (!v.se_puede_cerrar) { setValidacion(v); return; }
    }
    const r = await hacerCierreAnual(clave, anio, { traspasar_resultado: traspasar, forzar, motivo });
    setValidacion(null);
    setAviso(`Ejercicio ${anio} cerrado: ${r.tipo_resultado === 'utilidad' ? 'utilidad' : 'pérdida'} de ${dinero(r.resultado.replace('-', ''), '0.00')}. ${r.polizas.length} pólizas generadas.`);
    onCambio();
  });

  const deshacer = () => {
    const motivo = window.prompt(`Motivo para deshacer el cierre anual ${anio}`);
    if (!motivo) return;
    void correr(async () => {
      const r = await deshacerCierreAnual(clave, anio, motivo);
      setAviso(`Cierre anual ${anio} deshecho: ${r.canceladas} pólizas canceladas; diciembre quedó abierto.`);
      onCambio();
    });
  };

  return (
    <section className="card" aria-label="Cierre anual" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <strong style={{ display: 'flex', gap: 6, alignItems: 'center' }}><CalendarCheck size={16} /> Cierre anual {anio}</strong>
      {ejercicio.cierre_anual.hecho ? (
        <>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Hecho: {ejercicio.cierre_anual.polizas.map((p) => `${p.folio} (${p.concepto})`).join(' · ')}
          </div>
          <div><button type="button" className="btn-secondary" disabled={ocupado} onClick={deshacer}><Undo2 size={13} /> Deshacer cierre anual</button></div>
        </>
      ) : (
        <>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Salda las cuentas de resultados contra el resultado del ejercicio (305), cierra el balance al 31 de diciembre,
            abre {anio + 1} con esos saldos y cierra los doce meses.
          </div>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.85rem' }}>
            <input type="checkbox" checked={traspasar} onChange={(e) => setTraspasar(e.target.checked)} />
            Abrir {anio + 1} con el resultado ya traspasado a resultados de ejercicios anteriores (304)
          </label>
          <div><button type="button" className="btn-primary" disabled={ocupado} onClick={() => void cerrar()}>Hacer cierre anual</button></div>
        </>
      )}
      {validacion && (
        <ValidacionPeriodo titulo={`El ejercicio ${anio}`} validacion={validacion} ocupado={ocupado}
          onCancelar={() => setValidacion(null)} onForzar={(motivo) => void cerrar(true, motivo)} />
      )}
      {aviso && <div role="status" style={{ color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</div>}
      {error && <ErrorAlert message={error} />}
    </section>
  );
}
