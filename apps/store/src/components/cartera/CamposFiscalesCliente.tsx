/**
 * RFC, código postal y entidad federativa en el alta y la edición de cliente (C-01).
 *
 * Aparte de `ModalCliente` porque ése ya pasaba del tope de 300 líneas.
 *
 * **Obligatorios en el alta, opcionales en la edición**: un cliente guardado
 * antes de C-01 no los trae, y exigirlos para cambiarle el giro lo dejaría sin
 * poder guardarse por un campo de más. Lo que sí se rechaza siempre es un valor
 * mal formado. Un campo obligatorio vacío no pinta mensaje —lo dice el `*` de la
 * etiqueta y el botón apagado, igual que el identificador y la razón social—;
 * uno mal escrito sí, con el motivo.
 */

import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';
import {
  ENTIDADES_FEDERATIVAS,
  type DatosFiscales,
  problemaCodigoPostal,
  problemaEntidad,
  problemaRfc,
} from './datosFiscalesCliente';

const mensaje = { fontSize: '0.75rem', color: 'var(--danger)', margin: 0, flex: '1 1 100%' } as const;

export default function CamposFiscalesCliente({
  datos,
  regimen,
  obligatorio,
  onChange,
}: {
  datos: DatosFiscales;
  regimen: string;
  obligatorio: boolean;
  onChange: (cambio: DatosFiscales) => void;
}) {
  const rfc = datos.rfc ?? '';
  const cp = datos.codigo_postal ?? '';
  const entidad = datos.clave_entidad ?? '';
  // Sólo se explica lo MAL ESCRITO; lo vacío lo dice el asterisco.
  const errorRfc = rfc.trim() !== '' ? problemaRfc(rfc, regimen, false) : null;
  const errorCp = cp.trim() !== '' ? problemaCodigoPostal(cp, false) : null;
  const errorEntidad = entidad !== '' ? problemaEntidad(entidad, false) : null;
  const marca = obligatorio ? ' *' : '';

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
      <Campo label={`RFC${marca}`} ancho="1 1 200px">
        <input
          style={campo}
          value={rfc}
          maxLength={13}
          placeholder="12 moral · 13 física"
          autoCapitalize="characters"
          // Mayúsculas al teclear: lo que se ve es lo que se guarda.
          onChange={(e) => onChange({ rfc: e.target.value.toUpperCase() })}
        />
      </Campo>
      <Campo label={`Código postal${marca}`} ancho="1 1 140px">
        <input
          style={campo}
          value={cp}
          inputMode="numeric"
          maxLength={5}
          placeholder="Domicilio fiscal"
          onChange={(e) => onChange({ codigo_postal: e.target.value })}
        />
      </Campo>
      <Campo label={`Entidad federativa${marca}`} ancho="1 1 220px">
        <select
          style={campo}
          value={entidad}
          onChange={(e) => onChange({ clave_entidad: e.target.value })}
        >
          <option value="">{obligatorio ? 'Elige…' : 'Sin capturar'}</option>
          {/* Un valor guardado fuera del catálogo se enseña tal cual, con su
              error debajo, en vez de que el select lo pinte como vacío. */}
          {errorEntidad && <option value={entidad}>{entidad}</option>}
          {ENTIDADES_FEDERATIVAS.map((e) => (
            <option key={e.clave} value={e.clave}>{e.clave} · {e.nombre}</option>
          ))}
        </select>
      </Campo>
      {errorRfc && <p role="alert" style={mensaje}>{errorRfc}</p>}
      {errorCp && <p role="alert" style={mensaje}>{errorCp}</p>}
      {errorEntidad && <p role="alert" style={mensaje}>{errorEntidad}</p>}
    </div>
  );
}
