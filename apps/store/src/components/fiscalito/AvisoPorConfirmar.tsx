/**
 * Aviso de fuente por confirmar (O12): cuando el motor usó un índice o una tasa que
 * viene de fuente secundaria (INPC sin cotejar con el boletín del INEGI, tasa de
 * recargos de un año cuya LIF no se consultó, ISN de un estado no verificado), la
 * respuesta trae `por_confirmar` y la lista de esas fuentes. Aquí sólo se pinta.
 */

interface Props {
  fuentes: string[];
}

export default function AvisoPorConfirmar({ fuentes }: Props) {
  if (fuentes.length === 0) return null;
  return (
    <div role="note" aria-label="Fuente por confirmar" style={{
      border: '1px solid var(--warning)', borderRadius: 8, padding: '8px 12px',
      fontSize: '0.75rem', color: 'var(--warning)',
    }}>
      <strong>Por confirmar:</strong> el cálculo usa índices o tasas de fuente secundaria.
      <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
        {fuentes.map((f) => <li key={f}>{f}</li>)}
      </ul>
    </div>
  );
}
