/**
 * Alta y edición de un cliente del despacho (G-03).
 *
 * LA PRIMA DE RT ES DATO DE ENTRADA, NO SE DEDUCE DEL GIRO
 * -------------------------------------------------------
 * `despacho_demo.py` lo deja escrito y §D22 lo documenta: la asignación
 * giro → clase de riesgo sale del catálogo de actividades del RACERF, que no
 * está en el repo, y para un patrón real **la prima la autodetermina él cada
 * febrero** (Art. 74 LSS). Así que aquí se captura, no se adivina. El
 * formulario ofrece las primas medias por clase como ayuda, y dice que son
 * medias, para que nadie las confunda con la prima del cliente.
 */

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import {
  obtenerPrimasDeRiesgo,
  type ClienteCartera,
  type PrimasDeRiesgo,
} from '../../services/carteraApi';
import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';

type Datos = Omit<ClienteCartera, 'empleados'>;

function vacio(): Datos {
  return {
    id: '',
    nombre: '',
    giro: '',
    origen: 'propio',
    prima_riesgo: '',
    clase_riesgo: 1,
    clave_periodicidad: '04',
    zona: 'general',
    periodo_sugerido: { inicio: '', fin: '', fecha_pago: null },
  };
}

export default function ModalCliente({
  cliente,
  idsExistentes,
  onGuardar,
  onCerrar,
}: {
  cliente: Datos | null;
  idsExistentes: string[];
  onGuardar: (c: Datos) => Promise<void>;
  onCerrar: () => void;
}) {
  const esAlta = cliente === null;
  const [datos, setDatos] = useState<Datos>(() => cliente ?? vacio());
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [primas, setPrimas] = useState<PrimasDeRiesgo | null>(null);
  const [errorPrimas, setErrorPrimas] = useState(false);

  // Las primas medias las trae el MOTOR, con su fecha de vigencia. Copiarlas
  // aquí las dejaría sin año, sin fuente y sin test: en 2027 propondrían las de
  // 2026 en silencio.
  useEffect(() => {
    let cancelado = false;
    obtenerPrimasDeRiesgo(new Date().toISOString().slice(0, 10))
      .then((p) => !cancelado && setPrimas(p))
      // **No se traga el error.** Sin las primas no hay con qué acotar la de
      // este cliente, y dejarlo pasar en silencio permitiría guardar 5.4355 en
      // vez de 0.0054355 — justo el error que el aviso de abajo existe para
      // evitar, multiplicando Riesgos de Trabajo por mil.
      .catch(() => !cancelado && setErrorPrimas(true));
    return () => { cancelado = true; };
  }, []);

  const prima = Number(datos.prima_riesgo);
  /** Art. 72 LSS. Teclear 5.4355 en vez de 0.0054355 multiplica RT por mil. */
  const primaFueraDeRango =
    primas !== null &&
    datos.prima_riesgo !== '' &&
    (!Number.isFinite(prima) ||
      prima < Number(primas.minima) ||
      prima > Number(primas.maxima));

  const idRepetido = esAlta && idsExistentes.includes(datos.id.trim());
  const puedeGuardar =
    datos.id.trim() !== '' &&
    datos.nombre.trim() !== '' &&
    datos.prima_riesgo !== '' &&
    // Sin los límites del Art. 72 no se guarda: la validación no se evapora.
    primas !== null &&
    !primaFueraDeRango &&
    !idRepetido &&
    !guardando;

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      await onGuardar({ ...datos, id: datos.id.trim(), nombre: datos.nombre.trim() });
      onCerrar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
      setGuardando(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-label={esAlta ? 'Alta de cliente' : `Editar ${datos.nombre}`}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-md)',
      }}
    >
      <div
        className="card"
        style={{
          width: 'min(620px, 100%)', maxHeight: '90vh', overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 'var(--space-md)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            {esAlta ? 'Nuevo cliente' : datos.nombre}
          </h2>
          <button
            onClick={onCerrar}
            aria-label="Cerrar"
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="Identificador *" ancho="1 1 180px">
            <input
              style={campo}
              value={datos.id}
              disabled={!esAlta}
              onChange={(e) => setDatos({ ...datos, id: e.target.value })}
              placeholder="tortilleria-lopez"
            />
          </Campo>
          <Campo label="Razón social o nombre *" ancho="2 1 260px">
            <input
              style={campo}
              value={datos.nombre}
              onChange={(e) => setDatos({ ...datos, nombre: e.target.value })}
            />
          </Campo>
          <Campo label="Giro" ancho="1 1 200px">
            <input
              style={campo}
              value={datos.giro}
              onChange={(e) => setDatos({ ...datos, giro: e.target.value })}
            />
          </Campo>
        </div>

        {idRepetido && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
            Ya tienes un cliente con el identificador <strong>{datos.id}</strong>.
          </p>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
          <Campo label="Clase de riesgo" ancho="1 1 180px">
            <select
              style={campo}
              value={datos.clase_riesgo ?? 1}
              onChange={(e) => {
                const clase = Number(e.target.value);
                setDatos({
                  ...datos,
                  clase_riesgo: clase,
                  prima_riesgo: primas?.medias_por_clase[String(clase)] ?? datos.prima_riesgo,
                });
              }}
            >
              {[1, 2, 3, 4, 5].map((c) => (
                <option key={c} value={c}>Clase {c}</option>
              ))}
            </select>
          </Campo>
          <Campo label="Prima de RT (proporción)" ancho="1 1 180px">
            <input
              style={campo}
              inputMode="decimal"
              value={datos.prima_riesgo}
              onChange={(e) => setDatos({ ...datos, prima_riesgo: e.target.value })}
            />
          </Campo>
          {/* **Sólo quincenal, a propósito.** El periodo sugerido que la app
                calcula es siempre `quincena(hoy)`, y nadie valida que la
                duración del periodo case con esta clave: un cliente marcado
                Mensual recibiría la tarifa mensual del Art. 96 sobre una base
                de 15-16 días —**ISR subestimado en silencio**, con recibo
                creíble— y uno Semanal, la semanal sobre 16 días. Catorcenal ni
                siquiera puede calcular: no hay tarifa publicada (§D10).
                Abrir las otras tres exige que el motor rechace un periodo cuya
                duración no case con la clave. Queda anotado en el backlog. */}
          <Campo label="Periodicidad de pago" ancho="1 1 180px">
            <select
              style={campo}
              value={datos.clave_periodicidad}
              disabled
              onChange={(e) => setDatos({ ...datos, clave_periodicidad: e.target.value })}
            >
              <option value="04">Quincenal</option>
            </select>
          </Campo>
        </div>

        {errorPrimas && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
            No se pudieron cargar los límites de la prima de Riesgos de Trabajo (Art. 72 LSS),
            así que no se puede validar lo que captures. Revisa que la API esté corriendo.
          </p>
        )}

        {primaFueraDeRango && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.82rem' }}>
            La prima debe estar entre {primas?.minima} y {primas?.maxima} (Art. 72 LSS).
            Ojo con el punto decimal: <strong>5.4355</strong> en vez de{' '}
            <strong>0.0054355</strong> multiplica Riesgos de Trabajo por mil.
          </p>
        )}

        <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          Hoy sólo se puede llevar nómina <strong>quincenal</strong>: el periodo que la app
          propone siempre es una quincena, y calcular una quincena con la tarifa de otra
          periodicidad daría un ISR equivocado sin avisar.
        </p>

        <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          Al elegir clase se propone la <strong>prima media</strong> de esa clase (Art. 73 LSS),
          que es la que aplica a una empresa nueva. La prima real{' '}
          <strong>la autodetermina el patrón cada febrero</strong> con su siniestralidad
          (Art. 74 LSS): si la conoces, captúrala.
        </p>

        {error && (
          <p role="alert" style={{ margin: 0, color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</p>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
          <button className="btn-secondary" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primary" disabled={!puedeGuardar} onClick={guardar}>
            {guardando ? 'Guardando…' : esAlta ? 'Dar de alta' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}
