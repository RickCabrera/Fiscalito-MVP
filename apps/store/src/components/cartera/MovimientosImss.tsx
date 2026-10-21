/**
 * Movimientos IMSS del cliente activo (P4-09): pendientes por enviar, archivo IDSE por tipo
 * (08 alta/reingreso, 07 modificación de salario, 02 baja) o de importación al SUA, y marcar
 * enviado / acuse capturado.
 *
 * Los movimientos nacen en el backend al guardar la ficha (alta, baja con causa, cambio de SBC);
 * aquí no se arma ningún registro: el layout de 168 posiciones lo escribe el backend y la
 * pantalla sólo descarga el archivo y dice quién quedó fuera y por qué.
 */

import { useCallback, useEffect, useState } from 'react';
import { Download, FileText, Loader, Send } from 'lucide-react';
import {
  descargarLote, generarArchivo, listarMovimientos, marcarMovimientos,
  type ArchivoGenerado, type DestinoArchivo, type MovimientoImss,
} from '../../services/nominaImssApi';
import { descargarBlob } from '../contabilidad/comun';
import { tdStyle, thStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';

const TIPO: Record<MovimientoImss['tipo'], string> = {
  '08': 'Alta / reingreso', '07': 'Modificación de salario', '02': 'Baja',
};
const ESTADO: Record<MovimientoImss['estado'], string> = {
  pendiente: 'Pendiente', generado: 'Archivo generado', enviado: 'Enviado',
  acuse: 'Con acuse', cancelado: 'Cancelado',
};
const ARCHIVOS: [DestinoArchivo, string][] = [
  ['idse_08', 'IDSE altas (08)'], ['idse_07', 'IDSE modificaciones (07)'], ['idse_02', 'IDSE bajas (02)'],
  ['sua_trabajadores', 'SUA trabajadores'], ['sua_movimientos', 'SUA movimientos'],
];

export default function MovimientosImss({ clienteId }: { clienteId: string }) {
  const [movs, setMovs] = useState<MovimientoImss[] | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState('');
  const [marcados, setMarcados] = useState<number[]>([]);
  const [acuse, setAcuse] = useState('');
  const [ultimo, setUltimo] = useState<ArchivoGenerado | null>(null);
  const hoy = new Date().toISOString().slice(0, 10);
  const [rango, setRango] = useState({ desde: `${hoy.slice(0, 8)}01`, hasta: hoy });

  const cargar = useCallback(() => {
    listarMovimientos(clienteId)
      .then((r) => { setMovs(r.movimientos); setError(''); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudieron cargar.'));
  }, [clienteId]);

  useEffect(() => { cargar(); }, [cargar]);

  const accion = async (llave: string, fn: () => Promise<unknown>) => {
    setOcupado(llave);
    setError('');
    try {
      await fn();
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado('');
    }
  };

  const generar = (destino: DestinoArchivo) => accion(destino, async () => {
    const cuerpo = destino === 'sua_movimientos' ? { destino, ...rango }
      : destino === 'sua_trabajadores' ? { destino, al: hoy } : { destino };
    const r = await generarArchivo(clienteId, cuerpo);
    setUltimo(r);
    descargarBlob(r.lote.nombre_archivo, await descargarLote(clienteId, r.lote.id));
  });

  const marcar = (estado: 'enviado' | 'acuse') => accion(estado, async () => {
    await marcarMovimientos(clienteId, marcados, estado, acuse);
    setMarcados([]);
    setAcuse('');
  });

  const alternar = (id: number) =>
    setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  const pendientes = movs?.filter((m) => m.estado === 'pendiente').length ?? 0;

  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
        <FileText size={16} /> Movimientos IMSS
        {pendientes > 0 && <span className="badge">{pendientes} pendiente(s) por enviar</span>}
      </h2>
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)', alignItems: 'center' }}>
        {ARCHIVOS.map(([destino, texto]) => (
          <button key={destino} className="btn-secondary" disabled={!!ocupado} onClick={() => generar(destino)}>
            {ocupado === destino ? <Loader size={14} className="spin" /> : <Download size={14} />} {texto}
          </button>
        ))}
        <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          SUA del{' '}
          <input type="date" value={rango.desde} onChange={(e) => setRango({ ...rango, desde: e.target.value })} />
          {' '}al{' '}
          <input type="date" value={rango.hasta} onChange={(e) => setRango({ ...rango, hasta: e.target.value })} />
        </label>
      </div>
      {ultimo && (
        <p role="status" style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          {ultimo.lote.nombre_archivo}: {ultimo.lote.registros} registro(s).
          {ultimo.no_exportables.length > 0 && (
            <> Quedaron fuera: {ultimo.no_exportables.map((x) => `${x.empleado_no} (${x.motivo})`).join('; ')}.</>
          )}
        </p>
      )}
      {!movs && !error && <Loader size={16} className="spin" aria-label="Cargando movimientos" />}
      {movs && movs.length === 0 && (
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>
          Sin movimientos. Nacen al dar de alta, de baja o cambiar el SBC de un empleado.
        </p>
      )}
      {movs && movs.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr>
                <th style={thStyle}>Marcar</th>
                <th style={thStyle}>Empleado</th>
                <th style={thStyle}>Movimiento</th>
                <th style={thStyle}>Fecha</th>
                <th style={thStyle}>SBC / causa</th>
                <th style={thStyle}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {movs.map((m) => (
                <tr key={m.id}>
                  <td style={tdStyle}>
                    <input
                      type="checkbox"
                      aria-label={`Marcar movimiento ${m.id}`}
                      checked={marcados.includes(m.id)}
                      disabled={m.estado === 'acuse' || m.estado === 'cancelado'}
                      onChange={() => alternar(m.id)}
                    />
                  </td>
                  <td style={tdStyle}>{m.empleado_no} {m.nombre}</td>
                  <td style={tdStyle}>{m.tipo} · {TIPO[m.tipo]}</td>
                  <td style={tdStyle}>{m.fecha}</td>
                  <td style={tdStyle}>{m.tipo === '02' ? `Causa ${m.causa_baja || '— (falta)'}` : m.sbc}</td>
                  <td style={tdStyle}>{ESTADO[m.estado]}{m.acuse ? ` · ${m.acuse}` : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {marcados.length > 0 && (
        <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn-secondary" disabled={!!ocupado} onClick={() => marcar('enviado')}>
            <Send size={14} /> Marcar como enviados
          </button>
          <input
            aria-label="Folio del acuse"
            placeholder="Folio / lote del acuse IMSS"
            value={acuse}
            onChange={(e) => setAcuse(e.target.value)}
          />
          <button className="btn-primary" disabled={!!ocupado || !acuse.trim()} onClick={() => marcar('acuse')}>
            Capturar acuse
          </button>
        </div>
      )}
    </section>
  );
}
