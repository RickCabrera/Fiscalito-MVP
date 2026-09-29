/**
 * Cartera de clientes del despacho (E-02).
 *
 * Reemplaza el stub de E-01. La lista sale de `GET /despacho/clientes`: ni los
 * empleados ni la prima de riesgo se escriben en TypeScript.
 *
 * DEMO — se borra en F2.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FilaCliente from '../components/cartera/FilaCliente';
import ModalCliente from '../components/cartera/ModalCliente';
import { useCartera } from '../context/carteraStore';
import { sinEmpleados, type ClienteCartera } from '../services/carteraApi';
import { Building2, Loader, Plus, RefreshCw } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import { useAuth } from '../context/AuthContext';
import { esCuentaDeDesarrollo } from '../services/entorno';
import ErrorAlert from '../components/common/ErrorAlert';
import { useProfile } from '../context/ProfileContext';
import { motivoDelTope, planDelPerfil, usoDeClientes } from '../services/planes';

export default function ClientesPage() {
  // El cliente ACTIVO sigue saliendo del contexto de E-02 (es lo que lee el
  // selector del header). La LISTA sale de la cartera, que es donde el alta
  // escribe: pintarla desde el backend hacía que un cliente recién capturado
  // no apareciera nunca, sin error y sin mensaje.
  const { clienteId, setClienteId } = useClienteActivo();
  const { user } = useAuth();
  const { profile } = useProfile();
  const cuentaDeDesarrollo = esCuentaDeDesarrollo(user?.email);
  const cartera = useCartera();
  const clientes = cartera.clientes;
  const loading = cartera.loading;
  // El error y el reintento son de la CARTERA, que es lo que se pinta. Colgarlos
  // del cliente activo dejaba `cartera.error` sin renderizar en ningún lado y
  // hacía que un fallo del proveedor se viera como "la cartera está vacía —
  // revisa que la API esté corriendo", un diagnóstico equivocado.
  //
  // **`cartera.error` es hoy casi inalcanzable, y se dice aquí en vez de que
  // alguien lo descubra leyendo.** `CarteraContext` sólo lo escribe en el
  // `.catch` de `cargarCartera`, y `cargarCartera` tiene garantizado que no
  // rechaza —lo dice su docstring y lo fija un test—. La señal REAL de que algo
  // salió mal es `motivoFallback`, que se pinta arriba. Este bloque queda como
  // red por si el proveedor gana algún día un camino que sí lance.
  const error = cartera.error;
  const recargar = cartera.recargar;
  const [modalAbierto, setModalAbierto] = useState(false);
  const [errorSembrar, setErrorSembrar] = useState<string | null>(null);
  const [sembrando, setSembrando] = useState(false);
  const [editando, setEditando] = useState<Omit<ClienteCartera, 'empleados'> | null>(null);
  const navigate = useNavigate();

  // T8: el tope del plan. Es la ÚNICA parte del plan con consecuencia — ver
  // `services/planes.ts`—, y se calcula contra la cartera ya cargada: mientras
  // `loading` es `true` la lista está vacía y el uso diría "0 / 25".
  const plan = planDelPerfil(profile.plan);
  const uso = usoDeClientes(plan, clientes.length);
  // Sin cartera cargada no se bloquea nada: un tope calculado sobre una lista
  // que todavía no llega apagaría el botón en cada arranque.
  const alTope = !loading && !error && uso.alLimite;

  const abrir = (id: string) => {
    setClienteId(id);
    navigate(`/app/clientes/${id}`);
  };

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Clientes</h1>
        <p>La cartera del despacho. Elige uno para ver su plantilla y calcular su nómina.</p>
      </div>

      {/* R-06: la siembra es SÓLO para cuentas de desarrollo. Una cuenta de
          producción no tiene por qué poder copiarse a sí misma el salario de
          los trabajadores de un tercero, y el del caso real es dinero real de
          alguien. */}
      {cuentaDeDesarrollo && !cartera.soloLectura && clientes.length === 0 && !loading && (
        <div
          style={{
            marginBottom: 'var(--space-md)', background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)', fontSize: '0.86rem',
          }}
        >
          <div>
            Cuenta de desarrollo: puedes copiar los tres clientes de demostración a tu
            cartera para probar el flujo completo.
          </div>
          <button
            className="btn-primary"
            style={{ marginTop: 'var(--space-sm)' }}
            disabled={sembrando}
            onClick={() => {
              setSembrando(true);
              setErrorSembrar(null);
              cartera
                .sembrar()
                .catch((e: unknown) =>
                  setErrorSembrar(e instanceof Error ? e.message : 'No se pudo guardar la cartera'),
                )
                .finally(() => setSembrando(false));
            }}
          >
            {sembrando ? 'Guardando…' : 'Cargar clientes de demostración'}
          </button>
          {errorSembrar && (
            <div role="alert" style={{ marginTop: 'var(--space-xs)', color: 'var(--danger)' }}>
              {errorSembrar}
            </div>
          )}
        </div>
      )}

      {!cartera.soloLectura && (
        <div style={{ marginBottom: 'var(--space-md)', display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            onClick={() => { setEditando(null); setModalAbierto(true); }}
            disabled={alTope}
            title={alTope ? motivoDelTope(plan) : undefined}
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center', opacity: alTope ? 0.6 : 1 }}
          >
            <Plus size={16} /> Nuevo cliente
          </button>
          {/* T8: el uso va JUNTO al botón, no en el encabezado. Es el dato que
              explica por qué el botón está apagado, y separarlo del botón deja
              al contador buscando el motivo. */}
          {!loading && !error && (
            <span
              style={{
                fontSize: '0.8rem', fontFamily: "'JetBrains Mono', monospace",
                color: alTope ? 'var(--warning)' : 'var(--text-muted)',
              }}
            >
              {uso.texto} · plan {plan.nombre}
            </span>
          )}
        </div>
      )}

      {/* El motivo se ESCRIBE, no sólo se pone en un `title`: un botón
          deshabilitado no recibe hover en táctil, y el contador se quedaría sin
          saber por qué no puede dar de alta. */}
      {!cartera.soloLectura && alTope && (
        <div
          role="status"
          style={{
            marginBottom: 'var(--space-md)', background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)', fontSize: '0.86rem',
            display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap',
          }}
        >
          <span>{motivoDelTope(plan)}</span>
          <Link to="/app/planes" style={{ fontWeight: 600 }}>Ver planes</Link>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start' }}>
          <ErrorAlert message={error} />
          <button
            onClick={recargar}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', background: 'transparent',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)', fontSize: '0.83rem', cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', padding: '32px 0' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando la cartera...
        </div>
      )}

      {/* R-06: una cartera vacía NO es un error, y decirle al contador que
          "revise que la API esté corriendo" cuando lo único que pasa es que
          acaba de crear su cuenta era un diagnóstico equivocado que además no
          ofrecía salida. Ahora dice lo que hay y da el botón. */}
      {!loading && !error && clientes.length === 0 && (
        <div className="card" style={{ padding: 'var(--space-2xl) var(--space-lg)', textAlign: 'center' }}>
          <Building2 size={24} color="var(--text-muted)" />
          <div style={{ fontSize: '1.05rem', fontWeight: 600, margin: '12px 0 8px' }}>
            Aún no tienes clientes
          </div>
          <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>
            Da de alta el primero para empezar a llevarle la nómina.
          </p>
          <button
            className="btn-primary"
            onClick={() => { setEditando(null); setModalAbierto(true); }}
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}
          >
            <Plus size={16} /> Crear el primer cliente
          </button>
        </div>
      )}

      <div className="animate-in" style={{ animationDelay: '0.1s', display: 'grid', gap: 'var(--space-sm)' }}>
        {clientes.map((c) => (
          <FilaCliente
            key={c.id}
            cliente={c}
            activo={c.id === clienteId}
            editable={!cartera.soloLectura}
            onAbrir={() => abrir(c.id)}
            onEditar={() => { setEditando(sinEmpleados(c)); setModalAbierto(true); }}
          />
        ))}
      </div>

      {modalAbierto && (
        <ModalCliente
          cliente={editando}
          idsExistentes={cartera.clientes.map((c) => c.id)}
          onGuardar={cartera.guardarCliente}
          onCerrar={() => setModalAbierto(false)}
        />
      )}
    </div>
  );
}
