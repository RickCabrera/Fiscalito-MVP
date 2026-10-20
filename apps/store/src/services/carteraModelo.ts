/**
 * El modelo de la cartera del despacho: cliente, empleado, prestaciones y horario.
 *
 * Salió de `carteraApi.ts` (P4, tope de 300 líneas), que lo re-exporta. Sólo tipos,
 * constantes de captura y helpers puros: aquí no hay ni una llamada al backend.
 */

// ── El modelo ──

export type TipoContrato = 'indeterminado' | 'determinado' | 'obra_determinada' | 'prueba';
export type EstatusEnrolamiento = 'pendiente' | 'enrolado';

export interface Prestaciones {
  dias_aguinaldo: number;
  /** 0 = los de ley que le tocan a su antigüedad (Art. 76 LFT). */
  dias_vacaciones: number;
  /** Proporción, no porcentaje: 0.25 es el mínimo de ley. */
  prima_vacacional: string;
}

export interface EmpleadoCartera {
  /** Llave del CÁLCULO. Nunca vacía, única dentro del cliente. */
  empleado_no: string;
  /** El nombre completo, que es lo que se pinta en todas las pantallas. */
  nombre: string;
  /**
   * Los tres campos del layout del IMSS (O-04): apellidos y nombre de pila por
   * separado, 27 posiciones cada uno.
   *
   * **Se capturan; no se parten.** Partir "MARIA DE LOS ANGELES SANTA CRUZ
   * RIVERA" a la adivina produce un movimiento afiliatorio con el apellido
   * equivocado, y en español el apellido compuesto es la norma. Opcionales para
   * no romper una cartera escrita antes de O-04; quien los tenga vacíos no se
   * exporta, y el exportador lo dice con su razón.
   */
  apellido_paterno?: string;
  apellido_materno?: string;
  nombres?: string;
  puesto: string;
  salario_diario: string;
  salario_diario_integrado: string;
  zona: string;
  fecha_alta: string | null;
  tipo_contrato: TipoContrato;
  prestaciones: Prestaciones;
  /** Vacío cuando no se conoce. **Nunca se inventa.** */
  nss: string;
  /**
   * Llave del CHECADOR (`employeeNoString` del Hikvision). `null` = el empleado
   * **no está vinculado**: sus checadas no se pueden atribuir a nadie.
   * Es distinta de `empleado_no`, que es la del cálculo y nunca es nula.
   */
  employee_no: string | null;
  /** P4-03: fecha de baja. El periodo que la contiene se calcula PARCIAL (§D26). */
  fecha_baja?: string | null;
  /** P4-04: c_TipoRegimen. '02' sueldos; '05'-'11' asimilados (Art. 94 LISR, sin IMSS). */
  tipo_regimen?: string;
  enrolamiento: EstatusEnrolamiento;
  /** P4-09: catálogo IMSS de causas de baja (1-9, A). Vacío = no capturada. */
  causa_baja?: string;
  /** P4-09: IMSS 0 fijo, 1 variable, 2 mixto. */
  tipo_salario?: string;
  /** P4-11: datos del receptor del CFDI de nómina. Vacíos = no se puede timbrar. */
  rfc?: string;
  curp?: string;
  codigo_postal?: string;
  /** P4-12: cómo se le paga. Sólo `transferencia` entra a la dispersión. */
  forma_pago?: FormaPagoEmpleado;
  /** P4-12: clave c_Banco (3 dígitos). Vacío = la toma el backend de la CLABE. */
  banco?: string;
  /** P4-12: 18 dígitos con verificador de Banxico (`services/clabe.ts`). */
  clabe?: string;
  /** P4-12: cuenta (10-12 dígitos) o tarjeta (16) del mismo banco. */
  numero_cuenta?: string;
  /** P4-13: contacto para mandarle sus recibos. */
  correo?: string;
  /** P4-13: E.164 mexicano (+52 y 10 dígitos). El backend lo normaliza. */
  celular?: string;
  consentimiento_whatsapp?: boolean;
}

export type FormaPagoEmpleado = 'transferencia' | 'efectivo' | 'cheque';

/** El horario contra el que el checador mide retardos y faltas. (O-03) */
export interface HorarioLaboral {
  /** `HH:MM`. */
  hora_entrada: string;
  hora_salida: string;
  tolerancia_minutos: number;
  /** Convención de `Date.getDay()` corrida: 0 = lunes, como `datetime.weekday()`. */
  dias_laborables: number[];
}

/**
 * Las prestaciones del patrón, que alimentan el factor de integración. (O-03)
 *
 * **Lo que NO está aquí es tan importante como lo que sí**: las tablas de ISR,
 * las cuotas del IMSS, la UMA y el salario mínimo no se configuran. Son de ley,
 * viven en el motor con su fuente publicada y se actualizan con el DOF.
 */
export interface ParametrosSalariales {
  /** Mínimo 15 (Art. 87 LFT). */
  dias_aguinaldo: number;
  /** Proporción, no porcentaje. Mínimo 0.25 (Art. 80 LFT). */
  prima_vacacional: string;
  /** Escala propia `[[años, días], ...]`. Vacía = manda la ley (Art. 76 LFT). */
  tabla_vacaciones: [number, number][];
  horario: HorarioLaboral;
}

export const PARAMETROS_DE_LEY: ParametrosSalariales = {
  dias_aguinaldo: 15,
  prima_vacacional: '0.25',
  tabla_vacaciones: [],
  horario: {
    hora_entrada: '08:00',
    hora_salida: '17:00',
    tolerancia_minutos: 15,
    dias_laborables: [0, 1, 2, 3, 4],
  },
};

/**
 * Régimen fiscal del CLIENTE, no del despacho (T1).
 *
 * Es lo que decide qué tabs de Fiscalito se le pueden trabajar. **El corte
 * concreto 612 / 626 es un criterio HEREDADO de E-01, no una regla verificada:**
 * `getTabsForProfile` ya escondía DIOT y Retenciones a un 626 desde antes de T1,
 * y lo único que T1 hace es aplicarlo al cliente del despacho en vez de al
 * contribuyente. **Queda pendiente de confirmar con la contadora (§D30)**, y son
 * dos preguntas distintas que no comparten fundamento — el detalle está ahí.
 *
 * 612 y 626 son los dos que el motor y el calendario manejan para persona
 * física. **601 entró con T6 y es de otra naturaleza: un CASCARÓN.** El motor
 * de personas morales no existe —`routes/declaraciones.py` rechaza el 601 con
 * un 400 antes de `calculadora.py`— y lo que el despacho ve al elegirlo es el
 * tab de pagos provisionales PM, una estimación que se calcula en el navegador
 * y lo dice en un banner. Se ofrece porque un despacho contable real lleva
 * morales y verlas ausentes del alta es peor que verlas marcadas como
 * estimación; no se ofrece como régimen soportado de punta a punta.
 */
export const REGIMENES_DE_CLIENTE = [
  { code: '612', name: 'Actividad Empresarial y Profesional' },
  { code: '626', name: 'RESICO (Régimen Simplificado de Confianza)' },
  { code: '601', name: 'General de Ley Personas Morales' },
] as const;

/**
 * El régimen con el que se lee un cliente que NO lo trae capturado.
 *
 * DECISIÓN PROVISIONAL (nocturno): ver `docs/decisiones-nomina.md` §D29.
 *
 * **No es una adivinanza silenciosa**: es el default del alta, y la pantalla de
 * Fiscalito avisa cuando lo está aplicando por ausencia de dato en vez de por
 * captura. Se eligió 612 —el set completo, el de `pyme`— y no 626 porque
 * esconder tabs le quita al contador herramientas de trabajo sin decirle por
 * qué, mientras que un tab de más sobre un cliente que el contador conoce no
 * presenta nada solo: la DIOT se genera, se revisa y se presenta a mano.
 */
export const REGIMEN_CLIENTE_POR_DEFECTO = '612';

export interface ClienteCartera {
  id: string;
  nombre: string;
  giro: string;
  origen: string;
  /**
   * Régimen fiscal del cliente (T1). **Opcional**: una cartera escrita antes de
   * T1 no lo trae, y exigirlo dejaría al contador sin sus clientes por un campo
   * de más — la misma política que `rfc` y `registro_patronal`. Vacío o ausente
   * se lee como `REGIMEN_CLIENTE_POR_DEFECTO`.
   */
  regimen?: string;
  /**
   * RFC del cliente (el patrón, en nómina). **Opcional**: los tres clientes de
   * demostración no lo traen, y una cartera escrita antes de O-01 tampoco. Lo
   * capturan el alta y la edición de cliente (C-01) —obligatorio en el alta— y
   * la Configuración de empresa (O-01); lo consume el exportador de O-04.
   * Reglas en `components/cartera/datosFiscalesCliente.ts`.
   */
  rfc?: string;
  /**
   * Código postal del domicilio fiscal (C-01). Opcional por la misma razón que
   * `rfc`. Sólo candidato a default del `LugarExpedicion` del CFDI de nómina.
   */
  codigo_postal?: string;
  /**
   * Entidad federativa (C-01), clave del catálogo `c_Estado` del SAT. Opcional
   * por la misma razón que `rfc`. Sólo candidata a default de la `ClaveEntFed`
   * del CFDI de nómina, que es donde el TRABAJADOR presta el servicio.
   */
  clave_entidad?: string;
  /**
   * Registro patronal del IMSS, **11 caracteres** (10 + dígito verificador).
   * Opcional por la misma razón que `rfc`. Sin él no se pueden emitir
   * movimientos afiliatorios: son las posiciones 01-11 del layout.
   */
  registro_patronal?: string;
  /**
   * Número de guía de la subdelegación del IMSS (O-04). Va en las posiciones
   * 134-138 de cada movimiento afiliatorio. Lo asigna la subdelegación: no se
   * calcula ni se deduce.
   */
  guia_subdelegacion?: string;
  prima_riesgo: string;
  clase_riesgo: number | null;
  clave_periodicidad: string;
  zona: string;
  /**
   * Prestaciones y horario del patrón (O-03). **Opcional**: una cartera escrita
   * antes de O-03 no lo trae, y exigirlo dejaría al operador sin sus empleados
   * por un campo de más — el mismo modo de falla que `ilegibles[]` documenta.
   * Quien lo lee cae a `PARAMETROS_DE_LEY`, que es lo que la app aplicaba.
   */
  parametros?: ParametrosSalariales;
  /**
   * Criterios de nómina del despacho para este cliente (P4, DP-3). Opcional: sin él,
   * el backend aplica los defaults de `GET /nomina/criterios`.
   */
  criterios_nomina?: Record<string, string>;
  periodo_sugerido: { inicio: string; fin: string; fecha_pago: string | null };
  empleados: EmpleadoCartera[];
  /**
   * Empleados guardados que **no pasan la validación actual** del backend y por eso no
   * vienen en `empleados` ni entran al cálculo (R-10). Se pintan en la ficha con su
   * razón, como los "no vinculados". Sólo de lectura: no se guarda con el cliente.
   */
  ilegibles?: EmpleadoIlegible[];
}

/** Un empleado guardado que el backend no pudo leer, y por qué (R-10). */
export interface EmpleadoIlegible {
  empleado_no: string;
  nombre: string;
  razon: string;
}

export interface EmpleadosSemilla {
  cliente_id: string;
  origen: string;
  total: number;
  /** Cuántos NO tienen `employee_no`. Lo cuenta el backend, no la UI. */
  sin_vincular: number;
  empleados: EmpleadoCartera[];
}

/**
 * El cliente sin su plantilla: lo que `ModalCliente` edita y `guardarCliente`
 * escribe (C-01). Los empleados se guardan aparte, uno por uno.
 */
export function sinEmpleados(c: ClienteCartera): Omit<ClienteCartera, 'empleados'> {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { empleados, ...resto } = c;
  return resto;
}

/** `true` si sus checadas no tienen con qué casarse. */
export function estaVinculado(e: EmpleadoCartera): boolean {
  return Boolean(e.employee_no);
}

export function contarSinVincular(empleados: EmpleadoCartera[]): number {
  return empleados.filter((e) => !estaVinculado(e)).length;
}
