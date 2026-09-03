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

import { Fingerprint, Loader, Plus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCartera } from '../context/carteraStore';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
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
import TarjetaDispositivo from '../components/dispositivos/TarjetaDispositivo';
import ErrorAlert from '../components/common/ErrorAlert';
import SinClienteActivo from '../components/common/SinClienteActivo';
import { modoEmpresaUnica } from '../services/modoEmpresa';

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
  /**
   * `employee_no` con al menos una checada en el almacén del backend.
   *
   * **`null` = no se pudo preguntar**, y es una distinción que costó un
   * bloqueo del revisor. Con un `Set` vacío como estado de fallo, una API
   * caída convertía "no pude preguntar" en "no ha checado" —en ámbar, sobre
   * gente que sí está checando— y la ventana de carga hacía parpadear la
   * insignia en todos para desdecirse un segundo después.
   *
   * Es el MISMO defecto que se arregló tres líneas más abajo para `huerfanos`,
   * dejado abierto aquí: un aviso que aparece y desaparece solo enseña a
   * ignorarlo. Sin la respuesta del adaptador no se afirma nada.
   */
  const [cruce, setCruce] = useState<{
    para: string | null;
    checando: Set<string> | null;
  } | null>(null);
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
  // pantalla —se sigue pudiendo administrar aparatos— pero **sí se dice**: el
  // cruce deja de afirmar, no pasa a afirmar el negativo.
  useEffect(() => {
    if (!clienteId) return;
    let cancelado = false;
    obtenerEventos(clienteId)
      .then((r) => {
        if (cancelado) return;
        // El backend llama `empleado_no` a este campo, pero lo que trae es el
        // `employeeNo` del APARATO — la llave que G-02 separó de la del
        // cálculo. Es el único punto del archivo donde los dos nombres se
        // cruzan, y por eso se dice aquí: comparar contra `e.empleado_no` de
        // la cartera sería el defecto fiscal de G-02 reintroducido.
        setCruce({ para: clienteId, checando: new Set(r.eventos.map((e) => e.empleado_no)) });
      })
      .catch(() => {
        if (cancelado) return;
        setCruce({ para: clienteId, checando: null });
      });
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
        explicacion={
          modoEmpresaUnica()
            ? 'Los checadores de la empresa y quién está enrolado en cada uno.'
            : 'Los dispositivos son de un cliente: cada despacho lleva los aparatos de cada uno por separado.'
        }
      />
    );
  }

  // Derivados: `alDia` es falso mientras lo cargado no sea de ESTE cliente, así
  // que cambiar de cliente vacía la pantalla sola en vez de enseñar lo anterior.
  const alDia = carga !== null && carga.para === clienteId;
  const dispositivos = alDia ? carga.dispositivos : null;
  const error = alDia ? carga.error : null;
  /**
   * **El cruce lleva su propia compuerta `para`, y es la TERCERA vez que hace
   * falta la misma idea en este archivo.** Los dos efectos corren en paralelo
   * al cambiar de cliente y Firestore suele contestar antes que la red, así que
   * sin esto las tarjetas del cliente nuevo se pintaban contra el `checando`
   * del **anterior**: ámbar sobre gente que sí está checando, desdiciéndose un
   * segundo después. Cambiar de cliente en el selector superior es literalmente
   * el mecanismo de R-05, así que era el camino más transitado de los tres.
   */
  const cruceAlDia = cruce !== null && cruce.para === clienteId;
  const checando = cruceAlDia ? cruce.checando : null;
  const falloElCruce = cruceAlDia && cruce.checando === null;
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

      {falloElCruce && lista.length > 0 && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          <Aviso>
            No se pudo consultar el checador, así que <strong>esta pantalla no dice quién
            está checando</strong>. Los aparatos y sus enrolados son correctos; lo que falta
            es el cruce contra las checadas recibidas.
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
        {lista.map((d) => (
          <TarjetaDispositivo
            key={d.id}
            dispositivo={d}
            empleados={empleados}
            checando={checando}
            soloLectura={cartera.soloLectura}
            onEditar={() => { setEditando(d); setAbierto(true); }}
            onBorrar={() => setPorBorrar(d)}
            Aviso={Aviso}
          />
        ))}
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
