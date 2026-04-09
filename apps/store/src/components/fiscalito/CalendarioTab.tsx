/** Tab de calendario fiscal: muestra obligaciones del contribuyente */

import { useState, useEffect } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { obtenerCalendario, type ObligacionFiscal } from '../../services/fiscalAgentApi';
import { obtenerHistorial, type DeclaracionRecord } from '../../services/declaracionesHistory';
import { Calendar, Clock, AlertCircle, Loader, CheckCircle2 } from 'lucide-react';

const MES_NUM_TO_NAME: Record<number, string> = {
  1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
  7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
};

function getBadgeColor(periodicidad: string): { bg: string; border: string; color: string } {
  switch (periodicidad.toLowerCase()) {
    case 'mensual': return { bg: 'var(--teal-bg)', border: 'var(--border-hover)', color: 'var(--teal-light)' };
    case 'bimestral': return { bg: 'var(--purple-bg)', border: 'rgba(73,33,83,0.25)', color: 'var(--purple-light)' };
    case 'anual': return { bg: 'var(--success-bg)', border: 'var(--success-border)', color: 'var(--success)' };
    default: return { bg: 'var(--teal-bg)', border: 'var(--border-hover)', color: 'var(--teal-light)' };
  }
}

function isVencida(fecha: string): boolean {
  return new Date(fecha) < new Date();
}

function isProxima(fecha: string): boolean {
  const diff = new Date(fecha).getTime() - Date.now();
  return diff > 0 && diff < 15 * 24 * 60 * 60 * 1000;
}

// Cross-references an obligation against the user's saved declarations to
// determine whether it has already been filed. The Fiscal Agent API is
// stateless and always returns completada=false, so we compute it here.
function isObligacionCompletada(
  ob: ObligacionFiscal,
  historial: DeclaracionRecord[],
  year: number,
): boolean {
  const nombreLower = ob.nombre.toLowerCase();
  const yearStr = String(year);

  // "Declaracion mensual mes N" → match against predeclaracion mensual "<MesNombre> <year>"
  const mensualMatch = nombreLower.match(/declaraci[oó]n mensual mes (\d+)/);
  if (mensualMatch) {
    const mesNum = parseInt(mensualMatch[1], 10);
    const mesNombre = MES_NUM_TO_NAME[mesNum];
    if (!mesNombre) return false;
    return historial.some((r) => {
      const periodoLower = (r.periodo ?? '').toLowerCase();
      return r.categoria === 'predeclaracion'
        && r.tipo === 'mensual'
        && periodoLower.includes(mesNombre)
        && periodoLower.includes(yearStr);
    });
  }

  // "Declaracion anual" → match against predeclaracion with tipo containing "anual"
  if (nombreLower.includes('declaraci') && nombreLower.includes('anual')) {
    return historial.some((r) => {
      const tipoLower = (r.tipo ?? '').toLowerCase();
      const periodoLower = (r.periodo ?? '').toLowerCase();
      return r.categoria === 'predeclaracion'
        && tipoLower.includes('anual')
        && periodoLower.includes(yearStr);
    });
  }

  return false;
}

export default function CalendarioTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const [obligaciones, setObligaciones] = useState<ObligacionFiscal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!profile.rfc || !profile.regimen) {
      setError('Completa tu RFC y régimen en tu perfil para ver tu calendario.');
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        const yearActual = new Date().getFullYear();
        const [res, historial] = await Promise.all([
          obtenerCalendario({
            rfc: profile.rfc,
            regimen: profile.regimen,
            contributor_type: profile.contributorType || 'independiente',
            year: yearActual,
          }),
          user?.uid ? obtenerHistorial(user.uid, 100) : Promise.resolve([]),
        ]);

        const obligacionesConEstado = res.obligaciones.map((ob) => ({
          ...ob,
          completada: isObligacionCompletada(ob, historial, yearActual),
        }));
        setObligaciones(obligacionesConEstado);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Error al cargar calendario');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [profile.rfc, profile.regimen, profile.contributorType, user?.uid]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60, gap: 12, color: 'var(--text-muted)' }}>
        <Loader size={20} className="spin" /> Cargando calendario fiscal...
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 40 }}>
        <AlertCircle size={32} color="var(--text-muted)" style={{ marginBottom: 12 }} />
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{error}</p>
      </div>
    );
  }

  if (obligaciones.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 40 }}>
        <Calendar size={32} color="var(--text-muted)" style={{ marginBottom: 12 }} />
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No se encontraron obligaciones fiscales.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {obligaciones.map((ob, i) => {
        const completada = ob.completada === true;
        const vencida = !completada && isVencida(ob.fecha_limite);
        const proxima = !completada && isProxima(ob.fecha_limite);
        const badge = getBadgeColor(ob.periodicidad);

        const borderColor = completada
          ? 'var(--success)'
          : vencida ? 'var(--danger)'
          : proxima ? 'var(--teal-light)'
          : 'var(--border)';

        const iconBg = completada
          ? 'var(--success-bg)'
          : vencida ? 'var(--danger-bg)'
          : 'var(--purple-bg-subtle)';

        const iconColor = completada
          ? 'var(--success)'
          : vencida ? 'var(--danger)'
          : 'var(--teal-light)';

        const fechaColor = completada
          ? 'var(--success)'
          : vencida ? 'var(--danger)'
          : proxima ? 'var(--teal-light)'
          : 'var(--text-secondary)';

        return (
          <div key={i} className="card animate-in" style={{
            animationDelay: `${i * 0.05}s`, display: 'flex', alignItems: 'center', gap: 16,
            borderLeft: `3px solid ${borderColor}`,
            opacity: completada ? 0.65 : 1,
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: 'var(--radius-xs)', flexShrink: 0,
              background: iconBg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {completada
                ? <CheckCircle2 size={20} color={iconColor} />
                : <Clock size={18} color={iconColor} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{
                fontWeight: 600, fontSize: '0.9rem', marginBottom: 2,
                textDecoration: completada ? 'line-through' : 'none',
                color: completada ? 'var(--text-secondary)' : 'var(--text-primary)',
              }}>
                {ob.nombre}
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{ob.descripcion}</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: '0.82rem',
                color: fechaColor,
                fontWeight: 600,
              }}>
                {new Date(ob.fecha_limite).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
              <span style={{
                padding: '2px 10px', borderRadius: 'var(--radius-full)', fontSize: '0.68rem',
                fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                background: completada ? 'var(--success-bg)' : badge.bg,
                border: `1px solid ${completada ? 'var(--success-border)' : badge.border}`,
                color: completada ? 'var(--success)' : badge.color,
              }}>
                {completada ? 'Cumplida' : ob.periodicidad}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
