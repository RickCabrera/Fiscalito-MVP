/**
 * Tab "Periodos" de Contabilito (P2-08): estado de cada mes del ejercicio,
 * cerrar (con la validación del backend: balanza cuadrada y CFDI sin póliza,
 * con su lista), reabrir con motivo (sólo dueño o contador: el backend lo
 * exige y aquí se pinta su respuesta), cierre anual y bitácora.
 */

import { useEffect, useState } from 'react';
import { Loader, Lock, Unlock } from 'lucide-react';
import {
  cerrarMes, obtenerEjercicio, reabrirMes, validarCierreMes,
  type EjercicioContable, type ValidacionCierre,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import CierreAnual from './CierreAnual';
import ValidacionPeriodo from './ValidacionPeriodo';
import { MESES, mensaje } from './comun';
import { labelStyle, tdStyle, thStyle } from '../../utils/styles';

const ACCIONES: Record<string, string> = {
  cerrar: 'Cierre', reabrir: 'Reapertura', cierre_anual: 'Cierre anual', deshacer_cierre_anual: 'Cierre anual deshecho',
};

export default function PeriodosContables({ clave }: { clave: string }) {
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [ejercicio, setEjercicio] = useState<EjercicioContable | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [revision, setRevision] = useState<{ mes: number; v: ValidacionCierre } | null>(null);

  const [recarga, setRecarga] = useState(0);
  const cargar = () => setRecarga((n) => n + 1);

  useEffect(() => {
    let vivo = true;
    obtenerEjercicio(clave, anio)
      .then((r) => { if (vivo) { setEjercicio(r); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron leer los periodos.')); });
    return () => { vivo = false; };
  }, [clave, anio, recarga]);

  async function accion(fn: () => Promise<unknown>) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      cargar();
    } catch (e) {
      setError(mensaje(e, 'No se pudo completar la acción.'));
    } finally {
      setOcupado(false);
    }
  }

  async function revisar(mes: number) {
    await accion(async () => {
      const v = await validarCierreMes(clave, anio, mes);
      if (v.se_puede_cerrar) {
        await cerrarMes(clave, anio, mes);
        setRevision(null);
      } else {
        setRevision({ mes, v });
      }
    });
  }

  function reabrir(mes: number) {
    const motivo = window.prompt(`Motivo para reabrir ${MESES[mes - 1]} ${anio}`);
    if (!motivo) return;
    void accion(() => reabrirMes(clave, anio, mes, motivo));
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <label><span style={labelStyle}>Ejercicio</span>
          <input className="input-field" type="number" aria-label="Ejercicio" min={2000} max={2100} value={anio}
            onChange={(e) => { setRevision(null); setAnio(Number(e.target.value)); }} /></label>
        {(!ejercicio || ocupado) && !error && <Loader size={16} className="spin" />}
        <span style={{ flex: 1, color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
          Un mes cerrado no acepta pólizas nuevas, ediciones ni cancelaciones. Reabrir pide motivo y queda en la bitácora.
        </span>
      </div>

      {error && <ErrorAlert message={error} />}

      {revision && (
        <ValidacionPeriodo titulo={`${MESES[revision.mes - 1]} ${anio}`} validacion={revision.v} ocupado={ocupado}
          onCancelar={() => setRevision(null)}
          onForzar={(motivo) => void accion(async () => { await cerrarMes(clave, anio, revision.mes, true, motivo); setRevision(null); })} />
      )}

      {ejercicio && (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={thStyle}>Mes</th><th style={thStyle}>Estado</th><th style={{ ...thStyle, textAlign: 'right' }}>Pólizas</th>
                <th style={thStyle}>Cerrado</th><th style={thStyle} />
              </tr>
            </thead>
            <tbody>
              {ejercicio.meses.map((m) => (
                <tr key={m.mes} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={tdStyle}>{MESES[m.mes - 1]}</td>
                  <td style={{ ...tdStyle, color: m.estado === 'cerrado' ? 'var(--warning)' : 'var(--success)' }}>
                    {m.estado === 'cerrado' ? 'Cerrado' : 'Abierto'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{m.polizas}</td>
                  <td style={{ ...tdStyle, fontSize: '0.78rem' }}>{m.cerrado_en ? m.cerrado_en.slice(0, 16).replace('T', ' ') : '—'}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {m.estado === 'abierto' ? (
                      <button type="button" className="btn-secondary" disabled={ocupado} aria-label={`Cerrar ${MESES[m.mes - 1]}`}
                        onClick={() => void revisar(m.mes)}><Lock size={13} /> Cerrar</button>
                    ) : (
                      <button type="button" className="btn-secondary" disabled={ocupado} aria-label={`Reabrir ${MESES[m.mes - 1]}`}
                        onClick={() => reabrir(m.mes)}><Unlock size={13} /> Reabrir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {ejercicio && <CierreAnual clave={clave} ejercicio={ejercicio} onCambio={cargar} />}

      {ejercicio && ejercicio.historial.length > 0 && (
        <section className="card" aria-label="Bitácora de periodos" style={{ fontSize: '0.82rem' }}>
          <strong>Bitácora</strong>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: 'var(--text-secondary)' }}>
            {ejercicio.historial.map((h, i) => (
              <li key={`${h.fecha}-${i}`}>
                {h.fecha.slice(0, 16).replace('T', ' ')} · {ACCIONES[h.accion] ?? h.accion}
                {h.mes > 0 ? ` de ${MESES[h.mes - 1]}` : ''}{h.motivo ? ` · ${h.motivo}` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
