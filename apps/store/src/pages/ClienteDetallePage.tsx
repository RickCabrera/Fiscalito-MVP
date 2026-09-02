/**
 * Ficha de un cliente del despacho (E-02).
 *
 * Enseña la plantilla con la que se va a calcular la nómina: salario diario,
 * SBC, alta y factor. Todo sale de `GET /despacho/clientes/{id}`.
 *
 * POR QUÉ EL FACTOR SE ETIQUETA DISTINTO SEGÚN EL CLIENTE
 * ------------------------------------------------------
 * Para el caso real anonimizado, el factor es un **cociente observado**
 * (SBC ÷ salario diario) que puede incluir prestaciones superiores que el CFDI
 * no desglosa: no es comparable con el factor mínimo del Art. 27 LSS, y §D9
 * documenta que ahí el SBC no se deriva de la antigüedad. Enseñar las dos cosas
 * con la misma etiqueta invitaría a concluir que el motor está mal.
 *
 * DEMO — se borra en F2.
 */

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Info, Loader } from 'lucide-react';
import ErrorAlert from '../components/common/ErrorAlert';
import {
  etiquetaOrigen, obtenerCliente, primaComoPorcentaje,
  type ClienteDetalle,
} from '../services/despachoApi';

function Dato({ etiqueta, valor, mono }: { etiqueta: string; valor: string; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 2 }}>{etiqueta}</div>
      <div
        style={{
          fontSize: '0.95rem', fontWeight: 600,
          fontFamily: mono ? "'JetBrains Mono', monospace" : 'inherit',
        }}
      >
        {valor}
      </div>
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: 'left', padding: '10px 12px', fontSize: '0.75rem',
  color: 'var(--text-secondary)', fontWeight: 600, whiteSpace: 'nowrap',
  borderBottom: '1px solid var(--border)',
};
const td: React.CSSProperties = {
  padding: '10px 12px', fontSize: '0.85rem', borderBottom: '1px solid var(--border)',
};
const tdNum: React.CSSProperties = {
  ...td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace",
};

/**
 * El resultado se guarda JUNTO CON el id que lo produjo. Así `loading` se
 * deriva —`resultado.id !== id`— en vez de necesitar un `setLoading(true)`
 * síncrono dentro del efecto, y de paso una respuesta que llega tarde para el
 * cliente anterior no puede pintarse sobre la ficha del nuevo.
 */
type Resultado = { id: string; cliente?: ClienteDetalle; error?: string };

export default function ClienteDetallePage() {
  const { id } = useParams();
  const [resultado, setResultado] = useState<Resultado | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelado = false;

    obtenerCliente(id)
      .then((c) => { if (!cancelado) setResultado({ id, cliente: c }); })
      .catch((e: unknown) => {
        if (!cancelado) {
          setResultado({
            id,
            error: e instanceof Error ? e.message : 'Error al cargar el cliente',
          });
        }
      });

    return () => { cancelado = true; };
  }, [id]);

  const alDia = resultado !== null && resultado.id === id;
  const cliente = alDia ? resultado.cliente ?? null : null;
  const error = alDia ? resultado.error ?? null : null;
  const loading = !alDia;

  const hayFactorImplicito = cliente?.empleados.some((e) => e.factor_implicito) ?? false;

  return (
    <div className="page-container">
      <Link
        to="/app/clientes"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 24 }}
      >
        <ArrowLeft size={16} /> Clientes
      </Link>

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando el cliente...
        </div>
      )}

      {error && <ErrorAlert message={error} />}

      {cliente && (
        <>
          <div className="page-header animate-in">
            <h1>{cliente.nombre}</h1>
            <p>{cliente.giro} · {etiquetaOrigen(cliente.origen)}</p>
          </div>

          <div
            className="card animate-in"
            style={{
              animationDelay: '0.05s', marginBottom: 24,
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 20,
            }}
          >
            <Dato etiqueta="Empleados" valor={String(cliente.num_empleados)} mono />
            <Dato etiqueta="Prima de RT" valor={primaComoPorcentaje(cliente.prima_riesgo)} mono />
            <Dato
              etiqueta="Clase de riesgo"
              valor={cliente.clase_riesgo === null ? 'No aplica' : `${cliente.clase_riesgo} (supuesta)`}
            />
            <Dato
              etiqueta="Quincena sugerida"
              valor={`${cliente.periodo_sugerido.inicio} a ${cliente.periodo_sugerido.fin}`}
              mono
            />
          </div>

          <div className="animate-in" style={{ animationDelay: '0.1s' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 12 }}>Plantilla</h2>
            <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
                <thead>
                  <tr>
                    <th style={th}>No.</th>
                    <th style={th}>Nombre</th>
                    <th style={th}>Puesto</th>
                    <th style={{ ...th, textAlign: 'right' }}>Salario diario</th>
                    <th style={{ ...th, textAlign: 'right' }}>SBC</th>
                    <th style={{ ...th, textAlign: 'right' }}>Factor</th>
                    <th style={th}>Alta</th>
                    <th style={{ ...th, textAlign: 'right' }}>Antigüedad</th>
                  </tr>
                </thead>
                <tbody>
                  {cliente.empleados.map((e) => (
                    <tr key={e.empleado_no}>
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

            <div
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 12,
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
          </div>
        </>
      )}
    </div>
  );
}
