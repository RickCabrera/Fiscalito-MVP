/**
 * La rejilla de captura del CFDI de nómina: un renglón por empleado (T4).
 *
 * Salió de `PanelCFDINomina` porque ese archivo pasaba de las 300 líneas que
 * `apps/store/CLAUDE.md` pone en su sección NUNCA. Es presentacional: no llama
 * al backend, no decide qué falta y no guarda nada — recibe `faltantesDe` ya
 * resuelto y devuelve lo tecleado.
 *
 * **Cada campo dice qué le falta al lado del botón, no sólo en el `title`.** Un
 * botón deshabilitado no recibe hover en táctil: es la misma razón por la que
 * T8 escribió el motivo del límite de clientes en pantalla.
 */

import { FileCode2, Loader } from 'lucide-react';
import type { ReciboNomina } from '../../services/nominaDemoApi';
import CampoCFDI from './CampoCFDI';
import { CAPTURA_VACIA, type DatosTrabajadorCaptura } from './capturaCFDI';
import { envoltura, fila, tabla, td, th } from './estilosTabla';

interface Props {
  recibos: ReciboNomina[];
  capturado: Record<string, DatosTrabajadorCaptura>;
  /** El NSS que la cartera SÍ guarda, por `empleado_no`. Es el default del campo. */
  nssDeLaCartera: (empleadoNo: string) => string;
  onCambiar: (empleadoNo: string, campo: keyof DatosTrabajadorCaptura, valor: string) => void;
  faltantesDe: (recibo: ReciboNomina) => string[];
  /** `empleado_no` en curso, `'todos'`, o `null` si no hay nada corriendo. */
  generando: string | null;
  deshabilitado: boolean;
  onGenerar: (recibo: ReciboNomina) => void;
}

export default function TablaCFDIEmpleados({
  recibos,
  capturado,
  nssDeLaCartera,
  onCambiar,
  faltantesDe,
  generando,
  deshabilitado,
  onGenerar,
}: Props) {
  return (
    <div style={envoltura}>
      <table style={tabla(880)}>
        <thead>
          <tr>
            <th style={th}>Empleado</th>
            <th style={th}>RFC</th>
            <th style={th}>CURP</th>
            <th style={th}>NSS</th>
            <th style={th}>CP</th>
            <th style={th}>XML</th>
          </tr>
        </thead>
        <tbody>
          {recibos.map((r, i) => {
            const datos = capturado[r.empleado_no] ?? CAPTURA_VACIA;
            const cambiar = (campo: keyof DatosTrabajadorCaptura) => (v: string) =>
              onCambiar(r.empleado_no, campo, v);
            const falta = faltantesDe(r);
            return (
              <tr key={r.empleado_no} style={fila(i)}>
                <td style={td}>
                  {r.nombre}{' '}
                  <span style={{ color: 'var(--text-muted)' }}>({r.empleado_no})</span>
                </td>
                <td style={td}>
                  <CampoCFDI etiqueta={`RFC de ${r.nombre}`} ejemplo="XAXX010101000"
                    maxLength={13} valor={datos.rfc} onChange={cambiar('rfc')} />
                </td>
                <td style={td}>
                  <CampoCFDI etiqueta={`CURP de ${r.nombre}`} maxLength={18}
                    valor={datos.curp} onChange={cambiar('curp')} />
                </td>
                <td style={td}>
                  <CampoCFDI etiqueta={`NSS de ${r.nombre}`}
                    valor={datos.nss || nssDeLaCartera(r.empleado_no)}
                    onChange={cambiar('nss')} />
                </td>
                <td style={td}>
                  <CampoCFDI etiqueta={`CP de ${r.nombre}`} ejemplo="91020" maxLength={5}
                    valor={datos.codigo_postal} onChange={cambiar('codigo_postal')} />
                </td>
                <td style={td}>
                  <button className="btn-secondary" style={{ fontSize: '0.75rem' }}
                    disabled={deshabilitado || falta.length > 0 || generando !== null}
                    title={falta.length ? `Falta: ${falta.join(', ')}` : 'Descarga el XML'}
                    onClick={() => onGenerar(r)}>
                    {generando === r.empleado_no
                      ? <Loader size={13} className="spin" />
                      : <FileCode2 size={13} />}
                    {' '}Generar
                  </button>
                  {falta.length > 0 && (
                    <div style={{ fontSize: '0.7rem', color: 'var(--warning)', marginTop: 4 }}>
                      Falta: {falta.join(', ')}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
