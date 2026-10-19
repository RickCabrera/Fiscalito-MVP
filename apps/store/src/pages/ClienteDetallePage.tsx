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
import CredencialesCliente from '../components/cartera/CredencialesCliente';
// P1-05: opinión de cumplimiento, constancia y riesgos 69-B.
import CumplimientoCliente from '../components/cartera/CumplimientoCliente';
import AlertasCliente from '../components/alertas/AlertasCliente';
import DatosFiscalesFicha from '../components/cartera/DatosFiscalesFicha';
import EmpleadosTab from '../components/cartera/EmpleadosTab';
import PlantillaReferencia from '../components/cartera/PlantillaReferencia';
// P4: criterios de nómina del cliente (DP-3).
import CriteriosNominaCliente from '../components/cartera/CriteriosNominaCliente';
// P0-04: procesos en segundo plano del cliente (demo de EstadoTrabajos).
import ProcesosCliente from '../components/cartera/ProcesosCliente';
import { useCartera } from '../context/carteraStore';
import { useAuth } from '../context/AuthContext';
import { esCuentaDeDesarrollo } from '../services/entorno';
import { ArrowLeft, Loader } from 'lucide-react';
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
 * cartera del uid.
 *
 * R-06: el tab **Plantilla** —el histórico del caso real, construido de un CFDI
 * timbrado con montos reales anonimizados— **sólo se pinta en cuentas de
 * desarrollo**, y el default pasa a Empleados. En G-01 el default era Plantilla
 * a propósito, para no mover el guion de la demo la mañana de la demo; esa
 * demo ya pasó.
 *
 * **Las fixtures y sus tests no se tocan.** Se oculta una pestaña de la UI: el
 * caso real sigue siendo la verificación del motor contra la realidad y es lo
 * único que demuestra que los números cuadran al centavo.
 */
type Vista = 'empleados' | 'plantilla';

export default function ClienteDetallePage() {
  const { id } = useParams();
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const { user } = useAuth();
  const verPlantilla = esCuentaDeDesarrollo(user?.email);
  // R-06: una cuenta de producción aterriza en SU plantilla editable, no en el
  // histórico de un tercero.
  const [vista, setVista] = useState<Vista>(verPlantilla ? 'plantilla' : 'empleados');
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

  // Los empleados EDITABLES salen de la cartera, no de la ficha del backend.
  const deLaCartera = id ? cartera.clientePorId(id) : null;
  const empleadosCartera = deLaCartera?.empleados ?? [];

  const alDia = resultado !== null && resultado.id === id;
  const cliente = alDia ? resultado.cliente ?? null : null;

  /**
   * **Son TRES estados, no dos.** La ficha del backend puede haber llegado,
   * haber dado 404, o no haber llegado todavía. Confundir el tercero con el
   * segundo hacía que la ficha de un cliente de DEMOSTRACIÓN abriera diciendo
   * "este cliente lo diste de alta tú" durante toda la ventana del fetch —en
   * una demo con red lenta, segundos en pantalla—, porque la cartera ya lo
   * tenía y `loading` era `false`.
   */
  const fichaPendiente = !alDia;
  const fichaNoExiste = alDia && cliente === null;

  /**
   * La cabecera se pinta con la ficha del backend cuando existe, y si no con la
   * de la cartera. **Un cliente dado de alta por el contador no tiene ficha en
   * el backend** —`GET /despacho/clientes/{id}` sólo conoce los tres de
   * demostración—, y dejar que ese 404 apagara la pantalla habría dejado la
   * mitad de G-03 en un callejón: se puede capturar un cliente y no se puede
   * abrir.
   */
  const cabecera = cliente ?? deLaCartera;

  // El error sólo sobrevive si el cliente TAMPOCO está en la cartera.
  const error = fichaNoExiste && !deLaCartera ? resultado.error ?? null : null;
  const loading = fichaPendiente && !deLaCartera;

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

      {cabecera && (
        <>
          <div className="page-header animate-in">
            <h1>{cabecera.nombre}</h1>
            <p>{cabecera.giro} · {etiquetaOrigen(cabecera.origen)}</p>
          </div>

          <div
            className="card animate-in"
            style={{
              animationDelay: '0.05s', marginBottom: 'var(--space-lg)',
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 20,
            }}
          >
            {/* `??` y no `||`: con la cartera diciendo 0 empleados y el backend
                diciendo 2, el `||` pintaba 2 — trataba un cero legítimo como
                ausencia de dato. */}
            <Dato
              etiqueta="Empleados"
              valor={String(deLaCartera ? empleadosCartera.length : cliente?.num_empleados ?? 0)}
              mono
            />
            <Dato etiqueta="Prima de RT" valor={primaComoPorcentaje(cabecera.prima_riesgo)} mono />
            <Dato
              etiqueta="Clase de riesgo"
              // "No aplica" sería falso: todo patrón tiene clase. Lo que no
              // aplica es haber DEDUCIDO su prima de una clase.
              valor={cabecera.clase_riesgo === null ? 'Autodeterminada (Art. 74)' : `${cabecera.clase_riesgo} (supuesta)`}
            />
            <Dato
              etiqueta="Quincena sugerida"
              valor={`${cabecera.periodo_sugerido.inicio} a ${cabecera.periodo_sugerido.fin}`}
              mono
            />
          </div>

          {/* C-01: RFC, CP y entidad, con la edición del cliente. */}
          {deLaCartera && <DatosFiscalesFicha cliente={deLaCartera} />}
          {/* P0-05: e.firma y CSD del cliente, contra la bóveda del backend. */}
          {deLaCartera && <CredencialesCliente clave={deLaCartera.id} />}
          {deLaCartera && (
            <CriteriosNominaCliente
              key={deLaCartera.id}
              cliente={deLaCartera}
              soloLectura={cartera.soloLectura}
              onGuardar={cartera.guardarCliente}
            />
          )}

          <div className="animate-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', gap: 'var(--space-xs)', marginBottom: 'var(--space-md)' }}>
              {(verPlantilla
                ? ([['empleados', 'Empleados'], ['plantilla', 'Plantilla']] as const)
                : ([['empleados', 'Empleados']] as const)
              ).map(([v, texto]) => (
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
                <EmpleadosTab
                  empleados={empleadosCartera}
                  ilegibles={deLaCartera?.ilegibles ?? []}
                  soloLectura={cartera.soloLectura}
                  onGuardar={(e) => cartera.guardarEmpleado(id as string, e)}
                  onBorrar={(no) => cartera.borrarEmpleado(id as string, no)}
                />
              </div>
            )}

            {vista === 'plantilla' && (
              <PlantillaReferencia
                cliente={cliente}
                nombre={cabecera.nombre}
                fichaPendiente={fichaPendiente}
                fichaNoExiste={fichaNoExiste}
              />
            )}
          </div>

          {id && <AlertasCliente clave={id} />}
          {id && <CumplimientoCliente clave={id} />}
          {id && <ProcesosCliente cliente={id} />}
        </>
      )}
    </div>
  );
}
