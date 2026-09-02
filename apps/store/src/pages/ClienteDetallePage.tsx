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
import EmpleadosTab from '../components/cartera/EmpleadosTab';
import { useCartera } from '../context/carteraStore';
import { ArrowLeft, Info, Loader } from 'lucide-react';
import ErrorAlert from '../components/common/ErrorAlert';
import { envoltura, fila, tabla, td, tdNum, th, thNum } from '../components/nomina/estilosTabla';
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

// E-04: los mismos estilos que las tablas de nómina, para que la ficha y los
// recibos se lean igual. Eran th/td locales escritos en E-02.

/**
 * El resultado se guarda JUNTO CON el id que lo produjo. Así `loading` se
 * deriva —`resultado.id !== id`— en vez de necesitar un `setLoading(true)`
 * síncrono dentro del efecto, y de paso una respuesta que llega tarde para el
 * cliente anterior no puede pintarse sobre la ficha del nuevo.
 */
type Resultado = { id: string; cliente?: ClienteDetalle; error?: string };

/**
 * G-01: la ficha gana un tab de **Empleados**, que es el editable y sale de la
 * cartera del uid. El tab **Plantilla** es la vista de E-02/E-04 y se queda
 * intacta: es el camino probado, y dejarlo alcanzable es lo que hace que la
 * demo siga funcionando aunque el camino de Firestore falle.
 */
type Vista = 'empleados' | 'plantilla';

export default function ClienteDetallePage() {
  const { id } = useParams();
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [vista, setVista] = useState<Vista>('empleados');
  const cartera = useCartera();

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

  // Los empleados EDITABLES salen de la cartera, no de la ficha del backend: si
  // esta pantalla siguiera leyendo `obtenerCliente()`, un alta nueva no
  // aparecería aquí ni en el cálculo, y el criterio de G-01 fallaría callado.
  const deLaCartera = id ? cartera.clientePorId(id) : null;
  const empleadosCartera = deLaCartera?.empleados ?? [];

  return (
    <div className="page-container">
      <Link
        to="/app/clientes"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 'var(--space-lg)' }}
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
              animationDelay: '0.05s', marginBottom: 'var(--space-lg)',
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 20,
            }}
          >
            <Dato etiqueta="Empleados" valor={String(cliente.num_empleados)} mono />
            <Dato etiqueta="Prima de RT" valor={primaComoPorcentaje(cliente.prima_riesgo)} mono />
            <Dato
              etiqueta="Clase de riesgo"
              // "No aplica" sería falso: todo patrón tiene clase. Lo que no
              // aplica es haber DEDUCIDO su prima de una clase.
              valor={cliente.clase_riesgo === null ? 'Autodeterminada (Art. 74)' : `${cliente.clase_riesgo} (supuesta)`}
            />
            <Dato
              etiqueta="Quincena sugerida"
              valor={`${cliente.periodo_sugerido.inicio} a ${cliente.periodo_sugerido.fin}`}
              mono
            />
          </div>

          <div className="animate-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', gap: 'var(--space-xs)', marginBottom: 'var(--space-md)' }}>
              {([['empleados', 'Empleados'], ['plantilla', 'Plantilla']] as const).map(([v, texto]) => (
                <button
                  key={v}
                  onClick={() => setVista(v)}
                  aria-current={vista === v}
                  style={{
                    padding: 'var(--space-xs) var(--space-md)',
                    background: vista === v ? 'var(--accent-active)' : 'transparent',
                    color: vista === v ? 'var(--text-on-accent)' : 'var(--text-secondary)',
                    border: `1px solid ${vista === v ? 'var(--accent-active)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-full)', cursor: 'pointer', fontSize: '0.85rem',
                  }}
                >
                  {texto}
                </button>
              ))}
            </div>

            {vista === 'empleados' && (
              <div className="card" style={{ padding: 'var(--space-lg)' }}>
                {cartera.motivoFallback && (
                  <p style={{ margin: '0 0 var(--space-md)', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                    {cartera.motivoFallback}
                  </p>
                )}
                <EmpleadosTab
                  empleados={empleadosCartera}
                  soloLectura={cartera.soloLectura}
                  onGuardar={(e) => cartera.guardarEmpleado(id as string, e)}
                  onBorrar={(no) => cartera.borrarEmpleado(id as string, no)}
                />
              </div>
            )}

            {vista === 'plantilla' && (
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
          </div>
        </>
      )}
    </div>
  );
}
