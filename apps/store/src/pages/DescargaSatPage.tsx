/**
 * Descarga masiva del SAT del cliente activo (P1-01, P1-02).
 *
 * Opera sobre el **cliente activo** como la Bóveda: lee `useClienteActivo` y le
 * pide al backend la configuración, el calendario del mes y las solicitudes de
 * ESE cliente. Cada respuesta guarda para qué llave se pidió, así una respuesta
 * lenta del cliente anterior no se pinta sobre el nuevo.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Loader } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
  descargaHistorica, descargarAhora, guardarConfigSat, listarSolicitudesSat,
  obtenerBitacoraSat, obtenerConfigSat,
  type DiaBitacora, type PaginaSolicitudes, type RespuestaConfig,
} from '../services/satDescargaApi';
import CalendarioSat from '../components/sat/CalendarioSat';
import ConfigSat, { type CambiosConfig } from '../components/sat/ConfigSat';
import AccionesSat from '../components/sat/AccionesSat';
import ListaSolicitudesSat from '../components/sat/ListaSolicitudesSat';
import ErrorAlert from '../components/common/ErrorAlert';
import SuccessNotice from '../components/common/SuccessNotice';
import SinClienteActivo from '../components/common/SinClienteActivo';

const POR_PAGINA = 20;

interface Datos {
  llave: string;
  config: RespuestaConfig | null;
  dias: DiaBitacora[];
  solicitudes: PaginaSolicitudes | null;
  error: string | null;
}

function mensaje(e: unknown, defecto: string): string {
  return e instanceof Error ? e.message : defecto;
}

export default function DescargaSatPage() {
  const { clienteId, cliente, loading: cargandoCliente } = useClienteActivo();
  const hoy = new Date();
  const [mes, setMes] = useState({ anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 });
  const [pagina, setPagina] = useState(1);
  const [intento, setIntento] = useState(0);
  const [datos, setDatos] = useState<Datos | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [ocupado, setOcupado] = useState<'ahora' | 'historica' | null>(null);
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null);

  const llave = `${clienteId}|${mes.anio}-${mes.mes}|${pagina}|${intento}`;

  useEffect(() => {
    if (!clienteId) return;
    let cancelado = false;
    Promise.all([
      obtenerConfigSat(clienteId),
      obtenerBitacoraSat(clienteId, mes.anio, mes.mes),
      listarSolicitudesSat(clienteId, pagina, POR_PAGINA),
    ])
      .then(([config, dias, solicitudes]) => {
        if (!cancelado) setDatos({ llave, config, dias, solicitudes, error: null });
      })
      .catch((e: unknown) => {
        if (!cancelado) {
          setDatos({ llave, config: null, dias: [], solicitudes: null,
            error: mensaje(e, 'No se pudo cargar la descarga del SAT.') });
        }
      });
    return () => { cancelado = true; };
  }, [clienteId, mes, pagina, llave]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  const guardar = useCallback(async (c: CambiosConfig) => {
    if (!clienteId) return;
    setGuardando(true);
    setAviso(null);
    try {
      await guardarConfigSat(clienteId, c);
      setAviso({ ok: true, texto: 'Configuración guardada.' });
      recargar();
    } catch (e) {
      setAviso({ ok: false, texto: mensaje(e, 'No se pudo guardar la configuración.') });
    } finally {
      setGuardando(false);
    }
  }, [clienteId, recargar]);

  const encolar = useCallback(async (tipo: 'ahora' | 'historica', desde: string, hasta?: string) => {
    if (!clienteId) return;
    setOcupado(tipo);
    setAviso(null);
    try {
      const encolados = tipo === 'ahora'
        ? await descargarAhora(clienteId, desde, hasta ?? desde)
        : await descargaHistorica(clienteId, desde);
      setAviso({ ok: true, texto: `Se pidieron ${encolados.length} mes(es) al SAT. El SAT puede tardar horas; el calendario se actualiza solo.` });
      recargar();
    } catch (e) {
      setAviso({ ok: false, texto: mensaje(e, 'No se pudo pedir la descarga.') });
    } finally {
      setOcupado(null);
    }
  }, [clienteId, recargar]);

  if (!clienteId) {
    if (cargandoCliente) return <div className="page-container"><Loader className="spin" /></div>;
    return (
      <SinClienteActivo
        titulo="Descarga del SAT"
        explicacion="La descarga masiva se hace con la e.firma de UN cliente y baja sus CFDI a su bóveda."
      />
    );
  }

  const vigente = datos?.llave === llave ? datos : null;
  const efirma = vigente?.config?.efirma;

  return (
    <div className="page-container" style={{ display: 'grid', gap: 'var(--space-lg)' }}>
      <div className="page-header animate-in">
        <h1>Descarga del SAT</h1>
        <p>
          CFDI y metadata de <strong>{cliente?.nombre ?? clienteId}</strong> directo del SAT con su
          e.firma. Lo que baja entra a la bóveda una sola vez por UUID.
        </p>
      </div>

      {!vigente && (
        <div role="status" style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" /> Cargando…
        </div>
      )}
      {vigente?.error && (
        <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
          <ErrorAlert message={vigente.error} />
          <button type="button" className="btn-secondary" style={{ justifySelf: 'start' }} onClick={recargar}>Reintentar</button>
        </div>
      )}

      {efirma && !efirma.vigente && (
        <div role="alert" style={{
          display: 'flex', gap: 8, alignItems: 'center', padding: '12px 16px',
          borderRadius: 'var(--radius-xs)', background: 'var(--warning-bg)',
          border: '1px solid var(--warning-border)', color: 'var(--warning)',
        }}>
          <AlertTriangle size={18} />
          <span>
            {efirma.mensaje}{' '}
            <Link to={`/app/clientes/${encodeURIComponent(clienteId)}`}>Ir a la ficha del cliente</Link>
          </span>
        </div>
      )}
      {aviso && (aviso.ok ? <SuccessNotice message={aviso.texto} /> : <ErrorAlert message={aviso.texto} />)}
      {vigente?.config?.alertas.filter((a) => a.tipo !== 'sin_efirma').map((a) => (
        <div key={a.id} className="card" style={{ padding: 'var(--space-sm)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          <AlertTriangle size={14} color="var(--warning)" /> {a.mensaje}
        </div>
      ))}

      {vigente && !vigente.error && vigente.config && (
        <>
          <div style={{ display: 'grid', gap: 'var(--space-lg)', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
            <CalendarioSat anio={mes.anio} mes={mes.mes} dias={vigente.dias}
              onMes={(anio, m) => setMes({ anio, mes: m })} />
            <div style={{ display: 'grid', gap: 'var(--space-lg)', alignContent: 'start' }}>
              <ConfigSat key={`${clienteId}|${intento}`} config={vigente.config.config}
                guardando={guardando} onGuardar={(c) => void guardar(c)} />
              <AccionesSat deshabilitado={!efirma?.vigente} ocupado={ocupado}
                onAhora={(d, h) => void encolar('ahora', d, h)}
                onHistorica={(d) => void encolar('historica', d)} />
            </div>
          </div>
          <section style={{ display: 'grid', gap: 'var(--space-sm)' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Solicitudes al SAT</h2>
            {vigente.solicitudes && (
              <ListaSolicitudesSat solicitudes={vigente.solicitudes.solicitudes}
                total={vigente.solicitudes.total} pagina={vigente.solicitudes.pagina}
                porPagina={vigente.solicitudes.por_pagina} onPagina={setPagina} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
