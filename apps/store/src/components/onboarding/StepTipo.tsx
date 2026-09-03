/**
 * Step 1: Selector de tipo de contribuyente con cards visuales.
 *
 * O-01 · EN MODO EMPRESA ÚNICA HAY UNA SOLA OPCIÓN
 * ------------------------------------------------
 * Y no es cosmética. Sin esto, quien abre una cuenta para llevar **su propia
 * nómina** tendría que elegir "Despacho / Contador" —que es falso— para llegar
 * a la app que necesita, y cualquier otra opción lo dejaría en la app de
 * contribuyente, sin Empleados ni Nómina. El criterio de O-01 ("alta de
 * empleado → nómina → exportar") no sería alcanzable de verdad.
 *
 * El id guardado **sigue siendo `contador`**: es la llave que ya tienen todas
 * las cuentas en Firestore y renombrarla sería una migración de datos a cambio
 * de nada. Lo que cambia es cómo se llama en pantalla
 * (`etiquetaDelPerfilOperador`).
 */

import { Check } from 'lucide-react';
import { CONTRIBUTOR_TYPES } from '../../services/contributorProfiles';
import type { ContributorType } from '../../services/contributorProfiles';
import { modoEmpresaUnica } from '../../services/modoEmpresa';
import { esContador, etiquetaDelPerfilOperador } from '../../services/navigation';

interface StepTipoProps {
  tipo: ContributorType | null;
  setTipo: (t: ContributorType) => void;
}

export default function StepTipo({ tipo, setTipo }: StepTipoProps) {
  const empresaUnica = modoEmpresaUnica();
  const opciones = empresaUnica
    ? CONTRIBUTOR_TYPES.filter((ct) => esContador(ct.id))
    : CONTRIBUTOR_TYPES;

  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        {empresaUnica ? 'Confirma el tipo de cuenta' : '¿Que tipo de cuenta es?'}
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        {empresaUnica
          ? 'Esta app lleva la nómina de una empresa: sus empleados, su checador y sus cuotas al IMSS.'
          : 'Esto nos permite mostrarte solo los servicios y obligaciones que aplican a tu situacion. ' +
            'Si llevas la contabilidad de varios clientes, elige Despacho / Contador.'}
      </p>

      <div style={{ display: 'grid', gap: 12 }}>
        {opciones.map((ct) => {
          const selected = tipo === ct.id;
          return (
            <button
              key={ct.id}
              onClick={() => setTipo(ct.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '20px 24px',
                background: selected ? 'var(--nav-active-bg)' : 'var(--bg-card)',
                border: `1.5px solid ${selected ? 'var(--teal-light)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                color: 'var(--text-primary)',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <div style={{
                width: 52, height: 52, borderRadius: 'var(--radius-sm)',
                background: selected ? 'var(--accent-gradient)' : 'var(--bg-input)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1.5rem', flexShrink: 0,
                transition: 'background 0.2s',
              }}>
                {ct.icon}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '1.05rem', marginBottom: 2 }}>
                  {empresaUnica && esContador(ct.id) ? etiquetaDelPerfilOperador() : ct.label}
                </div>
                <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                  {empresaUnica && esContador(ct.id)
                    ? 'Nómina, empleados, checador y cuotas al IMSS de la empresa.'
                    : ct.description}
                </div>
              </div>
              {selected && (
                <div style={{
                  marginLeft: 'auto',
                  width: 24, height: 24, borderRadius: '50%',
                  background: 'var(--teal-light)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Check size={14} color="var(--bg-dark)" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
