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
  REGIMEN_CLIENTE_POR_DEFECTO,
  REGIMENES_DE_CLIENTE,
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
    // T1: decide qué tabs de Fiscalito se le pueden trabajar a este cliente.
    // Con valor desde el alta, para que el aviso de "régimen supuesto" de
    // `FiscalitoServicePage` sólo lo vean los clientes anteriores a T1.
    regimen: REGIMEN_CLIENTE_POR_DEFECTO,
    prima_riesgo: '',
    clase_riesgo: 1,
    // O-cierre: los dos datos que el IMSS asigna y que el exportador de
    // movimientos afiliatorios necesita en CADA renglón. Vacíos por default y
    // nunca deducidos.
    registro_patronal: '',
    guia_subdelegacion: '',
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

  /**
   * Los dos datos del IMSS, contra lo que el backend acepta (O-cierre).
   *
   * `schemas/cartera.py` los declara `^\d{0,5}$` (guía) y 11 caracteres
   * (registro patronal). Esta pantalla los creó y no los validaba: hoy no
   * revienta porque el interruptor de R-07 está apagado, pero con
   * `VITE_CARTERA_BACKEND=1` es un 422 al guardar, sobre un campo que el
   * operador ya dio por bueno. Es la misma asimetría que el techo de vacaciones
   * de `validacionEmpresa.ts`, que esta corrida acaba de cerrar del otro lado.
   *
   * Los dos son OPCIONALES: vacío es válido —el resto de la nómina y el PDF
   * funcionan sin ellos— y lo que se rechaza es un valor mal formado.
   */
  const rpMalFormado =
    (datos.registro_patronal ?? '').trim() !== '' &&
    (datos.registro_patronal ?? '').trim().length !== 11;
  const guiaMalFormada =
    (datos.guia_subdelegacion ?? '').trim() !== '' &&
    !/^\d{1,5}$/.test((datos.guia_subdelegacion ?? '').trim());
  const puedeGuardar =
    datos.id.trim() !== '' &&
    datos.nombre.trim() !== '' &&
    datos.prima_riesgo !== '' &&
    // Sin los límites del Art. 72 no se guarda: la validación no se evapora.
    primas !== null &&
    !primaFueraDeRango &&
    !idRepetido &&
    !rpMalFormado &&
    !guiaMalFormada &&
    !guardando;

  async function guardar() {
    // `disabled` es una propiedad del DOM, no una garantía del handler. Hoy no
    // hay forma de disparar esto sin el botón —no hay `<form>`, así que Enter
    // no envía— pero es la misma asimetría que esta rama gastó dos rondas
    // corrigiendo en `useNominaCliente`, y cuesta una línea.
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);
    try {
      await onGuardar({
        ...datos,
        id: datos.id.trim(),
        nombre: datos.nombre.trim(),
        // Un cliente guardado ANTES de T1 llega aquí sin la llave, y el `select`
        // de abajo pinta el default sin disparar `onChange`: sin esta línea se
        // guardaría tal cual y la pantalla seguiría avisando "régimen supuesto"
        // después de que el contador ya lo dio por bueno.
        regimen: datos.regimen || REGIMEN_CLIENTE_POR_DEFECTO,
      });
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
          {/* T1: es el régimen del CLIENTE, y decide sus tabs de Fiscalito —con
              el corte heredado de E-01, pendiente de confirmar con la contadora
              (§D30). Sólo 612 y 626: son los dos que el motor y el calendario
              manejan para persona física (`REGIMENES_DE_CLIENTE`). */}
          <Campo label="Régimen fiscal" ancho="1 1 240px">
            <select
              style={campo}
              value={datos.regimen || REGIMEN_CLIENTE_POR_DEFECTO}
              onChange={(e) => setDatos({ ...datos, regimen: e.target.value })}
            >
              {REGIMENES_DE_CLIENTE.map((r) => (
                <option key={r.code} value={r.code}>{r.code} · {r.name}</option>
              ))}
            </select>
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
          {/* O-cierre: sin estos dos, el TXT de movimientos afiliatorios de
              O-04 no se puede emitir para este cliente — van en cada renglón y
              los asigna el IMSS. Se capturaban SÓLO en Configuración de
              empresa, que con el flag apagado ni siquiera se renderiza: el
              contador pulsaba Exportar, leía "captúralo en Perfil" y esa
              pantalla no existía. Son opcionales: el resto de la nómina y el
              PDF funcionan sin ellos. */}
          <Campo label="Registro patronal (IMSS)" ancho="1 1 180px">
            <input
              style={campo}
              value={datos.registro_patronal ?? ''}
              placeholder="11 caracteres"
              onChange={(e) => setDatos({ ...datos, registro_patronal: e.target.value })}
            />
          </Campo>
          <Campo label="Guía de subdelegación" ancho="1 1 180px">
            <input
              style={campo}
              value={datos.guia_subdelegacion ?? ''}
              placeholder="La asigna el IMSS"
              onChange={(e) => setDatos({ ...datos, guia_subdelegacion: e.target.value })}
            />
          </Campo>
          {/* Fuera de `Campo`, que sólo admite un hijo. Los motivos van uno por
              uno: un "hay errores" genérico obliga a adivinar cuál de los dos. */}
          {rpMalFormado && (
            <p style={{ fontSize: '0.75rem', color: 'var(--danger)', margin: 0, flex: '1 1 100%' }}>
              El registro patronal son 11 caracteres: los 10 del registro más su dígito
              verificador.
            </p>
          )}
          {guiaMalFormada && (
            <p style={{ fontSize: '0.75rem', color: 'var(--danger)', margin: 0, flex: '1 1 100%' }}>
              La guía de la subdelegación son hasta 5 dígitos, sin letras ni guiones.
            </p>
          )}
          {/* **Sólo quincenal, a propósito.** El periodo sugerido que la app
                calcula es siempre `quincena(hoy)`, y el selector sigue
                cerrado, pero **la razón ya no es la misma**. Era que nadie
                validaba que la duración del periodo casara con esta clave: un
                cliente marcado Mensual recibía la tarifa mensual del Art. 96
                sobre una base de 15-16 días —ISR subestimado en silencio, con
                recibo creíble—. **O-03 construyó esa validación**
                (`duracion_periodo.py`, cableada en el orquestador y en el
                endpoint), así que ese hueco está cerrado.

                Lo que falta para abrir las otras tres es que la app SUGIERA el
                periodo correcto para cada clave —hoy `periodo_sugerido` ya lo
                hace para 01, 02, 04 y 05— y que esta pantalla deje elegirlo sin
                que el operador tenga que adivinar las fechas. Catorcenal se
                queda fuera igual: no hay tarifa publicada (§D10). Tarea propia,
                no un "de pasada". */}
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
