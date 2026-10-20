/**
 * Envío de documentos al cliente por correo y WhatsApp (P5-05). Contrato:
 * `docs/api-contract.md`, "Envío de documentos al cliente".
 */

import { apiArchivo, apiFetch } from './api';

export type Canal = 'correo' | 'whatsapp';
export type TipoDocumento =
  | 'factura' | 'cfdi' | 'retencion' | 'opinion' | 'constancia' | 'declaracion' | 'acuse'
  | 'otro' | 'recibo_nomina';

export interface Contacto {
  id: number;
  nombre: string;
  puesto: string;
  correo: string;
  telefono: string;
  consentimiento_whatsapp: boolean;
  consentimiento_en: string | null;
  activo: boolean;
}

export type ContactoCaptura = Omit<Contacto, 'id' | 'consentimiento_en'>;

export interface DocumentoEnviable {
  tipo: TipoDocumento;
  ref: string;
  nombre_tipo: string;
  descripcion: string;
  fecha: string | null;
  estado: string;
}

export interface Envio {
  id: number;
  contacto_id: number | null;
  canal: Canal;
  destino: string;
  tipo_documento: TipoDocumento;
  ref: string;
  descripcion: string;
  estado: 'pendiente' | 'enviado' | 'fallido' | 'rebotado';
  intentos: number;
  error: string;
  enviado_en: string | null;
}

export interface EstadoEnvios {
  envios: Envio[];
  resumen: Record<string, number>;
  trabajo: { id: number; estado: string; error: string | null } | null;
  omitidos?: { contacto: string; canal: Canal; motivo: string }[];
}

const base = (clave: string) => `/clientes/${encodeURIComponent(clave)}`;

export async function listarContactos(clave: string): Promise<Contacto[]> {
  return (await apiFetch<{ contactos: Contacto[] }>(`${base(clave)}/contactos`)).contactos;
}

export async function guardarContacto(clave: string, c: ContactoCaptura, id?: number): Promise<Contacto> {
  const ruta = id ? `${base(clave)}/contactos/${id}` : `${base(clave)}/contactos`;
  return (await apiFetch<{ contacto: Contacto }>(ruta, { method: id ? 'PUT' : 'POST', json: c })).contacto;
}

export async function borrarContacto(clave: string, id: number): Promise<void> {
  await apiFetch(`${base(clave)}/contactos/${id}`, { method: 'DELETE' });
}

export async function documentosEnviables(clave: string): Promise<DocumentoEnviable[]> {
  return (await apiFetch<{ documentos: DocumentoEnviable[] }>(`${base(clave)}/documentos-enviables`)).documentos;
}

export async function subirAlExpediente(
  clave: string, tipo: 'declaracion' | 'acuse' | 'otro', descripcion: string, periodo: string, archivo: File,
): Promise<void> {
  const fd = new FormData();
  fd.append('tipo', tipo);
  fd.append('descripcion', descripcion);
  fd.append('periodo', periodo);
  fd.append('archivo', archivo);
  await apiFetch(`${base(clave)}/expediente`, { method: 'POST', body: fd });
}

export async function descargarDocumento(clave: string, tipo: TipoDocumento, ref: string, indice = 0): Promise<Blob> {
  return apiArchivo(`${base(clave)}/documentos/${tipo}/${encodeURIComponent(ref)}/${indice}`);
}

export async function enviarDocumentos(
  clave: string, documentos: { tipo: TipoDocumento; ref: string }[], canales: Canal[],
  contactos: number[], mensaje: string,
): Promise<EstadoEnvios> {
  return apiFetch(`${base(clave)}/envios`, { method: 'POST', json: { documentos, canales, contactos, mensaje } });
}

export async function estadoEnvios(clave: string): Promise<EstadoEnvios> {
  return apiFetch(`${base(clave)}/envios`);
}

export async function reenviar(clave: string, id: number): Promise<EstadoEnvios> {
  return apiFetch(`${base(clave)}/envios/${id}/reenviar`, { method: 'POST' });
}
