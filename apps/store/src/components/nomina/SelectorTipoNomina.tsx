/**
 * Qué nómina se corre (P4): ordinaria, asimilados, extraordinaria, o las de un solo
 * pago —finiquito, aguinaldo y PTU— que tienen su propia captura. Presentacional.
 */

export type VistaNomina =
  | 'ordinaria'
  | 'asimilados'
  | 'extraordinaria'
  | 'finiquito'
  | 'aguinaldo'
  | 'ptu'
  | 'historial';

const VISTAS: { id: VistaNomina; texto: string; ayuda: string }[] = [
  { id: 'ordinaria', texto: 'Ordinaria', ayuda: 'Sueldos y salarios (régimen 02) del periodo, con checador.' },
  { id: 'asimilados', texto: 'Asimilados', ayuda: 'Art. 94 LISR: ISR sin cuotas del IMSS ni subsidio.' },
  { id: 'extraordinaria', texto: 'Extraordinaria', ayuda: 'Un pago fuera del periodo ordinario (CFDI tipo E).' },
  { id: 'finiquito', texto: 'Finiquito', ayuda: 'Separación: proporcionales, prima de antigüedad e indemnizaciones.' },
  { id: 'aguinaldo', texto: 'Aguinaldo', ayuda: 'Art. 87 LFT, 30 UMA exentas.' },
  { id: 'ptu', texto: 'PTU', ayuda: 'Reparto de utilidades: 50 % días, 50 % salarios, con tope.' },
  { id: 'historial', texto: 'Historial', ayuda: 'Nóminas guardadas del cliente: abrir, cerrar y comparar.' },
];

export default function SelectorTipoNomina({
  vista,
  onCambiar,
}: {
  vista: VistaNomina;
  onCambiar: (v: VistaNomina) => void;
}) {
  const actual = VISTAS.find((v) => v.id === vista);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
      <div role="tablist" aria-label="Tipo de nómina" style={{ display: 'flex', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
        {VISTAS.map((v) => (
          <button
            key={v.id}
            role="tab"
            aria-selected={vista === v.id}
            onClick={() => onCambiar(v.id)}
            style={{
              padding: 'var(--space-xs) var(--space-md)',
              background: vista === v.id ? 'var(--accent-active)' : 'transparent',
              color: vista === v.id ? 'var(--text-on-accent)' : 'var(--text-secondary)',
              border: `1px solid ${vista === v.id ? 'var(--accent-active)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            {v.texto}
          </button>
        ))}
      </div>
      {actual && (
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>{actual.ayuda}</p>
      )}
    </div>
  );
}
