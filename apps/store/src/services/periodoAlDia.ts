/**
 * El periodo sugerido de cada cliente, al día y según SU periodicidad. (O-03)
 *
 * Vivía en `carteraFirestore.ts`; P0-01 retiró ese archivo y esto se quedó, porque no
 * depende de quién guarde la cartera sino de que lo guardado es un SNAPSHOT.
 *
 * EL PERIODO SUGERIDO ES DERIVADO, NO DATO DEL CLIENTE
 * ----------------------------------------------------
 * Es el último periodo ya terminado, y el backend lo reevalúa en cada request. Lo que
 * quedó guardado es del momento del alta: dos semanas después, cada cliente nacería con
 * un periodo vencido. `periodo_sugerido` alimenta la `fecha_pago` que va al motor —de
 * la que dependen UMA, salario mínimo, la tarifa del Anexo 8 y el transitorio de enero
 * del subsidio (§D18)—, así que servir el snapshot no es cosmético.
 *
 * SE PIDE UNO POR CLAVE, NO UNO POR CLIENTE
 * -----------------------------------------
 * Los clientes que comparten periodicidad comparten periodo.
 *
 * **Nunca se rompe por esto**: si el backend no responde —o se cuelga, de ahí la
 * cota— se queda el snapshot, que es peor que estar al día pero mejor que no tener
 * cartera. Y una clave sin tarifa publicada (§D10, 422) deja a ESE cliente con su
 * snapshot: darle el periodo de otra periodicidad sería el bug que O-03 cerró.
 */

import { obtenerPeriodoSugerido } from './despachoApi';
import type { ClienteCartera } from './carteraApi';

/** Ningún refresco de periodo puede colgar la carga de la cartera más que esto. */
const TIMEOUT_MS = 2500;

function conTimeout<T>(promesa: Promise<T>, que: string, ms = TIMEOUT_MS): Promise<T> {
  let temporizador: ReturnType<typeof setTimeout>;
  return Promise.race([
    promesa,
    new Promise<T>((_, rechazar) => {
      temporizador = setTimeout(() => rechazar(new Error(`${que} tardó más de ${ms} ms`)), ms);
    }),
  ]).finally(() => clearTimeout(temporizador));
}

export async function conPeriodoAlDia(clientes: ClienteCartera[]): Promise<ClienteCartera[]> {
  if (clientes.length === 0) return clientes;

  /**
   * Un cliente guardado antes de que existiera el campo no trae clave: cae a `'04'`,
   * el mismo default de `ClienteCarteraSchema` — la app nunca ha llevado otra cosa
   * que quincenal.
   */
  const claveDe = (c: ClienteCartera) => c.clave_periodicidad || '04';
  const claves = [...new Set(clientes.map(claveDe))];
  const porClave = new Map<string, ClienteCartera['periodo_sugerido']>();

  await Promise.all(
    claves.map(async (clave) => {
      try {
        const { periodo } = await conTimeout(
          obtenerPeriodoSugerido(clave),
          `El periodo sugerido (${clave})`,
        );
        porClave.set(clave, periodo);
      } catch {
        // Sin tarifa (422) o API caída: ese cliente se queda con su snapshot.
      }
    }),
  );

  return clientes.map((c) => {
    const alDia = porClave.get(claveDe(c));
    return alDia ? { ...c, periodo_sugerido: alDia } : c;
  });
}
