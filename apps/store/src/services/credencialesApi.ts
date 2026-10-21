/**
 * Bóveda de credenciales del cliente (P0-05): e.firma (FIEL) y CSD.
 *
 * El front SUBE el .cer, la .key y la contraseña una sola vez; después sólo ve metadatos
 * (RFC, número de certificado, vigencia). La llave privada nunca regresa del backend.
 */

import { apiFetch } from './api';

export type TipoCredencial = 'efirma' | 'csd';

export interface Credencial {
  id: number;
  tipo: TipoCredencial;
  rfc: string;
  numero_certificado: string;
  valido_desde: string;
  valido_hasta: string;
  dias_para_vencer: number;
  vencida: boolean;
  por_vencer: boolean;
  creado_por: string;
  creado_en: string | null;
}

export const NOMBRE_TIPO: Record<TipoCredencial, string> = {
  efirma: 'e.firma (FIEL)',
  csd: 'Sello digital (CSD)',
};

const ruta = (clave: string) => `/clientes/${encodeURIComponent(clave)}/credenciales`;

export async function listarCredenciales(clave: string): Promise<Credencial[]> {
  const r = await apiFetch<{ credenciales: Credencial[] }>(ruta(clave));
  return r.credenciales ?? [];
}

export async function subirCredencial(
  clave: string,
  tipo: TipoCredencial,
  cer: File,
  key: File,
  password: string,
): Promise<Credencial> {
  const datos = new FormData();
  datos.append('tipo', tipo);
  datos.append('password', password);
  datos.append('cer', cer);
  datos.append('key', key);
  const r = await apiFetch<{ credencial: Credencial }>(ruta(clave), { method: 'POST', body: datos });
  return r.credencial;
}

export async function borrarCredencial(clave: string, id: number): Promise<void> {
  await apiFetch(`${ruta(clave)}/${id}`, { method: 'DELETE' });
}
