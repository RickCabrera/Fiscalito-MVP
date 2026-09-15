/**
 * El paso 4: elegir formato y exportar. (O-04)
 *
 * **El PDF se queda**, y va primero: es el documento que el contador y el
 * patrón leen. Los TXT son para las máquinas —el IMSS y el banco— y se eligen
 * de una lista.
 *
 * LO QUE ESTA PANTALLA TIENE QUE DECIR ANTES DE DESCARGAR
 * -------------------------------------------------------
 * Tres cosas, y ninguna es adorno:
 *
 * 1. **De dónde salió el layout.** Un formato `por-validar` lo lleva escrito en
 *    la lista, y el operador tiene que verlo antes de mandarle el archivo a su
 *    banco.
 * 2. **Quién quedó fuera.** Un empleado sin NSS o sin apellidos capturados no se
 *    exporta. Quedar fuera en silencio es el modo de falla que este repo lleva
 *    cinco épicas evitando.
 * 3. **Qué nombres se cambiaron.** "MUÑOZ" → "MUNOZ" en un movimiento
 *    afiliatorio no es una decisión de codificación: es un cambio de apellido en
 *    un documento de identidad laboral.
 *
 * LA DESCARGA ES DEL NAVEGADOR, Y EL ARCHIVO NO SE REGISTRA EN NINGÚN LADO
 * ------------------------------------------------------------------------
 * `Blob` + `URL.createObjectURL`. El contenido lleva NSS y salarios, así que
 * **no se loguea, no se manda a ninguna parte y no se guarda**: se arma en
 * memoria, se descarga y se libera la URL.
 */

import { useState } from 'react';
import { AlertTriangle, FileDown, Info } from 'lucide-react';
import { FORMATOS } from '../../services/exportadores/registro';
import { descargarBytes } from '../../services/exportadores/descargar';
import type { ArchivoGenerado, DatosExportacion } from '../../services/exportadores/tipos';
import { campoInput } from '../cartera/estilosCampo';

const ACCION: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 8 };

/** Envuelve `descargarBytes`, que T5 sacó de aquí para compartirlo con la DIOT. */
function descargar(archivo: ArchivoGenerado): void {
  descargarBytes(archivo.nombre, archivo.bytes);
}

export default function SelectorExportacion({
  datos,
  deshabilitado,
}: {
  datos: DatosExportacion | null;
  deshabilitado: boolean;
}) {
  const [formatoId, setFormatoId] = useState(FORMATOS[0].id);
  const [ultimo, setUltimo] = useState<ArchivoGenerado | null>(null);
  const [error, setError] = useState<string | null>(null);

  const formato = FORMATOS.find((f) => f.id === formatoId)!;
  const porValidar = formato.fuente.estado === 'por-validar';

  const exportar = () => {
    // Guarda propia, no sólo `disabled`: es una propiedad del DOM, no una
    // garantía del handler. T8 suma `proximamente` por la misma razón: un
    // `<option disabled>` se puede saltar con `fireEvent.change` o desde la
    // consola, y del otro lado hay un `generar` que levanta.
    if (!datos || deshabilitado || formato.proximamente) return;
    setError(null);
    try {
      const archivo = formato.generar(datos);
      setUltimo(archivo);
      descargar(archivo);
    } catch (e) {
      // Los generadores LEVANTAN en vez de truncar —un apellido cortado es un
      // movimiento sobre otra persona— así que el error es información, no un
      // fallo que esconder.
      setUltimo(null);
      setError(e instanceof Error ? e.message : 'No se pudo generar el archivo.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          className="input-field"
          style={{ ...campoInput, flex: '1 1 320px', width: 'auto' }}
          aria-label="Formato de exportación"
          value={formatoId}
          onChange={(e) => {
            setFormatoId(e.target.value);
            setUltimo(null);
            setError(null);
          }}
        >
          {FORMATOS.map((f) => (
            // T8: los movimientos que todavía no se emiten —bajas (02) y
            // modificaciones de salario (07)— aparecen en la lista y NO se
            // pueden elegir. Aparecen porque "¿y las bajas?" es la primera
            // pregunta del operador, y una lista donde no están la contesta
            // con silencio. `disabled` es lo que impide llamar a un `generar`
            // que levanta; el motivo va en el `title` y en la etiqueta.
            <option key={f.id} value={f.id} disabled={!!f.proximamente} title={f.proximamente}>
              {f.nombre}
              {f.proximamente ? '  — Próximamente' : ''}
              {f.fuente.estado === 'por-validar' ? '  ⚠ por validar' : ''}
            </option>
          ))}
        </select>
        <button
          className="btn-secondary"
          onClick={exportar}
          disabled={deshabilitado || !datos}
          style={ACCION}
        >
          <FileDown size={16} /> Exportar TXT
        </button>
      </div>

      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0 }}>
        {formato.descripcion}
      </p>

      {porValidar ? (
        <p
          role="status"
          style={{
            display: 'flex', gap: 'var(--space-xs)', alignItems: 'flex-start',
            fontSize: '0.8rem', color: 'var(--warning)', margin: 0,
          }}
        >
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>
            <strong>Por validar contra el manual vigente del banco.</strong>{' '}
            {formato.fuente.cita}
          </span>
        </p>
      ) : (
        <p
          style={{
            display: 'flex', gap: 'var(--space-xs)', alignItems: 'flex-start',
            fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0,
          }}
        >
          <Info size={13} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{formato.fuente.cita}</span>
        </p>
      )}

      {error && (
        <p role="alert" style={{ fontSize: '0.82rem', color: 'var(--danger)', margin: 0 }}>
          {error}
        </p>
      )}

      {ultimo && ultimo.noExportables.length > 0 && (
        <div
          role="status"
          style={{
            fontSize: '0.82rem', color: 'var(--warning)',
            background: 'var(--bg-input)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)',
          }}
        >
          <strong>
            {ultimo.noExportables.length}{' '}
            {ultimo.noExportables.length === 1 ? 'empleado no salió' : 'empleados no salieron'}{' '}
            en el archivo:
          </strong>
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
            {ultimo.noExportables.map((n) => (
              <li key={n.empleadoNo}>
                {n.nombre} ({n.empleadoNo}) — {n.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      {ultimo && ultimo.transliterados.length > 0 && (
        <div
          role="status"
          style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
        >
          <strong>Se quitaron acentos y eñes</strong> porque el IMSS lee estos archivos en
          ASCII. Revisa que sigan siendo la persona correcta:{' '}
          {ultimo.transliterados.join(', ')}.
        </div>
      )}
    </div>
  );
}
