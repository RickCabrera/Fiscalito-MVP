/**
 * La traducción entre las dos llaves, en el borde del cierre de periodo (G-02).
 *
 * EL PROBLEMA QUE RESUELVE
 * ------------------------
 * `POST /asistencia/cerrar-periodo` casa las checadas por la llave del
 * **CHECADOR**: `asistencia/incidencias.py` compara `evento.empleado_no` —que
 * es el `employeeNoString` que manda el Hikvision— contra la lista que se le
 * pasa, y su docstring lo dice con todas sus letras (*"`empleados`:
 * `employeeNo` de la plantilla del cliente"*).
 *
 * `POST /nomina/calcular-periodo`, en cambio, indexa por la llave del
 * **CÁLCULO** (`empleado_no`), que es la que llevan los recibos.
 *
 * Mientras las dos coincidieron —y coinciden para los 25 empleados de la
 * semilla, porque `routes/despacho.py` les pone `employee_no = empleado_no`—
 * esto no se notaba. En cuanto G-03 permite dar de alta un empleado con un
 * número de aparato distinto del interno, mandar la llave del cálculo al cierre
 * hace que **no se encuentre ni una de sus checadas**: cero días trabajados,
 * falta todo el periodo, menos días pagados, menor base de cuotas IMSS y menor
 * ISR. Y sus checadas reales aparecen en `empleados_desconocidos`, donde el
 * contador las lee como "a este cliente nadie le sembró".
 *
 * Es un error fiscal y silencioso, así que la traducción vive aquí, sola y
 * probada, en vez de inline en el hook.
 */

import { estaVinculado, type EmpleadoCartera } from '../../services/carteraApi';
import type { IncidenciasEmpleado } from '../../services/nominaDemoApi';

/**
 * Las llaves que se le mandan a `cerrar-periodo`.
 *
 * Con cartera, las del **CHECADOR**, y sólo de los vinculados: un empleado sin
 * `employee_no` no tiene con qué casarse y `plantillaDeNomina` ya lo dejó fuera
 * del cálculo.
 *
 * **Sin cartera, las de la plantilla del catálogo.** Ese es el camino de la
 * demo —cuando Firestore no está desplegado, la app corre sobre el catálogo del
 * backend—, y ahí las dos llaves coinciden por construcción
 * (`routes/despacho.py` siembra `employee_no = empleado_no`). Devolver una lista
 * vacía en ese caso dejaba el cierre sin un solo empleado: faltas para todos y
 * la tabla de incidencias en blanco. Lo cazó `NominaPorCliente.test.tsx`.
 */
export function llavesParaElCierre(
  plantilla: { empleado_no: string }[],
  deLaCartera: EmpleadoCartera[] | null,
): string[] {
  if (!deLaCartera) return plantilla.map((e) => e.empleado_no);
  return deLaCartera.filter(estaVinculado).map((e) => e.employee_no as string);
}

/**
 * Devuelve las incidencias con la llave del CÁLCULO.
 *
 * `cerrar-periodo` las devuelve con la misma llave que recibió —la del
 * checador—, y `calcular-periodo` responde 422 ante una incidencia cuyo
 * `empleado_no` no esté en la plantilla. Sin esta vuelta, un empleado con
 * llaves distintas tumbaría el cálculo entero.
 *
 * Una incidencia cuya llave de checador no corresponda a nadie de la cartera
 * **se descarta**: es una checada de un número que no está dado de alta, y el
 * backend ya la reporta aparte en `empleados_desconocidos`. Colarla con su
 * llave cruda produciría un 422 o, peor, un recibo a nombre de un número.
 */
export function incidenciasConLlaveDeCalculo(
  incidencias: IncidenciasEmpleado[],
  empleados: EmpleadoCartera[],
): IncidenciasEmpleado[] {
  const porLlaveDeChecador = new Map(
    empleados.filter(estaVinculado).map((e) => [e.employee_no as string, e.empleado_no]),
  );
  return incidencias.flatMap((i) => {
    const delCalculo = porLlaveDeChecador.get(i.empleado_no);
    return delCalculo ? [{ ...i, empleado_no: delCalculo }] : [];
  });
}

/**
 * `true` cuando alguien de la cartera tiene las dos llaves distintas.
 *
 * No es un error —es exactamente lo que G-02 permite—, pero es la condición
 * bajo la cual la traducción de arriba deja de ser la identidad. Sirve para que
 * un test pueda afirmar que el caso está ejercitado y no sólo el trivial.
 */
export function hayLlavesDistintas(empleados: EmpleadoCartera[]): boolean {
  return empleados.some((e) => estaVinculado(e) && e.employee_no !== e.empleado_no);
}
