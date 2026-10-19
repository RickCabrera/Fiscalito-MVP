/**
 * Alta y edición de un dispositivo biométrico. (R-04)
 *
 * EL ENROLAMIENTO SE ELIGE DE LA CARTERA, NO SE TECLEA
 * ----------------------------------------------------
 * Los `employee_no` se marcan de una lista de empleados **ya vinculados**, en
 * vez de capturarse a mano. Teclearlos permitiría enrolar un número que no
 * existe en la cartera, y ese empleado se volvería un "desconocido" el día del
 * cierre: sus checadas llegarían y no habría a quién atribuirlas. La pantalla
 * sabe cuáles son válidos; pedírselos al operador sería regalar un modo de
 * falla que ya cuesta trabajo diagnosticar.
 *
 * Los empleados **sin** `employee_no` aparecen listados y **deshabilitados**,
 * con la razón: no se pueden enrolar porque no tienen llave de checador, y esa
 * llave se captura en el modal de empleado. Ocultarlos dejaría al operador
 * preguntándose por qué falta gente.
 *
 * EL ROSTRO SE CAPTURA EN EL APARATO
 * ----------------------------------
 * `docs/D-DEMO-CHECADOR.md`: el alta biométrica es del menú Usuario del
 * dispositivo o de HikConnect Teams. Aquí sólo se registra **que ya se hizo**,
 * para que el despacho sepa a quién le falta.
 */

import { useMemo, useState } from 'react';
import { X } from 'lucide-react';
import type { EmpleadoCartera } from '../../services/carteraApi';
import {
  validarDispositivo,
  type DispositivoChecador,
  type ProblemaDispositivo,
} from '../../services/dispositivosApi';
import Campo from '../cartera/Campo';
import { campoInput as campo, etiquetaCampo as etiqueta } from '../cartera/estilosCampo';

function problemaDe(problemas: ProblemaDispositivo[], campoNombre: ProblemaDispositivo['campo']) {
  return problemas.find((p) => p.campo === campoNombre)?.motivo ?? null;
}

export default function ModalDispositivo({
  dispositivo,
  empleados,
  serialesEnUso,
  onGuardar,
  onCerrar,
}: {
  /** `null` = alta. Con valor = edición. */
  dispositivo: DispositivoChecador | null;
  /** Los de la cartera del cliente, para elegir a quién enrolar. */
  empleados: EmpleadoCartera[];
  /** Seriales de los OTROS aparatos: el que se edita no choca consigo mismo. */
  serialesEnUso: string[];
  onGuardar: (d: DispositivoChecador) => Promise<void>;
  onCerrar: () => void;
}) {
  const esAlta = dispositivo === null;
  const [datos, setDatos] = useState<DispositivoChecador>(
    () =>
      dispositivo ?? {
        id: '',
        nombre: '',
        ip: '',
        puerto: 80,
        marca: 'Hikvision',
        modelo: '',
        serial: '',
        employee_nos: [],
        notas: '',
      },
  );
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof DispositivoChecador>(k: K, v: DispositivoChecador[K]) =>
    setDatos((d) => ({ ...d, [k]: v }));

  const problemas = useMemo(
    () => validarDispositivo(datos, serialesEnUso),
    [datos, serialesEnUso],
  );
  const puedeGuardar = problemas.length === 0 && !guardando;

  /**
   * Enrola o desenrola por la llave del CHECADOR.
   *
   * **La guarda del nulo va aquí y no sólo en el `disabled` del checkbox.** El
   * atributo es presentación: un test lo demostró metiendo `null` dentro de
   * `employee_nos` con un clic forzado, y ese `null` se habría escrito en
   * Firestore como un enrolado fantasma permanente —envenenando la llave que
   * G-02 construyó y ensuciando el cruce para siempre—. Un dato que no se puede
   * borrar desde la UI no se protege con un atributo.
   */
  const alternar = (employeeNo: string | null) => {
    if (!employeeNo) return;
    setDatos((d) => ({
      ...d,
      employee_nos: d.employee_nos.includes(employeeNo)
        ? d.employee_nos.filter((n) => n !== employeeNo)
        : [...d.employee_nos, employeeNo],
    }));
  };

  async function guardar() {
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);
    try {
      await onGuardar({ ...datos, nombre: datos.nombre.trim(), serial: datos.serial.trim() });
      onCerrar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el dispositivo');
      setGuardando(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-label={esAlta ? 'Alta de dispositivo' : `Editar ${datos.nombre}`}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 'var(--space-md)',
      }}
    >
      <div
        className="card"
        style={{
          width: 'min(720px, 100%)', maxHeight: '90vh', overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 'var(--space-md)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            {esAlta ? 'Nuevo dispositivo' : datos.nombre}
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
          <Campo label="Nombre *" ancho="2 1 260px">
            <input
              style={campo}
              value={datos.nombre}
              onChange={(e) => set('nombre', e.target.value)}
              placeholder="Entrada planta"
            />
          </Campo>
          <Campo label="Marca">
            <input style={campo} value={datos.marca} onChange={(e) => set('marca', e.target.value)} />
          </Campo>
          <Campo label="Modelo">
            <input
              style={campo}
              value={datos.modelo}
              onChange={(e) => set('modelo', e.target.value)}
              placeholder="DS-K1T321MFWX"
            />
          </Campo>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="IP en la red del cliente">
            <input
              style={campo}
              value={datos.ip}
              onChange={(e) => set('ip', e.target.value)}
              placeholder="192.168.1.64"
              aria-invalid={Boolean(problemaDe(problemas, 'ip'))}
            />
          </Campo>
          <Campo label="Puerto">
            <input
              type="number"
              style={campo}
              value={datos.puerto}
              onChange={(e) => set('puerto', Number(e.target.value))}
            />
          </Campo>
          <Campo label="Número de serie">
            <input
              style={campo}
              value={datos.serial}
              onChange={(e) => set('serial', e.target.value)}
              aria-invalid={Boolean(problemaDe(problemas, 'serial'))}
            />
          </Campo>
        </div>

        <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          La IP y el puerto se <strong>registran</strong> para que sepas dónde está el equipo.
          La app <strong>no se conecta</strong> al aparato: eso es la tarea D-08 y necesita el
          dispositivo en la misma red.
        </p>

        {problemas.map((p) => (
          <p
            key={p.campo}
            role="alert"
            style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}
          >
            {p.motivo}
          </p>
        ))}

        <fieldset style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)' }}>
          <legend style={{ ...etiqueta, marginBottom: 0, padding: '0 6px' }}>
            Empleados enrolados en este aparato
          </legend>

          {empleados.length === 0 && (
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Este cliente todavía no tiene empleados en la cartera.
            </p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {empleados.map((e) => {
              const vinculado = Boolean(e.employee_no);
              return (
                <label
                  key={e.empleado_no}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.86rem',
                    color: vinculado ? 'var(--text-primary)' : 'var(--text-muted)',
                    cursor: vinculado ? 'pointer' : 'not-allowed',
                  }}
                >
                  <input
                    type="checkbox"
                    disabled={!vinculado}
                    checked={vinculado && datos.employee_nos.includes(e.employee_no as string)}
                    onChange={() => alternar(e.employee_no)}
                  />
                  <span>{e.nombre}</span>
                  {vinculado ? (
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>
                      #{e.employee_no}
                    </span>
                  ) : (
                    // No se esconde: si faltara de la lista sin explicación, el
                    // operador lo buscaría creyendo que se borró.
                    <span style={{ color: 'var(--warning)', fontSize: '0.78rem' }}>
                      sin número de checador — captúralo en su ficha para poder enrolarlo
                    </span>
                  )}
                </label>
              );
            })}
          </div>

          <p style={{ margin: '8px 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Marcar aquí registra <strong>que la persona está dada de alta en el aparato</strong>.
            El rostro se captura <strong>en el dispositivo</strong> (menú Usuario → Agregar),
            no desde la app.
          </p>
        </fieldset>

        <Campo label="Notas" ancho="1 1 100%">
          <input style={campo} value={datos.notas} onChange={(e) => set('notas', e.target.value)} />
        </Campo>

        {error && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.85rem' }}>
            {error}
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
