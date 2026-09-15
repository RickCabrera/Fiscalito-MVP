/**
 * El CFDI de nómina del paso 4: un XML por empleado, **sin timbrar** (T4).
 *
 * LO QUE DESCARGA NO TIENE VALOR FISCAL, Y LA PANTALLA LO DICE TRES VECES
 * -----------------------------------------------------------------------
 * En el badge de arriba, en el nombre del archivo (`...-sin-timbrar-...xml`) y
 * en la advertencia que devuelve el backend. Un `.xml` de nómina que alguien
 * encuentra en su carpeta de descargas se parece demasiado a uno timbrado: lo
 * único que los distingue es que éste no trae Timbre Fiscal Digital. El
 * timbrado con un PAC está **fuera de alcance** por el `CLAUDE.md` de la raíz.
 *
 * POR QUÉ HAY UN FORMULARIO Y NO SÓLO UN BOTÓN
 * ---------------------------------------------
 * El CFDI exige RFC, CURP, NSS, dos códigos postales, registro patronal y clave
 * de entidad. **El modelo de la cartera no guarda casi ninguno** —`EmpleadoCartera`
 * no tiene RFC ni CURP, y los tres clientes de demostración no traen ni el RFC
 * del patrón—, así que se capturan aquí. Las alternativas eran peores: inventar
 * los datos produce un papel con el nombre de una persona real y los datos de
 * nadie, y un botón que siempre truena con 422 no dice qué falta.
 *
 * **Lo capturado vive en memoria y se pierde al salir.** No se guarda en
 * Firestore ni en `localStorage`: meterlo en la cartera es cambiar el modelo,
 * las reglas y el alta de empleado, y eso es tarea propia — anotada en el log.
 * Mientras tanto, nada de esto se persiste ni se loguea, igual que los TXT.
 */

import { useMemo, useState } from 'react';
import { FileCode2, Loader } from 'lucide-react';
import {
  CLAVE_TIPO_CONTRATO,
  faltantesParaCFDI,
  generarCFDINomina,
  reciboParaCFDI,
  type PatronCFDI,
  type TrabajadorCFDI,
} from '../../services/cfdiNominaApi';
import { descargarBytes } from '../../services/exportadores/descargar';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { ClienteDetalle } from '../../services/despachoApi';
import type { NominaPeriodo, ReciboNomina } from '../../services/nominaDemoApi';
import CampoCFDI from './CampoCFDI';
import TablaCFDIEmpleados from './TablaCFDIEmpleados';
import { CAPTURA_VACIA, type DatosTrabajadorCaptura } from './capturaCFDI';
import { tituloSeccion } from './estilosTabla';

/** Entre descarga y descarga: Chrome bloquea la ráfaga de `a.click()` (T5). */
const MS_ENTRE_DESCARGAS = 350;

interface Props {
  nomina: NominaPeriodo | null;
  cliente: ClienteDetalle | null;
  /** La plantilla de la cartera: de ahí salen NSS, puesto, alta y contrato. */
  empleados: EmpleadoCartera[];
  registroPatronal: string;
  deshabilitado: boolean;
}

export default function PanelCFDINomina({
  nomina,
  cliente,
  empleados,
  registroPatronal,
  deshabilitado,
}: Props) {
  const [patron, setPatron] = useState<PatronCFDI>({
    rfc: '',
    nombre: '',
    regimen_fiscal: '',
    registro_patronal: '',
    codigo_postal: '',
    clave_entidad: '',
  });
  const [riesgoPuesto, setRiesgoPuesto] = useState('');
  const [porEmpleado, setPorEmpleado] = useState<Record<string, DatosTrabajadorCaptura>>({});
  const [generando, setGenerando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  /**
   * Lo que la ficha SÍ tiene se precarga; lo que no, se queda vacío y se pide.
   * El seed no pisa lo tecleado: sólo rellena el campo que sigue en blanco.
   */
  const patronEfectivo: PatronCFDI = {
    ...patron,
    nombre: patron.nombre || cliente?.nombre || '',
    regimen_fiscal: patron.regimen_fiscal || cliente?.regimen || '',
    registro_patronal: patron.registro_patronal || registroPatronal || '',
  };

  const deLaCartera = useMemo(
    () => new Map(empleados.map((e) => [e.empleado_no, e])),
    [empleados],
  );

  /** El trabajador del CFDI. `null` = no está en la cartera y no hay de dónde. */
  const trabajadorDe = (recibo: ReciboNomina): TrabajadorCFDI | null => {
    const ficha = deLaCartera.get(recibo.empleado_no);
    if (!ficha || !cliente) return null;
    const capturado = porEmpleado[recibo.empleado_no] ?? CAPTURA_VACIA;
    return {
      rfc: capturado.rfc,
      nombre: recibo.nombre,
      curp: capturado.curp,
      // El NSS de la cartera es el default; el capturado manda si lo hay.
      numero_seguridad_social: capturado.nss || ficha.nss,
      codigo_postal: capturado.codigo_postal,
      fecha_inicio_relacion_laboral: ficha.fecha_alta ?? '',
      tipo_contrato: CLAVE_TIPO_CONTRATO[ficha.tipo_contrato],
      numero_empleado: recibo.empleado_no,
      puesto: ficha.puesto,
      riesgo_puesto: riesgoPuesto,
      periodicidad_pago: cliente.clave_periodicidad,
      // `SalarioBaseCotApor` es el SBC **del motor** —ya acotado entre piso y
      // tope— y no el de la ficha: si el clamp del Art. 28 movió el número, el
      // recibo y el CFDI tienen que decir el mismo.
      salario_base_cotizacion: recibo.sbc,
      salario_diario_integrado: ficha.salario_diario_integrado,
      departamento: '',
    };
  };

  const faltantesDe = (recibo: ReciboNomina): string[] => {
    const trabajador = trabajadorDe(recibo);
    // "plantilla" y no "cartera": en modo empresa única la cartera no existe
    // como concepto, y la pantalla es la misma.
    if (!trabajador) return ['No está en la plantilla'];
    return faltantesParaCFDI(patronEfectivo, trabajador);
  };

  const generarUno = async (recibo: ReciboNomina): Promise<boolean> => {
    const trabajador = trabajadorDe(recibo);
    if (!nomina || !trabajador || faltantesDe(recibo).length > 0) return false;
    const res = await generarCFDINomina({
      recibo: reciboParaCFDI(recibo),
      patron: patronEfectivo,
      trabajador,
      periodo: {
        inicio: nomina.periodo.inicio,
        fin: nomina.periodo.fin,
        // La que el motor usó de verdad, ya resuelto el default. Derivarla aquí
        // otra vez sería la segunda verdad que `fecha_pago_efectiva` evita.
        fecha_pago: nomina.fecha_pago_efectiva,
      },
    });
    descargarBytes(res.nombre_archivo, new TextEncoder().encode(res.xml));
    return true;
  };

  const conManejo = async (clave: string, accion: () => Promise<void>) => {
    setError(null);
    setAviso(null);
    setGenerando(clave);
    try {
      await accion();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el CFDI.');
    } finally {
      setGenerando(null);
    }
  };

  const generarTodos = () =>
    conManejo('todos', async () => {
      const recibos = nomina?.recibos ?? [];
      const omitidos: string[] = [];
      let generados = 0;
      for (const r of recibos) {
        if (await generarUno(r)) {
          generados += 1;
          await new Promise((listo) => setTimeout(listo, MS_ENTRE_DESCARGAS));
        } else {
          omitidos.push(r.empleado_no);
        }
      }
      setAviso(
        `${generados} XML generado(s).` +
          (omitidos.length
            ? ` Sin datos completos, no se generó el de: ${omitidos.join(', ')}.`
            : ''),
      );
    });

  const listos = (nomina?.recibos ?? []).filter((r) => faltantesDe(r).length === 0).length;

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <h3 style={tituloSeccion}>CFDI de nómina (XML)</h3>
        <span style={{
          padding: '2px 8px', borderRadius: 'var(--radius-xs)', fontSize: '0.72rem',
          background: 'var(--warning-bg)', color: 'var(--warning)',
          border: '1px solid var(--warning-border)',
        }}>
          Pendiente de timbrado PAC
        </span>
      </header>

      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Genera el XML del recibo (CFDI 4.0 + complemento de nómina 1.2) validado contra los
        XSD del SAT. <strong>No está timbrado</strong>: no lleva Timbre Fiscal Digital y sus
        atributos de sello son centinelas, así que todavía no es un comprobante fiscal. Los
        datos de abajo <strong>no se guardan</strong>: el expediente del empleado no tiene
        dónde ponerlos todavía, y se piden aquí en vez de inventarlos.
      </p>

      <div style={{
        display: 'grid', gap: 'var(--space-sm)',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
      }}>
        <CampoCFDI etiqueta="RFC del patrón" ejemplo="XAXX010101000" maxLength={13}
          valor={patronEfectivo.rfc} faltante={!patronEfectivo.rfc}
          onChange={(v) => setPatron({ ...patronEfectivo, rfc: v })} />
        <CampoCFDI etiqueta="Razón social" mayusculas={false}
          valor={patronEfectivo.nombre} faltante={!patronEfectivo.nombre}
          onChange={(v) => setPatron({ ...patronEfectivo, nombre: v })} />
        <CampoCFDI etiqueta="Régimen fiscal" ejemplo="601" maxLength={3}
          valor={patronEfectivo.regimen_fiscal} faltante={!patronEfectivo.regimen_fiscal}
          onChange={(v) => setPatron({ ...patronEfectivo, regimen_fiscal: v })} />
        <CampoCFDI etiqueta="Registro patronal"
          valor={patronEfectivo.registro_patronal} faltante={!patronEfectivo.registro_patronal}
          onChange={(v) => setPatron({ ...patronEfectivo, registro_patronal: v })} />
        <CampoCFDI etiqueta="CP del patrón" ejemplo="91090" maxLength={5}
          valor={patronEfectivo.codigo_postal} faltante={!patronEfectivo.codigo_postal}
          onChange={(v) => setPatron({ ...patronEfectivo, codigo_postal: v })} />
        <CampoCFDI etiqueta="Entidad (ClaveEntFed)" ejemplo="VER" maxLength={3}
          valor={patronEfectivo.clave_entidad} faltante={!patronEfectivo.clave_entidad}
          onChange={(v) => setPatron({ ...patronEfectivo, clave_entidad: v })} />
        <CampoCFDI etiqueta="Clase de riesgo" ejemplo="2" maxLength={2}
          valor={riesgoPuesto} faltante={!riesgoPuesto} onChange={setRiesgoPuesto} />
      </div>

      <TablaCFDIEmpleados
        recibos={nomina?.recibos ?? []}
        capturado={porEmpleado}
        nssDeLaCartera={(empleadoNo) => deLaCartera.get(empleadoNo)?.nss ?? ''}
        onCambiar={(empleadoNo, campo, valor) =>
          setPorEmpleado((previo) => ({
            ...previo,
            [empleadoNo]: { ...(previo[empleadoNo] ?? CAPTURA_VACIA), [campo]: valor },
          }))
        }
        faltantesDe={faltantesDe}
        generando={generando}
        deshabilitado={deshabilitado}
        onGenerar={(r) => conManejo(r.empleado_no, async () => { await generarUno(r); })}
      />

      <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn-secondary" onClick={generarTodos}
          disabled={deshabilitado || listos === 0 || generando !== null}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {generando === 'todos'
            ? <Loader size={16} className="spin" />
            : <FileCode2 size={16} />}
          Generar todos ({listos})
        </button>
        {aviso && <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{aviso}</span>}
      </div>

      {error && (
        <div style={{
          padding: '8px 12px', borderRadius: 'var(--radius-xs)',
          background: 'var(--danger-bg)', border: '1px solid var(--danger-border)',
          fontSize: '0.78rem', color: 'var(--danger)',
        }}>
          {error}
        </div>
      )}
    </section>
  );
}
