/**
 * Bitácora de auditoría del despacho (P0-07): quién hizo qué, a qué cliente y cuándo.
 *
 * Se entra desde Perfil, no desde el sidebar (mismo criterio que Planes: no es una
 * herramienta diaria). El backend sólo la abre a `dueno` y `contador`; un auxiliar ve el
 * 403 como error en pantalla.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader } from 'lucide-react';
import ErrorAlert from '../components/common/ErrorAlert';
import TablaAuditoria from '../components/auditoria/TablaAuditoria';
import { listarAuditoria, type FiltrosAuditoria, type PaginaAuditoria } from '../services/trabajosApi';

const POR_PAGINA = 50;
const VACIOS = { usuario: '', cliente: '', accion: '', desde: '', hasta: '' };
type Campos = typeof VACIOS;

const CAMPOS: Array<[keyof Campos, string, string]> = [
  ['usuario', 'Usuario (uid)', 'text'],
  ['cliente', 'Cliente (clave)', 'text'],
  ['accion', 'Acción (p. ej. trabajo.*)', 'text'],
  ['desde', 'Desde', 'date'],
  ['hasta', 'Hasta', 'date'],
];

export default function AuditoriaPage() {
  const [borrador, setBorrador] = useState<Campos>(VACIOS);
  const [filtros, setFiltros] = useState<Campos>(VACIOS);
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<PaginaAuditoria | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vigente = true;
    const consulta: FiltrosAuditoria = { pagina, por_pagina: POR_PAGINA };
    for (const [k, v] of Object.entries(filtros)) {
      if (v) (consulta as Record<string, string>)[k] = v;
    }
    listarAuditoria(consulta)
      .then((d) => { if (vigente) { setDatos(d); setError(null); } })
      .catch((e: unknown) => {
        if (vigente) setError(e instanceof Error ? e.message : 'No se pudo cargar la bitácora.');
      })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [filtros, pagina]);

  const aplicar = (e: React.FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setPagina(1);
    setFiltros(borrador);
  };

  const irA = (p: number) => { setCargando(true); setPagina(p); };
  const paginas = datos ? Math.max(1, Math.ceil(datos.total / POR_PAGINA)) : 1;

  return (
    <div className="page-container">
      <Link
        to="/app/profile"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 'var(--space-lg)' }}
      >
        <ArrowLeft size={16} /> Perfil
      </Link>
      <div className="page-header animate-in">
        <h1>Bitácora de auditoría</h1>
        <p>Cada cambio que se hace en el despacho: quién, a qué cliente y cuándo.</p>
      </div>

      <form
        onSubmit={aplicar}
        className="card"
        style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 'var(--space-sm)', alignItems: 'end', marginBottom: 'var(--space-lg)',
        }}
      >
        {CAMPOS.map(([campo, etiqueta, tipo]) => (
          <label key={campo} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {etiqueta}
            <input
              className="input-field"
              type={tipo}
              value={borrador[campo]}
              onChange={(e) => setBorrador((b) => ({ ...b, [campo]: e.target.value }))}
              style={{ marginTop: 4 }}
            />
          </label>
        ))}
        <button className="btn-primary" type="submit">Filtrar</button>
      </form>

      {error && <ErrorAlert message={error} />}
      {cargando && !error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={18} className="spin" /> Cargando la bitácora...
        </div>
      )}
      {!cargando && !error && datos && datos.eventos.length === 0 && (
        <p style={{ color: 'var(--text-muted)' }}>No hay renglones con esos filtros.</p>
      )}
      {!cargando && !error && datos && datos.eventos.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-lg)' }}>
          <TablaAuditoria eventos={datos.eventos} />
          <div
            style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginTop: 'var(--space-md)', fontSize: '0.85rem', color: 'var(--text-secondary)',
            }}
          >
            <span>{datos.total} renglones · página {datos.pagina} de {paginas}</span>
            <span style={{ display: 'flex', gap: 'var(--space-xs)' }}>
              <button className="btn-secondary" disabled={pagina <= 1} onClick={() => irA(pagina - 1)}>
                Anterior
              </button>
              <button className="btn-secondary" disabled={pagina >= paginas} onClick={() => irA(pagina + 1)}>
                Siguiente
              </button>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
