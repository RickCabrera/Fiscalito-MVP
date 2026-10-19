/**
 * Datos anuales de la persona moral (P3-01): lo que no sale de la bóveda ni de la
 * contabilidad. Coeficiente de utilidad (el de la anual anterior), PTU pagada,
 * pérdidas pendientes, ISR retenido por el sistema financiero (Art. 54) y los
 * pagos realmente presentados. Se guarda en el backend por cliente y ejercicio;
 * los demás campos del esquema (saldos para el ajuste por inflación, cuentas,
 * estímulos) se conservan tal como vienen.
 */

import { useEffect, useState } from 'react';
import { Loader, Plus, Save, Trash2 } from 'lucide-react';
import { guardarDatosPM, obtenerDatosPM, type DatosAnualesPM, type PerdidaPM } from '../../services/anualApi';
import { labelStyle } from '../../utils/styles';
import { nombreMes } from './tablaMesesUtil';

interface Props {
  clave: string;
  anio: number;
  onGuardado: () => void;
}

const MESES = Array.from({ length: 12 }, (_, i) => i + 1);
const CORTA: React.CSSProperties = { width: 96, textAlign: 'right', padding: '4px 6px' };

export default function DatosPMForm({ clave, anio, onGuardado }: Props) {
  const [datos, setDatos] = useState<DatosAnualesPM>({});
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // El padre lo monta con `key` por cliente y ejercicio: cambiar de año es otro formulario.
  useEffect(() => {
    let vivo = true;
    obtenerDatosPM(clave, anio)
      .then((r) => { if (vivo) setDatos(r.datos); })
      .catch((e: unknown) => { if (vivo) setError(e instanceof Error ? e.message : 'No se pudieron leer los datos.'); })
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, [clave, anio]);

  const poner = (campo: keyof DatosAnualesPM, valor: unknown) =>
    setDatos((d) => ({ ...d, [campo]: valor }));

  const ponerMes = (campo: 'retenciones_bancarias' | 'pagos_efectuados', mes: number, valor: string) => {
    const actual = { ...(datos[campo] ?? {}) };
    if (valor === '') delete actual[String(mes)];
    else actual[String(mes)] = valor;
    poner(campo, actual);
  };

  const perdidas = datos.perdidas ?? [];
  const ponerPerdida = (i: number, cambio: Partial<PerdidaPM>) =>
    poner('perdidas', perdidas.map((p, j) => (j === i ? { ...p, ...cambio } : p)));

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      const limpio = {
        ...datos,
        coeficiente_utilidad: datos.coeficiente_utilidad || null,
        no_deducibles_art28_xxx: datos.no_deducibles_art28_xxx || null,
      };
      setDatos((await guardarDatosPM(clave, anio, limpio)).datos);
      onGuardado();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron guardar los datos.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <p className="card" role="status">Cargando datos del ejercicio…</p>;

  const campo = (id: string, etiqueta: string, valor: string, cambiar: (v: string) => void, paso = '0.01') => (
    <div>
      <label style={labelStyle} htmlFor={id}>{etiqueta}</label>
      <input id={id} className="input-field" type="number" step={paso} min={0} value={valor}
        onChange={(e) => cambiar(e.target.value)} />
    </div>
  );

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Datos del ejercicio {anio}</h3>
      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        {campo('pm-coef', 'Coeficiente de utilidad (vacío = calcularlo)', String(datos.coeficiente_utilidad ?? ''),
          (v) => poner('coeficiente_utilidad', v), '0.0001')}
        {campo('pm-ptu', 'PTU pagada en el ejercicio', String(datos.ptu_pagada ?? ''), (v) => poner('ptu_pagada', v || '0'))}
        {campo('pm-mes-ptu', 'Mes en que se pagó la PTU', String(datos.mes_pago_ptu ?? 5),
          (v) => poner('mes_pago_ptu', Number(v) || 5), '1')}
        {campo('pm-inv', 'Deducción fiscal de inversiones (anual)', String(datos.deduccion_inversiones ?? ''),
          (v) => poner('deduccion_inversiones', v || '0'))}
        {campo('pm-xxx', 'No deducibles Art. 28 fr. XXX para PTU (vacío = derivarlo)',
          String(datos.no_deducibles_art28_xxx ?? ''), (v) => poner('no_deducibles_art28_xxx', v))}
        <div>
          <label style={labelStyle} htmlFor="pm-fuente">Ingresos y deducciones de</label>
          <select id="pm-fuente" className="input-field" value={datos.fuente ?? 'auto'}
            onChange={(e) => poner('fuente', e.target.value)}>
            <option value="auto">Automático (contabilidad si hay pólizas)</option>
            <option value="contabilidad">Contabilidad</option>
            <option value="boveda">Bóveda de CFDI</option>
          </select>
        </div>
      </div>

      <div>
        <p style={{ ...labelStyle, marginBottom: 8 }}>Pérdidas fiscales pendientes (Art. 57 LISR)</p>
        {perdidas.map((p, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
            <input className="input-field" style={CORTA} type="number" aria-label={`Ejercicio pérdida ${i + 1}`}
              value={p.ejercicio} onChange={(e) => ponerPerdida(i, { ejercicio: Number(e.target.value) })} />
            <input className="input-field" style={{ ...CORTA, width: 140 }} type="number" step="0.01" min={0}
              aria-label={`Remanente pérdida ${i + 1}`} value={p.remanente}
              onChange={(e) => ponerPerdida(i, { remanente: e.target.value })} />
            <input className="input-field" style={{ ...CORTA, width: 110, textAlign: 'left' }} placeholder="AAAA-MM"
              aria-label={`Actualizada a pérdida ${i + 1}`} value={p.actualizada_a ?? ''}
              onChange={(e) => ponerPerdida(i, { actualizada_a: e.target.value || null })} />
            <button className="btn-secondary" aria-label={`Quitar pérdida ${i + 1}`}
              onClick={() => poner('perdidas', perdidas.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
          </div>
        ))}
        <button className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          onClick={() => poner('perdidas', [...perdidas, { ejercicio: anio - 1, remanente: '0', actualizada_a: null }])}>
          <Plus size={14} /> Agregar pérdida
        </button>
        <p style={{ margin: '6px 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Ejercicio · remanente · mes de su última actualización (vacío si es el monto histórico).
        </p>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ color: 'var(--text-secondary)' }}>
              <th style={{ textAlign: 'left', padding: 4 }}>Mes</th>
              <th style={{ padding: 4 }}>ISR retenido por bancos (Art. 54)</th>
              <th style={{ padding: 4 }}>Pago presentado (vacío = el del sistema)</th>
            </tr>
          </thead>
          <tbody>
            {MESES.map((m) => (
              <tr key={m}>
                <td style={{ padding: 4 }}>{nombreMes(m)}</td>
                <td style={{ padding: 4 }}>
                  <input className="input-field" style={CORTA} type="number" step="0.01" min={0}
                    aria-label={`Retención ${m}`} value={datos.retenciones_bancarias?.[String(m)] ?? ''}
                    onChange={(e) => ponerMes('retenciones_bancarias', m, e.target.value)} />
                </td>
                <td style={{ padding: 4 }}>
                  <input className="input-field" style={CORTA} type="number" step="0.01" min={0}
                    aria-label={`Pago presentado ${m}`} value={datos.pagos_efectuados?.[String(m)] ?? ''}
                    onChange={(e) => ponerMes('pagos_efectuados', m, e.target.value)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>{error}</p>}
      <button className="btn-primary" onClick={guardar} disabled={guardando}
        style={{ display: 'flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }}>
        {guardando ? <Loader size={14} className="spin" /> : <Save size={14} />} Guardar datos
      </button>
    </div>
  );
}
