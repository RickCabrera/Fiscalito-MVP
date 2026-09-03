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
import { modoEmpresaUnica } from '../services/modoEmpresa';
import { empresaConfigurada } from '../services/empresa';

export default function EmpleadosPage() {
  const { clienteId, cliente, loading } = useClienteActivo();
  const cartera = useCartera();

  const empleados = useMemo(
    () => (clienteId ? cartera.clientePorId(clienteId)?.empleados ?? [] : []),
    [cartera, clienteId],
  );

  /**
   * O-01: sin empresa configurada no hay plantilla que llevar.
   *
   * Va antes que la tabla y no como un aviso encima: dar de alta a alguien aquí
   * lo guardaría bajo una ficha que no existe y **desaparecería en la siguiente
   * lectura** (en Firestore un documento con sólo subcolecciones no aparece al
   * listar). El servicio también lo bloquea; esto es para que el operador vea
   * el camino en vez de un error al guardar.
   */
  if (modoEmpresaUnica() && !loading && !empresaConfigurada(cartera.empresa)) {
    return (
      <SinClienteActivo
        titulo="Empleados"
        explicacion="La plantilla que entra al cálculo de la nómina."
      />
    );
  }

  if (!loading && !clienteId) {
    return (
      <SinClienteActivo
        titulo="Empleados"
        explicacion={
          modoEmpresaUnica()
            ? 'La plantilla que entra al cálculo de la nómina.'
            : 'La plantilla es de un cliente: el despacho lleva la de cada uno por separado.'
        }
      />
    );
  }

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Empleados</h1>
        <p>
          {modoEmpresaUnica() ? (
            <>La plantilla que entra al cálculo de la nómina.</>
          ) : (
            <>
              La plantilla de <strong>{cliente?.nombre ?? clienteId}</strong>, que es la que
              entra al cálculo de su nómina.
            </>
          )}
        </p>
      </div>

      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        <EmpleadosTab
          empleados={empleados}
          soloLectura={cartera.soloLectura}
          onGuardar={(e) => cartera.guardarEmpleado(clienteId as string, e)}
          onBorrar={(no) => cartera.borrarEmpleado(clienteId as string, no)}
          /* O-03: las prestaciones del patrón son el default del alta y su
             escala de vacaciones viaja al SBC. Sin esto, capturarlas en
             Configuración de empresa sería un formulario decorativo. */
          parametros={cartera.empresa.parametros}
        />
      </div>
    </div>
  );
}
