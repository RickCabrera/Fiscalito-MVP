/**
 * Cómo se le paga y por dónde se le mandan los recibos (P4-12, P4-13).
 *
 * Forma de pago, banco, CLABE (con su dígito verificador al teclear), cuenta o tarjeta,
 * correo, celular y el consentimiento de WhatsApp. La validación al teclear es
 * `services/clabe.ts`; la autoridad es el backend, que rechaza lo mismo.
 *
 * Nada se infiere: sin CLABE ni cuenta, el empleado queda fuera de la dispersión con su
 * motivo en el reporte de excluidos; sin consentimiento no se le escribe por WhatsApp.
 */

import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';
import { BANCOS, errorPagoContacto } from '../../services/clabe';
import type { EmpleadoCartera, FormaPagoEmpleado } from '../../services/carteraModelo';

export default function PagoContactoEmpleado({
  datos,
  set,
}: {
  datos: EmpleadoCartera;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
}) {
  const error = errorPagoContacto(datos);
  const deClabe = (datos.clabe ?? '').replace(/\s/g, '').slice(0, 3);
  return (
    <fieldset style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)' }}>
      <legend style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Pago y contacto</legend>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
        <Campo label="Forma de pago">
          <select
            style={campo}
            value={datos.forma_pago ?? 'transferencia'}
            onChange={(e) => set('forma_pago', e.target.value as FormaPagoEmpleado)}
          >
            <option value="transferencia">Transferencia</option>
            <option value="efectivo">Efectivo</option>
            <option value="cheque">Cheque</option>
          </select>
        </Campo>
        <Campo label="Banco">
          <select style={campo} value={datos.banco ?? ''} onChange={(e) => set('banco', e.target.value)}>
            <option value="">{deClabe && BANCOS[deClabe] ? `El de la CLABE (${BANCOS[deClabe]})` : '—'}</option>
            {Object.entries(BANCOS).map(([clave, nombre]) => (
              <option key={clave} value={clave}>
                {clave} · {nombre}
              </option>
            ))}
          </select>
        </Campo>
        <Campo label="CLABE (18 dígitos)" ancho="2 1 240px">
          <input
            style={campo}
            inputMode="numeric"
            value={datos.clabe ?? ''}
            onChange={(e) => set('clabe', e.target.value)}
          />
        </Campo>
        <Campo label="Cuenta o tarjeta">
          <input
            style={campo}
            inputMode="numeric"
            value={datos.numero_cuenta ?? ''}
            onChange={(e) => set('numero_cuenta', e.target.value)}
          />
        </Campo>
        <Campo label="Correo" ancho="2 1 240px">
          <input style={campo} type="email" value={datos.correo ?? ''} onChange={(e) => set('correo', e.target.value)} />
        </Campo>
        <Campo label="Celular (+52)">
          <input style={campo} value={datos.celular ?? ''} onChange={(e) => set('celular', e.target.value)} />
        </Campo>
        <label style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center', fontSize: '0.85rem' }}>
          <input
            type="checkbox"
            checked={Boolean(datos.consentimiento_whatsapp)}
            onChange={(e) => set('consentimiento_whatsapp', e.target.checked)}
          />
          Aceptó recibir sus recibos por WhatsApp
        </label>
      </div>
      {error && (
        <p role="alert" style={{ margin: 'var(--space-xs) 0 0', color: 'var(--danger)', fontSize: '0.82rem' }}>
          {error}
        </p>
      )}
    </fieldset>
  );
}
