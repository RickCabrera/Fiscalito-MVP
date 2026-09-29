/**
 * De quién es el RFC y el régimen con que se calcula (C-02).
 *
 * EL PROBLEMA QUE CIERRA
 * ----------------------
 * Cada tab de Fiscalito armaba su perfil desde el USUARIO: `profile.rfc` y
 * `profile.regimen`. Para un contribuyente es correcto. Para un contador no:
 * desde E-05 su perfil no tiene régimen, así que todos los tabs le contestaban
 * "Completa tu RFC y régimen en tu perfil"; y si tuviera RFC, el motor
 * clasificaría emitidas y recibidas con el del DESPACHO —`clasificar_facturas`
 * decide ingreso/egreso comparando contra ese RFC— y todo saldría como ajeno.
 *
 * Aquí se decide en UN solo lugar: contador → el cliente activo; cualquier otro
 * → el perfil, exactamente como antes. Módulo puro: se prueba sin React, y el
 * hook `usePerfilFiscal` sólo le pasa los dos contextos.
 */

import type { UserProfile } from './ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';
import { REGIMEN_CLIENTE_POR_DEFECTO } from '../services/carteraApi';
import { esContador } from '../services/navigation';
import { tipoParaApi, type ApiContributorType, type PerfilContribuyente } from '../services/fiscalAgentApi';

/**
 * Qué impide calcular. `perfil` es el caso del contribuyente (se le manda a su
 * perfil); los otros tres son del despacho y se resuelven en la cartera.
 */
export type DatoFaltante = 'perfil' | 'cliente' | 'rfc' | 'regimen';

export interface PerfilFiscal {
  sujeto: 'contribuyente' | 'cliente';
  rfc: string;
  /** Régimen con el que se CALCULA. Nunca sale de un default. */
  regimen: string;
  nombre: string;
  contributorType: ApiContributorType | null;
  /** Id del cliente activo; `null` para el contribuyente. Asocia el historial. */
  clienteId: string | null;
  /**
   * Régimen con el que se ESCOGEN LOS TABS (T1). A un cliente sin régimen se le
   * enseñan los del 612 con un aviso; eso es navegación, no cálculo, y por eso
   * vive separado de `regimen`: los dos datos salen de aquí para que la pantalla
   * y los tabs no se desalineen.
   */
  regimenParaTabs: string | null;
  /** `true` si `regimenParaTabs` salió del default y no del alta del cliente. */
  regimenSupuesto: boolean;
  falta: DatoFaltante | null;
}

export function resolverPerfilFiscal(
  profile: UserProfile,
  clienteActivo: ClienteResumen | null,
): PerfilFiscal {
  if (!esContador(profile.contributorType)) {
    // El contribuyente, literal como estaba en cada tab: sin normalizar nada.
    return {
      sujeto: 'contribuyente',
      rfc: profile.rfc,
      regimen: profile.regimen,
      nombre: profile.nombre,
      contributorType: tipoParaApi(profile.contributorType),
      clienteId: null,
      regimenParaTabs: profile.regimen,
      regimenSupuesto: false,
      falta: !profile.rfc || !profile.regimen ? 'perfil' : null,
    };
  }

  if (!clienteActivo) {
    return {
      sujeto: 'cliente', rfc: '', regimen: '', nombre: '', contributorType: null,
      clienteId: null, regimenParaTabs: null, regimenSupuesto: false, falta: 'cliente',
    };
  }

  const rfc = (clienteActivo.rfc ?? '').trim().toUpperCase();
  const regimen = clienteActivo.regimen ?? '';
  return {
    sujeto: 'cliente',
    rfc,
    // Sin régimen capturado NO se calcula. Los tabs se ven con el 612 supuesto,
    // pero un ISR calculado con un régimen que nadie capturó es un número falso
    // con cara de verdadero. Capturarlo es un clic: `ModalCliente` guarda el
    // régimen que enseña su select.
    regimen,
    nombre: clienteActivo.nombre,
    // Lo mismo que `tipoParaApi('contador')`: el despacho no es el sujeto, y el
    // tipo del cliente no existe como dato — el régimen es lo que manda.
    contributorType: null,
    clienteId: clienteActivo.id,
    regimenParaTabs: regimen || REGIMEN_CLIENTE_POR_DEFECTO,
    regimenSupuesto: !regimen,
    falta: !rfc ? 'rfc' : !regimen ? 'regimen' : null,
  };
}

/** El texto del error que se pinta al intentar calcular sin el dato. */
export function mensajeFalta(falta: DatoFaltante): string {
  switch (falta) {
    case 'perfil': return 'Completa tu RFC y régimen en tu perfil.';
    case 'cliente': return 'Elige un cliente en la barra de arriba.';
    case 'rfc': return 'Captura el RFC de este cliente.';
    case 'regimen': return 'Captura el régimen de este cliente.';
  }
}

/** El `contribuyente` de los requests de cálculo. Un solo armado para los seis tabs. */
export function contribuyenteParaApi(p: PerfilFiscal): PerfilContribuyente {
  return { rfc: p.rfc, regimen: p.regimen, contributor_type: p.contributorType };
}
