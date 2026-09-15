/**
 * Selector de cliente activo, en la barra superior (E-02).
 *
 * SÓLO SE MUESTRA EN RUTAS CON ALCANCE DE CLIENTE, y quién entra a esa lista lo
 * decide `rutaTieneAlcanceDeCliente` con una regla que no se ha relajado desde
 * E-02: entra la ruta que **lee** un cliente y le pide sus datos, no la que
 * habla de clientes.
 *
 * Calendario y Perfil siguen fuera. Perfil es del DESPACHO; y Calendario, desde
 * E-07, sí es patronal —§D21 quedó resuelta, y la frase que este bloque traía
 * antes ("muestra sus obligaciones propias y nada patronal") describía la
 * lectura provisional de E-01— pero es el de TODA la cartera: un selector de
 * "cliente activo" sobre una lista que mezcla los tres clientes afirmaría un
 * alcance que la pantalla no tiene.
 *
 * T1 sumó `/app/store/fiscalito/use`, que sí cumple la regla: filtra sus tabs
 * con el régimen del cliente activo, y sin este selector el contador no tendría
 * cómo cambiar de cliente sin salirse de la pantalla.
 *
 * T2 · EL ERROR SE PODÍA VER PERO NO SE PODÍA SALIR DE ÉL
 * -------------------------------------------------------
 * La barra ya distinguía "no hay clientes" de "no se pudo cargar" —eso es de
 * R-06 y sigue igual—, pero el mensaje era una frase muerta: no decía el
 * motivo y no ofrecía reintentar. Y esta barra está en las rutas con alcance
 * de cliente, así que ahí el contador se quedaba sin **ninguna** forma de
 * recuperar la cartera sin recargar la página entera: el botón de reintentar
 * de `ClientesPage` vive en otra pantalla, y llegar a él exige salirse de
 * donde estaba.
 *
 * El motivo va en el `title` y no en el texto a propósito: el detalle que trae
 * `cargarCartera` es de diagnóstico ("La cartera de Firestore tardó más de
 * 2500 ms"), y ponerlo en la barra superior mientras se proyecta en pantalla
 * grande es ruido. Visible al pasar el cursor, y suficiente para copiarlo.
 *
 * DEMO — se borra en F2.
 */

import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Building2, Loader, RefreshCw } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import { rutaTieneAlcanceDeCliente } from '../services/navigation';

export default function SelectorCliente() {
  const { clientes, clienteId, loading, error, setClienteId, recargar } = useClienteActivo();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { id: idDeLaRuta } = useParams();

  if (!rutaTieneAlcanceDeCliente(pathname)) return null;

  // Sin cartera y sin carga en curso no hay nada que seleccionar: es el caso de
  // un contribuyente que entra por URL. Una barra con un selector deshabilitado
  // que dice "Sin clientes" sugiere que el despacho tiene la cartera vacía.
  // El error sí se muestra: una API caída no puede verse igual que no tener
  // clientes.
  if (!loading && !error && clientes.length === 0) return null;

  const cambiar = (nuevo: string) => {
    setClienteId(nuevo);
    // Si se está viendo algo DE un cliente, el selector tiene que mover esa
    // pantalla también: si no, el header diría una cosa y el contenido otra.
    //
    // La ruta se arma desde el patrón, no sustituyendo el id sobre el pathname:
    // un id puede volver a aparecer en la cadena (`/app/clientes/demo/nomina`
    // con un cliente llamado "nomina" es rebuscado, pero un `replace()` ciego
    // sí lo rompería).
    if (idDeLaRuta) {
      const subruta = pathname.endsWith('/nomina') ? '/nomina' : '';
      navigate(`/app/clientes/${nuevo}${subruta}`);
    }
  };

  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 24px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
      }}
    >
      <Building2 size={16} color="var(--text-secondary)" />
      {/* Sin `htmlFor` cuando no hay `<select>` que etiquetar: en la rama de
          error el control no se renderiza y el `for` apuntaría al vacío. */}
      <label
        htmlFor={error ? undefined : 'selector-cliente'}
        style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
      >
        Cliente activo
      </label>
      {error ? (
        <>
          <span role="alert" title={error} style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>
            No se pudo cargar la cartera
          </span>
          {/* Reintentar es sólo volver a leer: `recargar` incrementa el
              contador de intentos de `CarteraProvider` y el efecto de carga
              corre de nuevo. No escribe nada, así que pulsarlo de más es
              inofensivo. */}
          <button
            type="button"
            onClick={recargar}
            title="Volver a cargar la cartera"
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'none', border: 'none', padding: '2px 4px',
              color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.8rem',
            }}
          >
            <RefreshCw size={13} />
            Reintentar
          </button>
        </>
      ) : loading ? (
        <Loader size={14} className="spin" color="var(--text-muted)" />
      ) : (
        <select
          id="selector-cliente"
          className="input-field"
          value={clienteId ?? ''}
          onChange={(e) => cambiar(e.target.value)}
          style={{ width: 'auto', minWidth: 220, padding: '6px 10px', cursor: 'pointer' }}
        >
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre} · {c.num_empleados} empleados
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
