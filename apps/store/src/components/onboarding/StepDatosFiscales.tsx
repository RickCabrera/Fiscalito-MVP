/** Step 2: Formulario de datos fiscales (RFC, regimen, campos PYME) */

import { labelStyle } from './styles';

const NUM_EMPLEADOS_OPTIONS = ['Solo yo', '2-5', '6-20', '21+'];

interface StepDatosFiscalesProps {
  allowedRegimens: { code: string; name: string }[];
  rfc: string;
  setRfc: (v: string) => void;
  regimen: string;
  setRegimen: (v: string) => void;
  nombreNegocio: string;
  setNombreNegocio: (v: string) => void;
  numEmpleados: string;
  setNumEmpleados: (v: string) => void;
  isPyme: boolean;
}

export default function StepDatosFiscales({
  allowedRegimens, rfc, setRfc, regimen, setRegimen,
  nombreNegocio, setNombreNegocio, numEmpleados, setNumEmpleados, isPyme,
}: StepDatosFiscalesProps) {
  const rfcLen = rfc.length;
  const rfcHint = rfcLen === 0 ? '' : rfcLen === 12 ? 'Persona moral' : rfcLen === 13 ? 'Persona fisica' : 'El RFC debe tener 12 o 13 caracteres';
  const rfcError = rfcLen > 0 && rfcLen !== 12 && rfcLen !== 13;

  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        Datos fiscales
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        Necesitamos tu RFC y regimen para calcular tus obligaciones correctamente.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* RFC */}
        <div>
          <label style={labelStyle}>RFC</label>
          <input
            className="input-field"
            placeholder="XAXX010101000"
            value={rfc}
            onChange={(e) => setRfc(e.target.value.toUpperCase())}
            maxLength={13}
            style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}
          />
          {rfcHint && (
            <span style={{ fontSize: '0.78rem', marginTop: 4, display: 'block', color: rfcError ? 'var(--warning)' : 'var(--text-muted)' }}>
              {rfcHint}
            </span>
          )}
        </div>

        {/* Regimen */}
        <div>
          <label style={labelStyle}>Regimen fiscal</label>
          <select
            className="input-field"
            value={regimen}
            onChange={(e) => setRegimen(e.target.value)}
            style={{ cursor: 'pointer' }}
          >
            <option value="">Seleccionar regimen...</option>
            {allowedRegimens.map((r) => (
              <option key={r.code} value={r.code}>{r.code} — {r.name}</option>
            ))}
          </select>
        </div>

        {/* PYME extra fields */}
        {isPyme && (
          <>
            <div>
              <label style={labelStyle}>Nombre del negocio</label>
              <input
                className="input-field"
                placeholder="Mi Empresa S.A. de C.V."
                value={nombreNegocio}
                onChange={(e) => setNombreNegocio(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Numero de empleados</label>
              <select
                className="input-field"
                value={numEmpleados}
                onChange={(e) => setNumEmpleados(e.target.value)}
                style={{ cursor: 'pointer' }}
              >
                <option value="">Seleccionar...</option>
                {NUM_EMPLEADOS_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
