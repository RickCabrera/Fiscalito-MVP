/**
 * Pestaña Plantilla de la ficha: el histórico de referencia del caso real (R-06, sólo
 * cuentas de desarrollo). Salió de `ClienteDetallePage` en P4 por el tope de 300 líneas.
 *
 * POR QUÉ EL FACTOR SE ETIQUETA DISTINTO SEGÚN EL CLIENTE: en el caso real el factor es
 * un cociente observado (SBC ÷ salario diario) que puede incluir prestaciones superiores
 * que el CFDI no desglosa (§D9); no es comparable con el factor mínimo del Art. 27 LSS.
 */

import { Info, Loader } from 'lucide-react';
import type { ClienteDetalle } from '../../services/despachoApi';
import { envoltura, fila, tabla, td, tdNum, th, thNum } from '../nomina/estilosTabla';

/**
 * Estado vacío de la pestaña Plantilla: un título y una explicación de QUÉ VA
 * AHÍ.
 *
 * Los tres casos sin tabla —404, error del API y ficha con cero empleados— se
 * pintan con esta misma forma para que se lean como el mismo tipo de mensaje y
 * no como tres accidentes distintos. Va aquí y no en `components/common/`
 * porque hoy lo usa una sola pantalla; el día que lo pida una segunda, se mueve.
 */
function EstadoVacio({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
      <Info size={18} style={{ flexShrink: 0, marginTop: 2, color: 'var(--text-muted)' }} />
      <div>
        <div style={{ fontSize: '0.92rem', fontWeight: 600, marginBottom: 6 }}>{titulo}</div>
        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {children}
        </p>
      </div>
    </div>
  );
}

export default function PlantillaReferencia({
  cliente,
  nombre,
  fichaPendiente,
  fichaNoExiste,
}: {
  cliente: ClienteDetalle | null;
  nombre: string;
  fichaPendiente: boolean;
  fichaNoExiste: boolean;
}) {
  const cabecera = { nombre };
  const hayFactorImplicito = cliente?.empleados.some((e) => e.factor_implicito) ?? false;
  return (
    <>
    {fichaPendiente && (
      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando la plantilla...
        </div>
      </div>
    )}

    {fichaNoExiste && (
      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        {/* UN SOLO MENSAJE, Y NO ES PEREZA. El primer intento partía
            esto en dos —"lo diste de alta tú" contra "el API no
            respondió"— y no hay con qué: `obtenerCliente` convierte
            TODA respuesta no-ok en un `Error` con un texto, el 404 de
            la ficha incluido (`despachoApi.ts:leer`), así que el
            código de estado no sobrevive al viaje y las dos causas
            llegan aquí idénticas. Separarlas de verdad es cambiar el
            cliente REST para que conserve el status; adivinarlas por el
            texto del mensaje es peor que no distinguirlas. Mientras
            tanto la frase nombra las dos posibilidades en vez de
            afirmar la que no consta. */}
        <EstadoVacio titulo="Sin plantilla de referencia">
          Aquí va la plantilla <strong>de referencia</strong>: salario diario, SBC, factor
          de integración y antigüedad reconstruidos de un CFDI de nómina ya timbrado, para
          contrastar contra ellos lo que calcula la app. Sólo la tienen los clientes del
          catálogo de demostración, y la de éste no llegó: lo normal es que{' '}
          <strong>lo diste de alta tú</strong>, y si no, que el servicio de nómina no haya
          respondido. Su plantilla de trabajo es la de la pestaña{' '}
          <strong>Empleados</strong>, que además es la editable y la que alimenta el
          cálculo.
        </EstadoVacio>
      </div>
    )}

    {cliente && cliente.empleados.length === 0 && (
      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        {/* La ficha llegó y trae CERO empleados. Sin esto se pintaba la
            tabla con sus ocho encabezados y ni una fila debajo, más el
            pie de página hablando de factores y antigüedades que no
            existían: una pantalla que parece rota y no dice nada. */}
        <EstadoVacio titulo="La ficha no trae empleados">
          El servicio de nómina conoce a <strong>{cabecera.nombre}</strong> pero su
          plantilla de referencia viene vacía: no hay CFDI timbrado del que reconstruir
          salarios ni SBC. Captura su gente en la pestaña <strong>Empleados</strong> —es
          la que alimenta el cálculo de la nómina— y esta pestaña seguirá siendo sólo el
          histórico con el que se contrasta.
        </EstadoVacio>
      </div>
    )}

    {cliente && cliente.empleados.length > 0 && (
    <>
    <div className="card" style={{ padding: 'var(--space-lg)' }}>
      <div style={envoltura}>
        <table style={tabla(760)}>
        <thead>
          <tr>
            <th style={th}>No.</th>
            <th style={th}>Nombre</th>
            <th style={th}>Puesto</th>
            <th style={thNum}>Salario diario</th>
            <th style={thNum}>SBC</th>
            <th style={thNum}>Factor</th>
            <th style={th}>Alta</th>
            <th style={thNum}>Antigüedad</th>
          </tr>
        </thead>
        <tbody>
          {cliente.empleados.map((e, i) => (
            <tr key={e.empleado_no} style={fila(i)}>
              <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace" }}>{e.empleado_no}</td>
              <td style={td}>{e.nombre}</td>
              <td style={{ ...td, color: 'var(--text-secondary)' }}>{e.puesto || '—'}</td>
              <td style={tdNum}>{e.salario_diario}</td>
              <td style={tdNum}>{e.salario_diario_integrado}</td>
              <td style={tdNum}>
                {e.factor}
                {e.factor_implicito && (
                  <span
                    title="Cociente observado (SBC ÷ salario diario), no el factor de ley: puede incluir prestaciones superiores que el CFDI no desglosa."
                    style={{ color: 'var(--warning)', marginLeft: 4, cursor: 'help' }}
                  >
                    *
                  </span>
                )}
              </td>
              <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace" }}>
                {e.fecha_alta ?? '—'}
              </td>
              <td style={tdNum}>
                {e.antiguedad_anios === null ? '—' : `${e.antiguedad_anios} años`}
              </td>
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </div>

    <div
      style={{
        display: 'flex', alignItems: 'flex-start',
        gap: 'var(--space-xs)', marginTop: 'var(--space-sm)',
        fontSize: '0.78rem', color: 'var(--text-muted)',
      }}
    >
      <Info size={14} style={{ flexShrink: 0, marginTop: 2 }} />
      <span>
        {hayFactorImplicito ? (
          <>
            <strong style={{ color: 'var(--warning)' }}>*</strong> El factor marcado es un{' '}
            <strong>cociente observado</strong> (SBC ÷ salario diario), no el factor de ley
            del Art. 27 LSS: puede incluir prestaciones superiores que el CFDI no desglosa,
            y por eso este cliente no muestra alta ni antigüedad — el comprobante timbrado
            no las trae y no se inventan.
          </>
        ) : (
          <>
            Antigüedad y factor medidos al <strong>{cliente.fecha_referencia}</strong>, no a
            hoy: así el SBC de un cliente de demostración no cambia solo al cruzar un
            aniversario.
          </>
        )}
      </span>
    </div>
    </>
    )}
    </>
  );
}
