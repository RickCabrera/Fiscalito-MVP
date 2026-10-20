/**
 * Plantillas del envío de recibos del despacho (P4-13): asunto y cuerpo con las variables
 * {nombre}, {periodo} y {neto}; para WhatsApp, el nombre de la plantilla APROBADA por Meta
 * (su cuerpo recibe esos tres valores como {{1}}, {{2}}, {{3}} y su encabezado es el PDF).
 */

import { useEffect, useState } from 'react';
import {
  guardarPlantillaRecibo,
  listarPlantillasRecibo,
  type PlantillaRecibo,
} from '../../services/dispersionApi';

const campo: React.CSSProperties = {
  width: '100%', padding: 'var(--space-xs)', background: 'var(--bg-input)', color: 'var(--text-primary)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
};

export default function PlantillasRecibo() {
  const [plantillas, setPlantillas] = useState<PlantillaRecibo[] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    listarPlantillasRecibo()
      .then((r) => vivo && setPlantillas(r.plantillas))
      .catch((e: Error) => vivo && setError(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  const cambiar = (i: number, cambio: Partial<PlantillaRecibo>) =>
    setPlantillas((ps) => ps && ps.map((p, j) => (j === i ? { ...p, ...cambio } : p)));

  async function guardar(p: PlantillaRecibo) {
    setError(null);
    setAviso(null);
    try {
      await guardarPlantillaRecibo(p.canal, {
        asunto: p.asunto, cuerpo: p.cuerpo, plantilla_whatsapp: p.plantilla_whatsapp, idioma: p.idioma,
      });
      setAviso(`Plantilla de ${p.canal} guardada.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    }
  }

  if (!plantillas) return error ? <p role="alert">{error}</p> : <p style={{ color: 'var(--text-muted)' }}>Cargando…</p>;

  return (
    <div style={{ display: 'grid', gap: 'var(--space-sm)', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
      {plantillas.map((p, i) => (
        <fieldset key={p.canal} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
          <legend>{p.canal === 'correo' ? 'Correo' : 'WhatsApp'}</legend>
          {p.canal === 'correo' ? (
            <label style={{ fontSize: '0.8rem' }}>
              Asunto
              <input style={campo} value={p.asunto} onChange={(e) => cambiar(i, { asunto: e.target.value })} />
            </label>
          ) : (
            <label style={{ fontSize: '0.8rem' }}>
              Plantilla aprobada (Meta) / Content SID (Twilio)
              <input
                style={campo}
                value={p.plantilla_whatsapp}
                onChange={(e) => cambiar(i, { plantilla_whatsapp: e.target.value })}
              />
            </label>
          )}
          <label style={{ fontSize: '0.8rem' }}>
            {p.canal === 'correo' ? 'Cuerpo (HTML)' : 'Texto de referencia'}
            <textarea style={campo} rows={4} value={p.cuerpo} onChange={(e) => cambiar(i, { cuerpo: e.target.value })} />
          </label>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>Variables: {'{nombre} {periodo} {neto}'}</p>
          <button className="btn-secondary" onClick={() => guardar(p)}>
            Guardar
          </button>
        </fieldset>
      ))}
      {aviso && <p style={{ margin: 0, color: 'var(--success)' }}>{aviso}</p>}
      {error && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)' }}>
          {error}
        </p>
      )}
    </div>
  );
}
