/** Step 4: Confirmacion — resumen del perfil antes de guardar */

interface StepConfirmarProps {
  tipoLabel: string;
  tipoIcon: string;
  allowedRegimens: { code: string; name: string }[];
  /** E-05: un despacho no captura RFC ni régimen; imprimirlos daría un renglón vacío. */
  esContador: boolean;
  rfc: string;
  regimen: string;
  nombre: string;
  telefono: string;
  actividad: string;
  cp: string;
  nombreNegocio: string;
  numEmpleados: string;
  nombreDespacho: string;
}

export default function StepConfirmar({
  tipoLabel, tipoIcon, allowedRegimens, esContador,
  rfc, regimen, nombre, telefono, actividad, cp, nombreNegocio, numEmpleados, nombreDespacho,
}: StepConfirmarProps) {
  const regimenName = allowedRegimens.find((r) => r.code === regimen)?.name || regimen;

  const rows: { label: string; value: string }[] = [
    { label: 'Tipo', value: `${tipoIcon} ${tipoLabel}` },
    { label: 'Nombre', value: nombre },
  ];
  // Sin la guarda, el resumen de un despacho mostraba "RFC:" en blanco y un
  // "Regimen: —" suelto, que es peor que no mostrar el renglón.
  if (!esContador) {
    rows.push({ label: 'RFC', value: rfc });
    rows.push({ label: 'Regimen', value: `${regimen} — ${regimenName}` });
  }
  if (actividad) rows.push({ label: 'Actividad', value: actividad });
  if (cp) rows.push({ label: 'Codigo postal', value: cp });
  if (telefono) rows.push({ label: 'Telefono', value: telefono });
  if (nombreDespacho) rows.push({ label: 'Despacho', value: nombreDespacho });
  if (nombreNegocio) rows.push({ label: 'Negocio', value: nombreNegocio });
  if (numEmpleados) rows.push({ label: 'Empleados', value: numEmpleados });

  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        Confirma tu perfil
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
              fontFamily: row.label === 'RFC' || row.label === 'Codigo postal' ? "'JetBrains Mono', monospace" : 'inherit',
            }}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
