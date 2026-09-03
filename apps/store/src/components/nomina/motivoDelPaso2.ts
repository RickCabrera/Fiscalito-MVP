/**
 * Por qué el paso 2 de la nómina está bloqueado, en palabras. (O-01)
 *
 * VIVE APARTE POR DOS RAZONES, Y LAS DOS SON DE PESO
 * --------------------------------------------------
 * 1. **Los motivos se duplicaron por modo.** Cuatro de los cinco hablaban de
 *    "cartera", "cliente" y "tu lista de clientes", y en la nómina de la
 *    empresa única eso nombra cosas que no existen. Anidar dos ternarios por
 *    motivo dentro de un atributo JSX era ilegible; aquí se lee de un vistazo
 *    que **ningún texto del modo empresa dice cartera**, que es la mitad
 *    negativa del criterio de O-01.
 * 2. `NominaClientePage.tsx` se pasaba de las 300 líneas de
 *    `apps/store/CLAUDE.md` con la función dentro.
 *
 * EL ORDEN IMPORTA. Se dice el motivo más específico primero: si se
 * invirtiera, "espera a que cargue" taparía "falta la prima de riesgo", que es
 * lo único que el operador puede arreglar por su cuenta.
 */

import type { useNominaCliente } from './useNominaCliente';
import { modoEmpresaUnica } from '../../services/modoEmpresa';

export function motivoDelPaso2(
  n: ReturnType<typeof useNominaCliente>,
  estado: { faltaEmpresa: boolean; sinPeriodo: boolean },
): string {
  const empresa = modoEmpresaUnica();

  if (estado.faltaEmpresa) {
    return (
      `Falta ${n.faltaDeLaEmpresa.join(' y ')} de la empresa. Sin eso no se pueden ` +
      'calcular las cuotas patronales: captúralo en Perfil → Configuración de empresa.'
    );
  }
  // `ajenoALaCartera` es inalcanzable en modo empresa única —el único id que
  // resuelve es el de la empresa— pero su texto se escribe igual: un motivo que
  // depende de que una rama sea inalcanzable es el que reaparece con un mensaje
  // absurdo el día que deje de serlo.
  if (n.ajenoALaCartera) {
    return empresa
      ? 'Esta nómina no es de tu empresa, así que no se puede calcular aquí.'
      : 'Este cliente no está en la cartera de tu cuenta, así que su nómina no se ' +
        'puede calcular aquí: la plantilla saldría del catálogo de demostración y no ' +
        'de tus empleados. Ábrelo desde tu lista de clientes.';
  }
  if (estado.sinPeriodo) {
    return empresa
      ? 'Todavía no hay un periodo propuesto — captura las fechas de inicio y fin arriba ' +
        'y el paso se habilita.'
      : 'Este cliente todavía no tiene un periodo sugerido — captura las fechas de ' +
        'inicio y fin arriba y el paso se habilita. (Pasa con el primer cliente de ' +
        'una cuenta cuando el servicio no respondió al cargar la cartera.)';
  }
  if (n.carteraCargando) {
    return empresa
      ? 'Cargando tus empleados… El cierre espera a saber con qué números del checador buscar.'
      : 'Cargando tu cartera… El cierre espera a saber con qué números del checador buscar.';
  }
  return empresa
    ? 'Espera a que carguen los empleados.'
    : 'Espera a que cargue la plantilla del cliente.';
}
