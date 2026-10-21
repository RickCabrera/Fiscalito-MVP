/**
 * Enviar los recibos de una nómina cerrada al trabajador (P4-13).
 *
 * Elegir canal (correo o WhatsApp), enviar —el backend lo hace en segundo plano—, ver el
 * estado por recibo (pendiente / enviado / fallido / rebotado), reenviar uno, y ver a
 * quién NO se le mandó y por qué (sin correo, sin celular, sin consentimiento).
 * Sin timbrado todavía, lo que viaja es el PDF del recibo marcado "SIN TIMBRAR".
 */

import { useCallback, useEffect, useState } from 'react';
import {
  enviarRecibos,
  estadoEnvios,
  reenviarRecibo,
  type Canal,
  type EstadoEnvios,
} from '../../services/dispersionApi';
import PlantillasRecibo from './PlantillasRecibo';
import { envoltura, fila, tabla, td, th } from './estilosTabla';

const COLOR: Record<string, string> = {
  pendiente: 'var(--text-secondary)', enviado: 'var(--success)', fallido: 'var(--danger)', rebotado: 'var(--warning)',
};

export default function PanelEnvioRecibos({ clienteId, periodoId }: { clienteId: string; periodoId: number }) {
  const [canal, setCanal] = useState<Canal>('correo');
  const [estado, setEstado] = useState<EstadoEnvios | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [verPlantillas, setVerPlantillas] = useState(false);

  const accion = useCallback(async (p: Promise<EstadoEnvios>) => {
    setOcupado(true);
    setError(null);
    try {
      setEstado(await p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar');
    } finally {
      setOcupado(false);
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    estadoEnvios(clienteId, periodoId, canal)
      .then((r) => vivo && setEstado(r))
      .catch((e: Error) => vivo && setError(e.message));
    return () => {
      vivo = false;
    };
  }, [clienteId, periodoId, canal]);

  return (
    <section aria-label="Envío de recibos" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ margin: 0, fontSize: '1rem' }}>Enviar recibos</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)', alignItems: 'center' }}>
        <label style={{ fontSize: '0.85rem' }}>
          Canal{' '}
          <select
            value={canal}
            onChange={(e) => setCanal(e.target.value as Canal)}
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
          >
            <option value="correo">Correo</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
        </label>
        <button className="btn-primary" disabled={ocupado} onClick={() => accion(enviarRecibos(clienteId, periodoId, canal))}>
          {ocupado ? 'Enviando…' : 'Enviar recibos'}
        </button>
        <button className="btn-secondary" disabled={ocupado} onClick={() => accion(estadoEnvios(clienteId, periodoId, canal))}>
          Actualizar estado
        </button>
        <button className="btn-secondary" onClick={() => setVerPlantillas((v) => !v)}>
          {verPlantillas ? 'Ocultar plantillas' : 'Plantillas'}
        </button>
      </div>
      {verPlantillas && <PlantillasRecibo />}
      {error && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)' }}>
          {error}
        </p>
      )}
      {estado && (
        <>
          <p style={{ margin: 0, fontSize: '0.85rem' }}>
            {Object.entries(estado.resumen)
              .map(([k, v]) => `${v} ${k}`)
              .join(' · ')}
            {estado.trabajo ? ` — trabajo ${estado.trabajo.estado}` : ''}
          </p>
          {estado.envios.length > 0 && (
            <div style={envoltura}>
              <table style={tabla(620)} aria-label="Estado por recibo">
                <thead>
                  <tr>
                    <th style={th}>Empleado</th>
                    <th style={th}>Destino</th>
                    <th style={th}>Estado</th>
                    <th style={th}>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {estado.envios.map((e, i) => (
                    <tr key={e.id} style={fila(i)}>
                      <td style={td}>{e.empleado_no}</td>
                      <td style={td}>{e.destino}</td>
                      <td style={{ ...td, color: COLOR[e.estado] }} title={e.error || undefined}>
                        {e.estado}
                        {e.timbrado ? '' : ' (sin timbrar)'}
                        {e.error ? ` — ${e.error}` : ''}
                      </td>
                      <td style={td}>
                        {e.estado !== 'pendiente' && (
                          <button
                            className="btn-secondary"
                            disabled={ocupado}
                            onClick={() => accion(reenviarRecibo(clienteId, periodoId, e.id))}
                          >
                            Reenviar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {estado.omitidos.length > 0 && (
            <ul aria-label="No se envían" style={{ margin: 0, fontSize: '0.82rem', color: 'var(--warning)' }}>
              {estado.omitidos.map((o) => (
                <li key={o.empleado_no}>
                  {o.empleado_no} · {o.nombre}: {o.motivo}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
