/**
 * Los parámetros salariales del patrón. (O-03)
 *
 * QUÉ SE CONFIGURA AQUÍ Y QUÉ NO — LA MITAD DE ABAJO ES LA IMPORTANTE
 * -------------------------------------------------------------------
 * Aquí van las **prestaciones**, que son política del patrón: días de
 * aguinaldo, prima vacacional, escala de vacaciones, horario del checador y
 * periodicidad de pago. La ley les fija un piso y el patrón puede dar más.
 *
 * **Las tablas de ISR, las cuotas del IMSS, la UMA y el salario mínimo NO se
 * configuran**, y la pantalla lo dice. Son de ley, viven en el motor con su
 * fuente publicada y se actualizan con el DOF — no con un formulario. Un campo
 * editable ahí sería la puerta para que alguien "ajuste" un impuesto.
 *
 * LOS DÍAS DE VACACIONES NO SE RESUELVEN AQUÍ
 * -------------------------------------------
 * Se captura la escala y se manda **entera** a `POST /nomina/sbc` junto con la
 * antigüedad; el backend devuelve `dias_vacaciones_aplicados`. Buscar el
 * renglón en TypeScript sería una segunda implementación de la misma búsqueda,
 * y `vacaciones_efectivas` ya define `0 = los de ley`, que con una tabla sería
 * un centinela ambiguo.
 */

import { Plus, Trash2 } from 'lucide-react';
import Campo from '../cartera/Campo';
import { campoInput } from '../cartera/estilosCampo';
import type { ParametrosSalariales } from '../../services/carteraApi';
import { PERIODICIDADES, diasDeLey, erroresDeParametros } from './validacionEmpresa';

const FILA: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 'var(--space-md)',
  alignItems: 'flex-end',
};

const DIAS_SEMANA = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

export default function ParametrosSalarialesForm({
  valor,
  clavePeriodicidad,
  onCambio,
  onCambioPeriodicidad,
}: {
  valor: ParametrosSalariales;
  clavePeriodicidad: string;
  onCambio: (p: ParametrosSalariales) => void;
  onCambioPeriodicidad: (clave: string) => void;
}) {
  const errores = erroresDeParametros(valor);
  const set = <K extends keyof ParametrosSalariales>(
    campo: K,
    v: ParametrosSalariales[K],
  ) => onCambio({ ...valor, [campo]: v });

  const setHorario = <K extends keyof ParametrosSalariales['horario']>(
    campo: K,
    v: ParametrosSalariales['horario'][K],
  ) => onCambio({ ...valor, horario: { ...valor.horario, [campo]: v } });

  const tabla = valor.tabla_vacaciones;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      <div>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 4px' }}>
          Prestaciones
        </h3>
        <div style={FILA}>
          <Campo label="Días de aguinaldo (mín. 15)">
            <input
              className="input-field"
              style={campoInput}
              type="number"
              min={0}
              value={valor.dias_aguinaldo}
              onChange={(e) => set('dias_aguinaldo', Number(e.target.value))}
            />
          </Campo>
          <Campo label="Prima vacacional % (mín. 25)">
            <input
              className="input-field"
              style={campoInput}
              inputMode="decimal"
              /* Se captura en PORCENTAJE y se guarda como proporción, igual que
                 la prima de riesgo: teclear 25 creyendo que es 0.25 infla el
                 factor y el SBC un 77 % sin que ninguna tabla lo detecte. */
              value={String(Number(valor.prima_vacacional) * 100)}
              onChange={(e) =>
                set('prima_vacacional', String(Number(e.target.value) / 100))
              }
            />
          </Campo>
          <Campo label="Periodicidad de pago">
            <select
              className="input-field"
              style={campoInput}
              value={clavePeriodicidad}
              onChange={(e) => onCambioPeriodicidad(e.target.value)}
            >
              {PERIODICIDADES.map((p) => (
                <option key={p.clave} value={p.clave}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </Campo>
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 4px' }}>
          Vacaciones por antigüedad
        </h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0 0 8px' }}>
          Vacía, se aplica la tabla del Art. 76 LFT. Puedes dar <strong>más</strong> que la
          ley, nunca menos: cada renglón se compara contra el mínimo que le toca.
        </p>
        {tabla.map(([anios, dias], i) => (
          <div key={i} style={{ ...FILA, marginBottom: 'var(--space-sm)' }}>
            <Campo label="A partir del año" ancho="0 1 160px">
              <input
                className="input-field"
                style={campoInput}
                type="number"
                min={0}
                value={anios}
                onChange={(e) => {
                  const copia = tabla.map((r) => [...r] as [number, number]);
                  copia[i][0] = Number(e.target.value);
                  set('tabla_vacaciones', copia);
                }}
              />
            </Campo>
            <Campo label={`Días (ley: ${diasDeLey(anios)})`} ancho="0 1 160px">
              <input
                className="input-field"
                style={campoInput}
                type="number"
                min={0}
                value={dias}
                onChange={(e) => {
                  const copia = tabla.map((r) => [...r] as [number, number]);
                  copia[i][1] = Number(e.target.value);
                  set('tabla_vacaciones', copia);
                }}
              />
            </Campo>
            <button
              className="btn-secondary"
              aria-label={`Quitar el renglón del año ${anios}`}
              onClick={() => set('tabla_vacaciones', tabla.filter((_, j) => j !== i))}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Trash2 size={14} /> Quitar
            </button>
          </div>
        ))}
        <button
          className="btn-secondary"
          onClick={() =>
            set('tabla_vacaciones', [
              ...tabla,
              [tabla.length + 1, diasDeLey(tabla.length + 1)] as [number, number],
            ])
          }
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Plus size={14} /> Agregar renglón
        </button>
      </div>

      <div>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 4px' }}>
          Horario y tolerancia del checador
        </h3>
        <div style={FILA}>
          <Campo label="Entrada" ancho="0 1 140px">
            <input
              className="input-field"
              style={campoInput}
              type="time"
              value={valor.horario.hora_entrada}
              onChange={(e) => setHorario('hora_entrada', e.target.value)}
            />
          </Campo>
          <Campo label="Salida" ancho="0 1 140px">
            <input
              className="input-field"
              style={campoInput}
              type="time"
              value={valor.horario.hora_salida}
              onChange={(e) => setHorario('hora_salida', e.target.value)}
            />
          </Campo>
          <Campo label="Tolerancia (min)" ancho="0 1 140px">
            <input
              className="input-field"
              style={campoInput}
              type="number"
              min={0}
              max={120}
              value={valor.horario.tolerancia_minutos}
              onChange={(e) => setHorario('tolerancia_minutos', Number(e.target.value))}
            />
          </Campo>
        </div>
        <fieldset style={{ border: 'none', padding: 0, margin: 'var(--space-sm) 0 0' }}>
          <legend style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Días laborables
          </legend>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            {DIAS_SEMANA.map((nombre, dia) => (
              <label key={dia} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <input
                  type="checkbox"
                  checked={valor.horario.dias_laborables.includes(dia)}
                  onChange={(e) =>
                    setHorario(
                      'dias_laborables',
                      e.target.checked
                        ? [...valor.horario.dias_laborables, dia].sort((a, b) => a - b)
                        : valor.horario.dias_laborables.filter((d) => d !== dia),
                    )
                  }
                />
                {nombre}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {errores.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {errores.map((motivo) => (
            <li key={motivo} style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>
              {motivo}
            </li>
          ))}
        </ul>
      )}

      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
        Las tablas de <strong>ISR</strong>, las <strong>cuotas del IMSS</strong>, la{' '}
        <strong>UMA</strong> y el <strong>salario mínimo</strong> no se configuran aquí: son
        de ley, viven en el motor con su fuente publicada y se actualizan con el DOF.
      </p>
    </div>
  );
}
