/**
 * "Cambiaste las prestaciones — la plantilla que ya existe sigue en el SBC
 * viejo." (O-cierre)
 *
 * El aviso va **siempre visible**, no sólo cuando se detecta un desfase, y esa
 * es la decisión: detectar el desfase exige preguntarle al motor por cada
 * empleado, y hacerlo al montar la pantalla dispararía N llamadas cada vez que
 * alguien entra a Perfil. El aviso es barato y honesto; la comprobación la pide
 * el operador.
 *
 * SON DOS PASOS, Y EL PRIMERO NO ESCRIBE NADA
 * --------------------------------------------
 * Calcular enseña la lista; **guardar es un segundo clic**. La primera versión
 * decía en pantalla "aquí se ve quién cambia antes de guardarlo" y guardaba en
 * el mismo handler — una promesa que el código no cumplía, y el revisor de
 * cierre la cazó.
 *
 * No es ceremonia: subirle el SBC a un trabajador es un **movimiento 07
 * (modificación de salario) ante el IMSS** por cada uno, y esta app **no lo
 * puede generar** (O-04 lo dejó abierto por falta de historial de SBC). Quien
 * pulsa Guardar está adquiriendo un trámite que va a tener que presentar a
 * mano, así que tiene derecho a ver la lista primero.
 *
 * LAS BAJADAS NO SE GUARDAN
 * -------------------------
 * `reintegrarPlantilla` las separa y no las aplica (§D28). Se enseñan porque
 * una bajada de SBC **también** es un movimiento 07 y es la dirección
 * peligrosa: subintegra. Que se vea distinta de una subida, y no como un
 * renglón más de la misma lista.
 */

import { useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, RefreshCw, Save } from 'lucide-react';
import type { CarteraContextType } from '../../context/carteraStore';
import {
  reintegrarPlantilla,
  type ResultadoReintegracion,
} from '../../services/reintegrarPlantilla';
import { ID_EMPRESA } from '../../services/modoEmpresa';

const AVISO: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--space-sm)',
  alignItems: 'flex-start',
  fontSize: '0.82rem',
  color: 'var(--warning)',
  margin: 0,
};

const ACCION: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 8 };

export default function ReintegrarPlantilla({ cartera }: { cartera: CarteraContextType }) {
  const [calculando, setCalculando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [previo, setPrevio] = useState<ResultadoReintegracion | null>(null);
  const [guardados, setGuardados] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const empleados = cartera.clientePorId(ID_EMPRESA)?.empleados ?? [];
  const bloqueado = cartera.soloLectura || empleados.length === 0;

  /** Paso 1: calcular. **No escribe nada.** */
  const calcular = async () => {
    if (calculando || bloqueado) return;
    setCalculando(true);
    setError(null);
    setPrevio(null);
    setGuardados(0);
    try {
      setPrevio(await reintegrarPlantilla(empleados, cartera.empresa.parametros));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo calcular la reintegración.');
    } finally {
      setCalculando(false);
    }
  };

  /** Paso 2: guardar, y sólo a los que suben. */
  const guardar = async () => {
    if (!previo || guardando || bloqueado) return;
    setGuardando(true);
    setError(null);
    try {
      for (const cambio of previo.cambios) {
        const nuevo = previo.empleados.find((e) => e.empleado_no === cambio.empleadoNo);
        if (nuevo) await cartera.guardarEmpleado(ID_EMPRESA, nuevo);
      }
      setGuardados(previo.cambios.length);
      setPrevio(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron guardar los cambios.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div
      className="card"
      style={{
        padding: 'var(--space-lg)',
        marginTop: 'var(--space-md)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-sm)',
      }}
    >
      <h3 style={{ margin: 0, fontSize: '1rem' }}>Salario integrado de la plantilla</h3>

      <p style={AVISO}>
        <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
        <span>
          Cambiar el aguinaldo, la prima vacacional o la tabla de vacaciones{' '}
          <strong>no recalcula el SBC de quien ya está dado de alta</strong>. Hasta que se
          reintegre, la nómina se calcula con el salario integrado guardado, y si las
          prestaciones subieron las cuotas salen <strong>por debajo</strong> de lo que
          corresponde.
        </span>
      </p>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
        Cada cambio de SBC —<strong>suba o baje</strong>— es un aviso de modificación de
        salario ante el IMSS (movimiento 07), y esta app todavía{' '}
        <strong>no lo puede generar</strong>: hay que presentarlo aparte. Por eso son dos
        pasos, y el primero no guarda nada.
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <button
          className="btn-secondary"
          onClick={calcular}
          disabled={calculando || guardando || bloqueado}
          style={ACCION}
        >
          <RefreshCw size={16} />
          {calculando
            ? 'Calculando…'
            : `Calcular (${empleados.length} ${
                empleados.length === 1 ? 'empleado' : 'empleados'
              })`}
        </button>

        {previo && previo.cambios.length > 0 && (
          <button className="btn-primary" onClick={guardar} disabled={guardando} style={ACCION}>
            <Save size={16} />
            {guardando
              ? 'Guardando…'
              : `Guardar ${previo.cambios.length} ${
                  previo.cambios.length === 1 ? 'cambio' : 'cambios'
                }`}
          </button>
        )}
      </div>

      {error && (
        <p role="alert" style={{ fontSize: '0.82rem', color: 'var(--danger)', margin: 0 }}>
          {error}
        </p>
      )}

      {guardados > 0 && (
        <p role="status" style={{ fontSize: '0.82rem', color: 'var(--success)', margin: 0 }}>
          Se guardaron {guardados} {guardados === 1 ? 'cambio' : 'cambios'} de SBC. Cada uno
          necesita su aviso de modificación ante el IMSS.
        </p>
      )}

      {previo && (
        <div role="status" style={{ fontSize: '0.82rem' }}>
          {previo.cambios.length === 0 && previo.bajarian.length === 0 ? (
            <span>
              Se revisaron {previo.revisados} y <strong>ninguno cambia</strong>: la plantilla
              ya está integrada con estos parámetros.
            </span>
          ) : (
            <>
              {previo.cambios.length > 0 && (
                <>
                  <strong>
                    {previo.cambios.length} de {previo.revisados} suben de SBC
                  </strong>{' '}
                  — todavía no se ha guardado nada:
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                    {previo.cambios.map((c) => (
                      <li key={c.empleadoNo}>
                        <ArrowUp
                          size={12}
                          aria-label="sube"
                          style={{ verticalAlign: 'middle', color: 'var(--success)' }}
                        />{' '}
                        {c.nombre} ({c.empleadoNo}): {c.anterior} → <strong>{c.nuevo}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {previo.bajarian.length > 0 && (
                <div style={{ marginTop: 'var(--space-sm)', color: 'var(--warning)' }}>
                  <strong>
                    {previo.bajarian.length} bajarían de SBC y NO se van a guardar.
                  </strong>{' '}
                  Bajar un salario integrado subintegra las cuotas, así que no se hace en
                  lote: revísalos uno por uno en su ficha.
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                    {previo.bajarian.map((c) => (
                      <li key={c.empleadoNo}>
                        <ArrowDown size={12} aria-label="baja" style={{ verticalAlign: 'middle' }} />{' '}
                        {c.nombre} ({c.empleadoNo}): {c.anterior} → {c.nuevo}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {previo.fallidos.length > 0 && (
            <p style={{ color: 'var(--danger)', marginTop: 'var(--space-xs)' }}>
              {previo.fallidos.length} no se pudieron integrar y{' '}
              <strong>quedaron como estaban</strong>:{' '}
              {previo.fallidos.map((f) => `${f.nombre} (${f.fallo})`).join('; ')}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
