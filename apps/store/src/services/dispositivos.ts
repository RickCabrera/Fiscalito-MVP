/**
 * Los dispositivos del cliente, por la API. (R-04 → R-09 → P0-01)
 *
 * Vivían en Firestore escritos por el navegador (`dispositivosFirestore.ts`). Ahora el
 * backend es su dueño: `/api/v1/cartera/clientes/{id}/dispositivos`, guardados en SQL y
 * filtrados por despacho. El modelo y sus validaciones siguen en `dispositivosApi.ts`;
 * el backend aplica las mismas.
 *
 * No habla con ningún aparato: la IP es un dato de ficha (D-08).
 */

import { apiFetch } from './api';
import type { DispositivoChecador } from './dispositivosApi';

const TIMEOUT_MS = 10000;

const base = (clienteId: string) =>
  `/cartera/clientes/${encodeURIComponent(clienteId)}/dispositivos`;

/** Lo que se guarda: todo menos el `id`, que es la llave y va en la URL. */
function cuerpo(d: DispositivoChecador): Omit<DispositivoChecador, 'id'> {
  return {
    nombre: d.nombre,
    ip: d.ip,
    puerto: d.puerto,
    marca: d.marca,
    modelo: d.modelo,
    serial: d.serial,
    employee_nos: d.employee_nos,
    notas: d.notas,
  };
}

export async function listarDispositivos(clienteId: string): Promise<DispositivoChecador[]> {
  const r = await apiFetch<{ dispositivos: DispositivoChecador[] }>(base(clienteId), {
    timeoutMs: TIMEOUT_MS,
  });
  return r.dispositivos;
}

/**
 * Alta (sin `id`: lo genera el backend) o edición. Devuelve el id.
 *
 * El id no se deriva del nombre ni del serial: los dos son editables, y un id derivado
 * convertiría un cambio de nombre en un dispositivo nuevo con el anterior huérfano.
 */
export async function guardarDispositivo(
  clienteId: string,
  dispositivo: DispositivoChecador,
): Promise<string> {
  if (dispositivo.id) {
    await apiFetch(`${base(clienteId)}/${encodeURIComponent(dispositivo.id)}`, {
      method: 'PUT',
      json: cuerpo(dispositivo),
      timeoutMs: TIMEOUT_MS,
    });
    return dispositivo.id;
  }
  const r = await apiFetch<{ id: string }>(base(clienteId), {
    method: 'POST',
    json: cuerpo(dispositivo),
    timeoutMs: TIMEOUT_MS,
  });
  return r.id;
}

export async function borrarDispositivo(clienteId: string, id: string): Promise<void> {
  await apiFetch(`${base(clienteId)}/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    timeoutMs: TIMEOUT_MS,
  });
}
