/**
 * Dispositivos biométricos del cliente activo. (R-04, R-05)
 *
 * Restaura lo que G-02 recortó. Opera sobre el **cliente activo** del selector
 * superior, con el mismo patrón que `/app/nomina`: sin cliente, la pantalla lo
 * pide en vez de caer en un default silencioso — un default aquí haría que el
 * header afirmara un cliente y la pantalla enseñara los aparatos de otro.
 *
 * LO QUE ESTA PANTALLA NO AFIRMA, Y POR QUÉ
 * ------------------------------------------
 * No dice cuántas checadas mandó cada aparato, porque **no se puede saber**:
 * `EventoChecada` no identifica el dispositivo (`serial_no` es el consecutivo
 * del evento, no la serie del equipo). Lo que sí hace es cruzar contra el
 * endpoint **real** del adaptador —`GET /api/v1/asistencia/eventos`— para decir
 * **quién está checando y quién no**, que es la pregunta que el contador tiene
 * de verdad. La limitación se dice en pantalla en vez de dejar que el lector
 * suponga.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import { AlertTriangle, Fingerprint, Loader, Pencil, Plus, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCartera } from '../context/carteraStore';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
  cruzarEnrolamiento,
  sinAparato,
  type DispositivoChecador,
} from '../services/dispositivosApi';
import {
  borrarDispositivo,
  guardarDispositivo,
  listarDispositivos,
} from '../services/dispositivosFirestore';
import { obtenerEventos } from '../services/nominaDemoApi';
import ModalDispositivo from '../components/dispositivos/ModalDispositivo';
import ErrorAlert from '../components/common/ErrorAlert';
import SinClienteActivo from '../components/common/SinClienteActivo';

/** Aviso con el mismo aspecto que los de `EmpleadosTab`. */
function Aviso({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      style={{
        margin: 0, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
        borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm) var(--space-md)',
        fontSize: '0.88rem', color: 'var(--text-primary)',
      }}
    >
      {children}
    </p>
  );
}

export default function DispositivosPage() {
  const { user } = useAuth();
  const { clienteId, cliente, loading: cargandoCliente } = useClienteActivo();
  const cartera = useCartera();

  /**
   * La carga guarda **para qué cliente** se hizo, y todo lo demás se DERIVA de
   * compararlo con el actual. Es el patrón de `ClienteDetallePage`
   * (`resultado.id === id`) y de `CarteraContext`, y existe por dos razones:
   * evita llamar a `setState` sincrónicamente dentro del efecto —que dispara
   * renders en cascada y que la regla `react-hooks/set-state-in-effect`
   * prohíbe— y, de paso, impide que una respuesta lenta del cliente anterior se
   * pinte sobre la pantalla del nuevo.
   */
  const [carga, setCarga] = useState<{
    para: string | null;
    dispositivos: DispositivoChecador[];
    error: string | null;
  } | null>(null);
  const [editando, setEditando] = useState<DispositivoChecador | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [porBorrar, setPorBorrar] = useState<DispositivoChecador | null>(null);
  /** `employee_no` con al menos una checada en el almacén del backend. */
  const [checando, setChecando] = useState<Set<string>>(new Set());
  const [intento, setIntento] = useState(0);

  const uid = user?.uid ?? null;
  const empleados = useMemo(
    () => (clienteId ? cartera.clientePorId(clienteId)?.empleados ?? [] : []),
    [cartera, clienteId],
  );

  useEffect(() => {
    if (!uid || !clienteId) return;
    let cancelado = false;
    listarDispositivos(uid, clienteId)
      .then((d) => {
        if (!cancelado) setCarga({ para: clienteId, dispositivos: d, error: null });
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        setCarga({
          para: clienteId,
          dispositivos: [],
          error: e instanceof Error ? e.message : 'No se pudieron cargar los dispositivos',
        });
      });
    return () => { cancelado = true; };
  }, [uid, clienteId, intento]);

  // Quién está checando, del endpoint REAL del adaptador. Que falle no rompe la
  // pantalla: se pierde el cruce, no la administración de aparatos.
  useEffect(() => {
    if (!clienteId) return;
    let cancelado = false;
    obtenerEventos(clienteId)
      .then((r) => {
        if (!cancelado) setChecando(new Set(r.eventos.map((e) => e.empleado_no)));
      })
      .catch(() => { if (!cancelado) setChecando(new Set()); });
    return () => { cancelado = true; };
  }, [clienteId, intento]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  const guardar = useCallback(
    async (d: DispositivoChecador) => {
      if (!uid || !clienteId) throw new Error('Hace falta una sesión y un cliente activo.');
      await guardarDispositivo(uid, clienteId, d);
      recargar();
    },
    [uid, clienteId, recargar],
  );

  if (!cargandoCliente && !clienteId) {
    return (
      <SinClienteActivo
        titulo="Dispositivos"
        explicacion="Los dispositivos son de un cliente: cada despacho lleva los aparatos de cada uno por separado."
      />
    );
  }

  // Derivados: `alDia` es falso mientras lo cargado no sea de ESTE cliente, así
  // que cambiar de cliente vacía la pantalla sola en vez de enseñar lo anterior.
  const alDia = carga !== null && carga.para === clienteId;
  const dispositivos = alDia ? carga.dispositivos : null;
  const error = alDia ? carga.error : null;
  const lista = dispositivos ?? [];
  /**
   * **No se acusa a nadie mientras los aparatos cargan.**
   *
   * Con `dispositivos` todavía en `null`, `lista` es `[]` y `sinAparato`
   * devolvería a **todos** los vinculados: la pantalla abría gritando que la
   * plantilla entera está sin enrolar, y un segundo después se desdecía. Un
   * aviso que aparece y desaparece solo es peor que no tenerlo — enseña a
   * ignorarlo, y este en concreto es el que anuncia una nómina con faltas de
   * todos. Lo destapó un test que esperaba el aviso correcto y encontró éste.
   */
  const huerfanos = dispositivos === null ? [] : sinAparato(empleados, lista);

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Dispositivos</h1>
        <p>
          Los checadores de <strong>{cliente?.nombre ?? clienteId}</strong> y quién está
          enrolado en cada uno.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}

      {!cartera.soloLectura && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          <button
            className="btn-primary"
            onClick={() => { setEditando(null); setAbierto(true); }}
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}
          >
            <Plus size={16} /> Nuevo dispositivo
          </button>
        </div>
      )}

      {/* El tercer lado del triángulo de G-02: tienen llave de checador, así que
          entran al cálculo, pero no están en ningún aparato — no van a producir
          una sola checada y saldrán con falta en todos los días laborables. */}
      {huerfanos.length > 0 && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          <Aviso>
            <strong>
              {huerfanos.length}{' '}
              {huerfanos.length === 1
                ? 'empleado tiene número de checador y no está en ningún aparato'
                : 'empleados tienen número de checador y no están en ningún aparato'}
              :
            </strong>{' '}
            {huerfanos.map((e) => e.nombre).join(', ')}. Entran al cálculo de nómina, pero si
            nadie los enroló no van a checar nunca y saldrán con <strong>falta en todos los
            días laborables</strong> — una nómina completa y creíble, con menos días pagados.
          </Aviso>
        </div>
      )}

      {dispositivos === null && !error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', padding: '24px 0' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando los dispositivos...
        </div>
      )}

      {dispositivos !== null && lista.length === 0 && (
        <div className="card" style={{ padding: 'var(--space-2xl) var(--space-lg)', textAlign: 'center' }}>
          <Fingerprint size={24} color="var(--text-muted)" />
          <div style={{ fontSize: '1.05rem', fontWeight: 600, margin: '12px 0 8px' }}>
            Este cliente no tiene dispositivos registrados
          </div>
          <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)' }}>
            Da de alta el checador para llevar el control de quién está enrolado en él.
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gap: 'var(--space-md)' }}>
        {lista.map((d) => {
          const { enrolados, fantasmas } = cruzarEnrolamiento(d, empleados);
          return (
            <div key={d.id} className="card" style={{ padding: 'var(--space-lg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '1rem' }}>{d.nombre}</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {[d.marca, d.modelo].filter(Boolean).join(' ') || 'Sin modelo'}
                    {d.ip && (
                      <>
                        {' · '}
                        <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {d.ip}:{d.puerto}
                        </span>
                      </>
                    )}
                    {d.serial && <> · serie {d.serial}</>}
                  </div>
                </div>
                {!cartera.soloLectura && (
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      aria-label={`Editar ${d.nombre}`}
                      onClick={() => { setEditando(d); setAbierto(true); }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      aria-label={`Dar de baja ${d.nombre}`}
                      onClick={() => setPorBorrar(d)}
                      style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>

              <div style={{ marginTop: 'var(--space-md)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                  Enrolados · {enrolados.length}
                </div>
                {enrolados.length === 0 && (
                  <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Nadie enrolado todavía. Edítalo para marcar quién está dado de alta en el aparato.
                  </p>
                )}
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
                  {enrolados.map((e) => (
                    <li
                      key={e.empleado_no}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem',
                        border: '1px solid var(--border)', borderRadius: 'var(--radius-full)',
                        padding: '3px 10px',
                      }}
                    >
                      <span>{e.nombre}</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-muted)' }}>
                        #{e.employee_no}
                      </span>
                      {/* Del endpoint real del adaptador, no de la cartera. */}
                      {!checando.has(e.employee_no as string) && (
                        <span style={{ color: 'var(--warning)', fontSize: '0.72rem' }}>sin checadas</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>

              {fantasmas.length > 0 && (
                <div style={{ marginTop: 'var(--space-md)' }}>
                  <Aviso>
                    <AlertTriangle size={14} color="var(--warning)" style={{ verticalAlign: 'middle' }} />{' '}
                    <strong>
                      {fantasmas.length === 1
                        ? 'Un número enrolado en este aparato no está en la cartera'
                        : `${fantasmas.length} números enrolados en este aparato no están en la cartera`}
                      :
                    </strong>{' '}
                    <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {fantasmas.join(', ')}
                    </span>
                    . Sus checadas van a llegar y <strong>no habrá a quién atribuirlas</strong>:
                    es de donde salen los "empleados desconocidos" al cerrar el periodo.
                  </Aviso>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {lista.length > 0 && (
        <p style={{ marginTop: 'var(--space-lg)', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          <strong>Lo que esta pantalla no puede decir:</strong> cuántas checadas mandó cada
          aparato. Las checadas que llegan no traen la identidad del dispositivo que las
          produjo, así que "sin checadas" significa que esa persona no ha checado{' '}
          <em>en ningún aparato</em> de este cliente, no que este equipo esté apagado.
        </p>
      )}

      {porBorrar && (
        <div style={{ marginTop: 'var(--space-md)' }}>
          <Aviso>
            ¿Dar de baja <strong>{porBorrar.nombre}</strong>? Se pierde el registro de quién
            estaba enrolado en él. No borra a nadie de la cartera ni del aparato físico.{' '}
            <button className="btn-secondary" onClick={() => setPorBorrar(null)}>Cancelar</button>{' '}
            <button
              className="btn-primary"
              onClick={async () => {
                const quien = porBorrar;
                setPorBorrar(null);
                if (uid && clienteId) {
                  await borrarDispositivo(uid, clienteId, quien.id);
                  recargar();
                }
              }}
            >
              Sí, dar de baja
            </button>
          </Aviso>
        </div>
      )}

      {abierto && (
        <ModalDispositivo
          dispositivo={editando}
          empleados={empleados}
          serialesEnUso={lista
            .filter((d) => d.id !== editando?.id)
            .map((d) => d.serial)
            .filter(Boolean)}
          onGuardar={guardar}
          onCerrar={() => setAbierto(false)}
        />
      )}
    </div>
  );
}
