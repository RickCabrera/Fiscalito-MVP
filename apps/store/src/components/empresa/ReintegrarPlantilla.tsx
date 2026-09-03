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
 * POR QUÉ ES UN BOTÓN Y NO UN EFECTO DE GUARDAR
 * ----------------------------------------------
 * Subirle el SBC a un trabajador es un **movimiento 07 ante el IMSS** por cada
 * uno. Que eso ocurra como efecto colateral de guardar un formulario sería
 * esconder un trámite detrás de un `onSubmit`. Aquí se calcula, se enseña quién
 * cambia y de cuánto a cuánto, y se guarda sólo cuando el operador lo pide.
 *
 * Es la misma política que `sembrar()` de la cartera, y la misma que O-04 usó
 * para no emitir altas que nadie pidió.
 */

import { useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
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

export default function ReintegrarPlantilla({ cartera }: { cartera: CarteraContextType }) {
  const [corriendo, setCorriendo] = useState(false);
  const [resultado, setResultado] = useState<ResultadoReintegracion | null>(null);
  const [error, setError] = useState<string | null>(null);

  const empleados = cartera.clientePorId(ID_EMPRESA)?.empleados ?? [];

  const correr = async () => {
    if (corriendo || cartera.soloLectura || empleados.length === 0) return;
    setCorriendo(true);
    setError(null);
    setResultado(null);
    try {
      const r = await reintegrarPlantilla(empleados, cartera.empresa.parametros);
      // Se guarda SÓLO a quien cambió: escribir los demás dispararía una
      // escritura por empleado sin nada que escribir.
      for (const cambio of r.cambios) {
        const nuevo = r.empleados.find((e) => e.empleado_no === cambio.empleadoNo);
        if (nuevo) await cartera.guardarEmpleado(ID_EMPRESA, nuevo);
      }
      setResultado(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo reintegrar la plantilla.');
    } finally {
      setCorriendo(false);
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
        Subir el SBC de un trabajador es un <strong>aviso de modificación de salario ante el
        IMSS</strong> (movimiento 07) por cada uno. Por eso no se hace solo: aquí se ve quién
        cambia antes de guardarlo.
      </p>

      <div>
        <button
          className="btn-secondary"
          onClick={correr}
          disabled={corriendo || cartera.soloLectura || empleados.length === 0}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
        >
          <RefreshCw size={16} />
          {corriendo
            ? 'Reintegrando…'
            : `Reintegrar la plantilla (${empleados.length} ${
                empleados.length === 1 ? 'empleado' : 'empleados'
              })`}
        </button>
      </div>

      {error && (
        <p role="alert" style={{ fontSize: '0.82rem', color: 'var(--danger)', margin: 0 }}>
          {error}
        </p>
      )}

      {resultado && (
        <div role="status" style={{ fontSize: '0.82rem' }}>
          {resultado.cambios.length === 0 ? (
            <span>
              Se revisaron {resultado.revisados} y <strong>ninguno cambió</strong>: la
              plantilla ya estaba integrada con estos parámetros.
            </span>
          ) : (
            <>
              <strong>
                {resultado.cambios.length} de {resultado.revisados} cambiaron de SBC
              </strong>{' '}
              y se guardaron. Cada uno necesita su aviso de modificación ante el IMSS:
              <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                {resultado.cambios.map((c) => (
                  <li key={c.empleadoNo}>
                    {c.nombre} ({c.empleadoNo}): {c.anterior} → <strong>{c.nuevo}</strong>
                  </li>
                ))}
              </ul>
            </>
          )}

          {resultado.fallidos.length > 0 && (
            <p style={{ color: 'var(--danger)', marginTop: 'var(--space-xs)' }}>
              {resultado.fallidos.length} no se pudieron integrar y{' '}
              <strong>quedaron como estaban</strong>:{' '}
              {resultado.fallidos.map((f) => `${f.nombre} (${f.fallo})`).join('; ')}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
