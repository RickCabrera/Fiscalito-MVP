/**
 * Bóveda de CFDI del cliente activo (plan P, P0-03).
 *
 * Opera sobre el **cliente activo** del selector superior, como Empleados y
 * Dispositivos: sin cliente, la pantalla lo pide en vez de caer en un default.
 * La lista guarda **para qué cliente y con qué filtros** se pidió y lo demás se
 * deriva comparando: así una respuesta lenta del cliente anterior no se pinta
 * sobre el nuevo, y no hay `setState` sincrónico dentro del efecto.
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
  descargarXml,
  listarCfdi,
  type FiltrosBoveda as Filtros,
  type PaginaBoveda,
} from '../services/bovedaApi';
import CargaBoveda from '../components/boveda/CargaBoveda';
import FiltrosBoveda from '../components/boveda/FiltrosBoveda';
import TablaBoveda from '../components/boveda/TablaBoveda';
import ErrorAlert from '../components/common/ErrorAlert';
import SinClienteActivo from '../components/common/SinClienteActivo';

const POR_PAGINA = 50;

interface Carga {
  llave: string;
  pagina: PaginaBoveda | null;
  error: string | null;
}

export default function BovedaPage() {
  const { clienteId, cliente, loading: cargandoCliente } = useClienteActivo();
  const [filtros, setFiltros] = useState<Filtros>({ pagina: 1, por_pagina: POR_PAGINA });
  const [carga, setCarga] = useState<Carga | null>(null);
  const [intento, setIntento] = useState(0);
  const [descargando, setDescargando] = useState<string | null>(null);
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null);

  const llave = `${clienteId}|${JSON.stringify(filtros)}|${intento}`;

  useEffect(() => {
    if (!clienteId) return;
    let cancelado = false;
    listarCfdi(clienteId, filtros)
      .then((p) => { if (!cancelado) setCarga({ llave, pagina: p, error: null }); })
      .catch((e: unknown) => {
        if (cancelado) return;
        setCarga({
          llave, pagina: null,
          error: e instanceof Error ? e.message : 'No se pudo cargar la bóveda.',
        });
      });
    return () => { cancelado = true; };
  }, [clienteId, filtros, llave]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  const descargar = useCallback(async (uuid: string) => {
    if (!clienteId) return;
    setDescargando(uuid);
    setErrorDescarga(null);
    try {
      const blob = await descargarXml(clienteId, uuid);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${uuid}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorDescarga(e instanceof Error ? e.message : 'No se pudo descargar el XML.');
    } finally {
      setDescargando(null);
    }
  }, [clienteId]);

  if (!clienteId) {
    if (cargandoCliente) return <div className="page-container"><Loader className="spin" /></div>;
    return (
      <SinClienteActivo
        titulo="Bóveda de CFDI"
        explicacion="La bóveda guarda los comprobantes de UN cliente: emitidos y recibidos se distinguen por su RFC."
      />
    );
  }

  const vigente = carga?.llave === llave ? carga : null;

  return (
    <div className="page-container" style={{ display: 'grid', gap: 'var(--space-lg)' }}>
      <div className="page-header animate-in">
        <h1>Bóveda de CFDI</h1>
        <p>
          Comprobantes de <strong>{cliente?.nombre ?? clienteId}</strong>. Sube XML o ZIP: cada
          UUID se guarda una sola vez y se clasifica como emitido o recibido por el RFC del cliente.
        </p>
      </div>

      <CargaBoveda key={clienteId} clave={clienteId} onImportado={recargar} />

      <FiltrosBoveda valor={filtros} onCambio={setFiltros} />

      {errorDescarga && <ErrorAlert message={errorDescarga} />}
      {!vigente && (
        <div role="status" style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" /> Cargando comprobantes…
        </div>
      )}
      {vigente?.error && (
        <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
          <ErrorAlert message={vigente.error} />
          <button type="button" className="btn-secondary" style={{ justifySelf: 'start' }} onClick={recargar}>
            Reintentar
          </button>
        </div>
      )}
      {vigente?.pagina && vigente.pagina.total === 0 && (
        <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center', color: 'var(--text-secondary)' }}>
          No hay comprobantes con estos filtros.
        </div>
      )}
      {vigente?.pagina && vigente.pagina.total > 0 && (
        <TablaBoveda
          filas={vigente.pagina.comprobantes}
          total={vigente.pagina.total}
          pagina={vigente.pagina.pagina}
          porPagina={vigente.pagina.por_pagina}
          descargando={descargando}
          onPagina={(p) => setFiltros((f) => ({ ...f, pagina: p }))}
          onDescargar={(uuid) => void descargar(uuid)}
        />
      )}
    </div>
  );
}
