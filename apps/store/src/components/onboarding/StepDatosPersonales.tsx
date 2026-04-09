/** Step 3: Formulario de datos personales (nombre, telefono, actividad, CP) */

import { labelStyle } from './styles';

interface StepDatosPersonalesProps {
  nombre: string;
  setNombre: (v: string) => void;
  telefono: string;
  setTelefono: (v: string) => void;
  actividad: string;
  setActividad: (v: string) => void;
  cp: string;
  setCp: (v: string) => void;
}

export default function StepDatosPersonales({
  nombre, setNombre, telefono, setTelefono, actividad, setActividad, cp, setCp,
}: StepDatosPersonalesProps) {
  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        Datos personales
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        Informacion basica para tu perfil.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <label style={labelStyle}>Nombre completo <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input className="input-field" placeholder="Tu nombre completo" value={nombre}
            onChange={(e) => setNombre(e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Telefono <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(opcional)</span></label>
          <input className="input-field" placeholder="10 digitos" value={telefono}
            onChange={(e) => setTelefono(e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Actividad economica</label>
          <input className="input-field" placeholder="Ej: Diseno grafico, Consultoria..." value={actividad}
            onChange={(e) => setActividad(e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Codigo postal (domicilio fiscal)</label>
          <input className="input-field" placeholder="00000" value={cp}
            onChange={(e) => setCp(e.target.value)} maxLength={5}
            style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: 2 }} />
        </div>
      </div>
    </div>
  );
}
