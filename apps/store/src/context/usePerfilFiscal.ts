/**
 * Hook del perfil fiscal en uso (C-02). La regla vive en `perfilFiscal.ts`.
 *
 * Lee el cliente activo **sin exigir el proveedor**, igual que
 * `FiscalitoServicePage`: un contribuyente no tiene cartera, y sus pantallas
 * no pueden tronar por eso.
 */

import { useContext, useMemo } from 'react';
import { useProfile } from './ProfileContext';
import { ClienteActivoContext } from './clienteActivoStore';
import { resolverPerfilFiscal, type PerfilFiscal } from './perfilFiscal';

export function usePerfilFiscal(): PerfilFiscal {
  const { profile } = useProfile();
  const cliente = useContext(ClienteActivoContext)?.cliente ?? null;
  return useMemo(() => resolverPerfilFiscal(profile, cliente), [profile, cliente]);
}
