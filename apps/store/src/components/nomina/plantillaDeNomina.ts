/**
 * Quién entra a la nómina de un cliente (G-01, G-02).
 *
 * Vive suelto y no dentro de `useNominaCliente` porque **decide los dos
 * criterios de la épica** —que un alta nueva aparezca en el cálculo y que un
 * empleado sin llave de checador no— y eso tiene consecuencia fiscal: al
 * contador le falta gente en la nómina. Una decisión así se prueba directo, sin
 * montar un árbol de React con cinco proveedores para llegar a ella.
 */

import { estaVinculado, type EmpleadoCartera } from '../../services/carteraApi';
import type { EmpleadoCliente } from '../../services/despachoApi';
import type { EmpleadoNominaRequest } from '../../services/nominaDemoApi';

/** Los cinco campos que `POST /nomina/calcular-periodo` espera. */
function aRequest(e: EmpleadoCartera | EmpleadoCliente): EmpleadoNominaRequest {
  return {
    empleado_no: e.empleado_no,
    nombre: e.nombre,
    salario_diario: e.salario_diario,
    salario_diario_integrado: e.salario_diario_integrado,
    zona: e.zona,
  };
}

/**
 * La plantilla que se manda al backend.
 *
 * @param deLaFicha  Empleados de `GET /despacho/clientes/{id}` (catálogo de demo).
 * @param deLaCartera Empleados de la cartera del uid, o `null` si todavía no
 *   llegó. **`null` no es lo mismo que `[]`**: con la cartera cargando hay que
 *   usar la ficha, no dejar al contador con una nómina de cero empleados.
 *
 * **Sólo entran los VINCULADOS.** Sin `employee_no` no hay checadas que
 * atribuirle, y mandarlo con la llave en blanco haría que dos empleados sin
 * vincular colisionaran en el dedupe del almacén de checadas: uno se comería
 * las incidencias del otro. Quedar fuera **no es quedar en silencio** — el
 * conteo se pinta en la ficha, en la pantalla de nómina y en el PDF.
 *
 * Se construye la forma del REQUEST y no un `EmpleadoCliente` completo: rellenar
 * `factor: '0'` y `factor_implicito: false` para satisfacer aquel tipo serían
 * afirmaciones falsas sobre números que no existen, viajando con el tipo que la
 * tabla Plantilla y el PDF consumen.
 */
export function plantillaDeNomina(
  deLaFicha: EmpleadoCliente[],
  deLaCartera: EmpleadoCartera[] | null,
): EmpleadoNominaRequest[] {
  if (deLaCartera) return deLaCartera.filter(estaVinculado).map(aRequest);
  return deLaFicha.map(aRequest);
}
