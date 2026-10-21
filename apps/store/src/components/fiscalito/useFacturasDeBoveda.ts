/**
 * Los CFDI de un periodo, leídos de la bóveda del cliente (P1-06).
 *
 * Una sola costura para Fiscalito y Contabilito: cada tab dice de qué cliente y de
 * qué periodo, y aquí se pide `GET /boveda/clientes/{clave}/facturas-calculo`. La
 * respuesta guarda la LLAVE con que se pidió (cliente, periodo, intento) y lo demás
 * se deriva comparando —mismo patrón que `BovedaPage`—: una respuesta lenta del
 * periodo anterior no se pinta sobre el nuevo y no hay `setState` sincrónico en el
 * efecto.
 */

import { useCallback, useEffect, useState } from 'react';
import { facturasParaCalculo, type FacturasDeBoveda } from '../../services/bovedaApi';

export interface PeriodoBoveda {
  /** AAAA-MM-DD, inclusivo. */
  desde: string;
  /** AAAA-MM-DD, inclusivo. */
  hasta: string;
}

export type EstadoBoveda =
  | { estado: 'sin-cliente' }
  | { estado: 'cargando' }
  | { estado: 'error'; error: string }
  | { estado: 'listo'; datos: FacturasDeBoveda };

const dos = (n: number) => String(n).padStart(2, '0');

/** Del día 1 al último del mes. */
export function periodoDeMes(anio: number, mes: number): PeriodoBoveda {
  const ultimo = new Date(Date.UTC(anio, mes, 0)).getUTCDate();
  return { desde: `${anio}-${dos(mes)}-01`, hasta: `${anio}-${dos(mes)}-${dos(ultimo)}` };
}

/** El ejercicio completo. */
export function periodoDeAnio(anio: number): PeriodoBoveda {
  return { desde: `${anio}-01-01`, hasta: `${anio}-12-31` };
}

interface Carga {
  llave: string;
  datos: FacturasDeBoveda | null;
  error: string | null;
}

/**
 * `activo = false` no pide nada (el tab está en "archivos sueltos"): la bóveda no se
 * consulta para una fuente que nadie está usando.
 */
export function useFacturasDeBoveda(
  clave: string | null,
  periodo: PeriodoBoveda | null,
  activo = true,
): EstadoBoveda & { recargar: () => void } {
  const [intento, setIntento] = useState(0);
  const [carga, setCarga] = useState<Carga | null>(null);
  const desde = periodo?.desde ?? '';
  const hasta = periodo?.hasta ?? '';
  const llave = clave && desde && hasta && activo ? `${clave}|${desde}|${hasta}|${intento}` : null;

  useEffect(() => {
    if (!llave || !clave) return;
    let cancelado = false;
    facturasParaCalculo(clave, { desde, hasta })
      .then((datos) => { if (!cancelado) setCarga({ llave, datos, error: null }); })
      .catch((e: unknown) => {
        if (cancelado) return;
        setCarga({
          llave, datos: null,
          error: e instanceof Error ? e.message : 'No se pudo leer la bóveda del cliente.',
        });
      });
    return () => { cancelado = true; };
  }, [llave, clave, desde, hasta]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  if (!clave) return { estado: 'sin-cliente', recargar };
  const vigente = carga?.llave === llave ? carga : null;
  if (!vigente) return { estado: 'cargando', recargar };
  if (vigente.error !== null || !vigente.datos) {
    return { estado: 'error', error: vigente.error ?? 'Sin datos.', recargar };
  }
  return { estado: 'listo', datos: vigente.datos, recargar };
}
