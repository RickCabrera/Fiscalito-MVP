/**
 * Alta y edición de un empleado (G-01, G-02).
 *
 * EL SBC LO CALCULA EL MOTOR, NO ESTE ARCHIVO
 * -------------------------------------------
 * Al teclear el salario se llama a `POST /nomina/sbc`. No hay ni una fórmula
 * fiscal aquí: el Art. 27 tiene una sola implementación, en `integracion.py`,
 * con sus tests. Un factor calculado en TypeScript sería una segunda verdad que
 * nadie cuida.
 *
 * LA FECHA SE MANDA EXPLÍCITA
 * ---------------------------
 * `clamp_sbc` mueve el piso el 1-ene y el tope el 1-feb. Mandar la fecha —y no
 * dejar que el backend use `today()`— es lo que hace que el número sea
 * reproducible y que la pantalla pueda decir contra qué se midió.
 *
 * EL NSS (R-03)
 * -------------
 * G-01 lo dejó fuera con esta razón: "teclear el NSS real de un trabajador lo
 * escribiría en un Firestore cuyas reglas todavía nadie ha revisado". **R-01
 * eliminó esa razón** —las reglas se revisaron, se probaron con diez casos y se
 * desplegaron— así que el campo vuelve. El orden de la corrida no fue casual.
 *
 * La validación vive en `services/nss.ts`, no aquí. Lo único que este archivo
 * decide es qué se pinta: **la longitud bloquea el guardado y el dígito
 * verificador sólo advierte**, con la razón completa en el encabezado de ese
 * módulo (bloquear el verificador empujaría al contador a teclear uno que pase
 * Luhn, o sea a inventar un NSS y ponerlo junto a datos reales).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  integrarSBC,
  PARAMETROS_DE_LEY,
  type EmpleadoCartera,
  type ParametrosSalariales,
  type SBCResponse,
} from '../../services/carteraApi';
import { normalizarNSS, validarNSS } from '../../services/nss';
import IdentidadEmpleado from './IdentidadEmpleado';
import PagoContactoEmpleado from './PagoContactoEmpleado';
import { errorPagoContacto, normalizarCelular } from '../../services/clabe';
import CamposNominaEmpleado from './CamposNominaEmpleado';
import CamposImssCfdiEmpleado from './CamposImssCfdiEmpleado';
import ResultadoSbc from './ResultadoSbc';
import { antiguedad, vacio } from './empleadoNuevo';
import {
  AvisosDuplicados,
  CabeceraModal,
  ChecadorEmpleado,
  NssEmpleado,
  PrestacionesEmpleado,
  SalarioContratoEmpleado,
} from './SeccionesEmpleado';

export default function ModalEmpleado({
  empleado,
  existentes,
  enUsoPorOtro,
  onGuardar,
  onCerrar,
  parametros,
}: {
  /** `null` = alta. Con valor = edición. */
  empleado: EmpleadoCartera | null;
  /** Los `empleado_no` ya usados en este cliente, para no duplicar la llave. */
  existentes: string[];
  /** Los `employee_no` de LOS DEMÁS: el del aparato tampoco se puede repetir. */
  enUsoPorOtro: string[];
  onGuardar: (e: EmpleadoCartera) => Promise<void>;
  onCerrar: () => void;
  /**
   * Los parámetros del PATRÓN (O-03): sus prestaciones son el default de cada
   * empleado, y su escala de vacaciones viaja al SBC.
   *
   * Opcional: sin ellos manda el mínimo de ley.
   */
  parametros?: ParametrosSalariales;
}) {
  const esAlta = empleado === null;
  const [datos, setDatos] = useState<EmpleadoCartera>(() => empleado ?? vacio(parametros));
  // El resultado guarda LA CLAVE de la petición que lo produjo, y `calculando`
  // se DERIVA de compararla con la clave actual. Es el patrón que ya usa
  // `ClienteDetallePage` con `resultado.id === id`, y evita llamar a setState
  // sincrónicamente dentro del efecto, que dispara renders en cascada.
  const [resultado, setResultado] = useState<
    { clave: string; sbc: SBCResponse | null; error: string | null } | null
  >(null);
  const [guardando, setGuardando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const set = useCallback(
    <K extends keyof EmpleadoCartera>(k: K, v: EmpleadoCartera[K]) =>
      setDatos((d) => ({ ...d, [k]: v })),
    [],
  );

  const salario = datos.salario_diario;
  const fechaAlta = datos.fecha_alta ?? '';
  const { dias_aguinaldo, dias_vacaciones, prima_vacacional } = datos.prestaciones;
  /**
   * O-03: la escala de vacaciones es del PATRÓN, no del empleado.
   *
   * No se copia a `datos.prestaciones` a propósito: si se guardara con cada
   * empleado, cambiarla en los parámetros del patrón dejaría a los ya dados de
   * alta con la escala vieja, y nadie sabría por qué dos personas con la misma
   * antigüedad integran distinto.
   */
  /**
   * Identidad ESTABLE de la tabla.
   *
   * `deClienteCartera` reconstruye el arreglo en cada render del proveedor, así
   * que depender del objeto dispararía una petición de SBC por render — y los
   * 400 ms de debounce no alcanzan contra eso. Se memoiza sobre su forma
   * serializada, que sólo cambia cuando la tabla cambia de verdad.
   */
  const claveTablaVacaciones = JSON.stringify(
    (parametros ?? PARAMETROS_DE_LEY).tabla_vacaciones,
  );
  const tablaVacaciones = useMemo(
    () => JSON.parse(claveTablaVacaciones) as [number, number][],
    [claveTablaVacaciones],
  );

  const salarioValido = Number(salario) > 0;

  /** Todo lo que cambia el SBC. Si cambia, el resultado anterior ya no vale. */
  const clave = JSON.stringify([
    salario, fechaAlta, datos.zona, dias_aguinaldo, dias_vacaciones, prima_vacacional,
  ]);

  const alDia = resultado !== null && resultado.clave === clave;
  const sbc = alDia ? resultado.sbc : null;
  const errorSbc = alDia ? resultado.error : null;
  const calculando = salarioValido && !alDia;

  // El SBC se pide al motor con debounce. `fecha` viaja explícita: el backend
  // no tiene default, porque piso y tope se mueven en fechas distintas.
  useEffect(() => {
    if (!salarioValido) return;
    let cancelado = false;
    const t = setTimeout(() => {
      integrarSBC({
        salario_diario: salario,
        fecha: new Date().toISOString().slice(0, 10),
        zona: datos.zona,
        anios_servicio_cumplidos: antiguedad(fechaAlta),
        dias_aguinaldo,
        dias_vacaciones,
        prima_vacacional,
        // O-03: la escala del patrón viaja entera. Cuando la hay, el backend
        // ignora `dias_vacaciones` y devuelve los que aplicó — y el modal ya
        // los pinta al lado del factor, así que el operador ve con cuántos se
        // integró sin que el front tenga que buscarlos.
        tabla_vacaciones: tablaVacaciones,
      })
        .then((r) => !cancelado && setResultado({ clave, sbc: r, error: null }))
        .catch((e: unknown) => {
          if (cancelado) return;
          setResultado({
            clave,
            sbc: null,
            error: e instanceof Error ? e.message : 'No se pudo integrar el salario',
          });
        });
    }, 400);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [
    clave, salarioValido, salario, fechaAlta, datos.zona,
    dias_aguinaldo, dias_vacaciones, prima_vacacional, tablaVacaciones,
  ]);

  /** Vacío es válido: es la salida del contador que no tiene el número. */
  const nss = useMemo(() => validarNSS(datos.nss), [datos.nss]);

  const llaveRepetida = useMemo(
    () => esAlta && existentes.includes(datos.empleado_no.trim()),
    [esAlta, existentes, datos.empleado_no],
  );

  /**
   * Dos personas con el mismo número de aparato.
   *
   * El checador manda **una sola** serie de checadas para ese número, así que
   * una de las dos se queda sin incidencias y el cálculo revienta con "estos
   * empleados no traen incidencias del periodo" — un mensaje que manda a cerrar
   * un periodo que sí se cerró. Falla fuerte, no en silencio, pero la pista es
   * falsa y el arreglo cuesta esta línea.
   */
  const numeroDeAparatoRepetido = useMemo(() => {
    const propio = datos.employee_no?.trim();
    return Boolean(propio) && enUsoPorOtro.includes(propio as string);
  }, [datos.employee_no, enUsoPorOtro]);

  const puedeGuardar =
    datos.empleado_no.trim() !== '' &&
    datos.nombre.trim() !== '' &&
    sbc !== null &&
    !llaveRepetida &&
    !numeroDeAparatoRepetido &&
    // `advertencia` NO bloquea: ver `services/nss.ts`.
    nss.puedeGuardar &&
    // P4-12/13: CLABE con verificador, cuenta, correo y celular E.164.
    errorPagoContacto(datos) === null &&
    !guardando;

  async function guardar() {
    if (!sbc) return;
    setGuardando(true);
    setErrorGuardar(null);
    try {
      await onGuardar({
        ...datos,
        empleado_no: datos.empleado_no.trim(),
        nombre: datos.nombre.trim(),
        // El SDI que se guarda es el que devolvió el MOTOR, ya acotado. No se
        // recalcula ni se redondea aquí.
        salario_diario_integrado: sbc.sbc,
        employee_no: datos.employee_no?.trim() || null,
        // Normalizado: se captura con espacios y guiones, se guarda en dígitos.
        nss: normalizarNSS(datos.nss),
        clabe: (datos.clabe ?? '').replace(/\s/g, ''),
        celular: normalizarCelular(datos.celular ?? '') ?? '',
      });
      onCerrar();
    } catch (e) {
      setErrorGuardar(e instanceof Error ? e.message : 'No se pudo guardar');
      setGuardando(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-label={esAlta ? 'Alta de empleado' : `Editar ${datos.nombre}`}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 'var(--space-md)',
      }}
    >
      <div
        className="card"
        style={{
          width: 'min(760px, 100%)', maxHeight: '90vh', overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 'var(--space-md)',
        }}
      >
        <CabeceraModal titulo={esAlta ? 'Nuevo empleado' : datos.nombre} onCerrar={onCerrar} />

        <IdentidadEmpleado datos={datos} esAlta={esAlta} set={set} />

        <PagoContactoEmpleado datos={datos} set={set} />

        <AvisosDuplicados
          datos={datos}
          numeroDeAparatoRepetido={numeroDeAparatoRepetido}
          llaveRepetida={llaveRepetida}
        />

        <SalarioContratoEmpleado datos={datos} set={set} />
        {/* P4-03/P4-04: régimen (sueldos o asimilado) y fecha de baja. */}
        <CamposNominaEmpleado datos={datos} onCambiar={(c) => setDatos((d) => ({ ...d, ...c }))} />
        {/* P4-09/P4-11: causa de baja, tipo de salario y datos del receptor del CFDI. */}
        <CamposImssCfdiEmpleado datos={datos} onCambiar={(c) => setDatos((d) => ({ ...d, ...c }))} />

        <NssEmpleado datos={datos} set={set} nss={nss} />

        <PrestacionesEmpleado datos={datos} set={set} />

        {/* El resultado del MOTOR. Todo lo de esta caja viene del backend. */}
        <ResultadoSbc calculando={calculando} errorSbc={errorSbc} sbc={sbc} />

        <ChecadorEmpleado datos={datos} set={set} />

        {errorGuardar && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.85rem' }}>
            {errorGuardar}
          </p>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
          <button className="btn-secondary" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primary" disabled={!puedeGuardar} onClick={guardar}>
            {guardando ? 'Guardando…' : esAlta ? 'Dar de alta' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}
