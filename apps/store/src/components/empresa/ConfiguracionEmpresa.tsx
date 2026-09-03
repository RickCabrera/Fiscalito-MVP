/**
 * Configuración de empresa (O-01).
 *
 * Los datos patronales de la empresa única: razón social, RFC, registro
 * patronal, prima de riesgos de trabajo y clase de riesgo. Se capturan **una
 * vez** y alimentan el cálculo de cuotas, el PDF y los archivos de O-04.
 *
 * VIVE EN SU PROPIO ARCHIVO, NO DENTRO DE `ProfilePage`
 * -----------------------------------------------------
 * `ProfilePage.tsx` ya estaba en 298 líneas contra el tope de 300 de
 * `apps/store/CLAUDE.md`. Meterle esto dentro lo hubiera pasado de largo, y la
 * deuda de archivos sobre el tope ya lleva dos corridas anotada en el backlog
 * (§G punto 4). Se extrae **antes** de crecerlo, no después.
 *
 * LA PRIMA SE CAPTURA EN PORCENTAJE Y SE GUARDA EN FRACCIÓN
 * ---------------------------------------------------------
 * El modelo la guarda como fracción (0.0054355), que es lo que espera el motor,
 * pero el patrón la recibe del IMSS en porcentaje (0.54355 %). Capturar en
 * fracción es cómo alguien teclea `5.4355` creyendo que pone el 5.4 % y
 * multiplica el ramo de Riesgos de Trabajo **por mil** sin que ninguna tabla lo
 * detecte. La conversión se hace aquí, en un solo lugar, y el backend vuelve a
 * acotar a [0.005, 0.150] (Arts. 72 y 73 LSS).
 */

import { useState } from 'react';
import { Building2, Check, Save } from 'lucide-react';
import Campo from '../cartera/Campo';
import { campoInput } from '../cartera/estilosCampo';
import { faltantesDeLaEmpresa, type ConfigEmpresa } from '../../services/empresa';
import { aFraccion, aPorcentaje, erroresDeParametros, validar } from './validacionEmpresa';
import ParametrosSalarialesForm from './ParametrosSalarialesForm';

/**
 * LOS CAMPOS SE SIEMBRAN DEL PROP UNA SOLA VEZ, Y ESO BASTA **POR EL `key`**.
 *
 * `useState(empresa.x)` sólo lee el prop en el primer render. Montar esta
 * tarjeta antes de que la cartera resuelva —siempre pasa: es una lectura de
 * Firestore de hasta 2500 ms— dejaba los cinco campos en blanco sobre una
 * empresa ya capturada, con su banner de "falta la razón social" y sus errores
 * en rojo. Y lo caro venía después: el operador retecleaba lo que veía faltando
 * y al guardar se perdían el RFC y el registro patronal, que seguían vacíos en
 * el estado local y viajaban así.
 *
 * `TarjetaEmpresa` lo resuelve por fuera con dos cosas: no monta esto mientras
 * la cartera carga, y le pasa un `key` derivado de la empresa **guardada**, así
 * que un cambio del documento remonta el componente y vuelve a sembrar. Se
 * prefirió eso a un `useEffect` de resincronización porque el efecto llamaba
 * `setState` en cascada (`react-hooks/set-state-in-effect`) y porque el `key`
 * no puede pisar lo que el operador está tecleando: sólo cambia cuando cambia
 * lo guardado.
 */
export default function ConfiguracionEmpresa({
  empresa,
  soloLectura,
  onGuardar,
}: {
  empresa: ConfigEmpresa;
  soloLectura: boolean;
  onGuardar: (config: ConfigEmpresa) => Promise<void>;
}) {
  const [razonSocial, setRazonSocial] = useState(empresa.razonSocial);
  const [rfc, setRfc] = useState(empresa.rfc);
  const [registroPatronal, setRegistroPatronal] = useState(empresa.registroPatronal);
  const [primaPct, setPrimaPct] = useState(aPorcentaje(empresa.primaRiesgo));
  const [guia, setGuia] = useState(empresa.guiaSubdelegacion);
  const [claseRiesgo, setClaseRiesgo] = useState(
    empresa.claseRiesgo === null ? '' : String(empresa.claseRiesgo),
  );
  // O-03: los parámetros salariales viven en el mismo documento y se guardan
  // con el mismo botón. Separarlos en dos formularios haría que el operador
  // pudiera guardar la razón social y dejar el aguinaldo a medias, y sólo una
  // de las dos mitades bloquea el cálculo.
  const [parametros, setParametros] = useState(empresa.parametros);
  const [clavePeriodicidad, setClavePeriodicidad] = useState(empresa.clavePeriodicidad);
  const [guardando, setGuardando] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const errores = validar(razonSocial, rfc, registroPatronal, primaPct);
  const erroresParametros = erroresDeParametros(parametros);
  const puedeGuardar =
    Object.keys(errores).length === 0 && erroresParametros.length === 0 && !soloLectura;

  const guardar = async () => {
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);
    try {
      await onGuardar({
        ...empresa,
        razonSocial: razonSocial.trim(),
        rfc: rfc.trim().toUpperCase(),
        registroPatronal: registroPatronal.trim().toUpperCase(),
        primaRiesgo: aFraccion(primaPct),
        claseRiesgo: claseRiesgo === '' ? null : Number(claseRiesgo),
        clavePeriodicidad,
        guiaSubdelegacion: guia.trim(),
        parametros,
      });
      setGuardado(true);
      setTimeout(() => setGuardado(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar la empresa.');
    } finally {
      setGuardando(false);
    }
  };

  const faltan = faltantesDeLaEmpresa(empresa.razonSocial, empresa.primaRiesgo);

  return (
    <div className="card" style={{ padding: 'var(--space-lg)' }}>
      <h2
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          fontSize: '1.05rem', fontWeight: 700, marginTop: 0, marginBottom: 4,
        }}
      >
        <Building2 size={18} color="var(--teal-light)" /> Configuración de empresa
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 0 }}>
        Se captura una vez. De aquí salen las cuotas patronales, el encabezado de los recibos
        y los archivos que se le entregan al IMSS.
      </p>

      {faltan.length > 0 && (
        <p
          role="status"
          style={{
            fontSize: '0.82rem', color: 'var(--warning)',
            background: 'var(--bg-input)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm)',
          }}
        >
          Falta {faltan.join(' y ')}. Hasta que se capture, la nómina no se puede calcular.
        </p>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
        <Campo label="Razón social" ancho="1 1 320px">
          <input
            className="input-field"
            style={campoInput}
            value={razonSocial}
            onChange={(e) => setRazonSocial(e.target.value)}
            placeholder="Orca Ordorica Cristal Templado S.A. de C.V."
          />
        </Campo>
        <Campo label="RFC del patrón">
          <input
            className="input-field"
            style={campoInput}
            value={rfc}
            onChange={(e) => setRfc(e.target.value)}
            placeholder="AAA010101AAA"
          />
        </Campo>
        <Campo label="Registro patronal (11)">
          <input
            className="input-field"
            style={campoInput}
            value={registroPatronal}
            onChange={(e) => setRegistroPatronal(e.target.value)}
            placeholder="A1234567890"
          />
        </Campo>
        <Campo label="Prima de riesgo (%)">
          <input
            className="input-field"
            style={campoInput}
            inputMode="decimal"
            value={primaPct}
            onChange={(e) => setPrimaPct(e.target.value)}
            placeholder="0.54355"
          />
        </Campo>
        <Campo label="Guía de la subdelegación">
          <input
            className="input-field"
            style={campoInput}
            inputMode="numeric"
            value={guia}
            /* O-04: va en las posiciones 134-138 de CADA movimiento afiliatorio
               y en el registro de cifras de control. La asigna la subdelegación
               del IMSS: no se calcula ni se deduce. Sin ella el archivo no se
               puede emitir, y el exportador lo dice en vez de mandarlo vacío. */
            onChange={(e) => setGuia(e.target.value)}
            placeholder="00001"
          />
        </Campo>
        <Campo label="Clase de riesgo">
          <select
            className="input-field"
            style={campoInput}
            value={claseRiesgo}
            onChange={(e) => setClaseRiesgo(e.target.value)}
          >
            <option value="">Sin especificar</option>
            {[1, 2, 3, 4, 5].map((c) => (
              <option key={c} value={c}>{`Clase ${c}`}</option>
            ))}
          </select>
        </Campo>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: 'var(--space-lg) 0' }} />

      <ParametrosSalarialesForm
        valor={parametros}
        clavePeriodicidad={clavePeriodicidad}
        onCambio={setParametros}
        onCambioPeriodicidad={setClavePeriodicidad}
      />

      {/* Los motivos, uno por uno. Un "hay errores" genérico obliga a adivinar
          cuál de los cinco campos es. */}
      {Object.values(errores).length > 0 && (
        <ul style={{ margin: 'var(--space-md) 0 0', paddingLeft: 18 }}>
          {Object.values(errores).map((motivo) => (
            <li key={motivo} style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>
              {motivo}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p style={{ fontSize: '0.82rem', color: 'var(--danger)' }}>{error}</p>
      )}

      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
          marginTop: 'var(--space-lg)',
        }}
      >
        <button
          className="btn-primary"
          onClick={guardar}
          disabled={!puedeGuardar || guardando}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
        >
          <Save size={16} /> {guardando ? 'Guardando…' : 'Guardar empresa'}
        </button>
        {guardado && (
          <span
            role="status"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: '0.85rem', color: 'var(--success)',
            }}
          >
            <Check size={15} /> Guardado
          </span>
        )}
      </div>

      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 0 }}>
        Las tablas de ISR, las cuotas del IMSS, la UMA y el salario mínimo <strong>no se
        configuran aquí</strong>: son de ley, viven en el motor con su fuente publicada y se
        actualizan con el DOF, no con un formulario.
      </p>
    </div>
  );
}
