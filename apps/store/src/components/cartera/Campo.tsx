/**
 * Campos de formulario con la etiqueta **asociada al control**.
 *
 * `htmlFor`/`id` no es adorno: sin ellos un lector de pantalla lee el input sin
 * nombre y `getByLabelText` no encuentra nada — que es como se descubrió, al
 * escribir los tests que faltaban. `useId` da un id estable por instancia y
 * único entre modales abiertos.
 *
 * Vive aparte porque los dos modales de la cartera lo necesitan: tenerlo dos
 * veces sería la segunda copia de la misma corrección, y la que se olvide de
 * arreglar la próxima vez.
 */

import { cloneElement, useId } from 'react';
import { etiquetaCampo } from './estilosCampo';

export default function Campo({
  label, children, ancho = '1 1 200px',
}: {
  label: string;
  children: React.ReactElement<{ id?: string }>;
  ancho?: string;
}) {
  const id = useId();
  return (
    <div style={{ flex: ancho, minWidth: 0 }}>
      <label htmlFor={id} style={etiquetaCampo}>{label}</label>
      {cloneElement(children, { id })}
    </div>
  );
}
