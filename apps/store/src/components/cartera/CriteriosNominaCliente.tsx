/**
 * Bloque "Criterios de nómina" de la ficha del cliente (P4, DP-3).
 *
 * Las preguntas §D26 (periodos parciales), §D27 (febrero), §D28 (prestaciones), el
 * método de ISR de aguinaldo y PTU y el remanente de PTU no tienen respuesta legal única:
 * son criterio del despacho. Cada opción se pinta con la explicación que manda el backend
 * (`GET /nomina/criterios`), que también fija los defaults: aquí no se escribe ninguno.
 */

import { useEffect, useState } from 'react';
import type { ClienteCartera } from '../../services/carteraApi';
import { obtenerCriterios, type CriteriosDisponibles } from '../../services/nominaApi';
import { labelStyle } from '../../utils/styles';

const TITULOS: Record<string, string> = {
  parcial: 'Altas y bajas a mitad de periodo (§D26)',
  febrero: 'Quincenas de 13, 14 o 16 días (§D27)',
  prestaciones: 'Prestaciones del patrón contra la ficha del empleado (§D28)',
  isr_extraordinario: 'ISR de aguinaldo y PTU',
  ptu_remanente: 'Lo que excede el tope de PTU',
};

export default function CriteriosNominaCliente({
  cliente,
  soloLectura,
  onGuardar,
}: {
  cliente: ClienteCartera;
  soloLectura: boolean;
  onGuardar: (c: Omit<ClienteCartera, 'empleados'>) => Promise<void>;
}) {
  const [disponibles, setDisponibles] = useState<CriteriosDisponibles | null>(null);
  const [elegidos, setElegidos] = useState<Record<string, string>>(cliente.criterios_nomina ?? {});
  const [estado, setEstado] = useState<{ error?: string; guardado?: boolean; ocupado?: boolean }>({});

  useEffect(() => {
    let cancelado = false;
    // `Promise.resolve().then`: un fallo síncrono también cae al `catch` y no tumba la ficha.
    Promise.resolve()
      .then(obtenerCriterios)
      .then((d) => !cancelado && d?.opciones && setDisponibles(d))
      .catch((e: Error) => !cancelado && setEstado({ error: e.message }));
    return () => {
      cancelado = true;
    };
  }, []);

  const guardar = async () => {
    if (!disponibles) return;
    setEstado({ ocupado: true });
    try {
      await onGuardar({ ...cliente, criterios_nomina: { ...disponibles.defaults, ...elegidos } });
      setEstado({ guardado: true });
    } catch (e) {
      setEstado({ error: (e as Error).message });
    }
  };

  return (
    <section className="card" style={{ marginBottom: 'var(--space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <h2 style={{ margin: 0, fontSize: '1rem' }}>Criterios de nómina</h2>
      {!disponibles && !estado.error && <p style={{ margin: 0, color: 'var(--text-muted)' }}>Cargando criterios…</p>}
      {estado.error && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)' }}>
          {estado.error}
        </p>
      )}
      {disponibles &&
        Object.entries(disponibles.opciones).map(([criterio, opciones]) => {
          const valor = elegidos[criterio] ?? disponibles.defaults[criterio];
          return (
            <label key={criterio} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={labelStyle}>{TITULOS[criterio] ?? criterio}</span>
              <select
                className="input-field"
                value={valor}
                disabled={soloLectura}
                onChange={(e) => {
                  setElegidos({ ...elegidos, [criterio]: e.target.value });
                  setEstado({});
                }}
              >
                {Object.keys(opciones).map((op) => (
                  <option key={op} value={op}>
                    {op === disponibles.defaults[criterio] ? `${op} (default)` : op}
                  </option>
                ))}
              </select>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{opciones[valor]}</span>
            </label>
          );
        })}
      {disponibles && !soloLectura && (
        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
          <button className="btn-primary" disabled={estado.ocupado} onClick={() => void guardar()}>
            Guardar criterios
          </button>
          {estado.guardado && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}>Guardado.</span>}
        </div>
      )}
    </section>
  );
}
