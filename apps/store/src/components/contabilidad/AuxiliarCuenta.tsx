/**
 * Auxiliar de una cuenta (P2-04): saldo inicial, cada movimiento del periodo
 * con su póliza y saldo corrido, y saldo final — los mismos números que el
 * renglón de la balanza. Desde aquí se abre la póliza o se baja el XML del CFDI
 * de la bóveda.
 */

import { useEffect, useState } from 'react';
import { Download, Loader, X } from 'lucide-react';
import { obtenerAuxiliar, type Auxiliar, type RenglonBalanza } from '../../services/contabilidadApi';
import { descargarXml } from '../../services/bovedaApi';
import ErrorAlert from '../common/ErrorAlert';
import { descargarBlob, dinero, mensaje } from './comun';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

interface Props {
  clave: string;
  cuenta: RenglonBalanza;
  desde: string;
  hasta: string;
  onCerrar: () => void;
  onAbrirPoliza: (id: number) => void;
}

export default function AuxiliarCuenta({ clave, cuenta, desde, hasta, onCerrar, onAbrirPoliza }: Props) {
  const llave = `${cuenta.cuenta_id}|${desde}|${hasta}`;
  const [carga, setCarga] = useState<{ llave: string; aux: Auxiliar } | null>(null);
  const aux = carga?.llave === llave ? carga.aux : null;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    obtenerAuxiliar(clave, cuenta.cuenta_id, desde, hasta)
      .then((r) => { if (vivo) { setCarga({ llave, aux: r }); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo cargar el auxiliar.')); });
    return () => { vivo = false; };
  }, [clave, cuenta.cuenta_id, desde, hasta, llave]);

  async function xml(uuid: string) {
    try {
      descargarBlob(`${uuid}.xml`, await descargarXml(clave, uuid));
    } catch (e) {
      setError(mensaje(e, 'No se pudo descargar el XML.'));
    }
  }

  return (
    <section className="card" aria-label={`Auxiliar de ${cuenta.numero}`} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', borderColor: 'var(--border-active)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <strong style={{ flex: 1 }}>Auxiliar {cuenta.numero} {cuenta.nombre} · {desde} a {hasta}</strong>
        <button type="button" className="btn-secondary" aria-label="Cerrar auxiliar" onClick={onCerrar}><X size={14} /></button>
      </div>
      {error && <ErrorAlert message={error} />}
      {!aux ? (!error && <div><Loader size={16} className="spin" /> Cargando…</div>) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={thStyle}>Fecha</th><th style={thStyle}>Póliza</th><th style={thStyle}>Concepto</th>
                <th style={thStyle}>Cuenta</th><th style={{ ...thStyle, textAlign: 'right' }}>Cargo</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Abono</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Saldo</th><th style={thStyle}>XML</th>
              </tr>
            </thead>
            <tbody>
              <tr><td style={tdStyle} colSpan={6}>Saldo inicial</td><td style={tdMonoStyle}>{dinero(aux.saldo_inicial, '0.00')}</td><td /></tr>
              {aux.movimientos.map((m, i) => (
                <tr key={`${m.poliza_id}-${i}`} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={tdStyle}>{m.fecha}</td>
                  <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>
                    <button type="button" onClick={() => onAbrirPoliza(m.poliza_id)}
                      style={{ background: 'none', border: 'none', color: 'var(--teal-light)', font: 'inherit', cursor: 'pointer', padding: 0 }}>
                      {m.folio}
                    </button>
                  </td>
                  <td style={tdStyle}>{m.concepto}</td>
                  <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>{m.cuenta}</td>
                  <td style={tdMonoStyle}>{dinero(m.cargo, '')}</td>
                  <td style={tdMonoStyle}>{dinero(m.abono, '')}</td>
                  <td style={tdMonoStyle}>{dinero(m.saldo, '0.00')}</td>
                  <td style={tdStyle}>
                    {m.uuid && m.xml_disponible && (
                      <button type="button" className="btn-secondary" style={{ padding: '3px 8px' }}
                        aria-label={`Descargar XML ${m.uuid}`} onClick={() => void xml(m.uuid)}>
                        <Download size={13} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              <tr style={{ fontWeight: 700 }}>
                <td style={tdStyle} colSpan={4}>Totales y saldo final</td>
                <td style={tdMonoStyle}>{dinero(aux.cargos, '0.00')}</td>
                <td style={tdMonoStyle}>{dinero(aux.abonos, '0.00')}</td>
                <td style={tdMonoStyle}>{dinero(aux.saldo_final, '0.00')}</td>
                <td />
              </tr>
            </tbody>
          </table>
          {aux.truncado && <p style={{ color: 'var(--warning)', fontSize: '0.8rem' }}>Se muestran los primeros 5,000 movimientos; acota el periodo.</p>}
        </div>
      )}
    </section>
  );
}
