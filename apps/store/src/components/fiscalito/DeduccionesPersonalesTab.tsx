/** Tab de deducciones personales para asalariados */

import { useState, useRef } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import {
  calcularDeduccionesPersonales,
  type DeduccionesPersonalesRequest,
  type DeduccionesPersonalesResponse,
} from '../../services/fiscalAgentApi';
import { guardarDeclaracion } from '../../services/declaracionesHistory';
import { parseMultipleCFDI } from '../../services/cfdiParser';
import { ACCEPT_XML, separarXml, type ArchivoRechazado } from '../../services/archivosXml';
import { clasificarFacturaDeduccion, montosCapturados } from '../../services/deduccionesPersonales';
import { labelStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import CapturaDeducciones from './CapturaDeducciones';
import DeduccionesResult from './DeduccionesResult';
import ErroresDeCarga from './ErroresDeCarga';
import { Calculator, Loader, Upload } from 'lucide-react';

export default function DeduccionesPersonalesTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const xmlInputRef = useRef<HTMLInputElement>(null);
  const [ingresos, setIngresos] = useState('');
  const [nivelEducativo, setNivelEducativo] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<DeduccionesPersonalesResponse | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [xmlsCargados, setXmlsCargados] = useState(false);
  const [facturasCount, setFacturasCount] = useState(0);
  const [facturasIgnoradas, setFacturasIgnoradas] = useState(0);
  const [mesesNomina, setMesesNomina] = useState(0);
  // C-03: lo que no se cargó (no es XML, o el parser no lo pudo leer) se muestra; antes se perdía.
  const [erroresCarga, setErroresCarga] = useState<ArchivoRechazado[]>([]);

  const handleXMLUpload = async (files: FileList | File[]) => {
    const { xml: xmlFiles, rechazados } = separarXml(files);
    if (rechazados.length > 0) setErroresCarga(prev => [...prev, ...rechazados]);
    if (xmlFiles.length === 0) return;
    const result = await parseMultipleCFDI(xmlFiles);
    if (result.errors.length > 0) setErroresCarga(prev => [...prev, ...result.errors]);
    const nuevosValues: Record<string, number> = {};
    let ignoradas = 0;
    for (const cfdi of result.success) {
      const campo = clasificarFacturaDeduccion(cfdi.clave_prod_serv || '', cfdi.descripcion);
      if (campo) { nuevosValues[campo] = (nuevosValues[campo] || 0) + (cfdi.subtotal - (cfdi.descuento || 0)); }
      else { ignoradas++; }
    }
    const rfc = profile.rfc?.toUpperCase() || '';
    const nominas = result.success.filter(f => f.rfc_receptor?.toUpperCase() === rfc && (f.clave_prod_serv === '84111505' || f.clave_prod_serv?.startsWith('8411')));
    if (nominas.length > 0) {
      const totalNominas = nominas.reduce((sum, f) => sum + (f.subtotal || 0), 0);
      const mesesSubidos = new Set(nominas.map(f => f.fecha?.substring(0, 7))).size;
      const estimadoAnual = mesesSubidos > 0 ? Math.round((totalNominas / mesesSubidos) * 12) : totalNominas * 12;
      setIngresos(estimadoAnual.toString());
      setMesesNomina(mesesSubidos);
    }
    const newValues: Record<string, string> = { ...values };
    for (const [campo, monto] of Object.entries(nuevosValues)) {
      const current = parseFloat(newValues[campo] || '0');
      newValues[campo] = (current + monto).toFixed(2);
    }
    setValues(newValues);
    setXmlsCargados(true);
    setFacturasCount(result.success.length);
    setFacturasIgnoradas(ignoradas);
  };

  const handleCalc = async () => {
    const ingresosNum = parseFloat(ingresos);
    if (!ingresosNum || ingresosNum <= 0) { setError('Ingresa tus ingresos anuales.'); return; }
    if (!profile.rfc) { setError('Completa tu RFC en tu perfil.'); return; }
    if (parseFloat(values['colegiaturas'] || '0') > 0 && !nivelEducativo) {
      setError('Selecciona el nivel educativo para calcular el tope de colegiaturas.'); return;
    }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const fields = montosCapturados(values);
      const req: DeduccionesPersonalesRequest = {
        ingresos_anuales: ingresosNum,
        incluir_explicacion: true,
        ...fields,
        ...(nivelEducativo ? { nivel_educativo: nivelEducativo } : {}),
      };
      const res = await calcularDeduccionesPersonales(req);
      setResultado(res);
      if (user?.uid) {
        const year = new Date().getFullYear();
        guardarDeclaracion(user.uid, {
          tipo: 'anual', periodo: `Ejercicio fiscal ${year}`, regimen: 'Sueldos y salarios (605)',
          fecha_calculo: new Date(),
          desglose: {
            total_ingresos_facturados: ingresosNum, total_ingresos_gravados: ingresosNum,
            cantidad_facturas_ingreso: 0, total_egresos: 0,
            total_deducciones_autorizadas: res.total_deducible, cantidad_facturas_egreso: 0,
            base_isr: ingresosNum - res.total_deducible, tasa_isr: 0, isr_causado: 0, isr_retenido: 0,
            isr_a_pagar: -res.saldo_a_favor_estimado,
            iva_trasladado_cobrado: 0, iva_trasladado_pagado: 0, iva_retenido: 0, iva_a_pagar: 0,
            total_a_pagar: -res.saldo_a_favor_estimado,
          },
          explicacion: res.explicacion ?? null, advertencias: [], recomendaciones: [],
          facturas_count: 0,
        }, 'deducciones').then(() => setGuardado(true)).catch(() => { /* silent */ });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setResultado(null); setValues({}); setIngresos(''); setError(''); setMesesNomina(0); setErroresCarga([]); };

  if (resultado) {
    return <DeduccionesResult resultado={resultado} guardado={guardado} onReset={reset} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Deducciones personales</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 20 }}>
          Sube tus XMLs de gastos y recibos de nómina. El sistema clasificará todo automáticamente.
        </p>
        <div>
          <label style={labelStyle}>Ingresos anuales totales (se calcula de tus recibos de nómina)</label>
          <input className="input-field" type="number" placeholder="Ej: 480000" value={ingresos}
            onChange={(e) => setIngresos(e.target.value)}
            style={{ fontFamily: "'JetBrains Mono', monospace", marginBottom: mesesNomina > 0 ? 4 : 20 }} />
          {mesesNomina > 0 && (
            <p style={{ fontSize: '0.75rem', color: 'var(--teal-light)', marginTop: 4, marginBottom: 20 }}>
              Calculado desde {mesesNomina} recibo{mesesNomina > 1 ? 's' : ''} de nómina.
              {mesesNomina < 12 ? ` Estimado anual (x${Math.round(12 / mesesNomina)}).` : ''}
              {' '}Puedes editarlo si no es correcto.
            </p>
          )}
        </div>

        <div style={{
          border: `2px dashed ${xmlsCargados ? 'var(--success-border)' : 'var(--border-hover)'}`,
          borderRadius: 'var(--radius)', padding: 20, textAlign: 'center', cursor: 'pointer', marginBottom: 20,
          background: xmlsCargados ? 'var(--success-bg)' : 'transparent',
        }} onClick={() => xmlInputRef.current?.click()}>
          <input ref={xmlInputRef} type="file" accept={ACCEPT_XML} multiple style={{ display: 'none' }}
            onChange={(e) => e.target.files && handleXMLUpload(e.target.files)} />
          <Upload size={20} style={{ color: 'var(--teal-light)', marginBottom: 8 }} />
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
            {xmlsCargados
              ? `${facturasCount} facturas procesadas${facturasIgnoradas > 0 ? ` (${facturasIgnoradas} no son deducciones personales)` : ''}`
              : 'Sube tus XMLs de gastos médicos, colegiaturas, etc. para prellenar automáticamente'}
          </p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
            El sistema clasificará cada factura según su ClaveProdServ del SAT
          </p>
        </div>
        {erroresCarga.length > 0 && (
          <div style={{ marginTop: -8, marginBottom: 20 }}><ErroresDeCarga errores={erroresCarga} /></div>
        )}

        <CapturaDeducciones
          values={values}
          onChange={setValues}
          nivelEducativo={nivelEducativo}
          onNivelChange={setNivelEducativo}
        />
      </div>

      <button className="btn-primary" onClick={handleCalc} disabled={loading}
        style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
        {loading ? <Loader size={16} className="spin" /> : <Calculator size={16} />}
        {loading ? 'Calculando...' : 'Calcular deducciones'}
      </button>

      {error && <ErrorAlert message={error} />}
    </div>
  );
}
