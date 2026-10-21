/**
 * Secciones del modal de empleado: salario y contrato, NSS, prestaciones y
 * checador. Salieron de `ModalEmpleado.tsx` en P6-05 (tope de 300 líneas) sin
 * cambiar el marcado; el estado y las reglas siguen en el modal.
 */
import { X } from 'lucide-react';
import Campo from './Campo';
import { campoInput as campo, etiquetaCampo as etiqueta } from './estilosCampo';
import type { EmpleadoCartera, TipoContrato } from '../../services/carteraApi';
import type { ResultadoNSS } from '../../services/nss';

const TIPOS: { valor: TipoContrato; etiqueta: string }[] = [
  { valor: 'indeterminado', etiqueta: 'Indeterminado' },
  { valor: 'determinado', etiqueta: 'Por tiempo determinado' },
  { valor: 'obra_determinada', etiqueta: 'Por obra determinada' },
  { valor: 'prueba', etiqueta: 'A prueba' },
];

export function SalarioContratoEmpleado({ datos, set }: {
  datos: EmpleadoCartera;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
}) {
  const fechaAlta = datos.fecha_alta ?? '';
  return (
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
  );
}

export function NssEmpleado({ datos, set, nss }: {
  datos: EmpleadoCartera;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
  nss: ResultadoNSS;
}) {
  return (
    <>
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
    </>
  );
}

export function PrestacionesEmpleado({ datos, set }: {
  datos: EmpleadoCartera;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
}) {
  const { dias_aguinaldo, dias_vacaciones, prima_vacacional } = datos.prestaciones;
  return (
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
  );
}

export function ChecadorEmpleado({ datos, set }: {
  datos: EmpleadoCartera;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
}) {
  return (
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
  );
}

/** Las dos llaves que no se pueden repetir: número de empleado y de checador. */
export function AvisosDuplicados({ datos, numeroDeAparatoRepetido, llaveRepetida }: {
  datos: EmpleadoCartera;
  numeroDeAparatoRepetido: boolean;
  llaveRepetida: boolean;
}) {
  return (
    <>
      {numeroDeAparatoRepetido && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
          Otro empleado ya tiene el número de checador{' '}
          <strong>{datos.employee_no}</strong>. El aparato manda una sola serie de
          checadas por número, así que uno de los dos se quedaría sin incidencias.
        </p>
      )}

      {llaveRepetida && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
          Ya hay un empleado con el número <strong>{datos.empleado_no}</strong> en
          este cliente. El número es la llave del
          cálculo: repetirlo haría que uno se comiera las incidencias del otro.
        </p>
      )}
    </>
  );
}

/** Título del modal con el botón de cerrar. */
export function CabeceraModal({ titulo, onCerrar }: { titulo: string; onCerrar: () => void }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
        {titulo}
      </h2>
      <button
        onClick={onCerrar}
        aria-label="Cerrar"
        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
      >
        <X size={20} />
      </button>
    </div>
  );
}
