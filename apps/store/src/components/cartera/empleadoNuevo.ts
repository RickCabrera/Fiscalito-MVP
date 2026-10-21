/**
 * Datos de arranque del modal de empleado. Salieron de `ModalEmpleado.tsx` en
 * P6-05 (tope de 300 líneas) sin cambiar nada.
 */
import type { EmpleadoCartera, ParametrosSalariales } from '../../services/carteraApi';

/** Años cumplidos entre el alta y hoy. Sólo decide vacaciones de ley. */
export function antiguedad(fechaAlta: string): number {
  if (!fechaAlta) return 0;
  const alta = new Date(fechaAlta);
  const hoy = new Date();
  let anios = hoy.getFullYear() - alta.getFullYear();
  const cumpleEsteAnio =
    hoy.getMonth() > alta.getMonth() ||
    (hoy.getMonth() === alta.getMonth() && hoy.getDate() >= alta.getDate());
  if (!cumpleEsteAnio) anios -= 1;
  return Math.max(0, anios);
}

export function vacio(parametros?: ParametrosSalariales): EmpleadoCartera {
  return {
    empleado_no: '',
    nombre: '',
    puesto: '',
    salario_diario: '',
    salario_diario_integrado: '',
    zona: 'general',
    fecha_alta: null,
    tipo_contrato: 'indeterminado',
    // O-03: el alta arranca con las prestaciones del PATRÓN, no con el mínimo
    // de ley. Se pueden pisar para un caso particular; el default es la
    // política del patrón, que es lo que aplica a casi todos.
    prestaciones: {
      dias_aguinaldo: parametros?.dias_aguinaldo ?? 15,
      dias_vacaciones: 0,
      prima_vacacional: parametros?.prima_vacacional ?? '0.25',
    },
    nss: '',
    employee_no: null,
    enrolamiento: 'pendiente',
  };
}
