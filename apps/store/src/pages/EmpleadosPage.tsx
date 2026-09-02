/**
 * Empleados del cliente activo. (R-05)
 *
 * Entrada propia del sidebar, al lado de Clientes / Dispositivos / Nómina.
 * Hasta R-05 los empleados sólo se alcanzaban entrando a la ficha del cliente y
 * cambiando de pestaña — dos clics y saber que la pestaña existe.
 *
 * **Reusa `EmpleadosTab`, no lo copia.** La tabla, el aviso de no vinculados, la
 * confirmación de baja y el modal son los mismos objetos que ya usa la ficha:
 * una segunda implementación sería el lugar donde la próxima corrección se
 * aplique una sola vez. Lo único propio de esta pantalla es resolver el cliente
 * activo y poner el encabezado.
 *
 * La pestaña dentro de la ficha **se queda**: Ricardo lo autorizó explícitamente
 * ("las pestañas dentro de la ficha pueden quedarse"), y quitarla movería el
 * camino que la demo tiene ensayado.
 */

import { useMemo } from 'react';
import { useCartera } from '../context/carteraStore';
import { useClienteActivo } from '../context/clienteActivoStore';
import EmpleadosTab from '../components/cartera/EmpleadosTab';
import SinClienteActivo from '../components/common/SinClienteActivo';

export default function EmpleadosPage() {
  const { clienteId, cliente, loading } = useClienteActivo();
  const cartera = useCartera();

  const empleados = useMemo(
    () => (clienteId ? cartera.clientePorId(clienteId)?.empleados ?? [] : []),
    [cartera, clienteId],
  );

  if (!loading && !clienteId) {
    return (
      <SinClienteActivo
        titulo="Empleados"
        explicacion="La plantilla es de un cliente: el despacho lleva la de cada uno por separado."
      />
    );
  }

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Empleados</h1>
        <p>
          La plantilla de <strong>{cliente?.nombre ?? clienteId}</strong>, que es la que entra
          al cálculo de su nómina.
        </p>
      </div>

      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        <EmpleadosTab
          empleados={empleados}
          soloLectura={cartera.soloLectura}
          onGuardar={(e) => cartera.guardarEmpleado(clienteId as string, e)}
          onBorrar={(no) => cartera.borrarEmpleado(clienteId as string, no)}
        />
      </div>
    </div>
  );
}
