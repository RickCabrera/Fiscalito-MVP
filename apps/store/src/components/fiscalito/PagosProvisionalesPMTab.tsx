/**
 * Pagos provisionales de una PERSONA MORAL (601) o RESICO PM — P3-01.
 *
 * Reemplaza el cascarón de T6, que estimaba `ingresos × coeficiente × 30 %` en el
 * navegador. Ahora el cálculo es del motor (`app/fiscal_engine/personas_morales.py`):
 * ingresos de la bóveda o de la contabilidad, coeficiente de utilidad (Art. 14
 * fr. I), PTU pagada en octavos de mayo a diciembre, pérdidas actualizadas
 * (Art. 57), tasa del 30 % (Art. 9), menos pagos anteriores y retenciones del
 * Art. 54. En RESICO PM, flujo de efectivo (Art. 211). La pantalla sólo pinta.
 */

import { useCallback, useState } from 'react';
import { Building2, Loader, RefreshCw } from 'lucide-react';
import { usePerfilFiscal } from '../../context/usePerfilFiscal';
import { pagosProvisionalesPM, type ResultadoPagosPM } from '../../services/anualApi';
import DatosPMForm from './DatosPMForm';
import AvisoPorConfirmar from './AvisoPorConfirmar';
import TablaMeses from './TablaMeses';
import { nombreMes, type ColumnaMes } from './tablaMesesUtil';

const hoy = new Date();

const COLUMNAS_PM: ColumnaMes[] = [
  { campo: 'ingresos_acumulados', titulo: 'Ingresos nominales acum.' },
  { campo: 'utilidad_estimada', titulo: 'Utilidad estimada' },
  { campo: 'ptu_disminuida', titulo: 'PTU' },
  { campo: 'perdidas', titulo: 'Pérdidas' },
  { campo: 'base', titulo: 'Base' },
  { campo: 'isr_causado', titulo: 'ISR 30 %' },
  { campo: 'pagos_anteriores', titulo: 'Pagos anteriores' },
  { campo: 'retenciones', titulo: 'Retenciones' },
  { campo: 'pago_determinado', titulo: 'A pagar' },
  { campo: 'pago_efectuado', titulo: 'Presentado' },
];

const COLUMNAS_RESICO: ColumnaMes[] = [
  { campo: 'ingresos_acumulados', titulo: 'Cobrado acum.' },
  { campo: 'deducciones_acumuladas', titulo: 'Pagado acum.' },
  ...COLUMNAS_PM.slice(1),
];

export default function PagosProvisionalesPMTab() {
  const perfil = usePerfilFiscal();
  const clave = perfil.clienteId;
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() === 0 ? 12 : hoy.getMonth());
  const [resultado, setResultado] = useState<ResultadoPagosPM | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verDatos, setVerDatos] = useState(false);

  const calcular = useCallback(async () => {
    if (!clave) return;
    setCargando(true);
    setError(null);
    try {
      setResultado(await pagosProvisionalesPM(clave, anio, mes));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo calcular el pago provisional.');
    } finally {
      setCargando(false);
    }
  }, [clave, anio, mes]);

  if (!clave) return <p className="card">Elige un cliente para calcular sus pagos provisionales.</p>;

  const ultimo = resultado?.pagos[resultado.pagos.length - 1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', fontWeight: 600, margin: 0, flexBasis: '100%' }}>
          <Building2 size={18} /> Pago provisional de ISR — personas morales
        </h3>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Año
          <input className="input-field" type="number" value={anio} aria-label="Año"
            onChange={(e) => setAnio(Number(e.target.value))} style={{ width: 90 }} />
        </label>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Mes
          <input className="input-field" type="number" min={1} max={12} value={mes} aria-label="Mes"
            onChange={(e) => setMes(Number(e.target.value))} style={{ width: 70 }} />
        </label>
        <button className="btn-primary" onClick={calcular} disabled={cargando}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {cargando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />} Calcular
        </button>
        <button className="btn-secondary" onClick={() => setVerDatos((v) => !v)}>
          {verDatos ? 'Ocultar datos del ejercicio' : 'Datos del ejercicio'}
        </button>
      </div>

      {verDatos && <DatosPMForm key={`${clave}-${anio}`} clave={clave} anio={anio} onGuardado={calcular} />}
      {error && <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>{error}</p>}

      {resultado && ultimo && (
        <>
          <div className="card" style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'baseline' }}>
            <div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {nombreMes(ultimo.mes)} {resultado.anio} · vence {resultado.fecha_limite}
              </p>
              <p data-testid="pago-pm" style={{ margin: '4px 0 0', fontSize: '1.4rem', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
                {ultimo.pago_determinado}
              </p>
            </div>
            {resultado.tipo === 'pm' && (
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Coeficiente de utilidad <strong>{resultado.coeficiente}</strong> ({resultado.origen_coeficiente})
              </p>
            )}
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Ingresos y deducciones: {resultado.fuente === 'contabilidad' ? 'contabilidad' : 'bóveda de CFDI'}
            </p>
          </div>
          <AvisoPorConfirmar fuentes={resultado.fuentes_por_confirmar ?? []} />
          <TablaMeses etiqueta="Pagos provisionales"
            columnas={resultado.tipo === 'pm' ? COLUMNAS_PM : COLUMNAS_RESICO}
            filas={resultado.pagos as unknown as Record<string, unknown>[]} />
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {resultado.notas.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}
