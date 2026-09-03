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
import { AlertTriangle, Loader, X } from 'lucide-react';
import {
  integrarSBC,
  PARAMETROS_DE_LEY,
  type EmpleadoCartera,
  type ParametrosSalariales,
  type SBCResponse,
  type TipoContrato,
} from '../../services/carteraApi';
import { normalizarNSS, validarNSS } from '../../services/nss';
import Campo from './Campo';
import { campoInput as campo, etiquetaCampo as etiqueta } from './estilosCampo';
import { modoEmpresaUnica } from '../../services/modoEmpresa';

const TIPOS: { valor: TipoContrato; etiqueta: string }[] = [
  { valor: 'indeterminado', etiqueta: 'Indeterminado' },
  { valor: 'determinado', etiqueta: 'Por tiempo determinado' },
  { valor: 'obra_determinada', etiqueta: 'Por obra determinada' },
  { valor: 'prueba', etiqueta: 'A prueba' },
];

/** Años cumplidos entre el alta y hoy. Sólo decide vacaciones de ley. */
function antiguedad(fechaAlta: string): number {
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

function vacio(parametros?: ParametrosSalariales): EmpleadoCartera {
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
    // política de la empresa, que es lo que aplica a casi todos.
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
   * Opcional para no romper a los dos llamadores del modo despacho, donde no
   * hay una empresa única de la que sacarlos: sin ellos manda el mínimo de ley,
   * que es lo que la app aplicaba antes de O-03.
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
   * empleado, cambiarla en Configuración de empresa dejaría a los ya dados de
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            {esAlta ? 'Nuevo empleado' : datos.nombre}
          </h2>
          <button
            onClick={onCerrar}
            aria-label="Cerrar"
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="Número de empleado *">
            <input
              style={campo}
              value={datos.empleado_no}
              disabled={!esAlta}
              onChange={(e) => set('empleado_no', e.target.value)}
              placeholder="E-10"
            />
          </Campo>
          <Campo label="Nombre *" ancho="2 1 320px">
            <input
              style={campo}
              value={datos.nombre}
              onChange={(e) => set('nombre', e.target.value)}
            />
          </Campo>
          <Campo label="Puesto">
            <input style={campo} value={datos.puesto} onChange={(e) => set('puesto', e.target.value)} />
          </Campo>
        </div>

        {numeroDeAparatoRepetido && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
            Otro empleado ya tiene el número de checador{' '}
            <strong>{datos.employee_no}</strong>. El aparato manda una sola serie de
            checadas por número, así que uno de los dos se quedaría sin incidencias.
          </p>
        )}

        {llaveRepetida && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
            Ya hay un empleado con el número <strong>{datos.empleado_no}</strong>
            {modoEmpresaUnica() ? '' : ' en este cliente'}. El número es la llave del
            cálculo: repetirlo haría que uno se comiera las incidencias del otro.
          </p>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="Salario diario *">
            <input
              style={campo}
              inputMode="decimal"
              value={datos.salario_diario}
              onChange={(e) => set('salario_diario', e.target.value)}
              placeholder="450.00"
            />
          </Campo>
          <Campo label="Fecha de alta">
            <input
              type="date"
              style={campo}
              value={fechaAlta}
              onChange={(e) => set('fecha_alta', e.target.value || null)}
            />
          </Campo>
          <Campo label="Tipo de contrato">
            <select
              style={campo}
              value={datos.tipo_contrato}
              onChange={(e) => set('tipo_contrato', e.target.value as TipoContrato)}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>{t.etiqueta}</option>
              ))}
            </select>
          </Campo>
        </div>

        {/* R-03. Opcional a propósito, y el placeholder lo dice: es la salida
            para quien no tiene el número, y es lo que hace seguro rechazar por
            longitud sin acorralar a nadie. */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="NSS (opcional)">
            <input
              style={{
                ...campo,
                // `border` completo y no `borderColor`: `campoInput` usa el
                // atajo, y mezclar atajo con propiedad larga hace que React
                // avise y que el borde dependa del orden de las claves.
                border:
                  nss.gravedad === 'ok'
                    ? campo.border
                    : `1px solid var(--${nss.gravedad === 'error' ? 'danger' : 'warning'})`,
              }}
              inputMode="numeric"
              // Sin `maxLength`: truncar en silencio un pegado largo puede
              // dejar 11 dígitos con aspecto de buenos. La longitud la juzga
              // `validarNSS`, que sí lo dice.
              value={datos.nss}
              onChange={(e) => set('nss', e.target.value)}
              placeholder="Si no lo tienes, déjalo vacío"
              aria-invalid={nss.gravedad === 'error'}
              aria-describedby={nss.motivo ? 'nss-motivo' : undefined}
            />
          </Campo>
        </div>

        {nss.motivo && (
          <p
            id="nss-motivo"
            // `alert` sólo cuando impide guardar. Una advertencia que se anuncia
            // como error entrena a ignorarlas.
            role={nss.gravedad === 'error' ? 'alert' : 'status'}
            style={{
              margin: 0, fontSize: '0.82rem',
              color: nss.gravedad === 'error' ? 'var(--danger)' : 'var(--warning)',
            }}
          >
            {nss.motivo}
          </p>
        )}

        <fieldset style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)' }}>
          <legend style={{ ...etiqueta, marginBottom: 0, padding: '0 6px' }}>
            Prestaciones (integran el SBC — Art. 27 LSS)
          </legend>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
            <Campo label="Días de aguinaldo">
              <input
                type="number" min={15} style={campo}
                value={dias_aguinaldo}
                onChange={(e) => set('prestaciones', { ...datos.prestaciones, dias_aguinaldo: Number(e.target.value) })}
              />
            </Campo>
            <Campo label="Días de vacaciones (0 = los de ley)">
              <input
                type="number" min={0} style={campo}
                value={dias_vacaciones}
                onChange={(e) => set('prestaciones', { ...datos.prestaciones, dias_vacaciones: Number(e.target.value) })}
              />
            </Campo>
            <Campo label="Prima vacacional (0.25 = 25%)">
              <input
                style={campo} inputMode="decimal"
                value={prima_vacacional}
                onChange={(e) => set('prestaciones', { ...datos.prestaciones, prima_vacacional: e.target.value })}
              />
            </Campo>
          </div>
        </fieldset>

        {/* El resultado del MOTOR. Todo lo de esta caja viene del backend. */}
        <div
          style={{
            background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)', fontSize: '0.86rem',
          }}
        >
          {calculando && (
            <span style={{ color: 'var(--text-secondary)', display: 'flex', gap: 6, alignItems: 'center' }}>
              <Loader size={14} /> Integrando…
            </span>
          )}
          {!calculando && errorSbc && (
            <span role="alert" style={{ color: 'var(--danger)' }}>{errorSbc}</span>
          )}
          {!calculando && !errorSbc && !sbc && (
            <span style={{ color: 'var(--text-muted)' }}>
              Captura el salario diario para ver el SBC.
            </span>
          )}
          {!calculando && sbc && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
              <span>
                Factor <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{sbc.factor}</strong>
                <span style={{ color: 'var(--text-muted)' }}> ({sbc.dias_vacaciones_aplicados} días de vacaciones)</span>
              </span>
              <span>
                SBC <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>${sbc.sbc}</strong>
              </span>
              {sbc.piso_aplicado && (
                <span style={{ color: 'var(--warning)', display: 'flex', gap: 4, alignItems: 'center' }}>
                  <AlertTriangle size={14} />
                  Se aplicó el piso de 1 salario mínimo (${sbc.piso}). El patrón absorbe la
                  cuota obrera (Art. 36 LSS).
                </span>
              )}
              {sbc.tope_aplicado && (
                <span style={{ color: 'var(--warning)', display: 'flex', gap: 4, alignItems: 'center' }}>
                  <AlertTriangle size={14} /> Se aplicó el tope de 25 UMA (${sbc.tope}).
                </span>
              )}
            </div>
          )}
        </div>

        <fieldset style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)' }}>
          <legend style={{ ...etiqueta, marginBottom: 0, padding: '0 6px' }}>Checador</legend>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
            <Campo label="employeeNo del aparato">
              <input
                style={campo}
                value={datos.employee_no ?? ''}
                onChange={(e) => set('employee_no', e.target.value || null)}
                placeholder="Sin vincular"
              />
            </Campo>
            <Campo label="Enrolamiento biométrico">
              <select
                style={campo}
                value={datos.enrolamiento}
                onChange={(e) => set('enrolamiento', e.target.value as 'pendiente' | 'enrolado')}
              >
                <option value="pendiente">Pendiente</option>
                <option value="enrolado">Enrolado</option>
              </select>
            </Campo>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            El rostro se captura <strong>en el aparato</strong> (menú Usuario → Agregar), no aquí.
            Sin este número, las checadas de esta persona no se pueden atribuir y{' '}
            <strong>no entra al cálculo de nómina</strong>.
          </p>
        </fieldset>

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
