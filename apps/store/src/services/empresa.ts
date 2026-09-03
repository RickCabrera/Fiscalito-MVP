/**
 * La empresa única: una VISTA sobre el documento del cliente. (O-01)
 *
 * DÓNDE VIVE EL DATO, Y POR QUÉ NO EN EL PERFIL
 * ---------------------------------------------
 * En `users/{uid}/clientes/empresa`, el mismo documento que ya leen
 * `carteraFirestore.ts` y el backend de R-07. **No** en `users/{uid}`.
 *
 * Una versión anterior de esta tarea lo guardaba en el perfil "porque
 * `ProfileContext` ya lo carga". Eso producía **dos casas para el mismo dato**:
 * razón social, prima de riesgo, zona y periodicidad viviendo en dos documentos
 * que divergen al primer despiste — y la prima de riesgo entra directo al ramo
 * de Riesgos de Trabajo de `cuotas.py`, así que divergir ahí es cobrar mal.
 *
 * Es además el problema que R-07 acaba de cerrar: un solo dueño por dato. Se
 * escribe por `guardarCliente` de `services/cartera.ts`, que es el despachador
 * del interruptor de R-07, así que el día que el backend se encienda esto pasa
 * por él **por el mismo camino**.
 *
 * Que además **valide** contra `ClienteCarteraSchema` costó dos arreglos, y se
 * midió en vez de afirmarse: escribir el periodo vacío daba 422
 * (`periodo_sugerido.inicio` no es una fecha) y escribir los defaults daba otro
 * (`nombre` vacío, `prima_riesgo` no decimal). Los dos están cerrados —el
 * periodo se omite del documento y los defaults ya no se escriben— y el mismo
 * payload se valida hoy sin errores. Ver `context/empresaEnLaCartera.ts`.
 *
 * LA CARTERA NO DESAPARECE DEL ALMACÉN, Y HAY QUE DECIRLO
 * -------------------------------------------------------
 * Los empleados siguen en `users/{uid}/clientes/empresa/empleados/{id}`.
 * Mantener la ruta significa que **el interruptor de R-07 se enciende sin
 * migrar un solo documento**, que el checador sigue casando sus llaves y que el
 * cálculo sigue leyendo lo mismo. Cambiar el esquema de almacenamiento para que
 * el modelo interno "se vea" de una sola empresa sería una migración
 * destructiva a cambio de estética.
 *
 * Lo que O-01 promete —y cumple— es que **el concepto de cartera desaparece de
 * la interfaz**: no hay lista de clientes, ni selector, ni rutas.
 */

import {
  PARAMETROS_DE_LEY,
  type ClienteCartera,
  type EmpleadoCartera,
  type ParametrosSalariales,
} from './carteraApi';
import { ID_EMPRESA } from './modoEmpresa';

/** Periodo en blanco: la pantalla de nómina pide capturar las fechas (R-06). */
export const SIN_PERIODO: ClienteCartera['periodo_sugerido'] = {
  inicio: '',
  fin: '',
  fecha_pago: null,
};

/**
 * Los datos patronales de la empresa, en la forma que edita la pantalla.
 *
 * Todos son de captura: ninguno se deriva ni se adivina.
 */
export interface ConfigEmpresa {
  razonSocial: string;
  rfc: string;
  /**
   * Registro patronal del IMSS. Son **11 caracteres**: 10 de registro más su
   * dígito verificador (posiciones 01-10 y 11 del layout de movimientos
   * afiliatorios). Se captura junto y se parte al exportar (O-04): el
   * verificador **no se calcula**, porque no hay algoritmo publicado y un
   * dígito inventado junto a un registro real es peor que un campo vacío.
   */
  registroPatronal: string;
  /**
   * Prima de Riesgos de Trabajo como **fracción**, no porcentaje.
   *
   * Misma convención y mismo rango que `ClienteCartera.prima_riesgo`, que el
   * backend acota a [0.005, 0.150] (Arts. 72 y 73 LSS). La pantalla captura en
   * **porcentaje** y guarda fracción: capturar `5.4355` en vez de `0.054355`
   * multiplica el ramo de RT por mil y ninguna tabla lo detecta después.
   */
  primaRiesgo: string;
  claseRiesgo: number | null;
  /**
   * Área geográfica del salario mínimo.
   *
   * **No la pide el enunciado de O-01, y el motor la necesita**: el piso del
   * SBC es 1 salario mínimo del área (Art. 28 LSS) y la Zona Libre de la
   * Frontera Norte tiene el suyo.
   *
   * DECISIÓN PROVISIONAL (nocturno): se fija `general` porque Veracruz no está
   * en la ZLFN, que es la franja de municipios de la frontera norte. No se pinta
   * en esta tarea y **nadie la ha confirmado**: no está en
   * `docs/decisiones-nomina.md` ni en `PLAN_NOMINA.md` §5, que sólo pregunta por
   * Veracruz para el ISN. Si la empresa tuviera centro de trabajo en la ZLFN, el
   * piso del SBC saldría bajo. Abierta en `docs/nocturno-log.md`.
   */
  zona: string;
  /**
   * Clave de `c_PeriodicidadPago`.
   *
   * **`'04'` (quincenal) es el default declarado de O-01**, y no es una
   * elección estética: si viajara vacío, `tarifa_por_periodicidad` levantaría
   * con "clave desconocida" y la nómina no calcularía.
   *
   * DECISIÓN PROVISIONAL (nocturno): que la nómina de Orca **sea** quincenal no
   * lo ha confirmado nadie. Es la única periodicidad que la app ofrecía antes
   * del pivote y la que usa todo el material de la demo, así que es el default
   * menos sorprendente — pero de la clave depende la tarifa del Art. 96 que se
   * aplica. O-03 abre el selector a semanal y mensual, y sube al motor la guarda
   * que hoy sólo vive en el navegador. Abierta en `docs/nocturno-log.md`.
   */
  clavePeriodicidad: string;
  /**
   * Número de guía que la subdelegación del IMSS le asignó al patrón (O-04).
   *
   * Va en las posiciones 134-138 de **cada** registro de movimientos
   * afiliatorios y en el de cifras de control. **No se calcula ni se deduce**:
   * lo asigna la subdelegación y el patrón lo tiene en su papelería. Vacío
   * significa que no se puede emitir el archivo, y el exportador lo dice.
   */
  guiaSubdelegacion: string;
  /**
   * Prestaciones y horario del patrón (O-03).
   *
   * Alimentan el **factor de integración** y con él el SBC —que es la base de
   * casi todas las cuotas— y el cierre del checador. Se guardan con la empresa
   * y no por empleado: son política del patrón, no de la persona. El modal de
   * empleado los toma como default y puede pisarlos para un caso particular.
   */
  parametros: ParametrosSalariales;
}

export const EMPRESA_POR_DEFECTO: ConfigEmpresa = {
  razonSocial: '',
  rfc: '',
  registroPatronal: '',
  primaRiesgo: '',
  claseRiesgo: null,
  zona: 'general',
  clavePeriodicidad: '04',
  guiaSubdelegacion: '',
  parametros: PARAMETROS_DE_LEY,
};

/**
 * Lee la configuración del documento del cliente.
 *
 * `null` —no hay documento todavía, cuenta recién creada— devuelve los
 * defaults, **no** un objeto a medias: la pantalla de configuración tiene que
 * poder pintar campos vacíos sin reventar.
 */
export function deClienteCartera(c: ClienteCartera | null | undefined): ConfigEmpresa {
  if (!c) return EMPRESA_POR_DEFECTO;
  return {
    razonSocial: c.nombre ?? '',
    rfc: c.rfc ?? '',
    registroPatronal: c.registro_patronal ?? '',
    primaRiesgo: c.prima_riesgo ?? '',
    claseRiesgo: c.clase_riesgo ?? null,
    zona: c.zona || EMPRESA_POR_DEFECTO.zona,
    clavePeriodicidad: c.clave_periodicidad || EMPRESA_POR_DEFECTO.clavePeriodicidad,
    // Una cartera escrita antes de O-03 no trae `parametros`: cae al mínimo de
    // ley, que es exactamente lo que la app venía aplicando.
    parametros: c.parametros ?? PARAMETROS_DE_LEY,
    guiaSubdelegacion: c.guia_subdelegacion ?? '',
  };
}

/**
 * Proyecta la configuración al `ClienteCartera` que consume todo lo demás.
 *
 * `origen: 'propio'` **no es decorativo**: `CarteraContext` filtra por
 * `esClienteDemo(origen)` en toda cuenta que no sea de desarrollo. Con un
 * origen vacío o de demostración, la empresa quedaría filtrada, la cartera en
 * cero, y la nómina se bloquearía con el mensaje de *"este cliente no está en
 * la cartera de tu cuenta"* — que no tiene nada que ver con lo que pasó.
 *
 * `periodo_sugerido` llega de fuera porque **es derivado, no dato de la
 * empresa**: lo resuelve quien lea la cartera, con la regla que vive en el
 * backend. Fabricarlo aquí replicaría en TypeScript una regla de la que
 * dependen la UMA, el salario mínimo, la tarifa del Anexo 8 y el transitorio de
 * enero del subsidio (§D18).
 */
export function aClienteCartera(
  empresa: ConfigEmpresa,
  empleados: EmpleadoCartera[],
  periodoSugerido: ClienteCartera['periodo_sugerido'],
): ClienteCartera {
  return {
    id: ID_EMPRESA,
    nombre: empresa.razonSocial.trim(),
    giro: '',
    origen: 'propio',
    rfc: empresa.rfc,
    registro_patronal: empresa.registroPatronal,
    prima_riesgo: empresa.primaRiesgo,
    clase_riesgo: empresa.claseRiesgo,
    clave_periodicidad: empresa.clavePeriodicidad,
    zona: empresa.zona,
    parametros: empresa.parametros,
    guia_subdelegacion: empresa.guiaSubdelegacion,
    periodo_sugerido: periodoSugerido,
    empleados,
  };
}

/**
 * Si la empresa tiene lo mínimo para que su nómina signifique algo.
 *
 * **La prima de riesgo manda**: entra directo al ramo de Riesgos de Trabajo de
 * `cuotas.py`. Sin ella no hay cuota patronal que calcular, y ponerle un
 * default —el 0.54355% de la clase I, por ejemplo— sería afirmar la prima de
 * una empresa que no la ha declarado, que es exactamente el tipo de dato
 * inventado que este repo rechaza en todos lados.
 *
 * La razón social se exige porque es lo que sale impreso en el PDF, en los
 * archivos de O-04 y en el nombre de la descarga: una nómina sin patrón
 * identificado no le sirve a nadie.
 *
 * Recibe los dos campos sueltos y no el `ConfigEmpresa` entero, a propósito:
 * así el llamador no tiene que construir un objeto derivado por render. El
 * React Compiler no puede probar que un objeto armado al vuelo desde el cliente
 * de la cartera no lo mute, y desoptimizaba el `useMemo` de la plantilla que
 * viaja al cálculo.
 */
export function faltantesDeLaEmpresa(razonSocial: string, primaRiesgo: string): string[] {
  const faltan: string[] = [];
  if (razonSocial.trim() === '') faltan.push('la razón social');
  if (primaRiesgo.trim() === '') faltan.push('la prima de riesgos de trabajo');
  return faltan;
}

export function empresaConfigurada(e: ConfigEmpresa): boolean {
  return faltantesDeLaEmpresa(e.razonSocial, e.primaRiesgo).length === 0;
}
