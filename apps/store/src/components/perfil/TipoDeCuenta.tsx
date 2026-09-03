/**
 * La tarjeta de "Tipo de cuenta" del perfil.
 *
 * SE EXTRAJO EN O-01, Y POR UNA RAZÓN CONCRETA
 * --------------------------------------------
 * `ProfilePage.tsx` estaba en 298 líneas y la Configuración de empresa la
 * empujaba a 333, contra el tope de 300 de `apps/store/CLAUDE.md` (sección
 * NUNCA). La deuda de archivos por encima del tope lleva dos corridas anotada
 * en `backlog.md` §G punto 4 y en el `nocturno-log`; ésta no se suma a la pila.
 *
 * QUIÉN ELIGE Y QUIÉN SÓLO VE
 * ---------------------------
 * Un despacho —o, en modo empresa única, quien opera la nómina— **no elige aquí
 * su tipo**: lo ve. E-05 lo decidió así porque cambiarse a contribuyente desde
 * esta pantalla dejaba la cuenta sin las pantallas con las que trabaja.
 *
 * Y la condición cuelga del perfil **guardado**, no del estado local: si
 * colgara del local, un contribuyente que clickeara la tarjeta de despacho por
 * curiosidad vería desaparecer el selector en ese mismo render, sin haber
 * guardado nada y sin forma de volver salvo recargando.
 */

import { Check } from 'lucide-react';
import { CONTRIBUTOR_TYPES, getProfileByType } from '../../services/contributorProfiles';
import type { ContributorType } from '../../services/contributorProfiles';
import { etiquetaDelPerfilOperador } from '../../services/navigation';
import { modoEmpresaUnica } from '../../services/modoEmpresa';

export default function TipoDeCuenta({
  /** El tipo GUARDADO decide si esto es un selector o una etiqueta. */
  esOperadorDeNomina,
  tipo,
  setTipo,
}: {
  esOperadorDeNomina: boolean;
  tipo: ContributorType | null;
  setTipo: (t: ContributorType) => void;
}) {
  const empresaUnica = modoEmpresaUnica();

  return (
    <div className="card animate-in" style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 16 }}>Tipo de cuenta</h3>
      {esOperadorDeNomina ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '1.2rem' }}>{getProfileByType('contador').icon}</span>
          <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>
            {empresaUnica ? etiquetaDelPerfilOperador() : getProfileByType('contador').label}
          </span>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 10,
          }}
        >
          {CONTRIBUTOR_TYPES.map((ct) => {
            const selected = tipo === ct.id;
            return (
              <button
                key={ct.id}
                onClick={() => setTipo(ct.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 14px',
                  background: selected ? 'var(--nav-active-bg)' : 'var(--bg-input)',
                  border: `1.5px solid ${selected ? 'var(--teal-light)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-primary)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  position: 'relative',
                }}
              >
                <span style={{ fontSize: '1.2rem' }}>{ct.icon}</span>
                <span style={{ fontSize: '0.85rem', fontWeight: selected ? 600 : 400 }}>
                  {ct.label}
                </span>
                {selected && (
                  <Check size={14} style={{ marginLeft: 'auto', color: 'var(--teal-light)' }} />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
