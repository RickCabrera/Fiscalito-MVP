/**
 * Tab "Reportes" de Contabilito (P2-05): selector de reporte con sus filtros,
 * vista previa y descarga en Excel (lo genera el backend con openpyxl) y PDF
 * (jspdf en el navegador, transcribiendo la misma respuesta). Todo importe lo
 * calcula el backend; aquí sólo se pinta y se transcribe.
 */

import { useEffect, useState } from 'react';
import { FileSpreadsheet, FileText, Loader, Scale } from 'lucide-react';
import {
  descargarExcel, listarCuentas, obtenerAuxiliar, obtenerBalanceGeneral, obtenerBalanza,
  obtenerEstadoResultados, obtenerPolizasImpresion,
  type Auxiliar, type Balanza, type Cuenta, type EstadoFinanciero, type FiltrosReporte, type Poliza, type TipoReporte,
} from '../../services/contabilidadApi';
import { pdfAuxiliar, pdfBalanza, pdfEstadoFinanciero, pdfPolizas, type ClientePdf } from '../../services/pdfExportContabilidad';
import ErrorAlert from '../common/ErrorAlert';
import FiltrosReportes from './FiltrosReportes';
import TablaEstadoFinanciero from './TablaEstadoFinanciero';
import { descargarBlob, dinero, enArbol, mensaje, rangoDePeriodo } from './comun';

interface Props {
  clave: string;
  nombre: string;
  rfc: string;
  onVerBalanza: () => void;
}

type Datos =
  | { tipo: 'estado'; datos: EstadoFinanciero }
  | { tipo: 'balanza'; datos: Balanza }
  | { tipo: 'auxiliar'; datos: Auxiliar & { desde: string; hasta: string } }
  | { tipo: 'polizas'; datos: { total: number; truncado: boolean; polizas: Poliza[] } };

const hoy = new Date();

export default function ReportesContables({ clave, nombre, rfc, onVerBalanza }: Props) {
  const [reporte, setReporte] = useState<TipoReporte>('estado_resultados');
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [periodo, setPeriodo] = useState(hoy.getMonth() + 1);
  const [filtros, setFiltros] = useState<FiltrosReporte>({
    ...rangoDePeriodo(hoy.getFullYear(), hoy.getMonth() + 1), nivel: null, solo: 'con_saldo_o_movimiento',
    agrupar: 'cuenta', moneda: 'MXN', tipo_cambio: '', idioma: 'es', comparar: 'ninguno', incluir_cierre: false,
  });
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const cliente: ClientePdf = { nombre, rfc, clave };

  useEffect(() => {
    let vivo = true;
    listarCuentas(clave)
      .then((r) => { if (vivo) setCuentas(enArbol(r.cuentas)); })
      .catch(() => { if (vivo) setCuentas([]); });
    return () => { vivo = false; };
  }, [clave]);

  function cambiarPeriodo(a: number, p: number) {
    setAnio(a);
    setPeriodo(p);
    if (p !== -1) setFiltros((f) => ({ ...f, ...rangoDePeriodo(a, p) }));
  }

  const faltaTc = filtros.moneda !== 'MXN' && !(Number(filtros.tipo_cambio) > 0);
  const faltaCuenta = reporte === 'auxiliar' && cuentaId === null;
  const listo = !!filtros.desde && !!filtros.hasta && !faltaTc && !faltaCuenta;

  async function generar() {
    setCargando(true);
    setError(null);
    try {
      const { desde, hasta } = filtros;
      if (reporte === 'estado_resultados') setDatos({ tipo: 'estado', datos: await obtenerEstadoResultados(clave, filtros) });
      else if (reporte === 'balance_general') setDatos({ tipo: 'estado', datos: await obtenerBalanceGeneral(clave, filtros) });
      else if (reporte === 'balanza') setDatos({ tipo: 'balanza', datos: await obtenerBalanza(clave, desde, hasta, filtros.nivel, filtros.solo) });
      else if (reporte === 'auxiliar') setDatos({ tipo: 'auxiliar', datos: { ...(await obtenerAuxiliar(clave, cuentaId!, desde, hasta)), desde, hasta } });
      else setDatos({ tipo: 'polizas', datos: await obtenerPolizasImpresion(clave, desde, hasta) });
    } catch (e) {
      setDatos(null);
      setError(mensaje(e, 'No se pudo generar el reporte.'));
    } finally {
      setCargando(false);
    }
  }

  async function excel() {
    setDescargando(true);
    setError(null);
    try {
      const blob = await descargarExcel(clave, reporte, filtros, cuentaId);
      descargarBlob(`${reporte}_${clave}_${filtros.desde}_${filtros.hasta}.xlsx`, blob);
    } catch (e) {
      setError(mensaje(e, 'No se pudo descargar el Excel.'));
    } finally {
      setDescargando(false);
    }
  }

  function pdf() {
    if (!datos) return;
    try {
      if (datos.tipo === 'estado') pdfEstadoFinanciero(datos.datos);
      else if (datos.tipo === 'balanza') pdfBalanza(datos.datos, cliente);
      else if (datos.tipo === 'auxiliar') pdfAuxiliar(datos.datos, cliente);
      else pdfPolizas(datos.datos.polizas, cliente, filtros.desde, filtros.hasta);
    } catch (e) {
      setError(mensaje(e, 'No se pudo generar el PDF.'));
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <FiltrosReportes reporte={reporte} onReporte={(r) => { setReporte(r); setDatos(null); }}
        anio={anio} periodo={periodo} onPeriodo={cambiarPeriodo} filtros={filtros} onFiltros={setFiltros}
        cuentas={cuentas.filter((c) => c.tipo !== 'orden')} cuentaId={cuentaId} onCuenta={setCuentaId} />

      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" className="btn-primary" disabled={!listo || cargando} onClick={() => void generar()}>
          {cargando ? <Loader size={14} className="spin" /> : null} Generar reporte
        </button>
        <button type="button" className="btn-secondary" disabled={!listo || descargando} onClick={() => void excel()}>
          <FileSpreadsheet size={14} /> Excel
        </button>
        <button type="button" className="btn-secondary" disabled={!datos} onClick={pdf}>
          <FileText size={14} /> PDF
        </button>
        <button type="button" className="btn-secondary" onClick={onVerBalanza}>
          <Scale size={14} /> Ver balanza dinámica
        </button>
        {faltaTc && <span style={{ color: 'var(--warning)', fontSize: '0.82rem' }}>Captura el tipo de cambio para presentar en {filtros.moneda}.</span>}
        {faltaCuenta && <span style={{ color: 'var(--warning)', fontSize: '0.82rem' }}>Elige la cuenta del auxiliar.</span>}
      </div>

      {error && <ErrorAlert message={error} />}

      {datos?.tipo === 'estado' && <TablaEstadoFinanciero reporte={datos.datos} />}
      {datos?.tipo === 'balanza' && (
        <div className="card" role="status">
          Balanza del {datos.datos.desde} al {datos.datos.hasta}: {datos.datos.renglones.length} cuentas ·
          cargos {dinero(datos.datos.totales.cargos, '0.00')} · abonos {dinero(datos.datos.totales.abonos, '0.00')} ·{' '}
          <strong style={{ color: datos.datos.cuadra ? 'var(--success)' : 'var(--danger)' }}>
            {datos.datos.cuadra ? 'cuadra' : 'NO cuadra'}
          </strong>
        </div>
      )}
      {datos?.tipo === 'auxiliar' && (
        <div className="card" role="status">
          Auxiliar {datos.datos.cuenta.numero} {datos.datos.cuenta.nombre}: saldo inicial {dinero(datos.datos.saldo_inicial, '0.00')} ·
          {' '}{datos.datos.movimientos.length} movimientos · saldo final {dinero(datos.datos.saldo_final, '0.00')}
        </div>
      )}
      {datos?.tipo === 'polizas' && (
        <div className="card" role="status">
          {datos.datos.total} pólizas del periodo{datos.datos.truncado ? ' (se imprimen las primeras 2000)' : ''}. Descárgalas en PDF o Excel.
        </div>
      )}
    </div>
  );
}
