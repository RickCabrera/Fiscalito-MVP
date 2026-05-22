/** Componente reutilizable de upload de XMLs CFDI con drag & drop */

import { useState, useRef, useCallback } from 'react';
import { parseMultipleCFDI } from '../../services/cfdiParser';
import type { CFDI } from '../../services/fiscalAgentApi';
import { Upload, Trash2, FileText, AlertCircle } from 'lucide-react';

interface Props {
  facturas: CFDI[];
  onChange: (facturas: CFDI[]) => void;
}

export default function XMLUploader({ facturas, onChange }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [parseErrors, setParseErrors] = useState<{ fileName: string; error: string }[]>([]);
  const [duplicadas, setDuplicadas] = useState(0);

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const xmlFiles = Array.from(files).filter((f) => f.name.endsWith('.xml'));
    if (xmlFiles.length === 0) return;
    const result = await parseMultipleCFDI(xmlFiles);
    const existingUuids = new Set(facturas.map((f) => f.uuid));
    const nuevas = result.success.filter((f) => !existingUuids.has(f.uuid));
    const omitidas = result.success.length - nuevas.length;
    if (omitidas > 0) setDuplicadas(omitidas);
    onChange([...facturas, ...nuevas]);
    if (result.errors.length > 0) {
      setParseErrors((prev) => [...prev, ...result.errors]);
    }
  }, [facturas, onChange]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--teal-light)' : 'var(--border-hover)'}`,
          borderRadius: 'var(--radius)', padding: '32px 24px', textAlign: 'center',
          cursor: 'pointer', transition: 'all 0.2s',
          background: dragging ? 'var(--teal-bg-subtle)' : 'transparent',
        }}
      >
        <Upload size={28} color="var(--text-secondary)" style={{ marginBottom: 8 }} />
        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
          Arrastra tus archivos XML aquí
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          o haz clic para seleccionar CFDIs
        </div>
        <input ref={fileInputRef} type="file" accept=".xml" multiple hidden
          onChange={(e) => e.target.files && handleFiles(e.target.files)} />
      </div>

      {/* Parse errors */}
      {parseErrors.length > 0 && (
        <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-xs)', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)' }}>
          {parseErrors.map((err, i) => (
            <div key={i} style={{ fontSize: '0.78rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={12} /> {err.fileName}: {err.error}
            </div>
          ))}
        </div>
      )}

      {/* Duplicadas */}
      {duplicadas > 0 && (
        <div style={{ padding: '8px 12px', borderRadius: 'var(--radius-xs)', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', fontSize: '0.78rem', color: 'var(--warning)' }}>
          {duplicadas} factura{duplicadas > 1 ? 's' : ''} omitida{duplicadas > 1 ? 's' : ''} — UUID ya cargado.
        </div>
      )}

      {/* Summary badge */}
      {facturas.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px', borderRadius: 'var(--radius-xs)',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={16} color="var(--teal-light)" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
              {facturas.length} factura{facturas.length > 1 ? 's' : ''} cargada{facturas.length > 1 ? 's' : ''}
            </span>
          </div>
          <button onClick={() => { onChange([]); setParseErrors([]); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem' }}>
            <Trash2 size={14} /> Limpiar
          </button>
        </div>
      )}
    </div>
  );
}
