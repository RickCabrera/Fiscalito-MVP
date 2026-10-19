interface StepConfirmarProps {
  nombre: string;
  nombreDespacho: string;
  telefono: string;
}

/** Resumen del alta del despacho antes de guardar. */
export default function StepConfirmar({ nombre, nombreDespacho, telefono }: StepConfirmarProps) {
  const rows: { label: string; value: string }[] = [
    { label: 'Tipo', value: '🧾 Despacho / Contador' },
    { label: 'Contador', value: nombre },
    { label: 'Despacho', value: nombreDespacho },
  ];
  if (telefono) rows.push({ label: 'Telefono', value: telefono });

  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        Confirma los datos del despacho
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        Verifica que todo este correcto. Podras editarlo despues en tu perfil.
      </p>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {rows.map((row, i) => (
          <div key={row.label} style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 24px',
            borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{row.label}</span>
            <span style={{
              fontSize: '0.95rem',
              fontWeight: 600,
            }}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
