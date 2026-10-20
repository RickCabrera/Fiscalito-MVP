/**
 * Historial de nóminas del cliente (P4-02): lista, abrir, cerrar y comparar dos periodos.
 *
 * Abrir pinta lo GUARDADO: el backend no recalcula, así que una nómina de hace tres meses
 * se ve igual a como se calculó. Comparar pide al backend las diferencias; aquí no se
 * resta nada.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  abrirPeriodo,
  cerrarPeriodoNomina,
  compararPeriodos,
  listarHistorial,
  type Comparacion,
  type PeriodoGuardado,
  type ResumenPeriodo,
} from '../../services/nominaApi';
import { fmtMoney } from '../../utils/format';
import DesgloseRecibos, { type ReciboDesglosado } from './DesgloseRecibos';
import PanelDispersion from './PanelDispersion';
import PanelEnvioRecibos from './PanelEnvioRecibos';
import { envoltura, fila, tabla, td, tdNum, th, thNum, tituloSeccion } from './estilosTabla';

export default function HistorialNominas({ clienteId }: { clienteId: string }) {
  const [periodos, setPeriodos] = useState<ResumenPeriodo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<PeriodoGuardado | null>(null);
  const [marcados, setMarcados] = useState<number[]>([]);
  const [comparacion, setComparacion] = useState<Comparacion | null>(null);
  // P4-12/13: sobre una nómina cerrada, la dispersión o el envío de recibos.
  const [panel, setPanel] = useState<{ tipo: 'dispersion' | 'envio'; id: number } | null>(null);

  const cargar = useCallback(() => {
    setError(null);
    listarHistorial(clienteId)
      .then((r) => setPeriodos(r.periodos))
      .catch((e: Error) => setError(e.message));
  }, [clienteId]);

  // Al cambiar de cliente la pantalla monta este componente con otra `key`, así que el
  // estado ya nace limpio: aquí sólo se pide la lista.
  useEffect(() => {
    let cancelado = false;
    listarHistorial(clienteId)
      .then((r) => !cancelado && setPeriodos(r.periodos))
      .catch((e: Error) => !cancelado && setError(e.message));
    return () => {
      cancelado = true;
    };
  }, [clienteId]);

  const accion = (promesa: Promise<unknown>) => promesa.catch((e: Error) => setError(e.message));

  const marcar = (id: number) =>
    setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id].slice(-2)));

  if (periodos === null && !error) return <p style={{ color: 'var(--text-muted)' }}>Cargando historial…</p>;

  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <h2 style={tituloSeccion}>Historial de nóminas</h2>
      {error && (
        <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>
          {error}
        </p>
      )}
      {periodos && periodos.length === 0 && (
        <p style={{ color: 'var(--text-muted)', margin: 0 }}>Aún no hay nóminas guardadas de este cliente.</p>
      )}
      {periodos && periodos.length > 0 && (
        <div style={envoltura}>
          <table style={tabla(820)}>
            <thead>
              <tr>
                <th style={th}>Comparar</th>
                <th style={th}>Tipo</th>
                <th style={th}>Periodo</th>
                <th style={th}>Estado</th>
                <th style={thNum}>Percepciones</th>
                <th style={thNum}>ISR</th>
                <th style={thNum}>Neto</th>
                <th style={th}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {periodos.map((p, i) => (
                <tr key={p.id} style={fila(i)}>
                  <td style={td}>
                    <input
                      type="checkbox"
                      aria-label={`Comparar periodo ${p.id}`}
                      checked={marcados.includes(p.id)}
                      onChange={() => marcar(p.id)}
                    />
                  </td>
                  <td style={td}>{p.tipo}</td>
                  <td style={td}>
                    {p.inicio} a {p.fin}
                  </td>
                  <td style={td}>{p.estado}</td>
                  <td style={tdNum}>{fmtMoney(Number(p.total_percepciones))}</td>
                  <td style={tdNum}>{fmtMoney(Number(p.total_isr))}</td>
                  <td style={tdNum}>{fmtMoney(Number(p.total_neto))}</td>
                  <td style={{ ...td, display: 'flex', gap: 'var(--space-xs)' }}>
                    <button className="btn-secondary" onClick={() => accion(abrirPeriodo(clienteId, p.id).then(setAbierto))}>
                      Abrir
                    </button>
                    {p.estado === 'calculada' && (
                      <button
                        className="btn-secondary"
                        onClick={() => accion(cerrarPeriodoNomina(clienteId, p.id).then(cargar))}
                      >
                        Cerrar
                      </button>
                    )}
                    {(p.estado === 'cerrada' || p.estado === 'timbrada') && (
                      <>
                        <button className="btn-secondary" onClick={() => setPanel({ tipo: 'dispersion', id: p.id })}>
                          Dispersión
                        </button>
                        <button className="btn-secondary" onClick={() => setPanel({ tipo: 'envio', id: p.id })}>
                          Enviar recibos
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {panel?.tipo === 'dispersion' && <PanelDispersion key={`d${panel.id}`} clienteId={clienteId} periodoId={panel.id} />}
      {panel?.tipo === 'envio' && <PanelEnvioRecibos key={`e${panel.id}`} clienteId={clienteId} periodoId={panel.id} />}
      <div>
        <button
          className="btn-primary"
          disabled={marcados.length !== 2}
          onClick={() => {
            const [a, b] = [...marcados].sort((x, y) => x - y);
            accion(compararPeriodos(clienteId, a, b).then(setComparacion));
          }}
        >
          Comparar los dos marcados
        </button>
      </div>
      {comparacion && (
        <p style={{ margin: 0 }}>
          Del periodo {comparacion.a.inicio} al {comparacion.b.inicio}: neto{' '}
          <strong>{fmtMoney(Number(comparacion.diferencia_neto))}</strong>, ISR{' '}
          <strong>{fmtMoney(Number(comparacion.diferencia_isr))}</strong>, percepciones{' '}
          <strong>{fmtMoney(Number(comparacion.diferencia_percepciones))}</strong>.
        </p>
      )}
      {abierto && (
        <>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Periodo {abierto.periodo.inicio} a {abierto.periodo.fin} ({abierto.periodo.estado}), calculado con
            UMA {String(abierto.parametros.uma_diaria ?? '—')} y criterios{' '}
            {Object.entries(abierto.criterios)
              .map(([k, v]) => `${k}: ${v}`)
              .join(', ')}
            . Se muestra tal como se guardó.
          </p>
          <DesgloseRecibos recibos={(abierto.resultado.recibos as ReciboDesglosado[] | undefined) ?? []} />
        </>
      )}
    </section>
  );
}
