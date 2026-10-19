/**
 * Siembra de los clientes de demostración en la cartera del despacho. (R-06 → P0-01)
 *
 * **Sólo para cuentas de desarrollo**: quién ve el botón lo decide la pantalla
 * (`esCuentaDeDesarrollo`). Escribe salarios de terceros, y eso no tiene por qué acabar
 * en la cuenta de nadie que no lo haya pedido.
 *
 * VA POR LAS MISMAS RUTAS QUE EL ALTA A MANO
 * ------------------------------------------
 * No hay un endpoint de "sembrar" en el backend, y es deliberado: uno que copiara
 * salarios de terceros a la cuenta de quien llame sería la escalada que R-06 cerró. Lo
 * que hace esto es leer el catálogo público de demostración y darlo de alta cliente por
 * cliente con los mismos `PUT` que usa la pantalla, así que pasa por la misma
 * validación y por la misma tenencia.
 */

import { apiFetch } from './api';
import { obtenerCliente, obtenerClientes, type ClienteResumen } from './despachoApi';
import { obtenerEmpleadosSemilla, type ClienteCartera } from './carteraApi';

/** El catálogo del backend, en la forma de la cartera. */
export async function carteraDelCatalogo(): Promise<ClienteCartera[]> {
  const resumenes = await obtenerClientes();
  return Promise.all(
    resumenes.map(async (r: ClienteResumen) => {
      const [ficha, empleados] = await Promise.all([
        obtenerCliente(r.id),
        obtenerEmpleadosSemilla(r.id),
      ]);
      return {
        id: r.id,
        nombre: r.nombre,
        giro: r.giro,
        origen: r.origen,
        prima_riesgo: r.prima_riesgo,
        clase_riesgo: r.clase_riesgo,
        clave_periodicidad: r.clave_periodicidad,
        zona: r.zona,
        periodo_sugerido: ficha.periodo_sugerido,
        empleados: empleados.empleados,
      };
    }),
  );
}

/**
 * Copia los clientes de demostración a la cartera. **Idempotente**: si ya hay
 * clientes no hace nada y devuelve `false`, para no pisar lo que el contador editó.
 */
export async function sembrarDemo(): Promise<boolean> {
  const { clientes } = await apiFetch<{ clientes?: unknown[] }>('/cartera/clientes');
  if ((clientes ?? []).length > 0) return false;

  for (const cliente of await carteraDelCatalogo()) {
    const { empleados, ...datos } = cliente;
    const base = `/cartera/clientes/${encodeURIComponent(cliente.id)}`;
    await apiFetch(base, { method: 'PUT', json: datos });
    for (const e of empleados) {
      await apiFetch(`${base}/empleados/${encodeURIComponent(e.empleado_no)}`, {
        method: 'PUT',
        json: e,
      });
    }
  }
  return true;
}
