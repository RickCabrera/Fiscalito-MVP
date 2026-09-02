/**
 * Dispositivos biométricos de un cliente: el modelo y sus validaciones. (R-04)
 *
 * Restaura lo que G-02 recortó ("es colección nueva, CRUD nuevo y pantalla
 * nueva, no cambia ningún número"). El modelo sigue lo que ya prescribían
 * `PLAN_NOMINA.md` §3.3 y `docs/D-DEMO-CHECADOR.md`:
 * `clientes/{id}/checadores/{deviceId}` con `{marca, modelo, host, ultimo_serial}`.
 *
 * QUÉ PUEDE Y QUÉ NO PUEDE AFIRMAR LA PANTALLA
 * --------------------------------------------
 * Esto hay que decirlo antes de que alguien construya encima. **`EventoChecada`
 * no identifica el aparato.** Sus campos son `empleado_no`, `timestamp`, `tipo`,
 * `fuente`, `serial_no` y `raw`; `serial_no` es el consecutivo del **evento**,
 * no la serie del dispositivo. Con dos aparatos en un mismo cliente, el flujo de
 * checadas **no dice cuál produjo cada evento**.
 *
 * Consecuencia: la pantalla **no afirma** "este aparato mandó N checadas", que
 * sería inventado. Afirma lo que sí sabe —quién está enrolado en qué aparato, y
 * si esa persona está checando— y lo dice en pantalla en vez de dejar que el
 * lector suponga.
 *
 * LA IP SE REGISTRA, NO SE CONSULTA
 * ---------------------------------
 * Hablar ISAPI con el Hikvision es **D-08**, que es diurna y necesita el aparato
 * enfrente. Y desde el navegador sería, además, credenciales del dispositivo
 * viajando al cliente. Aquí la IP es un dato de ficha para que el técnico sepa
 * dónde está el aparato; nada la usa para conectarse.
 *
 * LA LLAVE DE ENROLAMIENTO ES `employee_no`, NO `empleado_no`
 * -----------------------------------------------------------
 * Es la separación que G-02 hizo y que sostiene todo esto: `empleado_no` es la
 * llave del CÁLCULO y nunca es nula; `employee_no` es la del CHECADOR y puede
 * serlo. Un aparato enrola números **del checador**, así que `employee_nos`
 * guarda de ésos. Guardar los del cálculo aquí volvería a fundir las dos llaves,
 * que es el defecto fiscal más grave que encontró la corrida G.
 */

import type { EmpleadoCartera } from './carteraApi';

export interface DispositivoChecador {
  /** Id del documento en Firestore. Estable, lo genera el alta. */
  id: string;
  nombre: string;
  /** IPv4 en la red del cliente. Vacío = no se conoce. **No se conecta nada.** */
  ip: string;
  /** Puerto ISAPI. 80 es el default del MinMoe (`D-DEMO-CHECADOR.md`). */
  puerto: number;
  marca: string;
  modelo: string;
  /** Número de serie del aparato, el del sticker. Vacío = no se conoce. */
  serial: string;
  /**
   * `employeeNoString` de las personas enroladas en ESTE aparato.
   * Es la llave del CHECADOR (G-02), no la del cálculo.
   */
  employee_nos: string[];
  notas: string;
}

export function dispositivoVacio(): DispositivoChecador {
  return {
    id: '',
    nombre: '',
    ip: '',
    puerto: 80,
    marca: 'Hikvision',
    modelo: '',
    serial: '',
    employee_nos: [],
    notas: '',
  };
}

// ── Validación ──

export interface ProblemaDispositivo {
  campo: 'nombre' | 'ip' | 'puerto' | 'serial';
  motivo: string;
}

/**
 * IPv4 con cuatro octetos en rango. Se valida de verdad y no con un regex de
 * dígitos y puntos: `999.1.1.1` pasa el regex ingenuo y no es una dirección.
 */
export function ipValida(ip: string): boolean {
  const partes = ip.split('.');
  if (partes.length !== 4) return false;
  return partes.every((p) => /^\d{1,3}$/.test(p) && Number(p) <= 255);
}

/**
 * Qué está mal en un dispositivo antes de guardarlo.
 *
 * `serialesEnUso` son los de los OTROS aparatos del mismo cliente: el que se
 * edita no choca consigo mismo. Un serial repetido no rompe ningún cálculo
 * —nada casa checadas por serial de aparato— pero sí deja al técnico sin poder
 * distinguir dos filas idénticas cuando vaya a buscar el equipo físicamente,
 * que es para lo que existe esta pantalla.
 */
export function validarDispositivo(
  d: DispositivoChecador,
  serialesEnUso: string[],
): ProblemaDispositivo[] {
  const problemas: ProblemaDispositivo[] = [];

  if (d.nombre.trim() === '') {
    problemas.push({
      campo: 'nombre',
      motivo: 'Ponle un nombre que sirva para encontrarlo: "Entrada planta", "Recepción".',
    });
  }

  // La IP es OPCIONAL —un aparato puede estar registrado antes de instalarse—
  // pero si se captura tiene que ser una dirección.
  if (d.ip.trim() !== '' && !ipValida(d.ip.trim())) {
    problemas.push({
      campo: 'ip',
      motivo: `"${d.ip}" no es una dirección IPv4. Son cuatro números de 0 a 255, como 192.168.1.64.`,
    });
  }

  if (!Number.isInteger(d.puerto) || d.puerto < 1 || d.puerto > 65535) {
    problemas.push({ campo: 'puerto', motivo: 'El puerto va de 1 a 65535. El del MinMoe es 80.' });
  }

  const serial = d.serial.trim();
  if (serial !== '' && serialesEnUso.includes(serial)) {
    problemas.push({
      campo: 'serial',
      motivo: `Ya hay otro dispositivo con el serial ${serial}. Son dos filas que no vas a poder distinguir cuando busques el aparato.`,
    });
  }

  return problemas;
}

// ── El cruce con la cartera, que es el valor real de la pantalla ──

export interface CruceEnrolamiento {
  /** Enrolados en este aparato que SÍ están en la cartera. */
  enrolados: EmpleadoCartera[];
  /**
   * `employee_no` enrolados en el aparato que **no existen en la cartera**.
   * Sus checadas llegan y no se pueden atribuir a nadie: es el mismo agujero
   * que `TablaIncidencias` llama "desconocidos", visto desde el otro lado.
   */
  fantasmas: string[];
}

/**
 * Cruza lo enrolado en un aparato contra la cartera del cliente.
 *
 * Es el tercer lado del triángulo que G-02 dejó a medias. Los otros dos ya
 * existen: `EmpleadosTab` cuenta los **no vinculados** (en la cartera, sin
 * `employee_no`) y `TablaIncidencias` los **desconocidos** (checaron, no están
 * en la plantilla). Faltaba éste: **enrolado en el aparato y ausente de la
 * cartera**, que es el que explica de dónde salen los desconocidos.
 */
export function cruzarEnrolamiento(
  dispositivo: DispositivoChecador,
  empleados: EmpleadoCartera[],
): CruceEnrolamiento {
  const porLlaveDelChecador = new Map(
    empleados.filter((e) => e.employee_no).map((e) => [e.employee_no as string, e]),
  );
  const enrolados: EmpleadoCartera[] = [];
  const fantasmas: string[] = [];
  for (const no of dispositivo.employee_nos) {
    const empleado = porLlaveDelChecador.get(no);
    if (empleado) enrolados.push(empleado);
    else fantasmas.push(no);
  }
  return { enrolados, fantasmas };
}

/**
 * Empleados vinculados al checador que **no están en ningún aparato**.
 *
 * Tienen `employee_no`, así que `EmpleadosTab` los da por buenos y entran al
 * cálculo de nómina — pero si nadie los enroló en un aparato, no van a producir
 * una sola checada y saldrán con **falta en todos los días laborables**. Es una
 * nómina completa y creíble, con menos días pagados, que es justo el modo de
 * falla que `D-DEMO-CHECADOR.md` advierte que no parece un error.
 */
export function sinAparato(
  empleados: EmpleadoCartera[],
  dispositivos: DispositivoChecador[],
): EmpleadoCartera[] {
  const enrolados = new Set(dispositivos.flatMap((d) => d.employee_nos));
  return empleados.filter((e) => e.employee_no && !enrolados.has(e.employee_no));
}
