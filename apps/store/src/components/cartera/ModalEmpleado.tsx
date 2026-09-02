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
 * NO SE PIDE EL NSS EN ESTA CORRIDA
 * ---------------------------------
 * El modelo lo tiene (`EmpleadoCartera.nss`) y el backend lo acepta, pero el
 * formulario **no lo muestra**. Este modal se abre enfrente de gente durante una
 * demo, y teclear el NSS real de un trabajador lo escribiría en un Firestore
 * cuyas reglas todavía nadie ha revisado. Es la opción conservadora y está
 * anotada como decisión abierta para Ricardo.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader, X } from 'lucide-react';
import {
  integrarSBC,
  type EmpleadoCartera,
  type SBCResponse,
  type TipoContrato,
} from '../../services/carteraApi';

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

function vacio(): EmpleadoCartera {
  return {
    empleado_no: '',
    nombre: '',
    puesto: '',
    salario_diario: '',
    salario_diario_integrado: '',
    zona: 'general',
    fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '',
    employee_no: null,
    enrolamiento: 'pendiente',
  };
}

const campo: React.CSSProperties = {
  width: '100%',
  padding: 'var(--space-sm)',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
};

const etiqueta: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  color: 'var(--text-secondary)',
  marginBottom: 4,
  textTransform: 'uppercase',
  letterSpacing: 0.4,
};

function Campo({
  label, children, ancho = '1 1 200px',
}: { label: string; children: React.ReactNode; ancho?: string }) {
  return (
    <div style={{ flex: ancho, minWidth: 0 }}>
      <label style={etiqueta}>{label}</label>
      {children}
    </div>
  );
}

export default function ModalEmpleado({
  empleado,
  existentes,
  enUsoPorOtro,
  onGuardar,
  onCerrar,
}: {
  /** `null` = alta. Con valor = edición. */
  empleado: EmpleadoCartera | null;
  /** Los `empleado_no` ya usados en este cliente, para no duplicar la llave. */
  existentes: string[];
  /** Los `employee_no` de LOS DEMÁS: el del aparato tampoco se puede repetir. */
  enUsoPorOtro: string[];
  onGuardar: (e: EmpleadoCartera) => Promise<void>;
  onCerrar: () => void;
}) {
  const esAlta = empleado === null;
  const [datos, setDatos] = useState<EmpleadoCartera>(() => empleado ?? vacio());
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
  }, [clave, salarioValido, salario, fechaAlta, datos.zona, dias_aguinaldo, dias_vacaciones, prima_vacacional]);

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
            Ya hay un empleado con el número <strong>{datos.empleado_no}</strong> en este
            cliente. El número es la llave del cálculo: repetirlo haría que uno se comiera
            las incidencias del otro.
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
