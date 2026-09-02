/**
 * Calendario patronal del despacho (E-07). Ruta `/app/calendario`.
 *
 * QUÉ ES Y QUÉ NO
 * ---------------
 * Las obligaciones **patronales** de los clientes: entero mensual del IMSS,
 * bimestral de RCV/Infonavit, avisos de variables, prima de RT, PTU, aguinaldo
 * y el entero del ISR retenido. **No** es el calendario de declaraciones ISR/IVA
 * del contribuyente, que es lo que este enlace mostraba hasta E-07 y que a un
 * despacho de nómina no le aplica (§D21).
 *
 * POR QUÉ AGRUPA POR (FECHA, OBLIGACIÓN) Y NO UNA FILA POR CLIENTE
 * ---------------------------------------------------------------
 * Hoy los tres calendarios de la cartera son idénticos —ninguna fecha depende
 * del cliente todavía—, así que una fila por cliente serían ~120 renglones
 * repetidos con tres nombres distintos: un dato constante disfrazado de dato por
 * cliente. La clave de agrupamiento incluye `condicional` y `nota` **además** de
 * la fecha y la clave: esos dos SÍ dependen de datos por cliente en cuanto F1-09
 * los registre, y sin ellos dos clientes con distinta personalidad jurídica se
 * colapsarían en un renglón y uno de los dos textos desaparecería sin que nada
 * fallara.
 *
 * `hoy` SE INYECTA
 * ----------------
 * "Vencida" y "próxima" dependen de la fecha del sistema. `despacho_demo.py`
 * documenta por qué en este repo nada de la demo cuelga de `date.today()`; aquí
 * se respeta haciendo que el cálculo sea una función pura con `hoy` como
 * argumento, y que la pantalla lo reciba como prop.
 */

import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { AlertTriangle, CalendarDays, Info, Loader } from 'lucide-react';
import { useProfile } from '../context/ProfileContext';
import { esContador } from '../services/navigation';
import { obtenerCalendarioPatronal, type CalendarioPatronal } from '../services/despachoApi';
import {
  agrupar,
  estadoDeFecha,
  ETIQUETA_PLAZO,
  fechaLarga,
  type EstadoFecha,
  type Renglon,
} from '../services/calendarioPatronal';
import ErrorAlert from '../components/common/ErrorAlert';
import { tituloSeccion } from '../components/nomina/estilosTabla';

const COLOR_ESTADO: Record<EstadoFecha, string> = {
  vencida: 'var(--text-muted)',
  proxima: 'var(--warning)',
  futura: 'var(--accent-active)',
};

function Insignia({ texto, color }: { texto: string; color: string }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 'var(--radius-full)', fontSize: '0.68rem',
      fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
      border: `1px solid ${color}`, color, whiteSpace: 'nowrap',
    }}>
      {texto}
    </span>
  );
}

function FilaObligacion({ renglon }: { renglon: Renglon }) {
  const { obligacion: o, clientes } = renglon;
  return (
    <div style={{
      display: 'flex', gap: 'var(--space-md)', alignItems: 'flex-start',
      padding: 'var(--space-sm) 0', borderTop: '1px solid var(--border)', flexWrap: 'wrap',
    }}>
      <div style={{ flex: '1 1 320px', minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: '0.92rem' }}>{o.nombre}</strong>
          <Insignia texto={ETIQUETA_PLAZO[o.regimen_de_plazo]} color="var(--text-muted)" />
          {o.condicional && <Insignia texto="Verificar" color="var(--warning)" />}
        </div>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          {o.descripcion}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
          {o.fundamento} · cubre {o.periodo_cubierto}
        </div>
        {o.nota && (
          <div style={{
            fontSize: '0.78rem', color: 'var(--warning)', marginTop: 4,
            display: 'flex', gap: 6, alignItems: 'flex-start',
          }}>
            <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 2 }} />
            <span>{o.nota}</span>
          </div>
        )}
      </div>
      <div style={{ flex: '0 1 220px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
        {clientes.join(' · ')}
      </div>
    </div>
  );
}

export default function CalendarioPatronalPage({ hoy = new Date() }: { hoy?: Date }) {
  const { profile } = useProfile();
  const [datos, setDatos] = useState<CalendarioPatronal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const anio = hoy.getFullYear();

  useEffect(() => {
    let cancelado = false;
    obtenerCalendarioPatronal(anio)
      .then((d) => { if (!cancelado) setDatos(d); })
      .catch((e: Error) => { if (!cancelado) setError(e.message); });
    return () => { cancelado = true; };
  }, [anio]);

  // Un contribuyente no tiene cartera: lo suyo es el calendario de sus propias
  // declaraciones. Va DESPUÉS de los hooks para no romper su orden entre
  // renders (mismo patrón que `DashboardPage`).
  if (!esContador(profile.contributorType)) {
    return <Navigate to="/app/store/fiscalito/use?tab=calendario" replace />;
  }

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Calendario patronal</h1>
        <p>
          Lo que hay que enterar, presentar o pagar por los clientes del despacho.{' '}
          {datos && datos.cubre_desde && datos.cubre_hasta && (
            <>Vencimientos del <strong>{datos.cubre_desde}</strong> al{' '}
            <strong>{datos.cubre_hasta}</strong> — son las obligaciones de las cuotas de{' '}
            {datos.anio_de_las_cuotas}, y las de diciembre vencen en enero del año siguiente.</>
          )}
        </p>
      </div>

      {/* La decisión §D21 dicha donde el contador la ve, no sólo en el registro. */}
      <p style={{
        display: 'flex', gap: 'var(--space-xs)', alignItems: 'flex-start',
        fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 'var(--space-lg)',
      }}>
        <Info size={14} style={{ flexShrink: 0, marginTop: 2 }} />
        <span>
          Este calendario es el de <strong>tus clientes</strong>. La app no calcula las
          obligaciones fiscales propias del despacho.
        </span>
      </p>

      {error && <ErrorAlert message={error} />}

      {!datos && !error && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--text-secondary)' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Cargando el calendario...
        </div>
      )}

      {datos && datos.obligaciones.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
          <CalendarDays size={24} color="var(--text-muted)" />
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: 10 }}>
            No hay obligaciones para este periodo.
          </p>
        </div>
      )}

      {datos && agrupar(datos.obligaciones).map(([fecha, renglones]) => {
        const estado = estadoDeFecha(fecha, hoy);
        return (
          <section
            key={fecha}
            className="card"
            style={{ marginBottom: 'var(--space-md)', borderLeft: `3px solid ${COLOR_ESTADO[estado]}` }}
          >
            <header style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'baseline', flexWrap: 'wrap' }}>
              <h2 style={tituloSeccion}>{fechaLarga(fecha)}</h2>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {fecha}
              </span>
              {estado !== 'futura' && (
                <Insignia
                  texto={estado === 'vencida' ? 'Vencida' : 'Próxima'}
                  color={COLOR_ESTADO[estado]}
                />
              )}
            </header>
            {/* La key separa LO MISMO que `agrupar`: en cuanto F1-09 registre el
                tipo de salario o la personalidad, dos renglones del mismo día
                pueden compartir clave y periodo y diferir sólo en
                `condicional`/`nota` — y React recibiría dos hijos con la misma
                key. Es el bug que la clave de agrupamiento existe para evitar. */}
            {renglones.map((r) => (
              <FilaObligacion
                key={[r.obligacion.clave, r.obligacion.periodo_cubierto,
                      r.obligacion.condicional, r.obligacion.nota].join('|')}
                renglon={r}
              />
            ))}
          </section>
        );
      })}

      {datos && (
        <ul style={{ fontSize: '0.8rem', color: 'var(--text-muted)', paddingLeft: 18, marginTop: 'var(--space-lg)' }}>
          {datos.advertencias.map((a) => <li key={a} style={{ marginBottom: 4 }}>{a}</li>)}
        </ul>
      )}
    </div>
  );
}
