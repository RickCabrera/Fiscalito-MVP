/**
 * Tab de empleados de la ficha del cliente (G-01, G-02).
 *
 * EL AVISO DE "NO VINCULADOS" NO ES EL MISMO QUE EL DE "DESCONOCIDOS"
 * -------------------------------------------------------------------
 * Son dos conjuntos que no se tocan y responden preguntas distintas:
 *
 * - **No vinculado** (aquí): un empleado de la cartera **sin `employee_no`**.
 *   No genera checadas atribuibles porque no hay llave con qué casarlas.
 * - **Desconocido** (`TablaIncidencias`, herencia D-04): un `employeeNo` que
 *   **sí checó** y no está en la plantilla.
 *
 * El primero se cuenta desde la CARTERA; el segundo, desde el flujo de eventos.
 * Tener sólo uno de los dos deja gente perdida en silencio, que es justo lo que
 * G-02 viene a evitar.
 */

import { useMemo, useState } from 'react';
import { AlertTriangle, Pencil, Plus, Trash2 } from 'lucide-react';
import {
  contarSinVincular,
  estaVinculado,
  type EmpleadoCartera,
} from '../../services/carteraApi';
import { nssPorVerificar } from '../../services/nss';
import { envoltura, fila, tabla, td, th, thNum, tituloSeccion } from '../nomina/estilosTabla';
import ModalEmpleado from './ModalEmpleado';
import { modoEmpresaUnica } from '../../services/modoEmpresa';
import type { ParametrosSalariales } from '../../services/carteraApi';

const num: React.CSSProperties = {
  ...td,
  textAlign: 'right',
  fontFamily: "'JetBrains Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
};

function Insignia({ texto, color }: { texto: string; color: string }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 'var(--radius-full)', fontSize: '0.68rem',
      fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
      border: `1px solid ${color}`, color, whiteSpace: 'nowrap',
    }}>
      {texto}
    </span>
  );
}

export default function EmpleadosTab({
  empleados,
  soloLectura,
  onGuardar,
  onBorrar,
  parametros,
}: {
  empleados: EmpleadoCartera[];
  /** `true` cuando la cartera viene del backend y no se puede escribir. */
  soloLectura: boolean;
  onGuardar: (e: EmpleadoCartera) => Promise<void>;
  /** Prestaciones del patrón (O-03): default del alta y escala del SBC. */
  parametros?: ParametrosSalariales;
  onBorrar: (empleadoNo: string) => Promise<void>;
}) {
  const [editando, setEditando] = useState<EmpleadoCartera | null>(null);
  const [abierto, setAbierto] = useState(false);
  // La confirmación es ESTADO, no `window.confirm`: es el patrón que ya usa
  // `useNominaCliente` para no cerrar una quincena sin preguntar. Un borrado en
  // Firestore es irreversible y cambia la nómina del cliente desde ese momento;
  // el botón es un icono de 15 px y en una demo con el proyector encendido, un
  // misclic se lleva a un empleado para siempre.
  const [porBorrar, setPorBorrar] = useState<EmpleadoCartera | null>(null);

  const sinVincular = useMemo(() => contarSinVincular(empleados), [empleados]);
  const llaves = useMemo(() => empleados.map((e) => e.empleado_no), [empleados]);
  /** Números de aparato de los OTROS: el que se edita no choca consigo mismo. */
  const numerosDeAparato = useMemo(
    () =>
      empleados
        .filter((e) => e.empleado_no !== editando?.empleado_no)
        .map((e) => e.employee_no)
        .filter((n): n is string => Boolean(n)),
    [empleados, editando],
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
        <h2 style={{ ...tituloSeccion, margin: 0 }}>
          Empleados{' '}
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· {empleados.length}</span>
        </h2>
        {!soloLectura && (
          <button
            className="btn-primary"
            onClick={() => { setEditando(null); setAbierto(true); }}
            style={{ display: 'flex', gap: 6, alignItems: 'center' }}
          >
            <Plus size={16} /> Nuevo empleado
          </button>
        )}
      </div>

      {/* G-02: el conteo sale de la cartera, no del flujo de checadas. */}
      {sinVincular > 0 && (
        <p
          role="alert"
          style={{
            margin: 0, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
            borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm) var(--space-md)',
            fontSize: '0.88rem', color: 'var(--text-primary)',
          }}
        >
          <strong>
            {sinVincular} {sinVincular === 1 ? 'empleado no está vinculado' : 'empleados no están vinculados'} al
            checador.
          </strong>{' '}
          Sin <code>employeeNo</code> no hay forma de atribuirle sus checadas, así que{' '}
          {sinVincular === 1 ? 'no entra' : 'no entran'} al cálculo de nómina de este periodo.
          Dale de alta el número que tenga en el aparato.
        </p>
      )}

      <div style={envoltura}>
        <table style={tabla(1000)}>
          <thead>
            <tr>
              <th style={th}>Núm.</th>
              <th style={th}>Nombre</th>
              <th style={th}>Puesto</th>
              <th style={thNum}>Salario diario</th>
              <th style={thNum}>SBC</th>
              <th style={th}>Alta</th>
              <th style={th}>NSS</th>
              <th style={th}>Checador</th>
              {!soloLectura && <th style={th} aria-label="Acciones" />}
            </tr>
          </thead>
          <tbody>
            {empleados.map((e, idx) => (
              <tr key={e.empleado_no} style={fila(idx)}>
                <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace" }}>{e.empleado_no}</td>
                <td style={td}>{e.nombre}</td>
                <td style={{ ...td, color: 'var(--text-secondary)' }}>{e.puesto || '—'}</td>
                <td style={num}>${e.salario_diario}</td>
                <td style={num}>${e.salario_diario_integrado}</td>
                <td style={{ ...td, color: 'var(--text-secondary)' }}>{e.fecha_alta ?? '—'}</td>
                {/* R-03: un NSS guardado con el dígito verificador en desacuerdo
                    NO se pierde de vista. El modal deja guardarlo a propósito
                    —bloquearlo empujaría a inventar uno que pase Luhn— y el
                    precio de esa decisión es que aquí tiene que verse. */}
                <td style={td}>
                  {e.nss ? (
                    <span style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{e.nss}</span>
                      {nssPorVerificar(e.nss) && (
                        <Insignia texto="Por verificar" color="var(--warning)" />
                      )}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)' }}>—</span>
                  )}
                </td>
                <td style={td}>
                  {estaVinculado(e) ? (
                    <span style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{e.employee_no}</span>
                      {e.enrolamiento === 'pendiente' && (
                        <Insignia texto="Sin rostro" color="var(--warning)" />
                      )}
                    </span>
                  ) : (
                    <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                      <AlertTriangle size={14} color="var(--warning)" />
                      <Insignia texto="No vinculado" color="var(--warning)" />
                    </span>
                  )}
                </td>
                {!soloLectura && (
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>
                    <button
                      aria-label={`Editar ${e.nombre}`}
                      onClick={() => { setEditando(e); setAbierto(true); }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      aria-label={`Dar de baja a ${e.nombre}`}
                      onClick={() => setPorBorrar(e)}
                      style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {empleados.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0 }}>
          {modoEmpresaUnica()
            ? 'Todavía no hay empleados dados de alta.'
            : 'Este cliente no tiene empleados todavía.'}
        </p>
      )}

      {soloLectura && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: 0 }}>
          {modoEmpresaUnica()
            ? 'Esta plantilla es de sólo lectura. Revisa que tu cuenta tenga permiso de escritura.'
            : 'Estás viendo el catálogo de demostración, que es de sólo lectura. Para dar de alta empleados hace falta que tu cartera esté guardada en tu cuenta.'}
        </p>
      )}

      {porBorrar && (
        <p
          role="alert"
          style={{
            margin: 0, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
            borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm) var(--space-md)',
            fontSize: '0.88rem', display: 'flex', gap: 'var(--space-sm)',
            alignItems: 'center', flexWrap: 'wrap',
          }}
        >
          <span>
            ¿Dar de baja a <strong>{porBorrar.nombre}</strong>? Deja de aparecer en la nómina
            {modoEmpresaUnica() ? '' : ' de este cliente'} y no se puede deshacer.
          </span>
          <button className="btn-secondary" onClick={() => setPorBorrar(null)}>Cancelar</button>
          <button
            className="btn-primary"
            onClick={async () => {
              const quien = porBorrar.empleado_no;
              setPorBorrar(null);
              await onBorrar(quien);
            }}
          >
            Sí, dar de baja
          </button>
        </p>
      )}

      {abierto && (
        <ModalEmpleado
          empleado={editando}
          existentes={llaves}
          enUsoPorOtro={numerosDeAparato}
          onGuardar={onGuardar}
          onCerrar={() => setAbierto(false)}
          parametros={parametros}
        />
      )}
    </section>
  );
}
