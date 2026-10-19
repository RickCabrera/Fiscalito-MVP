/**
 * Por qué el paso 2 de la nómina está bloqueado, en palabras.
 *
 * Vive aparte porque `NominaClientePage.tsx` se pasaba de las 300 líneas de
 * `apps/store/CLAUDE.md` con la función dentro.
 *
 * EL ORDEN IMPORTA. Se dice el motivo más específico primero: si se
 * invirtiera, "espera a que cargue" taparía un motivo que el operador sí puede
 * arreglar por su cuenta.
 */

import type { useNominaCliente } from './useNominaCliente';

export function motivoDelPaso2(
  n: ReturnType<typeof useNominaCliente>,
  estado: { sinPeriodo: boolean },
): string {
  if (n.ajenoALaCartera) {
    return (
      'Este cliente no está en la cartera de tu cuenta, así que su nómina no se ' +
      'puede calcular aquí: la plantilla saldría del catálogo de demostración y no ' +
      'de tus empleados. Ábrelo desde tu lista de clientes.'
    );
  }
  if (estado.sinPeriodo) {
    return (
      'Este cliente todavía no tiene un periodo sugerido — captura las fechas de ' +
      'inicio y fin arriba y el paso se habilita. (Pasa con el primer cliente de ' +
      'una cuenta cuando el servicio no respondió al cargar la cartera.)'
    );
  }
  if (n.carteraCargando) {
    return 'Cargando tu cartera… El cierre espera a saber con qué números del checador buscar.';
  }
  return 'Espera a que cargue la plantilla del cliente.';
}
