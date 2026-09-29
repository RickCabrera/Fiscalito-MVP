/**
 * Tab de declaración anual de persona física (T3).
 *
 * Clonado de `PreDeclaracionTab`, con tres diferencias que importan:
 *
 * 1. **El periodo es un EJERCICIO, no un mes**, y el backend NO filtra: el
 *    endpoint anual suma todas las facturas que le llegan. Por eso el filtro
 *    por año lo hace esta pantalla, y dice en voz alta cuántas dejó fuera.
 * 2. **Estado propio, no el del agente.** `PreDeclaracionTab` comparte sus
 *    facturas con `useAgent` porque el asistente conversa sobre el mes en curso;
 *    aquí se suben doce meses de XMLs, y volcarlos a ese estado compartido le
 *    cambiaría el periodo al otro tab por debajo.
 * 3. **Deducciones personales**, capturadas con la misma rejilla del tab del
 *    asalariado (`CapturaDeducciones`) y calculadas por su propio endpoint.
 *    Ver `ResultadoAnual` para por qué los dos resultados no se restan aquí.
 *
 * Sin lógica fiscal nueva: las dos cifras las produce el motor.
 */

import { useCallback, useState } from 'react';
import { usePerfilFiscal } from '../../context/usePerfilFiscal';
import { contribuyenteParaApi, mensajeFalta } from '../../context/perfilFiscal';
import { useAuth } from '../../context/AuthContext';
import {
  calcularPreDeclaracionAnual,
  calcularDeduccionesPersonales,
  type CFDI,
  type PreDeclaracionResponse,
  type DeduccionesPersonalesResponse,
  facturasFiscales,
} from '../../services/fiscalAgentApi';
import { guardarDeclaracion, desgloseRecordDesde } from '../../services/declaracionesHistory';
import { clasificarFacturaDeduccion, montosCapturados } from '../../services/deduccionesPersonales';
import { labelStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import FacturaTable from './FacturaTable';
import XMLUploader from './XMLUploader';
import CapturaDeducciones from './CapturaDeducciones';
import ResultadoAnual from './ResultadoAnual';
import FaltaDatoFiscal from './FaltaDatoFiscal';
import { AlertCircle, Calculator, Loader } from 'lucide-react';

const YEARS = [2026, 2025, 2024, 2023];

/**
 * RESICO no captura deducciones personales aquí.
 *
 * DECISIÓN PROVISIONAL (nocturno): no es una afirmación sobre el 113-E, es una
 * limitación honesta del cálculo disponible. `POST /api/v1/deducciones-personales`
 * estima el efecto con la tarifa general del Art. 152 y no recibe el régimen, así
 * que para un 626 devolvería un ahorro calculado con una tarifa que no es la suya.
 * Enseñar ese número sería peor que no enseñarlo. Pendiente de confirmar con la
 * contadora antes de abrirlo.
 */
function capturaDeduccionesAplica(regimen: string): boolean {
  return regimen !== '626';
}

export default function DeclaracionAnualTab() {
  const perfil = usePerfilFiscal();
  const { user } = useAuth();

  const [ejercicio, setEjercicio] = useState(YEARS[0]);
  const [facturas, setFacturas] = useState<CFDI[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [nivelEducativo, setNivelEducativo] = useState('');
  const [autoclasificadas, setAutoclasificadas] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<PreDeclaracionResponse | null>(null);
  const [deducciones, setDeducciones] = useState<DeduccionesPersonalesResponse | null>(null);
  const [guardado, setGuardado] = useState(false);

  const conDeducciones = capturaDeduccionesAplica(perfil.regimen);
  const delEjercicio = facturas.filter((f) => f.fecha.startsWith(String(ejercicio)));
  const fuera = facturas.length - delEjercicio.length;

  /**
   * `XMLUploader` es el dueño de la lista: de-duplica por UUID y reporta sus
   * propios errores de parseo. Aquí sólo se miran las facturas NUEVAS, para
   * prellenar la captura de deducciones por ClaveProdServ sin volver a sumar
   * las que ya estaban.
   *
   * El prellenado va FUERA del updater de `setFacturas` a propósito: React
   * puede invocar un updater dos veces (StrictMode), y sumar ahí duplicaría
   * los montos capturados.
   */
  const onFacturas = useCallback((siguientes: CFDI[]) => {
    const yaEstaban = new Set(facturas.map((f) => f.uuid));
    setFacturas(siguientes);
    if (!conDeducciones) return;

    const porCampo: Record<string, number> = {};
    for (const cfdi of siguientes) {
      if (yaEstaban.has(cfdi.uuid)) continue;
      const campo = clasificarFacturaDeduccion(cfdi.clave_prod_serv || '', cfdi.descripcion);
      if (campo) porCampo[campo] = (porCampo[campo] || 0) + (cfdi.subtotal - (cfdi.descuento || 0));
    }
    const cuantas = Object.keys(porCampo).length;
    if (cuantas === 0) return;

    setValues((vs) => {
      const next = { ...vs };
      for (const [campo, monto] of Object.entries(porCampo)) {
        next[campo] = (parseFloat(next[campo] || '0') + monto).toFixed(2);
      }
      return next;
    });
    setAutoclasificadas((n) => n + cuantas);
  }, [facturas, conDeducciones]);

  const quitar = (uuid: string) => setFacturas((prev) => prev.filter((f) => f.uuid !== uuid));

  const handleCalcular = async () => {
    if (delEjercicio.length === 0) {
      setError(`No hay facturas del ejercicio ${ejercicio}. Sube los XMLs del año que vas a declarar.`);
      return;
    }
    if (perfil.falta) {
      setError(mensajeFalta(perfil.falta));
      return;
    }
    if (conDeducciones && parseFloat(values['colegiaturas'] || '0') > 0 && !nivelEducativo) {
      setError('Selecciona el nivel educativo para calcular el tope de colegiaturas.');
      return;
    }

    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await calcularPreDeclaracionAnual({
        contribuyente: contribuyenteParaApi(perfil),
        facturas: facturasFiscales(delEjercicio),
        periodo_year: ejercicio,
        incluir_explicacion: true,
      });
      setResultado(res);

      // Las deducciones personales se calculan sobre la BASE del ejercicio que
      // acaba de devolver el motor, no sobre los ingresos brutos: es contra esa
      // base que el Art. 151 las resta. Si la base salió en cero o negativa el
      // endpoint las rechaza (exige ingresos > 0) y no hay ahorro que estimar.
      const capturado = conDeducciones ? montosCapturados(values) : {};
      let ded: DeduccionesPersonalesResponse | null = null;
      if (Object.keys(capturado).length > 0 && res.desglose.base_isr > 0) {
        ded = await calcularDeduccionesPersonales({
          ingresos_anuales: res.desglose.base_isr,
          incluir_explicacion: false,
          ...capturado,
          ...(nivelEducativo ? { nivel_educativo: nivelEducativo } : {}),
        });
      }
      setDeducciones(ded);

      if (user?.uid) {
        guardarDeclaracion(user.uid, {
          tipo: 'anual',
          periodo: res.periodo,
          regimen: res.regimen,
          fecha_calculo: new Date(),
          desglose: desgloseRecordDesde(res.desglose),
          explicacion: res.explicacion ?? null,
          advertencias: res.advertencias ?? [],
          recomendaciones: res.recomendaciones ?? [],
          facturas_count: delEjercicio.length,
        }, 'anual', perfil.clienteId).then(() => setGuardado(true)).catch(() => { /* el historial no bloquea el cálculo */ });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResultado(null);
    setDeducciones(null);
    setFacturas([]);
    setValues({});
    setNivelEducativo('');
    setAutoclasificadas(0);
    setError('');
  };

  // C-02: sin RFC (o sin régimen) del cliente no hay cálculo; se pide aquí.
  if (perfil.sujeto === 'cliente' && perfil.falta) return <FaltaDatoFiscal perfil={perfil} />;

  if (resultado) {
    return (
      <ResultadoAnual
        resultado={resultado}
        deducciones={deducciones}
        contribuyente={{ nombre: perfil.nombre, rfc: perfil.rfc }}
        guardado={guardado}
        onNueva={reset}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Declaración anual</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 16 }}>
          Sube los CFDI de todo el ejercicio. Sólo se calculan los del año seleccionado.
        </p>
        <label style={labelStyle}>Ejercicio</label>
        <select className="input-field" value={ejercicio} onChange={(e) => setEjercicio(Number(e.target.value))}
          style={{ width: 140, cursor: 'pointer' }}>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      <XMLUploader facturas={facturas} onChange={onFacturas} />

      {fuera > 0 && (
        <div style={{
          padding: '12px 16px', borderRadius: 'var(--radius-md)',
          background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
          display: 'flex', alignItems: 'flex-start', gap: 10,
        }}>
          <AlertCircle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
          <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {fuera} factura{fuera > 1 ? 's' : ''} fuera del ejercicio {ejercicio}:{' '}
            <strong>no entra{fuera > 1 ? 'n' : ''} al cálculo</strong>. Cambia el ejercicio si
            subiste el año equivocado.
          </span>
        </div>
      )}

      <FacturaTable facturas={delEjercicio} onRemove={quitar} />

      {conDeducciones ? (
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Deducciones personales (opcional)</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 16 }}>
            {autoclasificadas > 0
              ? `Se prellenaron ${autoclasificadas} concepto${autoclasificadas > 1 ? 's' : ''} desde los XMLs, por su ClaveProdServ. Revisa y corrige.`
              : 'Los XMLs de gastos médicos, colegiaturas y demás se clasifican solos al subirlos. También puedes capturarlos a mano.'}
          </p>
          <CapturaDeducciones
            values={values}
            onChange={setValues}
            nivelEducativo={nivelEducativo}
            onNivelChange={setNivelEducativo}
          />
        </div>
      ) : (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)' }}>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            Las deducciones personales no se capturan aquí para RESICO (626): el estimador de
            ahorro usa la tarifa general del Art. 152 y no la del 113-E, así que el número no
            sería el tuyo. Pendiente de confirmar con la contadora.
          </p>
        </div>
      )}

      <button className="btn-primary" onClick={handleCalcular} disabled={loading}
        style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
        {loading ? <Loader size={16} className="spin" /> : <Calculator size={16} />}
        {loading ? 'Calculando...' : `Calcular declaración anual ${ejercicio}`}
      </button>

      {error && <ErrorAlert message={error} />}
    </div>
  );
}
